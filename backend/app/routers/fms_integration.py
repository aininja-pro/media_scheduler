"""
FMS Integration Router
Handles bi-directional communication with Ruby on Rails FMS system

Key operations:
- Create vehicle requests in FMS (when user marks assignment as 'requested')
- Delete vehicle requests from FMS (when user deletes or unrequests)
- Bulk operations for Chain Builder

Author: Ray Rierson
Date: 2025-11-12
"""

from fastapi import APIRouter, HTTPException
from typing import List
from pydantic import BaseModel
import httpx
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fms", tags=["FMS Integration"])

# Environment configuration
FMS_ENVIRONMENT = os.getenv("FMS_ENVIRONMENT", "staging")
FMS_STAGING_URL = os.getenv("FMS_STAGING_URL", "https://staging.driveshop.com")
FMS_PRODUCTION_URL = os.getenv("FMS_PRODUCTION_URL", "https://fms.driveshop.com")
FMS_BASE_URL = FMS_PRODUCTION_URL if FMS_ENVIRONMENT == "production" else FMS_STAGING_URL

FMS_STAGING_TOKEN = os.getenv("FMS_STAGING_TOKEN", "ac6bc4df0fc050fa6cc31c066af8f02b")
FMS_PRODUCTION_TOKEN = os.getenv("FMS_PRODUCTION_TOKEN", "0b36ae1b3bebba027cf2ccd9049afa75")
FMS_TOKEN = FMS_PRODUCTION_TOKEN if FMS_ENVIRONMENT == "production" else FMS_STAGING_TOKEN

FMS_STAGING_REQUESTOR_ID = os.getenv("FMS_STAGING_REQUESTOR_ID", "1949")
FMS_PRODUCTION_REQUESTOR_ID = os.getenv("FMS_PRODUCTION_REQUESTOR_ID", "1949")  # TODO: Update when Alex creates dedicated user
FMS_REQUESTOR_ID = FMS_PRODUCTION_REQUESTOR_ID if FMS_ENVIRONMENT == "production" else FMS_STAGING_REQUESTOR_ID

# Import database service
from app.services.database import db_service


# Pydantic models
class BulkOperationRequest(BaseModel):
    assignment_ids: List[int]


class OperationResult(BaseModel):
    assignment_id: int
    success: bool
    error: str = None
    fms_request_id: int = None
    deleted_from_fms: bool = False
    created_in_fms: bool = False


# ============================================
# SINGLE OPERATIONS
# ============================================

@router.post("/create-vehicle-request/{assignment_id}")
async def create_fms_vehicle_request(assignment_id: int):
    """
    Create FMS vehicle request when user marks assignment as 'requested'

    Called when: User clicks "Request" button (green → magenta)

    Process:
    1. Fetch assignment details with vehicle_id (JOIN with vehicles table)
    2. Convert dates to FMS format (MM/DD/YY from YYYY-MM-DD)
    3. Build FMS API payload
    4. POST to FMS API
    5. Extract FMS request ID from response
    6. Store FMS request ID in database

    Args:
        assignment_id: Internal scheduler assignment ID

    Returns:
        Success status and FMS request ID
    """

    logger.info(f"Creating FMS vehicle request for assignment {assignment_id}")

    try:
        # 1. Fetch assignment with vehicle details (JOIN with vehicles table)
        query_result = await db_service.supabase.table('scheduled_assignments') \
            .select('*, vehicles!inner(vehicle_id, make, model)') \
            .eq('assignment_id', assignment_id) \
            .eq('status', 'requested') \
            .execute()

        if not query_result.data or len(query_result.data) == 0:
            raise HTTPException(
                status_code=404,
                detail="Assignment not found or not in 'requested' status"
            )

        assignment = query_result.data[0]
        vehicle_data = assignment.get('vehicles')

        if not vehicle_data:
            raise HTTPException(
                status_code=400,
                detail=f"Vehicle not found for VIN: {assignment.get('vin')}"
            )

        vehicle_id = vehicle_data.get('vehicle_id')

        if not vehicle_id:
            raise HTTPException(
                status_code=400,
                detail=f"vehicle_id not found for VIN: {assignment.get('vin')}. Ensure vehicle is in vehicles table."
            )

        # 2. Convert dates to FMS format (MM/DD/YY)
        from datetime import datetime

        start_date_obj = datetime.strptime(str(assignment['start_day']), '%Y-%m-%d')
        end_date_obj = datetime.strptime(str(assignment['end_day']), '%Y-%m-%d')

        fms_start_date = start_date_obj.strftime('%m/%d/%y')
        fms_end_date = end_date_obj.strftime('%m/%d/%y')

        # 3. Build FMS payload
        fms_payload = {
            "request": {
                # Required fields
                "requestor_id": int(FMS_REQUESTOR_ID),
                "start_date": fms_start_date,
                "end_date": fms_end_date,

                # Optional but helpful fields
                "activity_to": assignment.get('partner_name', ''),
                "reason": "Scheduled media partner loan",
                "loanee_id": assignment.get('person_id'),

                # Vehicle assignment
                "requests_vehicles": [
                    {
                        "vehicle_id": vehicle_id,
                        "notes": f"{vehicle_data.get('make')} {vehicle_data.get('model')} (VIN: {assignment.get('vin')})"
                    }
                ]
            }
        }

        logger.info(f"Sending FMS request to {FMS_BASE_URL}/api/v1/vehicle_requests")
        logger.debug(f"Payload: {fms_payload}")
        logger.debug(f"Dates converted: {assignment['start_day']} → {fms_start_date}, {assignment['end_day']} → {fms_end_date}")

        # 4. Send to FMS
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{FMS_BASE_URL}/api/v1/vehicle_requests",
                json=fms_payload,
                headers={
                    "Authorization": f"Bearer {FMS_TOKEN}",
                    "Content-Type": "application/json"
                }
            )

            if response.status_code not in [200, 201]:
                logger.error(f"FMS API error: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=500,
                    detail=f"FMS API error: {response.status_code} - {response.text}"
                )

            fms_response = response.json()
            logger.info(f"FMS response: {fms_response}")

            # 5. Extract FMS request ID (try multiple possible field names)
            fms_request_id = (
                fms_response.get('id') or
                fms_response.get('request_id') or
                fms_response.get('vehicle_request', {}).get('id')
            )

            if not fms_request_id:
                logger.warning(f"Could not extract FMS request ID from response: {fms_response}")
                # Continue anyway - we created the request successfully

            # 6. Store FMS request ID for future reference
            if fms_request_id:
                await db_service.supabase.table('scheduled_assignments').update({
                    'fms_request_id': fms_request_id
                }).eq('assignment_id', assignment_id).execute()

            return {
                "success": True,
                "fms_request_id": fms_request_id,
                "message": "Vehicle request created in FMS",
                "assignment_id": assignment_id
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating FMS request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error creating FMS request: {str(e)}"
        )


@router.delete("/delete-vehicle-request/{assignment_id}")
async def delete_fms_vehicle_request(assignment_id: int):
    """
    Delete FMS vehicle request when user deletes magenta assignment

    Called when: User deletes a 'requested' assignment

    Process:
    1. Get FMS request ID from database
    2. DELETE from FMS API
    3. Delete from scheduler database

    Args:
        assignment_id: Internal scheduler assignment ID

    Returns:
        Success status
    """

    logger.info(f"Deleting FMS vehicle request for assignment {assignment_id}")

    try:
        # 1. Get FMS request ID
        result = await db_service.supabase.table('scheduled_assignments') \
            .select('fms_request_id, status') \
            .eq('assignment_id', assignment_id) \
            .execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(
                status_code=404,
                detail="Assignment not found"
            )

        assignment = result.data[0]
        fms_request_id = assignment.get('fms_request_id')

        # 2. Delete from FMS (only if it was requested and has FMS ID)
        if assignment.get('status') == 'requested' and fms_request_id:
            logger.info(f"Deleting FMS request {fms_request_id}")

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    f"{FMS_BASE_URL}/api/v1/vehicle_requests/{fms_request_id}",
                    headers={"Authorization": f"Bearer {FMS_TOKEN}"}
                )

                if response.status_code not in [200, 204, 404]:
                    logger.error(f"FMS deletion failed: {response.status_code} - {response.text}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"FMS deletion failed: {response.status_code} - {response.text}"
                    )

                logger.info(f"Successfully deleted FMS request {fms_request_id}")
        else:
            logger.info(f"Assignment {assignment_id} not requested in FMS, skipping FMS deletion")

        # 3. Delete from scheduler database
        await db_service.supabase.table('scheduled_assignments') \
            .delete() \
            .eq('assignment_id', assignment_id) \
            .execute()

        return {
            "success": True,
            "message": "Request deleted from FMS and scheduler",
            "assignment_id": assignment_id,
            "deleted_from_fms": bool(fms_request_id and assignment.get('status') == 'requested')
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting FMS request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting FMS request: {str(e)}"
        )


# ============================================
# BULK OPERATIONS (Chain Builder)
# ============================================

@router.post("/bulk-create-vehicle-requests")
async def bulk_create_fms_vehicle_requests(request: BulkOperationRequest):
    """
    Bulk request multiple assignments (Green → Magenta)
    Loops through each and calls FMS CREATE API individually

    Used by: Chain Builder bulk request action

    Args:
        request: List of assignment IDs to request

    Returns:
        Summary of successes/failures with details per assignment
    """

    logger.info(f"Bulk creating {len(request.assignment_ids)} FMS vehicle requests")
    results = []

    for assignment_id in request.assignment_ids:
        try:
            # Check if assignment can be requested
            result = await db_service.supabase.table('scheduled_assignments') \
                .select('status, assignment_id') \
                .eq('assignment_id', assignment_id) \
                .execute()

            if not result.data or len(result.data) == 0:
                results.append(OperationResult(
                    assignment_id=assignment_id,
                    success=False,
                    error="Assignment not found"
                ))
                continue

            assignment = result.data[0]
            original_status = assignment['status']

            # Only request if status is 'planned' or 'manual'
            if assignment['status'] not in ['planned', 'manual']:
                results.append(OperationResult(
                    assignment_id=assignment_id,
                    success=False,
                    error=f"Cannot request assignment with status '{assignment['status']}'"
                ))
                continue

            # Update status to 'requested'
            await db_service.supabase.table('scheduled_assignments').update({
                'status': 'requested'
            }).eq('assignment_id', assignment_id).execute()

            # Create FMS request
            try:
                fms_result = await create_fms_vehicle_request(assignment_id)

                results.append(OperationResult(
                    assignment_id=assignment_id,
                    success=True,
                    created_in_fms=True,
                    fms_request_id=fms_result.get('fms_request_id')
                ))

            except HTTPException as he:
                # Rollback status change
                await db_service.supabase.table('scheduled_assignments').update({
                    'status': original_status
                }).eq('assignment_id', assignment_id).execute()

                results.append(OperationResult(
                    assignment_id=assignment_id,
                    success=False,
                    error=f"FMS API error: {he.detail}"
                ))

        except Exception as e:
            logger.error(f"Error in bulk create for assignment {assignment_id}: {str(e)}")
            results.append(OperationResult(
                assignment_id=assignment_id,
                success=False,
                error=str(e)
            ))

    # Summary
    success_count = sum(1 for r in results if r.success)
    failure_count = len(results) - success_count

    logger.info(f"Bulk create completed: {success_count} succeeded, {failure_count} failed")

    return {
        "total": len(request.assignment_ids),
        "succeeded": success_count,
        "failed": failure_count,
        "results": [r.dict() for r in results]
    }


@router.post("/bulk-unrequest-vehicle-requests")
async def bulk_unrequest_fms_vehicle_requests(request: BulkOperationRequest):
    """
    Bulk unrequest multiple assignments (Magenta → Green)
    Loops through each and calls FMS DELETE API individually
    Keeps assignments in scheduler

    Used by: Chain Builder bulk unrequest action

    Args:
        request: List of assignment IDs to unrequest

    Returns:
        Summary of successes/failures with details per assignment
    """

    logger.info(f"Bulk unrequesting {len(request.assignment_ids)} FMS vehicle requests")
    results = []

    for assignment_id in request.assignment_ids:
        try:
            # Check if assignment is 'requested'
            result = await db_service.supabase.table('scheduled_assignments') \
                .select('status, fms_request_id') \
                .eq('assignment_id', assignment_id) \
                .execute()

            if not result.data or len(result.data) == 0:
                results.append(OperationResult(
                    assignment_id=assignment_id,
                    success=False,
                    error="Assignment not found"
                ))
                continue

            assignment = result.data[0]

            # Only unrequest if status is 'requested'
            if assignment['status'] != 'requested':
                results.append(OperationResult(
                    assignment_id=assignment_id,
                    success=False,
                    error=f"Cannot unrequest assignment with status '{assignment['status']}'"
                ))
                continue

            # Delete from FMS first
            fms_request_id = assignment.get('fms_request_id')
            if fms_request_id:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.delete(
                        f"{FMS_BASE_URL}/api/v1/vehicle_requests/{fms_request_id}",
                        headers={"Authorization": f"Bearer {FMS_TOKEN}"}
                    )

                    if response.status_code not in [200, 204, 404]:
                        results.append(OperationResult(
                            assignment_id=assignment_id,
                            success=False,
                            error=f"FMS deletion failed: {response.status_code}"
                        ))
                        continue

            # Update status back to 'manual'
            await db_service.supabase.table('scheduled_assignments').update({
                'status': 'manual',
                'fms_request_id': None
            }).eq('assignment_id', assignment_id).execute()

            results.append(OperationResult(
                assignment_id=assignment_id,
                success=True,
                deleted_from_fms=True
            ))

        except Exception as e:
            logger.error(f"Error in bulk unrequest for assignment {assignment_id}: {str(e)}")
            results.append(OperationResult(
                assignment_id=assignment_id,
                success=False,
                error=str(e)
            ))

    # Summary
    success_count = sum(1 for r in results if r.success)
    failure_count = len(results) - success_count

    logger.info(f"Bulk unrequest completed: {success_count} succeeded, {failure_count} failed")

    return {
        "total": len(request.assignment_ids),
        "succeeded": success_count,
        "failed": failure_count,
        "results": [r.dict() for r in results]
    }


@router.post("/bulk-delete-vehicle-requests")
async def bulk_delete_fms_vehicle_requests(request: BulkOperationRequest):
    """
    Bulk delete multiple assignments
    Loops through each - calls FMS DELETE for 'requested' items
    Removes all from scheduler

    Used by: Chain Builder bulk delete action

    Args:
        request: List of assignment IDs to delete

    Returns:
        Summary of successes/failures with details per assignment
    """

    logger.info(f"Bulk deleting {len(request.assignment_ids)} assignments")
    results = []

    for assignment_id in request.assignment_ids:
        try:
            # Check assignment status
            result = await db_service.supabase.table('scheduled_assignments') \
                .select('status, fms_request_id') \
                .eq('assignment_id', assignment_id) \
                .execute()

            if not result.data or len(result.data) == 0:
                results.append(OperationResult(
                    assignment_id=assignment_id,
                    success=False,
                    error="Assignment not found"
                ))
                continue

            assignment = result.data[0]
            deleted_from_fms = False

            # If requested, delete from FMS
            if assignment['status'] == 'requested':
                fms_request_id = assignment.get('fms_request_id')

                if fms_request_id:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.delete(
                            f"{FMS_BASE_URL}/api/v1/vehicle_requests/{fms_request_id}",
                            headers={"Authorization": f"Bearer {FMS_TOKEN}"}
                        )

                        if response.status_code not in [200, 204, 404]:
                            results.append(OperationResult(
                                assignment_id=assignment_id,
                                success=False,
                                error=f"FMS deletion failed: {response.status_code}"
                            ))
                            continue

                        deleted_from_fms = True

            # Delete from scheduler database
            await db_service.supabase.table('scheduled_assignments') \
                .delete() \
                .eq('assignment_id', assignment_id) \
                .execute()

            results.append(OperationResult(
                assignment_id=assignment_id,
                success=True,
                deleted_from_fms=deleted_from_fms
            ))

        except Exception as e:
            logger.error(f"Error in bulk delete for assignment {assignment_id}: {str(e)}")
            results.append(OperationResult(
                assignment_id=assignment_id,
                success=False,
                error=str(e)
            ))

    # Summary
    success_count = sum(1 for r in results if r.success)
    failure_count = len(results) - success_count

    logger.info(f"Bulk delete completed: {success_count} succeeded, {failure_count} failed")

    return {
        "total": len(request.assignment_ids),
        "succeeded": success_count,
        "failed": failure_count,
        "results": [r.dict() for r in results]
    }


# ============================================
# ADMIN / TESTING ENDPOINTS
# ============================================

@router.get("/config")
async def get_fms_config():
    """
    Get current FMS configuration (for debugging)
    Does not expose sensitive tokens
    """
    return {
        "environment": FMS_ENVIRONMENT,
        "base_url": FMS_BASE_URL,
        "requestor_id": FMS_REQUESTOR_ID,
        "token_configured": bool(FMS_TOKEN),
        "token_length": len(FMS_TOKEN) if FMS_TOKEN else 0
    }
