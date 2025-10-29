# Optimizer Diagnostics Integration Guide

## Overview

The optimizer diagnostics system explains why the optimizer didn't fill all available capacity slots. It provides:
- Daily capacity breakdown showing utilization per day
- Primary bottlenecks preventing full utilization
- Actionable recommendations to improve capacity filling

## Backend Implementation

### 1. Diagnostic Module (`app/solver/optimizer_diagnostics.py`)

The `build_diagnostics()` function analyzes:
- **Feasibility funnel**: How many triples at each filtering stage
- **Constraint bottlenecks**: Which constraints blocked assignments
- **Daily utilization**: Slot usage per start day
- **Recommendations**: Specific actions to improve utilization

### 2. Solver Integration (`app/solver/ortools_solver_v6.py`)

Added three new parameters to `solve_with_all_constraints()`:
```python
vehicles_df: Optional[pd.DataFrame] = None,  # For diagnostic context
partners_df: Optional[pd.DataFrame] = None,  # For diagnostic context
enable_diagnostics: bool = True              # Toggle diagnostics on/off
```

Diagnostics are built after solving and included in the return dict:
```python
return {
    ...
    'diagnostics': diagnostics  # New field
}
```

### 3. API Integration (`app/routers/ui_phase7.py`)

The `/ui/phase7/run` endpoint now:
1. Passes `vehicles_df` and `partners_df` to the solver
2. Includes diagnostics in the response

## Frontend Implementation

### Component: `OptimizerDiagnostics.jsx`

Located at: `frontend/src/components/OptimizerDiagnostics.jsx`

**Props:**
- `diagnostics`: The diagnostics object from the API response

**Usage:**
```jsx
import OptimizerDiagnostics from '../components/OptimizerDiagnostics';

function OptimizerPage() {
  const [result, setResult] = useState(null);

  // After running optimizer...
  const runOptimizer = async () => {
    const response = await fetch('/ui/phase7/run', {
      method: 'POST',
      body: JSON.stringify(request),
      headers: { 'Content-Type': 'application/json' }
    });
    const data = await response.json();
    setResult(data);
  };

  return (
    <div>
      {/* Existing assignments table */}
      <AssignmentsTable assignments={result?.assignments} />

      {/* NEW: Diagnostics explanation below assignments */}
      <OptimizerDiagnostics diagnostics={result?.diagnostics} />
    </div>
  );
}
```

## Diagnostic Data Structure

### Response Format

```json
{
  "diagnostics": {
    "summary": {
      "total_capacity": 150,
      "total_assigned": 78,
      "total_empty": 72,
      "utilization_pct": 52.0,
      "total_feasible_triples": 12219,
      "total_vehicles_available": 126,
      "total_partners_eligible": 131
    },
    "daily_diagnostics": [
      {
        "day": "Mon 27",
        "date": "2025-10-27",
        "total_capacity": 30,
        "existing_count": 6,
        "available_capacity": 24,
        "assigned": 1,
        "empty_slots": 23,
        "utilization_pct": 4.2,
        "feasible_triples": 2500,
        "unique_vehicles": 45,
        "unique_partners": 85,
        "bottlenecks": [
          {
            "type": "vehicle_shortage",
            "severity": "high",
            "description": "Only 45 vehicles available for this start day",
            "impact": 23,
            "suggestion": "Review vehicle availability requirements (min_available_days)"
          }
        ]
      },
      // ... more days
    ],
    "primary_bottlenecks": [
      {
        "type": "vehicle_shortage",
        "severity": "high",
        "description": "Some days have insufficient vehicles available",
        "total_impact": 42,
        "affected_days": 2,
        "suggestion": "Check min_available_days setting (should be 8 for 8-day loans)"
      },
      {
        "type": "partner_day_limit",
        "severity": "high",
        "description": "Partner-day limit: 85 partners × 1 slots = 85 max",
        "total_impact": 30,
        "affected_days": 2,
        "suggestion": "Increase max_per_partner_per_day to 2 (could add ~85 slots)"
      }
    ],
    "recommendations": [
      {
        "priority": "high",
        "action": "Increase Partner-Day Limit",
        "description": "Change max vehicles per partner per day from 1 to 2",
        "estimated_impact": "Could add ~30 assignments",
        "implementation": "Adjust 'Max Vehicles per Media Partner per Day' setting to 2"
      },
      {
        "priority": "high",
        "action": "Review Vehicle Availability Requirements",
        "description": "Some days have insufficient vehicles available",
        "estimated_impact": "Could add ~42 assignments",
        "implementation": "Check min_available_days setting (should be 8 for 8-day loans)"
      }
    ]
  }
}
```

## Bottleneck Types

The diagnostic system identifies these bottleneck types:

### 1. `no_capacity`
- **Severity**: info
- **Meaning**: Day has 0 available capacity (blackout or fully booked)
- **Action**: None needed (expected)

### 2. `fully_utilized`
- **Severity**: success
- **Meaning**: All available capacity is being used
- **Action**: None needed (excellent!)

### 3. `no_feasible_triples`
- **Severity**: critical
- **Meaning**: No vehicle-partner combinations possible for this day
- **Action**: Check vehicle availability and partner eligibility

### 4. `insufficient_triples`
- **Severity**: critical
- **Meaning**: Fewer feasible triples than capacity slots
- **Action**: Increase vehicle availability or partner eligibility

### 5. `vehicle_shortage`
- **Severity**: high
- **Meaning**: Not enough vehicles available for consecutive days
- **Action**: Review `min_available_days` parameter (should match loan length)

### 6. `partner_day_limit`
- **Severity**: high
- **Meaning**: Not enough partners available due to per-day limits
- **Action**: Increase `max_per_partner_per_day` setting

### 7. `optimizer_decision`
- **Severity**: medium
- **Meaning**: Optimizer chose not to fill slots (optimizing for score/fairness)
- **Action**: Reduce fairness penalty or adjust scoring weights

## Testing

To test the diagnostics:

1. Run the optimizer with current settings
2. Check the API response includes the `diagnostics` field
3. Verify the frontend displays the diagnostics component
4. Confirm bottlenecks make sense (e.g., Mon/Tue show vehicle_shortage)

## Known Issues & Future Improvements

### Current Limitations:
- Diagnostics don't account for cooldown period filtering (done before solver)
- No breakdown by make/model (which vehicle types are constrained)
- No breakdown by partner tier (which partner ranks are constrained)

### Planned Enhancements:
- Add "What-if" simulator: Show estimated impact of parameter changes
- Add historical comparison: Compare this week to previous weeks
- Add constraint relaxation suggestions: Auto-detect which constraint to relax

## Configuration

### Disable Diagnostics
To disable diagnostics (e.g., for performance in production):

```python
solver_result = solve_with_all_constraints(
    ...
    enable_diagnostics=False  # Disable diagnostic collection
)
```

### Customize Diagnostic Display
The frontend component can be customized via CSS or by modifying `OptimizerDiagnostics.jsx`:
- Change color scheme (see `severityColors` mapping)
- Show/hide specific sections
- Add additional metrics

## Summary

The diagnostic system provides transparency into optimizer behavior, helping users understand:
1. **Why** capacity isn't fully utilized
2. **What** constraints are blocking assignments
3. **How** to improve capacity filling

This addresses the client's requirement: "I need to know why the Optimizer did what it did."
