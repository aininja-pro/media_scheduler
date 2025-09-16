"""
Check exactly what data we're pulling from Supabase and if it's complete.
"""

import asyncio
import pandas as pd
from app.services.database import db_service


async def audit_data_usage():
    """Audit what data we're actually pulling vs what exists."""

    print("=" * 80)
    print("SUPABASE DATA USAGE AUDIT")
    print("=" * 80)

    tables_to_check = [
        'vehicles', 'approved_makes', 'loan_history', 'media_partners',
        'rules', 'ops_capacity', 'current_activity'
    ]

    for table in tables_to_check:
        print(f"\n{table.upper()} TABLE:")

        try:
            # Get total count
            total_response = db_service.client.table(table).select('*', count='exact').execute()
            total_count = total_response.count

            # Get what we actually fetch in our ETL functions
            if table == 'loan_history':
                # Check our ETL fetch patterns
                print(f"   📊 Total records in DB: {total_count:,}")

                # Pattern 1: Our ETL publication endpoint (limit 1000 with pagination)
                pub_fetch = db_service.client.table(table).select('*').limit(1000).execute()
                pub_count = len(pub_fetch.data) if pub_fetch.data else 0
                print(f"   📥 Publication ETL fetches: {pub_count:,} (first 1000)")

                # Pattern 2: Our greedy assignment fetch (limit 5000)
                greedy_fetch = db_service.client.table(table).select('person_id, make, start_date, end_date').order('created_at', desc=True).limit(5000).execute()
                greedy_count = len(greedy_fetch.data) if greedy_fetch.data else 0
                print(f"   📥 Greedy assignment fetches: {greedy_count:,} (latest 5000)")

                # Check if we're missing data
                if total_count > 5000:
                    missing_count = total_count - 5000
                    missing_pct = (missing_count / total_count) * 100
                    print(f"   ⚠️  Missing {missing_count:,} records ({missing_pct:.1f}%) in greedy assignment")

            elif table == 'approved_makes':
                print(f"   📊 Total records: {total_count:,}")
                fetch_response = db_service.client.table(table).select('*').execute()
                fetch_count = len(fetch_response.data) if fetch_response.data else 0
                print(f"   📥 We fetch: {fetch_count:,} (all records)")

                if fetch_count < total_count:
                    print(f"   ⚠️  Missing {total_count - fetch_count:,} approved_makes records!")

            elif table == 'vehicles':
                print(f"   📊 Total records: {total_count:,}")
                # Check LA specifically
                la_response = db_service.client.table(table).select('*').eq('office', 'Los Angeles').execute()
                la_count = len(la_response.data) if la_response.data else 0
                print(f"   📥 Los Angeles vehicles: {la_count:,}")

            else:
                print(f"   📊 Total records: {total_count:,}")
                fetch_response = db_service.client.table(table).select('*').execute()
                fetch_count = len(fetch_response.data) if fetch_response.data else 0
                print(f"   📥 We fetch: {fetch_count:,}")

                if fetch_count < total_count:
                    print(f"   ⚠️  Missing {total_count - fetch_count:,} records!")

        except Exception as e:
            print(f"   ❌ Error checking {table}: {e}")

    # Specific analysis for our test case
    print(f"\n" + "="*50)
    print("LOS ANGELES 9/22 CANDIDATE ANALYSIS")
    print("="*50)

    # Get LA vehicles and their makes
    la_vehicles = db_service.client.table('vehicles').select('vin, make').eq('office', 'Los Angeles').execute()
    la_vehicle_makes = set([v['make'] for v in la_vehicles.data]) if la_vehicles.data else set()

    print(f"LA vehicle makes: {sorted(la_vehicle_makes)}")

    # Get partners approved for LA makes
    if la_vehicle_makes:
        la_approved = db_service.client.table('approved_makes').select('person_id, make, rank').in_('make', list(la_vehicle_makes)).execute()
        la_approved_df = pd.DataFrame(la_approved.data) if la_approved.data else pd.DataFrame()

        print(f"Partners approved for LA makes: {len(la_approved_df):,}")

        # Show breakdown by make
        if not la_approved_df.empty:
            make_counts = la_approved_df['make'].value_counts()
            print(f"Approved partners by make:")
            for make, count in make_counts.head(10).items():
                print(f"   {make}: {count} partners")

        # Calculate theoretical candidate universe
        theoretical_candidates = len(la_vehicles.data) * len(la_approved_df) if la_vehicles.data and not la_approved_df.empty else 0
        print(f"\nTheoretical max candidates: {len(la_vehicles.data)} vehicles × {len(la_approved_df)} partner-make pairs = {theoretical_candidates:,}")

    print(f"\n✅ Data audit complete")


if __name__ == "__main__":
    asyncio.run(audit_data_usage())