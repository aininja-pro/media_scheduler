"""
Simplified integration test for Phase 7.7 and 7.8 with mock realistic data.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.solver.ortools_solver_v6 import solve_with_all_constraints


def test_phase_77_78():
    """Test Phase 7.7 and 7.8 with realistic mock data."""
    print("="*80)
    print("PHASE 7.7 + 7.8 INTEGRATION TEST")
    print("="*80)

    # Create realistic mock data
    print("\n=== Creating Mock LA Data ===")

    # Mock feasible triples with scoring columns
    np.random.seed(42)
    num_triples = 500

    makes = ['Toyota', 'Honda', 'BMW', 'Mercedes-Benz', 'Audi', 'Volvo']
    models = ['Camry', 'Accord', '3 Series', 'C-Class', 'A4', 'XC90']
    ranks = ['S', 'A', 'B', 'C']
    rank_weights = {'S': 1000, 'A': 900, 'B': 800, 'C': 700}

    triples = []
    for i in range(num_triples):
        make_idx = i % len(makes)
        rank = ranks[i % len(ranks)]

        triple = {
            'vin': f'VIN{i:04d}',
            'person_id': f'P{i % 50:03d}',  # 50 unique partners
            'start_day': f'2025-09-{22 + (i % 7)}',  # Spread across week
            'make': makes[make_idx],
            'model': models[make_idx],
            'office': 'Los Angeles',
            'rank': rank,
            'rank_weight': rank_weights[rank],
            'geo_office_match': np.random.choice([0, 1], p=[0.6, 0.4]),  # 40% local
            'pub_rate_24m': np.random.beta(2, 5),  # Skewed towards lower rates
            'history_published': np.random.choice([0, 1], p=[0.7, 0.3]),  # 30% have history
            'score': rank_weights[rank]  # Base score
        }
        triples.append(triple)

    triples_df = pd.DataFrame(triples)
    print(f"Created {len(triples_df)} mock triples")

    # Mock ops capacity with dynamic features (Phase 7.7)
    ops_capacity = pd.DataFrame([
        {'office': 'Los Angeles', 'date': '2025-09-22', 'slots': 15, 'notes': ''},  # Mon
        {'office': 'Los Angeles', 'date': '2025-09-23', 'slots': 15, 'notes': ''},  # Tue
        {'office': 'Los Angeles', 'date': '2025-09-24', 'slots': 0, 'notes': 'Company Holiday'},  # Wed - BLACKOUT
        {'office': 'Los Angeles', 'date': '2025-09-25', 'slots': 8, 'notes': 'Travel day - reduced staff'},  # Thu - TRAVEL
        {'office': 'Los Angeles', 'date': '2025-09-26', 'slots': 12, 'notes': 'Half day'},  # Fri - REDUCED
        {'office': 'Los Angeles', 'date': '2025-09-27', 'slots': 0, 'notes': ''},  # Sat - Weekend
        {'office': 'Los Angeles', 'date': '2025-09-28', 'slots': 0, 'notes': ''},  # Sun - Weekend
    ])
    print(f"Created dynamic capacity calendar with blackouts and travel days")

    # Mock approved makes
    approved_makes = pd.DataFrame([
        {'person_id': f'P{i:03d}', 'make': makes[i % len(makes)], 'rank': ranks[i % len(ranks)]}
        for i in range(50)
    ])

    # Mock loan history (for cooldown)
    loan_history = pd.DataFrame([
        {
            'person_id': f'P{i:03d}',
            'make': makes[i % len(makes)],
            'start_date': '2025-09-01',
            'end_date': '2025-09-08'
        }
        for i in range(5)  # Some recent loans
    ])

    # Mock rules (for tier caps)
    rules = pd.DataFrame([
        {'make': make, 'rank': rank, 'annual_cap': 50 if rank == 'S' else 100}
        for make in makes
        for rank in ranks
    ])

    # Mock budgets
    budgets = pd.DataFrame([
        {
            'office': 'Los Angeles',
            'fleet': make.upper(),
            'year': 2025,
            'quarter': 'Q3',
            'budget_amount': 100000,
            'amount_used': 50000
        }
        for make in makes
    ])

    print("\n=== Phase 7.7: Dynamic Capacity Features ===")

    # Show special days
    special_days = ops_capacity[
        (ops_capacity['slots'] == 0) |
        (ops_capacity['notes'].str.contains('travel', case=False, na=False)) |
        (ops_capacity['notes'] != '')
    ]

    if not special_days.empty:
        print("Special days in the week:")
        for _, day in special_days.iterrows():
            date = pd.to_datetime(day['date'])
            day_name = date.strftime('%A')
            if day['slots'] == 0:
                print(f"  - {day['date']} ({day_name}): BLACKOUT - {day['notes'] or 'Weekend'}")
            elif 'travel' in day['notes'].lower():
                print(f"  - {day['date']} ({day_name}): TRAVEL DAY ({day['slots']} slots) - {day['notes']}")
            elif day['notes']:
                print(f"  - {day['date']} ({day_name}): {day['slots']} slots - {day['notes']}")

    print("\n=== Phase 7.8: Testing Different Weight Configurations ===")

    # Test 1: Default weights
    print("\n--- Test 1: Default Weights ---")
    result1 = solve_with_all_constraints(
        triples_df=triples_df,
        ops_capacity_df=ops_capacity,
        approved_makes_df=approved_makes,
        loan_history_df=loan_history,
        rules_df=rules,
        budgets_df=budgets,
        week_start='2025-09-22',
        office='Los Angeles',
        # Default weights
        w_rank=1.0,
        w_geo=100,
        w_pub=150,
        w_hist=50,
        # Other parameters
        lambda_cap=800,
        lambda_fair=200,
        fair_step_up=400,
        seed=42,
        verbose=True
    )

    print(f"\nSelected: {len(result1['selected_assignments'])} assignments")

    # Check dynamic capacity reporting
    if 'special_days' in result1:
        special = result1['special_days']
        if special.get('blackouts'):
            print(f"Blackouts identified: {len(special['blackouts'])}")
        if special.get('travel_days'):
            print(f"Travel days identified: {len(special['travel_days'])}")
        if special.get('reduced_capacity'):
            print(f"Reduced capacity days: {len(special['reduced_capacity'])}")

    # Check shaping breakdown
    if 'shaping_breakdown' in result1:
        shaping = result1['shaping_breakdown']
        counts = shaping.get('counts', {})
        print(f"\nDefault weights metrics:")
        print(f"  - Geo matches: {counts.get('geo_matches', 0)}")
        print(f"  - Avg pub rate: {counts.get('avg_pub_rate', 0):.3f}")
        print(f"  - With history: {counts.get('with_history', 0)}")

    # Test 2: High geographic preference
    print("\n--- Test 2: High Geographic Weight (w_geo=500) ---")
    result2 = solve_with_all_constraints(
        triples_df=triples_df,
        ops_capacity_df=ops_capacity,
        approved_makes_df=approved_makes,
        loan_history_df=loan_history,
        rules_df=rules,
        budgets_df=budgets,
        week_start='2025-09-22',
        office='Los Angeles',
        # High geo weight
        w_rank=1.0,
        w_geo=500,  # 5x default
        w_pub=150,
        w_hist=50,
        lambda_cap=800,
        lambda_fair=200,
        fair_step_up=400,
        seed=42,
        verbose=False
    )

    if 'shaping_breakdown' in result2:
        counts2 = result2['shaping_breakdown'].get('counts', {})
        print(f"Selected: {len(result2['selected_assignments'])} assignments")
        print(f"  - Geo matches: {counts2.get('geo_matches', 0)} (vs {counts.get('geo_matches', 0)} default)")

        # Calculate change
        if counts.get('geo_matches', 0) > 0:
            change = ((counts2.get('geo_matches', 0) - counts.get('geo_matches', 0))
                     / counts.get('geo_matches', 0) * 100)
            print(f"  - Change: {change:+.1f}%")

    # Test 3: High publication rate preference
    print("\n--- Test 3: High Publication Weight (w_pub=500) ---")
    result3 = solve_with_all_constraints(
        triples_df=triples_df,
        ops_capacity_df=ops_capacity,
        approved_makes_df=approved_makes,
        loan_history_df=loan_history,
        rules_df=rules,
        budgets_df=budgets,
        week_start='2025-09-22',
        office='Los Angeles',
        # High pub weight
        w_rank=1.0,
        w_geo=100,
        w_pub=500,  # Much higher
        w_hist=50,
        lambda_cap=800,
        lambda_fair=200,
        fair_step_up=400,
        seed=42,
        verbose=False
    )

    if 'shaping_breakdown' in result3:
        counts3 = result3['shaping_breakdown'].get('counts', {})
        print(f"Selected: {len(result3['selected_assignments'])} assignments")
        print(f"  - Avg pub rate: {counts3.get('avg_pub_rate', 0):.3f} (vs {counts.get('avg_pub_rate', 0):.3f} default)")

        # Calculate change
        if counts.get('avg_pub_rate', 0) > 0:
            change = ((counts3.get('avg_pub_rate', 0) - counts.get('avg_pub_rate', 0))
                     / counts.get('avg_pub_rate', 0) * 100)
            print(f"  - Change: {change:+.1f}%")

    # Daily usage report showing dynamic capacity
    print("\n=== Daily Usage with Dynamic Capacity (Phase 7.7) ===")
    if 'daily_usage' in result1:
        print("\nDate       Day | Capacity | Used | Remaining | Notes")
        print("-" * 70)

        for day in result1['daily_usage']:
            date = day['date']
            capacity = day.get('capacity', 0)
            used = day.get('used', 0)
            remaining = day.get('remaining', 0)
            notes = day.get('notes', '')

            # Format date to day name
            date_obj = pd.to_datetime(date)
            day_name = date_obj.strftime('%a')

            # Color coding for special days
            if capacity == 0:
                status = "BLACKOUT"
            elif notes and 'travel' in notes.lower():
                status = "TRAVEL"
            elif notes:
                status = "SPECIAL"
            else:
                status = ""

            notes_str = notes[:25] if notes else ""
            print(f"{date} {day_name} | {capacity:8} | {used:4} | {remaining:9} | {notes_str}")

    # Verify no assignments on blackout days
    print("\n=== Blackout Compliance Check ===")
    wednesday_assignments = [
        a for a in result1['selected_assignments']
        if a['start_day'] == '2025-09-24'
    ]

    if len(wednesday_assignments) == 0:
        print("✅ PASS: No assignments on blackout day (Wednesday)")
    else:
        print(f"❌ FAIL: Found {len(wednesday_assignments)} assignments on blackout day")

    # Check monotonic response to weight changes
    print("\n=== Monotonic Response Verification ===")

    geo_baseline = counts.get('geo_matches', 0) if 'shaping_breakdown' in result1 else 0
    geo_high = counts2.get('geo_matches', 0) if 'shaping_breakdown' in result2 else 0

    pub_baseline = counts.get('avg_pub_rate', 0) if 'shaping_breakdown' in result1 else 0
    pub_high = counts3.get('avg_pub_rate', 0) if 'shaping_breakdown' in result3 else 0

    geo_monotonic = geo_high >= geo_baseline
    pub_monotonic = pub_high >= pub_baseline

    print(f"Geographic preference monotonic: {'✅' if geo_monotonic else '❌'}")
    print(f"Publication rate monotonic: {'✅' if pub_monotonic else '❌'}")

    if geo_monotonic and pub_monotonic:
        print("\n✅ Phase 7.7 + 7.8 Integration Test PASSED!")
        return True
    else:
        print("\n❌ Some tests failed")
        return False


def main():
    """Run the simplified integration test."""
    success = test_phase_77_78()
    return success


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)