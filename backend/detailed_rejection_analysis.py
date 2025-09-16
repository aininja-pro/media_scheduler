"""
Detailed rejection analysis with EXACT constraint values and reasons.
"""

import asyncio
import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from app.services.database import db_service
from app.solver.greedy_assign import _loans_12m_by_pair, _cap_from_rules
from app.etl.availability import build_availability_grid
from app.etl.cooldown import compute_cooldown_flags


async def detailed_rejection_analysis():
    """Generate detailed rejection analysis with exact constraint values."""

    print("=" * 80)
    print("DETAILED REJECTION ANALYSIS - Every Constraint Checked")
    print("=" * 80)

    office = "Los Angeles"
    week_start = "2025-09-22"

    # Get all base data
    print("Loading complete dataset...")

    # LA vehicles
    vehicles_response = db_service.client.table('vehicles').select('*').eq('office', office).execute()
    vehicles_df = pd.DataFrame(vehicles_response.data) if vehicles_response.data else pd.DataFrame()

    # ALL approved makes with pagination
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

    # Current activity
    activity_response = db_service.client.table('current_activity').select('*').execute()
    activity_df = pd.DataFrame(activity_response.data) if activity_response.data else pd.DataFrame()

    # Rules
    rules_response = db_service.client.table('rules').select('*').execute()
    rules_df = pd.DataFrame(rules_response.data) if rules_response.data else pd.DataFrame()

    # ALL loan history with pagination
    all_loan_history = []
    limit = 1000
    offset = 0
    while True:
        loan_response = db_service.client.table('loan_history').select('*').range(offset, offset + limit - 1).execute()
        if not loan_response.data:
            break
        all_loan_history.extend(loan_response.data)
        offset += limit
        if len(loan_response.data) < limit:
            break

    loan_history_df = pd.DataFrame(all_loan_history)

    # Ops capacity
    ops_response = db_service.client.table('ops_capacity').select('*').execute()
    ops_capacity_df = pd.DataFrame(ops_response.data) if ops_response.data else pd.DataFrame()

    print(f"Dataset loaded:")
    print(f"   - Vehicles: {len(vehicles_df)}")
    print(f"   - Approved makes: {len(approved_makes_df):,}")
    print(f"   - Loan history: {len(loan_history_df):,}")
    print(f"   - Rules: {len(rules_df)}")

    # Prepare constraint data
    print(f"\nPreparing constraint analysis...")

    # Convert dates
    for date_col in ['in_service_date', 'expected_turn_in_date']:
        if date_col in vehicles_df.columns:
            vehicles_df[date_col] = pd.to_datetime(vehicles_df[date_col], errors='coerce').dt.date

    if not activity_df.empty:
        for date_col in ['start_date', 'end_date']:
            if date_col in activity_df.columns:
                activity_df[date_col] = pd.to_datetime(activity_df[date_col], errors='coerce').dt.date

    if not loan_history_df.empty:
        for date_col in ['start_date', 'end_date']:
            if date_col in loan_history_df.columns:
                loan_history_df[date_col] = pd.to_datetime(loan_history_df[date_col], errors='coerce').dt.date

    # Build availability grid
    availability_grid_df = build_availability_grid(
        vehicles_df=vehicles_df,
        activity_df=activity_df,
        week_start=week_start,
        office=office
    )

    # Compute cooldown flags
    cooldown_df = compute_cooldown_flags(
        loan_history_df=loan_history_df,
        rules_df=rules_df,
        week_start=week_start,
        default_days=60
    )

    # Build tier cap lookup
    pair_used = _loans_12m_by_pair(loan_history_df, week_start)

    # Build dynamic caps lookup
    la_vehicle_makes = set(vehicles_df['make'].unique())
    la_approved = approved_makes_df[approved_makes_df['make'].isin(la_vehicle_makes)].copy()

    # Normalize rank for rules lookup
    la_approved['rank_norm'] = la_approved['rank'].astype(str).str.upper().str.replace("PLUS", "+").str.replace(" ", "")

    caps_by_pair = {}
    if not rules_df.empty:
        rules = rules_df.copy()
        rules["make"] = rules["make"].astype(str).str.strip()
        rules["rank"] = rules["rank"].astype(str).str.upper().str.replace("PLUS", "+").str.replace(" ", "")

        merged = la_approved.merge(
            rules[["make", "rank", "loan_cap_per_year"]],
            left_on=["make", "rank_norm"],
            right_on=["make", "rank"],
            how="left"
        )

        merged["cap_dyn"] = merged["loan_cap_per_year"].map(_cap_from_rules)
        caps_by_pair = {(r.person_id, r.make): int(r.cap_dyn) for r in merged.itertuples(index=False)}

    # Get LA capacity
    la_capacity = 15  # Default
    if not ops_capacity_df.empty:
        la_cap_row = ops_capacity_df[ops_capacity_df['office'] == office]
        if not la_cap_row.empty:
            la_capacity = int(la_cap_row['drivers_per_day'].iloc[0])

    print(f"Constraint values:")
    print(f"   - LA daily capacity: {la_capacity} drivers/day")
    print(f"   - Cooldown period: 60 days")
    print(f"   - Dynamic tier caps: {len(caps_by_pair)} partner-make rules")

    # Now analyze EVERY pairing with detailed reasons
    detailed_analysis = []

    # Take first 1000 for detailed analysis (representative sample)
    sample_approved = la_approved.head(1000)
    sample_vehicles = vehicles_df.head(50)  # 50 vehicles for manageable output

    print(f"\nAnalyzing {len(sample_approved)} × {len(sample_vehicles)} = {len(sample_approved) * len(sample_vehicles):,} pairings in detail...")

    for _, vehicle in sample_vehicles.iterrows():
        vin = vehicle['vin']
        make = vehicle['make']
        model = vehicle.get('model', '')

        # Check vehicle availability first
        vin_availability = availability_grid_df[availability_grid_df['vin'] == vin]
        if vin_availability.empty:
            available_days = 0
            vehicle_available = False
        else:
            available_days = vin_availability['available'].sum()
            vehicle_available = available_days >= 7

        # Get partners approved for this make
        make_approved = sample_approved[sample_approved['make'] == make]

        for _, partner in make_approved.iterrows():
            person_id = partner['person_id']
            rank = partner['rank']

            # Initialize detailed result
            result = {
                'vin': vin,
                'vin_short': vin[-8:],
                'person_id': person_id,
                'make': make,
                'model': model,
                'rank': rank,
                'available_days': available_days,
                'vehicle_available': vehicle_available,
                'cooldown_ok': 'unknown',
                'tier_cap': 'unknown',
                'tier_usage': 'unknown',
                'tier_cap_ok': 'unknown',
                'final_result': 'unknown',
                'detailed_reason': 'unknown'
            }

            # Check vehicle availability constraint
            if not vehicle_available:
                result['final_result'] = 'REJECTED'
                result['detailed_reason'] = f'Vehicle only available {available_days}/7 days (need 7)'
                detailed_analysis.append(result)
                continue

            # Check cooldown constraint
            cooldown_match = cooldown_df[
                (cooldown_df['person_id'] == person_id) &
                (cooldown_df['make'] == make)
            ]

            if cooldown_match.empty:
                result['cooldown_ok'] = True  # No history = no cooldown
                cooldown_reason = "No loan history"
            else:
                cooldown_ok = cooldown_match['cooldown_ok'].iloc[0]
                result['cooldown_ok'] = cooldown_ok
                if cooldown_ok:
                    cooldown_reason = "Cooldown expired"
                else:
                    cooldown_until = cooldown_match['cooldown_until'].iloc[0]
                    cooldown_reason = f"Cooldown until {cooldown_until}"

            if not result['cooldown_ok']:
                result['final_result'] = 'REJECTED'
                result['detailed_reason'] = f'Cooldown blocked: {cooldown_reason}'
                detailed_analysis.append(result)
                continue

            # Check tier cap constraint
            cap_dyn = caps_by_pair.get((person_id, make), 0)
            used_pair = pair_used.get((person_id, make), 0)

            result['tier_cap'] = cap_dyn
            result['tier_usage'] = used_pair
            result['tier_cap_ok'] = used_pair < cap_dyn

            if cap_dyn == 0:
                result['final_result'] = 'REJECTED'
                result['detailed_reason'] = f'Tier cap = 0 (no assignments allowed for {rank} rank)'
            elif used_pair >= cap_dyn:
                result['final_result'] = 'REJECTED'
                result['detailed_reason'] = f'Tier cap exceeded: {used_pair}/{cap_dyn} loans in 12 months'
            else:
                result['final_result'] = 'ELIGIBLE'
                result['detailed_reason'] = f'PASSES ALL CONSTRAINTS: {used_pair}/{cap_dyn} tier, cooldown OK, {available_days}/7 days'

            detailed_analysis.append(result)

    # Convert to DataFrame and export
    analysis_df = pd.DataFrame(detailed_analysis)

    # Summary
    result_summary = analysis_df['final_result'].value_counts()
    print(f"\nDETAILED RESULTS SUMMARY:")
    for result, count in result_summary.items():
        pct = (count / len(analysis_df)) * 100
        print(f"   {result}: {count:,} ({pct:.1f}%)")

    # Export detailed analysis
    output_file = "detailed_rejection_analysis.csv"
    analysis_df.to_csv(output_file, index=False)
    print(f"\n📁 Detailed analysis exported to: {output_file}")

    # Show samples by category
    print(f"\nSample detailed rejections:")

    for result_type in ['REJECTED', 'ELIGIBLE']:
        if result_type in result_summary.index:
            print(f"\n{result_type} EXAMPLES:")
            sample = analysis_df[analysis_df['final_result'] == result_type].head(5)
            for _, row in sample.iterrows():
                print(f"   {row['vin_short']} + Partner {row['person_id']} ({row['make']}, {row['rank']}) → {row['detailed_reason']}")

    print(f"\n✅ Detailed analysis complete - check {output_file} for all {len(analysis_df):,} pairings")


if __name__ == "__main__":
    asyncio.run(detailed_rejection_analysis())