"""
Test partner availability grid with REAL database data.
"""

import sys
from app.services.database import DatabaseService
import pandas as pd
from app.chain_builder.availability import (
    build_partner_availability_grid,
    check_partner_slot_availability
)


def test_with_real_data():
    """Test partner availability with real database data"""

    print("\n=== Testing Partner Availability Grid with REAL DATA ===\n")

    db = DatabaseService()

    try:
        # 1. Load real data
        print("Step 1: Loading real data...")

        partners_response = db.client.table('media_partners').select('*').eq('office', 'Los Angeles').execute()
        partners_df = pd.DataFrame(partners_response.data) if partners_response.data else pd.DataFrame()
        print(f"  ✓ Loaded {len(partners_df)} LA partners")

        current_activity_response = db.client.table('current_activity').select('*').execute()
        current_activity_df = pd.DataFrame(current_activity_response.data) if current_activity_response.data else pd.DataFrame()
        print(f"  ✓ Loaded {len(current_activity_df)} current activity records")

        scheduled_response = db.client.table('scheduled_assignments').select('*').execute()
        scheduled_df = pd.DataFrame(scheduled_response.data) if scheduled_response.data else pd.DataFrame()
        print(f"  ✓ Loaded {len(scheduled_df)} scheduled assignments")
        print()

        # 2. Build availability grid for a date range
        print("Step 2: Building partner availability grid (Nov 1-30, 2025)...")

        availability_df = build_partner_availability_grid(
            partners_df=partners_df,
            current_activity_df=current_activity_df,
            scheduled_assignments_df=scheduled_df,
            start_date='2025-11-01',
            end_date='2025-11-30',
            office='Los Angeles'
        )

        print(f"  ✓ Created availability grid: {len(availability_df)} partner-day records")

        if not availability_df.empty:
            total_slots = len(availability_df)
            available_slots = availability_df['available'].sum()
            unavailable_slots = total_slots - available_slots

            print(f"  ✓ Available: {available_slots}/{total_slots} partner-days ({available_slots/total_slots*100:.1f}%)")
            print(f"  ✓ Busy: {unavailable_slots} partner-days")
        print()

        # 3. Test specific partner slot availability
        print("Step 3: Checking specific partner for 8-day slot...")

        # Get a real partner
        if not partners_df.empty:
            test_partner = partners_df.iloc[0]
            test_partner_id = int(test_partner['person_id'])
            test_partner_name = test_partner['name']

            # Check if they're available Nov 3-11 (8 days)
            slot_check = check_partner_slot_availability(
                person_id=test_partner_id,
                slot_start='2025-11-03',
                slot_end='2025-11-11',
                availability_df=availability_df
            )

            print(f"  Partner: {test_partner_name} (ID: {test_partner_id})")
            print(f"  Slot: Nov 3-11, 2025 (8 days)")
            print(f"  ✓ Available: {slot_check['available']}")
            print(f"  ✓ Days available: {slot_check['days_available']}/{slot_check['days_required']}")

            if not slot_check['available']:
                print(f"  ✓ Reason: {slot_check['reason']}")
                if slot_check['unavailable_dates']:
                    print(f"  ✓ Busy dates: {slot_check['unavailable_dates'][:3]}...")
        print()

        # 4. Find partners with current activity
        print("Step 4: Finding partners with active loans...")

        if not current_activity_df.empty:
            busy_partners = current_activity_df['person_id'].unique()[:5]
            print(f"  Found {len(current_activity_df['person_id'].unique())} partners with active loans")

            for partner_id in busy_partners:
                partner = partners_df[partners_df['person_id'] == partner_id]
                if not partner.empty:
                    partner_name = partner.iloc[0]['name']

                    # Get their activity
                    activity = current_activity_df[current_activity_df['person_id'] == partner_id].iloc[0]
                    print(f"  • {partner_name}: {activity.get('start_date')} to {activity.get('end_date')}")
        print()

        # 5. Count available partners per day
        print("Step 5: Availability by date (sample)...")

        if not availability_df.empty:
            # Group by date, count available
            daily_avail = availability_df.groupby('date')['available'].agg(['sum', 'count'])
            daily_avail.columns = ['available_partners', 'total_partners']

            print("  Sample dates:")
            for date in daily_avail.head(7).index:
                row = daily_avail.loc[date]
                print(f"    {date}: {int(row['available_partners'])}/{int(row['total_partners'])} partners available")
        print()

        print("=== All Partner Availability Tests Passed! ✓ ===\n")

    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    test_with_real_data()
