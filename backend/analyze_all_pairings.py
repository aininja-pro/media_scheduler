"""
Generate comprehensive analysis of ALL potential VIN-partner pairings
with detailed rejection reasons for debugging.
"""

import asyncio
import pandas as pd
import time
from datetime import datetime, timedelta

from app.tests.test_candidates_etl_integration import (
    fetch_etl_availability_data,
    fetch_etl_cooldown_data,
    fetch_etl_publication_data,
    fetch_etl_eligibility_data
)
from app.tests.test_scoring_real_data import fetch_scoring_data
from app.solver.candidates import build_weekly_candidates
from app.solver.scoring import compute_candidate_scores
from app.solver.greedy_assign import generate_week_schedule, _loans_12m_by_pair, _cap_from_rules
from app.services.database import db_service


async def analyze_all_pairings():
    """Generate detailed rejection analysis for every potential pairing."""

    print("=" * 80)
    print("COMPREHENSIVE PAIRING ANALYSIS - Los Angeles 9/22/2025")
    print("Analyzing EVERY potential VIN-partner combination with rejection reasons")
    print("=" * 80)

    office = "Los Angeles"
    week_start = "2025-09-22"

    # Get all base data
    print("Fetching all base data...")

    # Get LA vehicles
    vehicles_response = db_service.client.table('vehicles').select('vin, make, model').eq('office', office).execute()
    vehicles_df = pd.DataFrame(vehicles_response.data) if vehicles_response.data else pd.DataFrame()

    # Get ALL approved makes (with pagination)
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

    print(f"Data loaded:")
    print(f"   - LA vehicles: {len(vehicles_df)}")
    print(f"   - Total approved makes: {len(approved_makes_df)}")

    # Filter approved makes to LA vehicle makes only
    la_vehicle_makes = set(vehicles_df['make'].unique())
    la_approved = approved_makes_df[approved_makes_df['make'].isin(la_vehicle_makes)]

    print(f"   - LA-relevant approvals: {len(la_approved)}")

    # Generate ALL possible pairings
    all_pairings = []

    for _, vehicle in vehicles_df.iterrows():
        vin = vehicle['vin']
        make = vehicle['make']
        model = vehicle.get('model', '')

        # Get all partners approved for this make
        approved_partners = la_approved[la_approved['make'] == make]

        for _, partner in approved_partners.iterrows():
            person_id = partner['person_id']
            rank = partner['rank']

            all_pairings.append({
                'vin': vin,
                'person_id': person_id,
                'make': make,
                'model': model,
                'rank': rank,
                'pairing_id': f"{vin}_{person_id}"
            })

    pairings_df = pd.DataFrame(all_pairings)

    print(f"   - Total theoretical pairings: {len(pairings_df):,}")

    # Now run Phase 5 and track rejections
    print(f"\nRunning Phase 5 pipeline with rejection tracking...")

    # Run actual pipeline
    availability_df, cooldown_df, publication_df, eligibility_df = await asyncio.gather(
        fetch_etl_availability_data(office, week_start),
        fetch_etl_cooldown_data(week_start),
        fetch_etl_publication_data(),
        fetch_etl_eligibility_data()
    )

    candidates_df = build_weekly_candidates(
        availability_df=availability_df,
        cooldown_df=cooldown_df,
        publication_df=publication_df,
        week_start=week_start,
        eligibility_df=eligibility_df if not eligibility_df.empty else None,
        min_available_days=7
    )

    print(f"   - Candidates after Stage 1: {len(candidates_df):,}")

    # Add rejection reasons
    pairings_df['rejection_reason'] = 'unknown'
    pairings_df['assigned'] = False

    # Check which made it through candidate generation
    if not candidates_df.empty:
        candidate_pairs = set(zip(candidates_df['vin'], candidates_df['person_id']))

        for idx, row in pairings_df.iterrows():
            pair_key = (row['vin'], row['person_id'])
            if pair_key in candidate_pairs:
                pairings_df.at[idx, 'rejection_reason'] = 'passed_stage1'
            else:
                # Determine why it was rejected in Stage 1
                # Check availability
                vin_availability = availability_df[availability_df['vin'] == row['vin']]
                if vin_availability.empty:
                    pairings_df.at[idx, 'rejection_reason'] = 'vehicle_not_available'
                else:
                    available_days = vin_availability['available'].sum()
                    if available_days < 7:
                        pairings_df.at[idx, 'rejection_reason'] = f'insufficient_availability_{available_days}_days'
                    else:
                        # Check cooldown
                        cooldown_match = cooldown_df[
                            (cooldown_df['person_id'] == row['person_id']) &
                            (cooldown_df['make'] == row['make'])
                        ]
                        if not cooldown_match.empty and not cooldown_match['cooldown_ok'].iloc[0]:
                            pairings_df.at[idx, 'rejection_reason'] = 'cooldown_blocked'
                        else:
                            pairings_df.at[idx, 'rejection_reason'] = 'other_stage1_filter'

    # Score the candidates that made it through Stage 1
    if not candidates_df.empty:
        partner_rank_df, partners_df = await fetch_scoring_data()

        scored_candidates = compute_candidate_scores(
            candidates_df=candidates_df,
            partner_rank_df=partner_rank_df,
            partners_df=partners_df,
            publication_df=publication_df
        )

        # Run greedy assignment to see final assignments
        ops_response = db_service.client.table('ops_capacity').select('office, drivers_per_day').execute()
        ops_capacity_df = pd.DataFrame(ops_response.data) if ops_response.data else pd.DataFrame()

        rules_response = db_service.client.table('rules').select('make, rank, loan_cap_per_year').execute()
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

        schedule_df = generate_week_schedule(
            candidates_scored_df=scored_candidates,
            loan_history_df=loan_history_df,
            ops_capacity_df=ops_capacity_df,
            office=office,
            week_start=week_start,
            rules_df=rules_df
        )

        # Mark assigned pairings
        if not schedule_df.empty:
            assigned_pairs = set(zip(schedule_df['vin'], schedule_df['person_id']))

            for idx, row in pairings_df.iterrows():
                pair_key = (row['vin'], row['person_id'])
                if pair_key in assigned_pairs:
                    pairings_df.at[idx, 'assigned'] = True
                    pairings_df.at[idx, 'rejection_reason'] = 'ASSIGNED'
                elif row['rejection_reason'] == 'passed_stage1':
                    # Made it through candidates but not assigned - check why
                    pairings_df.at[idx, 'rejection_reason'] = 'tier_cap_or_capacity_blocked'

    # Generate summary
    rejection_summary = pairings_df['rejection_reason'].value_counts()

    print(f"\nREJECTION ANALYSIS:")
    print(f"Total potential pairings: {len(pairings_df):,}")
    for reason, count in rejection_summary.items():
        pct = (count / len(pairings_df)) * 100
        print(f"   {reason}: {count:,} ({pct:.1f}%)")

    # Export to CSV
    output_file = "pairing_analysis_detailed.csv"
    pairings_df.to_csv(output_file, index=False)
    print(f"\n📁 Detailed analysis exported to: {output_file}")

    # Show sample of each rejection type
    print(f"\nSample rejections by type:")
    for reason in rejection_summary.head(5).index:
        sample = pairings_df[pairings_df['rejection_reason'] == reason].head(3)
        print(f"\n{reason.upper()}:")
        for _, row in sample.iterrows():
            print(f"   {row['vin'][-8:]} + Partner {row['person_id']} ({row['make']}, Rank {row['rank']})")

    return pairings_df


if __name__ == "__main__":
    result = asyncio.run(analyze_all_pairings())