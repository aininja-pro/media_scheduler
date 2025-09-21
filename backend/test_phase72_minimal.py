"""
Minimal test suite for Phase 7.2: Core OR-Tools solver.

Tests VIN uniqueness, capacity constraints, and determinism.
"""

import pandas as pd
from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.solver.ortools_solver_v2 import solve_core_assignment, add_score_to_triples


def create_minimal_triples():
    """Create minimal test data with pre-computed scores."""

    week_start = '2025-09-22'  # Monday

    # Create some triples with scores
    triples = pd.DataFrame([
        # VIN001 options (high scores)
        {'vin': 'VIN001', 'person_id': 'P001', 'start_day': '2025-09-22', 'office': 'TestOffice',
         'make': 'Toyota', 'model': 'Camry', 'score': 1000, 'rank': 'A', 'geo_office_match': True},
        {'vin': 'VIN001', 'person_id': 'P002', 'start_day': '2025-09-22', 'office': 'TestOffice',
         'make': 'Toyota', 'model': 'Camry', 'score': 900, 'rank': 'B', 'geo_office_match': True},

        # VIN002 options (medium scores)
        {'vin': 'VIN002', 'person_id': 'P001', 'start_day': '2025-09-23', 'office': 'TestOffice',
         'make': 'Honda', 'model': 'Accord', 'score': 600, 'rank': 'B', 'geo_office_match': False},
        {'vin': 'VIN002', 'person_id': 'P003', 'start_day': '2025-09-24', 'office': 'TestOffice',
         'make': 'Honda', 'model': 'Accord', 'score': 500, 'rank': 'C', 'geo_office_match': True},

        # VIN003 options (Wed start - for capacity testing)
        {'vin': 'VIN003', 'person_id': 'P004', 'start_day': '2025-09-24', 'office': 'TestOffice',
         'make': 'Nissan', 'model': 'Altima', 'score': 700, 'rank': 'B', 'geo_office_match': True},

        # VIN004 (Friday start - for spillover testing)
        {'vin': 'VIN004', 'person_id': 'P005', 'start_day': '2025-09-26', 'office': 'TestOffice',
         'make': 'Ford', 'model': 'Fusion', 'score': 800, 'rank': 'A', 'geo_office_match': False},
    ])

    return triples


def test_capacity_tightness():
    """Test: Reduce Wed slots; assignments covering Wed decrease."""
    print("\n" + "="*60)
    print("TEST 1: CAPACITY TIGHTNESS")
    print("="*60)

    triples = create_minimal_triples()
    week_start = '2025-09-22'

    # Normal capacity (all days have slots)
    normal_capacity = pd.DataFrame([
        {'office': 'TestOffice', 'date': '2025-09-22', 'slots': 10},  # Mon
        {'office': 'TestOffice', 'date': '2025-09-23', 'slots': 10},  # Tue
        {'office': 'TestOffice', 'date': '2025-09-24', 'slots': 10},  # Wed
        {'office': 'TestOffice', 'date': '2025-09-25', 'slots': 10},  # Thu
        {'office': 'TestOffice', 'date': '2025-09-26', 'slots': 10},  # Fri
        {'office': 'TestOffice', 'date': '2025-09-27', 'slots': 10},  # Sat
        {'office': 'TestOffice', 'date': '2025-09-28', 'slots': 10},  # Sun
        # Add next week for spillover
        {'office': 'TestOffice', 'date': '2025-09-29', 'slots': 10},  # Mon
        {'office': 'TestOffice', 'date': '2025-09-30', 'slots': 10},  # Tue
        {'office': 'TestOffice', 'date': '2025-10-01', 'slots': 10},  # Wed
        {'office': 'TestOffice', 'date': '2025-10-02', 'slots': 10},  # Thu
    ])

    result_normal = solve_core_assignment(
        triples_df=triples,
        ops_capacity_df=normal_capacity,
        week_start=week_start,
        office='TestOffice',
        solver_time_limit_s=5,
        seed=42
    )

    # Tight Wednesday capacity (only 1 slot)
    tight_capacity = normal_capacity.copy()
    tight_capacity.loc[tight_capacity['date'] == '2025-09-24', 'slots'] = 1  # Wed

    result_tight = solve_core_assignment(
        triples_df=triples,
        ops_capacity_df=tight_capacity,
        week_start=week_start,
        office='TestOffice',
        solver_time_limit_s=5,
        seed=42
    )

    # Check Wednesday usage
    wed_usage_normal = next(
        (d['used'] for d in result_normal['daily_usage'] if d['date'] == '2025-09-24'), 0
    )
    wed_usage_tight = next(
        (d['used'] for d in result_tight['daily_usage'] if d['date'] == '2025-09-24'), 0
    )

    print(f"Wednesday usage with normal capacity (10): {wed_usage_normal}")
    print(f"Wednesday usage with tight capacity (1): {wed_usage_tight}")
    print(f"Total selected (normal): {len(result_normal['selected_assignments'])}")
    print(f"Total selected (tight): {len(result_tight['selected_assignments'])}")

    if wed_usage_tight <= 1 and wed_usage_tight < wed_usage_normal:
        print("✅ PASS: Capacity constraint respected, fewer assignments when tight")
        return True
    else:
        print("❌ FAIL: Capacity constraint not working correctly")
        return False


def test_vin_uniqueness():
    """Test: Duplicate high-score options for same VIN - choose at most one."""
    print("\n" + "="*60)
    print("TEST 2: VIN UNIQUENESS")
    print("="*60)

    # Create triples with multiple high-score options for same VIN
    triples = pd.DataFrame([
        # VIN001 has 3 high-score options
        {'vin': 'VIN001', 'person_id': 'P001', 'start_day': '2025-09-22', 'office': 'TestOffice',
         'make': 'Toyota', 'model': 'Camry', 'score': 2000, 'rank': 'A+', 'geo_office_match': True},
        {'vin': 'VIN001', 'person_id': 'P002', 'start_day': '2025-09-23', 'office': 'TestOffice',
         'make': 'Toyota', 'model': 'Camry', 'score': 1900, 'rank': 'A+', 'geo_office_match': True},
        {'vin': 'VIN001', 'person_id': 'P003', 'start_day': '2025-09-24', 'office': 'TestOffice',
         'make': 'Toyota', 'model': 'Camry', 'score': 1800, 'rank': 'A', 'geo_office_match': True},

        # VIN002 has 2 options
        {'vin': 'VIN002', 'person_id': 'P004', 'start_day': '2025-09-22', 'office': 'TestOffice',
         'make': 'Honda', 'model': 'Accord', 'score': 1000, 'rank': 'B', 'geo_office_match': True},
        {'vin': 'VIN002', 'person_id': 'P005', 'start_day': '2025-09-25', 'office': 'TestOffice',
         'make': 'Honda', 'model': 'Accord', 'score': 900, 'rank': 'B', 'geo_office_match': False},
    ])

    # Create capacity for 2 weeks (properly handling month boundaries)
    dates = []
    start = pd.to_datetime('2025-09-22')
    for i in range(14):
        dates.append((start + timedelta(days=i)).strftime('%Y-%m-%d'))

    capacity = pd.DataFrame([
        {'office': 'TestOffice', 'date': date, 'slots': 10}
        for date in dates
    ])

    result = solve_core_assignment(
        triples_df=triples,
        ops_capacity_df=capacity,
        week_start='2025-09-22',
        office='TestOffice',
        solver_time_limit_s=5,
        seed=42
    )

    # Count VIN assignments
    vin_counts = {}
    for assignment in result['selected_assignments']:
        vin = assignment['vin']
        vin_counts[vin] = vin_counts.get(vin, 0) + 1

    print(f"Total assignments: {len(result['selected_assignments'])}")
    print(f"VIN counts: {vin_counts}")
    print(f"Objective value: {result['objective_value']}")

    # Check that each VIN appears at most once
    all_unique = all(count <= 1 for count in vin_counts.values())

    # Should select the highest scoring option for VIN001 (score=2000)
    vin001_selected = [a for a in result['selected_assignments'] if a['vin'] == 'VIN001']
    highest_selected = len(vin001_selected) == 1 and vin001_selected[0]['score'] == 2000

    if all_unique and highest_selected:
        print("✅ PASS: Each VIN appears at most once, highest score selected")
        return True
    else:
        print("❌ FAIL: VIN uniqueness constraint violated or suboptimal selection")
        return False


def test_monotonic_capacity():
    """Test: Raise Friday slots; objective never decreases."""
    print("\n" + "="*60)
    print("TEST 3: MONOTONIC CAPACITY")
    print("="*60)

    triples = create_minimal_triples()
    week_start = '2025-09-22'

    # Low Friday capacity
    low_capacity = pd.DataFrame([
        {'office': 'TestOffice', 'date': '2025-09-22', 'slots': 10},  # Mon
        {'office': 'TestOffice', 'date': '2025-09-23', 'slots': 10},  # Tue
        {'office': 'TestOffice', 'date': '2025-09-24', 'slots': 10},  # Wed
        {'office': 'TestOffice', 'date': '2025-09-25', 'slots': 10},  # Thu
        {'office': 'TestOffice', 'date': '2025-09-26', 'slots': 1},   # Fri (LOW)
        {'office': 'TestOffice', 'date': '2025-09-27', 'slots': 10},  # Sat
        {'office': 'TestOffice', 'date': '2025-09-28', 'slots': 10},  # Sun
    ] + [
        {'office': 'TestOffice', 'date': f'2025-09-29', 'slots': 10},  # Mon
        {'office': 'TestOffice', 'date': f'2025-09-30', 'slots': 10},  # Tue
        {'office': 'TestOffice', 'date': f'2025-10-01', 'slots': 10},  # Wed
        {'office': 'TestOffice', 'date': f'2025-10-02', 'slots': 10},  # Thu
        {'office': 'TestOffice', 'date': f'2025-10-03', 'slots': 10},  # Fri
    ])

    result_low = solve_core_assignment(
        triples_df=triples,
        ops_capacity_df=low_capacity,
        week_start=week_start,
        office='TestOffice',
        solver_time_limit_s=5,
        seed=42
    )

    # High Friday capacity
    high_capacity = low_capacity.copy()
    high_capacity.loc[high_capacity['date'] == '2025-09-26', 'slots'] = 10  # Fri (HIGH)

    result_high = solve_core_assignment(
        triples_df=triples,
        ops_capacity_df=high_capacity,
        week_start=week_start,
        office='TestOffice',
        solver_time_limit_s=5,
        seed=42
    )

    print(f"Objective with low Friday capacity: {result_low['objective_value']}")
    print(f"Objective with high Friday capacity: {result_high['objective_value']}")
    print(f"Assignments (low): {len(result_low['selected_assignments'])}")
    print(f"Assignments (high): {len(result_high['selected_assignments'])}")

    # Check Friday usage
    fri_usage_low = next(
        (d['used'] for d in result_low['daily_usage'] if d['date'] == '2025-09-26'), 0
    )
    fri_usage_high = next(
        (d['used'] for d in result_high['daily_usage'] if d['date'] == '2025-09-26'), 0
    )

    print(f"Friday usage (low capacity): {fri_usage_low}")
    print(f"Friday usage (high capacity): {fri_usage_high}")

    if (result_high['objective_value'] >= result_low['objective_value'] and
        fri_usage_low <= 1 and fri_usage_high <= 10):
        print("✅ PASS: Objective is monotonic, capacity respected")
        return True
    else:
        print("❌ FAIL: Objective decreased or capacity violated")
        return False


def test_determinism():
    """Test: Two runs with same seed produce identical outputs."""
    print("\n" + "="*60)
    print("TEST 4: DETERMINISM")
    print("="*60)

    triples = create_minimal_triples()
    week_start = '2025-09-22'

    # Create capacity for 2 weeks (properly handling month boundaries)
    dates = []
    start = pd.to_datetime('2025-09-22')
    for i in range(14):
        dates.append((start + timedelta(days=i)).strftime('%Y-%m-%d'))

    capacity = pd.DataFrame([
        {'office': 'TestOffice', 'date': date, 'slots': 10}
        for date in dates
    ])

    # Run 1
    result1 = solve_core_assignment(
        triples_df=triples,
        ops_capacity_df=capacity,
        week_start=week_start,
        office='TestOffice',
        solver_time_limit_s=5,
        seed=42
    )

    # Run 2 (same seed)
    result2 = solve_core_assignment(
        triples_df=triples,
        ops_capacity_df=capacity,
        week_start=week_start,
        office='TestOffice',
        solver_time_limit_s=5,
        seed=42
    )

    # Run 3 (different seed)
    result3 = solve_core_assignment(
        triples_df=triples,
        ops_capacity_df=capacity,
        week_start=week_start,
        office='TestOffice',
        solver_time_limit_s=5,
        seed=99
    )

    # Compare assignments
    def assignment_key(a):
        return f"{a['vin']}_{a['person_id']}_{a['start_day']}"

    assignments1 = sorted([assignment_key(a) for a in result1['selected_assignments']])
    assignments2 = sorted([assignment_key(a) for a in result2['selected_assignments']])
    assignments3 = sorted([assignment_key(a) for a in result3['selected_assignments']])

    same_12 = (assignments1 == assignments2 and
               result1['objective_value'] == result2['objective_value'])

    print(f"Run 1 (seed=42): {len(assignments1)} assignments, obj={result1['objective_value']}")
    print(f"Run 2 (seed=42): {len(assignments2)} assignments, obj={result2['objective_value']}")
    print(f"Run 3 (seed=99): {len(assignments3)} assignments, obj={result3['objective_value']}")
    print(f"Runs 1&2 identical: {same_12}")

    if same_12:
        print("✅ PASS: Same seed produces identical results")
        return True
    else:
        print("❌ FAIL: Determinism not working")
        return False


def main():
    """Run all minimal tests."""
    print("="*80)
    print("PHASE 7.2 MINIMAL TEST SUITE")
    print("="*80)

    results = []

    # Run each test
    results.append(("Capacity Tightness", test_capacity_tightness()))
    results.append(("VIN Uniqueness", test_vin_uniqueness()))
    results.append(("Monotonic Capacity", test_monotonic_capacity()))
    results.append(("Determinism", test_determinism()))

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
        print("\n🎉 ALL TESTS PASSED!")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)