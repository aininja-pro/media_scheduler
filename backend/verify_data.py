import asyncio
from app.services.database import DatabaseService
import pandas as pd

async def verify():
    db = DatabaseService()
    await db.initialize()
    
    test_vin = "JTEVB58R9S5000721"
    
    # Check current_activity table directly
    print(f"Checking for VIN {test_vin} in current_activity table...")
    response = db.client.table('current_activity').select('*').eq('vehicle_vin', test_vin).execute()
    
    print(f"\nFound {len(response.data)} records")
    if response.data:
        for record in response.data:
            print(f"  Activity ID: {record['activity_id']}")
            print(f"  Type: {record['activity_type']}")
            print(f"  Start: {record['start_date']}")
            print(f"  End: {record['end_date']}")
            print(f"  To: {record.get('to_field', 'N/A')}")
            print()
    
    await db.close()

asyncio.run(verify())
