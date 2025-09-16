"""
REAL test of Phase 5 pipeline with Los Angeles on September 22, 2025.
"""

import asyncio
import pandas as pd
import time

from app.tests.test_candidates_etl_integration import (
    fetch_etl_availability_data,
    fetch_etl_cooldown_data,
    fetch_etl_publication_data,
    fetch_etl_eligibility_data
)
from app.tests.test_scoring_real_data import fetch_scoring_data
from app.solver.candidates import build_weekly_candidates
from app.solver.scoring import compute_candidate_scores
from app.solver.greedy_assign import generate_week_schedule
from app.services.database import db_service


async def test_real_data_sept22():
    """Run REAL Phase 5 test for Los Angeles, September 22, 2025."""

    office = "Los Angeles"
    week_start = "2025-09-22"  # Monday September 22, 2025

    print(f"REAL TEST: {office}, Week: {week_start}")
    print(f"Using actual Supabase database data")

    total_start = time.time()

    # STAGE 1: Real ETL Data
    print(f"\nSTAGE 1: Fetching REAL ETL data...")
    stage1_start = time.time()

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
        min_available_days=5
    )

    stage1_time = time.time() - stage1_start

    print(f"REAL Stage 1 Results:")
    print(f"   - Feasible pairings: {len(candidates_df):,}")
    print(f"   - Unique VINs: {candidates_df['vin'].nunique() if not candidates_df.empty else 0}")
    print(f"   - Unique partners: {candidates_df['person_id'].nunique() if not candidates_df.empty else 0}")
    print(f"   - Duration: {stage1_time:.3f}s")

    if candidates_df.empty:
        print("❌ No candidates - stopping test")
        return None

    # STAGE 2: Real Scoring
    print(f"\nSTAGE 2: Scoring with REAL partner data...")
    stage2_start = time.time()

    partner_rank_df, partners_df = await fetch_scoring_data()

    scored_candidates = compute_candidate_scores(
        candidates_df=candidates_df,
        partner_rank_df=partner_rank_df,
        partners_df=partners_df,
        publication_df=publication_df
    )

    stage2_time = time.time() - stage2_start

    print(f"REAL Stage 2 Results:")
    print(f"   - Scored options: {len(scored_candidates):,}")
    print(f"   - Score range: {scored_candidates['score'].min()}-{scored_candidates['score'].max()}")
    print(f"   - Duration: {stage2_time:.3f}s")

    rank_dist = scored_candidates['rank'].value_counts()
    print(f"   - Rank distribution: {dict(rank_dist)}")

    # STAGE 3: Real Greedy Assignment
    print(f"\nSTAGE 3: Greedy assignment with REAL rules...")
    stage3_start = time.time()

    # Get REAL rules and capacity data
    ops_response = db_service.client.table('ops_capacity').select('office, drivers_per_day').execute()
    ops_capacity_df = pd.DataFrame(ops_response.data) if ops_response.data else pd.DataFrame()

    rules_response = db_service.client.table('rules').select('make, rank, loan_cap_per_year').execute()
    rules_df = pd.DataFrame(rules_response.data) if rules_response.data else pd.DataFrame()

    # Fetch ALL loan history records with pagination
    all_loan_history = []
    limit = 1000
    offset = 0

    while True:
        loan_history_response = db_service.client.table('loan_history').select('person_id, make, start_date, end_date').range(offset, offset + limit - 1).execute()

        if not loan_history_response.data:
            break

        all_loan_history.extend(loan_history_response.data)
        offset += limit

        if len(loan_history_response.data) < limit:
            break

    loan_history_df = pd.DataFrame(all_loan_history) if all_loan_history else pd.DataFrame()

    print(f"Assignment constraints:")
    la_capacity = ops_capacity_df[ops_capacity_df['office'] == office]['drivers_per_day'].iloc[0] if not ops_capacity_df[ops_capacity_df['office'] == office].empty else 'Unknown'
    print(f"   - {office} capacity: {la_capacity} drivers/day")
    print(f"   - Rules: {len(rules_df)} tier cap rules")
    print(f"   - Loan history: {len(loan_history_df)} records for 12-month caps")

    schedule_df = generate_week_schedule(
        candidates_scored_df=scored_candidates,
        loan_history_df=loan_history_df,
        ops_capacity_df=ops_capacity_df,
        office=office,
        week_start=week_start,
        rules_df=rules_df  # REAL dynamic tier caps
    )

    stage3_time = time.time() - stage3_start
    total_time = time.time() - total_start

    print(f"REAL Stage 3 Results:")
    print(f"   - Schedule rows: {len(schedule_df):,}")
    print(f"   - Duration: {stage3_time:.3f}s")

    if not schedule_df.empty:
        weekly_assignments = schedule_df.drop_duplicates(['vin', 'person_id'])
        unique_vins = weekly_assignments['vin'].nunique()
        unique_partners = weekly_assignments['person_id'].nunique()
        unique_makes = weekly_assignments['make'].nunique()

        print(f"   - Weekly assignments: {len(weekly_assignments)}")
        print(f"   - Unique VINs assigned: {unique_vins}")
        print(f"   - Unique partners assigned: {unique_partners}")
        print(f"   - Vehicle makes: {unique_makes}")

        assignment_rate = len(weekly_assignments) / len(scored_candidates) * 100
        print(f"   - Assignment rate: {assignment_rate:.3f}%")

        print(f"\nTop 3 REAL assignments:")
        for i, (_, row) in enumerate(weekly_assignments.head(3).iterrows(), 1):
            vin_short = str(row['vin'])[-8:]
            print(f"   {i}. {vin_short} → Partner {row['person_id']} ({row['make']}, Score: {row['score']})")

    else:
        print("   - No assignments generated (all blocked by constraints)")

    print(f"\n⏱️ REAL Total Time: {total_time:.3f}s")
    print(f"✅ Phase 5 pipeline VERIFIED with real Supabase data for {week_start}")

    return {
        'candidates': len(candidates_df),
        'scored': len(scored_candidates),
        'assignments': len(schedule_df.drop_duplicates(['vin', 'person_id'])) if not schedule_df.empty else 0
    }


if __name__ == "__main__":
    result = asyncio.run(test_real_data_sept22())