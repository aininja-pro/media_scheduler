# FMS Integration

This document describes the technical integration between Media Scheduler and the Fleet Management System (FMS).

## Overview

Media Scheduler integrates bi-directionally with DriveShop's FMS (Ruby on Rails application) to:

- Create vehicle requests from scheduled assignments
- Delete vehicle requests when assignments are cancelled
- Sync vehicle, partner, and loan data
- Track request status and approvals

## Architecture

```
┌─────────────────┐                    ┌─────────────────┐
│ Media Scheduler │                    │      FMS        │
│                 │                    │                 │
│  ┌───────────┐  │    REST API        │  ┌───────────┐  │
│  │ Scheduler │──┼───────────────────▶│  │ Requests  │  │
│  │    DB     │  │                    │  │    DB     │  │
│  └───────────┘  │                    │  └───────────┘  │
│       ▲         │                    │       │         │
│       │         │    CSV Reports     │       │         │
│       └─────────┼────────────────────┼───────┘         │
│                 │                    │                 │
└─────────────────┘                    └─────────────────┘
```

## Configuration

### Environment Variables

```bash
# FMS Environment Selection
FMS_ENVIRONMENT=staging  # or 'production'

# Staging Configuration
FMS_STAGING_URL=https://staging.driveshop.com
FMS_STAGING_TOKEN=your-staging-api-token
FMS_STAGING_REQUESTOR_ID=1949

# Production Configuration
FMS_PRODUCTION_URL=https://fms.driveshop.com
FMS_PRODUCTION_TOKEN=your-production-api-token
FMS_PRODUCTION_REQUESTOR_ID=1949
```

### Switching Environments

Change `FMS_ENVIRONMENT` to switch between staging and production:

```bash
# Use staging for testing
FMS_ENVIRONMENT=staging

# Use production for live operations
FMS_ENVIRONMENT=production
```

## API Integration

### Authentication

All FMS API requests require Bearer token authentication:

```python
headers = {
    "Authorization": f"Bearer {FMS_TOKEN}",
    "Content-Type": "application/json"
}
```

### Create Vehicle Request

Creates a new vehicle request in FMS from a scheduled assignment.

**Endpoint**: `POST /api/v1/vehicle_requests`

**Request Payload**:
```json
{
  "vehicle_request": {
    "vehicle_id": 456,
    "requestor_id": 1949,
    "requested_delivery_datetime": "2024-01-15T09:00:00",
    "requested_pickup_datetime": "2024-01-22T17:00:00",
    "delivery_address_contact_id": 789
  }
}
```

**Field Mapping**:

| Scheduler Field | FMS Field |
|-----------------|-----------|
| `vehicle.vehicle_id` | `vehicle_id` |
| (configured) | `requestor_id` |
| `assignment.start_date` | `requested_delivery_datetime` |
| `assignment.end_date` | `requested_pickup_datetime` |
| `partner.fms_contact_id` | `delivery_address_contact_id` |

**Response**:
```json
{
  "id": 12345,
  "status": "pending",
  "vehicle_id": 456,
  "created_at": "2024-01-10T14:30:00Z"
}
```

### Delete Vehicle Request

Cancels an existing vehicle request in FMS.

**Endpoint**: `DELETE /api/v1/vehicle_requests/{id}`

**Response**:
```json
{
  "success": true
}
```

## Data Synchronization

### Nightly Sync Process

The scheduler syncs data from FMS reports automatically:

1. **Schedule**: 2:00 AM Pacific (configurable)
2. **Frequency**: Daily
3. **Method**: APScheduler background task

### Sync Configuration

```bash
SYNC_ENABLED=true
SYNC_HOUR=2
SYNC_MINUTE=0
```

### Data Sources

| Data Type | FMS Report URL |
|-----------|----------------|
| Vehicles | `/reports/vehicles.csv` |
| Partners | `/reports/media_partners.csv` |
| Approved Makes | `/reports/approved_makes.csv` |
| Loan History | `/reports/loan_history.csv` |
| Current Activity | `/reports/current_activity.csv` |

### Sync Process

```python
async def nightly_sync():
    db = DatabaseService()
    await db.initialize()

    try:
        # Fetch and process each data type
        for table in ['vehicles', 'media_partners', ...]:
            url = f"{FMS_URL}/reports/{table}.csv"
            data = await fetch_csv(url)
            await upsert_data(db, table, data)

        log_sync_success()
    except Exception as e:
        log_sync_error(e)
    finally:
        await db.close()
```

### Manual Sync

Trigger sync manually via API:

```bash
curl -X POST http://localhost:8081/api/ingest/sync
```

## Request Lifecycle

### Status Flow

```
Planned (Green)
    │
    ▼ [User clicks "Request"]
    │
Requested (Magenta)
    │
    ▼ [FMS approves]
    │
Active (Blue)
    │
    ▼ [Loan completes]
    │
Completed
```

### Creating a Request

1. User creates assignment in Scheduler (status: planned)
2. User clicks "Request" button
3. Scheduler calls FMS API to create vehicle request
4. FMS returns request ID
5. Scheduler updates assignment status to "requested"
6. Assignment displays as magenta

### Cancelling a Request

1. User clicks "Unrequest" on magenta assignment
2. Scheduler calls FMS API to delete vehicle request
3. FMS confirms deletion
4. Scheduler updates assignment status back to "planned"
5. Assignment displays as green

### FMS Approval

1. FMS processes and approves the request
2. During next sync, scheduler detects approval
3. Assignment status updates to "active"
4. Assignment displays as blue

## Implementation Details

### Backend Endpoints

**File**: `backend/app/routers/fms_integration.py`

```python
@router.post("/create-vehicle-request")
async def create_vehicle_request(request: CreateRequestBody):
    # Get assignment details
    assignment = await get_assignment(request.assignment_id)

    # Build FMS payload
    payload = build_fms_payload(assignment)

    # Send to FMS
    response = await fms_client.post(
        "/api/v1/vehicle_requests",
        json=payload
    )

    # Update assignment with FMS request ID
    await update_assignment(
        assignment.id,
        fms_request_id=response['id'],
        status='requested'
    )

    return {"success": True, "fms_request_id": response['id']}
```

### Frontend Integration

**File**: `frontend/src/pages/Calendar.jsx`

```javascript
const handleRequest = async (assignmentId) => {
    try {
        const response = await fetch(
            `${API_BASE_URL}/api/fms/create-vehicle-request`,
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ assignment_id: assignmentId })
            }
        );

        if (response.ok) {
            // Refresh calendar to show new status
            await fetchAssignments();
        }
    } catch (error) {
        console.error('Failed to create FMS request:', error);
    }
};
```

## Error Handling

### Common Errors

| Error | Cause | Resolution |
|-------|-------|------------|
| 401 Unauthorized | Invalid or expired token | Check FMS_TOKEN |
| 404 Not Found | Invalid vehicle/contact ID | Verify IDs exist in FMS |
| 422 Validation Error | Missing required fields | Check payload format |
| 500 Server Error | FMS internal error | Contact FMS admin |

### Retry Logic

Failed requests are logged but not automatically retried. Manual intervention required for:

- Network failures
- FMS downtime
- Invalid data

### Error Logging

```python
try:
    response = await fms_client.post(...)
except httpx.HTTPError as e:
    logger.error(f"FMS request failed: {e}")
    raise HTTPException(status_code=502, detail="FMS request failed")
```

## Testing

### Staging Environment

Always test with staging before production:

1. Set `FMS_ENVIRONMENT=staging`
2. Create test assignments
3. Verify requests appear in FMS staging
4. Test unrequest flow
5. Verify sync works correctly

### Test Cases

1. **Create Request**: Assignment changes to magenta
2. **Unrequest**: Assignment returns to green
3. **Delete Assigned**: FMS request is deleted
4. **Sync**: Data updates from FMS reports

### Verification

Check FMS directly:

```bash
# View request in FMS
https://staging.driveshop.com/vehicle_requests/12345
```

## Monitoring

### Sync Status

Check last sync in Availability page or via API:

```bash
curl http://localhost:8081/api/ingest/sync/status
```

### Logs

Monitor backend logs for:

- FMS API calls
- Sync results
- Error messages

### Metrics

Track:

- Request success rate
- Sync completion time
- Error frequency

## Security

### Token Management

- Tokens stored in environment variables
- Never commit tokens to version control
- Rotate tokens periodically
- Use separate tokens for staging/production

### Data Privacy

- Only sync necessary data
- Respect data retention policies
- Log access for auditing

## Troubleshooting

### Request Not Created

1. Check FMS environment setting
2. Verify token is valid
3. Check vehicle/partner IDs
4. Review error logs

### Sync Not Running

1. Verify `SYNC_ENABLED=true`
2. Check scheduler is running
3. Review sync logs
4. Test FMS report URLs manually

### Status Not Updating

1. Wait for next sync cycle
2. Trigger manual sync
3. Check FMS for actual status
4. Verify database connection

## Best Practices

1. **Test in staging first** - Never test with production data
2. **Monitor sync logs** - Catch errors early
3. **Verify before requesting** - Check assignment details
4. **Document changes** - Track configuration modifications
5. **Regular token rotation** - Security best practice
