"""
Debug the cooldown calculation discrepancy.
Why does sample show 81% availability but full dataset shows 0%?
"""

import asyncio
import pandas as pd
from datetime import datetime, timedelta
from app.services.database import db_service
from app.etl.cooldown import compute_cooldown_flags


async def debug_cooldown_calculation():
    """Debug the cooldown calculation to understand the 0% vs 81% discrepancy."""

    print("=" * 80)
    print("DEBUGGING COOLDOWN CALCULATION DISCREPANCY")
    print("=" * 80)

    week_start = "2025-09-22"
    week_start_date = datetime.strptime(week_start, '%Y-%m-%d').date()

    # Get rules
    rules_response = db_service.client.table('rules').select('*').execute()
    rules_df = pd.DataFrame(rules_response.data) if rules_response.data else pd.DataFrame()

    print(f"Target week: {week_start}")
    print(f"Cooldown window: 60 days before {week_start} = from {week_start_date - timedelta(days=60)} to {week_start_date}")

    # TEST 1: Small sample (what showed 81% availability)
    print(f"\n1. SMALL SAMPLE TEST (100 records):")
    sample_response = db_service.client.table('loan_history').select(
        'person_id, make, model, start_date, end_date'
    ).limit(100).execute()

    if sample_response.data:
        sample_df = pd.DataFrame(sample_response.data)

        # Convert dates
        for date_col in ['start_date', 'end_date']:
            sample_df[date_col] = pd.to_datetime(sample_df[date_col], errors='coerce').dt.date

        sample_cooldown = compute_cooldown_flags(
            loan_history_df=sample_df,
            rules_df=rules_df,
            week_start=week_start,
            default_days=60
        )

        sample_available = sample_cooldown['cooldown_ok'].sum()
        sample_total = len(sample_cooldown)
        sample_rate = (sample_available / sample_total * 100) if sample_total > 0 else 0

        print(f"   Sample cooldown: {sample_available}/{sample_total} available ({sample_rate:.1f}%)")

        # Check date ranges in sample
        if not sample_df.empty:
            min_end = sample_df['end_date'].min()
            max_end = sample_df['end_date'].max()
            print(f"   Sample end dates: {min_end} to {max_end}")

            # Check how many are within 60 days
            recent_loans = sample_df[sample_df['end_date'] > (week_start_date - timedelta(days=60))]
            print(f"   Recent loans (within 60 days): {len(recent_loans)}/{len(sample_df)}")

    # TEST 2: Full dataset (what shows 0% availability)
    print(f"\n2. FULL DATASET TEST (all records via ETL):")

    # Use the actual ETL function that's showing 0%
    from app.tests.test_candidates_etl_integration import fetch_etl_cooldown_data

    full_cooldown_df = await fetch_etl_cooldown_data(week_start)

    if not full_cooldown_df.empty:
        full_available = full_cooldown_df['cooldown_ok'].sum()
        full_total = len(full_cooldown_df)
        full_rate = (full_available / full_total * 100) if full_total > 0 else 0

        print(f"   Full ETL cooldown: {full_available}/{full_total} available ({full_rate:.1f}%)")

        # Check what data the ETL is using
        print(f"   ETL uses loan_history records: checking data source...")

        # The ETL function gets loan history - let's see what it's getting
        print(f"   (ETL internally fetches loan history and computes cooldown)")

    # TEST 3: Direct comparison with same data
    print(f"\n3. USING SAME LOAN HISTORY AS ETL:")

    # Get the exact same loan history that ETL uses
    etl_loan_response = db_service.client.table('loan_history').select(
        'person_id, make, model, start_date, end_date'
    ).order('end_date', desc=True).limit(5000).execute()

    if etl_loan_response.data:
        etl_loan_df = pd.DataFrame(etl_loan_response.data)

        # Convert dates
        for date_col in ['start_date', 'end_date']:
            etl_loan_df[date_col] = pd.to_datetime(etl_loan_df[date_col], errors='coerce').dt.date

        print(f"   ETL loan history: {len(etl_loan_df)} records")

        # Check date ranges
        min_end = etl_loan_df['end_date'].min()
        max_end = etl_loan_df['end_date'].max()
        print(f"   ETL end dates: {min_end} to {max_end}")

        # Check recent activity
        recent_threshold = week_start_date - timedelta(days=60)
        recent_loans = etl_loan_df[etl_loan_df['end_date'] > recent_threshold]
        recent_rate = (len(recent_loans) / len(etl_loan_df) * 100) if len(etl_loan_df) > 0 else 0

        print(f"   Recent loans (within 60 days of {week_start}): {len(recent_loans)}/{len(etl_loan_df)} ({recent_rate:.1f}%)")

        # If most loans are recent, that explains 0% availability
        if recent_rate > 80:
            print(f"   💡 EXPLANATION: {recent_rate:.1f}% of loans are recent → most partners in cooldown")

        # Compute cooldown with this data
        etl_cooldown_df = compute_cooldown_flags(
            loan_history_df=etl_loan_df,
            rules_df=rules_df,
            week_start=week_start,
            default_days=60
        )

        if not etl_cooldown_df.empty:
            etl_available = etl_cooldown_df['cooldown_ok'].sum()
            etl_total = len(etl_cooldown_df)
            etl_rate = (etl_available / etl_total * 100) if etl_total > 0 else 0

            print(f"   ETL-equivalent cooldown: {etl_available}/{etl_total} available ({etl_rate:.1f}%)")

    print(f"\n✅ Cooldown discrepancy investigation complete")


if __name__ == "__main__":
    asyncio.run(debug_cooldown_calculation())