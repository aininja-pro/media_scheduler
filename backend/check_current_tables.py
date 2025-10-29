"""Check what tables currently exist in the database."""

import asyncio
from app.services.database import DatabaseService

async def check_tables():
    db = DatabaseService()
    await db.initialize()

    # Tables we need for Phase 7.1
    required_tables = [
        'vehicles',
        'media_partners',
        'approved_makes',
        'ops_capacity',           # Current table
        'ops_capacity_calendar',  # New table needed
        'model_taxonomy',         # New table needed
        'loan_history',
        'current_activity',
        'rules'
    ]

    print("Checking tables in database:\n")

    for table_name in required_tables:
        try:
            # Try to query the table
            response = db.client.table(table_name).select('*').limit(1).execute()
            count_response = db.client.table(table_name).select('*', count='exact').execute()
            record_count = count_response.count if hasattr(count_response, 'count') else len(response.data)

            # Get columns from first record or empty dict
            if response.data:
                columns = list(response.data[0].keys())
            else:
                columns = []

            print(f"✓ {table_name}: EXISTS ({record_count} records)")
            if columns:
                print(f"  Columns: {', '.join(columns)}")
        except Exception as e:
            if "relation" in str(e).lower() and "does not exist" in str(e).lower():
                print(f"✗ {table_name}: DOES NOT EXIST")
            else:
                print(f"? {table_name}: Error - {str(e)}")
        print()

    # Check specific schema of ops_capacity
    print("\n--- Current ops_capacity schema ---")
    try:
        response = db.client.table('ops_capacity').select('*').limit(5).execute()
        if response.data:
            print("Sample data:")
            for row in response.data:
                print(f"  {row}")
        else:
            print("No data in table")
    except Exception as e:
        print(f"Error: {e}")

    await db.close()

if __name__ == "__main__":
    asyncio.run(check_tables())