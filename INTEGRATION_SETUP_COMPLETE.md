# FMS Integration - Backend Setup Complete ✅

## What's Been Implemented

### ✅ Phase 1: Backend Foundation (COMPLETE)

1. **Database Migration** (`backend/migrations/add_fms_request_id.sql`)
   - Added `fms_request_id` column to `scheduled_assignments` table
   - Added index for faster lookups
   - **ACTION REQUIRED**: Run this SQL in your Supabase SQL editor

2. **FMS Integration Router** (`backend/app/routers/fms_integration.py`)
   - Single operations:
     - `POST /api/fms/create-vehicle-request/{id}` - Create FMS vehicle request
     - `DELETE /api/fms/delete-vehicle-request/{id}` - Delete FMS vehicle request
   - Bulk operations (for Chain Builder):
     - `POST /api/fms/bulk-create-vehicle-requests` - Bulk request
     - `POST /api/fms/bulk-unrequest-vehicle-requests` - Bulk unrequest
     - `POST /api/fms/bulk-delete-vehicle-requests` - Bulk delete
   - Admin endpoint:
     - `GET /api/fms/config` - Check FMS configuration

3. **Environment Variables** (`backend/.env`)
   - FMS staging/production URLs
   - API tokens (from Alex)
   - Requestor ID (1949 for staging)
   - CSV export URLs (for future nightly sync)

4. **Modified Calendar Endpoint** (`backend/app/routers/calendar.py`)
   - Status change endpoint now integrates with FMS:
     - Green → Magenta = Creates FMS request
     - Magenta → Green = Deletes FMS request (unrequest)
     - Includes rollback on errors

5. **Registered Router** (`backend/app/main.py`)
   - FMS integration router added to FastAPI app

---

## Next Steps

### Immediate Actions

#### 1. Run Database Migration
Open your Supabase SQL editor and run:

```sql
-- Copy contents from backend/migrations/add_fms_request_id.sql
ALTER TABLE scheduled_assignments
ADD COLUMN IF NOT EXISTS fms_request_id INTEGER;

CREATE INDEX IF NOT EXISTS idx_scheduled_assignments_fms_request_id
ON scheduled_assignments(fms_request_id);

COMMENT ON COLUMN scheduled_assignments.fms_request_id
IS 'FMS vehicle_request ID returned from POST /api/v1/vehicle_requests - used for deletion';
```

#### 2. Start Backend Server
```bash
cd /Users/richardrierson/Desktop/Projects/media_scheduler/backend
source venv/bin/activate  # If using virtual env
uvicorn app.main:app --reload --port 8081
```

#### 3. Test FMS Configuration
```bash
curl http://localhost:8081/api/fms/config
```

Expected output:
```json
{
  "environment": "staging",
  "base_url": "https://staging.driveshop.com",
  "requestor_id": "1949",
  "token_configured": true,
  "token_length": 32
}
```

#### 4. Ask Alex to Confirm DELETE Endpoint
The DELETE endpoint (`DELETE /api/v1/vehicle_requests/{id}`) is still being built by Alex. Confirm when it's ready for testing.

---

### Phase 2: Frontend Updates (TODO)

Still need to update:

1. **Calendar.jsx** (`frontend/src/pages/Calendar.jsx`)
   - Update `requestAssignment()` handler
   - Update `unrequestAssignment()` handler
   - Update `handleDeleteAssignment()` handler

2. **ChainBuilder.jsx** (`frontend/src/pages/ChainBuilder.jsx`)
   - Add `handleBulkRequest()` handler
   - Add `handleBulkUnrequest()` handler
   - Update `handleBulkDelete()` handler
   - Add UI buttons for bulk operations

3. **Environment Variables** (`frontend/.env.production`)
   - Add production API URL

---

## Testing Checklist (Once DELETE Endpoint Ready)

### Test 1: Check Backend is Running
```bash
curl http://localhost:8081/api/fms/config
```

### Test 2: Test Single Request Flow (Manual)

#### Step 1: Create a manual assignment in your scheduler UI
- Go to Calendar view
- Create an assignment (any vehicle + partner)
- It should show as green (status = 'manual')

#### Step 2: Mark it as "requested" via API
```bash
# Replace {assignment_id} with actual ID
curl -X PATCH "http://localhost:8081/api/calendar/change-assignment-status/{assignment_id}?new_status=requested"
```

Expected response:
```json
{
  "success": true,
  "message": "Assignment {id} requested in FMS",
  "assignment_id": 123,
  "old_status": "manual",
  "new_status": "requested",
  "fms_action": "create"
}
```

#### Step 3: Check FMS Staging
Log into FMS staging and verify the vehicle request appears in pending requests.

#### Step 4: Unrequest via API
```bash
curl -X PATCH "http://localhost:8081/api/calendar/change-assignment-status/{assignment_id}?new_status=manual"
```

Expected response:
```json
{
  "success": true,
  "message": "Assignment {id} unrequested from FMS",
  "assignment_id": 123,
  "old_status": "requested",
  "new_status": "manual",
  "fms_action": "delete"
}
```

#### Step 5: Verify FMS Deletion
Check FMS staging - the request should be deleted.

---

## Common Issues & Troubleshooting

### Issue: "vehicle_id not found for VIN"
**Cause**: The vehicle isn't in your `vehicles` table, or `vehicle_id` is NULL.

**Fix**:
1. Check your vehicles table:
   ```sql
   SELECT vin, vehicle_id FROM vehicles WHERE vin = 'YOUR_VIN';
   ```
2. Re-import vehicles from FMS CSV
3. Ensure `vehicle_id` column is populated in CSV export

### Issue: "FMS API error: 401 Unauthorized"
**Cause**: Token is incorrect or expired.

**Fix**:
1. Check `.env` file has correct tokens from Alex
2. Verify `FMS_ENVIRONMENT` is set to "staging"
3. Test token manually:
   ```bash
   curl -H "Authorization: Bearer ac6bc4df0fc050fa6cc31c066af8f02b" \
        https://staging.driveshop.com/api/v1/vehicle_requests
   ```

### Issue: "Could not extract FMS request ID from response"
**Cause**: FMS response format is different than expected.

**Fix**:
1. Check backend logs for full FMS response
2. Update extraction logic in `fms_integration.py` line ~270:
   ```python
   fms_request_id = (
       fms_response.get('id') or
       fms_response.get('request_id') or
       fms_response.get('vehicle_request', {}).get('id') or
       fms_response.get('data', {}).get('id')  # Add more as needed
   )
   ```

### Issue: DELETE endpoint returns 404
**Cause**: Alex hasn't finished implementing the DELETE endpoint yet.

**Status**: In progress - coordinate with Alex for completion date.

---

## API Endpoints Summary

### FMS Integration Endpoints

| Method | Endpoint | Purpose | Used By |
|--------|----------|---------|---------|
| POST | `/api/fms/create-vehicle-request/{id}` | Create FMS request | Calendar status change |
| DELETE | `/api/fms/delete-vehicle-request/{id}` | Delete FMS request | Calendar delete |
| POST | `/api/fms/bulk-create-vehicle-requests` | Bulk create | Chain Builder |
| POST | `/api/fms/bulk-unrequest-vehicle-requests` | Bulk unrequest | Chain Builder |
| POST | `/api/fms/bulk-delete-vehicle-requests` | Bulk delete | Chain Builder |
| GET | `/api/fms/config` | Check config | Testing |

### Modified Calendar Endpoints

| Method | Endpoint | Changes |
|--------|----------|---------|
| PATCH | `/api/calendar/change-assignment-status/{id}` | Now calls FMS API |

---

## What's Still TODO

### Backend:
- [x] Database migration
- [x] FMS integration router
- [x] Environment variables
- [x] Calendar status endpoint
- [ ] Nightly sync automation (Phase 3)
- [ ] Error logging/monitoring (Phase 6)

### Frontend:
- [ ] Calendar.jsx handlers
- [ ] ChainBuilder.jsx bulk handlers
- [ ] Environment variables
- [ ] User feedback UI
- [ ] Error handling

### Testing:
- [ ] Wait for DELETE endpoint from Alex
- [ ] Test on staging
- [ ] End-to-end flow verification
- [ ] Bulk operations testing

### Deployment:
- [ ] Deploy to Render
- [ ] Configure production env vars
- [ ] Test iframe embedding
- [ ] Monitor logs

---

## Questions for Alex (Outstanding)

1. ✅ `requestor_id` - **ANSWERED**: Use 1949 for staging
2. ✅ `vehicle_id` mapping - **CONFIRMED**: Pass from vehicles table
3. ⚠️ DELETE endpoint status - **PENDING**: When will it be ready?
4. ⚠️ FMS API response format - **NEEDS TESTING**: What field contains request ID?
5. ⚠️ Production requestor ID - **PENDING**: Create dedicated scheduler user?

---

## Contact

- **Scheduler Developer**: Ray Rierson
- **FMS Developer**: Alex
- **Integration Doc**: `/FMS_INTEGRATION_PLAN.md`
- **This Setup Guide**: `/INTEGRATION_SETUP_COMPLETE.md`

---

**Last Updated**: November 12, 2025
**Status**: Backend complete, frontend TODO, awaiting DELETE endpoint from Alex
