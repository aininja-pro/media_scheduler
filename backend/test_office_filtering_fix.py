"""
Test that office filtering is working correctly after the fix.
"""

import asyncio
import pandas as pd
from app.services.database import db_service


async def test_office_filtering():
    """Test office-based partner filtering logic."""

    await db_service.initialize()

    office = 'Los Angeles'
    print(f"\n{'='*60}")
    print(f"TESTING OFFICE FILTERING FIX FOR {office}")
    print(f"{'='*60}\n")

    # 1. Get media partners for this office ONLY
    office_partners_response = db_service.client.table('media_partners').select('person_id, name').eq('office', office).execute()
    office_partner_ids = set([p['person_id'] for p in office_partners_response.data]) if office_partners_response.data else set()
    print(f"1. Partners in {office} office: {len(office_partner_ids)}")

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
    print(f"2. Total approved_makes entries (all offices): {len(approved_makes_df)}")

    # 3. Filter to only partners from this office
    office_approved_makes = approved_makes_df[approved_makes_df['person_id'].isin(office_partner_ids)]
    print(f"3. Approved_makes entries for {office} partners only: {len(office_approved_makes)}")

    # 4. Get LA vehicle makes
    vehicles_response = db_service.client.table('vehicles').select('make').eq('office', office).execute()
    office_vehicle_makes = set([v['make'] for v in vehicles_response.data]) if vehicles_response.data else set()
    print(f"4. Unique vehicle makes in {office}: {len(office_vehicle_makes)}")
    print(f"   Makes: {sorted(office_vehicle_makes)}")

    # 5. Filter to only makes present in office vehicles
    office_approved = office_approved_makes[office_approved_makes['make'].isin(office_vehicle_makes)]
    print(f"5. Approved entries for {office} partners AND {office} makes: {len(office_approved)}")

    # 6. Count unique partners with approvals
    partners_with_approvals = set(office_approved['person_id'].unique())
    print(f"6. {office} partners WITH approved_makes entries: {len(partners_with_approvals)}")

    # 7. Find partners without any approved_makes entries
    partners_without_approvals = office_partner_ids - partners_with_approvals
    print(f"7. {office} partners WITHOUT approved_makes entries: {len(partners_without_approvals)}")

    # 8. Calculate total eligible partners (the correct number)
    total_eligible_partners = len(office_partner_ids)  # All partners in the office
    print(f"\n{'='*60}")
    print(f"CORRECTED NUMBERS:")
    print(f"{'='*60}")
    print(f"✅ Total eligible partners for {office}: {total_eligible_partners}")
    print(f"   - {len(partners_with_approvals)} have specific make approvals")
    print(f"   - {len(partners_without_approvals)} will get default 'C' rank for all makes")

    # 9. Show what the publication_df will look like
    print(f"\n{'='*60}")
    print(f"PUBLICATION_DF BREAKDOWN:")
    print(f"{'='*60}")

    # Partners WITH approvals
    entries_with_approvals = len(office_approved)

    # Partners WITHOUT approvals get entries for ALL makes
    entries_without_approvals = len(partners_without_approvals) * len(office_vehicle_makes)

    total_entries = entries_with_approvals + entries_without_approvals

    print(f"Publication_df will have {total_entries} rows:")
    print(f"  - {entries_with_approvals} from partners with approved_makes")
    print(f"  - {entries_without_approvals} from partners without approvals")
    print(f"    ({len(partners_without_approvals)} partners × {len(office_vehicle_makes)} makes)")

    await db_service.close()


if __name__ == "__main__":
    asyncio.run(test_office_filtering())