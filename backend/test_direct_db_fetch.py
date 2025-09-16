"""
Test direct database fetch to see if we can get all 22,332 loan_history records.
"""

import asyncio
from app.services.database import db_service


async def test_direct_fetch():
    """Test direct fetch of all loan_history records."""

    print("Testing direct fetch of ALL loan_history records...")

    try:
        # Get total count first
        count_response = db_service.client.table('loan_history').select('*', count='exact').execute()
        total_count = count_response.count
        print(f"Total loan_history records in DB: {total_count:,}")

        # Try to fetch all at once
        print(f"Attempting to fetch all records...")
        all_response = db_service.client.table('loan_history').select('*').execute()
        fetched_count = len(all_response.data) if all_response.data else 0

        print(f"Successfully fetched: {fetched_count:,} records")

        if fetched_count < total_count:
            missing = total_count - fetched_count
            print(f"❌ Missing {missing:,} records ({missing/total_count*100:.1f}%)")

            # Try with different approaches
            print(f"\nTrying pagination approach...")
            all_loans = []
            limit = 1000
            offset = 0

            while True:
                batch_response = db_service.client.table('loan_history').select('*').range(offset, offset + limit - 1).execute()

                if not batch_response.data:
                    break

                all_loans.extend(batch_response.data)
                offset += limit
                print(f"   Fetched batch: {len(batch_response.data)} records (total: {len(all_loans):,})")

                if len(batch_response.data) < limit:
                    break

            print(f"✅ Pagination fetched: {len(all_loans):,} records")

        else:
            print(f"✅ Successfully fetched all {fetched_count:,} records in one query")

        # Test the same for other tables
        tables_to_test = ['approved_makes', 'media_partners']

        for table in tables_to_test:
            count_resp = db_service.client.table(table).select('*', count='exact').execute()
            total = count_resp.count

            fetch_resp = db_service.client.table(table).select('*').execute()
            fetched = len(fetch_resp.data) if fetch_resp.data else 0

            print(f"\n{table}: {fetched:,}/{total:,} records ({fetched/total*100:.1f}%)")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_direct_fetch())