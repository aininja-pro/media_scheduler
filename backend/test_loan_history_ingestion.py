"""
Test the loan history URL ingestion with the new clips_received text field.
"""

import asyncio
import pandas as pd
import httpx
from io import StringIO


async def test_loan_history_url():
    """Test the loan history URL ingestion."""
    url = "https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/loan_history.rpt&init=csv"

    print("Testing loan history URL ingestion...")
    print(f"URL: {url}")

    try:
        # Fetch the CSV data directly first
        print("\n1. Fetching CSV data directly...")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)

            if response.status_code != 200:
                print(f"❌ Failed to fetch CSV: {response.status_code}")
                return

        csv_content = response.text
        print(f"✅ CSV fetched successfully, {len(csv_content)} characters")

        # Show first few lines to validate format
        lines = csv_content.split('\n')[:5]
        print(f"\n📋 First 5 lines of CSV:")
        for i, line in enumerate(lines):
            print(f"   {i+1}: {line}")

        # Parse CSV to check structure
        print(f"\n2. Parsing CSV structure...")
        try:
            df = pd.read_csv(StringIO(csv_content))
            print(f"✅ CSV parsed successfully: {len(df)} rows, {len(df.columns)} columns")
            print(f"   Columns: {list(df.columns)}")

            if len(df) > 0:
                print(f"\n📊 Sample data (first row):")
                first_row = df.iloc[0]
                for i, (col, val) in enumerate(first_row.items()):
                    print(f"   {i+1:2d}. {col}: '{val}'")

                # Check if clips_received data exists
                if 'clips_received' in df.columns:
                    clips_values = df['clips_received'].value_counts()
                    print(f"\n🎬 clips_received values: {dict(clips_values)}")
                else:
                    print(f"\n⚠️  No 'clips_received' column found")

        except Exception as e:
            print(f"❌ Failed to parse CSV: {e}")
            return

        # Test the API endpoint
        print(f"\n3. Testing API endpoint...")
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                api_response = await client.post(
                    f"http://localhost:8081/ingest/loan_history/url",
                    params={"url": url}
                )

                if api_response.status_code == 200:
                    result = api_response.json()
                    print(f"✅ API call successful!")
                    print(f"   Status: {result.get('status', 'unknown')}")
                    print(f"   Rows processed: {result.get('rows_processed', 0)}")
                    print(f"   Rows affected: {result.get('rows_affected', 0)}")

                    if result.get('rows_processed', 0) == 0:
                        print(f"⚠️  Zero rows processed - investigating...")

                else:
                    print(f"❌ API call failed: {api_response.status_code}")
                    print(f"   Response: {api_response.text}")

        except Exception as e:
            print(f"❌ API test failed: {e}")

    except Exception as e:
        print(f"❌ Test failed: {e}")


async def check_database_data():
    """Check what's currently in the loan_history table."""
    print(f"\n4. Checking database data...")

    try:
        from app.services.database import db_service

        # Get total count
        count_response = db_service.client.table('loan_history').select('*', count='exact').execute()
        total_count = count_response.count
        print(f"   Total loan_history records: {total_count}")

        # Get recent records
        recent_response = db_service.client.table('loan_history').select(
            'activity_id, vin, person_id, clips_received, created_at'
        ).order('created_at', desc=True).limit(5).execute()

        if recent_response.data:
            print(f"   Recent records:")
            for i, record in enumerate(recent_response.data):
                clips = record.get('clips_received', 'NULL')
                print(f"     {i+1}. {record['activity_id']} | clips_received: '{clips}'")
        else:
            print(f"   No records found")

        # Check clips_received distribution
        clips_response = db_service.client.table('loan_history').select('clips_received').execute()
        if clips_response.data:
            clips_df = pd.DataFrame(clips_response.data)
            clips_dist = clips_df['clips_received'].value_counts(dropna=False)
            print(f"   clips_received distribution: {dict(clips_dist)}")

    except Exception as e:
        print(f"❌ Database check failed: {e}")


async def main():
    """Run the loan history ingestion test."""
    await test_loan_history_url()
    await check_database_data()


if __name__ == "__main__":
    asyncio.run(main())