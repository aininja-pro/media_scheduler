import asyncio
from sqlalchemy import text
from app.services.database import engine  # imports the SAME engine your app uses

async def main():
    async with engine.connect() as conn:
        val = await conn.scalar(text("SELECT 1"))
        print("ENGINE SELECT 1 ->", val)

asyncio.run(main())