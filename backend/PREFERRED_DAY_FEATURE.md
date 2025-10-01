# Preferred Day Feature Implementation

## Overview
Add ability to prioritize scheduling partners on their "normal" pickup day based on historical patterns.

## Analysis Results
- **65 partner-office combinations** have clear preferred days (≥5 loans, ≥40% confidence)
- **Average confidence: 83.9%** (very strong patterns!)
- **Day distribution**: Tuesday (17), Wednesday (15), Thursday (13), Monday (13), Friday (7)

## Implementation Steps

### 1. Database Migration ✅ READY
**File**: `migrations/add_preferred_day_columns.sql`

Adds to `media_partners` table:
- `preferred_day_of_week` (TEXT): 'Monday', 'Tuesday', etc.
- `preferred_day_confidence` (DECIMAL): 0-100 percentage
- Index on `(office, preferred_day_of_week)`

**Action Required**: Run this SQL in Supabase SQL Editor

### 2. Analysis Script ✅ COMPLETE
**File**: `analyze_preferred_days.py`

Analyzes `loan_history` to find patterns:
- Groups by `(person_id, office, day_of_week)`
- Weights recent loans (last 12 months) 2x more
- Requires ≥5 loans and ≥40% confidence
- Exports recommendations to CSV

**Usage**:
```bash
docker exec media_scheduler-backend-1 python3 analyze_preferred_days.py
```

### 3. Update Script ✅ COMPLETE
**File**: `update_preferred_days.py`

Updates `media_partners` table with preferred days:
- Takes analysis results and writes to database
- Supports dry-run mode for safety
- Can clear existing values
- Should be run monthly/quarterly

**Usage**:
```bash
# Dry run (preview changes)
docker exec media_scheduler-backend-1 python3 update_preferred_days.py --dry-run

# Actually update
docker exec media_scheduler-backend-1 python3 update_preferred_days.py

# Clear and update with custom thresholds
docker exec media_scheduler-backend-1 python3 update_preferred_days.py --clear --min-loans 3 --min-confidence 0.5
```

### 4. Solver Integration (TODO)
**Files to modify**:
- `app/solver/ortools_feasible_v2.py` - Add `preferred_day_match` to triples
- `app/solver/objective_shaping.py` - Add `w_preferred_day` weight
- `app/solver/ortools_solver_v6.py` - Add parameter
- `app/routers/ui_phase7.py` - Add toggle parameter

**Changes**:
1. Join `media_partners.preferred_day_of_week` into triples
2. Calculate `preferred_day_match` = 1 if start_day matches preferred day
3. Add to objective: `score += w_preferred_day * preferred_day_match`
4. Default `w_preferred_day = 0` (off), set to ~150 when toggle enabled

### 5. UI Toggle (TODO)
**File**: `frontend/src/pages/Optimizer.jsx`

Add checkbox in Business Rules section:
```
☐ Prioritize Partner Normal Days
```

When checked: passes `prefer_normal_days=true` to API → `w_preferred_day=150`

## Testing Plan
1. Run migration in Supabase
2. Run update script with --dry-run
3. Review proposed changes
4. Run actual update
5. Verify data in database
6. Implement solver integration
7. Add UI toggle
8. Test scheduling with toggle on/off
9. Compare results - should see more matches to preferred days

## Expected Behavior
- **Toggle OFF** (default): No preference for normal days, schedule optimally
- **Toggle ON**: Soft preference for partner normal days (~150 weight)
  - Partner with Monday preference gets bonus for Monday assignments
  - Still allows other days if needed (not a hard constraint)
  - Should see higher % of assignments matching preferred days

## Maintenance
- Re-run `update_preferred_days.py` monthly/quarterly to refresh patterns
- Can adjust thresholds if needed (--min-loans, --min-confidence)
- Monitor confidence scores - low confidence may indicate changing patterns
