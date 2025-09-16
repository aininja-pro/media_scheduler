"""
Analyze exactly what tier caps are blocking partners from assignments.
"""

import asyncio
import pandas as pd
from app.services.database import db_service


async def analyze_tier_cap_blocking():
    """Analyze what tier caps are blocking assignments."""

    print("=" * 80)
    print("TIER CAP BLOCKING ANALYSIS")
    print("=" * 80)

    office = "Los Angeles"

    # Get LA vehicles and makes
    vehicles_response = db_service.client.table('vehicles').select('vin, make').eq('office', office).execute()
    vehicles_df = pd.DataFrame(vehicles_response.data) if vehicles_response.data else pd.DataFrame()
    la_makes = set(vehicles_df['make'].unique())

    print(f"LA vehicle makes: {sorted(la_makes)}")

    # Get ALL approved makes for LA makes
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

    approved_df = pd.DataFrame(all_approved)
    la_approved = approved_df[approved_df['make'].isin(la_makes)]

    print(f"Partners approved for LA makes: {len(la_approved):,}")

    # Get ALL rules
    rules_response = db_service.client.table('rules').select('*').execute()
    rules_df = pd.DataFrame(rules_response.data) if rules_response.data else pd.DataFrame()

    print(f"Total rules in database: {len(rules_df)}")

    if not rules_df.empty:
        print(f"\nRules breakdown:")
        print(f"Rules columns: {list(rules_df.columns)}")

        # Show all rules
        for _, rule in rules_df.iterrows():
            make = rule.get('make', 'N/A')
            rank = rule.get('rank', 'N/A')
            cap = rule.get('loan_cap_per_year', 'N/A')
            print(f"   {make} + {rank}: cap = {cap}")

    # Analyze rank distribution in approved makes
    print(f"\n" + "="*50)
    print("RANK DISTRIBUTION IN APPROVED MAKES (LA)")
    print("="*50)

    rank_dist = la_approved['rank'].value_counts()
    print(f"Rank distribution for LA-approved partners:")
    for rank, count in rank_dist.items():
        print(f"   Rank {rank}: {count:,} partner-make pairs")

    # Cross-reference with rules
    print(f"\n" + "="*50)
    print("TIER CAP ANALYSIS BY RANK")
    print("="*50)

    if not rules_df.empty:
        # For each rank, show what caps apply
        for rank in rank_dist.index:
            rank_pairs = la_approved[la_approved['rank'] == rank]
            print(f"\nRank {rank} ({len(rank_pairs):,} pairs):")

            # Check what rules apply to this rank
            rank_rules = rules_df[rules_df['rank'] == rank]

            if rank_rules.empty:
                print(f"   ❌ NO RULES for rank {rank} → defaults to cap = 0 → ALL BLOCKED")
            else:
                print(f"   ✅ Has rules:")
                for _, rule in rank_rules.iterrows():
                    cap = rule.get('loan_cap_per_year', 'N/A')
                    make = rule.get('make', 'N/A')
                    print(f"     {make}: cap = {cap}")

                # Check which makes have rules vs don't
                rank_makes = set(rank_pairs['make'].unique())
                rule_makes = set(rank_rules['make'].unique())

                missing_rules = rank_makes - rule_makes
                if missing_rules:
                    missing_count = rank_pairs[rank_pairs['make'].isin(missing_rules)]['make'].value_counts()
                    print(f"   ⚠️  Missing rules for:")
                    for make, count in missing_count.items():
                        print(f"     {make}: {count} pairs → default cap = 0 → BLOCKED")

    # Summary of blocking
    print(f"\n" + "="*50)
    print("BLOCKING SUMMARY")
    print("="*50)

    if not rules_df.empty:
        # Count how many pairs have rules vs don't
        rules_lookup = set()
        for _, rule in rules_df.iterrows():
            rules_lookup.add((rule['make'], rule['rank']))

        pairs_with_rules = 0
        pairs_without_rules = 0

        for _, pair in la_approved.iterrows():
            key = (pair['make'], pair['rank'])
            if key in rules_lookup:
                pairs_with_rules += 1
            else:
                pairs_without_rules += 1

        print(f"Partner-make pairs WITH rules: {pairs_with_rules:,}")
        print(f"Partner-make pairs WITHOUT rules: {pairs_without_rules:,} → BLOCKED (cap = 0)")

        blocking_rate = (pairs_without_rules / len(la_approved)) * 100
        print(f"Blocking rate due to missing rules: {blocking_rate:.1f}%")

    print(f"\n✅ Tier cap blocking analysis complete")


if __name__ == "__main__":
    asyncio.run(analyze_tier_cap_blocking())