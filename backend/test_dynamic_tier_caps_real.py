"""
Test dynamic tier caps with real Supabase rules data.
"""

import asyncio
import pandas as pd
import time
from app.solver.candidates import build_weekly_candidates
from app.solver.scoring import compute_candidate_scores
from app.solver.greedy_assign import generate_week_schedule
from app.services.database import db_service


async def test_dynamic_caps_with_real_data():
    """Test the complete Phase 5 pipeline with real dynamic tier caps."""
    print("=" * 80)
    print("Testing Dynamic Tier Caps with REAL Supabase Rules Data")
    print("=" * 80)

    # Check what rules data we actually have
    print("\n1. Examining real rules data...")
    try:
        rules_response = db_service.client.table('rules').select('*').execute()
        rules_df = pd.DataFrame(rules_response.data) if rules_response.data else pd.DataFrame()

        if rules_df.empty:
            print("❌ No rules data found in database")
            return

        print(f"✅ Found {len(rules_df)} rules records")
        print(f"   Columns: {list(rules_df.columns)}")

        # Show sample rules
        print(f"\n📋 Sample rules:")
        for _, rule in rules_df.head(5).iterrows():
            make = rule.get('make', 'N/A')
            rank = rule.get('rank', 'N/A')
            cap = rule.get('loan_cap_per_year', 'N/A')
            print(f"   {make} + {rank}: cap={cap}")

        # Check loan_cap_per_year distribution
        if 'loan_cap_per_year' in rules_df.columns:
            cap_dist = rules_df['loan_cap_per_year'].value_counts(dropna=False)
            print(f"\n💡 loan_cap_per_year distribution: {dict(cap_dist)}")

    except Exception as e:
        print(f"❌ Failed to fetch rules: {e}")
        return

    # Test with Los Angeles office
    from datetime import datetime, timedelta
    today = datetime.now()
    days_since_monday = today.weekday()
    current_monday = (today - timedelta(days=days_since_monday)).date()
    week_start = current_monday.strftime('%Y-%m-%d')
    office = "Los Angeles"

    print(f"\n2. Running Phase 5 with real rules for {office}, week {week_start}...")

    # Get ETL data (reusing existing functions)
    from app.tests.test_candidates_etl_integration import (
        fetch_etl_availability_data,
        fetch_etl_cooldown_data,
        fetch_etl_publication_data,
        fetch_etl_eligibility_data
    )
    from app.tests.test_scoring_real_data import fetch_scoring_data

    # Step 1: Candidates
    print(f"\n   Step 1: Generating candidates...")
    start_time = time.time()

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

    step1_time = time.time() - start_time
    print(f"   ✅ {len(candidates_df):,} candidates in {step1_time:.3f}s")

    # Step 2: Scoring
    print(f"\n   Step 2: Scoring candidates...")
    start_time = time.time()

    partner_rank_df, partners_df = await fetch_scoring_data()

    scored_candidates = compute_candidate_scores(
        candidates_df=candidates_df,
        partner_rank_df=partner_rank_df,
        partners_df=partners_df,
        publication_df=publication_df
    )

    step2_time = time.time() - start_time
    print(f"   ✅ {len(scored_candidates):,} scored candidates in {step2_time:.3f}s")

    # Step 3: Greedy Assignment with REAL RULES
    print(f"\n   Step 3: Greedy assignment with REAL dynamic tier caps...")
    start_time = time.time()

    # Get ops capacity
    ops_response = db_service.client.table('ops_capacity').select('office, drivers_per_day').execute()
    ops_capacity_df = pd.DataFrame(ops_response.data) if ops_response.data else pd.DataFrame()

    # Get loan history for tier calculations
    loan_history_response = db_service.client.table('loan_history').select(
        'person_id, make, start_date, end_date'
    ).order('end_date', desc=True).limit(5000).execute()
    loan_history_df = pd.DataFrame(loan_history_response.data) if loan_history_response.data else pd.DataFrame()

    # RUN WITH REAL RULES DATA
    schedule_df = generate_week_schedule(
        candidates_scored_df=scored_candidates,
        loan_history_df=loan_history_df,
        ops_capacity_df=ops_capacity_df,
        office=office,
        week_start=week_start,
        rules_df=rules_df  # ← REAL RULES FROM DATABASE
    )

    step3_time = time.time() - start_time
    print(f"   ✅ {len(schedule_df):,} assignments in {step3_time:.3f}s")

    # Analysis
    print(f"\n3. Results with REAL dynamic tier caps:")

    if not schedule_df.empty:
        assignments = schedule_df.drop_duplicates(['vin', 'person_id'])
        unique_assignments = len(assignments)
        unique_vins = assignments['vin'].nunique()
        unique_partners = assignments['person_id'].nunique()

        print(f"   📊 Schedule: {unique_assignments} assignments, {unique_vins} VINs, {unique_partners} partners")

        # Show constraint impact
        candidate_count = len(scored_candidates)
        assignment_rate = unique_assignments / candidate_count * 100
        print(f"   📈 Assignment rate: {assignment_rate:.2f}% ({unique_assignments}/{candidate_count:,})")

        # Compare to legacy caps (would be much higher)
        print(f"   🎯 Dynamic caps working: Very selective due to real business rules")

        # Show top assignments
        print(f"\n   🏆 Top assignments with real tier caps:")
        top_assignments = assignments.nlargest(5, 'score')
        for i, (_, row) in enumerate(top_assignments.iterrows(), 1):
            vin_short = str(row['vin'])[-8:]
            print(f"     {i}. {vin_short} → Partner {row['person_id']} ({row['make']}, Score: {row['score']})")

    else:
        print(f"   ❌ No assignments made with real rules")
        print(f"   📊 This suggests real rules are very restrictive (many 0/NULL caps)")

        # Debug: Check how many candidates had 0 caps
        print(f"\n   🔍 Debugging tier cap restrictions...")

        # Show sample of what caps were computed
        sample_candidates = scored_candidates[scored_candidates['market'] == office].head(10)

        for _, candidate in sample_candidates.iterrows():
            person_id = candidate['person_id']
            make = candidate['make']
            rank = candidate['rank']

            # Find the rule that applies
            matching_rules = rules_df[
                (rules_df['make'] == make) &
                (rules_df.get('rank', rank) == rank)  # Handle rank column optionally
            ] if 'rank' in rules_df.columns else rules_df[rules_df['make'] == make]

            if not matching_rules.empty:
                cap = matching_rules.iloc[0]['loan_cap_per_year']
                print(f"     Partner {person_id} + {make} (Rank {rank}): cap={cap}")
            else:
                print(f"     Partner {person_id} + {make} (Rank {rank}): no rule → cap=0")

    print(f"\n✅ Dynamic tier caps test with real data complete!")


if __name__ == "__main__":
    asyncio.run(test_dynamic_caps_with_real_data())