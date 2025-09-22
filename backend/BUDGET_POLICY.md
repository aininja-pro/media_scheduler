# Phase 7.6: Quarterly Budget Constraints Policy

## Overview
Phase 7.6 adds budget awareness to the optimization, respecting quarterly budgets by office × fleet with either soft penalties or hard constraints.

> "We don't just schedule cars—we honor the purse strings." - Godin

## Data Source

**Table**: `budgets`
- `office`: Text (e.g., "Los Angeles", "Atlanta")
- `fleet`: Text, maps to make/brand (e.g., "TOYOTA", "AUDI")
- `year`: Integer
- `quarter`: Text ("Q1", "Q2", "Q3", "Q4")
- `budget_amount`: Numeric (total budget)
- `amount_used`: Numeric (already spent, NULL = 0)

## Configuration

### Default Settings
```python
# Cost model
DEFAULT_COST_PER_ASSIGNMENT = 1000  # Per vehicle-week
cost_per_assignment = {
    'Toyota': 1500,
    'BMW': 2500,
    'Bentley': 5000,
    # ... etc
}

# Penalty weight (soft mode)
DEFAULT_POINTS_PER_DOLLAR = 3  # Points penalty per dollar over budget

# Mode selection
enforce_budget_hard = False  # False = soft penalties, True = hard constraints
enforce_missing_budget = False  # False = no constraint if budget missing
```

## Fleet-Make Mapping

Normalized uppercase mapping with aliases:
```python
FLEET_ALIASES = {
    'VW': 'VOLKSWAGEN',
    'CHEVY': 'CHEVROLET',
    'MERCEDES': 'MERCEDES-BENZ',
    'LAND ROVER': 'LANDROVER',
    # ... etc
}
```

## Budget Calculation

For each office `o`, fleet `f`, quarter `q`, year `y`:

1. **Remaining Budget**:
   ```
   remaining = budget_amount - COALESCE(amount_used, 0)
   ```

2. **Planned Spend**:
   ```
   planned_spend = Σ(cost_per_assignment[make] × selected[v,p,s])
   ```

3. **Over Budget**:
   ```
   over_budget = max(0, planned_spend - remaining)
   ```

## Operating Modes

### Mode A: Soft Budget (Default)
- Allows exceeding budget with penalties
- Penalty = `POINTS_PER_DOLLAR × over_budget`
- Flexible when high-value assignments justify the cost
- Recommended for normal operations

### Mode B: Hard Budget
- Enforces `planned_spend ≤ remaining` as constraint
- No assignments can exceed budget
- Use when: Strict budget compliance required
- Set: `enforce_budget_hard = True`

## Objective Function

```
Maximize:
  total_score
  - λ_cap × Σ(tier_cap_overages)         [Phase 7.4s]
  - λ_fair × Σ(fairness_penalties)       [Phase 7.5]
  - points_per_dollar × Σ(over_budget)   [Phase 7.6]
```

## Edge Cases

1. **Missing Budget Row**:
   - Default: No constraint (unlimited budget)
   - With `enforce_missing_budget=True`: Treat as 0 budget

2. **NULL amount_used**:
   - Always treated as 0

3. **Already Over Budget**:
   - `amount_used > budget_amount`
   - Penalty only on additional spend beyond current

4. **Cross-Quarter Weeks**:
   - Week spans Q3/Q4 boundary
   - Each assignment charged to its start date quarter

## Audit Reporting

### Budget Summary Table
```
office | fleet  | quarter | budget_amount | planned_spend | over_budget | penalty
-------|--------|---------|---------------|---------------|-------------|--------
LA     | TOYOTA | Q3      | 50,000       | 52,000       | 2,000      | 6,000
LA     | HONDA  | Q3      | 40,000       | 35,000       | 0          | 0
```

### Assignment-Level Cost
Each assignment includes:
- `estimated_cost`: Cost for this assignment
- `fleet`: Normalized fleet name
- Budget bucket reference

### Objective Breakdown
```json
{
  "raw_score": 86000,
  "cap_penalty": 0,
  "fairness_penalty": 5400,
  "budget_penalty": 6000,
  "net_score": 74600
}
```

## Tuning Guide

### Points Per Dollar Calibration

| Value | Behavior | Use Case |
|-------|----------|----------|
| 1 | Very permissive | High-margin operations |
| **3** | **Balanced (DEFAULT)** | **Standard operations** |
| 5 | Conservative | Tight budget environment |
| 10+ | Very restrictive | Crisis/austerity mode |

### Finding the Right Value
- Start with 3 points per dollar
- Compare to average assignment score (500-1000)
- At 3 points: $333 overage ≈ losing one B-rank assignment

## Performance Considerations

- Budget constraints add minimal overhead
- Soft mode typically faster than hard mode
- LA scale still solves in <10 seconds

## Validation Checklist

✅ Fleet names correctly normalized and mapped
✅ Quarters correctly determined from dates
✅ Soft mode allows overage with penalties
✅ Hard mode enforces strict limits
✅ Missing budgets handled gracefully
✅ Already-overspent budgets don't double-penalize

## Emergency Procedures

### Budget Exceeded Alert
1. Check if intentional (high-value assignments)
2. Review `budget_summary` for details
3. Consider switching to hard mode temporarily
4. Adjust `points_per_dollar` if needed

### No Budget Found
1. Verify fleet name mapping
2. Check quarter/year calculation
3. Confirm budget data loaded
4. Set `enforce_missing_budget=True` if needed

## Integration Example

```python
result = solve_with_all_constraints(
    # ... other parameters ...
    budgets_df=budgets_df,
    cost_per_assignment={'Toyota': 1500, 'BMW': 2500},
    points_per_dollar=3,
    enforce_budget_hard=False,  # Soft mode
    # ...
)

# Check budget impact
budget_summary = result['budget_summary']
total_overage = budget_summary['over_budget'].sum()
print(f"Total budget overage: ${total_overage:,.0f}")