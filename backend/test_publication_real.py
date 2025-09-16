#!/usr/bin/env python3
"""
Test publication rate computation with real loan history data.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

import pandas as pd
import asyncio
from datetime import date
from app.etl.publication import compute_publication_rate_24m
from app.services.database import db_service

async def test_real_publication_data():
    """Test publication rate computation with real Supabase data."""

    print("🔌 Fetching real loan history data...")

    try:
        # Fetch loan history data (limit for performance)
        loan_history_response = db_service.client.table('loan_history').select('*').limit(200).execute()

        if not loan_history_response.data:
            print("❌ No loan history data found")
            return

        loan_history_df = pd.DataFrame(loan_history_response.data)
        print(f"📊 Found {len(loan_history_df)} loan history records")

        # Since clips_received doesn't exist yet, let's simulate some data
        print("\n🎯 Simulating clips_received data for testing...")

        # Add simulated clips_received data (mix of True/False/None)
        import random
        random.seed(42)  # For reproducible results

        clips_values = []
        for i in range(len(loan_history_df)):
            # Simulate realistic publication rate (~70% publish clips)
            rand_val = random.random()
            if rand_val < 0.7:
                clips_values.append(True)
            elif rand_val < 0.9:
                clips_values.append(False)
            else:
                clips_values.append(None)  # 10% missing data

        loan_history_df['clips_received'] = clips_values

        print(f"📋 Simulated clips_received distribution:")
        clip_counts = pd.Series(clips_values).value_counts(dropna=False)
        for value, count in clip_counts.items():
            print(f"   {value}: {count} records ({count/len(clips_values)*100:.1f}%)")

        # Test with current date
        as_of_date = "2025-09-14"
        print(f"\n🎯 Computing publication rates as of {as_of_date}...")

        result = compute_publication_rate_24m(
            loan_history_df=loan_history_df,
            as_of_date=as_of_date,
            window_months=24
        )

        print(f"\n📊 PUBLICATION RATE RESULTS:")
        print(f"   Total (person_id, make) combinations: {len(result)}")

        if len(result) > 0:
            # Show summary statistics
            avg_rate = result['pub_rate_24m'].mean()
            total_loans = result['loans_24m'].sum()
            total_published = result['published_24m'].sum()

            print(f"   📈 Average publication rate: {avg_rate:.1%}")
            print(f"   📊 Total loans in window: {total_loans}")
            print(f"   ✅ Total published: {total_published}")
            print(f"   📈 Overall publication rate: {total_published/total_loans:.1%}")

            # Show distribution by publication rate
            print(f"\n📊 Publication rate distribution:")
            rate_bins = pd.cut(result['pub_rate_24m'], bins=[0, 0.25, 0.5, 0.75, 1.0], include_lowest=True)
            rate_dist = rate_bins.value_counts().sort_index()
            for bin_range, count in rate_dist.items():
                print(f"   {bin_range}: {count} partners")

            # Show top and bottom performers
            print(f"\n🏆 Top performers (highest publication rates):")
            top_performers = result.nlargest(5, 'pub_rate_24m')[['person_id', 'make', 'pub_rate_24m', 'loans_24m', 'published_24m']]
            print(top_performers.to_string(index=False))

            print(f"\n📉 Lowest performers (lowest publication rates):")
            low_performers = result.nsmallest(5, 'pub_rate_24m')[['person_id', 'make', 'pub_rate_24m', 'loans_24m', 'published_24m']]
            print(low_performers.to_string(index=False))

            # Show make-level statistics
            print(f"\n🏭 Publication rates by make:")
            make_stats = result.groupby('make').agg({
                'pub_rate_24m': 'mean',
                'loans_24m': 'sum',
                'published_24m': 'sum'
            }).round(3)
            make_stats['overall_rate'] = (make_stats['published_24m'] / make_stats['loans_24m']).round(3)
            make_stats = make_stats.sort_values('overall_rate', ascending=False)

            for make, stats in make_stats.head(10).iterrows():
                print(f"   {make}: {stats['overall_rate']:.1%} rate ({int(stats['published_24m'])}/{int(stats['loans_24m'])} loans)")

        else:
            print("⚠️ No publication rate results generated")

        print(f"\n🎉 Real data publication rate test complete!")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_real_publication_data())