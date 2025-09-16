"""
Verify current LA numbers after media_partners update.
"""

import asyncio
from app.services.database import db_service


async def verify_current_numbers():
    """Check current LA partner numbers."""

    print("=" * 60)
    print("VERIFYING CURRENT LA NUMBERS")
    print("=" * 60)

    # 1. Current LA partners in media_partners table
    la_partners_response = db_service.client.table('media_partners').select('person_id, name').eq('office', 'Los Angeles').execute()
    la_partners_count = len(la_partners_response.data) if la_partners_response.data else 0

    print(f"1. LA Partners (media_partners.office = 'Los Angeles'): {la_partners_count}")

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

    # 4. Partners approved for LA vehicle makes
    la_approved = approved_makes_df[approved_makes_df['make'].isin(la_vehicle_makes)]
    la_approved_unique_partners = la_approved['person_id'].nunique()

    print(f"2. Partners approved for LA vehicle makes: {la_approved_unique_partners}")
    print(f"3. Total partner-make approvals for LA: {len(la_approved)}")

    # 5. Cross-reference: How many LA partners are in approved_makes?
    la_partner_ids = set([p['person_id'] for p in la_partners_response.data]) if la_partners_response.data else set()
    approved_partner_ids = set(la_approved['person_id'].unique())

    overlap = la_partner_ids.intersection(approved_partner_ids)
    print(f"4. LA partners who are also approved for LA makes: {len(overlap)}")

    print(f"\n" + "="*50)
    print("EXPLANATION OF 651 vs 202/142")
    print("="*50)

    print(f"If you see '651 Eligible Partners' in the UI, it means:")
    print(f"   - 651 unique partner IDs approved for LA vehicle makes")
    print(f"   - These partners come from ALL offices, not just LA office")
    print(f"   - Many are from other cities but approved for makes that LA has")
    print(f"")
    print(f"Your numbers:")
    print(f"   - 202 total partners in LA office")
    print(f"   - 142 LA partners in approved_makes")
    print(f"   - 651 total partners (all offices) approved for LA makes")

    print(f"\nThe 651 includes partners from Atlanta, Chicago, etc. who are")
    print(f"approved for Toyota, Volkswagen, etc. that LA also has.")

    print(f"\n✅ Verification complete")


if __name__ == "__main__":
    import pandas as pd
    asyncio.run(verify_current_numbers())