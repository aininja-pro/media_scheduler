"""
Trace exactly what the algorithm is doing step by step.
"""

import asyncio
import pandas as pd
from app.services.database import db_service


async def trace_algorithm_logic():
    """Trace exactly what data the algorithm uses."""

    print("=" * 80)
    print("TRACING ALGORITHM LOGIC FOR LOS ANGELES")
    print("=" * 80)

    office = "Los Angeles"

    # Step 1: What does the solver API actually pass to build_weekly_candidates?
    print("1. CHECKING SOLVER API DATA FLOW:")

    # Get LA vehicles
    vehicles_response = db_service.client.table('vehicles').select('vin, make').eq('office', office).execute()
    vehicles_df = pd.DataFrame(vehicles_response.data)
    la_vehicle_makes = set(vehicles_df['make'].unique())

    print(f"   - LA vehicles: {len(vehicles_df)}")
    print(f"   - LA vehicle makes: {sorted(la_vehicle_makes)}")

    # Get ALL approved makes (what the solver API fetches)
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

    # Step 2: Check what the solver API does with this data
    print(f"\n2. SOLVER API FILTERING LOGIC:")

    # This is exactly what the solver API does:
    office_vehicle_makes = set(vehicles_df['make'].unique())
    office_approved = approved_makes_df[approved_makes_df['make'].isin(office_vehicle_makes)]

    print(f"   - Total approved_makes records: {len(approved_makes_df):,}")
    print(f"   - Filtered to LA vehicle makes: {len(office_approved):,}")
    print(f"   - Unique partners in filtered data: {office_approved['person_id'].nunique()}")

    # Step 3: Check if these partners are from LA or other offices
    print(f"\n3. CHECKING PARTNER OFFICES:")

    # Get sample of partners and their offices
    sample_partner_ids = office_approved['person_id'].unique()[:10]

    print(f"   Sample partners in the 651:")
    for partner_id in sample_partner_ids:
        # Check what office this partner is from
        partner_response = db_service.client.table('media_partners').select('person_id, office').eq('person_id', partner_id).execute()

        if partner_response.data:
            partner_office = partner_response.data[0]['office']
            print(f"     Partner {partner_id}: office = '{partner_office}'")
        else:
            print(f"     Partner {partner_id}: NOT FOUND in media_partners")

    # Step 4: Check what SHOULD happen vs what IS happening
    print(f"\n4. WHAT SHOULD HAPPEN VS WHAT IS HAPPENING:")

    # Get actual LA partners
    la_partners_response = db_service.client.table('media_partners').select('person_id').eq('office', office).execute()
    la_partner_ids = set([p['person_id'] for p in la_partners_response.data]) if la_partners_response.data else set()

    print(f"   - LA partners in media_partners: {len(la_partner_ids)}")

    # Check overlap
    algorithm_partner_ids = set(office_approved['person_id'].unique())
    la_only = algorithm_partner_ids.intersection(la_partner_ids)
    non_la = algorithm_partner_ids - la_partner_ids

    print(f"   - Algorithm uses LA partners: {len(la_only)}")
    print(f"   - Algorithm uses NON-LA partners: {len(non_la)}")

    if len(non_la) > 0:
        print(f"\n❌ BUG CONFIRMED: Algorithm includes {len(non_la)} partners from other offices!")
        print(f"   Sample non-LA partners: {list(non_la)[:5]}")
    else:
        print(f"\n✅ Algorithm correctly filters to LA partners only")

    print(f"\n✅ Algorithm trace complete")


if __name__ == "__main__":
    asyncio.run(trace_algorithm_logic())