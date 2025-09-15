"""
Real data integration test for candidate generation.

This script connects to Supabase and tests build_weekly_candidates against actual ETL data.
"""

import asyncio
import pandas as pd
import time
from datetime import datetime, timedelta
from typing import Dict, Any

from app.solver.candidates import build_weekly_candidates
from app.services.database import db_service


async def fetch_availability_data(office: str = "SEA", week_start: str = "2024-01-08") -> pd.DataFrame:
    """
    Fetch availability data from the database.

    This simulates the availability ETL output using real vehicle and activity data.
    """
    print(f"Fetching availability data for {office}, week starting {week_start}...")

    try:
        # Get vehicles for the office
        vehicles_response = db_service.client.table('vehicles').select(
            'vin, make, model, office'
        ).eq('office', office).execute()

        if not vehicles_response.data:
            print(f"No vehicles found for office {office}")
            return pd.DataFrame()

        vehicles_df = pd.DataFrame(vehicles_response.data)
        print(f"Found {len(vehicles_df)} vehicles for {office}")

        # Get current activity data to determine availability
        activity_response = db_service.client.table('current_activity').select(
            'vehicle_vin, activity_type, start_date, end_date'
        ).execute()

        activity_df = pd.DataFrame(activity_response.data) if activity_response.data else pd.DataFrame()
        print(f"Found {len(activity_df)} activity records")

        # Generate week dates
        week_start_date = pd.to_datetime(week_start).date()
        week_dates = [(week_start_date + timedelta(days=i)) for i in range(7)]

        # Build availability data
        availability_data = []

        for _, vehicle in vehicles_df.iterrows():
            vin = vehicle['vin']
            make = vehicle['make']
            model = vehicle['model']
            market = vehicle['office']  # office = market

            for date in week_dates:
                # Check if vehicle is blocked by any activity on this date
                blocked = False

                if not activity_df.empty:
                    vehicle_activities = activity_df[activity_df['vehicle_vin'] == vin]

                    for _, activity in vehicle_activities.iterrows():
                        start_date = pd.to_datetime(activity['start_date']).date()
                        end_date = pd.to_datetime(activity['end_date']).date()

                        if start_date <= date <= end_date:
                            activity_type = activity.get('activity_type', '').lower()
                            # Block if it's a loan, service, or hold
                            if activity_type in ['loan', 'service', 'hold']:
                                blocked = True
                                break

                availability_data.append({
                    'vin': vin,
                    'date': date.strftime('%Y-%m-%d'),
                    'market': market,
                    'make': make,
                    'model': model,
                    'available': not blocked
                })

        availability_df = pd.DataFrame(availability_data)
        print(f"Generated {len(availability_df)} availability records")

        return availability_df

    except Exception as e:
        print(f"Error fetching availability data: {e}")
        return pd.DataFrame()


async def fetch_cooldown_data() -> pd.DataFrame:
    """
    Fetch cooldown data from the database.

    This simulates the cooldown ETL output using real loan history and rules.
    """
    print("Fetching cooldown data...")

    try:
        # Get loan history to compute cooldowns
        loan_history_response = db_service.client.table('loan_history').select(
            'person_id, make, model, start_date, end_date'
        ).order('end_date', desc=True).execute()

        loan_history_df = pd.DataFrame(loan_history_response.data) if loan_history_response.data else pd.DataFrame()
        print(f"Found {len(loan_history_df)} loan history records")

        # Get rules for cooldown periods
        rules_response = db_service.client.table('rules').select(
            'make, cooldown_period'
        ).execute()

        rules_df = pd.DataFrame(rules_response.data) if rules_response.data else pd.DataFrame()
        print(f"Found {len(rules_df)} rules records")

        if loan_history_df.empty:
            print("No loan history data found")
            return pd.DataFrame()

        # For simplicity, assume 60-day cooldown for all makes if no rules
        default_cooldown_days = 60
        cooldown_data = []

        # Get unique partner-make combinations
        partner_makes = loan_history_df.groupby(['person_id', 'make']).agg({
            'end_date': 'max'  # Get most recent loan end date
        }).reset_index()

        today = pd.Timestamp.now().date()

        for _, row in partner_makes.iterrows():
            person_id = row['person_id']
            make = row['make']
            last_end_date = pd.to_datetime(row['end_date']).date()

            # Get cooldown period for this make
            make_rules = rules_df[rules_df['make'] == make]
            cooldown_days = make_rules['cooldown_period'].iloc[0] if not make_rules.empty else default_cooldown_days

            # Check if cooldown has expired
            days_since_last_loan = (today - last_end_date).days
            cooldown_ok = days_since_last_loan >= cooldown_days

            # Add entries for different models of this make
            make_models = loan_history_df[
                (loan_history_df['person_id'] == person_id) &
                (loan_history_df['make'] == make)
            ]['model'].unique()

            for model in make_models:
                cooldown_data.append({
                    'person_id': person_id,
                    'make': make,
                    'model': model,
                    'cooldown_ok': cooldown_ok
                })

        cooldown_df = pd.DataFrame(cooldown_data)
        print(f"Generated {len(cooldown_df)} cooldown records")

        return cooldown_df

    except Exception as e:
        print(f"Error fetching cooldown data: {e}")
        return pd.DataFrame()


async def fetch_publication_data() -> pd.DataFrame:
    """
    Fetch publication rate data from the database.

    This uses the publication rate ETL output from Phase 4.
    """
    print("Fetching publication data...")

    try:
        # Get loan history with clips_received data
        loan_history_response = db_service.client.table('loan_history').select(
            'person_id, make, start_date, end_date, clips_received'
        ).execute()

        loan_history_df = pd.DataFrame(loan_history_response.data) if loan_history_response.data else pd.DataFrame()
        print(f"Found {len(loan_history_df)} loan history records")

        if loan_history_df.empty:
            return pd.DataFrame()

        # Simulate the publication rate calculation from Phase 4
        # (In production, this would call the actual ETL function)
        publication_data = []

        # Group by person_id and make
        for (person_id, make), group in loan_history_df.groupby(['person_id', 'make']):
            total_loans = len(group)

            # Count clips where we have data
            clips_data = group.dropna(subset=['clips_received'])
            observed_loans = len(clips_data)

            if observed_loans > 0:
                publications = clips_data['clips_received'].sum()
                publication_rate = publications / total_loans
                coverage = observed_loans / total_loans
                supported = observed_loans >= 3  # Min threshold for supported
            else:
                publication_rate = None
                coverage = 0.0
                supported = False
                publications = 0

            publication_data.append({
                'person_id': person_id,
                'make': make,
                'loans_total_24m': total_loans,
                'loans_observed_24m': observed_loans,
                'publications_observed_24m': publications,
                'publication_rate_observed': publication_rate,
                'coverage': coverage,
                'supported': supported
            })

        publication_df = pd.DataFrame(publication_data)
        print(f"Generated {len(publication_df)} publication rate records")

        return publication_df

    except Exception as e:
        print(f"Error fetching publication data: {e}")
        return pd.DataFrame()


async def fetch_eligibility_data() -> pd.DataFrame:
    """Fetch partner eligibility data from approved_makes table."""
    print("Fetching eligibility data...")

    try:
        eligibility_response = db_service.client.table('approved_makes').select(
            'person_id, make, rank'
        ).execute()

        eligibility_df = pd.DataFrame(eligibility_response.data) if eligibility_response.data else pd.DataFrame()
        print(f"Found {len(eligibility_df)} eligibility records")

        return eligibility_df

    except Exception as e:
        print(f"Error fetching eligibility data: {e}")
        return pd.DataFrame()


async def test_real_data_integration():
    """Main test function for real data integration."""
    print("=" * 60)
    print("Testing build_weekly_candidates with REAL Supabase data")
    print("=" * 60)

    # Test database connection
    print("\n1. Testing database connection...")
    connection_ok = await db_service.test_connection()
    if not connection_ok:
        print("❌ Database connection failed!")
        return
    print("✅ Database connection successful")

    # Fetch all required data
    print("\n2. Fetching ETL data...")

    # Use current week Monday
    today = datetime.now()
    days_since_monday = today.weekday()  # Monday = 0
    current_monday = (today - timedelta(days=days_since_monday)).date()
    week_start = current_monday.strftime('%Y-%m-%d')

    office = "Los Angeles"  # Test with LA office (has most vehicles: 225)

    # Fetch all data in parallel for better performance
    availability_df, cooldown_df, publication_df, eligibility_df = await asyncio.gather(
        fetch_availability_data(office, week_start),
        fetch_cooldown_data(),
        fetch_publication_data(),
        fetch_eligibility_data()
    )

    # Validate we have data
    if availability_df.empty:
        print("❌ No availability data found")
        return

    if cooldown_df.empty:
        print("❌ No cooldown data found")
        return

    if publication_df.empty:
        print("❌ No publication data found")
        return

    print(f"✅ Data fetched successfully:")
    print(f"   - Availability: {len(availability_df)} records")
    print(f"   - Cooldown: {len(cooldown_df)} records")
    print(f"   - Publication: {len(publication_df)} records")
    print(f"   - Eligibility: {len(eligibility_df)} records")

    # Test candidate generation
    print(f"\n3. Generating candidates for {office}, week of {week_start}...")

    start_time = time.time()

    result = build_weekly_candidates(
        availability_df=availability_df,
        cooldown_df=cooldown_df,
        publication_df=publication_df,
        week_start=week_start,
        eligibility_df=eligibility_df if not eligibility_df.empty else None,
        min_available_days=5  # Relaxed for testing
    )

    end_time = time.time()
    execution_time = end_time - start_time

    print(f"\n4. Results:")
    print(f"   - Generated {len(result):,} candidate pairs")
    print(f"   - Execution time: {execution_time:.3f} seconds")
    print(f"   - Performance: {len(result)/execution_time:.0f} candidates/second")

    if len(result) > 0:
        print(f"\n5. Sample candidates (first 5):")
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        print(result.head().to_string(index=False))

        # Analyze the results
        print(f"\n6. Analysis:")
        print(f"   - Unique VINs: {result['vin'].nunique()}")
        print(f"   - Unique partners: {result['person_id'].nunique()}")
        print(f"   - Unique makes: {result['make'].nunique()}")
        print(f"   - Average available days: {result['available_days'].mean():.1f}")
        print(f"   - Candidates with publication data: {result['publication_rate_observed'].notna().sum()}")

        # Top makes by candidate count
        make_counts = result['make'].value_counts()
        print(f"   - Top makes by candidates: {dict(make_counts.head(3))}")

        print(f"\n✅ Real data test completed successfully!")

    else:
        print("❌ No candidates generated - check data constraints")

        # Debug information
        print("\nDebugging info:")
        unique_vins = availability_df[availability_df['available'] == True].groupby('vin')['date'].count()
        sufficient_availability = unique_vins[unique_vins >= 5]
        print(f"   - VINs with ≥5 available days: {len(sufficient_availability)}")

        if not sufficient_availability.empty:
            cooldown_ok_count = cooldown_df[cooldown_df['cooldown_ok'] == True].shape[0]
            print(f"   - Partners not in cooldown: {cooldown_ok_count}")

    return result


async def main():
    """Run the real data integration test."""
    try:
        result = await test_real_data_integration()
        return result
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    result = asyncio.run(main())