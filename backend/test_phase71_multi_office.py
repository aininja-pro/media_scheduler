"""
Test Phase 7.1 with multiple offices and investigate why only Monday starts.
"""

import asyncio
import pandas as pd
from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.database import DatabaseService
from app.solver.ortools_feasible_v2 import build_feasible_start_day_triples
from app.etl.availability import build_availability_grid


async def test_multiple_scenarios():
    """Test Phase 7.1 with different offices and dates."""

    db = DatabaseService()
    await db.initialize()

    # Test different offices
    test_configs = [
        {'office': 'Los Angeles', 'week_start': '2025-09-22'},
        {'office': 'Denver', 'week_start': '2025-09-22'},
        {'office': 'Chicago', 'week_start': '2025-09-22'},
        {'office': 'Los Angeles', 'week_start': '2025-10-06'},  # Different week
    ]

    results = []

    for config in test_configs:
        office = config['office']
        week_start = config['week_start']

        print(f"\n{'='*60}")
        print(f"Testing: {office}, Week: {week_start}")
        print('='*60)

        # Load vehicles for office
        vehicles_response = db.client.table('vehicles').select('*').eq('office', office).execute()
        vehicles_df = pd.DataFrame(vehicles_response.data)
        print(f"Vehicles in {office}: {len(vehicles_df)}")

        if vehicles_df.empty:
            print(f"  No vehicles in {office}, skipping")
            continue

        # Load partners for office
        partners_response = db.client.table('media_partners').select('*').eq('office', office).execute()
        partners_df = pd.DataFrame(partners_response.data)
        print(f"Partners in {office}: {len(partners_df)}")

        # Load ALL approved makes with pagination
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
        office_partner_ids = set(partners_df['person_id'].tolist())
        approved_office = approved_df[approved_df['person_id'].isin(office_partner_ids)]
        print(f"Approved makes for {office} partners: {len(approved_office)}")

        # Build availability
        activity_response = db.client.table('current_activity').select('*').execute()
        activity_df = pd.DataFrame(activity_response.data)
        if 'vehicle_vin' in activity_df.columns:
            activity_df = activity_df.rename(columns={'vehicle_vin': 'vin'})

        availability_df = build_availability_grid(
            vehicles_df=vehicles_df,
            activity_df=activity_df,
            week_start=week_start,
            office=office
        )
        availability_df = availability_df.rename(columns={'day': 'date'})

        # Check availability patterns
        print("\nAvailability Analysis:")
        for i in range(5):  # Check Mon-Fri
            target_date = pd.to_datetime(week_start) + pd.Timedelta(days=i)
            day_name = target_date.strftime('%A')

            # Check how many vehicles are available for 7 days starting from this day
            vins_available = []
            for vin in vehicles_df['vin'].unique():
                vin_avail = availability_df[availability_df['vin'] == vin]
                dates_needed = pd.date_range(target_date, periods=7)

                available_count = 0
                for date in dates_needed:
                    if any((vin_avail['date'] == date) & (vin_avail['available'] == True)):
                        available_count += 1

                if available_count >= 7:
                    vins_available.append(vin)

            print(f"  {day_name}: {len(vins_available)} vehicles available for 7 days")

        # Load capacity calendar
        ops_cal_response = db.client.table('ops_capacity_calendar').select('*').execute()
        ops_calendar_df = pd.DataFrame(ops_cal_response.data)

        # Check capacity for the week
        print("\nCapacity for this week:")
        week_dates = pd.date_range(week_start, periods=5)
        for date in week_dates:
            day_cap = ops_calendar_df[
                (ops_calendar_df['office'] == office) &
                (pd.to_datetime(ops_calendar_df['date']).dt.date == date.date())
            ]
            if not day_cap.empty:
                slots = day_cap.iloc[0]['slots']
            else:
                slots = 15  # default
            print(f"  {date.strftime('%A %Y-%m-%d')}: {slots} slots")

        # Load model taxonomy
        taxonomy_response = db.client.table('model_taxonomy').select('*').execute()
        taxonomy_df = pd.DataFrame(taxonomy_response.data)

        # Build feasible triples
        triples_df = build_feasible_start_day_triples(
            vehicles_df=vehicles_df,
            partners_df=partners_df,
            availability_df=availability_df,
            approved_makes_df=approved_office,
            week_start=week_start,
            office=office,
            ops_capacity_df=ops_calendar_df,
            model_taxonomy_df=taxonomy_df,
            start_days=['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
            min_available_days=7,
            default_slots_per_day=15
        )

        # Analyze results
        if not triples_df.empty:
            start_day_counts = pd.to_datetime(triples_df['start_day']).dt.day_name().value_counts()

            result = {
                'office': office,
                'week': week_start,
                'total_triples': len(triples_df),
                'unique_vehicles': triples_df['vin'].nunique(),
                'unique_partners': triples_df['person_id'].nunique(),
                'start_days': dict(start_day_counts)
            }
        else:
            result = {
                'office': office,
                'week': week_start,
                'total_triples': 0,
                'reason': 'No feasible triples generated'
            }

        results.append(result)
        print(f"\nResult: {result}")

    # Summary
    print("\n" + "="*80)
    print("SUMMARY OF ALL TESTS")
    print("="*80)

    for result in results:
        print(f"\n{result['office']} - Week {result['week']}:")
        if result['total_triples'] > 0:
            print(f"  Total: {result['total_triples']} triples")
            print(f"  Vehicles: {result['unique_vehicles']}, Partners: {result['unique_partners']}")
            print(f"  Start days: {result.get('start_days', {})}")
        else:
            print(f"  {result.get('reason', 'No triples')}")

    await db.close()


if __name__ == "__main__":
    asyncio.run(test_multiple_scenarios())