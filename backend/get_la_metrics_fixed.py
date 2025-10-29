"""
Fixed script with proper pagination to extract key metrics for Los Angeles, Sept 22nd week
"""

import asyncio
import pandas as pd
from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.database import DatabaseService
from app.solver.ortools_feasible_v2 import build_feasible_start_day_triples
from app.solver.cooldown_filter import apply_cooldown_filter
from app.etl.availability import build_availability_grid

async def get_la_metrics_fixed():
    """Get key metrics for LA scheduling with proper pagination."""
    print("="*60)
    print("LOS ANGELES METRICS - Week of Sept 22, 2025")
    print("(WITH PAGINATION FIXES)")
    print("="*60)

    db = DatabaseService()
    await db.initialize()

    try:
        week_start = '2025-09-22'
        office = 'Los Angeles'
        week_start_date = pd.to_datetime(week_start)

        # 1. VEHICLES
        print("\n📊 VEHICLES")
        vehicles_response = db.client.table('vehicles').select('*').eq('office', office).execute()
        vehicles_df = pd.DataFrame(vehicles_response.data)
        print(f"  Total vehicles in {office}: {len(vehicles_df)}")

        # By make
        if not vehicles_df.empty:
            make_counts = vehicles_df['make'].value_counts().head(5)
            print("\n  Top 5 makes:")
            for make, count in make_counts.items():
                print(f"    {make}: {count}")

        # 2. MEDIA PARTNERS
        print("\n👥 MEDIA PARTNERS")
        partners_response = db.client.table('media_partners').select('*').eq('office', office).execute()
        partners_df = pd.DataFrame(partners_response.data)
        print(f"  Total partners in {office}: {len(partners_df)}")

        # 3. CURRENT ACTIVITY - WITH PAGINATION!
        print("\n📅 CURRENT ACTIVITY (WITH PAGINATION)")
        all_activity = []
        offset = 0
        limit = 1000
        page = 1

        while True:
            print(f"  Fetching page {page} (offset {offset})...")
            activity_response = db.client.table('current_activity').select('*').range(offset, offset + limit - 1).execute()

            if not activity_response.data:
                break

            all_activity.extend(activity_response.data)
            print(f"    Got {len(activity_response.data)} records")

            if len(activity_response.data) < limit:
                break

            offset += limit
            page += 1

        current_activity_df = pd.DataFrame(all_activity) if all_activity else pd.DataFrame()
        print(f"\n  ✓ Total activity records fetched: {len(current_activity_df)}")

        if 'vehicle_vin' in current_activity_df.columns:
            current_activity_df = current_activity_df.rename(columns={'vehicle_vin': 'vin'})

        # Filter to LA vehicles
        la_vins = set(vehicles_df['vin'].tolist())
        la_activity = current_activity_df[current_activity_df['vin'].isin(la_vins)]

        print(f"  LA activity records: {len(la_activity)}")

        if not la_activity.empty and 'activity_type' in la_activity.columns:
            activity_types = la_activity['activity_type'].value_counts()
            print("\n  Activity types:")
            for atype, count in activity_types.items():
                print(f"    {atype}: {count}")

        # 4. AVAILABILITY - NOW WITH PROPER DATA
        print("\n✅ AVAILABILITY CALCULATION")
        print("\n  How availability is calculated:")
        print("  1. For each vehicle in the office:")
        print("     - Check if date is within vehicle lifecycle (in_service to turn_in)")
        print("     - Check if vehicle has blocking activity on that date")
        print("  2. Vehicle is available if:")
        print("     - Within lifecycle window AND")
        print("     - No overlapping loan/service/hold/event/storage")

        availability_df = build_availability_grid(
            vehicles_df=vehicles_df,
            activity_df=current_activity_df,  # Now has ALL records!
            week_start=week_start,
            office=office
        )

        if 'day' in availability_df.columns:
            availability_df = availability_df.rename(columns={'day': 'date'})

        # Count available vehicles per day
        if not availability_df.empty:
            # Group by date and sum available (True=1, False=0)
            availability_df['available_count'] = availability_df['available'].astype(int)
            daily_avail = availability_df.groupby('date')['available_count'].sum()

            print("\n  Available vehicles by day:")
            for day in pd.date_range(week_start_date, periods=7):
                day_str = day.strftime('%Y-%m-%d')
                avail_count = daily_avail.get(day.date(), 0)
                print(f"    {day.strftime('%a %m/%d')}: {avail_count} vehicles")

            # Show some available VINs as proof
            avail_vins = availability_df[
                (availability_df['date'] == week_start_date.date()) &
                (availability_df['available'] == True)
            ]['vin'].head(5).tolist()

            if avail_vins:
                print(f"\n  Example available VINs for Monday: {', '.join(avail_vins[:3])}")

        # 5. APPROVED MAKES - WITH PAGINATION
        print("\n🚗 APPROVED MAKES (WITH PAGINATION)")
        all_approved = []
        offset = 0
        limit = 1000
        page = 1

        while True:
            print(f"  Fetching page {page}...")
            approved_response = db.client.table('approved_makes').select('*').range(offset, offset + limit - 1).execute()

            if not approved_response.data:
                break

            all_approved.extend(approved_response.data)

            if len(approved_response.data) < limit:
                break

            offset += limit
            page += 1

        approved_makes_df = pd.DataFrame(all_approved)
        print(f"  ✓ Total approved makes records: {len(approved_makes_df)}")

        # Filter to LA partners
        la_partner_ids = set(partners_df['person_id'].tolist())
        la_approved = approved_makes_df[approved_makes_df['person_id'].isin(la_partner_ids)]

        print(f"  LA approved makes: {len(la_approved)}")

        if not la_approved.empty:
            rank_counts = la_approved['rank'].value_counts()
            print("\n  Rank distribution:")
            for rank, count in rank_counts.items():
                print(f"    {rank}: {count}")

        # 6. OPS CAPACITY
        print("\n🏭 OPS CAPACITY")
        ops_response = db.client.table('ops_capacity_calendar').select('*').execute()
        ops_capacity_df = pd.DataFrame(ops_response.data)

        if not ops_capacity_df.empty:
            # Filter to week of Sept 22
            ops_capacity_df['date'] = pd.to_datetime(ops_capacity_df['date'])
            week_end = week_start_date + timedelta(days=6)
            week_capacity = ops_capacity_df[
                (ops_capacity_df['date'] >= week_start_date) &
                (ops_capacity_df['date'] <= week_end) &
                (ops_capacity_df['office'] == office)
            ]

            print(f"\n  Capacity for week of {week_start}:")
            for _, row in week_capacity.iterrows():
                date_str = row['date'].strftime('%a %m/%d')
                slots = row.get('slots', 0)
                notes = row.get('notes', '')
                if notes:
                    print(f"    {date_str}: {slots} slots ({notes})")
                else:
                    print(f"    {date_str}: {slots} slots")

        # 7. LOAN HISTORY - WITH PAGINATION
        print("\n📚 LOAN HISTORY (WITH PAGINATION)")
        all_loan_history = []
        offset = 0
        limit = 1000
        page = 1

        while True:
            print(f"  Fetching page {page}...")
            loan_response = db.client.table('loan_history').select('*').range(offset, offset + limit - 1).execute()

            if not loan_response.data:
                break

            all_loan_history.extend(loan_response.data)

            if len(loan_response.data) < limit:
                break

            offset += limit
            page += 1

        loan_history_df = pd.DataFrame(all_loan_history) if all_loan_history else pd.DataFrame()
        print(f"  ✓ Total loan history records: {len(loan_history_df)}")

        # Rules
        rules_response = db.client.table('rules').select('*').execute()
        rules_df = pd.DataFrame(rules_response.data)

        # 8. FEASIBLE TRIPLES
        print("\n🎯 FEASIBLE TRIPLES GENERATION")
        print("  Generating all possible (vehicle, partner, start_day) combinations...")

        # Generate feasible triples
        triples_df = build_feasible_start_day_triples(
            vehicles_df=vehicles_df,
            partners_df=partners_df,
            availability_df=availability_df,
            approved_makes_df=la_approved,
            week_start=week_start,
            office=office
        )

        print(f"\n  ✓ Feasible triples generated: {len(triples_df):,}")

        if not triples_df.empty:
            # Unique counts
            unique_vins = triples_df['vin'].nunique()
            unique_partners = triples_df['person_id'].nunique()
            unique_days = triples_df['start_day'].nunique()

            print(f"\n  Coverage:")
            print(f"    Unique vehicles: {unique_vins}")
            print(f"    Unique partners: {unique_partners}")
            print(f"    Unique start days: {unique_days}")

            # Apply cooldown filter
            print("\n  Applying cooldown filter...")
            filtered_triples = apply_cooldown_filter(
                feasible_triples_df=triples_df,
                loan_history_df=loan_history_df,
                rules_df=rules_df,
                default_cooldown_days=30
            )

            removed = len(triples_df) - len(filtered_triples)
            pct_removed = (removed / len(triples_df) * 100) if len(triples_df) > 0 else 0

            print(f"  ✓ After cooldown filter: {len(filtered_triples):,}")
            print(f"    Removed: {removed:,} ({pct_removed:.1f}%)")

        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"  Office: {office}")
        print(f"  Week: Sept 22-28, 2025")
        print(f"  Vehicles: {len(vehicles_df)}")
        print(f"  Partners: {len(partners_df)}")
        print(f"  Current Activities (paginated): {len(current_activity_df)}")
        print(f"  Loan History (paginated): {len(loan_history_df)}")
        print(f"  Approved Makes (paginated): {len(approved_makes_df)}")
        print(f"  Feasible triples: {len(triples_df):,}")
        print(f"  After cooldown: {len(filtered_triples):,}")

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(get_la_metrics_fixed())