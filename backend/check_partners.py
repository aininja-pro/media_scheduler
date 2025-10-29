import asyncio
from app.services.database import DatabaseService

async def check():
    db = DatabaseService()
    await db.initialize()
    
    # Get a sample partner
    response = db.client.table('media_partners').select('*').limit(3).execute()
    if response.data:
        print("Sample partners columns:")
        print(list(response.data[0].keys()))
        
        # Check if we have geocoding
        has_lat_lon = 'latitude' in response.data[0] or 'longitude' in response.data[0]
        print(f"\nHas lat/lon: {has_lat_lon}")
        
        if has_lat_lon:
            for partner in response.data:
                print(f"\n{partner.get('name')}: {partner.get('latitude')}, {partner.get('longitude')}")
    
    await db.close()

asyncio.run(check())
