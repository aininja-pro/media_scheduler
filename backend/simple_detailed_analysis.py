"""
Simple detailed rejection analysis - exact constraint values.
"""

import asyncio
import pandas as pd
from app.services.database import db_service
from app.solver.greedy_assign import _loans_12m_by_pair, _cap_from_rules


async def simple_detailed_analysis():
    """Generate exact constraint values for sample pairings."""

    print("=" * 80)
    print("EXACT CONSTRAINT ANALYSIS")
    print("=" * 80)

    office = "Los Angeles"
    week_start = "2025-09-22"

    # Get sample of 10 vehicles and 20 partners for detailed analysis
    vehicles_response = db_service.client.table('vehicles').select('vin, make, model').eq('office', office).limit(10).execute()
    vehicles_df = pd.DataFrame(vehicles_response.data) if vehicles_response.data else pd.DataFrame()

    approved_response = db_service.client.table('approved_makes').select('person_id, make, rank').limit(20).execute()
    approved_df = pd.DataFrame(approved_response.data) if approved_response.data else pd.DataFrame()

    rules_response = db_service.client.table('rules').select('*').execute()
    rules_df = pd.DataFrame(rules_response.data) if rules_response.data else pd.DataFrame()

    # Get ALL loan history for accurate tier caps
    all_loan_history = []
    limit = 1000
    offset = 0
    while True:
        loan_response = db_service.client.table('loan_history').select('person_id, make, start_date, end_date').range(offset, offset + limit - 1).execute()
        if not loan_response.data:
            break
        all_loan_history.extend(loan_response.data)
        offset += limit
        if len(loan_response.data) < limit:
            break

    loan_history_df = pd.DataFrame(all_loan_history)

    # Convert dates
    for date_col in ['start_date', 'end_date']:
        if date_col in loan_history_df.columns:
            loan_history_df[date_col] = pd.to_datetime(loan_history_df[date_col], errors='coerce').dt.date

    print(f"Sample data:")
    print(f"   - Vehicles: {len(vehicles_df)}")
    print(f"   - Partners: {len(approved_df)}")
    print(f"   - Loan history: {len(loan_history_df):,}")

    # Build tier cap analysis
    pair_used = _loans_12m_by_pair(loan_history_df, week_start)

    # Build dynamic caps
    caps_by_pair = {}
    if not rules_df.empty:
        rules = rules_df.copy()
        rules["make"] = rules["make"].astype(str).str.strip()
        rules["rank"] = rules["rank"].astype(str).str.upper().str.replace("PLUS", "+").str.replace(" ", "")

        approved_norm = approved_df.copy()
        approved_norm['rank_norm'] = approved_norm['rank'].astype(str).str.upper().str.replace("PLUS", "+").str.replace(" ", "")

        merged = approved_norm.merge(
            rules[["make", "rank", "loan_cap_per_year"]],
            left_on=["make", "rank_norm"],
            right_on=["make", "rank"],
            how="left"
        )

        merged["cap_dyn"] = merged["loan_cap_per_year"].map(_cap_from_rules)
        caps_by_pair = {(r.person_id, r.make): int(r.cap_dyn) for r in merged.itertuples(index=False) if pd.notna(r.cap_dyn)}

    print(f"   - Tier cap rules: {len(caps_by_pair)}")

    # Analyze each pairing
    detailed_results = []

    for _, vehicle in vehicles_df.iterrows():
        vin = vehicle['vin']
        make = vehicle['make']

        # Get partners approved for this make
        make_partners = approved_df[approved_df['make'] == make]

        for _, partner in make_partners.iterrows():
            person_id = partner['person_id']
            rank = partner['rank']

            # Check constraints
            tier_cap = caps_by_pair.get((person_id, make), 0)
            tier_usage = pair_used.get((person_id, make), 0)
            tier_cap_ok = tier_usage < tier_cap if tier_cap > 0 else False

            if tier_cap == 0:
                reason = f"Tier cap = 0 (rank {rank} not allowed)"
            elif tier_usage >= tier_cap:
                reason = f"Over tier cap: {tier_usage}/{tier_cap} loans in 12 months"
            else:
                reason = f"ELIGIBLE: {tier_usage}/{tier_cap} tier usage, rank {rank}"

            detailed_results.append({
                'vin_short': vin[-8:],
                'vin': vin,
                'person_id': person_id,
                'make': make,
                'rank': rank,
                'tier_cap': tier_cap,
                'tier_usage': tier_usage,
                'tier_cap_ok': tier_cap_ok,
                'detailed_reason': reason
            })

    # Convert to DataFrame and export
    results_df = pd.DataFrame(detailed_results)

    # Summary
    eligible_count = results_df['tier_cap_ok'].sum()
    total_count = len(results_df)

    print(f"\nSAMPLE ANALYSIS RESULTS:")
    print(f"   - Total pairings analyzed: {total_count:,}")
    print(f"   - Eligible (tier cap OK): {eligible_count} ({eligible_count/total_count*100:.1f}%)")
    print(f"   - Rejected: {total_count - eligible_count} ({(total_count-eligible_count)/total_count*100:.1f}%)")

    # Export
    output_file = "exact_constraint_analysis.csv"
    results_df.to_csv(output_file, index=False)
    print(f"\n📁 Exact constraint analysis exported to: {output_file}")

    # Show samples
    print(f"\nSample results:")
    print(f"\nELIGIBLE pairings:")
    eligible_sample = results_df[results_df['tier_cap_ok'] == True].head(5)
    for _, row in eligible_sample.iterrows():
        print(f"   {row['vin_short']} + Partner {row['person_id']} ({row['make']}, {row['rank']}) → {row['detailed_reason']}")

    print(f"\nREJECTED pairings:")
    rejected_sample = results_df[results_df['tier_cap_ok'] == False].head(5)
    for _, row in rejected_sample.iterrows():
        print(f"   {row['vin_short']} + Partner {row['person_id']} ({row['make']}, {row['rank']}) → {row['detailed_reason']}")

    print(f"\n✅ Exact constraint analysis complete")


if __name__ == "__main__":
    asyncio.run(simple_detailed_analysis())