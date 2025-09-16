"""Quick check of actual office names in vehicles table."""

import asyncio
from app.services.database import db_service

async def check_offices():
    # Get actual office names from vehicles table
    response = db_service.client.table('vehicles').select('office').execute()

    if response.data:
        offices = list(set([r['office'] for r in response.data]))
        print("Actual office names in vehicles table:")
        for office in sorted(offices):
            print(f"  '{office}'")

        # Check specific office
        la_count = len([r for r in response.data if r['office'] == 'Los Angeles'])
        print(f"\nLos Angeles vehicles: {la_count}")
    else:
        print("No vehicles found")

if __name__ == "__main__":
    asyncio.run(check_offices())