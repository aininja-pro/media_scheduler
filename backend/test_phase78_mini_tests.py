"""
Minimal tests for Phase 7.8 (Objective Shaping).

Tests S6-A through S6-D as specified in the requirements.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.solver.ortools_solver_v6 import solve_with_all_constraints
from app.solver.objective_shaping import (
    apply_objective_shaping,
    DEFAULT_W_RANK,
    DEFAULT_W_GEO,
    DEFAULT_W_PUB,
    DEFAULT_W_HIST
)


def test_s6a_geo_sensitivity():
    """S6-A: Two equal triples except geo_office_match; with higher W_GEO, geo=1 is chosen."""
    print("\n" + "="*60)
    print("S6-A: GEO SENSITIVITY")
    print("="*60)

    # Two vehicles, equal except for geo_office_match
    triples = pd.DataFrame([
        {'vin': 'V1', 'person_id': 'P001', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Camry', 'office': 'LA',
         'rank': 'A', 'rank_weight': 1000,
         'geo_office_match': 0,  # Different office
         'pub_rate_24m': 0.5,
         'history_published': 0},
        {'vin': 'V2', 'person_id': 'P001', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Camry', 'office': 'LA',
         'rank': 'A', 'rank_weight': 1000,
         'geo_office_match': 1,  # Same office
         'pub_rate_24m': 0.5,
         'history_published': 0},
    ])

    ops_capacity = pd.DataFrame([
        {'office': 'LA', 'date': '2025-09-22', 'slots': 1}  # Can only pick one
    ])

    approved = pd.DataFrame([
        {'person_id': 'P001', 'make': 'Toyota', 'rank': 'A'}
    ])

    # Test with low W_GEO - should be roughly random
    result_low = solve_with_all_constraints(
        triples_df=triples,
        ops_capacity_df=ops_capacity,
        approved_makes_df=approved,
        loan_history_df=pd.DataFrame(),
        rules_df=pd.DataFrame(),
        budgets_df=pd.DataFrame(),
        week_start='2025-09-22',
        office='LA',
        w_rank=1.0,
        w_geo=0,  # No geo bonus
        w_pub=0,
        w_hist=0,
        lambda_cap=0,
        lambda_fair=0,
        seed=42,
        verbose=False
    )

    # Test with high W_GEO - should prefer geo=1
    result_high = solve_with_all_constraints(
        triples_df=triples,
        ops_capacity_df=ops_capacity,
        approved_makes_df=approved,
        loan_history_df=pd.DataFrame(),
        rules_df=pd.DataFrame(),
        budgets_df=pd.DataFrame(),
        week_start='2025-09-22',
        office='LA',
        w_rank=1.0,
        w_geo=500,  # High geo bonus
        w_pub=0,
        w_hist=0,
        lambda_cap=0,
        lambda_fair=0,
        seed=42,
        verbose=False
    )

    selected_high = result_high['selected_assignments']
    if selected_high:
        selected_vin = selected_high[0]['vin']
        geo_match = triples[triples['vin'] == selected_vin]['geo_office_match'].iloc[0]
        print(f"With W_GEO=500: Selected VIN={selected_vin}, geo_office_match={geo_match}")

        shaping = result_high.get('shaping_breakdown', {})
        if shaping:
            counts = shaping.get('counts', {})
            print(f"Geo matches: {counts.get('geo_matches', 0)}/{len(selected_high)}")

    if selected_high and geo_match == 1:
        print("✅ PASS: Higher W_GEO correctly prefers same-office match")
        return True
    else:
        print("❌ FAIL: Expected geo=1 selection with high W_GEO")
        return False


def test_s6b_pub_sensitivity():
    """S6-B: Two equal triples except pub_rate_24m; higher W_PUB picks the higher rate."""
    print("\n" + "="*60)
    print("S6-B: PUB SENSITIVITY")
    print("="*60)

    # Two vehicles, equal except for pub_rate_24m
    triples = pd.DataFrame([
        {'vin': 'V1', 'person_id': 'P001', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Camry', 'office': 'LA',
         'rank': 'A', 'rank_weight': 1000,
         'geo_office_match': 1,
         'pub_rate_24m': 0.2,  # Low publication rate
         'history_published': 0},
        {'vin': 'V2', 'person_id': 'P001', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Camry', 'office': 'LA',
         'rank': 'A', 'rank_weight': 1000,
         'geo_office_match': 1,
         'pub_rate_24m': 0.8,  # High publication rate
         'history_published': 0},
    ])

    ops_capacity = pd.DataFrame([
        {'office': 'LA', 'date': '2025-09-22', 'slots': 1}
    ])

    approved = pd.DataFrame([
        {'person_id': 'P001', 'make': 'Toyota', 'rank': 'A'}
    ])

    # Test with high W_PUB - should prefer higher pub_rate
    result = solve_with_all_constraints(
        triples_df=triples,
        ops_capacity_df=ops_capacity,
        approved_makes_df=approved,
        loan_history_df=pd.DataFrame(),
        rules_df=pd.DataFrame(),
        budgets_df=pd.DataFrame(),
        week_start='2025-09-22',
        office='LA',
        w_rank=1.0,
        w_geo=0,
        w_pub=1000,  # High pub rate bonus
        w_hist=0,
        lambda_cap=0,
        lambda_fair=0,
        seed=42,
        verbose=False
    )

    selected = result['selected_assignments']
    if selected:
        selected_vin = selected[0]['vin']
        pub_rate = triples[triples['vin'] == selected_vin]['pub_rate_24m'].iloc[0]
        print(f"With W_PUB=1000: Selected VIN={selected_vin}, pub_rate_24m={pub_rate}")

        shaping = result.get('shaping_breakdown', {})
        if shaping:
            counts = shaping.get('counts', {})
            print(f"Avg pub rate: {counts.get('avg_pub_rate', 0):.3f}")

    if selected and pub_rate == 0.8:
        print("✅ PASS: Higher W_PUB correctly prefers higher publication rate")
        return True
    else:
        print("❌ FAIL: Expected pub_rate=0.8 selection with high W_PUB")
        return False


def test_s6c_no_feasibility_change():
    """S6-C: Count of feasible triples identical before/after shaping."""
    print("\n" + "="*60)
    print("S6-C: NO FEASIBILITY CHANGE")
    print("="*60)

    # Create test triples
    triples = pd.DataFrame([
        {'vin': f'V{i}', 'person_id': f'P{i//2}', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Camry', 'office': 'LA',
         'rank': 'A', 'rank_weight': 900 + i*10,
         'geo_office_match': i % 2,
         'pub_rate_24m': i * 0.1,
         'history_published': i % 3 == 0}
        for i in range(10)
    ])

    count_before = len(triples)
    print(f"Triples before shaping: {count_before}")

    # Apply shaping
    shaped_df = apply_objective_shaping(
        triples,
        w_rank=2.0,
        w_geo=200,
        w_pub=300,
        w_hist=100,
        verbose=False
    )

    count_after = len(shaped_df)
    print(f"Triples after shaping: {count_after}")

    # Check that we have shaped scores
    has_shaped = 'score_shaped' in shaped_df.columns
    print(f"Has score_shaped column: {has_shaped}")

    if has_shaped:
        score_range = (shaped_df['score_shaped'].min(), shaped_df['score_shaped'].max())
        print(f"Score range: {score_range[0]:.1f} - {score_range[1]:.1f}")

    if count_before == count_after and has_shaped:
        print("✅ PASS: Shaping does not change feasibility (same count)")
        return True
    else:
        print("❌ FAIL: Triple count changed or shaping failed")
        return False


def test_s6d_determinism():
    """S6-D: Same seed/weights => identical selection."""
    print("\n" + "="*60)
    print("S6-D: DETERMINISM")
    print("="*60)

    # Create test scenario
    triples = pd.DataFrame([
        {'vin': f'V{i}', 'person_id': f'P{i%3}', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Camry', 'office': 'LA',
         'rank': 'A', 'rank_weight': 950 + (i*7)%50,
         'geo_office_match': i % 2,
         'pub_rate_24m': (i * 13) % 100 / 100.0,
         'history_published': i % 4 == 0}
        for i in range(20)
    ])

    ops_capacity = pd.DataFrame([
        {'office': 'LA', 'date': '2025-09-22', 'slots': 5}
    ])

    approved = pd.DataFrame([
        {'person_id': f'P{i}', 'make': 'Toyota', 'rank': 'A'}
        for i in range(3)
    ])

    # Fixed weights for testing
    test_weights = {
        'w_rank': 1.5,
        'w_geo': 150,
        'w_pub': 200,
        'w_hist': 75
    }

    # Run twice with same seed and weights
    result1 = solve_with_all_constraints(
        triples_df=triples,
        ops_capacity_df=ops_capacity,
        approved_makes_df=approved,
        loan_history_df=pd.DataFrame(),
        rules_df=pd.DataFrame(),
        budgets_df=pd.DataFrame(),
        week_start='2025-09-22',
        office='LA',
        **test_weights,
        lambda_cap=0,
        lambda_fair=0,
        seed=12345,  # Fixed seed
        verbose=False
    )

    result2 = solve_with_all_constraints(
        triples_df=triples,
        ops_capacity_df=ops_capacity,
        approved_makes_df=approved,
        loan_history_df=pd.DataFrame(),
        rules_df=pd.DataFrame(),
        budgets_df=pd.DataFrame(),
        week_start='2025-09-22',
        office='LA',
        **test_weights,
        lambda_cap=0,
        lambda_fair=0,
        seed=12345,  # Same seed
        verbose=False
    )

    # Compare selections
    vins1 = sorted([a['vin'] for a in result1['selected_assignments']])
    vins2 = sorted([a['vin'] for a in result2['selected_assignments']])

    print(f"Run 1: Selected {len(vins1)} assignments")
    print(f"Run 2: Selected {len(vins2)} assignments")
    print(f"VINs match: {vins1 == vins2}")

    # Also check with different seed
    result3 = solve_with_all_constraints(
        triples_df=triples,
        ops_capacity_df=ops_capacity,
        approved_makes_df=approved,
        loan_history_df=pd.DataFrame(),
        rules_df=pd.DataFrame(),
        budgets_df=pd.DataFrame(),
        week_start='2025-09-22',
        office='LA',
        **test_weights,
        lambda_cap=0,
        lambda_fair=0,
        seed=99999,  # Different seed
        verbose=False
    )

    vins3 = sorted([a['vin'] for a in result3['selected_assignments']])
    print(f"Run 3 (diff seed): Selected {len(vins3)} assignments")

    if vins1 == vins2 and len(vins1) > 0:
        print("✅ PASS: Same seed/weights produce identical results")
        return True
    else:
        print("❌ FAIL: Results not deterministic with same seed/weights")
        return False


def main():
    """Run all Phase 7.8 mini-tests."""
    print("="*80)
    print("PHASE 7.8 MINI-TESTS (S6-A through S6-D)")
    print("Objective shaping minimal tests")
    print("="*80)

    results = []

    # Run each test
    results.append(("S6-A - Geo sensitivity", test_s6a_geo_sensitivity()))
    results.append(("S6-B - Pub sensitivity", test_s6b_pub_sensitivity()))
    results.append(("S6-C - No feasibility change", test_s6c_no_feasibility_change()))
    results.append(("S6-D - Determinism", test_s6d_determinism()))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{name}: {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL OBJECTIVE SHAPING MINI-TESTS PASSED!")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)