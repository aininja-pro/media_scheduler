"""
Database connection and operations service using SQLAlchemy with AsyncPG.
Handles connections to Supabase PostgreSQL and provides upsert functionality.
"""
import os
import logging
from typing import List, Dict, Any, Optional, Type
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text, MetaData
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base"""
    pass


class DatabaseService:
    """Async database service for Supabase PostgreSQL operations"""
    
    def __init__(self):
        self.engine = None
        self.async_session_maker = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize database connection"""
        if self._initialized:
            return
        
        # Get database URL from environment
        database_url = os.getenv("POSTGRES_URL")
        if not database_url:
            raise ValueError("POSTGRES_URL environment variable is required")
        
        # Convert to async URL if needed
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif not database_url.startswith("postgresql+asyncpg://"):
            database_url = f"postgresql+asyncpg://{database_url}"
        
        # Create async engine
        self.engine = create_async_engine(
            database_url,
            echo=False,  # Set to True for SQL debugging
            pool_pre_ping=True,
            pool_recycle=300,
        )
        
        # Create session maker
        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        self._initialized = True
        logger.info("Database service initialized")
    
    async def close(self):
        """Close database connections"""
        if self.engine:
            await self.engine.dispose()
        self._initialized = False
        logger.info("Database service closed")
    
    @asynccontextmanager
    async def get_session(self):
        """Get async database session context manager"""
        if not self._initialized:
            await self.initialize()
        
        async with self.async_session_maker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def test_connection(self) -> bool:
        """Test database connection"""
        try:
            async with self.get_session() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    async def upsert_records(
        self, 
        table_name: str, 
        records: List[BaseModel], 
        primary_key: str = None,
        conflict_columns: List[str] = None
    ) -> Dict[str, Any]:
        """
        Upsert records into a table using PostgreSQL ON CONFLICT.
        
        Args:
            table_name: Target table name
            records: List of Pydantic models to upsert
            primary_key: Primary key column name (optional)
            conflict_columns: Columns to check for conflicts (optional)
            
        Returns:
            Dict with operation results
        """
        if not records:
            return {"rows_processed": 0, "rows_inserted": 0, "rows_updated": 0}
        
        try:
            async with self.get_session() as session:
                # Convert Pydantic models to dicts
                record_dicts = [record.model_dump() for record in records]
                
                # Determine conflict columns based on table
                if not conflict_columns:
                    conflict_columns = self._get_default_conflict_columns(table_name, primary_key)
                
                # Build the upsert query
                columns = list(record_dicts[0].keys())
                values_placeholder = ", ".join([f":{col}" for col in columns])
                
                # Handle different conflict resolution strategies per table
                update_clause = self._build_update_clause(table_name, columns, conflict_columns)
                
                upsert_query = f"""
                INSERT INTO {table_name} ({", ".join(columns)})
                VALUES ({values_placeholder})
                ON CONFLICT ({", ".join(conflict_columns)})
                {update_clause}
                """
                
                # Execute the upsert for each record
                rows_affected = 0
                for record_dict in record_dicts:
                    result = await session.execute(text(upsert_query), record_dict)
                    rows_affected += result.rowcount
                
                await session.commit()
                
                logger.info(f"Upserted {rows_affected} records to {table_name}")
                
                return {
                    "rows_processed": len(record_dicts),
                    "rows_affected": rows_affected,
                    "status": "success"
                }
                
        except Exception as e:
            logger.error(f"Error upserting records to {table_name}: {e}")
            raise
    
    def _get_default_conflict_columns(self, table_name: str, primary_key: str = None) -> List[str]:
        """Get default conflict columns for each table"""
        table_conflicts = {
            "vehicles": ["vin"],
            "media_partners": ["partner_id"],
            "partner_make_rank": ["partner_id", "make"],
            "loan_history": ["loan_id"] if not primary_key else [primary_key],
            "current_activity": ["activity_id"] if not primary_key else [primary_key],
            "ops_capacity": ["office"],
            "budgets": ["office", "make", "year", "quarter"]
        }
        
        return table_conflicts.get(table_name, [primary_key] if primary_key else ["id"])
    
    def _build_update_clause(self, table_name: str, columns: List[str], conflict_columns: List[str]) -> str:
        """Build the DO UPDATE clause for upsert"""
        # Exclude conflict columns and auto-generated columns from updates
        exclude_columns = set(conflict_columns + ["created_at", "updated_at", "id", "loan_id", "activity_id", "log_id"])
        update_columns = [col for col in columns if col not in exclude_columns]
        
        if not update_columns:
            return "DO NOTHING"
        
        update_assignments = [f"{col} = EXCLUDED.{col}" for col in update_columns]
        
        # Add updated_at if the table has this column
        if table_name not in ["schedulers", "published_schedules", "audit_log"]:
            update_assignments.append("updated_at = now()")
        
        return f"DO UPDATE SET {', '.join(update_assignments)}"


# Global database service instance
db_service = DatabaseService()


async def get_database() -> DatabaseService:
    """Dependency injection for database service"""
    if not db_service._initialized:
        await db_service.initialize()
    return db_service