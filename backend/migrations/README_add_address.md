# Adding Partner Address Fields

## What Changed

Your client added a new `partner_address` field at the end of both:
- **loan_history** CSV (e.g., "3024 Hidden Forest Court, Marietta, GA")
- **current_activity** CSV (e.g., "5000 Kristie Way, Chamblee, GA")

## Changes Made

1. **Database Schema** - Added `partner_address` column to both tables
2. **Pydantic Schemas** - Updated ingest validation to accept the new field
3. **Auto-update Preferred Days** - After media_partners ingest, automatically recalculates preferred days from loan history

## To Apply Changes

### Step 1: Run the SQL migration
```bash
# Copy the SQL and run it in Supabase SQL Editor, or use psql:
psql <your-connection-string> -f migrations/add_address_fields.sql
```

### Step 2: Restart the backend
The backend should auto-reload, but if needed:
```bash
# Find the uvicorn process and restart it
ps aux | grep uvicorn
kill -HUP <process-id>
```

### Step 3: Re-ingest your data
Now you can ingest the updated CSVs with the address field:
- loan_history with 13 fields (added partner_address at end)
- current_activity with 8 fields (added partner_address at end)

## Files Modified

- `backend/migrations/add_address_fields.sql` - Database migration
- `backend/app/schemas/ingest.py` - Added `partner_address: Optional[str]` to both schemas
- `backend/app/routers/ingest.py` - Auto-updates preferred days after media_partners ingest

## Notes

- The `partner_address` field is **optional** - old data without it will still work
- Preferred days are now automatically calculated after each media_partners ingest
- No need to manually preserve preferred days anymore - they're regenerated fresh each time
