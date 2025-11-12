# FMS Integration Plan
## Media Scheduler ↔ Ruby on Rails FMS System

**Date**: November 2025
**Author**: Ray Rierson
**FMS Developer**: Alex
**Purpose**: Technical planning document for integrating Media Scheduler with FMS system

---

## Table of Contents

1. [Integration Overview](#integration-overview)
2. [Current Architecture](#current-architecture)
3. [Data Mapping: Scheduler → FMS API](#data-mapping-scheduler--fms-api)
4. [Status Flow & FMS Actions](#status-flow--fms-actions)
5. [Backend Implementation](#backend-implementation)
6. [Frontend Changes](#frontend-changes)
7. [Nightly Data Sync Automation](#nightly-data-sync-automation)
8. [Questions for Alex (Blockers)](#questions-for-alex-blockers)
9. [Testing Checklist](#testing-checklist)
10. [Implementation Phases](#implementation-phases)
11. [Security & Configuration](#security--configuration)

---

## Integration Overview

### Goals

1. **Embed Media Scheduler** in FMS as iframe (hosted on Render)
2. **Automate Data Sync** from FMS → Scheduler (nightly, replacing manual CSV imports)
3. **Enable Bi-Directional Workflow**:
   - User marks assignment as "Requested" (magenta) → Creates FMS vehicle request
   - User deletes magenta assignment → Deletes FMS vehicle request
   - User "unrequests" magenta → Deletes FMS vehicle request (but keeps assignment in scheduler)
   - FMS approves request → Shows as active (blue) in scheduler

### Current Setup

- **Scheduler**: FastAPI (Python) + React + Supabase PostgreSQL
- **Deployment**: Render (https://media-scheduler.onrender.com - pending)
- **FMS**: Ruby on Rails (https://fms.driveshop.com)
- **Data Flow**: Manual CSV imports via FMS report URLs

### Integration Points

- **FMS → Scheduler**: CSV exports (vehicles, partners, loan history, current activity)
- **Scheduler → FMS**: REST API calls (create/delete vehicle requests)
- **iframe**: FMS embeds scheduler in tab with shared authentication context

---

## Current Architecture

### Tech Stack

**Backend**:
- Framework: FastAPI (Python 3.12)
- Database: Supabase (PostgreSQL cloud-hosted)
- HTTP Client: httpx (async)
- Scheduler: APScheduler (for nightly sync)

**Frontend**:
- Framework: React 19 with Vite
- Styling: Tailwind CSS
- Key Libraries: @dnd-kit/core (drag and drop)

**Deployment**:
- Hosting: Render
- Environment: Production + Staging

### Database Schema (Key Tables)

#### `scheduled_assignments`
```sql
CREATE TABLE scheduled_assignments (
    assignment_id SERIAL PRIMARY KEY,
    vin VARCHAR(17) NOT NULL,              -- Vehicle VIN
    person_id INTEGER NOT NULL,            -- FMS media partner ID
    start_day DATE NOT NULL,               -- Loan start date
    end_day DATE NOT NULL,                 -- Loan end date (start + 7 days)
    make VARCHAR(100),
    model VARCHAR(255),
    office VARCHAR(100),                   -- FMS office/location
    partner_name VARCHAR(255),
    status VARCHAR(50) DEFAULT 'planned',  -- KEY: planned/manual/requested/active
    fms_request_id INTEGER,                -- ⭐ NEW: Stores FMS request ID
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
);
```

#### `vehicles`
```sql
CREATE TABLE vehicles (
    vin VARCHAR(17) PRIMARY KEY,
    vehicle_id INTEGER,                    -- ⚠️ CRITICAL: FMS internal vehicle ID
    make VARCHAR(100),
    model VARCHAR(255),
    year INTEGER,
    office VARCHAR(100),
    fleet VARCHAR(50),
    registration_exp DATE,
    insurance_exp DATE,
    current_mileage INTEGER,
    notes TEXT
);
```

#### `media_partners`
```sql
CREATE TABLE media_partners (
    person_id INTEGER PRIMARY KEY,         -- FMS contact/partner ID
    name VARCHAR(255),
    address TEXT,
    office VARCHAR(100),
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6),
    preferred_day_of_week INTEGER,
    notes_instructions TEXT
);
```

#### `current_activity`
```sql
CREATE TABLE current_activity (
    activity_id VARCHAR(50) PRIMARY KEY,   -- FMS loan/activity ID
    person_id INTEGER,
    vehicle_vin VARCHAR(17),
    activity_type VARCHAR(100),
    start_date DATE,
    end_date DATE,
    partner_address TEXT,
    region VARCHAR(100)
);
```

### Current CSV Import Endpoints

| Endpoint | Purpose | FMS Export URL |
|----------|---------|----------------|
| `POST /ingest/vehicles/url` | Import active vehicles | https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/active_vehicles.rpt&init=csv |
| `POST /ingest/media_partners/url` | Import media partners | https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/media_partners.rpt&init=csv |
| `POST /ingest/loan_history/url` | Import historical loans | https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/loan_history.rpt&init=csv |
| `POST /ingest/current_activity/url` | Import active loans | https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/current_activity.rpt&init=csv |

---

## Data Mapping: Scheduler → FMS API

### What We Have (Scheduler Data)

```javascript
{
  assignment_id: 123,              // Internal scheduler ID
  vin: "1HGBH41JXMN109186",       // Vehicle VIN
  person_id: 45678,                // Media partner FMS ID
  start_day: "2025-11-18",         // Loan start date
  end_day: "2025-11-25",           // Loan end date (always start + 7 days)
  make: "Toyota",
  model: "Camry",
  office: "Los Angeles",
  partner_name: "John Smith",
  status: "requested"              // ← TRIGGER for FMS integration
}
```

### What FMS API Expects (from Alex's email)

**Endpoint**: `POST https://fms.driveshop.com/api/v1/vehicle_requests`
**Authentication**: `Authorization: Bearer 0b36ae1b3bebba027cf2ccd9049afa75` (production)

```json
{
  "request": {
    // REQUIRED FIELDS (only 3)
    "requestor_id": ???,                    // ⚠️ BLOCKER: Need from Alex
    "start_date": "2025-11-18",             // ✅ Have: assignment.start_day
    "end_date": "2025-11-25",               // ✅ Have: assignment.end_day

    // OPTIONAL FIELDS (but useful)
    "activity_to": "John Smith",            // ✅ Have: assignment.partner_name
    "reason": "Scheduled media loan",       // ✅ Static text
    "requestor_notes": null,
    "activity_type_id": ???,                // ⚠️ Need from Alex (e.g., 5 for "Media Loan")
    "activity_type_subcategory_id": ???,   // ⚠️ Need from Alex
    "relocate_transportation_method_id": 1,
    "loanee_id": 45678,                     // ✅ Have: assignment.person_id
    "notes": null,
    "delivery_notes": null,
    "pickup_notes": null,
    "message_to_requestor": null,

    // VEHICLE ASSIGNMENT
    "requests_vehicles": [
      {
        "vehicle_id": 789,                  // ⚠️ CRITICAL: Must get from vehicles.vehicle_id
        "notes": "Toyota Camry (VIN: 1HG...)"
      }
    ]
  }
}
```

### Critical Data Join

To get `vehicle_id` from `vin`:

```sql
SELECT
    sa.assignment_id,
    sa.person_id as loanee_id,
    sa.start_day as start_date,
    sa.end_day as end_date,
    sa.partner_name as activity_to,
    v.vehicle_id,           -- ← This is what FMS needs!
    v.make,
    v.model,
    sa.vin
FROM scheduled_assignments sa
JOIN vehicles v ON sa.vin = v.vin
WHERE sa.status = 'requested'
  AND sa.office = 'Los Angeles';
```

**Assumption**: The `vehicle_id` in our `vehicles` table (imported from FMS CSV) matches what FMS expects in the API.
**TODO**: Confirm with Alex.

### FMS Delete Endpoint

**Endpoint**: `DELETE https://fms.driveshop.com/api/v1/vehicle_requests/{request_id}`
**Authentication**: Same bearer token

**Note**: Alex mentioned this endpoint "still needs to be done" - confirm completion status.

---

## Status Flow & FMS Actions

### Status States in Scheduler

| Status | Visual | Meaning | Source |
|--------|--------|---------|--------|
| `planned` | Green solid bar | Generated by optimizer | Scheduler algorithm |
| `manual` | Green dashed bar | Manually created by user | User action |
| `requested` | **Magenta bar** | Sent to FMS for approval | User clicks "Request" |
| `active` | Blue bar | Confirmed/active in FMS | Synced from `current_activity` CSV |

### Complete Status Transition Matrix

| User Action | From Status | To Status | Visual Change | FMS API Call | Notes |
|-------------|-------------|-----------|---------------|--------------|-------|
| Click "Request" | `planned` | `requested` | Green → Magenta | **POST** (create) | Single item |
| Click "Request" | `manual` | `requested` | Green dash → Magenta | **POST** (create) | Single item |
| Click "Unrequest" | `requested` | `planned` | Magenta → Green | **DELETE** | Keeps assignment in scheduler |
| Click "Unrequest" | `requested` | `manual` | Magenta → Green dash | **DELETE** | Keeps assignment in scheduler |
| Click "Delete" | `requested` | *removed* | Disappears | **DELETE** | Removes from scheduler |
| Click "Delete" | `planned` | *removed* | Disappears | None | Only local deletion |
| Click "Delete" | `manual` | *removed* | Disappears | None | Only local deletion |
| FMS approves | `requested` | `active` | Magenta → Blue | None | Via nightly sync |
| **Bulk Request** | Multiple `planned/manual` | `requested` | Green → Magenta | **POST** (loop) | Chain Builder |
| **Bulk Unrequest** | Multiple `requested` | `planned/manual` | Magenta → Green | **DELETE** (loop) | Chain Builder |
| **Bulk Delete** | Multiple any | *removed* | Disappears | **DELETE** (loop for requested) | Chain Builder |

### Key Insights

1. **"Unrequest" = Delete from FMS, Keep in Scheduler**
   - User is cancelling the request, not the assignment
   - Assignment reverts to green (editable)
   - FMS request is deleted

2. **All Bulk Operations Loop Individually**
   - No batch API available
   - Each assignment triggers separate FMS API call
   - Partial failures handled gracefully

3. **Only "Requested" Status Triggers FMS**
   - Green items (`planned`/`manual`) are local only
   - Blue items (`active`) are read-only from FMS sync

---

## Backend Implementation

### New Files to Create

#### 1. `backend/app/routers/fms_integration.py`

```python
from fastapi import APIRouter, HTTPException
from typing import List
import httpx
import os

router = APIRouter(prefix="/api/fms", tags=["FMS Integration"])

# Environment configuration
FMS_BASE_URL = os.getenv("FMS_BASE_URL", "https://fms.driveshop.com")
FMS_TOKEN = os.getenv("FMS_PRODUCTION_TOKEN")
FMS_REQUESTOR_ID = os.getenv("FMS_REQUESTOR_ID")  # TODO: Get from Alex
FMS_ACTIVITY_TYPE_ID = os.getenv("FMS_ACTIVITY_TYPE_ID")  # TODO: Get from Alex


# ============================================
# SINGLE OPERATIONS
# ============================================

@router.post("/create-vehicle-request/{assignment_id}")
async def create_fms_vehicle_request(assignment_id: int):
    """
    Create FMS vehicle request when user marks assignment as 'requested'
    Called when: User clicks "Request" button (green → magenta)
    """

    # 1. Fetch assignment with vehicle details (JOIN with vehicles table)
    query = """
        SELECT
            sa.assignment_id,
            sa.person_id,
            sa.start_day,
            sa.end_day,
            sa.partner_name,
            sa.vin,
            v.vehicle_id,
            v.make,
            v.model
        FROM scheduled_assignments sa
        JOIN vehicles v ON sa.vin = v.vin
        WHERE sa.assignment_id = $1
          AND sa.status = 'requested'
    """

    result = await db_service.supabase.rpc('execute_sql', {
        'query': query,
        'params': [assignment_id]
    }).execute()

    if not result.data:
        raise HTTPException(404, "Assignment not found or not in 'requested' status")

    assignment = result.data[0]

    # 2. Build FMS payload
    fms_payload = {
        "request": {
            # Required
            "requestor_id": FMS_REQUESTOR_ID,
            "start_date": str(assignment['start_day']),
            "end_date": str(assignment['end_day']),

            # Optional but helpful
            "activity_to": assignment['partner_name'],
            "reason": "Scheduled media partner loan",
            "activity_type_id": FMS_ACTIVITY_TYPE_ID,
            "loanee_id": assignment['person_id'],

            # Vehicle assignment
            "requests_vehicles": [
                {
                    "vehicle_id": assignment['vehicle_id'],
                    "notes": f"{assignment['make']} {assignment['model']} (VIN: {assignment['vin']})"
                }
            ]
        }
    }

    # 3. Send to FMS
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{FMS_BASE_URL}/api/v1/vehicle_requests",
            json=fms_payload,
            headers={
                "Authorization": f"Bearer {FMS_TOKEN}",
                "Content-Type": "application/json"
            }
        )

        if response.status_code not in [200, 201]:
            raise HTTPException(500, f"FMS API error: {response.text}")

        fms_response = response.json()

        # 4. Store FMS request ID for future reference
        fms_request_id = fms_response.get('id') or fms_response.get('request_id')

        await db_service.supabase.table('scheduled_assignments').update({
            'fms_request_id': fms_request_id,
            'updated_at': 'now()'
        }).eq('assignment_id', assignment_id).execute()

        return {
            "success": True,
            "fms_request_id": fms_request_id,
            "message": "Vehicle request created in FMS"
        }


@router.delete("/delete-vehicle-request/{assignment_id}")
async def delete_fms_vehicle_request(assignment_id: int):
    """
    Delete FMS vehicle request when user deletes magenta assignment
    Called when: User deletes a 'requested' assignment
    """

    # 1. Get FMS request ID
    result = await db_service.supabase.table('scheduled_assignments') \
        .select('fms_request_id') \
        .eq('assignment_id', assignment_id) \
        .execute()

    if not result.data or not result.data[0].get('fms_request_id'):
        raise HTTPException(404, "No FMS request ID found for this assignment")

    fms_request_id = result.data[0]['fms_request_id']

    # 2. Delete from FMS
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.delete(
            f"{FMS_BASE_URL}/api/v1/vehicle_requests/{fms_request_id}",
            headers={"Authorization": f"Bearer {FMS_TOKEN}"}
        )

        if response.status_code not in [200, 204]:
            raise HTTPException(500, f"FMS deletion failed: {response.text}")

    # 3. Delete from scheduler database
    await db_service.supabase.table('scheduled_assignments') \
        .delete() \
        .eq('assignment_id', assignment_id) \
        .execute()

    return {
        "success": True,
        "message": "Request deleted from FMS and scheduler"
    }


# ============================================
# BULK OPERATIONS (Chain Builder)
# ============================================

@router.post("/bulk-create-vehicle-requests")
async def bulk_create_fms_vehicle_requests(assignment_ids: List[int]):
    """
    Bulk request multiple assignments (Green → Magenta)
    Loops through each and calls FMS CREATE API individually
    """
    results = []

    for assignment_id in assignment_ids:
        try:
            # Check if assignment can be requested
            result = await db_service.supabase.table('scheduled_assignments') \
                .select('status, assignment_id') \
                .eq('assignment_id', assignment_id) \
                .execute()

            if not result.data:
                results.append({
                    "assignment_id": assignment_id,
                    "success": False,
                    "error": "Assignment not found"
                })
                continue

            assignment = result.data[0]

            # Only request if status is 'planned' or 'manual'
            if assignment['status'] not in ['planned', 'manual']:
                results.append({
                    "assignment_id": assignment_id,
                    "success": False,
                    "error": f"Cannot request assignment with status '{assignment['status']}'"
                })
                continue

            # Update status to 'requested'
            await db_service.supabase.table('scheduled_assignments').update({
                'status': 'requested',
                'updated_at': 'now()'
            }).eq('assignment_id', assignment_id).execute()

            # Create FMS request
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    fms_response = await client.post(
                        f"http://localhost:8081/api/fms/create-vehicle-request/{assignment_id}"
                    )

                    if fms_response.status_code != 200:
                        # Rollback status change
                        await db_service.supabase.table('scheduled_assignments').update({
                            'status': assignment['status']
                        }).eq('assignment_id', assignment_id).execute()

                        results.append({
                            "assignment_id": assignment_id,
                            "success": False,
                            "error": f"FMS API error: {fms_response.status_code}"
                        })
                        continue

                results.append({
                    "assignment_id": assignment_id,
                    "success": True,
                    "created_in_fms": True
                })

            except Exception as e:
                # Rollback on error
                await db_service.supabase.table('scheduled_assignments').update({
                    'status': assignment['status']
                }).eq('assignment_id', assignment_id).execute()

                results.append({
                    "assignment_id": assignment_id,
                    "success": False,
                    "error": f"FMS request failed: {str(e)}"
                })

        except Exception as e:
            results.append({
                "assignment_id": assignment_id,
                "success": False,
                "error": str(e)
            })

    # Summary
    success_count = sum(1 for r in results if r['success'])
    failure_count = len(results) - success_count

    return {
        "total": len(assignment_ids),
        "succeeded": success_count,
        "failed": failure_count,
        "results": results
    }


@router.post("/bulk-unrequest-vehicle-requests")
async def bulk_unrequest_fms_vehicle_requests(assignment_ids: List[int]):
    """
    Bulk unrequest multiple assignments (Magenta → Green)
    Loops through each and calls FMS DELETE API individually
    Keeps assignments in scheduler
    """
    results = []

    for assignment_id in assignment_ids:
        try:
            # Check if assignment is 'requested'
            result = await db_service.supabase.table('scheduled_assignments') \
                .select('status, fms_request_id') \
                .eq('assignment_id', assignment_id) \
                .execute()

            if not result.data:
                results.append({
                    "assignment_id": assignment_id,
                    "success": False,
                    "error": "Assignment not found"
                })
                continue

            assignment = result.data[0]

            # Only unrequest if status is 'requested'
            if assignment['status'] != 'requested':
                results.append({
                    "assignment_id": assignment_id,
                    "success": False,
                    "error": f"Cannot unrequest assignment with status '{assignment['status']}'"
                })
                continue

            # Delete from FMS first
            fms_request_id = assignment.get('fms_request_id')
            if fms_request_id:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.delete(
                        f"{FMS_BASE_URL}/api/v1/vehicle_requests/{fms_request_id}",
                        headers={"Authorization": f"Bearer {FMS_TOKEN}"}
                    )

                    if response.status_code not in [200, 204]:
                        results.append({
                            "assignment_id": assignment_id,
                            "success": False,
                            "error": f"FMS deletion failed: {response.status_code}"
                        })
                        continue

            # Update status back to 'manual'
            await db_service.supabase.table('scheduled_assignments').update({
                'status': 'manual',
                'fms_request_id': None,
                'updated_at': 'now()'
            }).eq('assignment_id', assignment_id).execute()

            results.append({
                "assignment_id": assignment_id,
                "success": True,
                "deleted_from_fms": True
            })

        except Exception as e:
            results.append({
                "assignment_id": assignment_id,
                "success": False,
                "error": str(e)
            })

    # Summary
    success_count = sum(1 for r in results if r['success'])
    failure_count = len(results) - success_count

    return {
        "total": len(assignment_ids),
        "succeeded": success_count,
        "failed": failure_count,
        "results": results
    }


@router.post("/bulk-delete-vehicle-requests")
async def bulk_delete_fms_vehicle_requests(assignment_ids: List[int]):
    """
    Bulk delete multiple assignments
    Loops through each - calls FMS DELETE for 'requested' items
    Removes all from scheduler
    """
    results = []

    for assignment_id in assignment_ids:
        try:
            # Check assignment status
            result = await db_service.supabase.table('scheduled_assignments') \
                .select('status, fms_request_id') \
                .eq('assignment_id', assignment_id) \
                .execute()

            if not result.data:
                results.append({
                    "assignment_id": assignment_id,
                    "success": False,
                    "error": "Assignment not found"
                })
                continue

            assignment = result.data[0]

            # If requested, delete from FMS
            if assignment['status'] == 'requested':
                fms_request_id = assignment.get('fms_request_id')

                if fms_request_id:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.delete(
                            f"{FMS_BASE_URL}/api/v1/vehicle_requests/{fms_request_id}",
                            headers={"Authorization": f"Bearer {FMS_TOKEN}"}
                        )

                        if response.status_code not in [200, 204]:
                            results.append({
                                "assignment_id": assignment_id,
                                "success": False,
                                "error": f"FMS deletion failed: {response.status_code}"
                            })
                            continue

            # Delete from scheduler database
            await db_service.supabase.table('scheduled_assignments') \
                .delete() \
                .eq('assignment_id', assignment_id) \
                .execute()

            results.append({
                "assignment_id": assignment_id,
                "success": True,
                "deleted_from_fms": assignment['status'] == 'requested'
            })

        except Exception as e:
            results.append({
                "assignment_id": assignment_id,
                "success": False,
                "error": str(e)
            })

    # Summary
    success_count = sum(1 for r in results if r['success'])
    failure_count = len(results) - success_count

    return {
        "total": len(assignment_ids),
        "succeeded": success_count,
        "failed": failure_count,
        "results": results
    }
```

### Modifications to Existing Files

#### 2. Update `backend/app/routers/calendar.py`

Modify the existing status change endpoint (around line 547):

```python
@router.patch("/change-assignment-status/{assignment_id}")
async def change_assignment_status(assignment_id: int, new_status: str):
    """
    UPDATED: Handles FMS integration when changing status
    - 'planned'/'manual' → 'requested' = CREATE FMS request
    - 'requested' → 'planned'/'manual' = DELETE FMS request (unrequest)
    """

    # 1. Get current assignment status
    result = await db_service.supabase.table('scheduled_assignments') \
        .select('status, fms_request_id') \
        .eq('assignment_id', assignment_id) \
        .execute()

    if not result.data:
        raise HTTPException(404, "Assignment not found")

    current_status = result.data[0]['status']
    fms_request_id = result.data[0].get('fms_request_id')

    # 2. SCENARIO 1: User is REQUESTING (Green → Magenta)
    if current_status in ['planned', 'manual'] and new_status == 'requested':
        await db_service.supabase.table('scheduled_assignments').update({
            'status': 'requested',
            'updated_at': 'now()'
        }).eq('assignment_id', assignment_id).execute()

        # Create FMS request
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                fms_response = await client.post(
                    f"http://localhost:8081/api/fms/create-vehicle-request/{assignment_id}"
                )

                if fms_response.status_code != 200:
                    # Rollback status change
                    await db_service.supabase.table('scheduled_assignments').update({
                        'status': current_status
                    }).eq('assignment_id', assignment_id).execute()

                    raise HTTPException(500, "Failed to create FMS request")
        except Exception as e:
            # Rollback on error
            await db_service.supabase.table('scheduled_assignments').update({
                'status': current_status
            }).eq('assignment_id', assignment_id).execute()
            raise HTTPException(500, f"FMS integration error: {str(e)}")

    # 3. SCENARIO 2: User is UNREQUESTING (Magenta → Green)
    elif current_status == 'requested' and new_status in ['planned', 'manual']:
        # Delete from FMS first
        if fms_request_id:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.delete(
                        f"{FMS_BASE_URL}/api/v1/vehicle_requests/{fms_request_id}",
                        headers={"Authorization": f"Bearer {FMS_TOKEN}"}
                    )

                    if response.status_code not in [200, 204]:
                        raise HTTPException(500, f"FMS deletion failed: {response.text}")
            except Exception as e:
                raise HTTPException(500, f"Failed to unrequest from FMS: {str(e)}")

        # Update local status
        await db_service.supabase.table('scheduled_assignments').update({
            'status': new_status,
            'fms_request_id': None,
            'updated_at': 'now()'
        }).eq('assignment_id', assignment_id).execute()

    # 4. SCENARIO 3: Other status changes (no FMS action)
    else:
        await db_service.supabase.table('scheduled_assignments').update({
            'status': new_status,
            'updated_at': 'now()'
        }).eq('assignment_id', assignment_id).execute()

    return {
        "success": True,
        "old_status": current_status,
        "new_status": new_status,
        "fms_action": "create" if new_status == 'requested' else ("delete" if current_status == 'requested' else "none")
    }
```

#### 3. Update `backend/app/main.py`

Add the new router:

```python
from app.routers import fms_integration

app.include_router(fms_integration.router)
```

#### 4. Database Migration

Add new column to store FMS request ID:

```sql
-- backend/migrations/add_fms_request_id.sql

ALTER TABLE scheduled_assignments
ADD COLUMN fms_request_id INTEGER;

CREATE INDEX idx_scheduled_assignments_fms_request_id
ON scheduled_assignments(fms_request_id);

COMMENT ON COLUMN scheduled_assignments.fms_request_id
IS 'FMS vehicle_request ID returned from POST /api/v1/vehicle_requests';
```

---

## Frontend Changes

### Files to Update

#### 1. `frontend/src/pages/Calendar.jsx`

Update request, unrequest, and delete handlers:

```javascript
// Request handler (green → magenta)
const requestAssignment = async (assignmentId) => {
  try {
    const response = await fetch(
      `${API_BASE}/api/calendar/change-assignment-status/${assignmentId}?new_status=requested`,
      { method: 'PATCH' }
    );

    if (!response.ok) {
      const error = await response.json();
      if (response.status === 500) {
        alert('Unable to connect to FMS. Your request was not sent. Please try again later.');
      } else {
        alert(`Failed to request assignment: ${error.detail}`);
      }
      return;
    }

    const result = await response.json();
    console.log('FMS action:', result.fms_action);

    await fetchCalendarData();
  } catch (err) {
    alert('Network error: Could not reach the server');
    console.error(err);
  }
};

// Unrequest handler (magenta → green)
const unrequestAssignment = async (assignmentId) => {
  try {
    const response = await fetch(
      `${API_BASE}/api/calendar/change-assignment-status/${assignmentId}?new_status=planned`,
      { method: 'PATCH' }
    );

    if (!response.ok) {
      const error = await response.json();
      alert(`Failed to unrequest assignment: ${error.detail}`);
      return;
    }

    const result = await response.json();
    console.log('FMS action:', result.fms_action);

    await fetchCalendarData();
  } catch (err) {
    alert('Network error: Could not reach the server');
    console.error(err);
  }
};

// Delete handler
const handleDeleteAssignment = async (assignmentId, status) => {
  let endpoint;

  if (status === 'requested') {
    // Magenta items: Delete from FMS + local database
    endpoint = `/api/fms/delete-vehicle-request/${assignmentId}`;
  } else {
    // Green items: Delete only from local database
    endpoint = `/api/calendar/assignment/${assignmentId}`;
  }

  try {
    const response = await fetch(
      `${API_BASE}${endpoint}`,
      { method: 'DELETE' }
    );

    if (!response.ok) {
      alert('Failed to delete assignment');
      return;
    }

    await fetchCalendarData();
  } catch (err) {
    alert('Network error: Could not delete assignment');
    console.error(err);
  }
};
```

#### 2. `frontend/src/pages/ChainBuilder.jsx`

Add bulk operation handlers:

```javascript
// Bulk request (green → magenta)
const handleBulkRequest = async () => {
  if (selectedAssignments.length === 0) return;

  const requestableAssignments = selectedAssignments.filter(
    a => a.status === 'planned' || a.status === 'manual'
  );

  if (requestableAssignments.length === 0) {
    alert('No requestable assignments selected');
    return;
  }

  const assignmentIds = requestableAssignments.map(a => a.assignment_id);

  try {
    const response = await fetch(
      `${API_BASE}/api/fms/bulk-create-vehicle-requests`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(assignmentIds)
      }
    );

    const result = await response.json();

    if (result.failed > 0) {
      alert(
        `Requested ${result.succeeded} of ${result.total} assignments.\n` +
        `${result.failed} failed - check console for details.`
      );
      console.error('Failed requests:', result.results.filter(r => !r.success));
    } else {
      alert(`Successfully requested ${result.succeeded} assignments to FMS`);
    }

    setSelectedAssignments([]);
    await fetchChainData();
  } catch (err) {
    alert('Network error: Could not bulk request');
    console.error(err);
  }
};

// Bulk unrequest (magenta → green)
const handleBulkUnrequest = async () => {
  if (selectedAssignments.length === 0) return;

  const requestedAssignments = selectedAssignments.filter(
    a => a.status === 'requested'
  );

  if (requestedAssignments.length === 0) {
    alert('No requested assignments selected');
    return;
  }

  const assignmentIds = requestedAssignments.map(a => a.assignment_id);

  try {
    const response = await fetch(
      `${API_BASE}/api/fms/bulk-unrequest-vehicle-requests`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(assignmentIds)
      }
    );

    const result = await response.json();

    if (result.failed > 0) {
      alert(
        `Unrequested ${result.succeeded} of ${result.total} assignments.\n` +
        `${result.failed} failed - check console for details.`
      );
      console.error('Failed unrequests:', result.results.filter(r => !r.success));
    } else {
      alert(`Successfully unrequested ${result.succeeded} assignments from FMS`);
    }

    setSelectedAssignments([]);
    await fetchChainData();
  } catch (err) {
    alert('Network error: Could not bulk unrequest');
    console.error(err);
  }
};

// Bulk delete
const handleBulkDelete = async () => {
  if (selectedAssignments.length === 0) return;

  const assignmentIds = selectedAssignments.map(a => a.assignment_id);

  try {
    const response = await fetch(
      `${API_BASE}/api/fms/bulk-delete-vehicle-requests`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(assignmentIds)
      }
    );

    const result = await response.json();

    if (result.failed > 0) {
      alert(
        `Deleted ${result.succeeded} of ${result.total} assignments.\n` +
        `${result.failed} failed - check console for details.`
      );
      console.error('Failed deletions:', result.results.filter(r => !r.success));
    } else {
      alert(`Successfully deleted ${result.succeeded} assignments`);
    }

    setSelectedAssignments([]);
    await fetchChainData();
  } catch (err) {
    alert('Network error: Could not bulk delete');
    console.error(err);
  }
};

// Add buttons to JSX (example)
return (
  <div>
    {selectedAssignments.length > 0 && (
      <div className="bulk-actions">
        <button onClick={handleBulkRequest}>
          📤 Request Selected ({selectedAssignments.filter(a => ['planned', 'manual'].includes(a.status)).length})
        </button>

        <button onClick={handleBulkUnrequest}>
          ↩️ Unrequest Selected ({selectedAssignments.filter(a => a.status === 'requested').length})
        </button>

        <button onClick={handleBulkDelete}>
          🗑️ Delete Selected ({selectedAssignments.length})
        </button>
      </div>
    )}
  </div>
);
```

#### 3. Environment Variables

Create `frontend/.env.production`:

```bash
VITE_API_BASE_URL=https://media-scheduler.onrender.com
```

Update all API calls to use:

```javascript
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8081';
```

---

## Nightly Data Sync Automation

### Implementation Strategy

Use APScheduler to run nightly sync at 2 AM (or after FMS exports refresh).

#### 1. Install Dependencies

```bash
pip install apscheduler
```

Add to `backend/requirements.txt`:
```
apscheduler==3.10.4
```

#### 2. Update `backend/app/main.py`

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import httpx
import os

scheduler = AsyncIOScheduler()

async def nightly_fms_sync():
    """
    Runs nightly to sync FMS CSV exports → Scheduler database
    Timing: After FMS export generation (recommend 2-3 AM)
    """
    print(f"[{datetime.now()}] Starting nightly FMS sync...")

    base_url = os.getenv("API_BASE_URL", "http://localhost:8081")

    csv_endpoints = [
        ("vehicles", os.getenv("FMS_VEHICLES_CSV_URL")),
        ("media_partners", os.getenv("FMS_PARTNERS_CSV_URL")),
        ("loan_history", os.getenv("FMS_LOAN_HISTORY_CSV_URL")),
        ("current_activity", os.getenv("FMS_CURRENT_ACTIVITY_CSV_URL")),
    ]

    results = []

    async with httpx.AsyncClient(timeout=600.0) as client:
        for entity, csv_url in csv_endpoints:
            try:
                print(f"  Syncing {entity}...")
                response = await client.post(
                    f"{base_url}/ingest/{entity}/url",
                    params={"url": csv_url}
                )

                if response.status_code == 200:
                    print(f"  ✓ {entity} synced successfully")
                    results.append({"entity": entity, "success": True})
                else:
                    print(f"  ✗ {entity} sync failed: {response.status_code}")
                    results.append({"entity": entity, "success": False, "error": response.status_code})

            except Exception as e:
                print(f"  ✗ {entity} sync error: {e}")
                results.append({"entity": entity, "success": False, "error": str(e)})

    success_count = sum(1 for r in results if r['success'])
    print(f"[{datetime.now()}] Nightly sync completed: {success_count}/{len(csv_endpoints)} successful")

    return results


@app.on_event("startup")
async def start_scheduler():
    """Start APScheduler on app startup"""
    sync_hour = int(os.getenv("SYNC_HOUR", 2))    # Default: 2 AM
    sync_minute = int(os.getenv("SYNC_MINUTE", 0))

    scheduler.add_job(
        nightly_fms_sync,
        CronTrigger(hour=sync_hour, minute=sync_minute),
        id="nightly_fms_sync",
        replace_existing=True
    )

    scheduler.start()
    print(f"Scheduler started - nightly sync at {sync_hour:02d}:{sync_minute:02d}")


@app.on_event("shutdown")
async def shutdown_scheduler():
    """Shutdown scheduler gracefully"""
    scheduler.shutdown()
    print("Scheduler stopped")


# Manual trigger endpoint (for testing)
@app.post("/api/admin/trigger-sync")
async def trigger_manual_sync():
    """Manually trigger FMS data sync (for testing/debugging)"""
    results = await nightly_fms_sync()
    return {
        "success": True,
        "message": "Manual sync completed",
        "results": results
    }
```

### Configuration

Add to `backend/.env`:

```bash
# Nightly Sync Configuration
SYNC_HOUR=2               # 2 AM
SYNC_MINUTE=0
API_BASE_URL=http://localhost:8081

# FMS CSV Export URLs
FMS_VEHICLES_CSV_URL=https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/active_vehicles.rpt&init=csv
FMS_PARTNERS_CSV_URL=https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/media_partners.rpt&init=csv
FMS_LOAN_HISTORY_CSV_URL=https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/loan_history.rpt&init=csv
FMS_CURRENT_ACTIVITY_CSV_URL=https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/current_activity.rpt&init=csv
```

### Testing Nightly Sync

```bash
# Trigger manual sync via API
curl -X POST http://localhost:8081/api/admin/trigger-sync

# Check logs for results
tail -f logs/scheduler.log
```

---

## Questions for Alex (Blockers)

### Priority 1: CRITICAL for MVP

#### 1. `requestor_id` Field (Required by API)
**Question**: What should we use for the `requestor_id` field in the vehicle request payload?

Options:
- A) Fixed system user ID (provide the ID)
- B) Office/location ID
- C) Create a special "Media Scheduler" user in FMS (provide the ID)

**Why it matters**: This is a required field; API calls will fail without it.

---

#### 2. `vehicle_id` Confirmation
**Question**: Confirm that the `vehicle_id` in our vehicles table (imported from your active_vehicles.rpt CSV) matches what FMS expects in the `requests_vehicles[].vehicle_id` field.

**Our assumption**: We import `vehicle_id` from your CSV's first column, store it in our `vehicles` table, and JOIN it when creating FMS requests.

**Test case**: Can you provide a sample vehicle from staging with:
- VIN: `_______________`
- Expected vehicle_id: `_____`

We'll test creating a request with it.

---

#### 3. FMS API Response Format
**Question**: When we successfully POST to `/api/v1/vehicle_requests`, what does the response look like?

We need to know which field contains the request ID so we can store it for future deletion.

Example possibilities:
```json
// Option A
{"id": 123}

// Option B
{"request_id": 123}

// Option C
{
  "vehicle_request": {
    "id": 123,
    "status": "pending"
  }
}
```

**Why it matters**: We store this ID in `scheduled_assignments.fms_request_id` for deletion.

---

#### 4. DELETE Endpoint Status
**Question**: You mentioned the DELETE endpoint "still needs to be done". What's the status?

Endpoint: `DELETE /api/v1/vehicle_requests/{request_id}`

**Can we test on staging?** If not ready, what's the ETA?

---

### Priority 2: Important for Production

#### 5. `activity_type_id` Configuration
**Question**: What is the FMS activity type ID for "Media Partner Loan"?

We'll store this in our environment config and send it with every request.

**Optional**: Same question for `activity_type_subcategory_id` if relevant.

---

#### 6. CORS Configuration
**Question**: Our app will be hosted on Render (e.g., `https://media-scheduler.onrender.com`).

Can you add CORS headers on FMS to allow:
- Origin: `https://media-scheduler.onrender.com`
- Methods: `GET, POST, PATCH, DELETE`
- Headers: `Authorization, Content-Type`

**Why it matters**: iframe embedding and API calls from frontend.

---

#### 7. Token Rotation Policy
**Question**: The bearer tokens you provided are static:
- Staging: `ac6bc4df0fc050fa6cc31c066af8f02b`
- Production: `0b36ae1b3bebba027cf2ccd9049afa75`

Are these permanent, or do they rotate? If they rotate, how will we get new tokens?

---

#### 8. FMS → Scheduler Webhook (Optional)
**Question**: When FMS approves/rejects a vehicle request, can you POST to our API with the update?

Endpoint example: `POST https://media-scheduler.onrender.com/api/fms/webhook/request-approved`

**Alternative**: We sync via nightly CSV import of `current_activity` (approved loans show up as active).

**Benefit of webhook**: Real-time updates instead of waiting until next day.

---

#### 9. CSV Export Refresh Timing
**Question**: What time do FMS CSV exports refresh daily?

We'll schedule our nightly sync to run 30-60 minutes after your exports generate.

**Current assumption**: Exports refresh at 1 AM, we sync at 2 AM.

---

#### 10. Error Handling & Validation
**Question**: What HTTP status codes should we expect from the FMS API?

- `200 OK` - Success
- `201 Created` - Request created
- `400 Bad Request` - Invalid payload (missing required fields?)
- `401 Unauthorized` - Bad token
- `404 Not Found` - Vehicle/contact doesn't exist?
- `422 Unprocessable Entity` - Validation errors?
- `500 Internal Server Error` - FMS error

**Example**: If we send an invalid `vehicle_id`, what error do we get?

---

## Testing Checklist

### Unit Tests (Backend)

- [ ] Test `create_fms_vehicle_request()` with valid data
- [ ] Test `create_fms_vehicle_request()` with missing vehicle_id
- [ ] Test `delete_fms_vehicle_request()` with valid fms_request_id
- [ ] Test `delete_fms_vehicle_request()` with missing fms_request_id
- [ ] Test bulk operations with mixed success/failure
- [ ] Test status change endpoint (all scenarios)
- [ ] Test nightly sync function

### Integration Tests (Staging)

#### Test 1: Single Request Flow
1. Create planned assignment in scheduler (green)
2. Click "Request" → Should turn magenta
3. Verify: FMS staging shows pending request
4. Check database: `fms_request_id` should be populated

#### Test 2: Single Unrequest Flow
1. Start with requested assignment (magenta)
2. Click "Unrequest" → Should turn green
3. Verify: FMS staging request is deleted
4. Verify: Assignment still exists in scheduler

#### Test 3: Single Delete Flow
1. Create requested assignment (magenta)
2. Delete assignment
3. Verify: FMS staging request is deleted
4. Verify: Assignment removed from scheduler

#### Test 4: Bulk Request (Chain Builder)
1. Create 5 planned assignments
2. Select all 5
3. Click "Request Selected"
4. Verify: All 5 turn magenta
5. Verify: All 5 appear in FMS staging

#### Test 5: Bulk Unrequest (Chain Builder)
1. Create 3 requested assignments (magenta)
2. Select all 3
3. Click "Unrequest Selected"
4. Verify: All 3 turn green
5. Verify: All 3 removed from FMS staging
6. Verify: All 3 still in scheduler

#### Test 6: Bulk Delete Mixed Statuses
1. Create: 2 planned (green), 3 requested (magenta)
2. Select all 5
3. Click "Delete Selected"
4. Verify: All 5 removed from scheduler
5. Verify: 3 FMS DELETE calls made (only for magenta items)

#### Test 7: Partial Failure Handling
1. Create 5 requested assignments
2. Manually break one in FMS (or simulate)
3. Bulk unrequest all 5
4. Verify: Error message shows "4 of 5 succeeded, 1 failed"
5. Verify: Failed item stays magenta, others turn green

#### Test 8: Nightly Sync
1. Manually trigger sync: `curl -X POST http://staging/api/admin/trigger-sync`
2. Verify: All 4 CSV imports succeed (vehicles, partners, history, activity)
3. Check database: New vehicles/partners imported
4. Verify: Active loans show as blue bars in calendar

#### Test 9: FMS Approval → Scheduler Update
1. Create requested assignment (magenta)
2. Have Alex approve in FMS staging
3. Wait for nightly sync (or trigger manually)
4. Verify: Assignment now shows as blue (active) in calendar

#### Test 10: iframe Embedding
1. Deploy scheduler to Render staging
2. Have Alex embed in FMS staging iframe
3. Verify: UI loads correctly inside iframe
4. Test: Click "Request" from within iframe
5. Verify: API call succeeds (CORS working)

### End-to-End Test (Production)

- [ ] Deploy to production (both scheduler + FMS)
- [ ] Create real vehicle request from scheduler
- [ ] Approve in FMS
- [ ] Verify appears as active in next day's sync
- [ ] Monitor logs for errors
- [ ] Confirm no data discrepancies

---

## Implementation Phases

### Phase 1: Foundation (Week 1)
**Goal**: Set up FMS integration infrastructure

Tasks:
- [ ] Get answers to all Alex blocker questions
- [ ] Add `fms_request_id` column to `scheduled_assignments` table
- [ ] Create `backend/app/routers/fms_integration.py` with all endpoints
- [ ] Add environment variables for FMS config
- [ ] Update `main.py` to include FMS router
- [ ] Test endpoints with Postman/curl (mock FMS responses if needed)

**Deliverable**: FMS integration endpoints ready for testing

---

### Phase 2: Core Integration (Week 2)
**Goal**: Connect status changes to FMS API

Tasks:
- [ ] Modify `calendar.py` status change endpoint (three scenarios)
- [ ] Update frontend `Calendar.jsx` (request/unrequest/delete handlers)
- [ ] Update frontend `ChainBuilder.jsx` (bulk operation handlers)
- [ ] Add error handling and user feedback
- [ ] Deploy to staging environment
- [ ] Test on FMS staging with Alex

**Deliverable**: Single operations working end-to-end on staging

---

### Phase 3: Bulk Operations (Week 3)
**Goal**: Implement Chain Builder bulk actions

Tasks:
- [ ] Test bulk request (5-10 items)
- [ ] Test bulk unrequest (5-10 items)
- [ ] Test bulk delete with mixed statuses
- [ ] Add progress indicators for bulk operations
- [ ] Implement partial failure handling
- [ ] Test with larger datasets (20-50 items)

**Deliverable**: Bulk operations working smoothly on staging

---

### Phase 4: Data Sync Automation (Week 4)
**Goal**: Automate nightly FMS → Scheduler sync

Tasks:
- [ ] Install APScheduler
- [ ] Implement nightly sync job in `main.py`
- [ ] Add manual trigger endpoint for testing
- [ ] Configure sync timing (after FMS export refresh)
- [ ] Set up logging and monitoring
- [ ] Test sync on staging for one week
- [ ] Verify data consistency

**Deliverable**: Automated nightly sync running reliably

---

### Phase 5: Production Deployment (Week 5)
**Goal**: Deploy to production and embed in FMS

Tasks:
- [ ] Deploy scheduler to Render production
- [ ] Configure production environment variables
- [ ] Update frontend to use production API URL
- [ ] Coordinate with Alex on iframe embedding
- [ ] Test CORS configuration
- [ ] End-to-end production test
- [ ] Monitor for 2-3 days

**Deliverable**: Production system live and stable

---

### Phase 6: Optimization & Monitoring (Ongoing)
**Goal**: Improve performance and reliability

Tasks:
- [ ] Add retry logic for failed API calls
- [ ] Implement request rate limiting (if needed)
- [ ] Add Sentry/logging for error tracking
- [ ] Create admin dashboard for sync status
- [ ] Document troubleshooting procedures
- [ ] Train users on new workflow

**Deliverable**: Production-ready system with monitoring

---

## Security & Configuration

### Environment Variables

**Backend** (`backend/.env`):

```bash
# FMS API Configuration
FMS_BASE_URL=https://fms.driveshop.com
FMS_STAGING_URL=https://staging.driveshop.com
FMS_ENVIRONMENT=production                          # or 'staging'
FMS_PRODUCTION_TOKEN=0b36ae1b3bebba027cf2ccd9049afa75
FMS_STAGING_TOKEN=ac6bc4df0fc050fa6cc31c066af8f02b

# FMS Request Configuration (get from Alex)
FMS_REQUESTOR_ID=???                                # TODO: Get from Alex
FMS_ACTIVITY_TYPE_ID=???                           # TODO: Get from Alex (e.g., 5)
FMS_ACTIVITY_TYPE_SUBCATEGORY_ID=???              # TODO: Get from Alex

# FMS CSV Export URLs
FMS_VEHICLES_CSV_URL=https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/active_vehicles.rpt&init=csv
FMS_PARTNERS_CSV_URL=https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/media_partners.rpt&init=csv
FMS_LOAN_HISTORY_CSV_URL=https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/loan_history.rpt&init=csv
FMS_CURRENT_ACTIVITY_CSV_URL=https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/current_activity.rpt&init=csv

# Nightly Sync Configuration
SYNC_HOUR=2                                        # 2 AM (after FMS export generation)
SYNC_MINUTE=0
API_BASE_URL=http://localhost:8081                # Update for production

# Database (Supabase)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
```

**Frontend** (`frontend/.env.production`):

```bash
VITE_API_BASE_URL=https://media-scheduler.onrender.com
```

### Deployment Configuration (Render)

**Backend Service**:
- Type: Web Service
- Build Command: `pip install -r backend/requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Environment: Python 3.12
- Instance Type: Starter (upgrade if needed)
- Auto-Deploy: Yes (on git push to main)

**Frontend Service**:
- Type: Static Site
- Build Command: `cd frontend && npm install && npm run build`
- Publish Directory: `frontend/dist`
- Auto-Deploy: Yes

### CORS Configuration

**Backend** (`backend/app/main.py`):

```python
from fastapi.middleware.cors import CORSMiddleware

origins = [
    "http://localhost:3001",
    "http://localhost:5173",
    "https://fms.driveshop.com",              # FMS production
    "https://staging.driveshop.com",          # FMS staging
    "https://media-scheduler.onrender.com",   # Production frontend
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**FMS Side** (Ruby on Rails):
Alex needs to configure FMS to allow iframe embedding and API calls from:
- `https://media-scheduler.onrender.com`

---

## Summary & Next Steps

### What's Clear

✅ **Data mapping**: Scheduler → FMS API (just need vehicle_id JOIN)
✅ **Status flow**: Green → Magenta → Blue (well-defined)
✅ **Architecture**: FastAPI endpoints calling FMS REST API
✅ **Sync strategy**: APScheduler nightly job
✅ **Bulk operations**: Loop through each item individually
✅ **Delete vs Unrequest**: Unrequest keeps assignment, Delete removes it

### What We Need from Alex

⚠️ **Critical blockers**:
1. `requestor_id` value
2. `activity_type_id` value
3. FMS API response format (which field has request ID?)
4. Confirm `vehicle_id` mapping
5. DELETE endpoint completion status

⚠️ **Production requirements**:
6. CORS configuration for Render domain
7. Token rotation policy (if any)
8. CSV export refresh timing
9. Error handling expectations

### Recommended Next Steps

1. **This meeting**: Review plan with Alex, get answers to blocker questions
2. **This week**: Implement Phase 1 (foundation) once blockers resolved
3. **Next week**: Test on staging with Alex's help
4. **Week 3**: Deploy to production and embed in FMS
5. **Ongoing**: Monitor, optimize, and add features as needed

---

## Appendix: API Quick Reference

### FMS → Scheduler (CSV Imports)
- Vehicles: `POST /ingest/vehicles/url?url={fms_csv_url}`
- Partners: `POST /ingest/media_partners/url?url={fms_csv_url}`
- History: `POST /ingest/loan_history/url?url={fms_csv_url}`
- Activity: `POST /ingest/current_activity/url?url={fms_csv_url}`

### Scheduler → FMS (Vehicle Requests)
- Create: `POST https://fms.driveshop.com/api/v1/vehicle_requests` (with JSON payload)
- Delete: `DELETE https://fms.driveshop.com/api/v1/vehicle_requests/{id}`
- Auth: `Authorization: Bearer {token}`

### Scheduler Internal (Status Management)
- Change status: `PATCH /api/calendar/change-assignment-status/{id}?new_status={status}`
- Delete assignment: `DELETE /api/calendar/assignment/{id}`
- Bulk request: `POST /api/fms/bulk-create-vehicle-requests` (array of IDs)
- Bulk unrequest: `POST /api/fms/bulk-unrequest-vehicle-requests` (array of IDs)
- Bulk delete: `POST /api/fms/bulk-delete-vehicle-requests` (array of IDs)

### Admin Tools
- Manual sync: `POST /api/admin/trigger-sync`

---

**Document Version**: 1.0
**Last Updated**: November 11, 2025
**Contact**: Ray Rierson (Media Scheduler) | Alex (FMS Developer)
