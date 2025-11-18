# API Reference

This document describes the Media Scheduler REST API endpoints.

## Base URL

| Environment | URL |
|-------------|-----|
| Production | `https://media-scheduler-api.onrender.com` |
| Development | `http://localhost:8081` |

## Authentication

Currently, API endpoints are open for internal use. Future versions will implement JWT authentication.

## Response Format

All endpoints return JSON with consistent structure:

**Success**:
```json
{
  "status": "success",
  "data": { ... }
}
```

**Error**:
```json
{
  "detail": "Error message"
}
```

---

## Optimizer Endpoints

### Run Optimizer

Run the Phase 7 constraint satisfaction optimizer.

**Endpoint**: `POST /api/ui_phase7/run`

**Request Body**:
```json
{
  "office": "Los Angeles",
  "target_week_start": "2024-01-15",
  "policy_weights": {
    "local_priority": 100,
    "publishing_success": 200,
    "tier_cap_penalty": 800,
    "fairness_weight": 50,
    "budget_weight": 30
  },
  "time_limit_seconds": 60
}
```

**Response**:
```json
{
  "assignments": [
    {
      "partner_id": 123,
      "partner_name": "Motor Trend",
      "vehicle_id": 456,
      "vehicle_info": "2024 BMW M3",
      "start_date": "2024-01-15",
      "end_date": "2024-01-22",
      "score": 0.85
    }
  ],
  "diagnostics": {
    "rejected": [...],
    "stats": {...}
  }
}
```

### Get Optimizer Metrics

Retrieve optimization statistics.

**Endpoint**: `GET /api/ui_phase7/metrics`

**Query Parameters**:
- `office` (required): Office name

**Response**:
```json
{
  "total_vehicles": 150,
  "total_partners": 75,
  "coverage_rate": 0.82
}
```

---

## Chain Builder Endpoints

### Auto-Suggest Partner Chain

Generate optimal vehicle chain for a partner.

**Endpoint**: `POST /api/chain_builder/partner/auto_suggest`

**Request Body**:
```json
{
  "partner_id": 123,
  "office": "Los Angeles",
  "start_date": "2024-01-15",
  "num_slots": 5
}
```

**Response**:
```json
{
  "chain": [
    {
      "slot": 1,
      "vehicle_id": 456,
      "vehicle_info": "2024 BMW M3",
      "start_date": "2024-01-15",
      "end_date": "2024-01-22",
      "score": 0.9
    }
  ]
}
```

### Auto-Suggest Vehicle Chain

Generate optimal partner chain for a vehicle.

**Endpoint**: `POST /api/chain_builder/vehicle/auto_suggest`

**Request Body**:
```json
{
  "vehicle_id": 456,
  "office": "Los Angeles",
  "start_date": "2024-01-15",
  "num_slots": 5
}
```

### Save Chain

Save a chain as assignments.

**Endpoint**: `POST /api/chain_builder/save`

**Request Body**:
```json
{
  "chain": [
    {
      "partner_id": 123,
      "vehicle_id": 456,
      "start_date": "2024-01-15",
      "end_date": "2024-01-22"
    }
  ],
  "request_to_fms": false
}
```

**Response**:
```json
{
  "saved": 5,
  "assignment_ids": [1, 2, 3, 4, 5]
}
```

---

## Calendar Endpoints

### Get Assignments

Retrieve assignments for a date range.

**Endpoint**: `GET /api/calendar/assignments`

**Query Parameters**:
- `office` (required): Office name
- `start_date` (required): Start of range (YYYY-MM-DD)
- `end_date` (required): End of range (YYYY-MM-DD)
- `status` (optional): Filter by status (planned, requested, active)

**Response**:
```json
{
  "assignments": [
    {
      "id": 1,
      "partner_id": 123,
      "partner_name": "Motor Trend",
      "vehicle_id": 456,
      "vehicle_info": "2024 BMW M3",
      "start_date": "2024-01-15",
      "end_date": "2024-01-22",
      "status": "planned",
      "fms_request_id": null
    }
  ]
}
```

### Get Vehicles

Get vehicles for calendar view.

**Endpoint**: `GET /api/calendar/vehicles`

**Query Parameters**:
- `office` (required): Office name

### Get Partners

Get partners for calendar view.

**Endpoint**: `GET /api/calendar/partners`

**Query Parameters**:
- `office` (required): Office name

### Update Assignment

Modify an existing assignment.

**Endpoint**: `PATCH /api/calendar/assignments/{id}`

**Request Body**:
```json
{
  "start_date": "2024-01-16",
  "end_date": "2024-01-23"
}
```

### Delete Assignment

Remove an assignment.

**Endpoint**: `DELETE /api/calendar/assignments/{id}`

**Response**:
```json
{
  "deleted": true,
  "fms_deleted": false
}
```

---

## FMS Integration Endpoints

### Create Vehicle Request

Send assignment to FMS.

**Endpoint**: `POST /api/fms/create-vehicle-request`

**Request Body**:
```json
{
  "assignment_id": 1
}
```

**Response**:
```json
{
  "success": true,
  "fms_request_id": 12345
}
```

### Delete Vehicle Request

Cancel FMS request.

**Endpoint**: `DELETE /api/fms/delete-vehicle-request`

**Request Body**:
```json
{
  "assignment_id": 1
}
```

### Get FMS Configuration

Check FMS environment settings.

**Endpoint**: `GET /api/fms/config`

**Response**:
```json
{
  "environment": "staging",
  "base_url": "https://staging.driveshop.com"
}
```

---

## Data Ingestion Endpoints

### Upload CSV

Ingest data from CSV file.

**Endpoint**: `POST /api/ingest/{table_name}/csv`

**Request**: multipart/form-data with CSV file

**Tables**: `vehicles`, `media_partners`, `approved_makes`, `loan_history`, `current_activity`

**Response**:
```json
{
  "processed": 150,
  "inserted": 145,
  "updated": 5,
  "errors": []
}
```

### Upload Excel

Ingest operations data from Excel.

**Endpoint**: `POST /api/ingest/operations/excel`

**Request**: multipart/form-data with Excel file

### Ingest from URL

Fetch and ingest data from FMS report URL.

**Endpoint**: `POST /api/ingest/{table_name}/url`

**Request Body**:
```json
{
  "url": "https://fms.driveshop.com/reports/vehicles.csv"
}
```

### Trigger Sync

Manually trigger nightly sync.

**Endpoint**: `POST /api/ingest/sync`

---

## Partner Endpoints

### List Partners

Get all partners with filtering.

**Endpoint**: `GET /api/partners`

**Query Parameters**:
- `office` (optional): Filter by office
- `tier` (optional): Filter by tier
- `search` (optional): Search by name

### Get Partner Details

Get full partner profile.

**Endpoint**: `GET /api/partners/{id}`

**Response**:
```json
{
  "id": 123,
  "name": "Motor Trend",
  "office": "Los Angeles",
  "tier": "A+",
  "publication_rate": 0.85,
  "approved_makes": [
    {"make": "BMW", "rank": 5},
    {"make": "Mercedes", "rank": 4}
  ],
  "preferred_days": {
    "pickup": ["Monday", "Wednesday"],
    "dropoff": ["Friday"]
  }
}
```

### Get Partner Context

Get partner context window data.

**Endpoint**: `GET /api/partners/{id}/context`

---

## Vehicle Endpoints

### List Vehicles

Get all vehicles with filtering.

**Endpoint**: `GET /api/vehicles`

**Query Parameters**:
- `office` (optional): Filter by office
- `make` (optional): Filter by make

### Get Vehicle Details

Get full vehicle information.

**Endpoint**: `GET /api/vehicles/{id}`

### Get Vehicle Context

Get vehicle context window data.

**Endpoint**: `GET /api/vehicles/{id}/context`

---

## Analytics Endpoints

### Publication Rates

Get publication rate data.

**Endpoint**: `GET /api/analytics/publication_rates`

**Query Parameters**:
- `office` (required): Office name

### Capacity

Get daily capacity data.

**Endpoint**: `GET /api/analytics/capacity`

**Query Parameters**:
- `office` (required): Office name
- `date` (required): Date (YYYY-MM-DD)

---

## Health & Utility

### Health Check

**Endpoint**: `GET /health`

**Response**:
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

### API Documentation

Interactive Swagger documentation available at:
- `GET /docs` - Swagger UI
- `GET /redoc` - ReDoc UI
- `GET /openapi.json` - OpenAPI schema

---

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request - Invalid parameters |
| 404 | Not Found - Resource doesn't exist |
| 409 | Conflict - Constraint violation |
| 422 | Validation Error - Invalid data format |
| 500 | Internal Server Error |

## Rate Limiting

Currently no rate limiting is enforced. Production may implement limits in the future.

## Pagination

List endpoints support pagination:

```
GET /api/partners?page=1&per_page=50
```

Response includes:
```json
{
  "data": [...],
  "total": 200,
  "page": 1,
  "per_page": 50,
  "pages": 4
}
```
