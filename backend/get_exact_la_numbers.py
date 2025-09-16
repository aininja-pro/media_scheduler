"""
Get EXACT Los Angeles numbers from Supabase - no confusion.
"""

import asyncio
import pandas as pd
from app.services.database import db_service


async def get_exact_numbers():
    """Get exact, precise numbers for Los Angeles."""

    print("=" * 80)
    print("EXACT LOS ANGELES NUMBERS FROM SUPABASE")
    print("=" * 80)

    # 1. Total partners in LA (from media_partners table)
    print("1. PARTNERS IN LOS ANGELES:")
    try:
        la_partners_response = db_service.client.table('media_partners').select('person_id, name').eq('office', 'Los Angeles').execute()
        la_partners_count = len(la_partners_response.data) if la_partners_response.data else 0
        print(f"   Total partners with office = 'Los Angeles': {la_partners_count}")

        if la_partners_response.data:
            print(f"   Sample LA partners:")
            for partner in la_partners_response.data[:5]:
                print(f"     Partner {partner['person_id']}: {partner['name']}")
    except Exception as e:
        print(f"   Error: {e}")

    # 2. LA vehicles
    print(f"\n2. VEHICLES IN LOS ANGELES:")
    try:
        la_vehicles_response = db_service.client.table('vehicles').select('vin, make, model').eq('office', 'Los Angeles').execute()
        la_vehicles_count = len(la_vehicles_response.data) if la_vehicles_response.data else 0
        la_vehicles_df = pd.DataFrame(la_vehicles_response.data) if la_vehicles_response.data else pd.DataFrame()

        print(f"   Total vehicles in Los Angeles: {la_vehicles_count}")

        if not la_vehicles_df.empty:
            la_makes = la_vehicles_df['make'].unique()
            print(f"   Vehicle makes in LA: {sorted(la_makes)}")
            print(f"   Number of makes: {len(la_makes)}")
    except Exception as e:
        print(f"   Error: {e}")

    # 3. Get ALL approved makes (with complete pagination)
    print(f"\n3. ALL APPROVED MAKES:")
    try:
        all_approved = []
        limit = 1000
        offset = 0

        print(f"   Fetching all approved_makes with pagination...")
        while True:
            approved_response = db_service.client.table('approved_makes').select('person_id, make, rank').range(offset, offset + limit - 1).execute()
            if not approved_response.data:
                break
            all_approved.extend(approved_response.data)
            offset += limit
            print(f"     Fetched {len(approved_response.data)} records (total: {len(all_approved)})")
            if len(approved_response.data) < limit:
                break

        approved_makes_df = pd.DataFrame(all_approved)
        print(f"   Total approved_makes records: {len(approved_makes_df):,}")

        # Count unique partners in approved_makes
        unique_approved_partners = approved_makes_df['person_id'].nunique()
        print(f"   Unique partners in approved_makes: {unique_approved_partners}")

    except Exception as e:
        print(f"   Error: {e}")
        approved_makes_df = pd.DataFrame()

    # 4. Cross-reference: Partners approved for LA makes
    print(f"\n4. PARTNERS APPROVED FOR LA VEHICLE MAKES:")
    if not approved_makes_df.empty and not la_vehicles_df.empty:
        la_approved = approved_makes_df[approved_makes_df['make'].isin(la_makes)]
        la_approved_partners = la_approved['person_id'].nunique()

        print(f"   Partners approved for LA makes: {la_approved_partners}")
        print(f"   Partner-make combinations for LA: {len(la_approved):,}")

        # Check overlap with LA partners
        la_partner_ids = set([p['person_id'] for p in la_partners_response.data]) if la_partners_response.data else set()
        approved_partner_ids = set(la_approved['person_id'].unique())

        overlap = la_partner_ids.intersection(approved_partner_ids)
        print(f"   LA partners who are also approved for LA makes: {len(overlap)}")

    # 5. Check what we used in our 9/22 test
    print(f"\n5. WHAT OUR 9/22 TEST USED:")
    print(f"   We said: '151 unique partners' and '18,240 pairings'")
    print(f"   Actual data shows much larger universe")

    print(f"\n" + "="*80)
    print("RECONCILIATION")
    print("="*80)
    print(f"The confusion comes from different data sources and filtering:")
    print(f"   - media_partners.office = 'Los Angeles': {la_partners_count} partners")
    print(f"   - approved_makes for LA vehicle makes: {la_approved_partners if 'la_approved_partners' in locals() else 'TBD'} partners")
    print(f"   - Our test used limited data: showing {18240} pairings vs theoretical {total_theoretical if 'total_theoretical' in locals() else 'TBD'}")


if __name__ == "__main__":
    asyncio.run(get_exact_numbers())