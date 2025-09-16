#!/usr/bin/env python3
"""
Test publication rate with full loan history (11,297 records).
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

import pandas as pd
import asyncio
from app.etl.publication import compute_publication_rate_24m
from app.services.database import db_service

async def test_full_loan_history():
    """Test publication rate with ALL loan history records."""

    print("🔌 Fetching ALL loan history data...")

    try:
        # Fetch ALL loan history records (not just 100)
        all_loans = []
        loan_response = db_service.client.table('loan_history').select('*').limit(1000).execute()
        if loan_response.data:
            all_loans.extend(loan_response.data)

            # Keep fetching until we get all records
            while len(loan_response.data) == 1000:
                offset = len(all_loans)
                loan_response = db_service.client.table('loan_history').select('*').range(offset, offset + 999).execute()
                if loan_response.data:
                    all_loans.extend(loan_response.data)
                else:
                    break

        loan_history_df = pd.DataFrame(all_loans)
        print(f"📊 Fetched {len(loan_history_df)} total loan history records")

        if len(loan_history_df) == 0:
            print("❌ No loan history data found")
            return

        # Test publication rate computation
        print(f"\n🎯 Computing publication rates for {len(loan_history_df)} loans...")

        result = compute_publication_rate_24m(loan_history_df, '2025-09-14')

        print(f"\n📊 FULL DATASET RESULTS:")
        print(f"   🎯 Total (person_id, make) grains: {len(result)}")

        if len(result) > 0:
            # Analyze the scope
            unique_partners = result['person_id'].nunique()
            unique_makes = result['make'].nunique()

            print(f"   👥 Unique partners: {unique_partners}")
            print(f"   🚗 Unique makes: {unique_makes}")
            print(f"   📊 Average grains per partner: {len(result)/unique_partners:.1f}")

            # Show loan distribution
            total_loans = result['loans_total_24m'].sum()
            avg_loans_per_grain = result['loans_total_24m'].mean()

            print(f"\n📈 LOAN DISTRIBUTION:")
            print(f"   📊 Total loans in 24m window: {total_loans:,}")
            print(f"   📊 Average loans per grain: {avg_loans_per_grain:.1f}")

            # Show top grains by loan volume
            top_grains = result.nlargest(5, 'loans_total_24m')[['person_id', 'make', 'loans_total_24m']]
            print(f"\n🏆 Most active (person_id, make) combinations:")
            for _, grain in top_grains.iterrows():
                print(f"   Partner {grain.person_id} × {grain.make}: {grain.loans_total_24m} loans")

            # Show make-level statistics
            make_stats = result.groupby('make').agg({
                'loans_total_24m': 'sum',
                'person_id': 'nunique'
            }).sort_values('loans_total_24m', ascending=False)

            print(f"\n🏭 Top makes by loan volume:")
            for make, stats in make_stats.head(10).iterrows():
                print(f"   {make}: {int(stats.loans_total_24m)} loans across {int(stats.person_id)} partners")

            # Current state (all NULL clips_received)
            null_rates = result[result.publication_rate_observed.isna()]
            print(f"\n💡 CURRENT STATE (before clips_received backfill):")
            print(f"   ❓ Grains with NULL rates: {len(null_rates)}")
            print(f"   📊 Average coverage: {result.coverage.mean():.1%}")
            print(f"   ✅ Grains with sufficient data: {result.supported.sum()}")

            print(f"\n🔮 AFTER you add clips_received data:")
            print(f"   📈 These {len(result)} grains will show real publication rates")
            print(f"   🎯 Partners with poor rates will be visible")
            print(f"   ✅ Rules can use publication_rate_observed and supported flags")

        else:
            print("❌ No grains found in 24-month window")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_full_loan_history())