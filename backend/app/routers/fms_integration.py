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

from fastapi import APIRouter, HTTPException, Header
from typing import List, Optional
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
from app.services.conflicts import find_vehicle_conflicts, log_fms_submission


def resolve_fms_requestor(authorization: Optional[str]) -> tuple:
    """Resolve the FMS requestor_id from the signed-in user's profile.

    Every FMS submission must be attributed to the real person who made it
    (client requirement — a shared/fallback ID shows up as the wrong person
    in FMS). The caller's Supabase token is verified and their
    user_metadata.fms_user_id is used. Raises 401/403 with an actionable
    message instead of falling back to a shared ID.

    Returns (fms_user_id, email) — the email feeds the submission audit log.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="Sign in with your personal account to send requests to FMS. "
                   "The shared login cannot submit FMS requests."
        )

    token = authorization.split(" ", 1)[1].strip()
    try:
        result = db_service.client.auth.get_user(token)
    except Exception as e:
        logger.warning(f"FMS requestor token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired session. Please sign in again.")

    user = getattr(result, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session. Please sign in again.")

    metadata = user.user_metadata or {}
    fms_user_id = str(metadata.get("fms_user_id") or "").strip()

    if not fms_user_id or not fms_user_id.isdigit():
        raise HTTPException(
            status_code=403,
            detail=f"No FMS User ID is set on your profile ({user.email}). "
                   "Ask an admin to add it in User Management before sending requests to FMS."
        )

    return int(fms_user_id), user.email


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
async def create_fms_vehicle_request(assignment_id: int,
                                     authorization: Optional[str] = Header(None)):
    """
    Create FMS vehicle request when user marks assignment as 'requested'

    Called when: User clicks "Request" button (green → magenta)

    Process:
    1. Fetch assignment details from scheduled_assignments
    2. Fetch vehicle details from vehicles table (get vehicle_id)
    3. Convert dates to FMS format (MM/DD/YY from YYYY-MM-DD)
    4. Build FMS API payload
    5. POST to FMS API
    6. Extract FMS request ID from response
    7. Store FMS request ID in database

    Args:
        assignment_id: Internal scheduler assignment ID

    Returns:
        Success status and FMS request ID
    """

    logger.info(f"Creating FMS vehicle request for assignment {assignment_id}")

    # Resolve who is making this request BEFORE touching anything else —
    # submissions without a real FMS user are rejected outright.
    requestor_id, requestor_email = resolve_fms_requestor(authorization)

    try:
        # 1. Fetch assignment details
        assignment_result = db_service.client.table('scheduled_assignments') \
            .select('*') \
            .eq('assignment_id', assignment_id) \
            .eq('status', 'requested') \
            .execute()

        if not assignment_result.data or len(assignment_result.data) == 0:
            raise HTTPException(
                status_code=404,
                detail="Assignment not found or not in 'requested' status"
            )

        assignment = assignment_result.data[0]
        vin = assignment.get('vin')

        # 1b. Re-check for booking conflicts RIGHT NOW. FMS activity changes
        # daily, so a slot that was free when this chain was planned may have
        # been taken since. Better to block here with a clear reason than
        # have FMS reject it cryptically.
        conflicts = find_vehicle_conflicts(
            db_service.client,
            vin=vin,
            start_day=str(assignment['start_day']),
            end_day=str(assignment['end_day']),
            exclude_assignment_id=assignment_id,
        )
        if conflicts:
            conflict_text = "; ".join(conflicts)
            logger.warning(f"Blocking FMS request for assignment {assignment_id}: conflicts with {conflict_text}")
            log_fms_submission(
                db_service.client,
                action='create', success=False, assignment=assignment,
                requestor_fms_id=requestor_id, requestor_email=requestor_email,
                error_detail=f"Blocked: vehicle already booked — {conflict_text}",
            )
            raise HTTPException(
                status_code=409,
                detail=f"This vehicle is already booked during "
                       f"{assignment['start_day']} to {assignment['end_day']}: {conflict_text}. "
                       "Adjust the dates or resolve the existing booking, then try again."
            )

        # 2. Fetch vehicle details to get vehicle_id
        vehicle_result = db_service.client.table('vehicles') \
            .select('vehicle_id, make, model') \
            .eq('vin', vin) \
            .execute()

        if not vehicle_result.data or len(vehicle_result.data) == 0:
            raise HTTPException(
                status_code=400,
                detail=f"Vehicle not found for VIN: {vin}"
            )

        vehicle_data = vehicle_result.data[0]
        vehicle_id = vehicle_data.get('vehicle_id')

        if not vehicle_id:
            raise HTTPException(
                status_code=400,
                detail=f"vehicle_id not found for VIN: {vin}. Ensure vehicle is in vehicles table."
            )

        # 2b. Fetch partner details for FMS payload (affiliation & subcategory)
        partner_result = db_service.client.table('media_partners') \
            .select('affiliation, activity_type_subcategory_id') \
            .eq('person_id', assignment.get('person_id')) \
            .eq('office', assignment.get('office')) \
            .execute()

        partner_data = partner_result.data[0] if partner_result.data else {}

        # 3. Convert dates to FMS format (MM/DD/YY)
        from datetime import datetime

        start_date_obj = datetime.strptime(str(assignment['start_day']), '%Y-%m-%d')
        end_date_obj = datetime.strptime(str(assignment['end_day']), '%Y-%m-%d')

        fms_start_date = start_date_obj.strftime('%m/%d/%y')
        fms_end_date = end_date_obj.strftime('%m/%d/%y')

        # 4. Build FMS payload
        fms_payload = {
            "request": {
                # Required fields
                "requestor_id": requestor_id,  # the signed-in user's FMS User ID
                "start_date": fms_start_date,
                "end_date": fms_end_date,
                "activity_type_id": 1,  # NEW: Always 1 for media partner loans

                # Optional but helpful fields
                "activity_to": assignment.get('partner_name', ''),
                "reason": partner_data.get('affiliation') or "Scheduled media partner loan",  # NEW: Use partner's affiliation if available
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

        # Add optional activity_type_subcategory_id if partner has one
        if partner_data.get('activity_type_subcategory_id'):
            fms_payload["request"]["activity_type_subcategory_id"] = partner_data.get('activity_type_subcategory_id')

        logger.info(f"Sending FMS request to {FMS_BASE_URL}/api/v1/vehicle_requests")
        logger.info(f"  Vehicle: {vehicle_data.get('make')} {vehicle_data.get('model')} (VIN: {vin}, vehicle_id: {vehicle_id})")
        logger.info(f"  Partner: {assignment.get('partner_name')} (person_id: {assignment.get('person_id')})")
        logger.info(f"  Dates: {fms_start_date} to {fms_end_date}")
        logger.info(f"  Requestor: {requestor_id}")
        logger.debug(f"Full payload: {fms_payload}")

        # 5. Send to FMS
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{FMS_BASE_URL}/api/v1/vehicle_requests",
                json=fms_payload,
                headers={
                    "Authorization": f"Token {FMS_TOKEN}",  # FMS uses "Token" not "Bearer"
                    "Content-Type": "application/json"
                }
            )

            if response.status_code not in [200, 201]:
                logger.error(f"FMS API error: {response.status_code} - {response.text}")
                log_fms_submission(
                    db_service.client,
                    action='create', success=False, assignment=assignment,
                    requestor_fms_id=requestor_id, requestor_email=requestor_email,
                    error_detail=f"FMS API error {response.status_code}: {response.text[:500]}",
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"FMS API error: {response.status_code} - {response.text}"
                )

            fms_response = response.json()
            logger.info(f"FMS response: {fms_response}")

            # 6. Extract FMS request ID
            # FMS returns: {"request": {"id": 4371, ...}}
            fms_request_id = fms_response.get('request', {}).get('id')

            if not fms_request_id:
                logger.warning(f"Could not extract FMS request ID from response: {fms_response}")
                # Continue anyway - we created the request successfully

            # 7. Store FMS request ID for future reference
            if fms_request_id:
                db_service.client.table('scheduled_assignments').update({
                    'fms_request_id': fms_request_id
                }).eq('assignment_id', assignment_id).execute()

            log_fms_submission(
                db_service.client,
                action='create', success=True, assignment=assignment,
                requestor_fms_id=requestor_id, requestor_email=requestor_email,
                fms_request_id=fms_request_id,
            )

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
        log_fms_submission(
            db_service.client,
            action='create', success=False, assignment_id=assignment_id,
            requestor_fms_id=requestor_id, requestor_email=requestor_email,
            error_detail=f"Unexpected error: {str(e)[:500]}",
        )
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
        result = db_service.client.table('scheduled_assignments') \
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
                    headers={"Authorization": f"Token {FMS_TOKEN}"}
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
        db_service.client.table('scheduled_assignments') \
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
async def bulk_create_fms_vehicle_requests(request: BulkOperationRequest,
                                           authorization: Optional[str] = Header(None)):
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

    # Fail the whole batch up front if the caller can't be attributed —
    # better than flipping statuses and rolling them all back one by one.
    resolve_fms_requestor(authorization)

    results = []

    for assignment_id in request.assignment_ids:
        try:
            # Check if assignment can be requested
            result = db_service.client.table('scheduled_assignments') \
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

            # Only request if status is 'planned', 'manual', or already 'requested' (but not sent to FMS yet)
            if assignment['status'] not in ['planned', 'manual', 'requested']:
                results.append(OperationResult(
                    assignment_id=assignment_id,
                    success=False,
                    error=f"Cannot request assignment with status '{assignment['status']}'"
                ))
                continue

            # Update status to 'requested' if not already
            if assignment['status'] != 'requested':
                db_service.client.table('scheduled_assignments').update({
                    'status': 'requested'
                }).eq('assignment_id', assignment_id).execute()

            # Create FMS request
            try:
                fms_result = await create_fms_vehicle_request(assignment_id, authorization)

                results.append(OperationResult(
                    assignment_id=assignment_id,
                    success=True,
                    created_in_fms=True,
                    fms_request_id=fms_result.get('fms_request_id')
                ))

            except HTTPException as he:
                # Rollback status change
                db_service.client.table('scheduled_assignments').update({
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
            result = db_service.client.table('scheduled_assignments') \
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
                        headers={"Authorization": f"Token {FMS_TOKEN}"}
                    )

                    if response.status_code not in [200, 204, 404]:
                        results.append(OperationResult(
                            assignment_id=assignment_id,
                            success=False,
                            error=f"FMS deletion failed: {response.status_code}"
                        ))
                        continue

            # Update status back to 'manual'
            db_service.client.table('scheduled_assignments').update({
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
            result = db_service.client.table('scheduled_assignments') \
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
                            headers={"Authorization": f"Token {FMS_TOKEN}"}
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
            db_service.client.table('scheduled_assignments') \
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
        "requestor_id": "per-user (fms_user_id on each profile)",
        "token_configured": bool(FMS_TOKEN),
        "token_length": len(FMS_TOKEN) if FMS_TOKEN else 0
    }
