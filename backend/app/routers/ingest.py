"""
CSV Ingest API endpoints for uploading and validating data.
"""
import pandas as pd
import httpx
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


@router.post("/vehicles/url")
async def ingest_vehicles_from_url(
    url: str,
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    Fetch and ingest vehicles data directly from a URL.
    
    Args:
        url: The URL to fetch CSV data from
        
    Returns:
        Dict with ingestion results and row counts
    """
    try:
        # Fetch CSV data from URL with proper headers
        headers = {
            'User-Agent': 'curl/8.7.1',
            'Accept': '*/*',
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            csv_content = response.text
            
            # Log response info
            logger.info(f"Fetched CSV: {response.status_code}, {len(csv_content)} chars, content-type: {response.headers.get('content-type')}")
        
        # Parse CSV without headers since client data doesn't have them
        # Add the correct column headers manually
        expected_headers = [
            'Year', 'Make', 'Model', 'Model Short Name', 'Office', 
            'VIN', 'Fleet', 'Registration Exp', 'Insurance Exp', 
            'Current Mileage', 'In Service Date', 'Expected Turn In Date', 'Notes'
        ]
        
        df = pd.read_csv(StringIO(csv_content), header=None, names=expected_headers)
        
        if df.empty:
            raise HTTPException(
                status_code=400,
                detail="CSV data from URL is empty"
            )
        
        logger.info(f"Parsed CSV: {len(df)} rows with headers: {list(df.columns)}")
        
        # Get the vehicles schema
        schema_class = INGEST_SCHEMAS["vehicles"]
        
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
                
                # Direct mapping from exact CSV headers to schema fields
                csv_header_mapping = {
                    'Year': 'year',
                    'Make': 'make',
                    'Model': 'model',
                    'Model Short Name': 'model_short_name',
                    'Office': 'office',
                    'VIN': 'vin',
                    'Fleet': 'fleet',
                    'Registration Exp': 'registration_exp',
                    'Insurance Exp': 'insurance_exp',
                    'Current Mileage': 'current_mileage',
                    'In Service Date': 'in_service_date',
                    'Expected Turn In Date': 'expected_turn_in_date',
                    'Notes': 'notes'
                }
                
                normalized_dict = {}
                for csv_header, value in row_dict.items():
                    # Map exact CSV header to our schema field
                    schema_field = csv_header_mapping.get(csv_header)
                    if schema_field:
                        normalized_dict[schema_field] = value
                
                # Log VIN info for first few rows to check for duplicates
                if index < 5:
                    vin_value = normalized_dict.get('vin')
                    logger.info(f"Row {index}: VIN = '{vin_value}'")
                
                # Validate using Pydantic schema
                validated_row = schema_class(**normalized_dict)
                validated_rows.append(validated_row)
                
            except Exception as e:
                validation_errors.append({
                    "row": index + 2,
                    "error": str(e),
                    "data": dict(row_dict) if len(str(e)) < 200 else "Data too large to display"
                })
                
                # Stop after 5 errors to avoid overwhelming response
                if len(validation_errors) >= 5:
                    break
        
        # If there are validation errors, return them
        if validation_errors:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": f"Validation errors found in fetched CSV data",
                    "errors": validation_errors,
                    "total_rows": len(df),
                    "error_count": len(validation_errors)
                }
            )
        
        # Perform database upsert
        try:
            upsert_result = await db.upsert_records(
                table_name="vehicles",
                records=validated_rows
            )
            
            logger.info(f"Successfully upserted {len(validated_rows)} vehicles from URL")
            
            return {
                "table": "vehicles",
                "source": "url", 
                "url": url,
                "rows_processed": len(validated_rows),
                "rows_affected": upsert_result.get("rows_affected", 0),
                "status": "success",
                "message": f"Successfully fetched and processed {len(validated_rows)} vehicles from URL"
            }
            
        except Exception as e:
            logger.error(f"Database upsert failed for vehicles from URL: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Database operation failed: {str(e)}"
            )
        
    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch data from URL {url}: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch data from URL: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error processing CSV from URL {url}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing CSV from URL: {str(e)}"
        )


@router.post("/approved_makes/url")
async def ingest_approved_makes_from_url(url: str, db: DatabaseService = Depends(get_database)):
    """Fetch and ingest approved makes data from URL."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers={'User-Agent': 'curl/8.7.1'})
            response.raise_for_status()
            
        df = pd.read_csv(StringIO(response.text), header=None, names=['Person_ID', 'Name', 'Make', 'Rank'])
        validated_rows = []
        
        for index, row in df.iterrows():
            row_dict = row.to_dict()
            for key, value in row_dict.items():
                if pd.isna(value):
                    row_dict[key] = None
            
            normalized_dict = {
                'person_id': row_dict['Person_ID'],
                'name': row_dict['Name'], 
                'make': row_dict['Make'],
                'rank': row_dict['Rank']
            }
            
            validated_row = INGEST_SCHEMAS["approved_makes"](**normalized_dict)
            validated_rows.append(validated_row)
        
        upsert_result = await db.upsert_records(table_name="approved_makes", records=validated_rows)
        
        return {
            "table": "approved_makes",
            "rows_processed": len(validated_rows),
            "rows_affected": upsert_result.get("rows_affected", 0),
            "status": "success",
            "message": f"Successfully processed {len(validated_rows)} approved makes"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.post("/media_partners/url")
async def ingest_media_partners_from_url(
    url: str,
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    Fetch and ingest media partners data directly from a URL.
    
    Args:
        url: The URL to fetch CSV data from
        
    Returns:
        Dict with ingestion results and row counts
    """
    try:
        # Fetch CSV data from URL with proper headers
        headers = {
            'User-Agent': 'curl/8.7.1',
            'Accept': '*/*',
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            csv_content = response.text
            
            # Log response info
            logger.info(f"Fetched CSV: {response.status_code}, {len(csv_content)} chars, content-type: {response.headers.get('content-type')}")
        
        # Parse CSV without headers since client data doesn't have them
        # Add the correct column headers manually for media partners
        expected_headers = [
            'Person_ID', 'Name', 'Office', 'Default loan region', 'Notes / Instructions'
        ]
        
        df = pd.read_csv(StringIO(csv_content), header=None, names=expected_headers)
        
        if df.empty:
            raise HTTPException(
                status_code=400,
                detail="CSV data from URL is empty"
            )
        
        logger.info(f"Parsed CSV: {len(df)} rows with headers: {list(df.columns)}")
        
        # Get the media partners schema
        schema_class = INGEST_SCHEMAS["media_partners"]
        
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
                
                # Direct mapping from exact CSV headers to schema fields
                csv_header_mapping = {
                    'Person_ID': 'person_id',
                    'Name': 'name',
                    'Office': 'office',
                    'Default loan region': 'default_loan_region',
                    'Notes / Instructions': 'notes_instructions'
                }
                
                normalized_dict = {}
                for csv_header, value in row_dict.items():
                    # Map exact CSV header to our schema field
                    schema_field = csv_header_mapping.get(csv_header)
                    if schema_field:
                        normalized_dict[schema_field] = value
                
                # Log person_id info for first few rows to check for duplicates
                if index < 5:
                    person_id_value = normalized_dict.get('person_id')
                    logger.info(f"Row {index}: Person_ID = '{person_id_value}'")
                
                # Validate using Pydantic schema
                validated_row = schema_class(**normalized_dict)
                validated_rows.append(validated_row)
                
            except Exception as e:
                validation_errors.append({
                    "row": index + 2,
                    "error": str(e),
                    "data": dict(row_dict) if len(str(e)) < 200 else "Data too large to display"
                })
                
                # Stop after 5 errors to avoid overwhelming response
                if len(validation_errors) >= 5:
                    break
        
        # If there are validation errors, return them
        if validation_errors:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": f"Validation errors found in fetched CSV data",
                    "errors": validation_errors,
                    "total_rows": len(df),
                    "error_count": len(validation_errors)
                }
            )
        
        # Perform database upsert
        try:
            upsert_result = await db.upsert_records(
                table_name="media_partners",
                records=validated_rows
            )
            
            logger.info(f"Successfully upserted {len(validated_rows)} media partners from URL")
            
            return {
                "table": "media_partners",
                "source": "url", 
                "url": url,
                "rows_processed": len(validated_rows),
                "rows_affected": upsert_result.get("rows_affected", 0),
                "status": "success",
                "message": f"Successfully fetched and processed {len(validated_rows)} media partners from URL"
            }
            
        except Exception as e:
            logger.error(f"Database upsert failed for media partners from URL: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Database operation failed: {str(e)}"
            )
        
    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch data from URL {url}: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch data from URL: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error processing CSV from URL {url}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing CSV from URL: {str(e)}"
        )


@router.post("/approved_makes/url")
async def ingest_approved_makes_from_url(url: str, db: DatabaseService = Depends(get_database)):
    """Fetch and ingest approved makes data from URL."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers={'User-Agent': 'curl/8.7.1'})
            response.raise_for_status()
            
        df = pd.read_csv(StringIO(response.text), header=None, names=['Person_ID', 'Name', 'Make', 'Rank'])
        validated_rows = []
        
        for index, row in df.iterrows():
            row_dict = row.to_dict()
            for key, value in row_dict.items():
                if pd.isna(value):
                    row_dict[key] = None
            
            normalized_dict = {
                'person_id': row_dict['Person_ID'],
                'name': row_dict['Name'], 
                'make': row_dict['Make'],
                'rank': row_dict['Rank']
            }
            
            validated_row = INGEST_SCHEMAS["approved_makes"](**normalized_dict)
            validated_rows.append(validated_row)
        
        upsert_result = await db.upsert_records(table_name="approved_makes", records=validated_rows)
        
        return {
            "table": "approved_makes",
            "rows_processed": len(validated_rows),
            "rows_affected": upsert_result.get("rows_affected", 0),
            "status": "success",
            "message": f"Successfully processed {len(validated_rows)} approved makes"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.post("/loan_history/url")
async def ingest_loan_history_from_url(url: str, db: DatabaseService = Depends(get_database)):
    """Fetch and ingest loan history data from URL."""
    try:
        logger.info(f"Fetching loan history data from URL (this may take several minutes for large files)...")
        async with httpx.AsyncClient(timeout=300.0) as client:  # 5 minute timeout
            response = await client.get(url, headers={'User-Agent': 'curl/8.7.1'})
            response.raise_for_status()
            logger.info(f"Download complete! Processing CSV data...")
            
        df = pd.read_csv(StringIO(response.text), header=None, names=[
            'Activity_ID', 'VIN', 'Person_ID', 'Make', 'Model', 'Year', 'Model_Short_Name', 
            'Start_Date', 'End_Date', 'Office', 'Name'
        ])
        
        # Optimize: Process in chunks and use vectorized operations
        df = df.fillna('')  # Replace NaN with empty strings for faster processing
        
        # Convert to records for faster batch processing
        records = df.to_dict('records')
        validated_rows = []
        skipped_count = 0
        
        logger.info(f"Processing {len(records)} loan history records in batches...")
        
        # Process in smaller chunks for better memory management
        chunk_size = 1000
        total_chunks = (len(records) - 1) // chunk_size + 1
        
        for i in range(0, len(records), chunk_size):
            chunk = records[i:i+chunk_size]
            chunk_num = i//chunk_size + 1
            logger.info(f"Processing chunk {chunk_num}/{total_chunks} ({len(validated_rows)} valid, {skipped_count} skipped so far)")
            
            for record in chunk:
                try:
                    normalized_dict = {
                        'activity_id': str(record['Activity_ID']).strip(),
                        'vin': str(record['VIN']).strip(),
                        'person_id': str(record['Person_ID']).strip(),
                        'make': str(record['Make']).strip(),
                        'model': str(record['Model']).strip(),
                        'year': record['Year'] if record['Year'] else None,
                        'model_short_name': str(record['Model_Short_Name']).strip() if record['Model_Short_Name'] else None,
                        'start_date': str(record['Start_Date']).strip(),
                        'end_date': str(record['End_Date']).strip(),
                        'office': str(record['Office']).strip(),
                        'name': str(record['Name']).strip()
                    }
                    
                    # Quick validation - skip if missing required fields
                    if not normalized_dict['activity_id'] or not normalized_dict['vin'] or not normalized_dict['person_id']:
                        skipped_count += 1
                        continue
                        
                    validated_row = INGEST_SCHEMAS["loan_history"](**normalized_dict)
                    validated_rows.append(validated_row)
                except Exception:
                    # Skip invalid records quietly to avoid spam
                    skipped_count += 1
                    continue
        
        logger.info(f"Validation complete! {len(validated_rows)} valid records, {skipped_count} records skipped due to missing data")
        
        logger.info(f"Validation complete! Uploading {len(validated_rows)} records to Supabase...")
        upsert_result = await db.upsert_records(table_name="loan_history", records=validated_rows)
        logger.info(f"Upload complete! {upsert_result.get('rows_affected', 0)} records affected.")
        
        return {
            "table": "loan_history",
            "rows_processed": len(validated_rows),
            "rows_affected": upsert_result.get("rows_affected", 0),
            "status": "success",
            "message": f"Successfully processed {len(validated_rows)} loan history records"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
