"""
Test Phase 7.1 with REAL data from the database.

This validates that the feasible triples generation works with actual
production data from your Supabase tables.
"""

import asyncio
import pandas as pd
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.database import DatabaseService
from app.solver.ortools_feasible_v2 import build_feasible_start_day_triples
from app.etl.availability import build_availability_grid


async def test_phase71_with_real_data():
    """Test Phase 7.1 feasible triples with real database data."""

    print("=" * 80)
    print("PHASE 7.1 TEST WITH REAL DATA")
    print("=" * 80)

    # Initialize database
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
        # 1. Load vehicles
        print("1. Loading vehicles...")
        vehicles_response = db.client.table('vehicles').select('*').eq('office', office).execute()
        vehicles_df = pd.DataFrame(vehicles_response.data)
        print(f"   ✓ {len(vehicles_df)} vehicles in {office}")

        if vehicles_df.empty:
            print("   ⚠️  No vehicles found - stopping test")
            return

        # 2. Load media partners
        print("\n2. Loading media partners...")
        partners_response = db.client.table('media_partners').select('*').eq('office', office).execute()
        partners_df = pd.DataFrame(partners_response.data)
        print(f"   ✓ {len(partners_df)} partners in {office}")

        # 3. Load approved makes WITH PAGINATION
        print("\n3. Loading approved makes (with pagination)...")
        all_approved = []
        limit = 1000
        offset = 0

        while True:
            approved_response = db.client.table('approved_makes').select('*').range(offset, offset + limit - 1).execute()
            if not approved_response.data:
                break
            all_approved.extend(approved_response.data)
            print(f"   Loading... {len(all_approved)} records")
            offset += limit
            if len(approved_response.data) < limit:
                break

        approved_df = pd.DataFrame(all_approved)
        print(f"   ✓ Total approved_makes loaded: {len(approved_df)}")

        # Filter to LA partners only
        la_partner_ids = set(partners_df['person_id'].tolist())
        approved_la = approved_df[approved_df['person_id'].isin(la_partner_ids)]
        print(f"   ✓ {len(approved_la)} approved make relationships for LA partners")
        print(f"   ✓ {approved_la['person_id'].nunique()} partners with approvals")

        # 4. Build availability grid
        print("\n4. Building availability grid...")
        activity_response = db.client.table('current_activity').select('*').execute()
        activity_df = pd.DataFrame(activity_response.data)

        # Rename vehicle_vin to vin for compatibility
        if 'vehicle_vin' in activity_df.columns:
            activity_df = activity_df.rename(columns={'vehicle_vin': 'vin'})

        availability_df = build_availability_grid(
            vehicles_df=vehicles_df,
            activity_df=activity_df,
            week_start=week_start,
            office=office
        )

        # Rename 'day' to 'date' for compatibility
        availability_df = availability_df.rename(columns={'day': 'date'})
        print(f"   ✓ Generated {len(availability_df)} availability records")
        print(f"   ✓ {availability_df[availability_df['available'] == True]['vin'].nunique()} vehicles available")

        # 5. Load ops_capacity_calendar (if exists)
        print("\n5. Loading ops capacity calendar...")
        try:
            ops_cal_response = db.client.table('ops_capacity_calendar').select('*').execute()
            ops_calendar_df = pd.DataFrame(ops_cal_response.data)
            print(f"   ✓ {len(ops_calendar_df)} capacity calendar entries")
        except Exception as e:
            print(f"   ⚠️  No ops_capacity_calendar table: {e}")
            ops_calendar_df = None

        # 6. Load model_taxonomy (if exists)
        print("\n6. Loading model taxonomy...")
        try:
            taxonomy_response = db.client.table('model_taxonomy').select('*').execute()
            taxonomy_df = pd.DataFrame(taxonomy_response.data)
            print(f"   ✓ {len(taxonomy_df)} model classifications")
        except Exception as e:
            print(f"   ⚠️  No model_taxonomy table: {e}")
            taxonomy_df = None

        # 7. Build feasible triples
        print("\n7. Building feasible triples...")
        print("   Parameters:")
        print("   - Min available days: 7")
        print("   - Start days: Mon-Fri")
        print("   - Default slots: 15")

        triples_df = build_feasible_start_day_triples(
            vehicles_df=vehicles_df,
            partners_df=partners_df,
            availability_df=availability_df,
            approved_makes_df=approved_la,  # Use filtered LA approvals
            week_start=week_start,
            office=office,
            ops_capacity_df=ops_calendar_df,
            model_taxonomy_df=taxonomy_df,
            start_days=['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
            min_available_days=7,
            default_slots_per_day=15
        )

        # 8. Analyze results
        print("\n" + "=" * 80)
        print("RESULTS")
        print("=" * 80)

        if triples_df.empty:
            print("\n⚠️  NO FEASIBLE TRIPLES GENERATED!")
            print("\nPossible reasons:")
            print("  1. No approved_makes data for LA partners")
            print("  2. No vehicles available for 7 consecutive days")
            print("  3. All days have 0 capacity in ops_capacity_calendar")
            print("  4. Partners have restrictive allowed_start_dows")
        else:
            print(f"\n✓ Generated {len(triples_df)} feasible triples!")

            # Summary statistics
            print("\nSummary:")
            print(f"  Unique vehicles: {triples_df['vin'].nunique()}")
            print(f"  Unique partners: {triples_df['person_id'].nunique()}")
            print(f"  Unique start days: {triples_df['start_day'].nunique()}")

            # Start day distribution
            print("\nStart days:")
            start_days_counts = pd.to_datetime(triples_df['start_day']).dt.day_name().value_counts()
            for day, count in start_days_counts.items():
                print(f"  {day}: {count} triples")

            # Make distribution
            print("\nTop 5 makes:")
            make_counts = triples_df['make'].value_counts().head(5)
            for make, count in make_counts.items():
                print(f"  {make}: {count} triples")

            # Rank distribution
            print("\nRank distribution:")
            rank_counts = triples_df['rank'].value_counts()
            for rank, count in rank_counts.items():
                print(f"  {rank}: {count} triples")

            # Check data quality
            print("\nData Quality Checks:")
            print(f"  All eligibility_ok = True: {triples_df['eligibility_ok'].all()}")
            print(f"  All availability_ok = True: {triples_df['availability_ok'].all()}")
            print(f"  Geo office matches: {triples_df['geo_office_match'].sum()} / {len(triples_df)}")

            # Check for model taxonomy data
            if 'short_model_class' in triples_df.columns:
                classes_present = triples_df['short_model_class'].notna().sum()
                print(f"  Model classes populated: {classes_present} / {len(triples_df)}")

            # Sample output
            print("\nFirst 5 triples:")
            print(triples_df[['vin', 'person_id', 'start_day', 'make', 'model', 'rank']].head())

            # Export for review
            output_file = 'phase71_feasible_triples.csv'
            triples_df.to_csv(output_file, index=False)
            print(f"\n✓ Exported to {output_file}")

        # 9. Diagnostic information if no triples
        if triples_df.empty or len(triples_df) < 100:
            print("\n" + "=" * 80)
            print("DIAGNOSTIC INFORMATION")
            print("=" * 80)

            # Check if it's an approved_makes issue
            if approved_la.empty:
                print("\n⚠️  CRITICAL: No approved_makes data for LA partners!")
                print("   This means NO partners are eligible for ANY vehicles")
                print("   Solution: Upload approved_makes data via /ingest endpoint")

            # Check availability
            available_vins = availability_df[availability_df['available'] == True]['vin'].unique()
            print(f"\nVehicles with some availability: {len(available_vins)}")

            # Check which vehicles are available all 7 days
            vins_7days = []
            for vin in available_vins:
                vin_avail = availability_df[availability_df['vin'] == vin]
                if vin_avail[vin_avail['available'] == True]['date'].nunique() >= 7:
                    vins_7days.append(vin)

            print(f"Vehicles available 7+ days: {len(vins_7days)}")

            if len(vins_7days) > 0 and not approved_la.empty:
                # Check make overlap
                available_makes = vehicles_df[vehicles_df['vin'].isin(vins_7days)]['make'].unique()
                approved_makes = approved_la['make'].unique()
                overlapping_makes = set(available_makes) & set(approved_makes)

                print(f"\nMake overlap analysis:")
                print(f"  Available vehicle makes: {len(available_makes)}")
                print(f"  Approved makes: {len(approved_makes)}")
                print(f"  Overlapping makes: {len(overlapping_makes)}")

                if len(overlapping_makes) > 0:
                    print(f"  Overlapping: {', '.join(list(overlapping_makes)[:5])}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await db.close()

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    print("Testing Phase 7.1 with real production data...")
    asyncio.run(test_phase71_with_real_data())