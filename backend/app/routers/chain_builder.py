"""
Chain Builder API - Build sequential vehicle loan chains for media partners

This router provides endpoints for:
- Suggesting optimal vehicle chains for a single partner
- Validating chain feasibility
- Saving chains as proposed assignments
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timedelta
import pandas as pd

from ..services.database import get_database, DatabaseService
from ..chain_builder.exclusions import get_vehicles_not_reviewed, get_model_cooldown_status
from ..chain_builder.availability import (
    build_chain_availability_grid,
    get_available_vehicles_for_slot,
    check_slot_availability
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chain-builder", tags=["chain-builder"])


@router.get("/suggest-chain")
async def suggest_chain(
    person_id: str = Query(..., description="Media partner ID"),
    office: str = Query(..., description="Office name"),
    start_date: str = Query(..., description="Chain start date (YYYY-MM-DD)"),
    num_vehicles: int = Query(4, description="Number of vehicles in chain", ge=1, le=10),
    days_per_loan: int = Query(7, description="Days per loan", ge=1, le=14),
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    Suggest optimal vehicle chain for a media partner.

    Returns sequentially available vehicles the partner hasn't reviewed,
    scored and ranked by quality/fit.

    Args:
        person_id: Target media partner ID
        office: Office to pull vehicles from
        start_date: When chain should start (must be weekday)
        num_vehicles: How many vehicles in the chain (default 4)
        days_per_loan: Loan duration in days (default 7)

    Returns:
        Dictionary with:
        - chain: List of suggested vehicles with dates
        - partner_info: Partner details
        - constraints: Applied business rules
        - conflicts: Any conflicts with existing recommendations
    """

    try:
        logger.info(f"Suggesting chain for partner {person_id}, office {office}, starting {start_date}")

        # Validate start_date is a weekday
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        if start_dt.weekday() >= 5:  # Saturday = 5, Sunday = 6
            raise HTTPException(
                status_code=400,
                detail=f"Start date must be a weekday (Mon-Fri). {start_date} is a {start_dt.strftime('%A')}"
            )

        # Load data from database
        logger.info(f"Loading vehicles for office {office}")
        vehicles_response = db.client.table('vehicles').select('*').eq('office', office).execute()
        vehicles_df = pd.DataFrame(vehicles_response.data) if vehicles_response.data else pd.DataFrame()

        if vehicles_df.empty:
            raise HTTPException(status_code=404, detail=f"No vehicles found for office {office}")

        # Load loan history with pagination
        logger.info("Loading loan history")
        all_loan_history = []
        limit = 1000
        offset = 0
        while True:
            loan_response = db.client.table('loan_history').select('*').range(offset, offset + limit - 1).execute()
            if not loan_response.data:
                break
            all_loan_history.extend(loan_response.data)
            offset += limit
            if len(loan_response.data) < limit:
                break

        loan_history_df = pd.DataFrame(all_loan_history) if all_loan_history else pd.DataFrame()

        # Get vehicles partner has NOT reviewed
        exclusion_result = get_vehicles_not_reviewed(
            person_id=person_id,
            office=office,
            loan_history_df=loan_history_df,
            vehicles_df=vehicles_df,
            months_back=12
        )

        available_vins = exclusion_result['available_vins']
        excluded_vins = exclusion_result['excluded_vins']

        logger.info(f"Exclusion: {len(available_vins)} available, {len(excluded_vins)} excluded")

        # Get model cooldown status
        cooldown_status = get_model_cooldown_status(
            person_id=person_id,
            loan_history_df=loan_history_df,
            vehicles_df=vehicles_df,
            cooldown_days=30
        )

        # Load current activity
        logger.info("Loading current activity")
        activity_response = db.client.table('current_activity').select('*').execute()
        activity_df = pd.DataFrame(activity_response.data) if activity_response.data else pd.DataFrame()

        # Fix column name if needed
        if not activity_df.empty and 'vehicle_vin' in activity_df.columns:
            activity_df['vin'] = activity_df['vehicle_vin']

        # Build availability grid for entire chain period
        logger.info(f"Building availability grid for {num_vehicles} slots")
        availability_grid = build_chain_availability_grid(
            vehicles_df=vehicles_df,
            activity_df=activity_df,
            start_date=start_date,
            num_slots=num_vehicles,
            days_per_slot=days_per_loan,
            office=office
        )

        # For each slot, determine which vehicles are available
        slot_availability_counts = []
        current_date = start_dt

        for slot_index in range(num_vehicles):
            slot_start = current_date.strftime('%Y-%m-%d')
            slot_end = (current_date + timedelta(days=days_per_loan - 1)).strftime('%Y-%m-%d')

            # Get vehicles available for this slot (from the filtered available_vins)
            slot_vins = get_available_vehicles_for_slot(
                slot_index=slot_index,
                slot_start=slot_start,
                slot_end=slot_end,
                candidate_vins=available_vins,
                availability_df=availability_grid,
                exclude_vins=set()  # In Commit 4, we'll exclude already-used VINs
            )

            slot_availability_counts.append({
                'slot': slot_index + 1,
                'start_date': slot_start,
                'end_date': slot_end,
                'available_count': len(slot_vins)
            })

            # Move to next slot (skip weekends)
            current_date = current_date + timedelta(days=days_per_loan)
            while current_date.weekday() >= 5:  # Skip weekends
                current_date = current_date + timedelta(days=1)

        # TODO: In Commit 4, add scoring and greedy selection
        # For now, use mock chain with real availability data

        mock_chain = []
        current_date = start_dt

        for i in range(num_vehicles):
            # Calculate slot dates
            slot_start = current_date.strftime('%Y-%m-%d')
            slot_end = (current_date + timedelta(days=days_per_loan - 1)).strftime('%Y-%m-%d')

            # Mock vehicle
            mock_chain.append({
                "slot": i + 1,
                "vin": f"MOCK{i+1}234567890ABC",
                "make": ["Toyota", "Honda", "Ford", "Chevrolet"][i % 4],
                "model": ["Camry", "Accord", "F-150", "Silverado"][i % 4],
                "year": "2024",
                "start_date": slot_start,
                "end_date": slot_end,
                "score": 950 - (i * 30),  # Decreasing score
                "tier": ["A+", "A", "A", "B"][i % 4],
                "conflict": {
                    "has_conflict": i == 0,  # Mock: first vehicle has conflict
                    "conflict_type": "optimizer_recommendation" if i == 0 else None,
                    "current_partner": "John Doe" if i == 0 else None,
                    "current_dates": "Jan 8-14" if i == 0 else None,
                    "resolution": "Will be removed if chain accepted" if i == 0 else None
                }
            })

            # Next slot: add days_per_loan, skip weekends
            current_date = current_date + timedelta(days=days_per_loan)
            while current_date.weekday() >= 5:  # Skip weekends
                current_date = current_date + timedelta(days=1)

        return {
            "status": "success",
            "partner_info": {
                "person_id": person_id,
                "name": f"Partner {person_id}",  # TODO: Load from DB
                "office": office
            },
            "chain_params": {
                "start_date": start_date,
                "num_vehicles": num_vehicles,
                "days_per_loan": days_per_loan,
                "total_span_days": (
                    datetime.strptime(mock_chain[-1]["end_date"], '%Y-%m-%d') -
                    start_dt
                ).days + 1 if mock_chain else 0
            },
            "chain": mock_chain,
            "constraints_applied": {
                "excluded_vins": len(excluded_vins),
                "cooldown_filtered": sum(1 for status in cooldown_status.values() if not status['cooldown_ok']),
                "tier_cap_warnings": 0,  # TODO: Count in Commit 4
                "availability_checked": True
            },
            "exclusion_details": exclusion_result.get('exclusion_details', []),
            "cooldown_status": {
                f"{make}_{model}": status
                for (make, model), status in cooldown_status.items()
            },
            "slot_availability": slot_availability_counts,
            "conflicts": {
                "total_conflicts": 1,  # Mock: one conflict
                "conflicting_slots": [1]
            },
            "message": f"Real availability checking complete. {len(available_vins)} vehicles after exclusion. Slot availability varies per period. Scoring/selection coming in commit 4."
        }

    except ValueError as e:
        logger.error(f"Invalid date format: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid date format: {start_date}. Use YYYY-MM-DD")

    except Exception as e:
        logger.error(f"Error suggesting chain: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validate-chain")
async def validate_chain(
    chain_vins: str = Query(..., description="Comma-separated VINs"),
    start_date: str = Query(..., description="Chain start date"),
    days_per_loan: int = Query(7, description="Days per loan"),
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    Validate a manually-edited chain for feasibility.

    Checks:
    - Sequential availability
    - Cooldown compliance
    - Tier cap limits
    - Conflicts with existing recommendations

    Returns validation status and any issues found.
    """

    try:
        vins = chain_vins.split(',')

        # TODO: Implement validation logic in later commits

        return {
            "status": "valid",
            "chain_vins": vins,
            "issues": [],
            "warnings": [],
            "message": "Validation logic coming in future commits"
        }

    except Exception as e:
        logger.error(f"Error validating chain: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
