"""
Test Phase 5 with 30-day cooldown instead of 60-day to see the impact.
"""

import asyncio
import pandas as pd
import time

from app.tests.test_candidates_etl_integration import (
    fetch_etl_availability_data,
    fetch_etl_publication_data,
    fetch_etl_eligibility_data
)
from app.tests.test_scoring_real_data import fetch_scoring_data
from app.solver.candidates import build_weekly_candidates
from app.solver.scoring import compute_candidate_scores
from app.solver.greedy_assign import generate_week_schedule
from app.services.database import db_service
from app.etl.cooldown import compute_cooldown_flags


async def test_30day_cooldown():
    """Test with 30-day cooldown instead of 60-day."""

    office = "Los Angeles"
    week_start = "2025-09-22"

    print(f"COOLDOWN COMPARISON TEST: {office}, Week: {week_start}")
    print(f"Testing 30-day vs 60-day cooldown periods")

    # Get loan history and rules for cooldown calculation
    loan_history_response = db_service.client.table('loan_history').select('person_id, make, model, start_date, end_date').order('created_at', desc=True).limit(5000).execute()
    loan_history_df = pd.DataFrame(loan_history_response.data) if loan_history_response.data else pd.DataFrame()

    rules_response = db_service.client.table('rules').select('*').execute()
    rules_df = pd.DataFrame(rules_response.data) if rules_response.data else pd.DataFrame()

    # Convert date columns
    for date_col in ['start_date', 'end_date']:
        if date_col in loan_history_df.columns:
            loan_history_df[date_col] = pd.to_datetime(loan_history_df[date_col], errors='coerce').dt.date

    print(f"\nCooldown data:")
    print(f"   - Loan history records: {len(loan_history_df)}")
    print(f"   - Rules records: {len(rules_df)}")

    # TEST 1: 60-day cooldown (current)
    print(f"\n60-DAY COOLDOWN:")
    cooldown_60_df = compute_cooldown_flags(
        loan_history_df=loan_history_df,
        rules_df=rules_df,
        week_start=week_start,
        default_days=60
    )

    cooldown_60_ok = cooldown_60_df['cooldown_ok'].sum() if not cooldown_60_df.empty else 0
    cooldown_60_total = len(cooldown_60_df)
    cooldown_60_rate = (cooldown_60_ok / cooldown_60_total * 100) if cooldown_60_total > 0 else 0

    print(f"   - Total partner-make combinations: {cooldown_60_total}")
    print(f"   - Available (cooldown_ok=True): {cooldown_60_ok}")
    print(f"   - Availability rate: {cooldown_60_rate:.1f}%")

    # TEST 2: 30-day cooldown
    print(f"\n30-DAY COOLDOWN:")
    cooldown_30_df = compute_cooldown_flags(
        loan_history_df=loan_history_df,
        rules_df=rules_df,
        week_start=week_start,
        default_days=30  # ← Changed to 30 days
    )

    cooldown_30_ok = cooldown_30_df['cooldown_ok'].sum() if not cooldown_30_df.empty else 0
    cooldown_30_total = len(cooldown_30_df)
    cooldown_30_rate = (cooldown_30_ok / cooldown_30_total * 100) if cooldown_30_total > 0 else 0

    print(f"   - Total partner-make combinations: {cooldown_30_total}")
    print(f"   - Available (cooldown_ok=True): {cooldown_30_ok}")
    print(f"   - Availability rate: {cooldown_30_rate:.1f}%")

    # Show some examples of the partner-make combinations
    print(f"\nSample partner-make combinations (what the 992 represents):")
    if not cooldown_60_df.empty:
        sample_combinations = cooldown_60_df.head(10)
        for _, row in sample_combinations.iterrows():
            cooldown_status = "AVAILABLE" if row['cooldown_ok'] else "BLOCKED"
            cooldown_until = row['cooldown_until'].strftime('%Y-%m-%d') if pd.notna(row['cooldown_until']) else "N/A"
            print(f"   Partner {row['person_id']} + {row['make']}: {cooldown_status} (until {cooldown_until})")

    # If 30-day shows improvement, run full pipeline test
    if cooldown_30_ok > cooldown_60_ok:
        print(f"\n🎯 30-day cooldown improves availability! Running full pipeline...")

        # Get other ETL data
        availability_df, publication_df, eligibility_df = await asyncio.gather(
            fetch_etl_availability_data(office, week_start),
            fetch_etl_publication_data(),
            fetch_etl_eligibility_data()
        )

        # Run pipeline with 30-day cooldown
        candidates_30_df = build_weekly_candidates(
            availability_df=availability_df,
            cooldown_df=cooldown_30_df,
            publication_df=publication_df,
            week_start=week_start,
            eligibility_df=eligibility_df if not eligibility_df.empty else None,
            min_available_days=5
        )

        print(f"   With 30-day cooldown: {len(candidates_30_df):,} candidates (vs {18240:,} with 60-day)")

        if len(candidates_30_df) > 18240:
            print(f"   🚀 More candidates available with shorter cooldown!")
        else:
            print(f"   ⚠️  No improvement - other constraints still limiting")

    else:
        print(f"\n⚠️  30-day cooldown doesn't improve availability")
        print(f"   This suggests most loans ended within the last 30 days")

    print(f"\n✅ Cooldown comparison test complete")


if __name__ == "__main__":
    asyncio.run(test_30day_cooldown())