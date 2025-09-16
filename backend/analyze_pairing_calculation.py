"""
Analyze how the 22,709 feasible pairings are calculated.
"""

import asyncio
import pandas as pd
from app.services.database import db_service


async def analyze_pairing_calculation():
    """Understand the pairing calculation for LA."""

    await db_service.initialize()

    office = 'Los Angeles'
    print(f"\n{'='*60}")
    print(f"ANALYZING FEASIBLE PAIRING CALCULATION FOR {office}")
    print(f"{'='*60}\n")

    # 1. Get vehicles for LA
    vehicles_response = db_service.client.table('vehicles').select('vin, make, model').eq('office', office).execute()
    vehicles_df = pd.DataFrame(vehicles_response.data) if vehicles_response.data else pd.DataFrame()
    print(f"1. Total vehicles in {office}: {len(vehicles_df)}")

    # Show vehicle make distribution
    make_counts = vehicles_df['make'].value_counts()
    print(f"\n   Vehicle distribution by make:")
    for make, count in make_counts.items():
        print(f"      {make}: {count} vehicles")

    # 2. Get media partners for LA
    partners_response = db_service.client.table('media_partners').select('person_id, name').eq('office', office).execute()
    office_partner_ids = set([p['person_id'] for p in partners_response.data]) if partners_response.data else set()
    print(f"\n2. Total partners in {office}: {len(office_partner_ids)}")

    # 3. Get approved makes for LA partners
    all_approved = []
    limit = 1000
    offset = 0
    while True:
        approved_response = db_service.client.table('approved_makes').select('person_id, make').range(offset, offset + limit - 1).execute()
        if not approved_response.data:
            break
        all_approved.extend(approved_response.data)
        offset += limit
        if len(approved_response.data) < limit:
            break

    approved_df = pd.DataFrame(all_approved)

    # Filter to LA partners and LA vehicle makes
    office_vehicle_makes = set(vehicles_df['make'].unique())
    la_approved = approved_df[
        (approved_df['person_id'].isin(office_partner_ids)) &
        (approved_df['make'].isin(office_vehicle_makes))
    ]

    # Count partners per make
    print(f"\n3. Partner eligibility by make:")
    for make in sorted(office_vehicle_makes):
        partners_for_make = la_approved[la_approved['make'] == make]['person_id'].nunique()
        vehicles_for_make = len(vehicles_df[vehicles_df['make'] == make])
        potential_pairs = partners_for_make * vehicles_for_make
        print(f"   {make:12} - {vehicles_for_make:3} vehicles × {partners_for_make:3} partners = {potential_pairs:6} potential pairs")

    # 4. Partners without approved_makes
    partners_with_approvals = set(la_approved['person_id'].unique())
    partners_without_approvals = office_partner_ids - partners_with_approvals
    print(f"\n4. Partners without approved_makes: {len(partners_without_approvals)}")
    print(f"   These get C rank for all {len(office_vehicle_makes)} makes")

    # Calculate theoretical maximum
    print(f"\n{'='*60}")
    print(f"THEORETICAL CALCULATION:")
    print(f"{'='*60}")

    # Partners WITH approvals
    pairs_with_approvals = 0
    for make in office_vehicle_makes:
        partners_for_make = la_approved[la_approved['make'] == make]['person_id'].nunique()
        vehicles_for_make = len(vehicles_df[vehicles_df['make'] == make])
        pairs_with_approvals += partners_for_make * vehicles_for_make

    # Partners WITHOUT approvals (get all makes)
    pairs_without_approvals = len(partners_without_approvals) * len(vehicles_df)

    theoretical_max = pairs_with_approvals + pairs_without_approvals
    print(f"Theoretical maximum (before constraints): {theoretical_max:,}")
    print(f"  - From partners with approvals: {pairs_with_approvals:,}")
    print(f"  - From partners without approvals: {pairs_without_approvals:,}")

    print(f"\nActual feasible pairings: 22,709")
    print(f"Reduction from theoretical: {theoretical_max - 22709:,} ({((theoretical_max - 22709) / theoretical_max * 100):.1f}%)")

    print(f"\n{'='*60}")
    print(f"CONSTRAINTS THAT REDUCE PAIRINGS:")
    print(f"{'='*60}")
    print(f"1. Vehicle availability (must be available >= min_days)")
    print(f"2. Cooldown periods (30-day restriction)")
    print(f"3. Current activity (vehicles already on loan)")
    print(f"4. Turn-in dates (vehicles being turned in)")

    await db_service.close()


if __name__ == "__main__":
    asyncio.run(analyze_pairing_calculation())