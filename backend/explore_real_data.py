"""
Explore the real data in Supabase to understand what's available.
"""

import asyncio
import pandas as pd
from app.services.database import db_service


async def explore_data():
    """Explore what data is actually in the database."""
    print("=" * 60)
    print("Exploring REAL Supabase data")
    print("=" * 60)

    # Test connection
    connection_ok = await db_service.test_connection()
    if not connection_ok:
        print("❌ Database connection failed!")
        return

    print("✅ Database connection successful\n")

    # Explore vehicles table
    print("1. VEHICLES TABLE:")
    try:
        vehicles_response = db_service.client.table('vehicles').select('office, make, model, vin').limit(10).execute()
        if vehicles_response.data:
            vehicles_df = pd.DataFrame(vehicles_response.data)
            print(f"   Found {len(vehicles_df)} vehicles (showing first 10)")
            print(f"   Available offices: {vehicles_df['office'].unique()}")
            print(f"   Available makes: {vehicles_df['make'].unique()}")
            print("\n   Sample vehicles:")
            print(vehicles_df.head().to_string(index=False))
        else:
            print("   No vehicles found")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "-" * 40)

    # Get actual count of vehicles
    print("2. VEHICLE COUNTS BY OFFICE:")
    try:
        all_vehicles = db_service.client.table('vehicles').select('office').execute()
        if all_vehicles.data:
            office_counts = pd.DataFrame(all_vehicles.data)['office'].value_counts()
            print(office_counts.to_string())
        else:
            print("   No vehicles found")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "-" * 40)

    # Explore current_activity table
    print("3. CURRENT_ACTIVITY TABLE:")
    try:
        activity_response = db_service.client.table('current_activity').select('*').limit(5).execute()
        if activity_response.data:
            activity_df = pd.DataFrame(activity_response.data)
            print(f"   Found {len(activity_df)} activity records (showing first 5)")
            print(activity_df.head().to_string(index=False))
        else:
            print("   No current activity found")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "-" * 40)

    # Explore loan_history table
    print("4. LOAN_HISTORY TABLE:")
    try:
        loan_response = db_service.client.table('loan_history').select('person_id, make, clips_received').limit(5).execute()
        if loan_response.data:
            loan_df = pd.DataFrame(loan_response.data)
            print(f"   Found loan history records (showing first 5)")
            print(loan_df.head().to_string(index=False))

            # Check clips_received data
            all_loans = db_service.client.table('loan_history').select('clips_received').execute()
            if all_loans.data:
                clips_df = pd.DataFrame(all_loans.data)
                clips_counts = clips_df['clips_received'].value_counts(dropna=False)
                print(f"\n   Clips received distribution:")
                print(clips_counts.to_string())
        else:
            print("   No loan history found")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "-" * 40)

    # Explore approved_makes/eligibility
    print("5. APPROVED_MAKES TABLE:")
    try:
        approved_response = db_service.client.table('approved_makes').select('person_id, make, rank').limit(5).execute()
        if approved_response.data:
            approved_df = pd.DataFrame(approved_response.data)
            print(f"   Found eligibility records (showing first 5)")
            print(approved_df.head().to_string(index=False))
        else:
            print("   No approved makes found")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "-" * 40)

    # Check for any actual data combinations that would work
    print("6. DATA COMPATIBILITY CHECK:")
    try:
        # Get all available offices from vehicles
        all_vehicles_response = db_service.client.table('vehicles').select('office, make').execute()
        vehicles_by_office = {}
        if all_vehicles_response.data:
            for vehicle in all_vehicles_response.data:
                office = vehicle['office']
                make = vehicle['make']
                if office not in vehicles_by_office:
                    vehicles_by_office[office] = set()
                vehicles_by_office[office].add(make)

        # Get partner makes
        all_partners_response = db_service.client.table('approved_makes').select('make').execute()
        partner_makes = set()
        if all_partners_response.data:
            partner_makes = set([p['make'] for p in all_partners_response.data])

        print("   Vehicle makes by office:")
        for office, makes in vehicles_by_office.items():
            print(f"     {office}: {sorted(list(makes))}")

        print(f"\n   Partner approved makes: {sorted(list(partner_makes))}")

        # Find compatible office/make combinations
        print(f"\n   Compatible combinations:")
        for office, vehicle_makes in vehicles_by_office.items():
            compatible_makes = vehicle_makes.intersection(partner_makes)
            if compatible_makes:
                print(f"     {office}: {sorted(list(compatible_makes))}")

    except Exception as e:
        print(f"   Error: {e}")


if __name__ == "__main__":
    asyncio.run(explore_data())