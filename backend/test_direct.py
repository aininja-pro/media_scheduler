import asyncio
import asyncpg

async def test_direct_connection():
    """Test direct asyncpg connection without SQLAlchemy"""
    try:
        # Use the exact same connection that worked before
        conn = await asyncpg.connect('postgresql://postgres:labe1234Kirk!@akhiqayfjmnrzsofmwrv.supabase.co:5432/postgres')
        
        # Test basic query
        result = await conn.fetchval('SELECT 1')
        print(f"DIRECT CONNECTION SUCCESS: {result}")
        
        # Test actual database operation - create a test table and insert
        await conn.execute('CREATE TABLE IF NOT EXISTS test_connection (id SERIAL PRIMARY KEY, test_data TEXT)')
        await conn.execute("INSERT INTO test_connection (test_data) VALUES ('test_insert')")
        
        # Query back the data
        rows = await conn.fetch('SELECT * FROM test_connection LIMIT 1')
        print(f"DIRECT INSERT/SELECT SUCCESS: {len(rows)} rows")
        
        # Cleanup
        await conn.execute('DROP TABLE test_connection')
        
        await conn.close()
        print("DIRECT ASYNCPG: ALL OPERATIONS SUCCESSFUL")
        
    except Exception as e:
        print(f"DIRECT ASYNCPG FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_direct_connection())