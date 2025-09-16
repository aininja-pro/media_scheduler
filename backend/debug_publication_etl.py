"""
Debug the publication rate ETL to see if it's reading clips_received data correctly.
"""

import asyncio
import pandas as pd
from app.services.database import db_service
from app.etl.publication import compute_publication_rate_24m


async def debug_publication_calculation():
    """Debug the publication rate calculation."""
    print("=" * 60)
    print("Debugging Publication Rate ETL")
    print("=" * 60)

    try:
        # Fetch loan history like the ETL does
        print("1. Fetching loan history data...")
        all_loans = []
        loan_response = db_service.client.table('loan_history').select('*').limit(1000).execute()
        if loan_response.data:
            all_loans.extend(loan_response.data)

        loan_history_df = pd.DataFrame(all_loans) if all_loans else pd.DataFrame()
        print(f"   Fetched {len(loan_history_df)} loan history records")

        if loan_history_df.empty:
            print("❌ No loan history data found")
            return

        # Check what columns we have
        print(f"   Columns: {list(loan_history_df.columns)}")

        # Check clips_received data specifically
        if 'clips_received' in loan_history_df.columns:
            print(f"\n2. Analyzing clips_received data...")
            clips_dist = loan_history_df['clips_received'].value_counts(dropna=False)
            print(f"   clips_received distribution: {dict(clips_dist)}")

            # Show sample records with clips_received data
            recent_with_clips = loan_history_df[
                loan_history_df['clips_received'].notna()
            ].head(5)

            if not recent_with_clips.empty:
                print(f"\n   Sample records with clips_received data:")
                for _, row in recent_with_clips.iterrows():
                    print(f"     {row['activity_id']}: person_id={row['person_id']}, make={row['make']}, clips_received='{row['clips_received']}'")
            else:
                print(f"   ❌ No records with non-null clips_received found")

        else:
            print(f"❌ clips_received column not found in loan_history data")
            return

        # Test the publication rate calculation
        print(f"\n3. Testing publication rate calculation...")

        result_df = compute_publication_rate_24m(
            loan_history_df=loan_history_df,
            as_of_date=None,  # Use today
            window_months=24,
            min_observed=3
        )

        print(f"   ✅ Publication rate calculated: {len(result_df)} grains")

        if not result_df.empty:
            # Check for grains with actual clip data
            with_data = result_df[result_df['has_clip_data'] == True]
            print(f"   - Grains with clip data: {len(with_data)}")

            if len(with_data) > 0:
                print(f"   - Sample grains with publication data:")
                for _, row in with_data.head(3).iterrows():
                    rate = row['publication_rate']
                    rate_str = f"{rate:.1%}" if rate is not None else "None"
                    print(f"     {row['person_id']} + {row['make']}: {row['publications_24m']}/{row['loans_total_24m']} = {rate_str}")
            else:
                print(f"   ❌ No grains showing has_clip_data = True")

            # Check the normalization logic
            print(f"\n4. Testing clips_received normalization...")
            test_df = loan_history_df.head(100).copy()  # Small sample for testing

            # Run the normalization logic manually
            if "clips_received" not in test_df.columns:
                test_df["clips_received"] = pd.NA

            test_df["clips_received_norm"] = (
                test_df["clips_received"]
                .map(lambda x: True if str(x).strip().lower() in {"true","1","yes","1.0"} else
                           False if str(x).strip().lower() in {"false","0","no","0.0"} else pd.NA)
            )

            norm_dist = test_df["clips_received_norm"].value_counts(dropna=False)
            print(f"   Normalization test results: {dict(norm_dist)}")

            # Show some examples
            sample_norm = test_df[['clips_received', 'clips_received_norm']].head(10)
            print(f"   Sample normalization:")
            for _, row in sample_norm.iterrows():
                print(f"     '{row['clips_received']}' → {row['clips_received_norm']}")

    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_publication_calculation())