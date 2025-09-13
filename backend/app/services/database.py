"""
Database service using Supabase Python client.
"""
import os
import logging
from typing import List, Dict, Any
from pydantic import BaseModel
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = "https://akhiqayfjmnrzsofmwrv.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFraGlxYXlmam1ucnpzb2Ztd3J2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY5OTI5NjcsImV4cCI6MjA3MjU2ODk2N30.nfKgjSQoJPWr2qn8LQyLF8QYMeOrxwkikBc3opKhY5Y"


class DatabaseService:
    """Database service using Supabase Python client"""
    
    def __init__(self):
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        self._initialized = True
        logger.info("Supabase client initialized")
    
    async def initialize(self):
        """No-op - client is ready immediately"""
        logger.info("Database service initialized")
    
    async def close(self):
        """No-op - Supabase client handles connections automatically"""
        logger.info("Database service closed")
    
    async def test_connection(self) -> bool:
        """Test database connection using a simple query"""
        try:
            # Test connection by querying the vehicles table (should exist)
            response = self.client.table('vehicles').select('*').limit(1).execute()
            logger.info(f"Database connection test: SUCCESS")
            return True
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
        """Upsert records using Supabase client"""
        if not records:
            return {"rows_processed": 0, "rows_affected": 0}
        
        try:
            # Convert Pydantic models to dicts with date serialization
            record_dicts = []
            
            # Get the upsert column 
            upsert_column = self._get_upsert_column(table_name, primary_key, conflict_columns)
            
            # For approved_makes, we want ALL records but need to dedupe within batch
            if table_name == "approved_makes":
                seen_combinations = set()  # Track person_id + make combinations
                
                for record in records:
                    record_dict = record.model_dump()
                    # Convert date objects to strings for JSON serialization
                    for key, value in record_dict.items():
                        if hasattr(value, 'isoformat'):  # Check if it's a date/datetime object
                            record_dict[key] = value.isoformat()
                    
                    # Create a unique key for person_id + make combination
                    combo_key = f"{record_dict['person_id']}_{record_dict['make']}"
                    
                    if combo_key not in seen_combinations:
                        seen_combinations.add(combo_key)
                        record_dicts.append(record_dict)
                    else:
                        logger.warning(f"Skipping duplicate person_id+make: {record_dict['person_id']} + {record_dict['make']}")
            else:
                # For other tables, use duplicate detection
                seen_keys = set()  # Track unique constraint values to avoid duplicates
                
                for record in records:
                    record_dict = record.model_dump()
                    # Convert date objects to strings for JSON serialization
                    for key, value in record_dict.items():
                        if hasattr(value, 'isoformat'):  # Check if it's a date/datetime object
                            record_dict[key] = value.isoformat()
                    
                    # Check for duplicates based on upsert column
                    upsert_value = record_dict.get(upsert_column)
                    if upsert_value and upsert_value not in seen_keys:
                        seen_keys.add(upsert_value)
                        record_dicts.append(record_dict)
                    elif upsert_value:
                        logger.warning(f"Skipping duplicate {upsert_column}: {upsert_value}")
            
            
            logger.info(f"Upserting {len(record_dicts)} records to {table_name} with upsert column: {upsert_column}")
            
            # Special handling for tables with composite keys
            if table_name == "approved_makes":
                # For approved_makes, delete all existing records for the person_ids first
                person_ids = list(set([record['person_id'] for record in record_dicts]))
                logger.info(f"Deleting existing records for {len(person_ids)} person_ids")
                
                # Delete existing records for these person_ids in one operation
                if person_ids:
                    self.client.table(table_name).delete().in_('person_id', person_ids).execute()
                
                # Insert all new records
                logger.info(f"Inserting {len(record_dicts)} new approved_makes records")
                response = self.client.table(table_name).insert(record_dicts, count='exact').execute()
            else:
                # Regular upsert for other tables
                response = self.client.table(table_name).upsert(
                    record_dicts,
                    on_conflict=upsert_column,
                    count='exact'
                ).execute()
            
            rows_affected = len(response.data) if response.data else 0
            
            logger.info(f"Successfully upserted {rows_affected} records to {table_name}")
            
            return {
                "rows_processed": len(record_dicts),
                "rows_affected": rows_affected,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Error upserting records to {table_name}: {e}")
            raise
    
    def _get_upsert_column(self, table_name: str, primary_key: str = None, conflict_columns: List[str] = None) -> str:
        """Get the appropriate upsert column for each table"""
        if conflict_columns:
            return conflict_columns[0] if len(conflict_columns) == 1 else ",".join(conflict_columns)
        
        if primary_key:
            return primary_key
            
        # Default upsert columns for each table - use lists for composite keys
        table_upsert_columns = {
            "vehicles": "vin",
            "media_partners": "person_id",
            "approved_makes": "person_id",  # Use person_id as primary upsert key
            "partner_make_rank": ["partner_id", "make"], 
            "loan_history": "loan_id",
            "current_activity": "activity_id",
            "ops_capacity": "office",
            "budgets": ["office", "make", "year", "quarter"]  # Composite key as list
        }
        
        upsert_col = table_upsert_columns.get(table_name, "id")
        
        # If it's a list (composite key), join with commas
        if isinstance(upsert_col, list):
            return ",".join(upsert_col)
        return upsert_col


# Global database service instance
db_service = DatabaseService()


async def get_database() -> DatabaseService:
    """Dependency injection for database service"""
    return db_service