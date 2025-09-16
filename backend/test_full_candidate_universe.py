"""
Test the FULL candidate universe for Los Angeles 9/22 - including partners
who never loaned specific makes before.
"""

import asyncio
import pandas as pd
from app.services.database import db_service


async def analyze_full_candidate_universe():
    """Analyze the complete candidate universe vs just loan history."""

    print("=" * 80)
    print("FULL CANDIDATE UNIVERSE ANALYSIS - Los Angeles 9/22/2025")
    print("=" * 80)

    office = "Los Angeles"
    week_start = "2025-09-22"

    # Get approved makes (ALL possible partner-make combinations)
    print("1. Analyzing approved_makes (full eligible universe)...")
    approved_response = db_service.client.table('approved_makes').select('person_id, make, rank').execute()
    approved_df = pd.DataFrame(approved_response.data) if approved_response.data else pd.DataFrame()

    if approved_df.empty:
        print("❌ No approved makes data")
        return

    total_approved_combinations = len(approved_df)
    unique_partners = approved_df['person_id'].nunique()
    unique_makes = approved_df['make'].nunique()

    print(f"   - Total approved combinations: {total_approved_combinations:,}")
    print(f"   - Unique partners: {unique_partners}")
    print(f"   - Unique makes: {unique_makes}")

    # Show sample
    print(f"\n   Sample approved combinations:")
    for _, row in approved_df.head(10).iterrows():
        print(f"     Partner {row['person_id']} + {row['make']} (Rank {row['rank']})")

    # Get loan history (what the 997 represents)
    print(f"\n2. Analyzing loan_history (historical combinations only)...")
    loan_response = db_service.client.table('loan_history').select('person_id, make').execute()
    loan_df = pd.DataFrame(loan_response.data) if loan_response.data else pd.DataFrame()

    if not loan_df.empty:
        historical_combinations = loan_df[['person_id', 'make']].drop_duplicates()
        total_historical = len(historical_combinations)

        print(f"   - Historical combinations: {total_historical:,}")
        print(f"   - These are the ~997 with loan history")

        # Show sample
        print(f"\n   Sample historical combinations:")
        for _, row in historical_combinations.head(10).iterrows():
            print(f"     Partner {row['person_id']} + {row['make']} (has loan history)")

    # Get vehicles for Los Angeles
    print(f"\n3. Analyzing Los Angeles vehicles...")
    vehicles_response = db_service.client.table('vehicles').select('vin, make, model').eq('office', office).execute()
    vehicles_df = pd.DataFrame(vehicles_response.data) if vehicles_response.data else pd.DataFrame()

    if not vehicles_df.empty:
        vehicle_makes = vehicles_df['make'].unique()
        print(f"   - LA vehicles: {len(vehicles_df)}")
        print(f"   - LA vehicle makes: {list(vehicle_makes)}")

        # Find approved partners for LA vehicle makes
        la_eligible = approved_df[approved_df['make'].isin(vehicle_makes)]
        la_combinations = len(la_eligible)

        print(f"   - Eligible combinations for LA makes: {la_combinations:,}")

    # Compare universes
    print(f"\n4. UNIVERSE COMPARISON:")
    print(f"   📊 Total approved combinations: {total_approved_combinations:,}")
    print(f"   📚 Historical combinations (~997): {total_historical:,}")
    print(f"   🎯 LA-eligible combinations: {la_combinations:,}")

    # Calculate potential new combinations (never loaned before)
    if not loan_df.empty:
        # Find approved combinations that have NO loan history
        approved_set = set(zip(approved_df['person_id'], approved_df['make']))
        historical_set = set(zip(historical_combinations['person_id'], historical_combinations['make']))

        new_combinations = approved_set - historical_set

        print(f"   🆕 NEW combinations (never loaned): {len(new_combinations):,}")
        print(f"   💡 These should have cooldown_ok=True automatically!")

        # Show some examples
        if new_combinations:
            print(f"\n   Sample NEW combinations (no cooldown):")
            for i, (partner, make) in enumerate(list(new_combinations)[:10]):
                print(f"     Partner {partner} + {make} (never loaned before)")

    print(f"\n✅ Analysis complete - we should be considering ALL {total_approved_combinations:,} approved combinations, not just the ~997 with history!")


if __name__ == "__main__":
    asyncio.run(analyze_full_candidate_universe())