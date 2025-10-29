"""
Test script to debug availability checking for overlapping loans.
"""
import asyncio
from app.services.database import DatabaseService
from app.etl.availability import build_availability_grid
import pandas as pd
from datetime import datetime, date

async def test_availability():
    db = DatabaseService()
    await db.initialize()

    # Test parameters
    office = "Dallas"
    week_start = "2025-10-06"  # Monday of the week with conflicts
    test_vin = "JTEVB5BR9S5000721"  # Toyota 4Runner TRD Pro

    print(f"\n{'='*80}")
    print(f"Testing availability for VIN: {test_vin}")
    print(f"Week start: {week_start}")
    print(f"Office: {office}")
    print(f"{'='*80}\n")

    # Load vehicles
    vehicles_response = db.client.table('vehicles').select('*').eq('office', office).execute()
    vehicles_df = pd.DataFrame(vehicles_response.data)

    # Load current_activity
    all_activity = []
    offset = 0
    limit = 1000
    while True:
        activity_response = db.client.table('current_activity').select('*').range(offset, offset + limit - 1).execute()
        if not activity_response.data:
            break
        all_activity.extend(activity_response.data)
        if len(activity_response.data) < limit:
            break
        offset += limit

    current_activity_df = pd.DataFrame(all_activity)

    # Rename vehicle_vin to vin for consistency
    if 'vehicle_vin' in current_activity_df.columns:
        current_activity_df = current_activity_df.rename(columns={'vehicle_vin': 'vin'})

    print(f"Total current_activity records loaded: {len(current_activity_df)}")

    # Filter to test VIN
    vin_activities = current_activity_df[current_activity_df['vin'] == test_vin]
    print(f"\nActivities for {test_vin}:")
    print(vin_activities[['activity_id', 'vin', 'activity_type', 'start_date', 'end_date', 'to_field']].to_string())

    # Build availability grid
    print(f"\n{'='*80}")
    print("Building availability grid...")
    print(f"{'='*80}\n")

    availability_df = build_availability_grid(
        vehicles_df=vehicles_df,
        activity_df=current_activity_df,
        week_start=week_start,
        office=office,
        availability_horizon_days=14,
        loan_length_days=7
    )

    # Filter to test VIN
    vin_availability = availability_df[availability_df['vin'] == test_vin].sort_values('day')

    print(f"Availability grid for {test_vin}:")
    print(vin_availability[['vin', 'day', 'available']].to_string())

    # Check specific dates
    print(f"\n{'='*80}")
    print("Checking specific dates:")
    print(f"{'='*80}\n")

    test_dates = [
        date(2025, 10, 7),   # Maria start
        date(2025, 10, 10),  # Scotty start (CONFLICT)
        date(2025, 10, 14),  # Maria end
        date(2025, 10, 17),  # Scotty end
    ]

    for test_date in test_dates:
        day_avail = vin_availability[vin_availability['day'] == test_date]
        if not day_avail.empty:
            is_available = day_avail.iloc[0]['available']
            print(f"{test_date}: {'✅ AVAILABLE' if is_available else '❌ BLOCKED'}")
        else:
            print(f"{test_date}: NOT IN GRID")

    await db.close()

if __name__ == "__main__":
    asyncio.run(test_availability())
