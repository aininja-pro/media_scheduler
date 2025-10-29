import asyncio
from app.services.database import DatabaseService

async def debug():
    db = DatabaseService()
    await db.initialize()
    
    # Get total count of current_activity records
    response = db.client.table('current_activity').select('*', count='exact').execute()
    print(f"Total records in current_activity: {response.count}")
    
    # Get a few sample records to verify connection
    sample = db.client.table('current_activity').select('vehicle_vin, activity_id, to_field').limit(5).execute()
    print(f"\nSample records:")
    for record in sample.data:
        print(f"  VIN: {record['vehicle_vin']}, Activity: {record['activity_id']}, To: {record.get('to_field', 'N/A')}")
    
    # Try different search methods for the VIN
    test_vin = "JTEVB58R9S5000721"
    
    print(f"\n\nSearching for VIN: {test_vin}")
    print("Method 1: Direct eq query")
    result1 = db.client.table('current_activity').select('*').eq('vehicle_vin', test_vin).execute()
    print(f"  Found: {len(result1.data)} records")
    
    print("Method 2: ilike query (case-insensitive)")
    result2 = db.client.table('current_activity').select('*').ilike('vehicle_vin', test_vin).execute()
    print(f"  Found: {len(result2.data)} records")
    
    print("Method 3: contains query")
    result3 = db.client.table('current_activity').select('*').like('vehicle_vin', f'%{test_vin}%').execute()
    print(f"  Found: {len(result3.data)} records")
    
    await db.close()

asyncio.run(debug())
