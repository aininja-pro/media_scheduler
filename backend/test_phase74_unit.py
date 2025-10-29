"""
Unit tests for Phase 7.4 tier cap logic.

Tests:
1. Cap resolution precedence (make+rank → make → fallback)
2. Used_12m window calculation
3. Explicit 0/NULL = block
4. Window shift behavior
"""

import pandas as pd
from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.solver.tier_caps import (
    get_cap_for_pair,
    count_used_12m,
    normalize_rank,
    prefilter_zero_caps,
    DEFAULT_RANK_CAPS
)


def test_cap_resolution_precedence():
    """Test simplified cap resolution."""
    print("\n" + "="*60)
    print("TEST: SIMPLIFIED CAP RESOLUTION")
    print("="*60)

    # Test 1: Exact (make, rank) rule
    rules = pd.DataFrame([
        {'make': 'Toyota', 'rank': 'A', 'loan_cap_per_year': 10},
        {'make': 'Toyota', 'rank': 'B', 'loan_cap_per_year': 5},
    ])

    cap = get_cap_for_pair('P001', 'Toyota', 'A', rules)
    print(f"Toyota + A (exact rule match): {cap}")
    assert cap == 10, f"Expected 10, got {cap}"

    # Test 2: No rule match - use rank default
    cap = get_cap_for_pair('P001', 'Honda', 'A', pd.DataFrame())
    print(f"Honda + A (no rule, default): {cap}")
    assert cap == 100, f"Expected 100 (A default), got {cap}"

    # Test 3: A+ rank gets unlimited
    cap = get_cap_for_pair('P001', 'Genesis', 'A+', pd.DataFrame())
    print(f"Genesis + A+ (no rule, unlimited): {cap}")
    assert cap is None, f"Expected None (unlimited), got {cap}"

    # Test 4: B rank default
    cap = get_cap_for_pair('P001', 'Mazda', 'B', pd.DataFrame())
    print(f"Mazda + B (no rule, default): {cap}")
    assert cap == 50, f"Expected 50 (B default), got {cap}"

    # Test 5: C rank default
    cap = get_cap_for_pair('P001', 'Volvo', 'C', pd.DataFrame())
    print(f"Volvo + C (no rule, default): {cap}")
    assert cap == 10, f"Expected 10 (C default), got {cap}"

    print("✅ PASS: Simplified cap resolution working correctly")
    return True


def test_used_12m_window():
    """Test 12-month rolling window calculation."""
    print("\n" + "="*60)
    print("TEST: USED_12M WINDOW CALCULATION")
    print("="*60)

    week_start = datetime(2025, 9, 22)

    # Create loan history
    loans = pd.DataFrame([
        # Within 12 months (should count)
        {'person_id': 'P001', 'make': 'Toyota',
         'start_date': week_start - timedelta(days=30),
         'end_date': week_start - timedelta(days=23)},  # 1 month ago

        {'person_id': 'P001', 'make': 'Toyota',
         'start_date': week_start - timedelta(days=180),
         'end_date': week_start - timedelta(days=173)},  # 6 months ago

        {'person_id': 'P001', 'make': 'Toyota',
         'start_date': week_start - timedelta(days=360),
         'end_date': week_start - timedelta(days=353)},  # ~11.8 months ago

        # Outside 12 months (should not count)
        {'person_id': 'P001', 'make': 'Toyota',
         'start_date': week_start - timedelta(days=400),
         'end_date': week_start - timedelta(days=393)},  # >12 months ago

        # Different make (should not count)
        {'person_id': 'P001', 'make': 'Honda',
         'start_date': week_start - timedelta(days=60),
         'end_date': week_start - timedelta(days=53)},

        # Different person (should not count)
        {'person_id': 'P002', 'make': 'Toyota',
         'start_date': week_start - timedelta(days=60),
         'end_date': week_start - timedelta(days=53)},
    ])

    # Test count
    count = count_used_12m('P001', 'Toyota', loans, week_start, 12)
    print(f"Loans in 12m window: {count}")
    assert count == 3, f"Expected 3 loans in window, got {count}"

    # Test with no end_date (use start_date)
    loans_no_end = pd.DataFrame([
        {'person_id': 'P001', 'make': 'BMW',
         'start_date': week_start - timedelta(days=100),
         'end_date': None}
    ])

    count = count_used_12m('P001', 'BMW', loans_no_end, week_start, 12)
    print(f"Loan with no end_date: {count}")
    assert count == 1, f"Expected 1, got {count}"

    print("✅ PASS: Window calculation working correctly")
    return True


def test_explicit_zero_blocks():
    """Test that explicit 0 or NULL in rules = blocked."""
    print("\n" + "="*60)
    print("TEST: EXPLICIT ZERO/NULL BLOCKS")
    print("="*60)

    # Test 1: Explicit 0 blocks
    rules = pd.DataFrame([
        {'make': 'Volvo', 'rank': 'A', 'loan_cap_per_year': 0}
    ])

    cap = get_cap_for_pair('P001', 'Volvo', 'A', rules)
    print(f"Volvo + A (cap=0): {cap}")
    assert cap == 0, f"Expected 0, got {cap}"

    # Test 2: NULL also blocks
    rules = pd.DataFrame([
        {'make': 'Saab', 'rank': 'B', 'loan_cap_per_year': None}
    ])

    cap = get_cap_for_pair('P001', 'Saab', 'B', rules)
    print(f"Saab + B (cap=NULL): {cap}")
    assert cap == 0, f"Expected 0, got {cap}"

    # Test 3: No rule = fallback (not blocked)
    cap = get_cap_for_pair('P001', 'BMW', 'A', pd.DataFrame())
    print(f"BMW + A (no rule, fallback): {cap}")
    assert cap > 0, f"Expected >0, got {cap}"

    print("✅ PASS: Explicit zero/NULL blocks correctly")
    return True


def test_prefilter_zero_caps():
    """Test pre-filtering of zero cap triples."""
    print("\n" + "="*60)
    print("TEST: PRE-FILTER ZERO CAPS")
    print("="*60)

    # Rules blocking Volvo for specific ranks
    rules = pd.DataFrame([
        {'make': 'Volvo', 'rank': 'A', 'loan_cap_per_year': 0},
        {'make': 'Volvo', 'rank': 'B', 'loan_cap_per_year': 0}
    ])

    # Triples including Volvo
    triples = pd.DataFrame([
        {'vin': 'V1', 'person_id': 'P001', 'make': 'Volvo', 'office': 'LA'},
        {'vin': 'V2', 'person_id': 'P001', 'make': 'Toyota', 'office': 'LA'},
        {'vin': 'V3', 'person_id': 'P002', 'make': 'Volvo', 'office': 'LA'},
    ])

    approved = pd.DataFrame([
        {'person_id': 'P001', 'make': 'Volvo', 'rank': 'A'},
        {'person_id': 'P001', 'make': 'Toyota', 'rank': 'A'},
        {'person_id': 'P002', 'make': 'Volvo', 'rank': 'B'},
    ])

    # Pre-filter
    filtered = prefilter_zero_caps(triples, approved, rules)

    print(f"Input triples: {len(triples)}")
    print(f"Output triples: {len(filtered)}")
    print(f"Remaining makes: {filtered['make'].tolist()}")

    assert len(filtered) == 1, f"Expected 1 triple, got {len(filtered)}"
    assert filtered.iloc[0]['make'] == 'Toyota', "Expected only Toyota to remain"

    print("✅ PASS: Zero-cap pre-filter working")
    return True


def test_rank_normalization():
    """Test rank normalization (simplified - no unranked)."""
    print("\n" + "="*60)
    print("TEST: RANK NORMALIZATION")
    print("="*60)

    test_cases = [
        ("a", "A"),
        ("A", "A"),
        ("a+", "A+"),
        ("A+", "A+"),
        ("b", "B"),
        ("B", "B"),
        ("c", "C"),
        ("C", "C"),
        (None, "C"),  # Missing defaults to most restrictive
    ]

    for input_rank, expected in test_cases:
        result = normalize_rank(input_rank)
        print(f"  '{input_rank}' → '{result}'")
        assert result == expected, f"Expected {expected}, got {result}"

    print("✅ PASS: Rank normalization working")
    return True


def main():
    """Run all unit tests."""
    print("="*80)
    print("PHASE 7.4 UNIT TESTS")
    print("Tier Cap Logic Components")
    print("="*80)

    results = []

    # Run each test
    results.append(("Simplified cap resolution", test_cap_resolution_precedence()))
    results.append(("Used_12m window", test_used_12m_window()))
    results.append(("Explicit zero blocks", test_explicit_zero_blocks()))
    results.append(("Pre-filter zero caps", test_prefilter_zero_caps()))
    results.append(("Rank normalization", test_rank_normalization()))

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
        print("\n🎉 ALL UNIT TESTS PASSED!")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)