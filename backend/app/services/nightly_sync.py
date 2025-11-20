"""
Nightly Data Sync Service

Automatically syncs data from FMS CSV exports every night.

Syncs:
- Vehicles (active_vehicles.rpt)
- Media Partners (media_partners.rpt) - includes geocoding + preferred day analysis
- Loan History (loan_history.rpt)
- Current Activity (current_vehicle_activity.rpt)
- Approved Makes (approved_makes.rpt)

Manual only (NOT synced):
- Operations Data (Excel upload)
- Budgets (Excel upload)

Author: Ray Rierson
Date: November 12, 2025
"""

import logging
import httpx
import os
import pytz
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)
pacific_tz = pytz.timezone('America/Los_Angeles')

# FMS CSV Export URLs from environment
SYNC_URLS = {
    'vehicles': os.getenv('FMS_VEHICLES_CSV_URL', 'https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/active_vehicles.rpt&init=csv'),
    'media_partners': os.getenv('FMS_PARTNERS_CSV_URL', 'https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/media_partners.rpt&init=csv'),
    'loan_history': os.getenv('FMS_LOAN_HISTORY_CSV_URL', 'https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/loan_history.rpt&init=csv'),
    'current_activity': os.getenv('FMS_CURRENT_ACTIVITY_CSV_URL', 'https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/current_vehicle_activity.rpt&init=csv'),
    'approved_makes': os.getenv('FMS_APPROVED_MAKES_CSV_URL', 'https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/approved_makes.rpt&init=csv'),
    'budget_spending': os.getenv('FMS_BUDGET_SPENDING_CSV_URL', ''),  # User will provide URL
}

# API base URL (internal Docker network or localhost)
# Use 'backend' for Docker internal calls, 'localhost:8081' for local dev
API_BASE_URL = os.getenv('INTERNAL_API_URL', 'http://backend:8000')

# Global variable to track last successful sync
last_sync_result = None


async def sync_single_table(table_name: str, csv_url: str) -> Dict:
    """
    Sync a single table from FMS CSV export

    Args:
        table_name: Name of the table (vehicles, media_partners, etc.)
        csv_url: FMS CSV export URL

    Returns:
        Dict with sync result
    """
    logger.info(f"[Nightly Sync] Starting sync for {table_name}")

    try:
        # Choose the appropriate endpoint
        # Media partners uses /stream endpoint for progress tracking (includes geocoding)
        if table_name == 'media_partners':
            endpoint = f"{API_BASE_URL}/ingest/media_partners/url"
        else:
            endpoint = f"{API_BASE_URL}/ingest/{table_name}/url"

        # Call the ingest endpoint with the CSV URL
        async with httpx.AsyncClient(timeout=600.0) as client:  # 10 minute timeout
            response = await client.post(
                endpoint,
                params={'url': csv_url}
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"[Nightly Sync] ✓ {table_name} synced successfully: {result.get('rows_processed', 0)} rows")
                return {
                    'table': table_name,
                    'success': True,
                    'rows_processed': result.get('rows_processed', 0),
                    'rows_affected': result.get('rows_affected', 0),
                    'message': result.get('message', 'Success')
                }
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"[Nightly Sync] ✗ {table_name} sync failed: {error_msg}")
                return {
                    'table': table_name,
                    'success': False,
                    'error': error_msg
                }

    except httpx.TimeoutException:
        logger.error(f"[Nightly Sync] ✗ {table_name} sync timed out")
        return {
            'table': table_name,
            'success': False,
            'error': 'Request timed out after 10 minutes'
        }
    except Exception as e:
        logger.error(f"[Nightly Sync] ✗ {table_name} sync error: {str(e)}")
        return {
            'table': table_name,
            'success': False,
            'error': str(e)
        }


async def run_nightly_sync() -> Dict:
    """
    Run complete nightly sync for all tables

    Returns:
        Dict with summary of sync results
    """
    start_time = datetime.now(pacific_tz)
    logger.info(f"[Nightly Sync] ========================================")
    logger.info(f"[Nightly Sync] Starting nightly FMS data sync at {start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info(f"[Nightly Sync] ========================================")

    results: List[Dict] = []

    # Sync each table sequentially
    # Note: Media partners takes longest due to geocoding
    for table_name, csv_url in SYNC_URLS.items():
        if csv_url:  # Only sync if URL is configured
            result = await sync_single_table(table_name, csv_url)
            results.append(result)
        else:
            logger.warning(f"[Nightly Sync] ⚠ {table_name} skipped: No CSV URL configured")
            results.append({
                'table': table_name,
                'success': False,
                'error': 'No CSV URL configured'
            })

    # Summary
    end_time = datetime.now(pacific_tz)
    duration = (end_time - start_time).total_seconds()
    success_count = sum(1 for r in results if r['success'])
    failure_count = len(results) - success_count
    total_rows = sum(r.get('rows_processed', 0) for r in results if r['success'])

    logger.info(f"[Nightly Sync] ========================================")
    logger.info(f"[Nightly Sync] Nightly sync completed at {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"[Nightly Sync] Duration: {duration:.1f} seconds")
    logger.info(f"[Nightly Sync] Success: {success_count}/{len(results)} tables")
    logger.info(f"[Nightly Sync] Total rows processed: {total_rows}")

    if failure_count > 0:
        logger.warning(f"[Nightly Sync] ⚠ {failure_count} tables failed to sync")
        for result in results:
            if not result['success']:
                logger.warning(f"[Nightly Sync]   - {result['table']}: {result.get('error', 'Unknown error')}")

    logger.info(f"[Nightly Sync] ========================================")

    result_summary = {
        'start_time': start_time.isoformat(),
        'end_time': end_time.isoformat(),
        'duration_seconds': duration,
        'total_tables': len(results),
        'success_count': success_count,
        'failure_count': failure_count,
        'total_rows_processed': total_rows,
        'results': results
    }

    # Store in global variable for status endpoint
    global last_sync_result
    last_sync_result = result_summary

    return result_summary


def get_sync_config() -> Dict:
    """
    Get current sync configuration

    Returns:
        Dict with sync URLs and schedule
    """
    return {
        'sync_urls': {
            table: url if url else 'Not configured'
            for table, url in SYNC_URLS.items()
        },
        'sync_hour': int(os.getenv('SYNC_HOUR', 2)),
        'sync_minute': int(os.getenv('SYNC_MINUTE', 0)),
        'api_base_url': API_BASE_URL,
        'manual_only': ['operations_data', 'budgets']
    }


def get_last_sync_result() -> Dict:
    """
    Get last sync result (if any)

    Returns:
        Last sync result or None
    """
    return last_sync_result
