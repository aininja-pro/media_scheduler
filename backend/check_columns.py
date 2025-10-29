import asyncio
from app.services.database import DatabaseService
import pandas as pd

async def check():
    db = DatabaseService()
    await db.initialize()
    
    # Load one record to see column names
    response = db.client.table('current_activity').select('*').limit(1).execute()
    if response.data:
        print("Columns in current_activity table:")
        print(list(response.data[0].keys()))
        
    await db.close()

asyncio.run(check())
