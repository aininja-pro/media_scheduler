"""
Sanity self-tests for Phase 5 implementation.
Quick probes to catch implementation issues.
"""

import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from app.solver.candidates import build_weekly_candidates
from app.solver.greedy_assign import generate_week_schedule


def _mk(data):
    """Helper to create DataFrame from list of dicts."""
    return pd.DataFrame(data)


def test_availability_default_7_days():
    """Test: calling build_weekly_candidates without min_available_days should require 7 days."""
    print("TEST 1: Availability default = 7 days")

    # VIN with only 6 available days
    availability_df = _mk([
        {"vin": "v1", "date": "2025-09-22", "market": "LA", "make": "Toyota", "model": "Camry", "available": True},
        {"vin": "v1", "date": "2025-09-23", "market": "LA", "make": "Toyota", "model": "Camry", "available": True},
        {"vin": "v1", "date": "2025-09-24", "market": "LA", "make": "Toyota", "model": "Camry", "available": True},
        {"vin": "v1", "date": "2025-09-25", "market": "LA", "make": "Toyota", "model": "Camry", "available": True},
        {"vin": "v1", "date": "2025-09-26", "market": "LA", "make": "Toyota", "model": "Camry", "available": True},
        {"vin": "v1", "date": "2025-09-27", "market": "LA", "make": "Toyota", "model": "Camry", "available": True},
        {"vin": "v1", "date": "2025-09-28", "market": "LA", "make": "Toyota", "model": "Camry", "available": False},  # Not available Sunday
    ])

    cooldown_df = _mk([])
    publication_df = _mk([{"person_id": "p1", "make": "Toyota", "publication_rate_observed": None, "supported": False, "coverage": 0}])
    eligibility_df = _mk([{"person_id": "p1", "make": "Toyota"}])

    # Call WITHOUT min_available_days parameter (should default to 7)
    result = build_weekly_candidates(
        availability_df=availability_df,
        cooldown_df=cooldown_df,
        publication_df=publication_df,
        week_start="2025-09-22",
        eligibility_df=eligibility_df
        # Note: NO min_available_days parameter - should default to 7
    )

    # Should be empty because VIN only has 6/7 days available
    if result.empty:
        print("   ✅ PASS: Default requires 7 days, VIN with 6 days rejected")
    else:
        print("   ❌ FAIL: Default should require 7 days")

    return result.empty


def test_tier_cap_zero_blocks():
    """Test: RULES cap 0 for (make, rank) + one candidate → no assignments."""
    print("\nTEST 2: Tier cap zero blocks assignments")

    candidates_df = _mk([
        {"vin": "v1", "person_id": "p1", "market": "LA", "make": "Toyota", "model": "Camry", "week_start": "2025-09-22", "available_days": 7, "cooldown_ok": True, "rank": "A", "score": 70}
    ])

    loan_history_df = _mk([])  # No historical usage
    ops_capacity_df = _mk([{"office": "LA", "drivers_per_day": 10}])

    # Rules with cap=0 for Toyota/A
    rules_df = _mk([{"make": "Toyota", "rank": "A", "loan_cap_per_year": 0}])

    result = generate_week_schedule(
        candidates_scored_df=candidates_df,
        loan_history_df=loan_history_df,
        ops_capacity_df=ops_capacity_df,
        office="LA",
        week_start="2025-09-22",
        rules_df=rules_df
    )

    if result.empty:
        print("   ✅ PASS: Cap=0 blocks all assignments")
    else:
        print("   ❌ FAIL: Cap=0 should block assignments")

    return result.empty


def test_tier_cap_null_blocks():
    """Test: missing value → no assignments."""
    print("\nTEST 3: Tier cap NULL blocks assignments")

    candidates_df = _mk([
        {"vin": "v1", "person_id": "p1", "market": "LA", "make": "Honda", "model": "Accord", "week_start": "2025-09-22", "available_days": 7, "cooldown_ok": True, "rank": "B", "score": 50}
    ])

    loan_history_df = _mk([])
    ops_capacity_df = _mk([{"office": "LA", "drivers_per_day": 10}])

    # Rules with NULL cap
    rules_df = _mk([{"make": "Honda", "rank": "B", "loan_cap_per_year": None}])

    result = generate_week_schedule(
        candidates_scored_df=candidates_df,
        loan_history_df=loan_history_df,
        ops_capacity_df=ops_capacity_df,
        office="LA",
        week_start="2025-09-22",
        rules_df=rules_df
    )

    if result.empty:
        print("   ✅ PASS: Cap=NULL blocks all assignments")
    else:
        print("   ❌ FAIL: Cap=NULL should block assignments")

    return result.empty


def test_tier_cap_rolling_window():
    """Test: 11-month old loan allows assignment, 13-month old doesn't count."""
    print("\nTEST 4: Tier cap rolling window (12-month)")

    candidates_df = _mk([
        {"vin": "v1", "person_id": "p1", "market": "LA", "make": "Mazda", "model": "CX-5", "week_start": "2025-09-22", "available_days": 7, "cooldown_ok": True, "rank": "A", "score": 60}
    ])

    # Loan 11 months ago (should count toward cap)
    loan_11m_ago = (datetime(2025, 9, 22) - relativedelta(months=11)).strftime("%Y-%m-%d")

    # Loan 13 months ago (should NOT count toward cap)
    loan_13m_ago = (datetime(2025, 9, 22) - relativedelta(months=13)).strftime("%Y-%m-%d")

    ops_capacity_df = _mk([{"office": "LA", "drivers_per_day": 10}])
    rules_df = _mk([{"make": "Mazda", "rank": "A", "loan_cap_per_year": 1}])  # Cap = 1

    # Test A: 11-month old loan (should block new assignment)
    loan_history_11m = _mk([
        {"person_id": "p1", "make": "Mazda", "start_date": loan_11m_ago, "end_date": loan_11m_ago}
    ])

    result_11m = generate_week_schedule(
        candidates_scored_df=candidates_df,
        loan_history_df=loan_history_11m,
        ops_capacity_df=ops_capacity_df,
        office="LA",
        week_start="2025-09-22",
        rules_df=rules_df
    )

    # Test B: 13-month old loan (should allow new assignment)
    loan_history_13m = _mk([
        {"person_id": "p1", "make": "Mazda", "start_date": loan_13m_ago, "end_date": loan_13m_ago}
    ])

    result_13m = generate_week_schedule(
        candidates_scored_df=candidates_df,
        loan_history_df=loan_history_13m,
        ops_capacity_df=ops_capacity_df,
        office="LA",
        week_start="2025-09-22",
        rules_df=rules_df
    )

    test_11m_blocked = result_11m.empty
    test_13m_allowed = not result_13m.empty

    if test_11m_blocked and test_13m_allowed:
        print("   ✅ PASS: 11-month loan blocks (counts toward cap), 13-month loan allows (outside window)")
    else:
        print(f"   ❌ FAIL: 11-month blocked={test_11m_blocked}, 13-month allowed={test_13m_allowed}")
        print(f"   Expected: 11-month blocked=True, 13-month allowed=True")

    return test_11m_blocked and test_13m_allowed


def test_model_missing_cooldown_fallback():
    """Test: history (pid, make, model=None) blocks (pid, same make, any model)."""
    print("\nTEST 5: Model-missing cooldown fallback")

    # Candidate: Partner p1 wants Honda Accord
    availability_df = _mk([
        {"vin": "v1", "date": "2025-09-22", "market": "LA", "make": "Honda", "model": "Accord", "available": True},
        {"vin": "v1", "date": "2025-09-23", "market": "LA", "make": "Honda", "model": "Accord", "available": True},
        {"vin": "v1", "date": "2025-09-24", "market": "LA", "make": "Honda", "model": "Accord", "available": True},
        {"vin": "v1", "date": "2025-09-25", "market": "LA", "make": "Honda", "model": "Accord", "available": True},
        {"vin": "v1", "date": "2025-09-26", "market": "LA", "make": "Honda", "model": "Accord", "available": True},
        {"vin": "v1", "date": "2025-09-27", "market": "LA", "make": "Honda", "model": "Accord", "available": True},
        {"vin": "v1", "date": "2025-09-28", "market": "LA", "make": "Honda", "model": "Accord", "available": True},
    ])

    # Cooldown history: Partner p1 had Honda with model=None recently (within cooldown)
    recent_date = (datetime(2025, 9, 22) - timedelta(days=30)).strftime("%Y-%m-%d")  # 30 days ago
    cooldown_df = _mk([
        {"person_id": "p1", "make": "Honda", "model": None, "cooldown_ok": False}  # Blocked due to recent Honda loan (any model)
    ])

    publication_df = _mk([{"person_id": "p1", "make": "Honda", "publication_rate_observed": None, "supported": False, "coverage": 0}])
    eligibility_df = _mk([{"person_id": "p1", "make": "Honda"}])

    result = build_weekly_candidates(
        availability_df=availability_df,
        cooldown_df=cooldown_df,
        publication_df=publication_df,
        week_start="2025-09-22",
        eligibility_df=eligibility_df
    )

    if result.empty:
        print("   ✅ PASS: Model=None cooldown blocks any model of same make")
    else:
        print("   ❌ FAIL: Model=None cooldown should block same make regardless of model")

    return result.empty


def run_all_sanity_tests():
    """Run all sanity tests."""
    print("=" * 60)
    print("PHASE 5 SANITY TESTS")
    print("=" * 60)

    tests = [
        test_availability_default_7_days,
        test_tier_cap_zero_blocks,
        test_tier_cap_null_blocks,
        test_tier_cap_rolling_window,
        test_model_missing_cooldown_fallback
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            results.append(False)

    passed = sum(results)
    total = len(results)

    print(f"\n{'='*60}")
    print(f"SANITY TEST RESULTS: {passed}/{total} PASSED")
    print(f"{'='*60}")

    if passed == total:
        print("✅ ALL TESTS PASS - Phase 5 implementation is correct")
    else:
        print("❌ SOME TESTS FAILED - Implementation needs patches")

    return passed == total


if __name__ == "__main__":
    run_all_sanity_tests()