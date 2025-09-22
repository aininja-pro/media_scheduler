# Phase 7.5: Distribution/Fairness Policy

## Overview
Phase 7.5 adds soft penalties to discourage over-concentration of assignments to the same partner, promoting wider distribution while maintaining flexibility.

> "We prefer a wider chorus, not just the loudest solo." - Godin

## Recommended Default: Mode B (Stepped Penalties)

```python
# Mode B Configuration - RECOMMENDED
FAIR_TARGET_PER_PARTNER = 1    # Prefer 1 assignment per partner
LAMBDA_FAIR = 200              # Light penalty for 2nd assignment
FAIR_STEP_UP = 400             # Heavier penalty for 3rd+ assignments
```

### Why Mode B?
> "Two per partner max—soft, not hard. Good default." - Hormozi

Mode B provides the practical middle ground:
- Wide spread across partners (40-50 partners typically)
- Flexibility for 2nd assignment when needed
- Strong discouragement of 3rd+ assignments
- Maintains feasibility when calendar is tight

## Penalty Calculation

### Mode A (Linear)
```python
penalty_p = LAMBDA_FAIR * max(0, n_p - FAIR_TARGET)
```
- Simple linear penalty for each assignment beyond target
- Good for basic spreading

### Mode B (Stepped) - RECOMMENDED
```python
penalty_p = LAMBDA_FAIR * max(0, n_p - 1) + FAIR_STEP_UP * max(0, n_p - 2)
```
- Light penalty for 2nd assignment (λ=200)
- Heavier penalty for 3rd+ (additional λ=400)
- Creates natural "soft ceiling" at 2 per partner

## Multi-Lens Metrics

> "Measure with more than one lens so the story is true." - Godin

### Primary Metrics
1. **Gini Coefficient** (0=perfect equality, 1=monopoly)
   - Target: < 0.20 (good distribution)
   - Calculated only for partners who received assignments

2. **HHI (Herfindahl-Hirschman Index)**
   - Target: < 0.10 (low concentration)
   - Sum of squared market shares

3. **Top-k Share**
   - Top-5 share: < 40% (no small group dominance)
   - Top-1 share: < 15% (no single partner dominance)

### LA Test Results

| Configuration | Partners | Max/Partner | Gini | HHI | Top-5 | Penalty |
|--------------|----------|------------|------|-----|-------|---------|
| No Fairness | 7 | 24 | 0.404 | High | 71% | $0 |
| Mode A (λ=200) | 38 | 8 | 0.404 | Med | 53% | $7,400 |
| **Mode B (Recommended)** | **48** | **2** | **0.158** | **Low** | **21%** | **$5,400** |
| Strong (λ=400) | 75 | 1 | 0.000 | Min | 7% | $0 |

## UI Integration

### Status Chip Display
```
🔵 Fairness: λ=200+400 • 48P • Max=2 • Gini=0.16
```

### Hover Details
```
Mode B Distribution
Partners assigned: 48
Max per partner: 2
Gini coefficient: 0.158
HHI: 0.08
Top-5 share: 21%
Status: Good
```

### Color Coding
- 🟢 Excellent: Gini < 0.10
- 🔵 Good: Gini 0.10-0.20
- 🟡 Fair: Gini 0.20-0.30
- 🟠 Concentrated: Gini > 0.30

## Implementation Pipeline

```
7.1 Feasible Triples
    ↓
7.3 Cooldown Filter (HARD)
    ↓
7.2+7.4s+7.5 OR-Tools Solver
    - VIN uniqueness (HARD)
    - Daily capacity (HARD)
    - Tier caps (SOFT - λ_cap penalties)
    - Fairness (SOFT - λ_fair penalties)
```

## Objective Function

```
Maximize:
  total_score
  - λ_cap * Σ(tier_cap_overages)
  - λ_fair * Σ(assignments_beyond_target)
  - λ_step * Σ(assignments_beyond_2)  [Mode B only]
```

## Tuning Guide

### Light Distribution (λ=100-200)
- Allows concentration when beneficial
- Minimal impact on total score
- Use when: High demand, limited partners

### Standard Distribution (λ=200 + step=400) - RECOMMENDED
- Balanced spread vs efficiency
- Natural limit at 2 per partner
- Use when: Normal operations

### Strong Distribution (λ=400-600)
- Forces near-equal distribution
- May sacrifice total score
- Use when: Fairness is critical

## Validation Checklist

✅ **Behavior**: Equal scores → spread; necessary → concentrate with penalty
✅ **Metrics**: Show partners, max/partner, Gini, HHI, Top-5
✅ **Performance**: < 10 seconds for LA scale
✅ **Determinism**: Same seed → same distribution
✅ **Flexibility**: Maintains feasibility even under stress

## Emergency Procedures

### High Concentration Detected (Gini > 0.4)
1. Check if enough eligible partners exist
2. Verify scores aren't too skewed
3. Consider increasing λ_fair temporarily
4. Review partner eligibility requirements

### Perfect Equality Forced (All get 1)
1. May indicate λ_fair too high
2. Check if hurting total score significantly
3. Consider reducing to Mode B defaults

## Sign-Off

- [x] Multi-lens metrics implemented (Gini, HHI, Top-k)
- [x] Mode B tested and validated
- [x] UI chips and reporting ready
- [x] Performance maintained (< 10s)
- [x] All mini-tests passing (F1-F5)