"""
Test the media partners CSV format to understand the new structure.
"""

import asyncio
import pandas as pd
import httpx
from io import StringIO


async def test_media_partners_csv():
    """Test the media partners CSV format."""
    url = "https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/media_partners.rpt&init=csv"

    print("Testing media partners CSV format...")
    print(f"URL: {url}")

    try:
        # Fetch the CSV data
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)

            if response.status_code != 200:
                print(f"❌ Failed to fetch CSV: {response.status_code}")
                return

        csv_content = response.text
        print(f"✅ CSV fetched successfully, {len(csv_content)} characters")

        # Show first few lines
        lines = csv_content.split('\n')[:10]
        print(f"\n📋 First 10 lines of CSV:")
        for i, line in enumerate(lines):
            print(f"   {i+1}: {line}")

        # Try parsing with headers first
        print(f"\n🔍 Trying to parse with headers...")
        try:
            df_with_headers = pd.read_csv(StringIO(csv_content))
            print(f"✅ Parsed with headers: {len(df_with_headers)} rows, {len(df_with_headers.columns)} columns")
            print(f"   Headers: {list(df_with_headers.columns)}")

            if len(df_with_headers) > 0:
                print(f"\n📊 Sample data (first row with headers):")
                first_row = df_with_headers.iloc[0]
                for i, (col, val) in enumerate(first_row.items()):
                    print(f"   {i+1:2d}. {col}: '{val}'")

        except Exception as e:
            print(f"   Failed to parse with headers: {e}")

        # Try parsing without headers (positional)
        print(f"\n🔍 Trying to parse without headers (positional)...")
        try:
            # Based on your example: person_id, name, address, office, default_loan_region
            df_no_headers = pd.read_csv(StringIO(csv_content), header=None, names=[
                'Person_ID', 'Name', 'Address', 'Office', 'Default_Loan_Region'
            ])
            print(f"✅ Parsed without headers: {len(df_no_headers)} rows, {len(df_no_headers.columns)} columns")

            if len(df_no_headers) > 0:
                print(f"\n📊 Sample data (first row without headers):")
                first_row = df_no_headers.iloc[0]
                for i, (col, val) in enumerate(first_row.items()):
                    print(f"   {i+1:2d}. {col}: '{val}'")

                # Check for your example record
                yousef_records = df_no_headers[df_no_headers['Name'].str.contains('Yousef', na=False)]
                if not yousef_records.empty:
                    print(f"\n🎯 Found Yousef record:")
                    yousef = yousef_records.iloc[0]
                    print(f"   Person_ID: '{yousef['Person_ID']}'")
                    print(f"   Name: '{yousef['Name']}'")
                    print(f"   Address: '{yousef['Address']}'")
                    print(f"   Office: '{yousef['Office']}'")
                    print(f"   Default_Loan_Region: '{yousef['Default_Loan_Region']}'")

        except Exception as e:
            print(f"   Failed to parse without headers: {e}")

    except Exception as e:
        print(f"❌ Test failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_media_partners_csv())