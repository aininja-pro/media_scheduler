"""
Check if the recent loan history records have clips_received data.
"""

import asyncio
import pandas as pd
from app.services.database import db_service


async def check_recent_data():
    """Check recent loan history records for clips_received."""
    print("Checking recent loan history records...")

    try:
        # Get most recent records (ordered by created_at)
        recent_response = db_service.client.table('loan_history').select(
            'activity_id, person_id, make, clips_received, created_at'
        ).order('created_at', desc=True).limit(20).execute()

        if not recent_response.data:
            print("❌ No loan history records found")
            return

        recent_df = pd.DataFrame(recent_response.data)
        print(f"✅ Found {len(recent_df)} recent records")

        # Check clips_received in recent data
        clips_dist = recent_df['clips_received'].value_counts(dropna=False)
        print(f"Recent clips_received distribution: {dict(clips_dist)}")

        # Show sample recent records
        print(f"\nSample recent records:")
        for _, row in recent_df.head(10).iterrows():
            print(f"  {row['activity_id']}: clips_received='{row['clips_received']}'")

        # Check if we need to update the ETL query
        has_clips_data = recent_df['clips_received'].notna().any()
        non_null_clips = recent_df[recent_df['clips_received'].notna()]

        if has_clips_data:
            print(f"\n✅ Recent data has clips_received values!")
            print(f"   {len(non_null_clips)} records with non-null clips_received")

            # Test the normalization on recent data
            print(f"\nTesting normalization on recent clips_received:")
            for _, row in non_null_clips.head(5).iterrows():
                clips_val = row['clips_received']
                normalized = True if str(clips_val).strip().lower() in {"true","1","yes","1.0"} else False if str(clips_val).strip().lower() in {"false","0","no","0.0"} else None
                print(f"   '{clips_val}' → {normalized}")

        else:
            print(f"❌ Recent data still shows null clips_received")

        # Check total count to understand data distribution
        total_response = db_service.client.table('loan_history').select('*', count='exact').execute()
        total_count = total_response.count
        print(f"\nTotal loan_history records: {total_count}")

        # Get oldest records too
        oldest_response = db_service.client.table('loan_history').select(
            'activity_id, clips_received, created_at'
        ).order('created_at', desc=False).limit(10).execute()

        if oldest_response.data:
            oldest_df = pd.DataFrame(oldest_response.data)
            oldest_clips_dist = oldest_df['clips_received'].value_counts(dropna=False)
            print(f"Oldest records clips_received: {dict(oldest_clips_dist)}")

    except Exception as e:
        print(f"❌ Check failed: {e}")


if __name__ == "__main__":
    asyncio.run(check_recent_data())