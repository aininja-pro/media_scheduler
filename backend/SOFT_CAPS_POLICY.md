# Soft Tier Caps Policy Documentation

## Overview
Phase 7.4s implements soft tier caps using penalties in the objective function rather than hard constraints. This provides flexibility while maintaining strong preferences for staying within caps.

## Default Policy Settings

### Core Parameters
```python
# Primary configuration
LAMBDA_CAP = 800                    # Penalty weight per unit overage
allow_override_zero_caps = False    # Hard block cap=0 rules (don't override)
max_total_delta_overage = None      # No hard budget limit (optional constraint)
rolling_window_months = 12           # Look back 12 months for usage
```

### Cap Resolution Hierarchy
1. **Exact Rule Match**: Check RULES table for (make, rank) → loan_cap_per_year
2. **Rank Defaults** (if no rule):
   - A+ → Unlimited (no penalty)
   - A → 100 loans/year
   - B → 50 loans/year
   - C → 10 loans/year

### Penalty Calculation
```python
# For each (partner, make) pair:
current_overage = max(0, used_12m - cap)
future_overage = max(0, used_12m + new_assignments - cap)
delta_overage = future_overage - current_overage  # Only NEW violations
penalty = LAMBDA_CAP * delta_overage
```

## Lambda Tuning Guide

| Lambda | Behavior | Use Case |
|--------|----------|----------|
| 400 | Permissive | Testing, high demand periods |
| **800** | **Balanced (DEFAULT)** | **Standard operations** |
| 1200 | Restrictive | Conservative scheduling |
| 2000 | Very Restrictive | Minimal violations allowed |

### Lambda Selection Criteria
- **Score Context**: Lambda=800 ≈ losing one B-rank assignment
- **Business Impact**: Balance between utilization and fairness
- **Monitoring**: Track penalty trends to adjust if needed

## Zero-Cap Handling

### Default Behavior (allow_override_zero_caps = False)
- Rules with `loan_cap_per_year = 0` are **hard blocks**
- Triples matching zero-cap rules are removed before solver
- **Cannot be overridden** with penalties

### Override Mode (allow_override_zero_caps = True)
- Zero caps treated as soft constraints
- High penalties applied but assignments possible
- Use only in exceptional circumstances

## Optional Constraints

### max_total_delta_overage
- **Default**: None (unlimited)
- **Purpose**: Hard budget on total new violations
- **Example**: `max_total_delta_overage = 10` → at most 10 total units over all caps
- **Use Case**: Gradual cap relaxation during transitions

## Implementation Pipeline

```
7.1 Feasible Triples
    ↓
7.3 Cooldown Filter (HARD)
    ↓
[Remove zero-cap triples if !allow_override]
    ↓
7.2+7.4s OR-Tools Solver
    - VIN uniqueness (HARD)
    - Daily capacity (HARD)
    - Tier caps (SOFT via penalties)
```

## Monitoring & Reporting

### Key Metrics
1. **total_cap_penalty**: Sum of all penalties incurred
2. **total_delta_overage**: Sum of new violations
3. **pairs_over_cap**: Count of (partner, make) exceeding caps
4. **penalty_percentage**: Penalty as % of total score

### Audit Report Fields
```json
{
  "penalty_summary": {
    "total_penalty": 0,
    "total_delta_overage": 0,
    "pairs_with_penalties": 0,
    "pairs_at_cap": 7,
    "pairs_over_cap": 0
  },
  "overcap_table": [
    {
      "person_id": "...",
      "make": "Honda",
      "rank": "B",
      "used_12m": 48,
      "cap": 50,
      "assigned_this_week": 3,
      "delta_overage": 1,
      "penalty": 800
    }
  ],
  "objective_breakdown": {
    "raw_score": 86295,
    "penalty": 0,
    "net_score": 86295
  }
}
```

## UI Integration

### Stage Summary Display
```
✓ Soft Tier Caps Active
• Removed by zero-cap rules: 3,822
• Cap penalties: $0
• Partners at cap: 7
```

### Assignment Details
Show alongside each assignment:
```
Partner 972 + Volvo
Used: 48/50 (remaining: 2)
```

## Testing & Validation

### Acceptance Criteria
✅ VIN uniqueness maintained
✅ Daily capacity respected
✅ Zero-cap rules enforced (when !allow_override)
✅ Monotonic lambda behavior (higher λ → fewer violations)
✅ Deterministic with fixed seed
✅ LA week solves < 10 seconds

### Stress Test Results
- Normal capacity (75 slots): No penalties needed
- Reduced capacity (40 slots): System adapts, still no penalties
- Extreme scenarios: Penalties applied appropriately

## Production Recommendations

1. **Start Conservative**: Use LAMBDA_CAP=800 initially
2. **Monitor Weekly**: Track penalty trends and cap violations
3. **Adjust Gradually**: Modify lambda based on business feedback
4. **Document Changes**: Log any policy adjustments with rationale
5. **Review Quarterly**: Assess cap levels and rule effectiveness

## Emergency Procedures

### High Penalty Week
1. Review overcap_table for patterns
2. Check for data anomalies (missing vehicles, partner changes)
3. Consider temporary lambda reduction if justified
4. Document decision and revert after resolution

### Zero Assignments
1. Verify feasible triples generated (Phase 7.1)
2. Check cooldown filter not too aggressive (Phase 7.3)
3. Confirm capacity settings correct
4. Review zero-cap rules for unintended blocks