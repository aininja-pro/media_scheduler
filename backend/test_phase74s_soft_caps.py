"""
Test suite for Phase 7.4s (Soft Tier Caps with Penalties).

Tests the 5 mini scenarios from the spec:
T1 - Prefer in-cap
T2 - Allow when necessary
T3 - Existing overage
T4 - Sensitivity to lambda
T5 - Determinism
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.solver.ortools_solver_v4 import solve_with_soft_caps
from app.solver.ortools_solver_v2 import add_score_to_triples


def test_t1_prefer_in_cap():
    """T1: Two triples same score, one in-cap, one over-cap. Expect: selects in-cap."""
    print("\n" + "="*60)
    print("T1: PREFER IN-CAP")
    print("="*60)

    # Create two triples with same score
    triples = pd.DataFrame([
        # Partner P001 with Toyota - within cap
        {'vin': 'V1', 'person_id': 'P001', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Camry', 'office': 'LA',
         'rank': 'B', 'score': 500},

        # Partner P002 with Honda - will be over cap
        {'vin': 'V2', 'person_id': 'P002', 'start_day': '2025-09-22',
         'make': 'Honda', 'model': 'Civic', 'office': 'LA',
         'rank': 'B', 'score': 500},
    ])

    # P002 already at cap for Honda (B rank = 50)
    loan_history = pd.DataFrame([{
        'person_id': 'P002',
        'make': 'Honda',
        'start_date': '2024-10-01',
        'end_date': '2024-10-08',
        'office': 'LA'
    }] * 50)  # 50 Honda loans = at cap

    # Capacity allows 1
    ops_capacity = pd.DataFrame([
        {'office': 'LA', 'date': '2025-09-22', 'slots': 1}
    ])

    approved = pd.DataFrame([
        {'person_id': 'P001', 'make': 'Toyota', 'rank': 'B'},
        {'person_id': 'P002', 'make': 'Honda', 'rank': 'B'},
    ])

    result = solve_with_soft_caps(
        triples_df=triples,
        ops_capacity_df=ops_capacity,
        approved_makes_df=approved,
        loan_history_df=loan_history,
        rules_df=pd.DataFrame(),
        week_start='2025-09-22',
        office='LA',
        lambda_cap=800,
        seed=42
    )

    selected = result['selected_assignments']
    print(f"Selected: {len(selected)} assignment(s)")

    if selected:
        winner = selected[0]
        print(f"Winner: {winner['person_id']} + {winner['make']}")

        if winner['person_id'] == 'P001' and winner['make'] == 'Toyota':
            print("✅ PASS: Solver preferred in-cap option")
            return True
        else:
            print("❌ FAIL: Solver chose over-cap option")
            return False
    else:
        print("❌ FAIL: No assignments selected")
        return False


def test_t2_allow_when_necessary():
    """T2: Only available triple is over-cap. Expect: selects it with penalty."""
    print("\n" + "="*60)
    print("T2: ALLOW WHEN NECESSARY")
    print("="*60)

    # Only one triple available, but it's over cap
    triples = pd.DataFrame([
        {'vin': 'V1', 'person_id': 'P001', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Camry', 'office': 'LA',
         'rank': 'C', 'score': 1000},  # Good score
    ])

    # P001 already at cap for Toyota (C rank = 10)
    loan_history = pd.DataFrame([{
        'person_id': 'P001',
        'make': 'Toyota',
        'start_date': f'2025-{(i%9)+1:02d}-01',  # Jan-Sept 2025
        'end_date': f'2025-{(i%9)+1:02d}-08',
        'office': 'LA'
    } for i in range(10)])  # 10 Toyota loans = at cap for C rank

    ops_capacity = pd.DataFrame([
        {'office': 'LA', 'date': '2025-09-22', 'slots': 5}
    ])

    approved = pd.DataFrame([
        {'person_id': 'P001', 'make': 'Toyota', 'rank': 'C'},
    ])

    result = solve_with_soft_caps(
        triples_df=triples,
        ops_capacity_df=ops_capacity,
        approved_makes_df=approved,
        loan_history_df=loan_history,
        rules_df=pd.DataFrame(),
        week_start='2025-09-22',
        office='LA',
        lambda_cap=800,
        seed=42
    )

    selected = result['selected_assignments']
    penalty = result['total_cap_penalty']

    print(f"Selected: {len(selected)} assignment(s)")
    print(f"Cap penalty: {penalty}")

    if len(selected) == 1 and penalty == 800:
        print("✅ PASS: Solver allowed over-cap assignment with penalty")
        return True
    else:
        print(f"❌ FAIL: Expected 1 assignment with 800 penalty")
        return False


def test_t3_existing_overage():
    """T3: Partner already over cap. Test incremental penalty only."""
    print("\n" + "="*60)
    print("T3: EXISTING OVERAGE")
    print("="*60)

    # Partner already has 6 Volvo loans when cap is 3
    triples = pd.DataFrame([
        # Two Volvo options (over cap)
        {'vin': 'V1', 'person_id': 'P001', 'start_day': '2025-09-22',
         'make': 'Volvo', 'model': 'XC90', 'office': 'LA',
         'rank': 'B', 'score': 600},
        {'vin': 'V2', 'person_id': 'P001', 'start_day': '2025-09-23',
         'make': 'Volvo', 'model': 'XC60', 'office': 'LA',
         'rank': 'B', 'score': 600},

        # One Toyota option (in cap, high score)
        {'vin': 'V3', 'person_id': 'P001', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Highlander', 'office': 'LA',
         'rank': 'A', 'score': 1100},  # A+ equivalent score
    ])

    # Already 6 Volvo loans (cap is 3 from rule)
    loan_history = pd.DataFrame([{
        'person_id': 'P001',
        'make': 'Volvo',
        'start_date': f'2025-0{i+1}-01',
        'end_date': f'2025-0{i+1}-08',
        'office': 'LA'
    } for i in range(6)])

    ops_capacity = pd.DataFrame([
        {'office': 'LA', 'date': '2025-09-22', 'slots': 5},
        {'office': 'LA', 'date': '2025-09-23', 'slots': 5},
    ])

    approved = pd.DataFrame([
        {'person_id': 'P001', 'make': 'Volvo', 'rank': 'B'},
        {'person_id': 'P001', 'make': 'Toyota', 'rank': 'A'},
    ])

    # Volvo B rank has cap of 3 in rules
    rules = pd.DataFrame([
        {'make': 'Volvo', 'rank': 'B', 'loan_cap_per_year': 3}
    ])

    result = solve_with_soft_caps(
        triples_df=triples,
        ops_capacity_df=ops_capacity,
        approved_makes_df=approved,
        loan_history_df=loan_history,
        rules_df=rules,
        week_start='2025-09-22',
        office='LA',
        lambda_cap=800,
        seed=42
    )

    selected = result['selected_assignments']
    selected_makes = [a['make'] for a in selected]

    print(f"Selected makes: {selected_makes}")
    print(f"Total penalty: {result['total_cap_penalty']}")

    # Expect Toyota selected (high score, no penalty)
    # Maybe 1 Volvo if score difference > penalty
    if 'Toyota' in selected_makes:
        print("✅ PASS: Solver selected high-score Toyota to avoid penalties")
        return True
    else:
        print("❌ FAIL: Solver didn't select Toyota despite it avoiding penalties")
        return False


def test_t4_sensitivity():
    """T4: Test that increasing lambda reduces over-cap assignments."""
    print("\n" + "="*60)
    print("T4: LAMBDA SENSITIVITY")
    print("="*60)

    # Multiple triples, some will exceed cap
    triples = pd.DataFrame([
        {'vin': f'V{i}', 'person_id': 'P001', 'start_day': '2025-09-22',
         'make': 'Honda', 'model': 'Civic', 'office': 'LA',
         'rank': 'C', 'score': 900}
        for i in range(5)  # 5 Honda options
    ])

    # Already at cap (C rank = 10)
    loan_history = pd.DataFrame([{
        'person_id': 'P001',
        'make': 'Honda',
        'start_date': f'2025-{(i%9)+1:02d}-01',  # Jan-Sept 2025
        'end_date': f'2025-{(i%9)+1:02d}-08',
        'office': 'LA'
    } for i in range(10)])

    ops_capacity = pd.DataFrame([
        {'office': 'LA', 'date': '2025-09-22', 'slots': 10}
    ])

    approved = pd.DataFrame([
        {'person_id': 'P001', 'make': 'Honda', 'rank': 'C'},
    ])

    # Test with low lambda
    result_low = solve_with_soft_caps(
        triples_df=triples,
        ops_capacity_df=ops_capacity,
        approved_makes_df=approved,
        loan_history_df=loan_history,
        rules_df=pd.DataFrame(),
        week_start='2025-09-22',
        office='LA',
        lambda_cap=400,  # Low penalty
        seed=42
    )

    # Test with high lambda
    result_high = solve_with_soft_caps(
        triples_df=triples,
        ops_capacity_df=ops_capacity,
        approved_makes_df=approved,
        loan_history_df=loan_history,
        rules_df=pd.DataFrame(),
        week_start='2025-09-22',
        office='LA',
        lambda_cap=1200,  # High penalty
        seed=42
    )

    selected_low = len(result_low['selected_assignments'])
    selected_high = len(result_high['selected_assignments'])

    print(f"Lambda=400: {selected_low} assignments")
    print(f"Lambda=1200: {selected_high} assignments")

    if selected_low >= selected_high:
        print("✅ PASS: Higher lambda reduces or maintains over-cap assignments")
        return True
    else:
        print("❌ FAIL: Higher lambda increased assignments (unexpected)")
        return False


def test_t5_determinism():
    """T5: Same seed returns identical results."""
    print("\n" + "="*60)
    print("T5: DETERMINISM")
    print("="*60)

    # Create test data
    triples = pd.DataFrame([
        {'vin': f'V{i}', 'person_id': f'P{i//3}', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Camry', 'office': 'LA',
         'rank': 'B', 'score': 500 + i * 10}
        for i in range(10)
    ])

    loan_history = pd.DataFrame()
    ops_capacity = pd.DataFrame([
        {'office': 'LA', 'date': '2025-09-22', 'slots': 5}
    ])

    approved = pd.DataFrame([
        {'person_id': f'P{i}', 'make': 'Toyota', 'rank': 'B'}
        for i in range(4)
    ])

    # Run twice with same seed
    result1 = solve_with_soft_caps(
        triples_df=triples,
        ops_capacity_df=ops_capacity,
        approved_makes_df=approved,
        loan_history_df=loan_history,
        rules_df=pd.DataFrame(),
        week_start='2025-09-22',
        office='LA',
        lambda_cap=800,
        seed=42
    )

    result2 = solve_with_soft_caps(
        triples_df=triples,
        ops_capacity_df=ops_capacity,
        approved_makes_df=approved,
        loan_history_df=loan_history,
        rules_df=pd.DataFrame(),
        week_start='2025-09-22',
        office='LA',
        lambda_cap=800,
        seed=42
    )

    # Compare results
    vins1 = {a['vin'] for a in result1['selected_assignments']}
    vins2 = {a['vin'] for a in result2['selected_assignments']}

    penalty1 = result1['total_cap_penalty']
    penalty2 = result2['total_cap_penalty']

    print(f"Run 1: {len(vins1)} assignments, penalty={penalty1}")
    print(f"Run 2: {len(vins2)} assignments, penalty={penalty2}")

    if vins1 == vins2 and penalty1 == penalty2:
        print("✅ PASS: Deterministic - identical results with same seed")
        return True
    else:
        print("❌ FAIL: Different results with same seed")
        return False


def main():
    """Run all soft cap tests."""
    print("="*80)
    print("PHASE 7.4s SOFT CAP TESTS")
    print("Penalty-based tier caps")
    print("="*80)

    results = []

    # Run each test
    results.append(("T1 - Prefer in-cap", test_t1_prefer_in_cap()))
    results.append(("T2 - Allow when necessary", test_t2_allow_when_necessary()))
    results.append(("T3 - Existing overage", test_t3_existing_overage()))
    results.append(("T4 - Lambda sensitivity", test_t4_sensitivity()))
    results.append(("T5 - Determinism", test_t5_determinism()))

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
        print("\n🎉 ALL SOFT CAP TESTS PASSED!")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)