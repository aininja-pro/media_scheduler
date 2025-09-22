"""
Minimal tests for Phase 7.6 (Budget Constraints).

Tests B1-B6 as specified in the requirements.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.solver.ortools_solver_v6 import solve_with_all_constraints
from app.solver.budget_constraints import get_quarter_from_date


def test_b1_prefer_in_budget():
    """B1: Two equal-score assignments, one in-budget, one exceeds. Expect: in-budget selected."""
    print("\n" + "="*60)
    print("B1: PREFER IN-BUDGET")
    print("="*60)

    # Budget with limited remaining
    budgets = pd.DataFrame([{
        'office': 'LA',
        'fleet': 'TOYOTA',
        'year': 2025,
        'quarter': 'Q3',
        'budget_amount': 5000,
        'amount_used': 4000  # Only $1000 remaining
    }])

    # Two vehicles, equal scores, but second would exceed budget
    triples = pd.DataFrame([
        {'vin': 'V1', 'person_id': 'P001', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Camry', 'office': 'LA',
         'rank': 'A', 'score': 1000},
        {'vin': 'V2', 'person_id': 'P001', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Corolla', 'office': 'LA',
         'rank': 'A', 'score': 1000},
    ])

    ops_capacity = pd.DataFrame([
        {'office': 'LA', 'date': '2025-09-22', 'slots': 1}  # Can only pick one
    ])

    approved = pd.DataFrame([
        {'person_id': 'P001', 'make': 'Toyota', 'rank': 'A'}
    ])

    # Each assignment costs $1000, budget has $1000 remaining
    # Selecting one stays in budget, selecting both would exceed
    result = solve_with_all_constraints(
        triples_df=triples,
        ops_capacity_df=ops_capacity,
        approved_makes_df=approved,
        loan_history_df=pd.DataFrame(),
        rules_df=pd.DataFrame(),
        budgets_df=budgets,
        week_start='2025-09-22',
        office='LA',
        cost_per_assignment={'Toyota': 1000},
        points_per_dollar=3,
        enforce_budget_hard=False,  # Soft mode
        lambda_cap=0,
        lambda_fair=0,
        seed=42,
        verbose=False
    )

    selected = result['selected_assignments']
    budget_penalty = result['objective_breakdown']['budget_penalty']

    print(f"Selected: {len(selected)} assignment(s)")
    print(f"Budget penalty: {budget_penalty} points")

    if len(selected) == 1 and budget_penalty == 0:
        print("✅ PASS: Solver selected in-budget option")
        return True
    else:
        print("❌ FAIL: Expected 1 assignment with no penalty")
        return False


def test_b2_permit_with_price():
    """B2: Only option exceeds budget; soft mode picks it with correct penalty."""
    print("\n" + "="*60)
    print("B2: PERMIT WITH PRICE")
    print("="*60)

    budgets = pd.DataFrame([{
        'office': 'LA',
        'fleet': 'TOYOTA',
        'year': 2025,
        'quarter': 'Q3',
        'budget_amount': 1000,
        'amount_used': 500  # $500 remaining
    }])

    # Single option that costs $1000 (exceeds $500 remaining)
    triples = pd.DataFrame([
        {'vin': 'V1', 'person_id': 'P001', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Camry', 'office': 'LA',
         'rank': 'A', 'score': 2000}  # High score to justify overage
    ])

    ops_capacity = pd.DataFrame([
        {'office': 'LA', 'date': '2025-09-22', 'slots': 1}
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
        budgets_df=budgets,
        week_start='2025-09-22',
        office='LA',
        cost_per_assignment={'Toyota': 1000},
        points_per_dollar=3,
        enforce_budget_hard=False,  # Soft mode
        lambda_cap=0,
        lambda_fair=0,
        seed=42,
        verbose=False
    )

    selected = result['selected_assignments']
    budget_penalty = result['objective_breakdown']['budget_penalty']
    expected_penalty = 3 * 500  # $500 overage × 3 points/dollar

    print(f"Selected: {len(selected)} assignment(s)")
    print(f"Budget penalty: {budget_penalty} points (expected {expected_penalty})")

    if len(selected) == 1 and budget_penalty == expected_penalty:
        print("✅ PASS: Soft mode allowed overage with correct penalty")
        return True
    else:
        print(f"❌ FAIL: Expected 1 assignment with {expected_penalty} penalty")
        return False


def test_b3_hard_block():
    """B3: Same as B2 but with hard mode; should block assignment."""
    print("\n" + "="*60)
    print("B3: HARD BLOCK")
    print("="*60)

    budgets = pd.DataFrame([{
        'office': 'LA',
        'fleet': 'TOYOTA',
        'year': 2025,
        'quarter': 'Q3',
        'budget_amount': 1000,
        'amount_used': 500  # $500 remaining
    }])

    # Single option that costs $1000 (exceeds $500 remaining)
    triples = pd.DataFrame([
        {'vin': 'V1', 'person_id': 'P001', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Camry', 'office': 'LA',
         'rank': 'A', 'score': 2000}
    ])

    ops_capacity = pd.DataFrame([
        {'office': 'LA', 'date': '2025-09-22', 'slots': 1}
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
        budgets_df=budgets,
        week_start='2025-09-22',
        office='LA',
        cost_per_assignment={'Toyota': 1000},
        points_per_dollar=3,
        enforce_budget_hard=True,  # HARD mode
        lambda_cap=0,
        lambda_fair=0,
        seed=42,
        verbose=False
    )

    selected = result['selected_assignments']
    toyota_spend = sum(1000 for a in selected if a['make'] == 'Toyota')

    print(f"Selected: {len(selected)} assignment(s)")
    print(f"Toyota spend: ${toyota_spend} (budget remaining: $500)")

    if len(selected) == 0:
        print("✅ PASS: Hard mode blocked over-budget assignment")
        return True
    else:
        print("❌ FAIL: Hard mode should have blocked assignment")
        return False


def test_b4_null_amount_used():
    """B4: Budget with NULL amount_used treated as 0."""
    print("\n" + "="*60)
    print("B4: NULL AMOUNT_USED")
    print("="*60)

    budgets = pd.DataFrame([{
        'office': 'LA',
        'fleet': 'TOYOTA',
        'year': 2025,
        'quarter': 'Q3',
        'budget_amount': 2000,
        'amount_used': None  # NULL - should be treated as 0
    }])

    triples = pd.DataFrame([
        {'vin': 'V1', 'person_id': 'P001', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Camry', 'office': 'LA',
         'rank': 'A', 'score': 1000}
    ])

    ops_capacity = pd.DataFrame([
        {'office': 'LA', 'date': '2025-09-22', 'slots': 1}
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
        budgets_df=budgets,
        week_start='2025-09-22',
        office='LA',
        cost_per_assignment={'Toyota': 1000},
        points_per_dollar=3,
        enforce_budget_hard=False,
        lambda_cap=0,
        lambda_fair=0,
        seed=42,
        verbose=False
    )

    selected = result['selected_assignments']
    budget_penalty = result['objective_breakdown']['budget_penalty']

    print(f"Selected: {len(selected)} assignment(s)")
    print(f"Budget penalty: {budget_penalty} points")
    print(f"NULL amount_used treated as 0, full $2000 available")

    if len(selected) == 1 and budget_penalty == 0:
        print("✅ PASS: NULL amount_used correctly treated as 0")
        return True
    else:
        print("❌ FAIL: Should have selected with no penalty")
        return False


def test_b5_already_overspent():
    """B5: Already overspent budget; penalty only on additional spend."""
    print("\n" + "="*60)
    print("B5: ALREADY OVERSPENT")
    print("="*60)

    budgets = pd.DataFrame([{
        'office': 'LA',
        'fleet': 'TOYOTA',
        'year': 2025,
        'quarter': 'Q3',
        'budget_amount': 1000,
        'amount_used': 2000  # Already $1000 over budget
    }])

    triples = pd.DataFrame([
        {'vin': 'V1', 'person_id': 'P001', 'start_day': '2025-09-22',
         'make': 'Toyota', 'model': 'Camry', 'office': 'LA',
         'rank': 'A', 'score': 1000}
    ])

    ops_capacity = pd.DataFrame([
        {'office': 'LA', 'date': '2025-09-22', 'slots': 1}
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
        budgets_df=budgets,
        week_start='2025-09-22',
        office='LA',
        cost_per_assignment={'Toyota': 300},  # $300 assignment
        points_per_dollar=3,
        enforce_budget_hard=False,
        lambda_cap=0,
        lambda_fair=0,
        seed=42,
        verbose=False
    )

    selected = result['selected_assignments']
    budget_penalty = result['objective_breakdown']['budget_penalty']
    expected_penalty = 3 * 300  # Only $300 additional spend

    print(f"Budget already -$1000 (overspent)")
    print(f"New assignment: $300")
    print(f"Penalty: {budget_penalty} points (expected {expected_penalty})")

    if len(selected) == 1 and budget_penalty == expected_penalty:
        print("✅ PASS: Penalty only on additional $300, not total $1300")
        return True
    else:
        print(f"❌ FAIL: Expected penalty of {expected_penalty}, got {budget_penalty}")
        return False


def test_b6_mapping_quarter():
    """B6: Sep 30 maps to Q3, Oct 1 maps to Q4."""
    print("\n" + "="*60)
    print("B6: MAPPING/QUARTER")
    print("="*60)

    # Two budgets for different quarters
    budgets = pd.DataFrame([
        {
            'office': 'LA',
            'fleet': 'TOYOTA',
            'year': 2025,
            'quarter': 'Q3',
            'budget_amount': 1000,
            'amount_used': 0
        },
        {
            'office': 'LA',
            'fleet': 'TOYOTA',
            'year': 2025,
            'quarter': 'Q4',
            'budget_amount': 2000,
            'amount_used': 0
        }
    ])

    # Two assignments on quarter boundary
    triples = pd.DataFrame([
        {'vin': 'V1', 'person_id': 'P001', 'start_day': '2025-09-30',  # Q3
         'make': 'Toyota', 'model': 'Camry', 'office': 'LA',
         'rank': 'A', 'score': 1000},
        {'vin': 'V2', 'person_id': 'P001', 'start_day': '2025-10-01',  # Q4
         'make': 'Toyota', 'model': 'Corolla', 'office': 'LA',
         'rank': 'A', 'score': 1000},
    ])

    # Test quarter mapping directly
    q3_year, q3_quarter = get_quarter_from_date('2025-09-30')
    q4_year, q4_quarter = get_quarter_from_date('2025-10-01')

    print(f"Sep 30, 2025 → {q3_quarter} {q3_year}")
    print(f"Oct 1, 2025 → {q4_quarter} {q4_year}")

    ops_capacity = pd.DataFrame([
        {'office': 'LA', 'date': '2025-09-30', 'slots': 1},
        {'office': 'LA', 'date': '2025-10-01', 'slots': 1}
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
        budgets_df=budgets,
        week_start='2025-09-29',  # Week spans quarters
        office='LA',
        cost_per_assignment={'Toyota': 500},
        points_per_dollar=3,
        enforce_budget_hard=False,
        lambda_cap=0,
        lambda_fair=0,
        seed=42,
        verbose=False
    )

    # Check budget summary for correct quarter assignment
    budget_summary = result['budget_summary']
    budget_penalty = result['objective_breakdown']['budget_penalty']

    q3_correct = q3_quarter == 'Q3'
    q4_correct = q4_quarter == 'Q4'
    no_penalty = budget_penalty == 0  # Both should be within budget

    print(f"\nQuarter mapping: Q3={q3_correct}, Q4={q4_correct}")
    print(f"Budget penalty: {budget_penalty} (should be 0)")

    if q3_correct and q4_correct and no_penalty:
        print("✅ PASS: Quarters mapped correctly, budgets respected")
        return True
    else:
        print("❌ FAIL: Quarter mapping or budget calculation error")
        return False


def main():
    """Run all budget mini-tests B1-B6."""
    print("="*80)
    print("PHASE 7.6 MINI-TESTS (B1-B6)")
    print("Budget constraint minimal tests")
    print("="*80)

    results = []

    # Run each test
    results.append(("B1 - Prefer in-budget", test_b1_prefer_in_budget()))
    results.append(("B2 - Permit with price", test_b2_permit_with_price()))
    results.append(("B3 - Hard block", test_b3_hard_block()))
    results.append(("B4 - NULL amount_used", test_b4_null_amount_used()))
    results.append(("B5 - Already overspent", test_b5_already_overspent()))
    results.append(("B6 - Mapping/quarter", test_b6_mapping_quarter()))

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
        print("\n🎉 ALL BUDGET MINI-TESTS PASSED!")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)