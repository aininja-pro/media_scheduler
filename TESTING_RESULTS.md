# FMS Integration Testing Results

**Date**: November 12, 2025
**Environment**: Staging (https://staging.driveshop.com)

---

## ✅ What's Working

### 1. Backend Server
- ✅ Server running successfully in Docker
- ✅ FMS integration router loaded
- ✅ Configuration endpoint working: `GET /api/fms/config`

```json
{
  "environment": "staging",
  "base_url": "https://staging.driveshop.com",
  "requestor_id": "1949",
  "token_configured": true,
  "token_length": 32
}
```

### 2. Database
- ✅ Vehicles table has 981 vehicles with `vehicle_id` populated
- ✅ Test vehicle found: 2025 Audi A3 Premium Plus S line (VIN: WAUHUDGY1SA051916, vehicle_id: 89943)
- ✅ Media partners loaded
- ✅ Test assignment created successfully (ID: 10610)

### 3. Network Connectivity
- ✅ Can reach FMS staging API
- ✅ SSL/TLS working correctly
- ✅ API responds with proper HTTP status codes

---

## ❌ What's Not Working

### FMS API Authorization Issue

**Test Command**:
```bash
curl -X POST "https://staging.driveshop.com/api/v1/vehicle_requests" \
  -H "Authorization: Bearer ac6bc4df0fc050fa6cc31c066af8f02b" \
  -H "Content-Type: application/json" \
  -d '{"request":{"requestor_id":1949,"start_date":"2025-11-19","end_date":"2025-11-26"}}'
```

**Response**:
```
HTTP/1.1 401 Unauthorized
{"errors":[{"detail":"Access denied"}]}
```

**Analysis**:
- Token `ac6bc4df0fc050fa6cc31c066af8f02b` is being received by FMS
- FMS recognizes the request but returns 401 Unauthorized
- This suggests the token may not have permission for the `/api/v1/vehicle_requests` endpoint

---

## 🔍 Questions for Alex

### Priority 1: Token Permissions

**Question**: Does the token `ac6bc4df0fc050fa6cc31c066af8f02b` have permission to access `/api/v1/vehicle_requests`?

**Context**:
- You mentioned this is "the same token as clips"
- Clips might use different endpoints
- The vehicle_requests endpoint might need different permissions

**Possible Solutions**:
1. Generate a new token specifically for vehicle_requests
2. Update permissions for existing token
3. Confirm we're using the right endpoint URL

### Priority 2: Test Credentials

**Question**: Can you provide test credentials or a test token that we can use to verify the integration works?

**What we need**:
- A token that has permission to POST to `/api/v1/vehicle_requests`
- Confirmation that `requestor_id: 1949` is correct
- A test vehicle_id we can use for testing

### Priority 3: API Documentation

**Question**: Is there API documentation for the vehicle_requests endpoint?

**What would help**:
- Required vs optional fields
- Expected response format (especially which field contains the request ID)
- Error codes and their meanings
- Any rate limiting or special requirements

---

## 🧪 Test Data Used

### Test Vehicle
```json
{
  "vin": "WAUHUDGY1SA051916",
  "vehicle_id": 89943,
  "year": 2025,
  "make": "Audi",
  "model": "A3 Premium Plus S line"
}
```

### Test Partner
```json
{
  "person_id": 3035,
  "name": "Nick Kurczewski"
}
```

### Test Assignment
```json
{
  "assignment_id": 10610,
  "vin": "WAUHUDGY1SA051916",
  "person_id": 3035,
  "start_day": "2025-11-19",
  "end_day": "2025-11-26",
  "status": "manual",
  "office": "Los Angeles"
}
```

### Test Request Payload (What we're trying to send to FMS)
```json
{
  "request": {
    "requestor_id": 1949,
    "start_date": "2025-11-19",
    "end_date": "2025-11-26",
    "activity_to": "Nick Kurczewski",
    "reason": "Scheduled media partner loan",
    "loanee_id": 3035,
    "requests_vehicles": [
      {
        "vehicle_id": 89943,
        "notes": "Audi A3 Premium Plus S line (VIN: WAUHUDGY1SA051916)"
      }
    ]
  }
}
```

---

## 📋 What's Ready to Test (Once Token Issue Resolved)

### Scenario 1: Single Request Flow
1. ✅ Create assignment in scheduler
2. ⏸️ Mark as "requested" (waiting for token fix)
3. ⏸️ Verify in FMS staging
4. ⏸️ Test unrequest
5. ⏸️ Verify deletion in FMS

### Scenario 2: Bulk Request Flow (Chain Builder)
1. ⏸️ Create multiple assignments
2. ⏸️ Bulk request
3. ⏸️ Verify all appear in FMS
4. ⏸️ Bulk unrequest
5. ⏸️ Verify all deleted from FMS

### Scenario 3: Error Handling
1. ⏸️ Test with invalid vehicle_id
2. ⏸️ Test with invalid person_id
3. ⏸️ Test with missing required fields
4. ⏸️ Test FMS rejection flow

---

## 🎯 Next Steps

### Immediate (Blocked on Alex)
1. **Get working token** for `/api/v1/vehicle_requests` endpoint
2. **Test single request** creation once token works
3. **Verify FMS response format** to ensure we extract request ID correctly

### After Token Fixed
1. Run full integration test
2. Update frontend Calendar.jsx
3. Update frontend ChainBuilder.jsx
4. End-to-end testing
5. Deploy to staging

### Future
1. Implement nightly data sync
2. Add error monitoring/logging
3. Production deployment
4. iframe embedding in FMS

---

## 📞 Contact

**Scheduler Developer**: Ray Rierson
**FMS Developer**: Alex
**Next Meeting**: TBD

---

## 🔧 How to Retest Once Token Fixed

### Option 1: Run Test Script
```bash
cd /Users/richardrierson/Desktop/Projects/media_scheduler/backend
python3 test_fms_integration.py
```

### Option 2: Manual API Test
```bash
# Update token in this command
curl -X POST "https://staging.driveshop.com/api/v1/vehicle_requests" \
  -H "Authorization: Bearer [NEW_TOKEN]" \
  -H "Content-Type: application/json" \
  -d '{
    "request": {
      "requestor_id": 1949,
      "start_date": "2025-11-19",
      "end_date": "2025-11-26",
      "requests_vehicles": [{"vehicle_id": 89943}]
    }
  }'
```

### Option 3: Test via Scheduler API
```bash
# Once token is updated in .env file
curl -X PATCH "http://localhost:8081/api/calendar/change-assignment-status/10610?new_status=requested"
```

---

**Status**: Backend implementation complete, blocked on FMS API token permissions
**Last Updated**: November 12, 2025
