"""
Integration test for Phase 7.7 (Dynamic Capacity) and 7.8 (Objective Shaping) with real data.
"""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.database import DatabaseService
from app.solver.ortools_solver_v6 import solve_with_all_constraints
from app.solver.ortools_feasible_v2 import build_feasible_start_day_triples as generate_feasible_triples
from app.solver.cooldown_filter import apply_cooldown_filter as filter_by_cooldown
from app.solver.ortools_solver_v2 import add_score_to_triples


async def test_real_data_integration():
    """Test Phase 7.7 and 7.8 with real LA data."""
    print("="*80)
    print("PHASE 7.7 + 7.8 REAL DATA INTEGRATION TEST")
    print("="*80)

    db = DatabaseService()
    await db.initialize()

    try:
        # Load real data
        print("\n=== Loading Real Data ===")

        # Vehicles
        vehicles_response = db.client.table('vehicles').select('*').execute()
        vehicles_df = pd.DataFrame(vehicles_response.data)
        print(f"Vehicles: {len(vehicles_df)}")

        # Partners
        partners_response = db.client.table('partners').select('*').execute()
        partners_df = pd.DataFrame(partners_response.data)
        print(f"Partners: {len(partners_df)}")

        # Availability
        availability_response = db.client.table('availability').select('*').execute()
        availability_df = pd.DataFrame(availability_response.data)
        print(f"Availability records: {len(availability_df)}")

        # Ops capacity with dynamic slots and notes
        ops_capacity_response = db.client.table('ops_capacity_calendar').select('*').execute()
        ops_capacity_df = pd.DataFrame(ops_capacity_response.data)
        print(f"Ops capacity records: {len(ops_capacity_df)}")

        # Approved makes
        approved_response = db.client.table('approved_makes').select('*').execute()
        approved_makes_df = pd.DataFrame(approved_response.data)
        print(f"Approved makes: {len(approved_makes_df)}")

        # Loan history
        history_response = db.client.table('loan_history').select('*').execute()
        loan_history_df = pd.DataFrame(history_response.data)
        print(f"Loan history: {len(loan_history_df)}")

        # Rules
        rules_response = db.client.table('rules').select('*').execute()
        rules_df = pd.DataFrame(rules_response.data)
        print(f"Rules: {len(rules_df)}")

        # Budgets
        budgets_response = db.client.table('budgets').select('*').execute()
        budgets_df = pd.DataFrame(budgets_response.data)
        print(f"Budgets: {len(budgets_df)}")

        week_start = '2025-09-22'
        office = 'Los Angeles'

        # Phase 7.1: Generate feasible triples
        print("\n=== Phase 7.1: Generating Feasible Triples ===")
        triples = generate_feasible_triples(
            vehicles_df=vehicles_df,
            partners_df=partners_df,
            availability_df=availability_df,
            ops_capacity_df=ops_capacity_df,
            approved_makes_df=approved_makes_df,
            week_start=week_start,
            office=office,
            verbose=True
        )
        print(f"Feasible triples: {len(triples)}")

        # Phase 7.3: Apply cooldown filter
        print("\n=== Phase 7.3: Applying Cooldown Filter ===")
        triples_filtered = filter_by_cooldown(
            triples_df=triples,
            loan_history_df=loan_history_df,
            week_start=week_start,
            cooldown_days=30,
            verbose=True
        )
        print(f"Post-cooldown triples: {len(triples_filtered)}")

        # Add scores (required for solver)
        triples_filtered = add_score_to_triples(triples_filtered)

        # Check for dynamic capacity features
        print("\n=== Phase 7.7: Dynamic Capacity Check ===")
        la_capacity = ops_capacity_df[ops_capacity_df['office'] == office]

        # Look for special days in the week
        week_dates = pd.date_range(week_start, periods=7)
        special_days = []

        for date in week_dates:
            date_str = date.strftime('%Y-%m-%d')
            day_capacity = la_capacity[la_capacity['date'] == date_str]

            if not day_capacity.empty:
                row = day_capacity.iloc[0]
                slots = row.get('slots', 0)
                notes = row.get('notes', '')

                # Identify special days
                if slots == 0:
                    special_days.append(f"  - {date_str} ({date.strftime('%A')}): BLACKOUT {notes}")
                elif notes and 'travel' in notes.lower():
                    special_days.append(f"  - {date_str} ({date.strftime('%A')}): TRAVEL DAY ({slots} slots) - {notes}")
                elif notes:
                    special_days.append(f"  - {date_str} ({date.strftime('%A')}): {slots} slots - {notes}")

        if special_days:
            print("Special days found:")
            for day in special_days:
                print(day)
        else:
            print("No special days with notes in this week")

        # Test with different objective shaping weights
        print("\n=== Phase 7.8: Testing Objective Shaping ===")

        # Check if we have the shaping columns
        shaping_cols = ['rank_weight', 'geo_office_match', 'pub_rate_24m', 'history_published']
        missing_cols = [col for col in shaping_cols if col not in triples_filtered.columns]

        if missing_cols:
            print(f"Adding mock shaping columns: {missing_cols}")
            # Add mock data for testing
            if 'rank_weight' not in triples_filtered.columns:
                # Map rank to weight
                rank_weights = {'S': 1000, 'A': 900, 'B': 800, 'C': 700, 'D': 600}
                triples_filtered['rank_weight'] = triples_filtered['rank'].map(
                    lambda x: rank_weights.get(x, 500)
                )

            if 'geo_office_match' not in triples_filtered.columns:
                # Random geo matches for testing
                np.random.seed(42)
                triples_filtered['geo_office_match'] = np.random.choice([0, 1], size=len(triples_filtered), p=[0.7, 0.3])

            if 'pub_rate_24m' not in triples_filtered.columns:
                # Random publication rates
                triples_filtered['pub_rate_24m'] = np.random.uniform(0, 1, size=len(triples_filtered))

            if 'history_published' not in triples_filtered.columns:
                # Random history
                triples_filtered['history_published'] = np.random.choice([0, 1], size=len(triples_filtered), p=[0.8, 0.2])

        # Configuration 1: Default weights
        print("\n--- Configuration 1: Default Weights ---")
        result1 = solve_with_all_constraints(
            triples_df=triples_filtered,
            ops_capacity_df=ops_capacity_df,
            approved_makes_df=approved_makes_df,
            loan_history_df=loan_history_df,
            rules_df=rules_df,
            budgets_df=budgets_df,
            week_start=week_start,
            office=office,
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
        if 'capacity_notes' in result1 and result1['capacity_notes']:
            print("\nCapacity Notes:")
            for note in result1['capacity_notes']:
                print(f"  - {note['date']}: {note['notes']}")

        if 'special_days' in result1 and result1['special_days']:
            special = result1['special_days']
            if special.get('blackouts'):
                print(f"Blackout days: {len(special['blackouts'])}")
            if special.get('travel_days'):
                print(f"Travel days: {len(special['travel_days'])}")

        # Check shaping breakdown
        if 'shaping_breakdown' in result1:
            shaping = result1['shaping_breakdown']
            weights = shaping.get('weights', {})
            components = shaping.get('components', {})
            counts = shaping.get('counts', {})

            print("\nObjective Shaping Results:")
            print(f"  Weights: rank={weights.get('w_rank')}, geo={weights.get('w_geo')}, "
                  f"pub={weights.get('w_pub')}, hist={weights.get('w_hist')}")
            print(f"  Component totals: rank={components.get('rank_total', 0):.0f}, "
                  f"geo={components.get('geo_total', 0):.0f}, "
                  f"pub={components.get('pub_total', 0):.0f}, "
                  f"hist={components.get('hist_total', 0):.0f}")
            print(f"  Metrics: geo_matches={counts.get('geo_matches', 0)}, "
                  f"avg_pub_rate={counts.get('avg_pub_rate', 0):.3f}")

        # Configuration 2: Favor geographic matches
        print("\n--- Configuration 2: High Geographic Weight ---")
        result2 = solve_with_all_constraints(
            triples_df=triples_filtered,
            ops_capacity_df=ops_capacity_df,
            approved_makes_df=approved_makes_df,
            loan_history_df=loan_history_df,
            rules_df=rules_df,
            budgets_df=budgets_df,
            week_start=week_start,
            office=office,
            # High geo weight
            w_rank=1.0,
            w_geo=500,  # 5x higher
            w_pub=150,
            w_hist=50,
            # Other parameters
            lambda_cap=800,
            lambda_fair=200,
            fair_step_up=400,
            seed=42,
            verbose=False
        )

        if 'shaping_breakdown' in result2:
            counts2 = result2['shaping_breakdown'].get('counts', {})
            print(f"Selected: {len(result2['selected_assignments'])} assignments")
            print(f"Geo matches: {counts2.get('geo_matches', 0)} "
                  f"(vs {counts.get('geo_matches', 0)} with default weights)")

        # Configuration 3: Favor high publishers
        print("\n--- Configuration 3: High Publication Weight ---")
        result3 = solve_with_all_constraints(
            triples_df=triples_filtered,
            ops_capacity_df=ops_capacity_df,
            approved_makes_df=approved_makes_df,
            loan_history_df=loan_history_df,
            rules_df=rules_df,
            budgets_df=budgets_df,
            week_start=week_start,
            office=office,
            # High pub weight
            w_rank=1.0,
            w_geo=100,
            w_pub=500,  # Much higher
            w_hist=50,
            # Other parameters
            lambda_cap=800,
            lambda_fair=200,
            fair_step_up=400,
            seed=42,
            verbose=False
        )

        if 'shaping_breakdown' in result3:
            counts3 = result3['shaping_breakdown'].get('counts', {})
            print(f"Selected: {len(result3['selected_assignments'])} assignments")
            print(f"Avg pub rate: {counts3.get('avg_pub_rate', 0):.3f} "
                  f"(vs {counts.get('avg_pub_rate', 0):.3f} with default weights)")

        # Daily usage with dynamic capacity
        print("\n=== Daily Usage Report (Phase 7.7) ===")
        if 'daily_usage' in result1:
            print("Day       | Capacity | Used | Remaining | Notes")
            print("-" * 60)
            for day in result1['daily_usage']:
                date = day['date']
                capacity = day.get('capacity', 0)
                used = day.get('used', 0)
                remaining = day.get('remaining', 0)
                notes = day.get('notes', '')

                # Format date to day name
                day_name = pd.to_datetime(date).strftime('%a')

                notes_str = f" - {notes[:20]}" if notes else ""
                print(f"{date} {day_name} | {capacity:8} | {used:4} | {remaining:9} |{notes_str}")

        print("\n✅ Phase 7.7 + 7.8 Integration Test Complete!")
        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        await db.close()


def main():
    """Run the integration test."""
    print("\nTesting Phase 7.7 (Dynamic Capacity) and 7.8 (Objective Shaping) with real data...")
    success = asyncio.run(test_real_data_integration())
    return success


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)