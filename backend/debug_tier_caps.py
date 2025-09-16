"""
Debug tier cap enforcement in the greedy assignment algorithm.
"""

import asyncio
import pandas as pd
from app.solver.greedy_assign import _loans_12m_counts
from app.services.database import db_service


async def debug_tier_caps():
    """Debug tier cap calculation and enforcement."""
    print("=" * 60)
    print("Debugging Tier Cap Enforcement")
    print("=" * 60)

    try:
        # Get loan history for tier cap calculation
        print("1. Fetching loan history for tier cap analysis...")
        loan_response = db_service.client.table('loan_history').select(
            'person_id, make, start_date, end_date'
        ).order('end_date', desc=True).limit(2000).execute()

        loan_history_df = pd.DataFrame(loan_response.data) if loan_response.data else pd.DataFrame()
        print(f"   Found {len(loan_history_df)} loan history records")

        if loan_history_df.empty:
            print("❌ No loan history data")
            return

        # Test the 12-month counting function
        print(f"\n2. Testing 12-month loan counting...")
        week_start = "2025-09-15"

        tcounts = _loans_12m_counts(loan_history_df, week_start)
        print(f"   Generated {len(tcounts)} partner-make combinations with 12m counts")

        # Show top partners by loan count
        if not tcounts.empty:
            top_counts = tcounts.nlargest(10, 'loans_12m')
            print(f"\n   Top 10 partners by 12-month loan count:")
            for _, row in top_counts.iterrows():
                print(f"     Partner {row['person_id']} + {row['make']}: {row['loans_12m']} loans")

        # Check specific partners that got assignments
        print(f"\n3. Checking assigned partners against tier caps...")

        # Get some recent assignments from our test
        assigned_partners = ["14402", "8278"]  # From test results
        tier_caps = {"A+": 999, "A": 6, "B": 2, "C": 0}

        # Get approved ranks for these partners
        ranks_response = db_service.client.table('approved_makes').select(
            'person_id, make, rank'
        ).in_('person_id', assigned_partners).execute()

        ranks_df = pd.DataFrame(ranks_response.data) if ranks_response.data else pd.DataFrame()

        for partner_id in assigned_partners:
            partner_ranks = ranks_df[ranks_df['person_id'] == partner_id]
            partner_counts = tcounts[tcounts['person_id'] == partner_id]

            print(f"\n   Partner {partner_id}:")
            print(f"     Ranks: {dict(zip(partner_ranks['make'], partner_ranks['rank']))}")
            print(f"     12m counts: {dict(zip(partner_counts['make'], partner_counts['loans_12m']))}")

            # Check if tier caps would block them
            for _, rank_row in partner_ranks.iterrows():
                make = rank_row['make']
                rank = rank_row['rank']
                current_count = partner_counts[partner_counts['make'] == make]['loans_12m'].iloc[0] if not partner_counts[partner_counts['make'] == make].empty else 0
                cap = tier_caps.get(rank, 0)

                blocked = current_count >= cap
                print(f"     {make} (Rank {rank}): {current_count}/{cap} loans {'BLOCKED' if blocked else 'OK'}")

        # Check why so few assignments
        print(f"\n4. Assignment Analysis:")

        # Get a sample of candidates to see tier cap impacts
        sample_candidates = pd.DataFrame([
            {"person_id": "14402", "make": "Volkswagen", "rank": "A+"},
            {"person_id": "8278", "make": "Mazda", "rank": "B"},
            {"person_id": "1000", "make": "Toyota", "rank": "A"}  # Random example
        ])

        for _, candidate in sample_candidates.iterrows():
            person_id = candidate['person_id']
            make = candidate['make']
            rank = candidate['rank']

            current_count = tcounts[(tcounts['person_id'] == person_id) & (tcounts['make'] == make)]['loans_12m'].iloc[0] if not tcounts[(tcounts['person_id'] == person_id) & (tcounts['make'] == make)].empty else 0
            cap = tier_caps.get(rank, 0)
            can_assign = current_count < cap

            print(f"   Partner {person_id} + {make} (Rank {rank}): {current_count}/{cap} → {'CAN ASSIGN' if can_assign else 'BLOCKED'}")

    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_tier_caps())