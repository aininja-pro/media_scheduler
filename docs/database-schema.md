# Database Schema

This document describes the Media Scheduler database structure hosted on Supabase (PostgreSQL).

## Overview

The database stores all data required for vehicle-partner assignment optimization:

- Vehicle inventory
- Media partner profiles
- Assignment history
- Operational constraints

## Entity Relationship

```
┌──────────┐     ┌───────────────┐     ┌──────────────┐
│ vehicles │────▶│  assignments  │◀────│media_partners│
└──────────┘     └───────────────┘     └──────────────┘
                        │                      │
                        ▼                      ▼
                 ┌─────────────┐      ┌───────────────┐
                 │loan_history │      │approved_makes │
                 └─────────────┘      └───────────────┘
```

## Core Tables

### vehicles

Stores fleet inventory information.

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | Primary key |
| `vehicle_id` | integer | FMS vehicle ID |
| `vin` | varchar(17) | Vehicle Identification Number |
| `make` | varchar(50) | Manufacturer (BMW, Mercedes, etc.) |
| `model` | varchar(100) | Model name |
| `year` | integer | Model year |
| `office` | varchar(50) | Assigned office |
| `status` | varchar(20) | Current status (available, assigned, etc.) |
| `available_from` | date | Start of availability window |
| `available_to` | date | End of availability window |
| `created_at` | timestamp | Record creation time |
| `updated_at` | timestamp | Last update time |

**Indexes**:
- `idx_vehicles_office` on (office)
- `idx_vehicles_make` on (make)
- `idx_vehicles_vin` on (vin)

### media_partners

Stores media partner profiles.

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | Primary key |
| `partner_id` | integer | FMS partner ID |
| `name` | varchar(200) | Partner/outlet name |
| `email` | varchar(100) | Contact email |
| `phone` | varchar(20) | Contact phone |
| `address` | text | Physical address |
| `city` | varchar(100) | City |
| `state` | varchar(50) | State/province |
| `zip` | varchar(20) | Postal code |
| `latitude` | decimal(10,7) | Geocoded latitude |
| `longitude` | decimal(10,7) | Geocoded longitude |
| `office` | varchar(50) | Assigned office |
| `tier` | varchar(5) | Quality tier (A+, A, B, C) |
| `affiliation` | varchar(100) | Network affiliation |
| `status` | varchar(20) | Active, inactive, under_review |
| `preferred_pickup_days` | text[] | Array of preferred pickup days |
| `preferred_dropoff_days` | text[] | Array of preferred dropoff days |
| `publication_rate` | decimal(5,4) | 24-month rolling publication rate |
| `created_at` | timestamp | Record creation time |
| `updated_at` | timestamp | Last update time |

**Indexes**:
- `idx_partners_office` on (office)
- `idx_partners_tier` on (tier)
- `idx_partners_name` on (name)

### approved_makes

Stores partner-make approval relationships.

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | Primary key |
| `partner_id` | integer | Foreign key to media_partners |
| `make` | varchar(50) | Vehicle make |
| `quality_rank` | integer | Partner's rank for this make (1-5) |
| `created_at` | timestamp | Record creation time |

**Constraints**:
- Unique on (partner_id, make)

### scheduled_assignments

Stores current and planned assignments.

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | Primary key |
| `partner_id` | integer | Foreign key to media_partners |
| `vehicle_id` | integer | Foreign key to vehicles |
| `start_date` | date | Loan start date |
| `end_date` | date | Loan end date |
| `status` | varchar(20) | planned, requested, active, completed |
| `fms_request_id` | integer | FMS request ID (if requested) |
| `cost` | decimal(10,2) | Estimated assignment cost |
| `notes` | text | Optional notes |
| `created_at` | timestamp | Record creation time |
| `updated_at` | timestamp | Last update time |
| `created_by` | varchar(100) | User or system that created |

**Indexes**:
- `idx_assignments_partner` on (partner_id)
- `idx_assignments_vehicle` on (vehicle_id)
- `idx_assignments_dates` on (start_date, end_date)
- `idx_assignments_status` on (status)

### loan_history

Stores historical loan records with outcomes.

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | Primary key |
| `partner_id` | integer | Foreign key to media_partners |
| `vehicle_id` | integer | Foreign key to vehicles |
| `make` | varchar(50) | Vehicle make (denormalized) |
| `start_date` | date | Loan start date |
| `end_date` | date | Loan end date |
| `clip_received` | boolean | Whether media clip was received |
| `clip_date` | date | Date clip was published |
| `publication_url` | text | Link to published content |
| `created_at` | timestamp | Record creation time |

**Indexes**:
- `idx_loan_history_partner` on (partner_id)
- `idx_loan_history_dates` on (start_date)
- `idx_loan_history_make` on (make)

### current_activity

Stores real-time vehicle location and status.

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | Primary key |
| `vehicle_id` | integer | Foreign key to vehicles |
| `partner_id` | integer | Current partner (if assigned) |
| `status` | varchar(50) | Current status |
| `location` | varchar(200) | Current location description |
| `updated_at` | timestamp | Last status update |

## Operational Tables

### ops_capacity

Stores daily capacity limits per office.

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | Primary key |
| `office` | varchar(50) | Office name |
| `date` | date | Specific date |
| `pickups` | integer | Max pickups for the day |
| `dropoffs` | integer | Max dropoffs for the day |
| `swaps` | integer | Max same-partner swaps |
| `is_override` | boolean | Whether this is a manual override |

**Constraints**:
- Unique on (office, date)

### holiday_blackout_dates

Stores dates when assignments are blocked.

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | Primary key |
| `office` | varchar(50) | Office name (or 'all') |
| `date` | date | Blackout date |
| `reason` | varchar(200) | Reason for blackout |

### budgets

Stores fleet budget allocations.

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | Primary key |
| `fleet` | varchar(50) | Fleet/make name |
| `quarter` | varchar(10) | Quarter (Q1, Q2, Q3, Q4) |
| `year` | integer | Budget year |
| `allocated` | decimal(12,2) | Allocated budget amount |
| `spent` | decimal(12,2) | Amount spent so far |

## Supporting Tables

### cooldowns

Tracks partner-make cooldown status.

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | Primary key |
| `partner_id` | integer | Foreign key to media_partners |
| `make` | varchar(50) | Vehicle make |
| `last_loan_end` | date | End date of last loan |
| `cooldown_expires` | date | Date cooldown expires |

**Constraints**:
- Unique on (partner_id, make)

### geocoding_cache

Caches geocoding results to reduce API calls.

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | Primary key |
| `address_hash` | varchar(64) | SHA256 of address |
| `latitude` | decimal(10,7) | Geocoded latitude |
| `longitude` | decimal(10,7) | Geocoded longitude |
| `created_at` | timestamp | Cache entry time |

### sync_log

Tracks data synchronization events.

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | Primary key |
| `sync_type` | varchar(50) | Type of sync |
| `table_name` | varchar(50) | Table synced |
| `records_processed` | integer | Number of records |
| `status` | varchar(20) | success, error |
| `error_message` | text | Error details if failed |
| `started_at` | timestamp | Sync start time |
| `completed_at` | timestamp | Sync completion time |

## Views

### v_partner_availability

Computed view showing partner availability status.

```sql
CREATE VIEW v_partner_availability AS
SELECT
    mp.id,
    mp.name,
    mp.office,
    mp.tier,
    mp.publication_rate,
    array_agg(DISTINCT am.make) as approved_makes,
    COUNT(DISTINCT sa.id) as active_assignments
FROM media_partners mp
LEFT JOIN approved_makes am ON mp.id = am.partner_id
LEFT JOIN scheduled_assignments sa ON mp.id = sa.partner_id
    AND sa.status IN ('planned', 'requested', 'active')
GROUP BY mp.id;
```

### v_vehicle_schedule

Computed view showing vehicle assignment timeline.

```sql
CREATE VIEW v_vehicle_schedule AS
SELECT
    v.id,
    v.vin,
    v.make,
    v.model,
    v.office,
    sa.partner_id,
    sa.start_date,
    sa.end_date,
    sa.status
FROM vehicles v
LEFT JOIN scheduled_assignments sa ON v.id = sa.vehicle_id
ORDER BY v.id, sa.start_date;
```

## Common Queries

### Get Available Vehicles

```sql
SELECT * FROM vehicles v
WHERE v.office = 'Los Angeles'
AND v.status = 'available'
AND NOT EXISTS (
    SELECT 1 FROM scheduled_assignments sa
    WHERE sa.vehicle_id = v.id
    AND sa.start_date <= '2024-01-22'
    AND sa.end_date >= '2024-01-15'
);
```

### Check Partner Cooldown

```sql
SELECT * FROM cooldowns
WHERE partner_id = 123
AND make = 'BMW'
AND cooldown_expires > CURRENT_DATE;
```

### Calculate Publication Rate

```sql
SELECT
    partner_id,
    COUNT(*) as total_loans,
    SUM(CASE WHEN clip_received THEN 1 ELSE 0 END) as clips,
    AVG(CASE WHEN clip_received THEN 1 ELSE 0 END) as rate
FROM loan_history
WHERE start_date >= CURRENT_DATE - INTERVAL '24 months'
GROUP BY partner_id
HAVING COUNT(*) >= 3;
```

## Migrations

Database migrations are stored in `backend/migrations/` and should be applied in order.

### Running Migrations

```sql
-- Example migration
ALTER TABLE media_partners
ADD COLUMN publication_rate decimal(5,4);
```

## Backup & Recovery

Supabase handles automated backups. For manual exports:

```bash
pg_dump -h db.xxx.supabase.co -U postgres -d postgres > backup.sql
```

## Performance Optimization

### Recommended Indexes

Additional indexes for common query patterns:

```sql
-- Assignment date lookups
CREATE INDEX idx_assignments_date_range
ON scheduled_assignments (start_date, end_date);

-- Partner-make combinations
CREATE INDEX idx_cooldowns_lookup
ON cooldowns (partner_id, make, cooldown_expires);
```

### Query Optimization Tips

1. Use date range queries with indexed columns
2. Limit result sets with pagination
3. Use materialized views for complex aggregations
4. Avoid SELECT * in production code
