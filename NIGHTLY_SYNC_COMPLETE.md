# Nightly Data Sync - Complete ✅

**Date**: November 12, 2025
**Status**: Tested and working perfectly
**Test Duration**: 5 minutes 38 seconds
**Total Rows Synced**: 18,214 rows

---

## Summary

Implemented automated nightly sync to pull FMS data via CSV exports every night at 2:00 AM. Successfully syncs 5 tables with special processing for media partners (geocoding + preferred day analysis).

---

## What's Synced Automatically

### 1. **Vehicles** (979 rows)
- Active vehicle inventory
- Source: `active_vehicles.rpt`
- Processing: Standard import

### 2. **Media Partners** (592 rows) ⭐
- Media partner roster
- Source: `media_partners.rpt`
- **Special Processing**:
  - ✅ Geocodes 562 addresses using Google Maps API
  - ✅ Auto-updates 426 preferred days from loan history analysis
  - ✅ Calculates confidence scores for day preferences

### 3. **Loan History** (10,806 rows)
- Historical loan records
- Source: `loan_history.rpt`
- Processing: Bulk insert with chunking

### 4. **Current Activity** (1,122 rows)
- Active loans currently out with partners
- Source: `current_vehicle_activity.rpt`
- Processing: Shows as blue bars in calendar

### 5. **Approved Makes** (4,715 rows)
- Partner make approvals with tier rankings
- Source: `approved_makes.rpt`
- Processing: Partner-make mappings

---

## What Stays Manual

### Operations Data
- **Type**: Excel upload
- **Contents**: Rules, capacity limits, holiday dates
- **Why manual**: Complex multi-sheet format
- **Upload via**: Upload Data tab

### Budgets
- **Type**: Excel upload
- **Contents**: Office/fleet budget tracking
- **Why manual**: Quarterly planning data
- **Upload via**: Upload Data tab

---

## Implementation Details

### Files Created

1. **`backend/app/services/nightly_sync.py`**
   - Sync orchestration service
   - Loops through each table
   - Calls ingest endpoints
   - Provides detailed logging

2. **Admin Endpoints** (in `main.py`):
   - `POST /api/admin/trigger-sync` - Manual trigger
   - `GET /api/admin/sync-status` - Scheduler status
   - `GET /api/admin/sync-config` - View configuration

### Dependencies Added

- **APScheduler 3.10.4** - Async job scheduling
- Added to `requirements.txt`
- Installed in Docker container

### Configuration

**Environment Variables** (in `backend/.env`):

```bash
# Nightly Sync Configuration
SYNC_ENABLED=true           # Enable/disable sync
SYNC_HOUR=2                 # Run at 2:00 AM
SYNC_MINUTE=0
INTERNAL_API_URL=http://backend:8000  # Docker internal network

# CSV Export URLs (all 5 tables configured)
FMS_VEHICLES_CSV_URL=https://reports.driveshop.com/...
FMS_PARTNERS_CSV_URL=https://reports.driveshop.com/...
FMS_LOAN_HISTORY_CSV_URL=https://reports.driveshop.com/...
FMS_CURRENT_ACTIVITY_CSV_URL=https://reports.driveshop.com/...
FMS_APPROVED_MAKES_CSV_URL=https://reports.driveshop.com/...
```

---

## Scheduler Configuration

### APScheduler Setup

**Started on app startup** (in `main.py`):
```python
scheduler.add_job(
    run_nightly_sync,
    CronTrigger(hour=2, minute=0),  # 2:00 AM daily
    id='nightly_fms_sync',
    replace_existing=True
)
scheduler.start()
```

### Schedule
- **Frequency**: Daily
- **Time**: 2:00 AM (configurable via `SYNC_HOUR`/`SYNC_MINUTE`)
- **Timezone**: Server timezone
- **Next run**: Visible via `/api/admin/sync-status`

### Disable Sync

To disable nightly sync (keep manual control):
```bash
SYNC_ENABLED=false
```

---

## Testing Results (Manual Trigger)

### Test Command
```bash
curl -X POST http://localhost:8081/api/admin/trigger-sync
```

### Results

```json
{
  "start_time": "2025-11-12T18:50:46",
  "end_time": "2025-11-12T18:56:25",
  "duration_seconds": 338.87,
  "total_tables": 5,
  "success_count": 5,
  "failure_count": 0,
  "total_rows_processed": 18214
}
```

### Performance
- **Total time**: 5 minutes 38 seconds
- **Vehicles**: ~1 second
- **Media Partners**: ~4-5 minutes (geocoding 562 addresses!)
- **Loan History**: ~15-20 seconds (10,806 rows)
- **Current Activity**: ~5 seconds
- **Approved Makes**: ~5 seconds

### Media Partners Special Processing
```
✅ Auto-updated 426 preferred days from loan history
✅ Geocoded 562 addresses using Google Maps API
```

This means 426 partners now have auto-populated `preferred_day_of_week` with confidence scores, and 562 have accurate latitude/longitude for distance calculations!

---

## Security Considerations

### CSV URLs
- ✅ **Safe to use**: Already accessible to you (used in manual uploads)
- ✅ **No additional risk**: Same URLs you use in UI
- ✅ **FMS authentication**: Built into the report URLs
- ✅ **Read-only**: Only fetches data, doesn't modify FMS

### Internal API Calls
- Uses Docker internal network (`http://backend:8000`)
- Not exposed externally
- Only backend can call backend

### Environment Variables
- Tokens stored in `.env` (gitignored)
- CSV URLs are public report endpoints
- No secrets exposed in logs

---

## Admin Endpoints

### Check Scheduler Status
```bash
curl http://localhost:8081/api/admin/sync-status
```

**Response:**
```json
{
  "scheduler_running": true,
  "next_sync_time": "2025-11-13T02:00:00+00:00",
  "sync_hour": 2,
  "sync_minute": 0,
  "sync_enabled": true
}
```

### View Sync Configuration
```bash
curl http://localhost:8081/api/admin/sync-config
```

**Response:**
```json
{
  "sync_urls": {
    "vehicles": "https://reports.driveshop.com/...",
    "media_partners": "https://reports.driveshop.com/...",
    ...
  },
  "sync_hour": 2,
  "sync_minute": 0,
  "manual_only": ["operations_data", "budgets"]
}
```

### Trigger Manual Sync
```bash
curl -X POST http://localhost:8081/api/admin/trigger-sync
```

**Use cases:**
- Testing after configuration changes
- Emergency data refresh
- Debugging sync issues
- Initial data load

---

## Logging

### Startup Logs
```
INFO:apscheduler.scheduler:Added job "run_nightly_sync" to job store "default"
INFO:app.main:✓ Nightly sync scheduler started - runs daily at 02:00
```

### Sync Logs (during execution)
```
INFO: [Nightly Sync] ========================================
INFO: [Nightly Sync] Starting nightly FMS data sync at 2025-11-12 18:50:46
INFO: [Nightly Sync] Starting sync for vehicles
INFO: [Nightly Sync] ✓ vehicles synced successfully: 979 rows
INFO: [Nightly Sync] Starting sync for media_partners
INFO: [Nightly Sync] ✓ media_partners synced successfully: 592 rows
...
INFO: [Nightly Sync] Success: 5/5 tables
INFO: [Nightly Sync] Total rows processed: 18214
INFO: [Nightly Sync] ========================================
```

### Error Logs (if sync fails)
```
WARNING: [Nightly Sync] ⚠ 1 tables failed to sync
WARNING: [Nightly Sync]   - vehicles: HTTP 404: Report not found
```

---

## Monitoring & Maintenance

### Check Last Sync Results
Monitor backend logs:
```bash
docker logs media_scheduler-backend-1 | grep "Nightly Sync"
```

### Verify Data Freshness
Check database:
```sql
SELECT
  'vehicles' as table_name,
  COUNT(*) as row_count
FROM vehicles
UNION ALL
SELECT 'media_partners', COUNT(*) FROM media_partners
UNION ALL
SELECT 'loan_history', COUNT(*) FROM loan_history
UNION ALL
SELECT 'current_activity', COUNT(*) FROM current_activity
UNION ALL
SELECT 'approved_makes', COUNT(*) FROM approved_makes;
```

### Adjust Sync Timing
Update in `.env`:
```bash
SYNC_HOUR=3     # Run at 3 AM instead
SYNC_MINUTE=30  # Run at 3:30 AM
```

Restart backend for changes to take effect.

---

## Troubleshooting

### Sync Fails with Timeout
**Cause**: CSV export is very large or slow

**Solution**: Increase timeout in `nightly_sync.py`:
```python
async with httpx.AsyncClient(timeout=1200.0) as client:  # 20 minutes
```

### Geocoding Fails
**Cause**: Google Maps API quota exceeded or key issue

**Result**: Non-critical - sync continues, addresses not geocoded
**Check**: Backend logs for geocoding errors

### Scheduler Not Running
**Check**: `/api/admin/sync-status`
**Fix**: Ensure `SYNC_ENABLED=true` in `.env` and restart backend

---

## Benefits

### Before (Manual)
- ❌ Manually click "Upload" for each table
- ❌ Wait for each import to complete
- ❌ Remember to do it regularly
- ❌ Risk of stale data

### After (Automatic)
- ✅ Runs automatically every night
- ✅ All 5 tables updated in one job
- ✅ Includes geocoding + preferred day analysis
- ✅ Fresh data every morning
- ✅ Manual trigger available for testing
- ✅ Detailed logging and error handling

---

## Production Deployment Notes

### Render Configuration

Add environment variable in Render dashboard:
```
INTERNAL_API_URL=http://localhost:8000
```

(In production, the backend calls itself on localhost since it's a single service)

### Monitoring Recommendations

1. **Set up alerts** for failed syncs (Sentry, email, etc.)
2. **Monitor sync duration** - should stay under 10 minutes
3. **Track row counts** - sudden changes indicate issues
4. **Check geocoding success rate** - should be >90%

### Adjust Timing for Production

Check when FMS exports refresh:
- If FMS exports at 1:00 AM, run sync at 2:00 AM (current)
- If different, adjust `SYNC_HOUR` accordingly
- Leave 30-60 minute buffer after FMS export generation

---

## Future Enhancements

### Option 1: Retry Logic
Add automatic retry for failed syncs:
```python
max_retries = 3
for attempt in range(max_retries):
    result = await sync_single_table(table, url)
    if result['success']:
        break
    await asyncio.sleep(60)  # Wait 1 minute before retry
```

### Option 2: Sync Notifications
Send email/Slack notification on:
- Successful sync completion
- Sync failures
- Unusual row count changes

### Option 3: Incremental Sync
Instead of full refresh, sync only changes:
- Track last sync timestamp
- Request incremental data from FMS
- Faster sync times

### Option 4: Parallel Sync
Sync tables in parallel instead of sequentially:
```python
results = await asyncio.gather(*[
    sync_single_table(table, url)
    for table, url in SYNC_URLS.items()
])
```

---

## Summary

✅ **Nightly sync is production-ready!**

**What it does:**
- Automatically syncs 5 FMS tables every night at 2 AM
- Geocodes media partner addresses (Google Maps API)
- Analyzes loan history for preferred days
- Processes 18,000+ rows in ~6 minutes
- Provides admin endpoints for monitoring

**What's manual:**
- Operations Data (Excel - complex format)
- Budgets (Excel - quarterly planning)

**Security:**
- Uses same FMS CSV URLs you already use manually
- Internal Docker network communication
- No additional access required

**Next steps:**
- Runs automatically starting tonight at 2:00 AM
- Monitor logs after first auto-run
- Adjust timing if needed

---

**Status**: Complete and tested ✅
**Next Sync**: 2025-11-13 at 02:00:00 UTC
**Last Updated**: November 12, 2025
