"""
Minimal tests for Phase 7.7 (Dynamic Capacity).

Tests C7-A, C7-B, C7-C as specified in the requirements.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.solver.ortools_solver_v6 import solve_with_all_constraints
from app.solver.dynamic_capacity import (
    load_capacity_calendar,
    identify_special_days,
    validate_capacity_compliance
)


def test_c7a_blackout():
    """C7-A: Wednesday has slots=0, no assignments allowed."""
    print("\n" + "="*60)
    print("C7-A: BLACKOUT")
    print("="*60)

    # Wednesday 9/24 is a blackout (slots=0)
    ops_capacity = pd.DataFrame([
        {'office': 'LA', 'date': '2025-09-22', 'slots': 5},   # Mon
        {'office': 'LA', 'date': '2025-09-23', 'slots': 5},   # Tue
        {'office': 'LA', 'date': '2025-09-24', 'slots': 0, 'notes': 'Company Holiday'},  # Wed - BLACKOUT
        {'office': 'LA', 'date': '2025-09-25', 'slots': 5},   # Thu
        {'office': 'LA', 'date': '2025-09-26', 'slots': 5},   # Fri
    ])

    # Triples for each day of the week
    triples = pd.DataFrame([
        {'vin': f'V{i}', 'person_id': f'P00{i}', 'start_day': f'2025-09-{22+i}',
         'make': 'Toyota', 'model': 'Camry', 'office': 'LA',
         'rank': 'A', 'score': 1000}
        for i in range(5)  # Mon-Fri
    ])

    approved = pd.DataFrame([
        {'person_id': f'P00{i}', 'make': 'Toyota', 'rank': 'A'}
        for i in range(5)
    ])

    result = solve_with_all_constraints(
        triples_df=triples,
        ops_capacity_df=ops_capacity,
        approved_makes_df=approved,
        loan_history_df=pd.DataFrame(),
        rules_df=pd.DataFrame(),
        budgets_df=pd.DataFrame(),
        week_start='2025-09-22',
        office='LA',
        lambda_cap=0,
        lambda_fair=0,
        seed=42,
        verbose=False
    )

    selected = result['selected_assignments']
    wednesday_assignments = [a for a in selected if a['start_day'] == '2025-09-24']
    special_days = result.get('special_days', {})
    blackouts = special_days.get('blackouts', [])

    print(f"Wednesday assignments: {len(wednesday_assignments)}")
    print(f"Blackout days identified: {len(blackouts)}")
    if blackouts:
        print(f"  - {blackouts[0]['date']} ({blackouts[0]['day']}): {blackouts[0]['notes']}")

    # Verify no assignments on blackout day
    # Note: weekends are also blackouts by default
    wednesday_blackout = any(b['date'] == '2025-09-24' for b in blackouts)
    if len(wednesday_assignments) == 0 and wednesday_blackout:
        print("✅ PASS: Blackout enforced, no Wednesday assignments")
        return True
    else:
        print("❌ FAIL: Expected 0 Wednesday assignments and blackout identified")
        return False


def test_c7b_tighten():
    """C7-B: Friday slots reduced to 2, only 2 assignments allowed."""
    print("\n" + "="*60)
    print("C7-B: TIGHTEN")
    print("="*60)

    # Friday has reduced capacity
    ops_capacity = pd.DataFrame([
        {'office': 'LA', 'date': '2025-09-22', 'slots': 5},   # Mon
        {'office': 'LA', 'date': '2025-09-23', 'slots': 5},   # Tue
        {'office': 'LA', 'date': '2025-09-24', 'slots': 5},   # Wed
        {'office': 'LA', 'date': '2025-09-25', 'slots': 5},   # Thu
        {'office': 'LA', 'date': '2025-09-26', 'slots': 2, 'notes': 'Half-day operations'},  # Fri - REDUCED
    ])

    # 4 candidates want Friday (but only 2 slots)
    triples = pd.DataFrame([
        {'vin': f'V{i}', 'person_id': f'P00{i}', 'start_day': '2025-09-26',
         'make': 'Toyota', 'model': 'Camry', 'office': 'LA',
         'rank': 'A', 'score': 1000 - i*10}  # Scores: 1000, 990, 980, 970
        for i in range(4)
    ])

    approved = pd.DataFrame([
        {'person_id': f'P00{i}', 'make': 'Toyota', 'rank': 'A'}
        for i in range(4)
    ])

    result = solve_with_all_constraints(
        triples_df=triples,
        ops_capacity_df=ops_capacity,
        approved_makes_df=approved,
        loan_history_df=pd.DataFrame(),
        rules_df=pd.DataFrame(),
        budgets_df=pd.DataFrame(),
        week_start='2025-09-22',
        office='LA',
        lambda_cap=0,
        lambda_fair=0,
        seed=42,
        verbose=False
    )

    selected = result['selected_assignments']
    friday_assignments = [a for a in selected if a['start_day'] == '2025-09-26']
    special_days = result.get('special_days', {})
    reduced_days = special_days.get('reduced_capacity', [])

    print(f"Friday assignments: {len(friday_assignments)} (limit 2)")
    print(f"Reduced capacity days: {len(reduced_days)}")
    if reduced_days:
        print(f"  - {reduced_days[0]['date']}: {reduced_days[0]['slots']} slots ({reduced_days[0]['notes']})")

    # Should pick top 2 scores (P000, P001)
    if friday_assignments:
        selected_ids = sorted([a['person_id'] for a in friday_assignments])
        print(f"Selected: {', '.join(selected_ids)}")

    # Friday (9/26) should have reduced capacity
    friday_reduced = any(d['date'] == '2025-09-26' and d['slots'] == 2 for d in reduced_days)
    if len(friday_assignments) == 2 and friday_reduced:
        print("✅ PASS: Friday capacity limit enforced (2 slots)")
        return True
    else:
        print(f"❌ FAIL: Expected exactly 2 Friday assignments, got {len(friday_assignments)}")
        return False


def test_c7c_notes_surfaced():
    """C7-C: Travel day notes appear in capacity_notes."""
    print("\n" + "="*60)
    print("C7-C: NOTES SURFACED")
    print("="*60)

    # Thursday is a travel day with reduced capacity and notes
    ops_capacity = pd.DataFrame([
        {'office': 'LA', 'date': '2025-09-22', 'slots': 5},   # Mon
        {'office': 'LA', 'date': '2025-09-23', 'slots': 5},   # Tue
        {'office': 'LA', 'date': '2025-09-24', 'slots': 5},   # Wed
        {'office': 'LA', 'date': '2025-09-25', 'slots': 3,    # Thu - TRAVEL DAY
         'notes': 'Travel day - team at conference'},
        {'office': 'LA', 'date': '2025-09-26', 'slots': 5},   # Fri
    ])

    # Simple test with one assignment on travel day
    triples = pd.DataFrame([
        {'vin': 'V1', 'person_id': 'P001', 'start_day': '2025-09-25',
         'make': 'Toyota', 'model': 'Camry', 'office': 'LA',
         'rank': 'A', 'score': 1000}
    ])

    approved = pd.DataFrame([
        {'person_id': 'P001', 'make': 'Toyota', 'rank': 'A'}
    ])

    result = solve_with_all_constraints(
        triples_df=triples,
        ops_capacity_df=ops_capacity,
        approved_makes_df=approved,
        loan_history_df=pd.DataFrame(),
        rules_df=pd.DataFrame(),
        budgets_df=pd.DataFrame(),
        week_start='2025-09-22',
        office='LA',
        lambda_cap=0,
        lambda_fair=0,
        seed=42,
        verbose=False
    )

    capacity_notes = result.get('capacity_notes', [])
    special_days = result.get('special_days', {})
    travel_days = special_days.get('travel_days', [])

    print(f"Capacity notes found: {len(capacity_notes)}")
    if capacity_notes:
        for note in capacity_notes:
            print(f"  - {note['date']} ({note['day']}): {note['notes']}")

    print(f"Travel days identified: {len(travel_days)}")
    if travel_days:
        for day in travel_days:
            print(f"  - {day['date']}: {day['slots']} slots - {day['notes']}")

    # Verify notes are surfaced
    has_travel_note = any('travel' in note.get('notes', '').lower() for note in capacity_notes)
    has_travel_day = len(travel_days) == 1

    if has_travel_note and has_travel_day:
        print("✅ PASS: Travel day notes properly surfaced")
        return True
    else:
        print("❌ FAIL: Travel day notes not found")
        return False


def test_capacity_validation():
    """Additional test: Validate capacity compliance checking."""
    print("\n" + "="*60)
    print("CAPACITY VALIDATION TEST")
    print("="*60)

    # Load test calendar
    ops_capacity = pd.DataFrame([
        {'office': 'LA', 'date': '2025-09-22', 'slots': 2},
        {'office': 'LA', 'date': '2025-09-23', 'slots': 0},  # Blackout
        {'office': 'LA', 'date': '2025-09-24', 'slots': 3},
    ])

    capacity_map, notes_map = load_capacity_calendar(
        ops_capacity_df=ops_capacity,
        office='LA',
        week_start='2025-09-22'
    )

    # Test assignments that violate capacity
    bad_assignments = [
        {'start_day': '2025-09-22', 'person_id': 'P1'},
        {'start_day': '2025-09-22', 'person_id': 'P2'},
        {'start_day': '2025-09-22', 'person_id': 'P3'},  # Exceeds capacity of 2
        {'start_day': '2025-09-23', 'person_id': 'P4'},  # Blackout day
    ]

    is_valid, violations = validate_capacity_compliance(bad_assignments, capacity_map)

    print(f"Validation result: {'VALID' if is_valid else 'INVALID'}")
    print(f"Violations found: {len(violations)}")
    for violation in violations:
        print(f"  - {violation}")

    # Should have 2-3 violations (blackout may be reported twice)
    if not is_valid and len(violations) >= 2:
        print("✅ PASS: Capacity violations correctly detected")
        return True
    else:
        print(f"❌ FAIL: Should have detected violations, got {len(violations)}")
        return False


def main():
    """Run all Phase 7.7 mini-tests."""
    print("="*80)
    print("PHASE 7.7 MINI-TESTS (C7-A, C7-B, C7-C)")
    print("Dynamic capacity constraint minimal tests")
    print("="*80)

    results = []

    # Run each test
    results.append(("C7-A - Blackout", test_c7a_blackout()))
    results.append(("C7-B - Tighten", test_c7b_tighten()))
    results.append(("C7-C - Notes surfaced", test_c7c_notes_surfaced()))
    results.append(("Capacity validation", test_capacity_validation()))

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
        print("\n🎉 ALL DYNAMIC CAPACITY MINI-TESTS PASSED!")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)