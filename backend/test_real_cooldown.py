#!/usr/bin/env python3
"""
Test cooldown flags with real Supabase data.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

import pandas as pd
import asyncio
from datetime import date
from app.etl.cooldown import compute_cooldown_flags
from app.services.database import db_service

async def test_real_cooldown_data():
    """Test cooldown computation with real Supabase data."""

    print("🔌 Fetching real data from Supabase...")

    try:
        # Test connection
        is_connected = await db_service.test_connection()
        if not is_connected:
            print("❌ Database connection failed")
            return

        print("✅ Connected to Supabase!")

        # Fetch loan history data
        print("\n📋 Fetching loan history...")
        loan_history_response = db_service.client.table('loan_history').select('*').limit(100).execute()

        if not loan_history_response.data:
            print("❌ No loan history data found")
            return

        loan_history_df = pd.DataFrame(loan_history_response.data)
        print(f"📊 Found {len(loan_history_df)} loan history records")

        # Show sample data structure
        print(f"\n📋 Loan History Columns: {list(loan_history_df.columns)}")
        print("Sample data:")
        display_cols = ['person_id', 'make', 'model', 'start_date', 'end_date']
        available_cols = [col for col in display_cols if col in loan_history_df.columns]
        print(loan_history_df[available_cols].head())

        # Check for model field
        if 'model' not in loan_history_df.columns:
            print("⚠️ No 'model' column found, adding None values")
            loan_history_df['model'] = None

        # Show model distribution
        model_counts = loan_history_df['model'].value_counts(dropna=False)
        print(f"\n🚗 Model distribution (top 10):")
        print(model_counts.head(10))
        print(f"Null/empty models: {loan_history_df['model'].isna().sum()}")

        # Fetch rules data
        print("\n📋 Fetching rules...")
        rules_response = db_service.client.table('rules').select('*').execute()

        if rules_response.data:
            rules_df = pd.DataFrame(rules_response.data)
            print(f"📊 Found {len(rules_df)} rules")
            print("Rules data:")
            rule_cols = ['make', 'cooldown_period_days'] if 'cooldown_period_days' in rules_df.columns else ['make', 'cooldown_period']
            available_rule_cols = [col for col in rule_cols if col in rules_df.columns]
            print(rules_df[available_rule_cols].head())
        else:
            print("⚠️ No rules data found, using empty DataFrame")
            rules_df = pd.DataFrame()

        # Convert date columns
        print("\n🔧 Processing data...")
        for date_col in ['start_date', 'end_date']:
            if date_col in loan_history_df.columns:
                loan_history_df[date_col] = pd.to_datetime(loan_history_df[date_col], errors='coerce').dt.date

        # Test with current week
        week_start = "2025-09-08"  # Monday
        print(f"\n🎯 Computing cooldown flags for week: {week_start}")

        # Run cooldown computation
        result = compute_cooldown_flags(
            loan_history_df=loan_history_df,
            rules_df=rules_df,
            week_start=week_start,
            default_days=60
        )

        print(f"\n📊 COOLDOWN RESULTS:")
        print(f"   Total grains processed: {len(result)}")

        if len(result) > 0:
            # Show summary statistics
            total_ok = result['cooldown_ok'].sum()
            total_blocked = len(result) - total_ok

            print(f"   ✅ Allowed: {total_ok}")
            print(f"   ❌ Blocked: {total_blocked}")
            print(f"   📈 Allow rate: {total_ok/len(result)*100:.1f}%")

            # Show cooldown days distribution
            days_dist = result['cooldown_days_used'].value_counts().sort_index()
            print(f"\n📊 Cooldown days used:")
            for days, count in days_dist.items():
                print(f"   {days} days: {count} grains")

            # Show some example results
            print(f"\n📋 Sample results (first 10):")
            display_result_cols = ['person_id', 'make', 'model', 'cooldown_ok', 'cooldown_days_used']
            print(result[display_result_cols].head(10).to_string(index=False))

            # Show blocked examples
            blocked_results = result[result['cooldown_ok'] == False]
            if len(blocked_results) > 0:
                print(f"\n❌ Blocked examples ({len(blocked_results)} total):")
                print(blocked_results[['person_id', 'make', 'model', 'cooldown_until', 'cooldown_days_used']].head(5).to_string(index=False))

            # Show make distribution in results
            make_dist = result['make'].value_counts().head(5)
            print(f"\n🏭 Top makes in cooldown results:")
            for make, count in make_dist.items():
                make_results = result[result['make'] == make]
                allowed = make_results['cooldown_ok'].sum()
                print(f"   {make}: {count} grains ({allowed} allowed, {count-allowed} blocked)")

        else:
            print("⚠️ No cooldown results generated")

            # Debug why no results
            print("🔍 Debugging...")
            if loan_history_df.empty:
                print("   - Loan history is empty")
            else:
                print(f"   - Loan history has {len(loan_history_df)} rows")
                valid_dates = loan_history_df['end_date'].notna().sum()
                print(f"   - Valid end_dates: {valid_dates}")

                if valid_dates == 0:
                    print("   - No valid end_dates found")
                    print("   - Sample end_date values:", loan_history_df['end_date'].head().tolist())

        print(f"\n🎉 Real data cooldown test complete!")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_real_cooldown_data())