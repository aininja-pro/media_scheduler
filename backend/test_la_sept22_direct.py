"""
Direct test of Los Angeles 9/22 with fallback caps - bypassing ETL integration issues.
"""

import asyncio
import pandas as pd
import time
from datetime import datetime, timedelta

from app.services.database import db_service
from app.solver.candidates import build_weekly_candidates
from app.solver.scoring import compute_candidate_scores
from app.solver.greedy_assign import generate_week_schedule
from app.etl.availability import build_availability_grid
from app.etl.cooldown import compute_cooldown_flags


async def test_la_sept22_direct():
    """Direct test of LA 9/22 with new fallback caps."""

    print("=" * 80)
    print("DIRECT LOS ANGELES TEST - 9/22/2025 with Fallback Caps")
    print("=" * 80)

    office = "Los Angeles"
    week_start = "2025-09-22"

    total_start = time.time()

    # Get base data directly
    print("Loading data directly from Supabase...")

    # LA vehicles
    vehicles_response = db_service.client.table('vehicles').select('*').eq('office', office).execute()
    vehicles_df = pd.DataFrame(vehicles_response.data) if vehicles_response.data else pd.DataFrame()

    # Current activity
    activity_response = db_service.client.table('current_activity').select('*').execute()
    activity_df = pd.DataFrame(activity_response.data) if activity_response.data else pd.DataFrame()

    # Fix activity column name for ETL function
    if not activity_df.empty and 'vehicle_vin' in activity_df.columns:
        activity_df['vin'] = activity_df['vehicle_vin']

    # Get ALL approved makes
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

    # Get ALL loan history
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

    # Get other data
    rules_response = db_service.client.table('rules').select('*').execute()
    rules_df = pd.DataFrame(rules_response.data) if rules_response.data else pd.DataFrame()

    ops_response = db_service.client.table('ops_capacity').select('*').execute()
    ops_capacity_df = pd.DataFrame(ops_response.data) if ops_response.data else pd.DataFrame()

    partners_response = db_service.client.table('media_partners').select('*').execute()
    partners_df = pd.DataFrame(partners_response.data) if partners_response.data else pd.DataFrame()

    print(f"Data loaded:")
    print(f"   - Vehicles: {len(vehicles_df)}")
    print(f"   - Approved makes: {len(approved_makes_df):,}")
    print(f"   - Loan history: {len(loan_history_df):,}")
    print(f"   - Rules: {len(rules_df)}")

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

    # STAGE 1: Build availability and candidates
    stage1_start = time.time()

    # Build availability grid
    availability_grid_df = build_availability_grid(
        vehicles_df=vehicles_df,
        activity_df=activity_df,
        week_start=week_start,
        office=office
    )

    # Convert to candidate input format
    availability_records = []
    if not availability_grid_df.empty:
        vehicle_lookup = vehicles_df.set_index('vin')[['make', 'model']].to_dict('index')

        for _, row in availability_grid_df.iterrows():
            vin = row['vin']
            vehicle_info = vehicle_lookup.get(vin, {'make': '', 'model': ''})

            availability_records.append({
                'vin': vin,
                'date': row['day'].strftime('%Y-%m-%d'),
                'market': office,
                'make': vehicle_info.get('make', ''),
                'model': vehicle_info.get('model', ''),
                'available': row['available']
            })

    availability_df = pd.DataFrame(availability_records)

    # Compute cooldown with 30-day period
    cooldown_df = compute_cooldown_flags(
        loan_history_df=loan_history_df,
        rules_df=rules_df,
        week_start=week_start,
        default_days=30  # Changed from 45 to 30 days
    )

    # Filter approved makes to LA vehicle makes
    la_vehicle_makes = set(vehicles_df['make'].unique())
    la_approved = approved_makes_df[approved_makes_df['make'].isin(la_vehicle_makes)]

    # Create minimal publication data structure
    publication_df = pd.DataFrame([
        {'person_id': pid, 'make': make, 'publication_rate_observed': None, 'supported': False, 'coverage': 0.0}
        for pid, make in la_approved[['person_id', 'make']].drop_duplicates().values
    ])

    # Build candidates
    candidates_df = build_weekly_candidates(
        availability_df=availability_df,
        cooldown_df=cooldown_df,
        publication_df=publication_df,
        week_start=week_start,
        eligibility_df=la_approved,
        min_available_days=7
    )

    stage1_time = time.time() - stage1_start

    print(f"\nSTAGE 1 Results:")
    print(f"   - Availability records: {len(availability_df):,}")
    print(f"   - Cooldown combinations: {len(cooldown_df):,}")
    print(f"   - LA approved makes: {len(la_approved):,}")
    print(f"   - Candidates generated: {len(candidates_df):,}")
    print(f"   - Duration: {stage1_time:.3f}s")

    if candidates_df.empty:
        print("❌ No candidates generated")
        return

    # STAGE 2: Score candidates
    stage2_start = time.time()

    scored_candidates = compute_candidate_scores(
        candidates_df=candidates_df,
        partner_rank_df=approved_makes_df,
        partners_df=partners_df,
        publication_df=publication_df
    )

    stage2_time = time.time() - stage2_start

    print(f"\nSTAGE 2 Results:")
    print(f"   - Scored candidates: {len(scored_candidates):,}")
    print(f"   - Score range: {scored_candidates['score'].min()}-{scored_candidates['score'].max()}")
    print(f"   - Duration: {stage2_time:.3f}s")

    # STAGE 3: Generate assignments with NEW fallback caps
    stage3_start = time.time()

    schedule_df = generate_week_schedule(
        candidates_scored_df=scored_candidates,
        loan_history_df=loan_history_df,
        ops_capacity_df=ops_capacity_df,
        office=office,
        week_start=week_start,
        rules_df=rules_df  # Use fallback caps for missing rules
    )

    stage3_time = time.time() - stage3_start
    total_time = time.time() - total_start

    print(f"\nSTAGE 3 Results with NEW FALLBACK CAPS:")
    print(f"   - Schedule rows: {len(schedule_df):,}")
    print(f"   - Duration: {stage3_time:.3f}s")

    if not schedule_df.empty:
        weekly_assignments = schedule_df.drop_duplicates(['vin', 'person_id'])
        unique_partners = weekly_assignments['person_id'].nunique()
        unique_makes = weekly_assignments['make'].nunique()

        print(f"   - Weekly assignments: {len(weekly_assignments)}")
        print(f"   - Unique partners: {unique_partners}")
        print(f"   - Unique makes: {unique_makes}")

        assignment_rate = len(weekly_assignments) / len(scored_candidates) * 100
        print(f"   - Assignment rate: {assignment_rate:.3f}%")

        # Show assignments by make
        make_assignments = weekly_assignments['make'].value_counts()
        print(f"   - Assignments by make: {dict(make_assignments)}")

        # Show top assignments
        print(f"\n🏆 Top assignments with fallback caps:")
        for _, assignment in weekly_assignments.head(10).iterrows():
            vin_short = str(assignment['vin'])[-8:]
            print(f"     {vin_short} → Partner {assignment['person_id']} ({assignment['make']}, Score: {assignment['score']})")

    else:
        print("❌ No assignments generated even with fallback caps")

    print(f"\n⏱️ Total Time: {total_time:.3f}s")
    print(f"✅ Direct test complete with B=4, UNRANKED=3 fallback caps")


if __name__ == "__main__":
    asyncio.run(test_la_sept22_direct())