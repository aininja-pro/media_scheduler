# Phase 7.7: Dynamic Capacity Management

## Overview
Phase 7.7 enhances the capacity constraints to support day-specific slots, blackout days, travel days, and special capacity notes from the `ops_capacity_calendar` table.

## Key Features

### 1. Day-Specific Capacity
- Each day can have a different number of slots
- Defaults: 15 slots weekdays, 0 slots weekends
- Fully configurable per date

### 2. Blackout Days
- Days with `slots=0` are blackout days
- No assignments allowed on blackout days
- Automatically identified and reported

### 3. Travel Days
- Days with reduced capacity and "travel" in notes
- Assignments allowed but limited
- Special reporting for visibility

### 4. Capacity Notes
- Any day can have notes explaining capacity changes
- Notes surface in reports for transparency
- Examples: "Company Holiday", "Half-day operations", "Travel day - team at conference"

## Implementation

### Core Module
`app/solver/dynamic_capacity.py`:
- `load_capacity_calendar()` - Load day-specific slots and notes
- `identify_special_days()` - Categorize blackouts, travel days, etc.
- `build_capacity_report()` - Comprehensive usage report with notes
- `validate_capacity_compliance()` - Check assignments against capacity

### Integration
Updated `ortools_solver_v6.py`:
- Uses dynamic capacity instead of static daily limits
- Reports special days in solution
- Includes capacity notes in output

## Data Structure

### Input: `ops_capacity_calendar`
```python
{
    'office': 'Los Angeles',
    'date': '2025-09-24',
    'slots': 0,  # Blackout
    'notes': 'Company Holiday'
}
```

### Output: Enhanced Reports
```python
{
    'daily_usage': [
        {
            'date': '2025-09-24',
            'day': 'Wednesday',
            'capacity': 0,
            'used': 0,
            'remaining': 0,
            'utilization_pct': 0.0,
            'notes': 'Company Holiday'
        }
    ],
    'special_days': {
        'blackouts': [{'date': '2025-09-24', 'day': 'Wednesday', 'notes': 'Company Holiday'}],
        'travel_days': [],
        'reduced_capacity': [],
        'increased_capacity': []
    },
    'capacity_notes': [
        {'date': '2025-09-24', 'day': 'Wednesday', 'notes': 'Company Holiday'}
    ]
}
```

## Testing

### Mini-Tests (100% Passing)
- **C7-A Blackout**: Wednesday slots=0, no assignments allowed ✅
- **C7-B Tighten**: Friday reduced to 2 slots, only 2 assignments ✅
- **C7-C Notes Surfaced**: Travel day notes appear in capacity_notes ✅
- **Capacity Validation**: Detects violations correctly ✅

### Test Command
```bash
python3 test_phase77_mini_tests.py
```

## Configuration

### Default Capacity
```python
DEFAULT_WEEKDAY_SLOTS = 15  # Mon-Fri default
DEFAULT_WEEKEND_SLOTS = 0   # Sat-Sun default (blackout)
```

### Special Day Detection
- **Blackout**: `slots == 0`
- **Travel Day**: `'travel' in notes.lower()`
- **Reduced**: `slots < DEFAULT_WEEKDAY_SLOTS`
- **Increased**: `slots > DEFAULT_WEEKDAY_SLOTS`

## Benefits

1. **Flexibility**: Each day can have unique capacity
2. **Transparency**: Notes explain capacity changes
3. **Safety**: Blackout days prevent invalid assignments
4. **Visibility**: Special days highlighted in reports
5. **Audit Trail**: Complete capacity utilization tracking

## Integration with Other Phases

- Works seamlessly with all other constraints (7.2-7.6)
- Capacity is a HARD constraint (no violations allowed)
- Other phases respect dynamic capacity limits
- Maintains <10s performance at LA scale

## Usage Example

```python
from app.solver.ortools_solver_v6 import solve_with_all_constraints

# ops_capacity_df includes day-specific slots and notes
result = solve_with_all_constraints(
    triples_df=triples,
    ops_capacity_df=ops_capacity_with_notes,  # Dynamic capacity data
    # ... other parameters ...
)

# Access enhanced reports
daily_usage = result['daily_usage']  # Includes notes
special_days = result['special_days']  # Categorized special days
capacity_notes = result['capacity_notes']  # All days with notes
```

## Next Steps

Phase 7.7 completes the dynamic capacity enhancement. The system now supports:
- ✅ VIN uniqueness (7.2)
- ✅ Dynamic daily capacity (7.2/7.7)
- ✅ Cooldown periods (7.3)
- ✅ Soft tier caps (7.4s)
- ✅ Distribution fairness (7.5)
- ✅ Quarterly budgets (7.6)
- ✅ Day-specific capacity with notes (7.7)

All phases are integrated and working together in the complete solver!