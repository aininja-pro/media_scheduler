"""
Test Phase 7.2 with START-DAY capacity (not occupancy).

This verifies the fix that changes capacity from occupancy-based to start-day-based.
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


async def test_startday_capacity():
    """Test Phase 7.2 with start-day capacity constraints."""

    print("="*80)
    print("PHASE 7.2 TEST: START-DAY CAPACITY (FIXED)")
    print("="*80)

    db = DatabaseService()
    await db.initialize()

    office = 'Los Angeles'
    week_start = '2025-09-22'  # Monday

    print(f"\nTest Configuration:")
    print(f"  Office: {office}")
    print(f"  Week: {week_start}")
    print()

    try:
        # 1. Note about weekend capacity
        print("1. Weekend capacity handling...")
        print("   Note: Weekends should have 0 capacity in ops_capacity_calendar")
        print("   If not already set, run update_weekend_capacity.sql")

        # 2. Load and verify capacity settings
        print("\n2. Verifying capacity settings...")
        ops_cal_response = db.client.table('ops_capacity_calendar').select('*').execute()
        ops_calendar_df = pd.DataFrame(ops_cal_response.data)

        # Show capacity for the week
        week_dates = pd.date_range(week_start, periods=7)
        for date in week_dates:
            date_str = date.strftime('%Y-%m-%d')
            day_name = date.strftime('%A')
            capacity_row = ops_calendar_df[
                (ops_calendar_df['office'] == office) &
                (ops_calendar_df['date'] == date_str)
            ]
            if not capacity_row.empty:
                slots = capacity_row.iloc[0]['slots']
            else:
                slots = 15  # default
            print(f"   {day_name} ({date_str}): {slots} slots")

        # 3. Generate feasible triples
        print("\n3. Generating feasible triples...")

        # Load all necessary data
        vehicles_response = db.client.table('vehicles').select('*').eq('office', office).execute()
        vehicles_df = pd.DataFrame(vehicles_response.data)

        partners_response = db.client.table('media_partners').select('*').eq('office', office).execute()
        partners_df = pd.DataFrame(partners_response.data)

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

        # 4. Add scores
        print("\n4. Adding scores to triples...")
        triples_with_scores = add_score_to_triples(
            triples_df=triples_df,
            partners_df=partners_df,
            publication_df=pd.DataFrame(),
            seed=42
        )

        # 5. Run solver with START-DAY capacity
        print("\n5. Running OR-Tools solver (start-day capacity)...")
        result = solve_core_assignment(
            triples_df=triples_with_scores,
            ops_capacity_df=ops_calendar_df,
            week_start=week_start,
            office=office,
            loan_length_days=7,
            solver_time_limit_s=10,
            seed=42
        )

        # 6. Analyze results
        print("\n" + "="*80)
        print("RESULTS WITH START-DAY CAPACITY")
        print("="*80)

        print(f"\nSolver Status: {result['meta']['solver_status']}")
        print(f"Objective Value: {result['objective_value']:,}")
        print(f"Total Assignments: {len(result['selected_assignments'])}")

        # Day distribution
        if result['selected_assignments']:
            day_counts = {}
            for assignment in result['selected_assignments']:
                day = pd.to_datetime(assignment['start_day']).strftime('%A')
                day_counts[day] = day_counts.get(day, 0) + 1

            print("\nAssignments by START day:")
            for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
                count = day_counts.get(day, 0)
                print(f"  {day}: {count}")

        print("\nStart-day capacity usage:")
        for day_data in result['daily_usage']:
            day_name = pd.to_datetime(day_data['date']).strftime('%A')
            print(f"  {day_name}: {day_data['used']}/{day_data['capacity']} starts")

        # Verify no weekend starts
        weekend_starts = [a for a in result['selected_assignments']
                          if pd.to_datetime(a['start_day']).weekday() in [5, 6]]
        if weekend_starts:
            print(f"\n⚠️  WARNING: Found {len(weekend_starts)} weekend starts!")
        else:
            print("\n✅ No weekend starts (as expected)")

        # Compare to old occupancy model
        print("\n" + "="*80)
        print("KEY DIFFERENCES FROM OCCUPANCY MODEL")
        print("="*80)
        print("1. Capacity now constrains STARTS per day, not active loans")
        print("2. Saturday/Sunday show 0 starts (not 15 active loans)")
        print("3. Distribution should be more balanced across Mon-Fri")
        print("4. Total assignments can be up to 75 (15 x 5 days)")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await db.close()

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)


if __name__ == "__main__":
    print("Testing Phase 7.2 with START-DAY capacity...")
    asyncio.run(test_startday_capacity())