#!/usr/bin/env python3
"""
Debug partner eligibility by office to find why some offices have 0 partners.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

import pandas as pd
import asyncio
from app.services.database import db_service

async def debug_partner_data():
    """Debug partner eligibility data by office."""

    print("🔌 Connecting to Supabase...")

    try:
        # Fetch all relevant data
        print("\n📋 Fetching data...")

        # Vehicles
        vehicles_response = db_service.client.table('vehicles').select('*').execute()
        vehicles_df = pd.DataFrame(vehicles_response.data)
        print(f"Vehicles: {len(vehicles_df)} records")

        # Media Partners
        partners_response = db_service.client.table('media_partners').select('*').execute()
        partners_df = pd.DataFrame(partners_response.data) if partners_response.data else pd.DataFrame()
        print(f"Media Partners: {len(partners_df)} records")

        # Approved Makes
        approved_makes_response = db_service.client.table('approved_makes').select('*').execute()
        approved_makes_df = pd.DataFrame(approved_makes_response.data) if approved_makes_response.data else pd.DataFrame()
        print(f"Approved Makes: {len(approved_makes_df)} records")

        print("\n" + "="*60)
        print("DIAGNOSIS: Partner Eligibility by Office")
        print("="*60)

        # Check distribution by office
        print("\n🏢 VEHICLE DISTRIBUTION BY OFFICE:")
        vehicle_counts = vehicles_df['office'].value_counts()
        for office, count in vehicle_counts.items():
            print(f"   {office}: {count} vehicles")

        if not partners_df.empty:
            print("\n👥 MEDIA PARTNER DISTRIBUTION BY OFFICE:")
            partner_counts = partners_df['office'].value_counts()
            for office, count in partner_counts.items():
                print(f"   {office}: {count} partners")

            # Check for office name mismatches
            vehicle_offices = set(vehicles_df['office'].unique())
            partner_offices = set(partners_df['office'].unique())

            print(f"\n🔍 OFFICE NAME ANALYSIS:")
            print(f"   Vehicle offices: {sorted(vehicle_offices)}")
            print(f"   Partner offices: {sorted(partner_offices)}")

            missing_in_partners = vehicle_offices - partner_offices
            missing_in_vehicles = partner_offices - vehicle_offices

            if missing_in_partners:
                print(f"   ⚠️ Vehicle offices with NO partners: {sorted(missing_in_partners)}")
            if missing_in_vehicles:
                print(f"   ⚠️ Partner offices with NO vehicles: {sorted(missing_in_vehicles)}")

            common_offices = vehicle_offices & partner_offices
            print(f"   ✅ Common offices: {sorted(common_offices)}")

        else:
            print("\n❌ NO MEDIA PARTNERS DATA FOUND")

        if not approved_makes_df.empty:
            print("\n🎯 APPROVED MAKES ANALYSIS:")

            # Check make distribution
            make_counts = approved_makes_df['make'].value_counts()
            print(f"   Top makes in approved_makes: {dict(make_counts.head())}")

            # Check person_id distribution
            person_counts = approved_makes_df['person_id'].value_counts()
            print(f"   Partners with approvals: {len(person_counts)} unique person_ids")
            print(f"   Max approvals per partner: {person_counts.max()}")

            # Cross-check with media partners
            if not partners_df.empty:
                approved_person_ids = set(approved_makes_df['person_id'].astype(str))
                partner_person_ids = set(partners_df['person_id'].astype(str))

                overlap = approved_person_ids & partner_person_ids
                print(f"   🔗 Person_ID overlap: {len(overlap)} out of {len(approved_person_ids)} approved partners")

                if len(overlap) < len(approved_person_ids):
                    missing = approved_person_ids - partner_person_ids
                    print(f"   ⚠️ Approved partners NOT in media_partners: {len(missing)} (sample: {list(missing)[:5]})")

        else:
            print("\n❌ NO APPROVED MAKES DATA FOUND")

        # Test specific offices
        print("\n" + "="*60)
        print("DETAILED OFFICE ANALYSIS")
        print("="*60)

        test_offices = ['Atlanta', 'Denver', 'Los Angeles']

        for office in test_offices:
            print(f"\n🏢 {office.upper()}:")

            # Vehicle info
            office_vehicles = vehicles_df[vehicles_df['office'] == office]
            if office_vehicles.empty:
                print(f"   ❌ No vehicles in {office}")
                continue

            print(f"   🚗 Vehicles: {len(office_vehicles)}")
            make_dist = office_vehicles['make'].value_counts().head(3)
            print(f"   Top makes: {dict(make_dist)}")

            # Partner info
            if not partners_df.empty:
                office_partners = partners_df[partners_df['office'] == office]
                print(f"   👥 Partners: {len(office_partners)}")

                if len(office_partners) > 0:
                    sample_partners = office_partners['person_id'].head(3).tolist()
                    print(f"   Sample partner IDs: {sample_partners}")
            else:
                print(f"   ❌ No partners data available")

            # Eligibility analysis
            if not approved_makes_df.empty and not partners_df.empty:
                # For the top make in this office, find eligible partners
                top_make = make_dist.index[0] if len(make_dist) > 0 else None
                if top_make:
                    # Partners approved for this make
                    make_approvals = approved_makes_df[approved_makes_df['make'] == top_make]['person_id'].unique()

                    # Partners in this office
                    office_partner_ids = office_partners['person_id'].tolist()

                    # Intersection - partners both approved AND in this office
                    eligible_for_make = [p for p in make_approvals if str(p) in [str(x) for x in office_partner_ids]]

                    print(f"   🎯 For {top_make}:")
                    print(f"      Partners approved for {top_make}: {len(make_approvals)}")
                    print(f"      Partners in {office}: {len(office_partner_ids)}")
                    print(f"      ✅ Eligible partners: {len(eligible_for_make)}")

                    if len(eligible_for_make) == 0:
                        print(f"      ❌ PROBLEM: No overlap between approved partners and office partners!")

        print(f"\n🔍 This explains why some offices show 0 partner counts!")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_partner_data())