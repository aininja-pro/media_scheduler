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

from ..services.database import get_database, DatabaseService

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

        # TODO: Load real data in Commit 2-4
        # For now, return mock structure to test endpoint

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
                "excluded_vins": 0,  # TODO: Count in Commit 2
                "cooldown_filtered": 0,  # TODO: Count in Commit 3
                "tier_cap_warnings": 0,  # TODO: Count in Commit 4
                "availability_checked": True
            },
            "conflicts": {
                "total_conflicts": 1,  # Mock: one conflict
                "conflicting_slots": [1]
            },
            "message": f"Mock chain generated. Real logic coming in commits 2-4."
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
