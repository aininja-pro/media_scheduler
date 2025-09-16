"""
Check the current media_partners table schema and recent data.
"""

import asyncio
from app.services.database import db_service


async def check_schema():
    """Check media_partners table schema and data."""
    print("Checking media_partners table...")

    try:
        # Get recent records to see current schema
        response = db_service.client.table('media_partners').select('*').limit(5).execute()

        if response.data:
            print(f"✅ Found {len(response.data)} records")
            print(f"Current columns: {list(response.data[0].keys())}")

            # Check for Yousef record
            yousef_response = db_service.client.table('media_partners').select('*').eq('name', 'Yousef Alvi').execute()
            if yousef_response.data:
                yousef = yousef_response.data[0]
                print(f"\n🎯 Yousef Alvi record:")
                for key, value in yousef.items():
                    print(f"   {key}: '{value}'")
            else:
                print("❌ Yousef Alvi record not found")

        else:
            print("❌ No media_partners records found")

    except Exception as e:
        print(f"❌ Schema check failed: {e}")


if __name__ == "__main__":
    asyncio.run(check_schema())