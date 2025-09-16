#!/usr/bin/env python3
"""
Query Chicago media partners approved for Volkswagen vehicles.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

import pandas as pd
import asyncio
from app.services.database import db_service

async def query_chicago_volkswagen():
    """Find all Chicago media partners approved for Volkswagen."""

    print("🔌 Connecting to Supabase...")

    try:
        # Fetch ALL media partners
        print("📋 Fetching all media partners...")
        all_partners = []
        partners_response = db_service.client.table('media_partners').select('*').limit(1000).execute()
        if partners_response.data:
            all_partners.extend(partners_response.data)
            while len(partners_response.data) == 1000:
                offset = len(all_partners)
                partners_response = db_service.client.table('media_partners').select('*').range(offset, offset + 999).execute()
                if partners_response.data:
                    all_partners.extend(partners_response.data)
                else:
                    break

        partners_df = pd.DataFrame(all_partners)
        print(f"✅ Fetched {len(partners_df)} total media partners")

        # Fetch ALL approved makes
        print("📋 Fetching all approved makes...")
        all_approved = []
        approved_response = db_service.client.table('approved_makes').select('*').limit(1000).execute()
        if approved_response.data:
            all_approved.extend(approved_response.data)
            while len(approved_response.data) == 1000:
                offset = len(all_approved)
                approved_response = db_service.client.table('approved_makes').select('*').range(offset, offset + 999).execute()
                if approved_response.data:
                    all_approved.extend(approved_response.data)
                else:
                    break

        approved_makes_df = pd.DataFrame(all_approved)
        print(f"✅ Fetched {len(approved_makes_df)} total approved makes records")

        print("\n" + "="*60)
        print("CHICAGO VOLKSWAGEN ANALYSIS")
        print("="*60)

        # Step 1: Find all Chicago media partners
        chicago_partners = partners_df[partners_df['office'] == 'Chicago'].copy()
        print(f"\n🏢 Total Chicago media partners: {len(chicago_partners)}")

        if chicago_partners.empty:
            print("❌ No media partners found in Chicago office")
            return

        # Step 2: Find partners approved for Volkswagen
        vw_approved = approved_makes_df[approved_makes_df['make'] == 'Volkswagen'].copy()
        print(f"🚗 Total partners approved for Volkswagen: {len(vw_approved)}")
        print(f"   Unique partners approved for VW: {vw_approved['person_id'].nunique()}")

        if vw_approved.empty:
            print("❌ No partners approved for Volkswagen")
            return

        # Step 3: Find intersection - Chicago partners who are approved for VW
        chicago_partner_ids = set(chicago_partners['person_id'].astype(str))
        vw_approved_ids = set(vw_approved['person_id'].astype(str))

        chicago_vw_partners = chicago_partner_ids & vw_approved_ids
        print(f"\n🎯 Chicago partners approved for Volkswagen: {len(chicago_vw_partners)}")

        if len(chicago_vw_partners) > 0:
            # Get the actual partner details
            chicago_vw_df = chicago_partners[
                chicago_partners['person_id'].astype(str).isin(chicago_vw_partners)
            ].copy()

            print(f"\n📋 CHICAGO VOLKSWAGEN-APPROVED PARTNERS:")
            print("-" * 60)

            for _, partner in chicago_vw_df.iterrows():
                person_id = partner['person_id']
                name = partner['name']

                # Get their VW approvals (which VW models they can get)
                partner_vw_models = vw_approved[
                    vw_approved['person_id'].astype(str) == str(person_id)
                ]['rank'].tolist()

                print(f"  {name} (ID: {person_id})")
                print(f"    Rank: {', '.join(set(partner_vw_models))}")

            # Show summary by rank
            print(f"\n📊 VOLKSWAGEN APPROVAL BREAKDOWN (Chicago):")
            chicago_vw_approvals = vw_approved[
                vw_approved['person_id'].astype(str).isin(chicago_vw_partners)
            ]

            rank_counts = chicago_vw_approvals['rank'].value_counts()
            for rank, count in rank_counts.items():
                print(f"   Rank {rank}: {count} approvals")

        else:
            print("❌ No Chicago partners are approved for Volkswagen")

            # Debug: Show sample of each dataset
            print("\n🔍 DEBUG INFO:")
            print(f"Sample Chicago partner IDs: {list(chicago_partner_ids)[:5]}")
            print(f"Sample VW approved IDs: {list(vw_approved_ids)[:5]}")

        print(f"\n📈 SUMMARY:")
        print(f"   Chicago office partners: {len(chicago_partners)}")
        print(f"   Partners approved for VW (any office): {len(vw_approved_ids)}")
        print(f"   ✅ Chicago partners approved for VW: {len(chicago_vw_partners)}")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(query_chicago_volkswagen())