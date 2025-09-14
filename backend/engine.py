import ssl
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = "postgresql+asyncpg://postgres:labe1234Kirk!@db.akhiqayfjmnrzsofmwrv.supabase.co:5432/postgres"

ssl_ctx = ssl.create_default_context()

engine = create_async_engine(
    DATABASE_URL,
    poolclass=None,                 # no pooling while testing
    pool_pre_ping=True,
    connect_args={"ssl": ssl_ctx},  # <-- valid for asyncpg
)

# SMOKE TEST
async def smoke():
    async with engine.connect() as conn:
        val = await conn.scalar(text("SELECT 1"))
        print("SELECT 1 ->", val)