"""
Test Phase 7.2 with REAL data - Core OR-Tools solver.

Tests the solver with actual production data from Supabase.
"""

import asyncio
import pandas as pd
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.database import DatabaseService
from app.solver.ortools_feasible_v2 import build_feasible_start_day_triples
from app.solver.ortools_solver_v2 import solve_core_assignment, add_score_to_triples
from app.etl.availability import build_availability_grid


async def test_phase72_with_real_data():
    """Test Phase 7.2 OR-Tools solver with real database data."""

    print("="*80)
    print("PHASE 7.2 TEST WITH REAL DATA")
    print("="*80)

    db = DatabaseService()
    await db.initialize()

    # Test parameters
    office = 'Los Angeles'
    week_start = '2025-09-22'  # Monday

    print(f"\nTest Configuration:")
    print(f"  Office: {office}")
    print(f"  Week: {week_start}")
    print()

    try:
        # 1. Generate feasible triples (Phase 7.1)
        print("1. Generating feasible triples...")

        # Load vehicles
        vehicles_response = db.client.table('vehicles').select('*').eq('office', office).execute()
        vehicles_df = pd.DataFrame(vehicles_response.data)
        print(f"   ✓ {len(vehicles_df)} vehicles")

        # Load partners
        partners_response = db.client.table('media_partners').select('*').eq('office', office).execute()
        partners_df = pd.DataFrame(partners_response.data)
        print(f"   ✓ {len(partners_df)} partners")

        # Load approved makes with pagination
        all_approved = []
        limit = 1000
        offset = 0
        while True:
            approved_response = db.client.table('approved_makes').select('*').range(offset, offset + limit - 1).execute()
            if not approved_response.data:
                break
            all_approved.extend(approved_response.data)
            offset += limit
            if len(approved_response.data) < limit:
                break

        approved_df = pd.DataFrame(all_approved)
        la_partner_ids = set(partners_df['person_id'].tolist())
        approved_la = approved_df[approved_df['person_id'].isin(la_partner_ids)]
        print(f"   ✓ {len(approved_la)} approved makes for LA partners")

        # Build availability
        activity_response = db.client.table('current_activity').select('*').execute()
        activity_df = pd.DataFrame(activity_response.data)
        if 'vehicle_vin' in activity_df.columns:
            activity_df = activity_df.rename(columns={'vehicle_vin': 'vin'})

        availability_df = build_availability_grid(
            vehicles_df=vehicles_df,
            activity_df=activity_df,
            week_start=week_start,
            office=office,
            availability_horizon_days=14
        )
        availability_df = availability_df.rename(columns={'day': 'date'})

        # Load capacity and taxonomy
        ops_cal_response = db.client.table('ops_capacity_calendar').select('*').execute()
        ops_calendar_df = pd.DataFrame(ops_cal_response.data)

        taxonomy_response = db.client.table('model_taxonomy').select('*').execute()
        taxonomy_df = pd.DataFrame(taxonomy_response.data)

        # Build feasible triples
        triples_df = build_feasible_start_day_triples(
            vehicles_df=vehicles_df,
            partners_df=partners_df,
            availability_df=availability_df,
            approved_makes_df=approved_la,
            week_start=week_start,
            office=office,
            ops_capacity_df=ops_calendar_df,
            model_taxonomy_df=taxonomy_df,
            start_days=['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
            min_available_days=7,
            default_slots_per_day=15
        )

        print(f"   ✓ Generated {len(triples_df)} feasible triples")

        if triples_df.empty:
            print("   ⚠️  No feasible triples - stopping")
            return

        # 2. Add scores to triples
        print("\n2. Adding scores to triples...")

        # Load publication data if available
        try:
            pub_response = db.client.table('publications').select('*').execute()
            publication_df = pd.DataFrame(pub_response.data)
        except:
            publication_df = pd.DataFrame()

        triples_with_scores = add_score_to_triples(
            triples_df=triples_df,
            partners_df=partners_df,
            publication_df=publication_df,
            rank_weights={"A+": 1000, "A": 700, "B": 400, "C": 100, "UNRANKED": 50},
            geo_bonus_points=100,
            history_bonus_points=50,
            seed=42
        )

        print(f"   ✓ Score range: {triples_with_scores['score'].min()} - {triples_with_scores['score'].max()}")
        print(f"   ✓ Mean score: {triples_with_scores['score'].mean():.1f}")

        # 3. Run OR-Tools solver (Phase 7.2)
        print("\n3. Running OR-Tools solver...")

        result = solve_core_assignment(
            triples_df=triples_with_scores,
            ops_capacity_df=ops_calendar_df,
            week_start=week_start,
            office=office,
            loan_length_days=7,
            solver_time_limit_s=10,
            seed=42
        )

        # 4. Analyze results
        print("\n" + "="*80)
        print("RESULTS")
        print("="*80)

        print(f"\nSolver Status: {result['meta']['solver_status']}")
        print(f"Wall Time: {result['timing']['wall_ms']}ms")
        print(f"Nodes Explored: {result['timing']['nodes_explored']}")

        print(f"\nObjective Value: {result['objective_value']:,}")
        print(f"Selected Assignments: {len(result['selected_assignments'])}")

        if result['selected_assignments']:
            # Day distribution
            day_counts = {}
            for assignment in result['selected_assignments']:
                day = pd.to_datetime(assignment['start_day']).strftime('%A')
                day_counts[day] = day_counts.get(day, 0) + 1

            print("\nAssignments by day:")
            for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
                count = day_counts.get(day, 0)
                print(f"  {day}: {count}")

            # Check capacity usage for main week
            print("\nCapacity usage (main week):")
            for i in range(7):
                day_data = result['daily_usage'][i]
                day_name = pd.to_datetime(day_data['date']).strftime('%A')
                print(f"  {day_name}: {day_data['used']}/{day_data['capacity']} "
                      f"(remaining: {day_data['remaining']})")

            # VIN uniqueness check
            vins = [a['vin'] for a in result['selected_assignments']]
            unique_vins = len(set(vins))
            print(f"\nVIN Uniqueness Check:")
            print(f"  Total VINs: {len(vins)}")
            print(f"  Unique VINs: {unique_vins}")
            print(f"  ✓ PASS" if len(vins) == unique_vins else f"  ❌ FAIL: Duplicates found!")

            # Partner distribution
            partners = [a['person_id'] for a in result['selected_assignments']]
            unique_partners = len(set(partners))
            print(f"\nPartner Distribution:")
            print(f"  Unique partners: {unique_partners}")

            # Make distribution
            makes = [a['make'] for a in result['selected_assignments']]
            make_counts = pd.Series(makes).value_counts().head(5)
            print(f"\nTop 5 makes:")
            for make, count in make_counts.items():
                print(f"  {make}: {count}")

            # Score statistics
            scores = [a['score'] for a in result['selected_assignments']]
            print(f"\nScore Statistics:")
            print(f"  Min: {min(scores)}")
            print(f"  Max: {max(scores)}")
            print(f"  Mean: {sum(scores)/len(scores):.1f}")

            # Export results
            output_file = 'phase72_assignments.csv'
            pd.DataFrame(result['selected_assignments']).to_csv(output_file, index=False)
            print(f"\n✓ Exported assignments to {output_file}")

        # 5. Verify constraints
        print("\n" + "="*80)
        print("CONSTRAINT VERIFICATION")
        print("="*80)

        all_valid = True

        # Check VIN uniqueness
        vins = [a['vin'] for a in result['selected_assignments']]
        if len(vins) != len(set(vins)):
            print("❌ VIN uniqueness violated!")
            all_valid = False
        else:
            print("✓ VIN uniqueness maintained")

        # Check capacity constraints
        capacity_ok = True
        for day_data in result['daily_usage']:
            if day_data['used'] > day_data['capacity']:
                print(f"❌ Capacity violated on {day_data['date']}: "
                      f"{day_data['used']} > {day_data['capacity']}")
                capacity_ok = False
                all_valid = False

        if capacity_ok:
            print("✓ All capacity constraints respected")

        # Check score calculation
        if result['selected_assignments']:
            calculated_obj = sum(a['score'] for a in result['selected_assignments'])
            if abs(calculated_obj - result['objective_value']) > 1:  # Allow small rounding
                print(f"❌ Objective mismatch: calculated={calculated_obj}, "
                      f"reported={result['objective_value']}")
                all_valid = False
            else:
                print("✓ Objective value correct")

        if all_valid:
            print("\n✅ ALL CONSTRAINTS VERIFIED!")
        else:
            print("\n⚠️  Some constraints failed verification")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await db.close()

    print("\n" + "="*80)
    print("PHASE 7.2 TEST COMPLETE")
    print("="*80)


if __name__ == "__main__":
    print("Testing Phase 7.2 with real production data...")
    asyncio.run(test_phase72_with_real_data())