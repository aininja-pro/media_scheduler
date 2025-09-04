"""
CSV Ingest API endpoints for uploading and validating data.
"""
import pandas as pd
from fastapi import APIRouter, UploadFile, HTTPException, Depends
from typing import Dict, Any, List
from io import StringIO
import logging

from ..schemas.ingest import INGEST_SCHEMAS
from ..services.database import get_database, DatabaseService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/{table}")
async def ingest_csv(
    table: str, 
    file: UploadFile,
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    Ingest CSV data for a specific table.
    
    Args:
        table: The target table name (vehicles, media_partners, etc.)
        file: CSV file upload
        
    Returns:
        Dict with ingestion results and row counts
    """
    if table not in INGEST_SCHEMAS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid table name '{table}'. Valid tables: {list(INGEST_SCHEMAS.keys())}"
        )
    
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=400,
            detail="File must be a CSV file"
        )
    
    try:
        # Read CSV content
        content = await file.read()
        csv_content = content.decode('utf-8')
        
        # Parse CSV with pandas
        df = pd.read_csv(StringIO(csv_content))
        
        if df.empty:
            raise HTTPException(
                status_code=400,
                detail="CSV file is empty"
            )
        
        logger.info(f"Processing {len(df)} rows for table '{table}'")
        
        # Get the appropriate schema
        schema_class = INGEST_SCHEMAS[table]
        
        # Validate each row
        validated_rows = []
        validation_errors = []
        
        for index, row in df.iterrows():
            try:
                # Convert pandas Series to dict and handle NaN values
                row_dict = row.to_dict()
                
                # Replace NaN with None for proper validation
                for key, value in row_dict.items():
                    if pd.isna(value):
                        row_dict[key] = None
                
                # Validate using Pydantic schema
                validated_row = schema_class(**row_dict)
                validated_rows.append(validated_row)
                
            except Exception as e:
                validation_errors.append({
                    "row": index + 2,  # +2 because pandas is 0-indexed and we account for header
                    "error": str(e)
                })
                
                # Stop after 5 errors to avoid overwhelming response
                if len(validation_errors) >= 5:
                    break
        
        # If there are validation errors, return them
        if validation_errors:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": f"Validation errors found in CSV",
                    "errors": validation_errors,
                    "total_rows": len(df),
                    "error_count": len(validation_errors)
                }
            )
        
        # Perform database upsert
        try:
            upsert_result = await db.upsert_records(
                table_name=table,
                records=validated_rows
            )
            
            logger.info(f"Successfully upserted {len(validated_rows)} rows to table '{table}'")
            
            return {
                "table": table,
                "rows_processed": len(validated_rows),
                "rows_affected": upsert_result.get("rows_affected", 0),
                "status": "success",
                "message": f"Successfully processed {len(validated_rows)} rows for table '{table}'"
            }
            
        except Exception as e:
            logger.error(f"Database upsert failed for table '{table}': {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Database operation failed: {str(e)}"
            )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error processing CSV for table '{table}': {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing CSV file: {str(e)}"
        )