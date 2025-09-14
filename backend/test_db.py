import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = (
    "postgresql+psycopg://postgres:labe1234Kirk!@"
    "db.akhiqayfjmnrzsofmwrv.supabase.co:5432/postgres?sslmode=require"
)

engine = create_async_engine(
    DATABASE_URL,
    poolclass=None,
    pool_pre_ping=True,
)

async def main():
    async with engine.connect() as conn:
        val = await conn.scalar(text("SELECT 1"))
        print("SELECT 1 ->", val)

asyncio.run(main())