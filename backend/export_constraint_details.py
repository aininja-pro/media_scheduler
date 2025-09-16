"""
Export exact constraint details for every pairing.
"""

import asyncio
import pandas as pd
from app.services.database import db_service
from app.solver.greedy_assign import _loans_12m_by_pair, _cap_from_rules


async def export_constraint_details():
    """Export exact constraint values for debugging."""

    print("Exporting constraint details...")

    office = "Los Angeles"
    week_start = "2025-09-22"

    # Get small sample for detailed analysis
    vehicles_response = db_service.client.table('vehicles').select('vin, make, model').eq('office', office).limit(5).execute()
    vehicles_df = pd.DataFrame(vehicles_response.data)

    # Get sample partners
    approved_response = db_service.client.table('approved_makes').select('person_id, make, rank').limit(10).execute()
    approved_df = pd.DataFrame(approved_response.data)

    # Get rules
    rules_response = db_service.client.table('rules').select('*').execute()
    rules_df = pd.DataFrame(rules_response.data)

    # Get ALL loan history
    all_loans = []
    limit = 1000
    offset = 0
    while True:
        loan_response = db_service.client.table('loan_history').select('person_id, make, start_date, end_date').range(offset, offset + limit - 1).execute()
        if not loan_response.data:
            break
        all_loans.extend(loan_response.data)
        offset += limit
        if len(loan_response.data) < limit:
            break

    loan_history_df = pd.DataFrame(all_loans)

    # Convert dates
    for date_col in ['start_date', 'end_date']:
        if date_col in loan_history_df.columns:
            loan_history_df[date_col] = pd.to_datetime(loan_history_df[date_col], errors='coerce').dt.date

    # Get 12-month usage
    pair_used = _loans_12m_by_pair(loan_history_df, week_start)

    # Build tier caps
    caps_by_pair = {}
    if not rules_df.empty and not approved_df.empty:
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

        for _, row in merged.iterrows():
            if pd.notna(row['loan_cap_per_year']):
                cap = _cap_from_rules(row['loan_cap_per_year'])
                caps_by_pair[(row['person_id'], row['make'])] = cap

    print(f"Analysis data:")
    print(f"   - Vehicles: {len(vehicles_df)}")
    print(f"   - Partners: {len(approved_df)}")
    print(f"   - 12-month usage data: {len(pair_used)} partner-make pairs")
    print(f"   - Tier cap rules: {len(caps_by_pair)} partner-make pairs")

    # Create detailed pairing analysis
    results = []

    for _, vehicle in vehicles_df.iterrows():
        vin = vehicle['vin']
        make = vehicle['make']
        model = vehicle.get('model', '')

        # Get partners approved for this make
        make_partners = approved_df[approved_df['make'] == make]

        for _, partner in make_partners.iterrows():
            person_id = partner['person_id']
            rank = partner['rank']

            # Get exact constraint values
            tier_cap = caps_by_pair.get((person_id, make), 0)
            tier_usage = pair_used.get((person_id, make), 0)

            # Determine specific rejection reason
            if tier_cap == 0:
                status = "REJECTED"
                reason = f"Tier cap = 0 for rank {rank}"
            elif tier_usage >= tier_cap:
                status = "REJECTED"
                reason = f"Over tier cap: used {tier_usage}/{tier_cap} in 12 months"
            else:
                status = "ELIGIBLE"
                reason = f"Under tier cap: {tier_usage}/{tier_cap}, rank {rank}"

            results.append({
                'vin': vin[-8:],
                'full_vin': vin,
                'person_id': person_id,
                'make': make,
                'model': model,
                'rank': rank,
                'tier_cap_limit': tier_cap,
                'tier_usage_12m': tier_usage,
                'status': status,
                'detailed_reason': reason
            })

    # Export to CSV
    results_df = pd.DataFrame(results)
    output_file = "exact_constraint_details.csv"
    results_df.to_csv(output_file, index=False)

    # Summary
    status_counts = results_df['status'].value_counts()
    total = len(results_df)

    print(f"\nRESULTS:")
    for status, count in status_counts.items():
        pct = (count / total) * 100
        print(f"   {status}: {count}/{total} ({pct:.1f}%)")

    print(f"\nSample ELIGIBLE pairings:")
    eligible = results_df[results_df['status'] == 'ELIGIBLE']
    for _, row in eligible.head(5).iterrows():
        print(f"   {row['vin']} + Partner {row['person_id']} ({row['make']}, {row['rank']}) → {row['detailed_reason']}")

    print(f"\nSample REJECTED pairings:")
    rejected = results_df[results_df['status'] == 'REJECTED']
    for _, row in rejected.head(5).iterrows():
        print(f"   {row['vin']} + Partner {row['person_id']} ({row['make']}, {row['rank']}) → {row['detailed_reason']}")

    print(f"\n📁 Detailed constraint analysis exported to: {output_file}")
    print(f"✅ Analysis complete - {total} pairings analyzed")


if __name__ == "__main__":
    asyncio.run(export_constraint_details())