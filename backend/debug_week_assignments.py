"""
Debug why the same assignments appear regardless of week selected.
"""

import asyncio
import pandas as pd
from datetime import datetime, timedelta
from app.services.database import db_service
from app.etl.availability import build_availability_grid


async def debug_week_assignments():
    """Check what's happening with different week selections."""

    await db_service.initialize()

    office = 'Los Angeles'

    # Test with multiple different weeks
    test_weeks = [
        '2024-09-16',  # Current week
        '2024-09-23',  # Next week
        '2024-09-30',  # Week after
        '2024-10-07',  # October week
    ]

    print(f"\n{'='*80}")
    print(f"DEBUGGING WEEK-BASED ASSIGNMENTS FOR {office}")
    print(f"{'='*80}\n")

    # Load data once
    vehicles_response = db_service.client.table('vehicles').select('*').eq('office', office).execute()
    vehicles_df = pd.DataFrame(vehicles_response.data) if vehicles_response.data else pd.DataFrame()

    activity_response = db_service.client.table('current_activity').select('*').execute()
    activity_df = pd.DataFrame(activity_response.data) if activity_response.data else pd.DataFrame()

    if 'vehicle_vin' in activity_df.columns:
        activity_df['vin'] = activity_df['vehicle_vin']

    # Convert dates
    for date_col in ['in_service_date', 'expected_turn_in_date']:
        if date_col in vehicles_df.columns:
            vehicles_df[date_col] = pd.to_datetime(vehicles_df[date_col], errors='coerce').dt.date

    if not activity_df.empty:
        for date_col in ['start_date', 'end_date']:
            if date_col in activity_df.columns:
                activity_df[date_col] = pd.to_datetime(activity_df[date_col], errors='coerce').dt.date

    print(f"Total vehicles in {office}: {len(vehicles_df)}")
    print(f"Total current activities: {len(activity_df)}")

    # Check each week
    for week_start in test_weeks:
        print(f"\n{'-'*60}")
        print(f"WEEK: {week_start}")
        print(f"{'-'*60}")

        # Build availability grid for this week
        availability_grid = build_availability_grid(
            vehicles_df=vehicles_df,
            activity_df=activity_df,
            week_start=week_start,
            office=office
        )

        if availability_grid.empty:
            print(f"  ❌ No availability grid generated")
            continue

        # Count available vehicles per day
        week_start_date = pd.to_datetime(week_start).date()
        week_dates = [week_start_date + timedelta(days=i) for i in range(7)]

        print(f"  Availability by day:")
        for date in week_dates:
            day_availability = availability_grid[availability_grid['day'] == date]
            available_count = day_availability['available'].sum() if not day_availability.empty else 0
            print(f"    {date.strftime('%a %Y-%m-%d')}: {available_count} vehicles available")

        # Count vehicles available for entire week
        vehicles_available_all_week = []
        for vin in availability_grid['vin'].unique():
            vin_data = availability_grid[availability_grid['vin'] == vin]
            days_available = vin_data['available'].sum()
            if days_available >= 5:  # Default min_available_days
                vehicles_available_all_week.append(vin)

        print(f"\n  Vehicles available ≥5 days: {len(vehicles_available_all_week)}")

        # Check current activities affecting this week
        if not activity_df.empty:
            week_end_date = week_start_date + timedelta(days=6)

            # Activities overlapping with this week
            overlapping_activities = activity_df[
                (activity_df['start_date'] <= week_end_date) &
                (activity_df['end_date'] >= week_start_date)
            ]

            print(f"  Active loans during week: {len(overlapping_activities)}")
            if len(overlapping_activities) > 0:
                print(f"  VINs on loan: {list(overlapping_activities['vin'].unique())[:5]}...")

    # Check loan history for cooldown
    print(f"\n{'='*80}")
    print(f"CHECKING COOLDOWN IMPACTS")
    print(f"{'='*80}\n")

    loan_history_response = db_service.client.table('loan_history').select('*').execute()
    loan_history_df = pd.DataFrame(loan_history_response.data) if loan_history_response.data else pd.DataFrame()

    if not loan_history_df.empty:
        loan_history_df['end_date'] = pd.to_datetime(loan_history_df['end_date'], errors='coerce').dt.date

        # Check recent loans (within 30 days of each test week)
        for week_start in test_weeks:
            week_start_date = pd.to_datetime(week_start).date()
            cooldown_start = week_start_date - timedelta(days=30)

            recent_loans = loan_history_df[
                (loan_history_df['end_date'] >= cooldown_start) &
                (loan_history_df['end_date'] < week_start_date)
            ]

            print(f"Week {week_start}: {len(recent_loans)} loans in cooldown period")

            if len(recent_loans) > 0:
                # Count unique partner-make combinations in cooldown
                cooldown_combos = recent_loans.groupby(['person_id', 'make']).size()
                print(f"  Unique partner-make combos in cooldown: {len(cooldown_combos)}")

    await db_service.close()
    print(f"\n✅ Debug complete")


if __name__ == "__main__":
    asyncio.run(debug_week_assignments())