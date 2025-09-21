"""
Minimal test suite for Phase 7.1 feasible triples generation.

These tests use tiny fixtures to verify specific behaviors without mocks.
"""

import pandas as pd
from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.solver.ortools_feasible_v2 import build_feasible_start_day_triples
from app.etl.availability import build_availability_grid


def create_minimal_data():
    """Create minimal test fixtures."""

    # 2 vehicles
    vehicles_df = pd.DataFrame([
        {'vin': 'VIN001', 'make': 'Toyota', 'model': 'Camry', 'office': 'TestOffice'},
        {'vin': 'VIN002', 'make': 'Honda', 'model': 'Accord', 'office': 'TestOffice'}
    ])

    # 2 partners
    partners_df = pd.DataFrame([
        {'person_id': 'P001', 'name': 'Partner 1', 'office': 'TestOffice'},
        {'person_id': 'P002', 'name': 'Partner 2', 'office': 'TestOffice'}
    ])

    # Approved makes - P001 approved for Toyota only, P002 approved for both
    approved_makes_df = pd.DataFrame([
        {'person_id': 'P001', 'make': 'Toyota', 'rank': 1},
        {'person_id': 'P002', 'make': 'Toyota', 'rank': 1},
        {'person_id': 'P002', 'make': 'Honda', 'rank': 2}
    ])

    # Empty ops capacity and taxonomy for simplicity
    ops_capacity_df = pd.DataFrame()
    model_taxonomy_df = pd.DataFrame()

    return vehicles_df, partners_df, approved_makes_df, ops_capacity_df, model_taxonomy_df


def test_availability_window():
    """Test: A VIN missing availability on s+3 is excluded for that s."""
    print("\n" + "="*60)
    print("TEST 1: AVAILABILITY WINDOW")
    print("="*60)

    vehicles_df, partners_df, approved_makes_df, ops_capacity_df, model_taxonomy_df = create_minimal_data()
    week_start = '2025-09-22'  # Monday

    # Create activity blocking VIN001 on Thursday (day 3)
    activity_df = pd.DataFrame([
        {
            'vin': 'VIN001',
            'activity_type': 'service',
            'start_date': '2025-09-25',  # Thursday
            'end_date': '2025-09-25'
        }
    ])

    # Build availability with the blocked day
    availability_df = build_availability_grid(
        vehicles_df=vehicles_df,
        activity_df=activity_df,
        week_start=week_start,
        office='TestOffice',
        availability_horizon_days=14
    )
    availability_df = availability_df.rename(columns={'day': 'date'})

    # Check Monday start (should be blocked due to Thursday)
    triples_monday = build_feasible_start_day_triples(
        vehicles_df=vehicles_df,
        partners_df=partners_df,
        availability_df=availability_df,
        approved_makes_df=approved_makes_df,
        week_start=week_start,
        office='TestOffice',
        ops_capacity_df=ops_capacity_df,
        model_taxonomy_df=model_taxonomy_df,
        start_days=['Mon'],  # Monday only
        min_available_days=7,
        default_slots_per_day=15
    )

    # Check Friday start (should be allowed - Thursday block is before Friday window)
    triples_friday = build_feasible_start_day_triples(
        vehicles_df=vehicles_df,
        partners_df=partners_df,
        availability_df=availability_df,
        approved_makes_df=approved_makes_df,
        week_start=week_start,
        office='TestOffice',
        ops_capacity_df=ops_capacity_df,
        model_taxonomy_df=model_taxonomy_df,
        start_days=['Fri'],  # Friday only
        min_available_days=7,
        default_slots_per_day=15
    )

    vin001_monday = triples_monday[triples_monday['vin'] == 'VIN001']
    vin001_friday = triples_friday[triples_friday['vin'] == 'VIN001']

    print(f"VIN001 triples for Monday start: {len(vin001_monday)}")
    print(f"VIN001 triples for Friday start: {len(vin001_friday)}")

    if len(vin001_monday) == 0 and len(vin001_friday) > 0:
        print("✅ PASS: VIN001 blocked for Monday (due to Thu conflict), allowed for Friday")
        return True
    else:
        print("❌ FAIL: Availability window not working correctly")
        return False


def test_start_day_slots():
    """Test: Setting slots=0 on Thu yields no Thu triples."""
    print("\n" + "="*60)
    print("TEST 2: START-DAY SLOTS")
    print("="*60)

    vehicles_df, partners_df, approved_makes_df, _, model_taxonomy_df = create_minimal_data()
    week_start = '2025-09-22'

    # Create ops_capacity with Thursday slots = 0
    ops_capacity_df = pd.DataFrame([
        {'office': 'TestOffice', 'date': '2025-09-22', 'slots': 15},  # Mon
        {'office': 'TestOffice', 'date': '2025-09-23', 'slots': 15},  # Tue
        {'office': 'TestOffice', 'date': '2025-09-24', 'slots': 15},  # Wed
        {'office': 'TestOffice', 'date': '2025-09-25', 'slots': 0},   # Thu - ZERO
        {'office': 'TestOffice', 'date': '2025-09-26', 'slots': 15},  # Fri
    ])

    # No activities - all vehicles available
    activity_df = pd.DataFrame()
    availability_df = build_availability_grid(
        vehicles_df=vehicles_df,
        activity_df=activity_df,
        week_start=week_start,
        office='TestOffice',
        availability_horizon_days=14
    )
    availability_df = availability_df.rename(columns={'day': 'date'})

    # Build triples for all days
    triples_df = build_feasible_start_day_triples(
        vehicles_df=vehicles_df,
        partners_df=partners_df,
        availability_df=availability_df,
        approved_makes_df=approved_makes_df,
        week_start=week_start,
        office='TestOffice',
        ops_capacity_df=ops_capacity_df,
        model_taxonomy_df=model_taxonomy_df,
        start_days=['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
        min_available_days=7,
        default_slots_per_day=15
    )

    # Check Thursday triples
    thursday_date = pd.to_datetime('2025-09-25')
    thursday_triples = triples_df[pd.to_datetime(triples_df['start_day']) == thursday_date]
    other_triples = triples_df[pd.to_datetime(triples_df['start_day']) != thursday_date]

    print(f"Thursday triples: {len(thursday_triples)}")
    print(f"Other day triples: {len(other_triples)}")

    if len(thursday_triples) == 0 and len(other_triples) > 0:
        print("✅ PASS: No Thursday triples when slots=0")
        return True
    else:
        print("❌ FAIL: Thursday slots=0 not preventing triples")
        return False


def test_eligibility_strict():
    """Test: A partner without approved_makes row for VIN's make never appears."""
    print("\n" + "="*60)
    print("TEST 3: ELIGIBILITY STRICT")
    print("="*60)

    vehicles_df, partners_df, approved_makes_df, ops_capacity_df, model_taxonomy_df = create_minimal_data()
    week_start = '2025-09-22'

    # No activities
    activity_df = pd.DataFrame()
    availability_df = build_availability_grid(
        vehicles_df=vehicles_df,
        activity_df=activity_df,
        week_start=week_start,
        office='TestOffice',
        availability_horizon_days=14
    )
    availability_df = availability_df.rename(columns={'day': 'date'})

    # Build triples
    triples_df = build_feasible_start_day_triples(
        vehicles_df=vehicles_df,
        partners_df=partners_df,
        availability_df=availability_df,
        approved_makes_df=approved_makes_df,
        week_start=week_start,
        office='TestOffice',
        ops_capacity_df=ops_capacity_df,
        model_taxonomy_df=model_taxonomy_df,
        start_days=['Mon'],
        min_available_days=7,
        default_slots_per_day=15
    )

    # Check P001 (only approved for Toyota) with Honda vehicle
    p001_honda = triples_df[(triples_df['person_id'] == 'P001') & (triples_df['make'] == 'Honda')]
    p001_toyota = triples_df[(triples_df['person_id'] == 'P001') & (triples_df['make'] == 'Toyota')]
    p002_honda = triples_df[(triples_df['person_id'] == 'P002') & (triples_df['make'] == 'Honda')]

    print(f"P001 + Honda triples: {len(p001_honda)}")
    print(f"P001 + Toyota triples: {len(p001_toyota)}")
    print(f"P002 + Honda triples: {len(p002_honda)}")

    if len(p001_honda) == 0 and len(p001_toyota) > 0 and len(p002_honda) > 0:
        print("✅ PASS: Strict eligibility - P001 only gets Toyota, not Honda")
        return True
    else:
        print("❌ FAIL: Eligibility not strictly enforced")
        return False


def test_determinism():
    """Test: Two runs with same seed produce identical results."""
    print("\n" + "="*60)
    print("TEST 4: DETERMINISM")
    print("="*60)

    vehicles_df, partners_df, approved_makes_df, ops_capacity_df, model_taxonomy_df = create_minimal_data()
    week_start = '2025-09-22'

    # No activities
    activity_df = pd.DataFrame()
    availability_df = build_availability_grid(
        vehicles_df=vehicles_df,
        activity_df=activity_df,
        week_start=week_start,
        office='TestOffice',
        availability_horizon_days=14
    )
    availability_df = availability_df.rename(columns={'day': 'date'})

    # Run 1 with seed=42
    triples_1 = build_feasible_start_day_triples(
        vehicles_df=vehicles_df,
        partners_df=partners_df,
        availability_df=availability_df,
        approved_makes_df=approved_makes_df,
        week_start=week_start,
        office='TestOffice',
        ops_capacity_df=ops_capacity_df,
        model_taxonomy_df=model_taxonomy_df,
        start_days=['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
        min_available_days=7,
        default_slots_per_day=15,
        seed=42
    )

    # Run 2 with seed=42 (same)
    triples_2 = build_feasible_start_day_triples(
        vehicles_df=vehicles_df,
        partners_df=partners_df,
        availability_df=availability_df,
        approved_makes_df=approved_makes_df,
        week_start=week_start,
        office='TestOffice',
        ops_capacity_df=ops_capacity_df,
        model_taxonomy_df=model_taxonomy_df,
        start_days=['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
        min_available_days=7,
        default_slots_per_day=15,
        seed=42
    )

    # Run 3 with seed=99 (different)
    triples_3 = build_feasible_start_day_triples(
        vehicles_df=vehicles_df,
        partners_df=partners_df,
        availability_df=availability_df,
        approved_makes_df=approved_makes_df,
        week_start=week_start,
        office='TestOffice',
        ops_capacity_df=ops_capacity_df,
        model_taxonomy_df=model_taxonomy_df,
        start_days=['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
        min_available_days=7,
        default_slots_per_day=15,
        seed=99
    )

    # Compare
    same_count = len(triples_1) == len(triples_2)
    same_order = triples_1.equals(triples_2) if same_count else False
    different_from_3 = not triples_1.equals(triples_3) or len(triples_1) != len(triples_3)

    print(f"Run 1 (seed=42): {len(triples_1)} triples")
    print(f"Run 2 (seed=42): {len(triples_2)} triples")
    print(f"Run 3 (seed=99): {len(triples_3)} triples")
    print(f"Runs 1&2 identical: {same_order}")
    print(f"Run 3 different: {different_from_3}")

    if same_order:
        print("✅ PASS: Same seed produces identical results")
        return True
    else:
        print("❌ FAIL: Determinism not working")
        return False


def main():
    """Run all minimal tests."""
    print("="*80)
    print("PHASE 7.1 MINIMAL TEST SUITE")
    print("="*80)

    results = []

    # Run each test
    results.append(("Availability Window", test_availability_window()))
    results.append(("Start-Day Slots", test_start_day_slots()))
    results.append(("Eligibility Strict", test_eligibility_strict()))
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