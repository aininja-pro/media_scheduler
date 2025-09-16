"""
Count exact partner-make pairs for Los Angeles and define what they mean.
"""

import asyncio
import pandas as pd
from app.services.database import db_service


async def count_la_partner_makes():
    """Count and explain partner-make pairs for Los Angeles."""

    print("=" * 80)
    print("PARTNER-MAKE PAIR ANALYSIS - Los Angeles")
    print("=" * 80)

    office = "Los Angeles"

    # Get LA vehicles and their makes
    vehicles_response = db_service.client.table('vehicles').select('vin, make, model').eq('office', office).execute()
    vehicles_df = pd.DataFrame(vehicles_response.data) if vehicles_response.data else pd.DataFrame()

    la_vehicle_makes = set(vehicles_df['make'].unique())
    print(f"LA Vehicle Makes: {sorted(la_vehicle_makes)}")
    print(f"Total LA vehicle makes: {len(la_vehicle_makes)}")

    # Count vehicles per make
    make_counts = vehicles_df['make'].value_counts()
    print(f"\nVehicles per make in LA:")
    for make, count in make_counts.items():
        print(f"   {make}: {count} vehicles")

    # Get ALL approved makes with pagination
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

    # Filter to LA vehicle makes only
    la_partner_makes = approved_makes_df[approved_makes_df['make'].isin(la_vehicle_makes)]

    print(f"\n" + "="*60)
    print("PARTNER-MAKE PAIR DEFINITION")
    print("="*60)

    print(f"\nWhat is a 'Partner-Make Pair'?")
    print(f"   - A unique combination of (Partner ID + Vehicle Make)")
    print(f"   - Represents: 'Partner X is approved to loan Make Y vehicles'")
    print(f"   - Example: (Partner 8278, Toyota) = 'Partner 8278 can loan Toyota vehicles'")

    print(f"\nExamples from your data:")
    for _, row in la_partner_makes.head(10).iterrows():
        print(f"   Partner {row['person_id']} + {row['make']} (Rank {row['rank']})")

    print(f"\n" + "="*60)
    print("LOS ANGELES PARTNER-MAKE COUNTS")
    print("="*60)

    print(f"\nTotal partner-make pairs for LA vehicle makes: {len(la_partner_makes):,}")

    # Break down by make
    la_make_counts = la_partner_makes['make'].value_counts()
    print(f"\nPartner approvals by make:")
    for make, count in la_make_counts.items():
        vehicles_for_make = make_counts.get(make, 0)
        potential_pairings = count * vehicles_for_make
        print(f"   {make}: {count} partners × {vehicles_for_make} vehicles = {potential_pairings:,} potential VIN-partner pairings")

    # Calculate total theoretical pairings
    total_theoretical = sum(la_make_counts[make] * make_counts.get(make, 0) for make in la_make_counts.index)
    print(f"\nTotal theoretical VIN-partner pairings: {total_theoretical:,}")

    # Partner distribution
    partner_make_counts = la_partner_makes['person_id'].value_counts()
    print(f"\nPartner approval distribution:")
    print(f"   - Unique partners approved for LA makes: {len(partner_make_counts)}")
    print(f"   - Average makes per partner: {len(la_partner_makes) / len(partner_make_counts):.1f}")
    print(f"   - Max makes for one partner: {partner_make_counts.max()}")
    print(f"   - Min makes for one partner: {partner_make_counts.min()}")

    # Show top partners by make count
    print(f"\nTop partners by number of approved makes:")
    for person_id in partner_make_counts.head(5).index:
        partner_makes = la_partner_makes[la_partner_makes['person_id'] == person_id]['make'].tolist()
        print(f"   Partner {person_id}: {len(partner_makes)} makes - {partner_makes}")

    # Export the data
    output_file = "la_partner_make_pairs.csv"
    la_partner_makes.to_csv(output_file, index=False)
    print(f"\n📁 LA partner-make pairs exported to: {output_file}")

    print(f"\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Partner-Make Pairs for Los Angeles: {len(la_partner_makes):,}")
    print(f"Theoretical VIN-Partner Pairings: {total_theoretical:,}")
    print(f"Unique Partners: {len(partner_make_counts)}")
    print(f"Vehicle Makes: {len(la_vehicle_makes)}")


if __name__ == "__main__":
    asyncio.run(count_la_partner_makes())