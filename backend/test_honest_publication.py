#!/usr/bin/env python3
"""
Test the honest NULL-aware publication rate approach.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

import pandas as pd
import asyncio
from app.etl.publication import compute_publication_rate_24m
from app.services.database import db_service

async def test_honest_approach():
    """Test NULL-aware approach shows honest metrics instead of misleading zeros."""

    print("🔌 Testing honest NULL-aware publication rates...")

    try:
        # Get real loan history (without clips_received field)
        response = db_service.client.table('loan_history').select('*').limit(100).execute()
        df = pd.DataFrame(response.data)

        print(f"📊 Real loan history: {len(df)} records")
        print(f"📋 Schema: {list(df.columns)}")

        # Test with current data (all clips_received will be NULL)
        result = compute_publication_rate_24m(df, '2025-09-14')

        print(f"\n🎯 NULL-AWARE RESULTS:")
        print(f"   Total (person_id, make) grains: {len(result)}")

        if len(result) > 0:
            # Show what the honest approach looks like
            sample = result.head(3)
            for _, row in sample.iterrows():
                print(f"\n📊 {row.person_id} × {row.make}:")
                print(f"   📈 Total loans (24m): {row.loans_total_24m}")
                print(f"   🔍 Observed loans: {row.loans_observed_24m}")
                print(f"   📊 Publication rate: {row.publication_rate_observed}")
                print(f"   📈 Coverage: {row.coverage:.1%}")
                print(f"   ✅ Supported: {row.supported}")

            # Summary statistics
            null_rates = result[result.publication_rate_observed.isna()]
            valid_rates = result[result.publication_rate_observed.notna()]
            supported = result[result.supported == True]

            print(f"\n📈 HONEST METRICS SUMMARY:")
            print(f"   🎯 Total grains: {len(result)}")
            print(f"   ❓ Unknown rates (NULL): {len(null_rates)} grains")
            print(f"   📊 Known rates: {len(valid_rates)} grains")
            print(f"   ✅ Supported grains: {len(supported)} grains")
            print(f"   📈 Average coverage: {result.coverage.mean():.1%}")

            print(f"\n🎨 Why this approach is better:")
            print(f"   ❌ Old way: All {len(result)} grains would show 0% (misleading)")
            print(f"   ✅ New way: {len(null_rates)} grains show NULL rate (honest)")
            print(f"   🎯 UI can show 'Insufficient data' instead of fake 0%")

        else:
            print("❌ No results - all loans outside 24m window")

        print(f"\n✅ Honest publication rate approach complete!")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_honest_approach())