# Phase 7.8: Objective Shaping (Weights, not filters)

## Overview
Phase 7.8 makes scoring weights explicit and configurable, allowing intuitive control over assignment preferences without changing feasibility. All hard constraints remain unchanged - only the objective function is shaped.

## Key Principle
**"Shape the objective, not the feasibility"** - We keep all hard constraints as-is and only adjust how we score and prioritize feasible assignments.

## Configurable Weights

### Default Configuration
```python
W_RANK = 1.0    # Multiplier for rank_weight (already 500-1000)
W_GEO = 100     # Bonus for same-office match
W_PUB = 150     # Bonus for publication rate (0-1 normalized)
W_HIST = 50     # Bonus for prior publication history
```

### Shaped Score Formula
```
score_shaped =
    W_RANK × rank_weight
  + W_GEO × geo_office_match      # 0 or 1
  + W_PUB × norm(pub_rate_24m)    # 0-1 normalized
  + W_HIST × history_published    # 0 or 1
  + BASE_TIEBREAKER               # Tiny deterministic noise
```

## Implementation

### Core Module
`app/solver/objective_shaping.py`:
- `apply_objective_shaping()` - Compute shaped scores for all triples
- `build_shaping_breakdown()` - Report component contributions
- `validate_monotonicity()` - Test weight sensitivity

### Integration
Updated `ortools_solver_v6.py`:
- Applies shaping before optimization
- Uses `score_shaped` instead of original `score`
- Reports shaping breakdown in results

## Behavior Control

### Geographic Preference
Increase `W_GEO` to favor same-office assignments:
```python
# Strong local preference
w_geo=500  # Partners in same office heavily preferred

# Neutral
w_geo=0    # No geographic preference
```

### Publication Rate Preference
Increase `W_PUB` to favor partners with higher publication rates:
```python
# Favor high publishers
w_pub=500  # Strong preference for high pub_rate_24m

# Neutral
w_pub=0    # Publication rate ignored
```

### Rank vs Other Factors
Adjust `W_RANK` to change importance of rank relative to other factors:
```python
# Rank dominates
w_rank=2.0, w_geo=50   # Rank 2x more important

# Balance rank with geography
w_rank=1.0, w_geo=200  # Geo can override small rank differences
```

## Testing Results (100% Passing)

### S6-A: Geo Sensitivity ✅
- Two equal triples except `geo_office_match`
- Higher `W_GEO` correctly selects geo=1

### S6-B: Pub Sensitivity ✅
- Two equal triples except `pub_rate_24m`
- Higher `W_PUB` correctly selects higher rate

### S6-C: No Feasibility Change ✅
- Triple count identical before/after shaping
- Only scores change, not feasibility

### S6-D: Determinism ✅
- Same seed + weights = identical results
- Different seeds may produce different (but valid) results

## Output Structure

### Shaping Breakdown
```json
{
  "weights": {
    "w_rank": 1.0,
    "w_geo": 100,
    "w_pub": 150,
    "w_hist": 50
  },
  "components": {
    "rank_total": 50000,
    "geo_total": 3500,
    "pub_total": 2250,
    "hist_total": 800,
    "total": 56550
  },
  "counts": {
    "geo_matches": 35,
    "with_history": 16,
    "avg_pub_rate": 0.423
  }
}
```

## Usage Examples

### Standard Configuration
```python
result = solve_with_all_constraints(
    triples_df=triples,
    # ... other parameters ...
    w_rank=1.0,
    w_geo=100,
    w_pub=150,
    w_hist=50,
    # ...
)
```

### Favor Local Partners
```python
# Strong preference for same-office partners
result = solve_with_all_constraints(
    # ...
    w_rank=1.0,
    w_geo=500,  # 5x stronger geo preference
    w_pub=100,
    w_hist=50,
    # ...
)
```

### Favor High Publishers
```python
# Prioritize partners with high publication rates
result = solve_with_all_constraints(
    # ...
    w_rank=1.0,
    w_geo=50,
    w_pub=500,  # Strong publication preference
    w_hist=100,
    # ...
)
```

## Monotonic Response Guarantee

The system guarantees monotonic responses to weight changes:
- ↑ `W_GEO` → ↑ share of same-office assignments
- ↑ `W_PUB` → ↑ average publication rate of selected partners
- ↑ `W_HIST` → ↑ partners with publication history
- ↑ `W_RANK` → ↑ importance of rank differences

## Important Properties

### Preserved
✅ Feasibility unchanged - all hard constraints intact
✅ Determinism - same inputs produce same outputs
✅ Performance - still <10s for LA scale
✅ Audit trail - full breakdown of scoring components

### Changed
📝 Scores are now shaped by configurable weights
📝 Objective function includes multiple components
📝 Trade-offs between factors are explicit and tunable

## Interaction with Other Phases

- **Phase 7.2-7.3**: Hard constraints unaffected
- **Phase 7.4s**: Soft caps still subtract penalties after shaped scores
- **Phase 7.5**: Fairness penalties still applied after shaping
- **Phase 7.6**: Budget penalties still applied after shaping
- **Phase 7.7**: Capacity constraints unaffected

The shaping happens BEFORE optimization, then penalties are subtracted:
```
Final Objective = Σ(score_shaped) - cap_penalties - fairness_penalties - budget_penalties
```

## Policy Recommendations

### Default (Balanced)
```python
w_rank=1.0, w_geo=100, w_pub=150, w_hist=50
```

### Local Focus
```python
w_rank=1.0, w_geo=300, w_pub=100, w_hist=50
```

### Publisher Focus
```python
w_rank=1.0, w_geo=50, w_pub=400, w_hist=150
```

### Rank Dominant
```python
w_rank=2.0, w_geo=50, w_pub=75, w_hist=25
```

## Conclusion

Phase 7.8 completes the optimization pipeline by making all scoring factors explicit and configurable. This provides intuitive control over assignment preferences without compromising feasibility or performance. The system now offers full transparency and tunability across all optimization dimensions.