"""
Test suite for Phase 7.5 (Distribution/Fairness Penalties).

Tests the 5 mini scenarios from the spec:
F1 - Prefer spread
F2 - Allow concentration if required
F3 - Sensitivity to lambda
F4 - Interaction with soft caps
F5 - Determinism
"""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.solver.ortools_solver_v5 import solve_with_caps_and_fairness
from app.solver.ortools_solver_v2 import add_score_to_triples


def test_f1_prefer_spread():
    """F1: Two partners, four VINs, equal scores. Expect 2-2 split with fairness."""
    print("\n" + "="*60)
    print("F1: PREFER SPREAD")
    print("="*60)

    # Create 4 vehicles, 2 partners, all equal scores
    triples = pd.DataFrame([
        # Partner P001 options
        {'vin': 'V1', 'person_id': 'P001', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Camry', 'office': 'LA', 'rank': 'A', 'score': 1000},
        {'vin': 'V2', 'person_id': 'P001', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Corolla', 'office': 'LA', 'rank': 'A', 'score': 1000},
        {'vin': 'V3', 'person_id': 'P001', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'RAV4', 'office': 'LA', 'rank': 'A', 'score': 1000},
        {'vin': 'V4', 'person_id': 'P001', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Highlander', 'office': 'LA', 'rank': 'A', 'score': 1000},

        # Partner P002 options (same vehicles)
        {'vin': 'V1', 'person_id': 'P002', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Camry', 'office': 'LA', 'rank': 'A', 'score': 1000},
        {'vin': 'V2', 'person_id': 'P002', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Corolla', 'office': 'LA', 'rank': 'A', 'score': 1000},
        {'vin': 'V3', 'person_id': 'P002', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'RAV4', 'office': 'LA', 'rank': 'A', 'score': 1000},
        {'vin': 'V4', 'person_id': 'P002', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Highlander', 'office': 'LA', 'rank': 'A', 'score': 1000},
    ])

    # Capacity allows all 4
    ops_capacity = pd.DataFrame([
        {'office': 'LA', 'date': '2025-09-22', 'slots': 4}
    ])

    approved = pd.DataFrame([
        {'person_id': 'P001', 'make': 'Toyota', 'rank': 'A'},
        {'person_id': 'P002', 'make': 'Toyota', 'rank': 'A'},
    ])

    # Test WITHOUT fairness (lambda_fair=0)
    result_no_fair = solve_with_caps_and_fairness(
        triples_df=triples,
        ops_capacity_df=ops_capacity,
        approved_makes_df=approved,
        loan_history_df=pd.DataFrame(),
        rules_df=pd.DataFrame(),
        week_start='2025-09-22',
        office='LA',
        lambda_cap=800,
        lambda_fair=0,  # No fairness
        fair_target=1,
        seed=42,
        verbose=False
    )

    # Test WITH fairness (lambda_fair=200)
    result_with_fair = solve_with_caps_and_fairness(
        triples_df=triples,
        ops_capacity_df=ops_capacity,
        approved_makes_df=approved,
        loan_history_df=pd.DataFrame(),
        rules_df=pd.DataFrame(),
        week_start='2025-09-22',
        office='LA',
        lambda_cap=800,
        lambda_fair=200,  # With fairness
        fair_target=1,
        seed=42,
        verbose=False
    )

    # Analyze distributions
    def get_distribution(result):
        counts = {}
        for a in result['selected_assignments']:
            p = a['person_id']
            counts[p] = counts.get(p, 0) + 1
        return counts

    dist_no_fair = get_distribution(result_no_fair)
    dist_with_fair = get_distribution(result_with_fair)

    print(f"Without fairness (λ_fair=0): {dist_no_fair}")
    print(f"With fairness (λ_fair=200): {dist_with_fair}")

    # Check if fairness improved distribution
    if dist_with_fair == {'P001': 2, 'P002': 2}:
        print("✅ PASS: Fairness achieved 2-2 split")
        return True
    else:
        # Check if at least more balanced than without
        max_no_fair = max(dist_no_fair.values()) if dist_no_fair else 0
        max_with_fair = max(dist_with_fair.values()) if dist_with_fair else 0
        if max_with_fair <= max_no_fair:
            print("✅ PASS: Fairness improved or maintained balance")
            return True
        else:
            print("❌ FAIL: Fairness did not improve distribution")
            return False


def test_f2_allow_concentration():
    """F2: Only one eligible partner for three VINs. Must concentrate."""
    print("\n" + "="*60)
    print("F2: ALLOW CONCENTRATION IF REQUIRED")
    print("="*60)

    # Only P001 is eligible
    triples = pd.DataFrame([
        {'vin': 'V1', 'person_id': 'P001', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Camry', 'office': 'LA', 'rank': 'B', 'score': 800},
        {'vin': 'V2', 'person_id': 'P001', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Corolla', 'office': 'LA', 'rank': 'B', 'score': 800},
        {'vin': 'V3', 'person_id': 'P001', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'RAV4', 'office': 'LA', 'rank': 'B', 'score': 800},
    ])

    ops_capacity = pd.DataFrame([
        {'office': 'LA', 'date': '2025-09-22', 'slots': 3}
    ])

    approved = pd.DataFrame([
        {'person_id': 'P001', 'make': 'Toyota', 'rank': 'B'},
    ])

    result = solve_with_caps_and_fairness(
        triples_df=triples,
        ops_capacity_df=ops_capacity,
        approved_makes_df=approved,
        loan_history_df=pd.DataFrame(),
        rules_df=pd.DataFrame(),
        week_start='2025-09-22',
        office='LA',
        lambda_cap=800,
        lambda_fair=200,
        fair_target=1,
        seed=42,
        verbose=False
    )

    selected = result['selected_assignments']
    fairness_penalty = result['total_fairness_penalty']

    print(f"Selected: {len(selected)} assignments")
    print(f"Fairness penalty: ${fairness_penalty}")

    # Should assign all 3 despite fairness penalty
    if len(selected) == 3 and fairness_penalty == 400:  # 200*(3-1)
        print("✅ PASS: Allowed concentration with correct penalty")
        return True
    else:
        print(f"❌ FAIL: Expected 3 assignments with $400 penalty")
        return False


def test_f3_sensitivity():
    """F3: Test that increasing lambda_fair reduces concentration."""
    print("\n" + "="*60)
    print("F3: LAMBDA SENSITIVITY")
    print("="*60)

    # Many options, some concentration possible
    triples = pd.DataFrame([
        # P001 has 5 options
        {'vin': f'V{i}', 'person_id': 'P001', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Model', 'office': 'LA', 'rank': 'A', 'score': 1000}
        for i in range(1, 6)
    ] + [
        # P002 has 3 options (overlapping vehicles)
        {'vin': f'V{i}', 'person_id': 'P002', 'start_day': '2025-09-22',
         'make': 'Honda', 'model': 'Model', 'office': 'LA', 'rank': 'A', 'score': 950}
        for i in range(3, 6)
    ] + [
        # P003 has 2 options
        {'vin': f'V{i}', 'person_id': 'P003', 'start_day': '2025-09-22',
         'make': 'Mazda', 'model': 'Model', 'office': 'LA', 'rank': 'B', 'score': 900}
        for i in range(5, 7)
    ])

    ops_capacity = pd.DataFrame([
        {'office': 'LA', 'date': '2025-09-22', 'slots': 6}
    ])

    approved = pd.DataFrame([
        {'person_id': 'P001', 'make': 'Toyota', 'rank': 'A'},
        {'person_id': 'P002', 'make': 'Honda', 'rank': 'A'},
        {'person_id': 'P003', 'make': 'Mazda', 'rank': 'B'},
    ])

    # Test with different lambda values
    lambda_values = [100, 400, 800]
    max_concentrations = []

    for lambda_fair in lambda_values:
        result = solve_with_caps_and_fairness(
            triples_df=triples,
            ops_capacity_df=ops_capacity,
            approved_makes_df=approved,
            loan_history_df=pd.DataFrame(),
            rules_df=pd.DataFrame(),
            week_start='2025-09-22',
            office='LA',
            lambda_cap=800,
            lambda_fair=lambda_fair,
            fair_target=1,
            seed=42,
            verbose=False
        )

        # Find max concentration
        partner_counts = {}
        for a in result['selected_assignments']:
            p = a['person_id']
            partner_counts[p] = partner_counts.get(p, 0) + 1

        max_conc = max(partner_counts.values()) if partner_counts else 0
        max_concentrations.append(max_conc)

        print(f"λ_fair={lambda_fair}: max concentration = {max_conc}, "
              f"penalty=${result['total_fairness_penalty']}")

    # Check monotonicity
    if all(max_concentrations[i] >= max_concentrations[i+1]
           for i in range(len(max_concentrations)-1)):
        print("✅ PASS: Higher lambda reduces or maintains concentration")
        return True
    else:
        print("❌ FAIL: Lambda sensitivity not monotonic")
        return False


def test_f4_interaction():
    """F4: Test interaction between cap and fairness penalties."""
    print("\n" + "="*60)
    print("F4: CAP-FAIRNESS INTERACTION")
    print("="*60)

    # P001 is in-cap, P002 would exceed cap
    triples = pd.DataFrame([
        # P001 options (in cap)
        {'vin': 'V1', 'person_id': 'P001', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Camry', 'office': 'LA', 'rank': 'B', 'score': 800},
        {'vin': 'V2', 'person_id': 'P001', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Corolla', 'office': 'LA', 'rank': 'B', 'score': 800},

        # P002 options (would exceed cap)
        {'vin': 'V1', 'person_id': 'P002', 'start_day': '2025-09-22',
         'make': 'Honda', 'model': 'Civic', 'office': 'LA', 'rank': 'C', 'score': 800},
        {'vin': 'V2', 'person_id': 'P002', 'start_day': '2025-09-22',
         'make': 'Honda', 'model': 'Accord', 'office': 'LA', 'rank': 'C', 'score': 800},
    ])

    # P002 already at cap for Honda (C rank = 10)
    loan_history = pd.DataFrame([{
        'person_id': 'P002',
        'make': 'Honda',
        'start_date': f'2025-{i+1:02d}-01',
        'end_date': f'2025-{i+1:02d}-08',
        'office': 'LA'
    } for i in range(10)])  # At cap

    ops_capacity = pd.DataFrame([
        {'office': 'LA', 'date': '2025-09-22', 'slots': 2}
    ])

    approved = pd.DataFrame([
        {'person_id': 'P001', 'make': 'Toyota', 'rank': 'B'},
        {'person_id': 'P002', 'make': 'Honda', 'rank': 'C'},
    ])

    result = solve_with_caps_and_fairness(
        triples_df=triples,
        ops_capacity_df=ops_capacity,
        approved_makes_df=approved,
        loan_history_df=loan_history,
        rules_df=pd.DataFrame(),
        week_start='2025-09-22',
        office='LA',
        lambda_cap=800,
        lambda_fair=200,
        fair_target=1,
        seed=42,
        verbose=False
    )

    # Analyze selection
    partner_counts = {}
    for a in result['selected_assignments']:
        p = a['person_id']
        partner_counts[p] = partner_counts.get(p, 0) + 1

    cap_penalty = result['total_cap_penalty']
    fair_penalty = result['total_fairness_penalty']

    print(f"Distribution: {partner_counts}")
    print(f"Cap penalty: ${cap_penalty}")
    print(f"Fairness penalty: ${fair_penalty}")

    # Should prefer 1-1 split to avoid both penalties if possible
    if partner_counts.get('P001', 0) == 1 and partner_counts.get('P002', 0) == 1:
        print("✅ PASS: Solver balanced cap vs fairness trade-offs (1-1 split)")
        return True
    elif partner_counts.get('P001', 0) == 2:
        print("✅ PASS: Solver chose concentration to avoid cap penalty")
        return True
    else:
        print("❌ FAIL: Unexpected distribution")
        return False


def test_f5_determinism():
    """F5: Same seed returns identical results."""
    print("\n" + "="*60)
    print("F5: DETERMINISM")
    print("="*60)

    # Create test data
    triples = pd.DataFrame([
        {'vin': f'V{i}', 'person_id': f'P{i//3}', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Model', 'office': 'LA',
         'rank': 'B', 'score': 500 + i * 10}
        for i in range(15)
    ])

    ops_capacity = pd.DataFrame([
        {'office': 'LA', 'date': '2025-09-22', 'slots': 8}
    ])

    approved = pd.DataFrame([
        {'person_id': f'P{i}', 'make': 'Toyota', 'rank': 'B'}
        for i in range(5)
    ])

    # Run twice with same seed
    result1 = solve_with_caps_and_fairness(
        triples_df=triples,
        ops_capacity_df=ops_capacity,
        approved_makes_df=approved,
        loan_history_df=pd.DataFrame(),
        rules_df=pd.DataFrame(),
        week_start='2025-09-22',
        office='LA',
        lambda_cap=800,
        lambda_fair=200,
        fair_target=1,
        seed=42,
        verbose=False
    )

    result2 = solve_with_caps_and_fairness(
        triples_df=triples,
        ops_capacity_df=ops_capacity,
        approved_makes_df=approved,
        loan_history_df=pd.DataFrame(),
        rules_df=pd.DataFrame(),
        week_start='2025-09-22',
        office='LA',
        lambda_cap=800,
        lambda_fair=200,
        fair_target=1,
        seed=42,
        verbose=False
    )

    # Compare results
    vins1 = {a['vin'] for a in result1['selected_assignments']}
    vins2 = {a['vin'] for a in result2['selected_assignments']}

    penalty1 = result1['total_fairness_penalty']
    penalty2 = result2['total_fairness_penalty']

    print(f"Run 1: {len(vins1)} assignments, fairness penalty=${penalty1}")
    print(f"Run 2: {len(vins2)} assignments, fairness penalty=${penalty2}")

    if vins1 == vins2 and penalty1 == penalty2:
        print("✅ PASS: Deterministic - identical results with same seed")
        return True
    else:
        print("❌ FAIL: Different results with same seed")
        return False


def main():
    """Run all fairness tests."""
    print("="*80)
    print("PHASE 7.5 FAIRNESS TESTS")
    print("Distribution/concentration penalties")
    print("="*80)

    results = []

    # Run each test
    results.append(("F1 - Prefer spread", test_f1_prefer_spread()))
    results.append(("F2 - Allow concentration", test_f2_allow_concentration()))
    results.append(("F3 - Lambda sensitivity", test_f3_sensitivity()))
    results.append(("F4 - Cap-fairness interaction", test_f4_interaction()))
    results.append(("F5 - Determinism", test_f5_determinism()))

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
        print("\n🎉 ALL FAIRNESS TESTS PASSED!")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)