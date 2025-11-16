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
            
            # Detect composite vs single key
            is_composite = ',' in upsert_column
            seen_keys = set()
            
            for record in records:
                record_dict = record.model_dump()
                # Convert date objects to strings for JSON serialization
                for key, value in record_dict.items():
                    if hasattr(value, 'isoformat'):  # Check if it's a date/datetime object
                        record_dict[key] = value.isoformat()
                
                # Build dedupe key for composite or single columns
                if table_name == "approved_makes":
                    # Special handling for approved_makes
                    combo_key = f"{record_dict['person_id']}_{record_dict['make']}"
                    dedupe_key = combo_key
                elif is_composite:
                    key_parts = self._split_composite_columns(upsert_column)
                    try:
                        dedupe_key = tuple(record_dict[k] for k in key_parts)
                    except KeyError as e:
                        # If mapping is wrong, keep the record and log to avoid dropping all rows
                        logger.warning(f"Missing composite key fields for {table_name}: needed {key_parts}, got keys {list(record_dict.keys())}, error: {e}")
                        dedupe_key = None
                else:
                    dedupe_key = record_dict.get(upsert_column)
                
                # Add record if not duplicate
                if dedupe_key is None:
                    # No dedupe key → still include the row (better to insert than to drop everything)
                    record_dicts.append(record_dict)
                elif dedupe_key not in seen_keys:
                    seen_keys.add(dedupe_key)
                    record_dicts.append(record_dict)
                else:
                    logger.warning(f"Skipping duplicate key for {table_name}: {dedupe_key}")
            
            # Safety check - never call insert/upsert with empty payload
            if not record_dicts:
                logger.error(f"Refusing to call insert/upsert with empty payload for {table_name}. Check upstream validation/dedupe.")
                return {"rows_processed": 0, "rows_affected": 0, "status": "noop"}
            
            logger.info(f"Upserting {len(record_dicts)} records to {table_name} with upsert column: {upsert_column}")
            
            # Defensive check - never call DB with empty payload
            if not record_dicts:
                raise ValueError(f"No records to write for {table_name}")
            
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
            elif table_name in ["holiday_blackout_dates", "rules", "budgets"]:
                # Use proper upsert with composite keys
                logger.info(f"Upserting {len(record_dicts)} records to {table_name} with composite key: {upsert_column}")
                response = self.client.table(table_name).upsert(
                    record_dicts,
                    on_conflict=upsert_column
                ).execute()
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
    
    def _split_composite_columns(self, upsert_column: str) -> List[str]:
        """Split composite column string into individual column names"""
        return [c.strip() for c in upsert_column.split(',') if c.strip()]
    
    def _get_upsert_column(self, table_name: str, primary_key: str = None, conflict_columns: List[str] = None) -> str:
        """Get the appropriate upsert column for each table"""
        if conflict_columns:
            return conflict_columns[0] if len(conflict_columns) == 1 else ",".join(conflict_columns)
        
        if primary_key:
            return primary_key
            
        # Default upsert columns for each table - use lists for composite keys
        table_upsert_columns = {
            "vehicles": "vin",
            "media_partners": "person_id,office",  # Composite key (person can be in multiple offices)
            "approved_makes": "person_id",  # Use person_id as primary upsert key
            "partner_make_rank": ["partner_id", "make"],
            "loan_history": "activity_id",
            "current_activity": "activity_id",
            "ops_capacity": "office",
            "holiday_blackout_dates": "office,date,holiday_name",  # Composite primary key
            "rules": "make,rank",  # Composite primary key
            "budgets": "office,fleet,year,quarter"  # Composite key matching new table structure
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