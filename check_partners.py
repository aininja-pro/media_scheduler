import asyncio
from app.services.database import DatabaseService

async def check():
    db = DatabaseService()
    await db.initialize()
    
    # Get a sample partner
    response = db.client.table('partners').select('*').limit(3).execute()
    if response.data:
        print("Sample partners:")
        for partner in response.data:
            print(f"\nPartner ID: {partner.get('person_id')}")
            print(f"  Columns: {list(partner.keys())}")
            if 'latitude' in partner or 'longitude' in partner:
                print(f"  Lat/Lon: {partner.get('latitude')}, {partner.get('longitude')}")
    
    await db.close()

asyncio.run(check())
