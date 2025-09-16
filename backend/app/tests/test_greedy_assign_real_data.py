"""
Real data integration test for greedy assignment algorithm.

This script tests the complete Phase 5 pipeline:
Step 1: Candidate generation → Step 2: Scoring → Step 3: Greedy assignment
"""

import asyncio
import pandas as pd
import time
import httpx
from datetime import datetime, timedelta

from app.solver.candidates import build_weekly_candidates
from app.solver.scoring import compute_candidate_scores
from app.solver.greedy_assign import generate_week_schedule
from app.services.database import db_service


async def fetch_ops_capacity_data() -> pd.DataFrame:
    """Fetch operations capacity data for daily limits."""
    print("Fetching ops capacity data...")

    try:
        ops_response = db_service.client.table('ops_capacity').select(
            'office, drivers_per_day'
        ).execute()

        ops_df = pd.DataFrame(ops_response.data) if ops_response.data else pd.DataFrame()
        print(f"✅ Ops capacity: {len(ops_df)} office records")

        if not ops_df.empty:
            for _, row in ops_df.iterrows():
                print(f"   {row['office']}: {row['drivers_per_day']} drivers/day")

        return ops_df

    except Exception as e:
        print(f"Error fetching ops capacity: {e}")
        return pd.DataFrame()


async def fetch_loan_history_for_tier_caps() -> pd.DataFrame:
    """Fetch loan history for 12-month tier cap calculations."""
    print("Fetching loan history for tier caps...")

    try:
        # Get recent loan history (last 18 months to ensure 12-month window coverage)
        loan_response = db_service.client.table('loan_history').select(
            'person_id, make, start_date, end_date'
        ).order('end_date', desc=True).execute()

        loan_df = pd.DataFrame(loan_response.data) if loan_response.data else pd.DataFrame()
        print(f"✅ Loan history: {len(loan_df)} records for tier cap calculation")

        return loan_df

    except Exception as e:
        print(f"Error fetching loan history: {e}")
        return pd.DataFrame()


async def test_complete_phase5_pipeline():
    """Test the complete Phase 5 pipeline with real data."""
    print("=" * 80)
    print("Testing COMPLETE Phase 5 Pipeline with Real Data")
    print("Step 1: Candidates → Step 2: Scoring → Step 3: Greedy Assignment")
    print("=" * 80)

    # Set up parameters
    today = datetime.now()
    days_since_monday = today.weekday()
    current_monday = (today - timedelta(days=days_since_monday)).date()
    week_start = current_monday.strftime('%Y-%m-%d')
    office = "Los Angeles"

    print(f"\nTarget: {office}, Week: {week_start}")

    total_start_time = time.time()

    # STEP 1: Generate Candidates (using ETL endpoints)
    print(f"\n" + "="*60)
    print("STEP 1: Candidate Generation")
    print("="*60)

    step1_start = time.time()

    # Use our ETL integration test
    from app.tests.test_candidates_etl_integration import (
        fetch_etl_availability_data,
        fetch_etl_cooldown_data,
        fetch_etl_publication_data,
        fetch_etl_eligibility_data
    )

    availability_df, cooldown_df, publication_df, eligibility_df = await asyncio.gather(
        fetch_etl_availability_data(office, week_start),
        fetch_etl_cooldown_data(week_start),
        fetch_etl_publication_data(),
        fetch_etl_eligibility_data()
    )

    if availability_df.empty or cooldown_df.empty or publication_df.empty:
        print("❌ Missing ETL data for candidate generation")
        return None

    candidates_df = build_weekly_candidates(
        availability_df=availability_df,
        cooldown_df=cooldown_df,
        publication_df=publication_df,
        week_start=week_start,
        eligibility_df=eligibility_df if not eligibility_df.empty else None,
        min_available_days=5
    )

    step1_time = time.time() - step1_start
    print(f"✅ Step 1 Complete: {len(candidates_df):,} candidates in {step1_time:.3f}s")

    if candidates_df.empty:
        print("❌ No candidates generated")
        return None

    # STEP 2: Score Candidates
    print(f"\n" + "="*60)
    print("STEP 2: Candidate Scoring")
    print("="*60)

    step2_start = time.time()

    # Fetch partner data for scoring
    from app.tests.test_scoring_real_data import fetch_scoring_data
    partner_rank_df, partners_df = await fetch_scoring_data()

    if partner_rank_df.empty or partners_df.empty:
        print("❌ Missing partner data for scoring")
        return None

    scored_candidates = compute_candidate_scores(
        candidates_df=candidates_df,
        partner_rank_df=partner_rank_df,
        partners_df=partners_df,
        publication_df=publication_df,
        rank_weights={"A+": 100, "A": 70, "B": 40, "C": 10},
        geo_bonus_points=10,
        history_bonus_points=5
    )

    step2_time = time.time() - step2_start
    print(f"✅ Step 2 Complete: {len(scored_candidates):,} scored candidates in {step2_time:.3f}s")

    # STEP 3: Greedy Assignment
    print(f"\n" + "="*60)
    print("STEP 3: Greedy Assignment")
    print("="*60)

    step3_start = time.time()

    # Fetch additional data for greedy assignment
    ops_capacity_df, loan_history_df = await asyncio.gather(
        fetch_ops_capacity_data(),
        fetch_loan_history_for_tier_caps()
    )

    if ops_capacity_df.empty:
        print("⚠️  No ops capacity data - using default limits")

    schedule_df = generate_week_schedule(
        candidates_scored_df=scored_candidates,
        loan_history_df=loan_history_df,
        ops_capacity_df=ops_capacity_df,
        office=office,
        week_start=week_start,
        rank_caps={"A+": 999, "A": 6, "B": 2, "C": 0}
    )

    step3_time = time.time() - step3_start
    total_time = time.time() - total_start_time

    print(f"✅ Step 3 Complete: {len(schedule_df):,} assignments in {step3_time:.3f}s")

    # ANALYSIS
    print(f"\n" + "="*60)
    print("PHASE 5 PIPELINE RESULTS")
    print("="*60)

    print(f"⏱️  Performance Summary:")
    print(f"   - Step 1 (Candidates): {step1_time:.3f}s")
    print(f"   - Step 2 (Scoring): {step2_time:.3f}s")
    print(f"   - Step 3 (Assignment): {step3_time:.3f}s")
    print(f"   - Total Pipeline: {total_time:.3f}s")

    if not schedule_df.empty:
        assignments = schedule_df.drop_duplicates(['vin', 'person_id'])
        unique_vins = assignments['vin'].nunique()
        unique_partners = assignments['person_id'].nunique()
        unique_makes = assignments['make'].nunique()

        print(f"\n📊 Schedule Analysis:")
        print(f"   - Weekly assignments: {len(assignments)} VIN-partner pairs")
        print(f"   - Daily schedule rows: {len(schedule_df)} (7 days × assignments)")
        print(f"   - Unique VINs scheduled: {unique_vins}")
        print(f"   - Unique partners assigned: {unique_partners}")
        print(f"   - Vehicle makes: {unique_makes}")

        # Conversion rates
        candidate_to_assignment_rate = len(assignments) / len(scored_candidates) * 100
        print(f"   - Assignment rate: {candidate_to_assignment_rate:.1f}% of candidates assigned")

        # Score distribution of assigned vs unassigned
        assigned_vins = set(assignments['vin'])
        assigned_scores = scored_candidates[scored_candidates['vin'].isin(assigned_vins)]['score']
        unassigned_scores = scored_candidates[~scored_candidates['vin'].isin(assigned_vins)]['score']

        print(f"   - Assigned score range: {assigned_scores.min()}-{assigned_scores.max()} (avg: {assigned_scores.mean():.1f})")
        print(f"   - Unassigned score range: {unassigned_scores.min()}-{unassigned_scores.max()} (avg: {unassigned_scores.mean():.1f})")

        # Top assignments
        print(f"\n🏆 Top 5 Assignments:")
        top_assignments = assignments.nlargest(5, 'score')
        for i, (_, row) in enumerate(top_assignments.iterrows(), 1):
            vin_short = str(row['vin'])[-8:] if len(str(row['vin'])) > 8 else row['vin']
            print(f"   {i}. {vin_short} → Partner {row['person_id']} ({row['make']}, Score: {row['score']})")

        # Daily capacity usage
        print(f"\n📅 Daily Schedule Preview (Monday):")
        monday_assignments = schedule_df[schedule_df['day'] == week_start]
        for i, (_, row) in enumerate(monday_assignments.head(5).iterrows(), 1):
            vin_short = str(row['vin'])[-8:] if len(str(row['vin'])) > 8 else row['vin']
            print(f"   {i}. {vin_short} → Partner {row['person_id']} ({row['make']}) | Flags: {row['flags']}")

        if len(monday_assignments) > 5:
            print(f"   ... and {len(monday_assignments) - 5} more assignments")

        print(f"\n✅ Phase 5 Complete Pipeline Test Successful!")

    else:
        print(f"\n❌ No assignments generated")
        print(f"Debugging info:")
        print(f"   - Candidates: {len(scored_candidates)}")
        print(f"   - Office filter: candidates for '{office}'")
        print(f"   - Cooldown filter: candidates with cooldown_ok=True")

        office_candidates = scored_candidates[scored_candidates['market'] == office]
        cooldown_ok_candidates = office_candidates[office_candidates['cooldown_ok'] == True]
        print(f"   - Office candidates: {len(office_candidates)}")
        print(f"   - Cooldown OK candidates: {len(cooldown_ok_candidates)}")

    return schedule_df


async def main():
    """Run the complete Phase 5 real data test."""
    try:
        result = await test_complete_phase5_pipeline()
        return result
    except Exception as e:
        print(f"❌ Phase 5 pipeline test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    result = asyncio.run(main())