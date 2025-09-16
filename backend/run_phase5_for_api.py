"""
Run the Phase 5 pipeline directly for API testing.
"""

import asyncio
import pandas as pd
import time
import sys
import os

# Add the backend directory to Python path
sys.path.append('/Users/richardrierson/Desktop/Projects/media_scheduler/backend')

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


async def run_phase5_pipeline(office: str, week_start: str, enable_tier_caps: bool = True):
    """Run the exact Phase 5 pipeline that works in our tests."""

    print(f"Running Phase 5 for {office}, week {week_start}, tier_caps={enable_tier_caps}")

    total_start = time.time()

    # STAGE 1: Get feasible pairings
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
    print(f"Stage 1: {len(candidates_df)} candidates in {stage1_time:.3f}s")

    if candidates_df.empty:
        return {"error": "No candidates generated"}

    # STAGE 2: Score candidates
    stage2_start = time.time()

    partner_rank_df, partners_df = await fetch_scoring_data()

    scored_candidates = compute_candidate_scores(
        candidates_df=candidates_df,
        partner_rank_df=partner_rank_df,
        partners_df=partners_df,
        publication_df=publication_df
    )

    stage2_time = time.time() - stage2_start
    print(f"Stage 2: {len(scored_candidates)} scored in {stage2_time:.3f}s")

    # STAGE 3: Generate assignments
    stage3_start = time.time()

    # Get additional data
    ops_response = db_service.client.table('ops_capacity').select('office, drivers_per_day').execute()
    ops_capacity_df = pd.DataFrame(ops_response.data) if ops_response.data else pd.DataFrame()

    rules_response = db_service.client.table('rules').select('make, rank, loan_cap_per_year').execute()
    rules_df = pd.DataFrame(rules_response.data) if rules_response.data else pd.DataFrame()

    loan_history_response = db_service.client.table('loan_history').select('person_id, make, start_date, end_date').order('created_at', desc=True).limit(5000).execute()
    loan_history_df = pd.DataFrame(loan_history_response.data) if loan_history_response.data else pd.DataFrame()

    schedule_df = generate_week_schedule(
        candidates_scored_df=scored_candidates,
        loan_history_df=loan_history_df,
        ops_capacity_df=ops_capacity_df,
        office=office,
        week_start=week_start,
        rules_df=rules_df if enable_tier_caps else None
    )

    stage3_time = time.time() - stage3_start
    total_time = time.time() - total_start

    print(f"Stage 3: {len(schedule_df)} schedule rows in {stage3_time:.3f}s")
    print(f"Total: {total_time:.3f}s")

    # Return structured data
    assignments = []
    if not schedule_df.empty:
        weekly_assignments = schedule_df.drop_duplicates(['vin', 'person_id'])

        for _, assignment in weekly_assignments.iterrows():
            partner_info = partners_df[partners_df['person_id'] == assignment['person_id']]
            partner_name = partner_info['name'].iloc[0] if not partner_info.empty else f"Partner {assignment['person_id']}"

            assignments.append({
                'vin': assignment['vin'],
                'person_id': assignment['person_id'],
                'partner_name': partner_name,
                'make': assignment['make'],
                'score': int(assignment['score'])
            })

    return {
        'office': office,
        'pipeline': {
            'stage1': {'candidate_count': len(candidates_df), 'duration': stage1_time},
            'stage2': {'scored_count': len(scored_candidates), 'duration': stage2_time},
            'stage3': {'assignment_count': len(assignments), 'duration': stage3_time}
        },
        'assignments': assignments,
        'constraint_toggles': {'tier_caps': enable_tier_caps}
    }


async def main():
    # Test both with and without tier caps
    print("=== WITH TIER CAPS ===")
    result_with = await run_phase5_pipeline("Los Angeles", "2025-09-15", enable_tier_caps=True)

    print("\n=== WITHOUT TIER CAPS ===")
    result_without = await run_phase5_pipeline("Los Angeles", "2025-09-15", enable_tier_caps=False)

    print(f"\nComparison:")
    print(f"With tier caps: {result_with['pipeline']['stage3']['assignment_count']} assignments")
    print(f"Without tier caps: {result_without['pipeline']['stage3']['assignment_count']} assignments")


if __name__ == "__main__":
    asyncio.run(main())