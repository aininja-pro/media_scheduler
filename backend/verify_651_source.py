"""
Verify if the 651 'Eligible Partners' comes from the 202 LA media partners pool.
"""

import asyncio
import pandas as pd
from app.services.database import db_service


async def verify_651_source():
    """Check exactly where the 651 number comes from."""

    print("=" * 60)
    print("VERIFYING 651 'ELIGIBLE PARTNERS' SOURCE")
    print("=" * 60)

    # 1. Current LA partners (your updated number)
    la_partners_response = db_service.client.table('media_partners').select('person_id, name').eq('office', 'Los Angeles').execute()
    la_partner_ids = set([p['person_id'] for p in la_partners_response.data]) if la_partners_response.data else set()

    print(f"1. LA media partners (office = 'Los Angeles'): {len(la_partner_ids)}")
    print(f"   Sample LA partner IDs: {list(la_partner_ids)[:5]}")

    # 2. Get ALL approved makes
    all_approved = []
    limit = 1000
    offset = 0
    while True:
        approved_response = db_service.client.table('approved_makes').select('person_id, make, rank').range(offset, offset + limit - 1).execute()
        if not approved_response.data:
            break
        all_approved.extend(approved_response.data)
        offset += limit
        if len(approved_response.data) < limit:
            break

    approved_makes_df = pd.DataFrame(all_approved)

    # 3. Get LA vehicle makes
    vehicles_response = db_service.client.table('vehicles').select('make').eq('office', 'Los Angeles').execute()
    la_vehicle_makes = set([v['make'] for v in vehicles_response.data]) if vehicles_response.data else set()

    print(f"2. LA vehicle makes: {sorted(la_vehicle_makes)}")

    # 4. Partners approved for LA vehicle makes
    la_approved = approved_makes_df[approved_makes_df['make'].isin(la_vehicle_makes)]

    print(f"3. ALL partners approved for LA makes: {la_approved['person_id'].nunique()}")
    print(f"4. Total partner-make combinations: {len(la_approved)}")

    # 5. CRITICAL CHECK: How many of the approved partners are actually LA partners?
    approved_partner_ids = set(la_approved['person_id'].unique())
    la_partners_in_approved = la_partner_ids.intersection(approved_partner_ids)

    print(f"\n" + "="*50)
    print("THE CRITICAL BREAKDOWN")
    print("="*50)

    print(f"LA partners in approved_makes: {len(la_partners_in_approved)}")
    print(f"Non-LA partners in approved for LA makes: {len(approved_partner_ids) - len(la_partners_in_approved)}")

    # 6. If the algorithm SHOULD filter to LA partners only
    la_only_approved = la_approved[la_approved['person_id'].isin(la_partner_ids)]

    print(f"\nIF algorithm filtered to LA partners only:")
    print(f"   - Unique LA partners: {la_only_approved['person_id'].nunique()}")
    print(f"   - LA partner-make combinations: {len(la_only_approved)}")

    print(f"\n" + "="*50)
    print("ANSWER TO YOUR QUESTION")
    print("="*50)

    if len(approved_partner_ids) == len(la_partners_in_approved):
        print(f"✅ YES: The 651 represents combinations from the 202 LA partners pool")
    else:
        print(f"❌ NO: The 651 includes partners from other offices")
        print(f"   - LA partners contributing: {len(la_partners_in_approved)}")
        print(f"   - Non-LA partners included: {len(approved_partner_ids) - len(la_partners_in_approved)}")

    print(f"\n✅ Analysis complete")


if __name__ == "__main__":
    asyncio.run(verify_651_source())