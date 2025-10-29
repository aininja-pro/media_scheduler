"""
Debug why approved_makes data isn't matching LA partners.
"""

import asyncio
import pandas as pd
from app.services.database import DatabaseService


async def debug_approved_makes():
    db = DatabaseService()
    await db.initialize()

    print("=" * 80)
    print("DEBUGGING APPROVED_MAKES MATCHING ISSUE")
    print("=" * 80)

    # 1. Check person_id 10613 specifically
    print("\n1. Checking person_id 10613 (example):")

    # Check in media_partners
    partner_response = db.client.table('media_partners').select('*').eq('person_id', '10613').execute()
    if partner_response.data:
        partner = partner_response.data[0]
        print(f"   Found in media_partners: {partner['name']}, Office: {partner['office']}")
    else:
        print("   NOT found in media_partners")

    # Check in approved_makes
    approved_response = db.client.table('approved_makes').select('*').eq('person_id', '10613').execute()
    if approved_response.data:
        print(f"   Found {len(approved_response.data)} approved_makes entries")
        for app in approved_response.data[:3]:
            print(f"     - {app['make']}, Rank: {app.get('rank', 'N/A')}")
    else:
        print("   NOT found in approved_makes")

    # 2. Check LA partners
    print("\n2. Loading LA partners:")
    la_partners_response = db.client.table('media_partners').select('person_id, name, office').eq('office', 'Los Angeles').execute()
    la_partners_df = pd.DataFrame(la_partners_response.data)
    print(f"   Total LA partners: {len(la_partners_df)}")

    # Show data types
    if not la_partners_df.empty:
        print(f"   person_id dtype in media_partners: {la_partners_df['person_id'].dtype}")
        print(f"   Sample person_ids: {la_partners_df['person_id'].head(5).tolist()}")

    # 3. Check approved_makes
    print("\n3. Loading all approved_makes:")
    all_approved_response = db.client.table('approved_makes').select('person_id, make, rank').execute()
    all_approved_df = pd.DataFrame(all_approved_response.data)
    print(f"   Total approved_makes records: {len(all_approved_df)}")

    if not all_approved_df.empty:
        print(f"   person_id dtype in approved_makes: {all_approved_df['person_id'].dtype}")
        print(f"   Sample person_ids: {all_approved_df['person_id'].head(5).tolist()}")

    # 4. Check data type matching issue
    print("\n4. Checking data type matching:")

    if not la_partners_df.empty and not all_approved_df.empty:
        # Convert both to strings for comparison
        la_ids_str = set(la_partners_df['person_id'].astype(str).tolist())
        approved_ids_str = set(all_approved_df['person_id'].astype(str).tolist())

        matching_ids = la_ids_str & approved_ids_str
        print(f"   LA partner IDs (as strings): {len(la_ids_str)}")
        print(f"   Approved makes person IDs (as strings): {len(approved_ids_str)}")
        print(f"   Matching IDs: {len(matching_ids)}")

        if matching_ids:
            print(f"   First 10 matching IDs: {list(matching_ids)[:10]}")

            # Show some matches with details
            sample_ids = list(matching_ids)[:3]
            for pid in sample_ids:
                partner = la_partners_df[la_partners_df['person_id'].astype(str) == pid].iloc[0]
                approvals = all_approved_df[all_approved_df['person_id'].astype(str) == pid]
                print(f"\n   Partner {pid}: {partner['name']}")
                print(f"     Office: {partner['office']}")
                print(f"     Approved makes: {approvals['make'].nunique()} unique makes")

    # 5. Check the actual filtering in the test
    print("\n5. Testing the filtering logic:")

    # This mimics what the test does
    la_partner_ids = set(la_partners_df['person_id'].tolist())
    print(f"   LA partner IDs set type: {type(list(la_partner_ids)[0]) if la_partner_ids else 'empty'}")

    # Filter approved makes
    approved_la = all_approved_df[all_approved_df['person_id'].isin(la_partner_ids)]
    print(f"   Filtered approved_makes for LA: {len(approved_la)} records")

    if len(approved_la) == 0 and len(matching_ids) > 0:
        print("\n   ⚠️  DATA TYPE MISMATCH DETECTED!")
        print("   The person_id columns have different data types.")
        print("   Need to ensure consistent types when filtering.")

        # Try with explicit type conversion
        la_partner_ids_str = set(la_partners_df['person_id'].astype(str).tolist())
        all_approved_df['person_id_str'] = all_approved_df['person_id'].astype(str)
        approved_la_fixed = all_approved_df[all_approved_df['person_id_str'].isin(la_partner_ids_str)]
        print(f"\n   After string conversion: {len(approved_la_fixed)} records match!")

    await db.close()


if __name__ == "__main__":
    asyncio.run(debug_approved_makes())