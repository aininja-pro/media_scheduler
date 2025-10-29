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
from ..utils.media_costs import get_cost_for_assignment
from ..chain_builder.availability import (
    build_chain_availability_grid,
    get_available_vehicles_for_slot,
    check_slot_availability
)
from ..chain_builder.smart_scheduling import adjust_chain_for_existing_commitments
from ..solver.scoring import compute_candidate_scores

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chain-builder", tags=["chain-builder"])


@router.get("/suggest-chain")
async def suggest_chain(
    person_id: int = Query(..., description="Media partner ID"),
    office: str = Query(..., description="Office name"),
    start_date: str = Query(..., description="Chain start date (YYYY-MM-DD)"),
    num_vehicles: int = Query(4, description="Number of vehicles in chain", ge=1, le=10),
    days_per_loan: int = Query(7, description="Days per loan", ge=1, le=14),
    preferred_makes: Optional[str] = Query(None, description="Comma-separated list of makes to filter (e.g., 'Toyota,Honda')"),
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

        # Filter by preferred makes if specified
        if preferred_makes:
            preferred_makes_list = [m.strip() for m in preferred_makes.split(',')]
            logger.info(f"Filtering to preferred makes: {preferred_makes_list}")

            # Filter available vehicles to only preferred makes
            preferred_vehicles = vehicles_df[
                (vehicles_df['vin'].isin(available_vins)) &
                (vehicles_df['make'].isin(preferred_makes_list))
            ]
            available_vins = set(preferred_vehicles['vin'].unique())

            logger.info(f"After make filtering: {len(available_vins)} vehicles available")
        else:
            logger.info("No make filter applied - using all approved makes")

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

        # Load scheduled assignments for this partner
        logger.info(f"Loading scheduled assignments for partner {person_id}")
        scheduled_response = db.client.table('scheduled_assignments')\
            .select('*')\
            .eq('person_id', int(person_id))\
            .execute()

        scheduled_df = pd.DataFrame(scheduled_response.data) if scheduled_response.data else pd.DataFrame()
        logger.info(f"Found {len(scheduled_df)} scheduled assignments for partner {person_id}")

        # Use smart scheduling to find slots that work around existing commitments
        estimated_chain_end = (start_dt + timedelta(days=num_vehicles * days_per_loan * 2)).strftime('%Y-%m-%d')

        smart_slots = adjust_chain_for_existing_commitments(
            person_id=int(person_id),
            start_date=start_date,
            num_vehicles=num_vehicles,
            days_per_loan=days_per_loan,
            current_activity_df=activity_df,
            scheduled_assignments_df=scheduled_df
        )

        logger.info(f"Smart scheduling found {len(smart_slots)} available slots (threading through {len(scheduled_df)} existing commitments)")

        # Build availability grid covering the ACTUAL smart slot range (not estimated)
        if smart_slots and len(smart_slots) > 0:
            actual_start = smart_slots[0]['start_date']
            actual_end = smart_slots[-1]['end_date']

            # Calculate how many days we actually need
            start_dt_actual = datetime.strptime(actual_start, '%Y-%m-%d')
            end_dt_actual = datetime.strptime(actual_end, '%Y-%m-%d')
            actual_days_needed = (end_dt_actual - start_dt_actual).days + 1

            logger.info(f"Building availability grid from {actual_start} to {actual_end} ({actual_days_needed} days for {len(smart_slots)} slots)")

            availability_grid = build_chain_availability_grid(
                vehicles_df=vehicles_df,
                activity_df=activity_df,
                start_date=actual_start,
                num_slots=len(smart_slots),
                days_per_slot=days_per_loan,
                office=office,
                end_date=actual_end  # Pass explicit end date to cover weekend extensions
            )
        else:
            # No smart slots - return empty
            availability_grid = pd.DataFrame()

        # Use smart slots (which avoid existing commitments) instead of simple sequential dates
        slot_availability_counts = []

        for slot_index, smart_slot in enumerate(smart_slots):
            slot_start = smart_slot['start_date']
            slot_end = smart_slot['end_date']

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

        # Load additional data needed for scoring
        logger.info("Loading partners and approved makes for scoring")
        partners_response = db.client.table('media_partners').select('*').execute()
        partners_df = pd.DataFrame(partners_response.data) if partners_response.data else pd.DataFrame()

        # Load approved makes with pagination
        all_approved = []
        limit = 1000
        offset = 0
        while True:
            approved_response = db.client.table('approved_makes').select('person_id, make, rank').range(offset, offset + limit - 1).execute()
            if not approved_response.data:
                break
            all_approved.extend(approved_response.data)
            offset += limit
            if len(approved_response.data) < limit:
                break

        approved_makes_df = pd.DataFrame(all_approved) if all_approved else pd.DataFrame()

        # Ensure person_id types are consistent (int)
        if not approved_makes_df.empty and 'person_id' in approved_makes_df.columns:
            approved_makes_df['person_id'] = approved_makes_df['person_id'].astype(int)

        # Get partner info for response
        # Ensure partners_df person_id is int for comparison
        if not partners_df.empty and 'person_id' in partners_df.columns:
            partners_df['person_id'] = partners_df['person_id'].astype(int)

        partner_info_row = partners_df[partners_df['person_id'] == int(person_id)]
        partner_name = partner_info_row.iloc[0]['name'] if not partner_info_row.empty and 'name' in partner_info_row.columns else f"Partner {person_id}"

        # Greedy chain selection: Pick best vehicle for each smart slot
        suggested_chain = []
        used_vins = set()  # Track VINs already used in chain
        used_models = set()  # Track (make, model) combos already used - HARD RULE: no duplicates
        recent_makes = []  # Track last 2 makes to prevent 3+ in a row

        for slot_index, smart_slot in enumerate(smart_slots):
            slot_start = smart_slot['start_date']
            slot_end = smart_slot['end_date']

            # Get vehicles available for this slot (excluding already-used VINs)
            slot_vins = get_available_vehicles_for_slot(
                slot_index=slot_index,
                slot_start=slot_start,
                slot_end=slot_end,
                candidate_vins=available_vins,
                availability_df=availability_grid,
                exclude_vins=used_vins
            )

            if not slot_vins:
                logger.warning(f"No vehicles available for slot {slot_index + 1}")
                break

            # Build candidate DataFrame for scoring
            slot_vehicles = vehicles_df[vehicles_df['vin'].isin(slot_vins)].copy()

            # Ensure person_id type matches partners_df
            # Convert partners_df person_id to int if needed
            if not partners_df.empty and 'person_id' in partners_df.columns:
                partners_df['person_id'] = partners_df['person_id'].astype(int)

            slot_vehicles['person_id'] = int(person_id)
            slot_vehicles['market'] = office  # Use office as market

            # Rename 'office' column to avoid conflict with partners_df merge
            if 'office' in slot_vehicles.columns:
                slot_vehicles = slot_vehicles.rename(columns={'office': 'vehicle_office'})

            # Score candidates using optimizer logic
            scored_candidates = compute_candidate_scores(
                candidates_df=slot_vehicles,
                partner_rank_df=approved_makes_df,
                partners_df=partners_df,
                publication_df=pd.DataFrame()  # Empty publication data for now
            )

            if scored_candidates.empty:
                logger.warning(f"No scored candidates for slot {slot_index + 1}")
                break

            # HARD RULE: Filter out models already used in this chain
            # ALSO: Prevent 3+ same make in a row (e.g., Toyota, Toyota, Toyota)
            # Sort by score and pick the first one that doesn't violate rules
            scored_candidates = scored_candidates.sort_values('score', ascending=False)

            best_vehicle = None
            for _, candidate in scored_candidates.iterrows():
                make = candidate.get('make', 'Unknown')
                model = candidate.get('model', 'Unknown')
                model_key = (make, model)

                # Check if this model was already used in chain
                if model_key in used_models:
                    continue

                # Check if this would be 3rd consecutive same make
                # Example: recent_makes = ['Toyota', 'Toyota'], candidate make = 'Toyota' → SKIP
                if len(recent_makes) >= 2 and recent_makes[-1] == make and recent_makes[-2] == make:
                    continue  # Would be 3rd in a row

                # This vehicle passes all rules!
                best_vehicle = candidate
                break

            if best_vehicle is None:
                logger.warning(f"No unique models available for slot {slot_index + 1}")
                logger.warning(f"  Total candidates: {len(scored_candidates)}, Used models so far: {used_models}")
                logger.warning(f"  Slot dates: {slot_start} to {slot_end}")
                break

            vin = best_vehicle['vin']
            make = best_vehicle.get('make', 'Unknown')
            model = best_vehicle.get('model', 'Unknown')
            year = best_vehicle.get('year', '')
            score = int(best_vehicle['score'])
            tier = best_vehicle.get('rank', 'C')

            # Track this model as used
            model_key = (make, model)
            used_models.add(model_key)

            # Track make for consecutive rule (keep last 2)
            recent_makes.append(make)
            if len(recent_makes) > 2:
                recent_makes.pop(0)  # Keep only last 2

            # Check for conflicts with existing recommendations
            # TODO: Query scheduled_assignments for conflicts
            conflict = {
                "has_conflict": False,
                "conflict_type": None,
                "current_partner": None,
                "current_dates": None,
                "resolution": None
            }

            suggested_chain.append({
                "slot": slot_index + 1,
                "vin": vin,
                "make": make,
                "model": model,
                "year": str(year),
                "start_date": slot_start,
                "end_date": slot_end,
                "score": score,
                "tier": tier,
                "conflict": conflict
            })

            # Mark this VIN as used
            used_vins.add(vin)

        logger.info(f"Generated chain with {len(suggested_chain)} vehicles (threading through existing commitments)")

        return {
            "status": "success",
            "partner_info": {
                "person_id": person_id,
                "name": partner_name,
                "office": office
            },
            "chain_params": {
                "start_date": start_date,
                "num_vehicles": num_vehicles,
                "days_per_loan": days_per_loan,
                "total_span_days": (
                    datetime.strptime(suggested_chain[-1]["end_date"], '%Y-%m-%d') -
                    start_dt
                ).days + 1 if suggested_chain else 0
            },
            "chain": suggested_chain,
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
                "total_conflicts": sum(1 for v in suggested_chain if v['conflict']['has_conflict']),
                "conflicting_slots": [v['slot'] for v in suggested_chain if v['conflict']['has_conflict']]
            },
            "message": f"Chain generated successfully. {len(suggested_chain)}/{num_vehicles} vehicles selected using optimizer scoring. {len(excluded_vins)} VINs excluded from partner history."
        }

    except ValueError as e:
        logger.error(f"Invalid date format: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid date format: {start_date}. Use YYYY-MM-DD")

    except Exception as e:
        logger.error(f"Error suggesting chain: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/get-slot-options")
async def get_slot_options(
    person_id: int = Query(..., description="Media partner ID"),
    office: str = Query(..., description="Office name"),
    start_date: str = Query(..., description="Chain start date (YYYY-MM-DD)"),
    num_vehicles: int = Query(..., description="Number of vehicles in chain", ge=1, le=10),
    days_per_loan: int = Query(..., description="Days per loan", ge=1, le=14),
    slot_index: int = Query(..., description="Slot index (0-based)", ge=0),
    preferred_makes: Optional[str] = Query(None, description="Comma-separated list of makes to filter"),
    exclude_vins: Optional[str] = Query(None, description="Comma-separated list of VINs to exclude (already selected in other slots)"),
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    Get eligible vehicles for a specific slot in manual chain building.

    This endpoint is used for Manual Build mode, where the scheduler
    manually selects vehicles from dropdowns for each slot.

    Args:
        person_id: Target media partner ID
        office: Office to pull vehicles from
        start_date: Chain start date
        num_vehicles: Total number of vehicles in chain
        days_per_loan: Days per loan
        slot_index: Which slot to get options for (0-based)
        preferred_makes: Optional comma-separated makes filter
        exclude_vins: Optional VINs already selected in other slots

    Returns:
        Dictionary with:
        - slot: Slot info (index, start_date, end_date)
        - eligible_vehicles: List of vehicles with scores
        - total_eligible: Count of eligible vehicles
    """
    try:
        logger.info(f"Getting slot options for partner {person_id}, slot {slot_index}")

        # Validate slot_index
        if slot_index >= num_vehicles:
            raise HTTPException(
                status_code=400,
                detail=f"slot_index ({slot_index}) must be less than num_vehicles ({num_vehicles})"
            )

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
        logger.info(f"Exclusion: {len(available_vins)} vehicles not reviewed by partner")

        # Filter by preferred makes if specified
        if preferred_makes:
            preferred_makes_list = [m.strip() for m in preferred_makes.split(',')]
            logger.info(f"Filtering to preferred makes: {preferred_makes_list}")

            preferred_vehicles = vehicles_df[
                (vehicles_df['vin'].isin(available_vins)) &
                (vehicles_df['make'].isin(preferred_makes_list))
            ]
            available_vins = set(preferred_vehicles['vin'].unique())
            logger.info(f"After make filtering: {len(available_vins)} vehicles available")

        # Parse exclude_vins parameter
        excluded_vins_set = set()
        if exclude_vins:
            excluded_vins_set = set([v.strip() for v in exclude_vins.split(',')])
            logger.info(f"Excluding {len(excluded_vins_set)} VINs already selected in other slots")

        # Load current activity and scheduled assignments
        logger.info("Loading current activity")
        activity_response = db.client.table('current_activity').select('*').execute()
        activity_df = pd.DataFrame(activity_response.data) if activity_response.data else pd.DataFrame()

        # Fix column name if needed
        if not activity_df.empty and 'vehicle_vin' in activity_df.columns:
            activity_df['vin'] = activity_df['vehicle_vin']

        # Load scheduled assignments for this partner
        logger.info(f"Loading scheduled assignments for partner {person_id}")
        scheduled_response = db.client.table('scheduled_assignments')\
            .select('*')\
            .eq('person_id', int(person_id))\
            .execute()

        scheduled_df = pd.DataFrame(scheduled_response.data) if scheduled_response.data else pd.DataFrame()

        # Use smart scheduling to calculate all slot dates
        smart_slots = adjust_chain_for_existing_commitments(
            person_id=int(person_id),
            start_date=start_date,
            num_vehicles=num_vehicles,
            days_per_loan=days_per_loan,
            current_activity_df=activity_df,
            scheduled_assignments_df=scheduled_df
        )

        if not smart_slots or slot_index >= len(smart_slots):
            raise HTTPException(
                status_code=400,
                detail=f"Unable to find slot {slot_index} (only {len(smart_slots)} slots available)"
            )

        # Get the specific slot we're interested in
        target_slot = smart_slots[slot_index]
        slot_start = target_slot['start_date']
        slot_end = target_slot['end_date']

        logger.info(f"Slot {slot_index}: {slot_start} to {slot_end}")

        # Build availability grid covering the entire chain period
        if smart_slots and len(smart_slots) > 0:
            actual_start = smart_slots[0]['start_date']
            actual_end = smart_slots[-1]['end_date']

            logger.info(f"Building availability grid from {actual_start} to {actual_end}")

            availability_grid = build_chain_availability_grid(
                vehicles_df=vehicles_df,
                activity_df=activity_df,
                start_date=actual_start,
                num_slots=len(smart_slots),
                days_per_slot=days_per_loan,
                office=office,
                end_date=actual_end
            )
        else:
            availability_grid = pd.DataFrame()

        # Get available VINs for this specific slot
        slot_vins = get_available_vehicles_for_slot(
            slot_index=slot_index,
            slot_start=slot_start,
            slot_end=slot_end,
            candidate_vins=available_vins,
            availability_df=availability_grid,
            exclude_vins=excluded_vins_set
        )

        logger.info(f"Found {len(slot_vins)} vehicles available for slot {slot_index}")

        if not slot_vins:
            # Return empty result if no vehicles available
            return {
                "status": "success",
                "slot": {
                    "index": slot_index,
                    "start_date": slot_start,
                    "end_date": slot_end
                },
                "eligible_vehicles": [],
                "total_eligible": 0,
                "message": "No vehicles available for this slot"
            }

        # Load additional data for scoring
        logger.info("Loading partners and approved makes for scoring")
        partners_response = db.client.table('media_partners').select('*').execute()
        partners_df = pd.DataFrame(partners_response.data) if partners_response.data else pd.DataFrame()

        # Load approved makes with pagination
        all_approved = []
        limit = 1000
        offset = 0
        while True:
            approved_response = db.client.table('approved_makes').select('person_id, make, rank').range(offset, offset + limit - 1).execute()
            if not approved_response.data:
                break
            all_approved.extend(approved_response.data)
            offset += limit
            if len(approved_response.data) < limit:
                break

        approved_makes_df = pd.DataFrame(all_approved) if all_approved else pd.DataFrame()

        # Ensure person_id types are consistent (int)
        if not approved_makes_df.empty and 'person_id' in approved_makes_df.columns:
            approved_makes_df['person_id'] = approved_makes_df['person_id'].astype(int)

        if not partners_df.empty and 'person_id' in partners_df.columns:
            partners_df['person_id'] = partners_df['person_id'].astype(int)

        # Build candidate DataFrame for scoring
        slot_vehicles = vehicles_df[vehicles_df['vin'].isin(slot_vins)].copy()
        slot_vehicles['person_id'] = int(person_id)
        slot_vehicles['market'] = office

        # Rename 'office' column to avoid conflict with partners_df merge
        if 'office' in slot_vehicles.columns:
            slot_vehicles = slot_vehicles.rename(columns={'office': 'vehicle_office'})

        # Score candidates using optimizer logic
        scored_candidates = compute_candidate_scores(
            candidates_df=slot_vehicles,
            partner_rank_df=approved_makes_df,
            partners_df=partners_df,
            publication_df=pd.DataFrame()
        )

        if scored_candidates.empty:
            return {
                "status": "success",
                "slot": {
                    "index": slot_index,
                    "start_date": slot_start,
                    "end_date": slot_end
                },
                "eligible_vehicles": [],
                "total_eligible": 0,
                "message": "No scored vehicles available for this slot"
            }

        # Sort by score (best first)
        scored_candidates = scored_candidates.sort_values('score', ascending=False)

        # Limit to top 50 vehicles to avoid overwhelming the frontend
        max_vehicles = 50
        top_candidates = scored_candidates.head(max_vehicles)

        # Build response list
        # Note: Vehicles with conflicts are already filtered out by availability grid check above
        eligible_vehicles = []
        for _, vehicle in top_candidates.iterrows():
            vin = vehicle['vin']
            last_4_vin = vin[-4:] if len(vin) >= 4 else vin

            eligible_vehicles.append({
                "vin": vin,
                "make": vehicle.get('make', 'Unknown'),
                "model": vehicle.get('model', 'Unknown'),
                "trim": vehicle.get('trim', ''),
                "year": str(vehicle.get('year', '')),
                "score": int(vehicle['score']),
                "tier": vehicle.get('rank', 'C'),
                "last_4_vin": last_4_vin
            })

        logger.info(f"Returning {len(eligible_vehicles)} eligible vehicles for slot {slot_index}")

        return {
            "status": "success",
            "slot": {
                "index": slot_index,
                "start_date": slot_start,
                "end_date": slot_end
            },
            "eligible_vehicles": eligible_vehicles,
            "total_eligible": len(eligible_vehicles),
            "message": f"Found {len(eligible_vehicles)} eligible vehicles for slot {slot_index + 1}"
        }

    except ValueError as e:
        logger.error(f"Invalid date format: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid date format: {start_date}. Use YYYY-MM-DD")

    except Exception as e:
        logger.error(f"Error getting slot options: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save-chain")
async def save_chain(
    request: Dict[str, Any],
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    Save chain to scheduled_assignments table.

    Accepts chain data and inserts as 'proposed' status for Calendar view.

    Request body:
        {
            "person_id": int,
            "partner_name": str,
            "office": str,
            "status": str (optional, default='manual', can be 'manual' or 'requested'),
            "chain": [
                {
                    "vin": str,
                    "make": str,
                    "model": str,
                    "start_date": str,
                    "end_date": str,
                    "score": int
                }
            ]
        }

    Returns success status and assignment IDs
    """

    try:
        person_id = request.get('person_id')
        partner_name = request.get('partner_name')
        office = request.get('office')
        status = request.get('status', 'manual')  # Default to 'manual', can be 'requested'
        chain_vehicles = request.get('chain', [])

        if not person_id or not office or not chain_vehicles:
            raise HTTPException(status_code=400, detail="Missing required fields: person_id, office, chain")

        logger.info(f"Saving chain for partner {person_id}: {len(chain_vehicles)} vehicles")

        # Insert each vehicle as a scheduled assignment
        assignments_to_insert = []

        for vehicle in chain_vehicles:
            # Calculate week_start (Monday of the week this assignment starts)
            start_date = datetime.strptime(vehicle['start_date'], '%Y-%m-%d')
            monday = start_date - timedelta(days=start_date.weekday())
            week_start = monday.strftime('%Y-%m-%d')

            assignments_to_insert.append({
                'vin': vehicle['vin'],
                'person_id': int(person_id),
                'start_day': vehicle['start_date'],
                'end_day': vehicle['end_date'],
                'make': vehicle.get('make', ''),
                'model': vehicle.get('model', ''),
                'office': office,
                'partner_name': partner_name,
                'score': vehicle.get('score', 0),
                'week_start': week_start,  # Monday of the week
                'status': status  # 'manual' (green) or 'requested' (magenta)
            })

        # Insert all assignments
        if assignments_to_insert:
            result = db.client.table('scheduled_assignments').insert(assignments_to_insert).execute()

            return {
                'success': True,
                'message': f'Chain saved successfully! {len(assignments_to_insert)} vehicles added to calendar.',
                'assignments_saved': len(assignments_to_insert),
                'assignment_ids': [a.get('assignment_id') for a in result.data] if result.data else []
            }
        else:
            return {
                'success': False,
                'message': 'No vehicles to save'
            }

    except Exception as e:
        logger.error(f"Error saving chain: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calculate-chain-budget")
async def calculate_chain_budget(
    request: Dict[str, Any],
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    Calculate budget impact for a proposed chain in the EXACT same format as Optimizer.

    Request body:
        {
            "office": str,
            "chain": [{"person_id": int, "make": str, "start_date": str}]
        }

    Returns budget_summary in same format as Optimizer for consistent UI.
    """
    try:
        office = request.get('office')
        chain = request.get('chain', [])

        # Load budgets for this office
        budgets_response = db.client.table('budgets').select('*').eq('office', office).execute()
        budgets_df = pd.DataFrame(budgets_response.data) if budgets_response.data else pd.DataFrame()

        # Determine quarter from first vehicle (or use current quarter)
        if chain and len(chain) > 0:
            start_dt = datetime.strptime(chain[0]['start_date'], '%Y-%m-%d')
            current_year = start_dt.year
            current_quarter = f'Q{((start_dt.month - 1) // 3) + 1}'
        else:
            now = datetime.now()
            current_year = now.year
            current_quarter = f'Q{((now.month - 1) // 3) + 1}'

        # Get quarter budgets
        quarter_budgets = budgets_df[
            (budgets_df['year'] == current_year) &
            (budgets_df['quarter'] == current_quarter)
        ]

        # Calculate chain costs by make
        planned_by_make = {}
        for assignment in chain:
            person_id = assignment.get('person_id')
            make = assignment.get('make')
            if not person_id or not make:
                continue

            cost_info = get_cost_for_assignment(person_id, make)
            make_upper = make.upper()
            planned_by_make[make_upper] = planned_by_make.get(make_upper, 0) + cost_info['cost']

        # Build budget_summary in same format as Optimizer
        budget_fleets = {}

        # First, add all makes from quarter_budgets table
        for _, row in quarter_budgets.iterrows():
            fleet = row['fleet']
            current_used = float(row['amount_used']) if pd.notna(row['amount_used']) else 0
            budget_amount = float(row['budget_amount']) if pd.notna(row['budget_amount']) else 0
            planned_spend = planned_by_make.get(fleet, 0)

            budget_fleets[fleet] = {
                'current': int(current_used),
                'planned': planned_spend,
                'projected': current_used + planned_spend,
                'budget': int(budget_amount)
            }

        # Second, add any makes from the chain that aren't in budgets table
        for make, cost in planned_by_make.items():
            if make not in budget_fleets:
                budget_fleets[make] = {
                    'current': 0,
                    'planned': cost,
                    'projected': cost,
                    'budget': 0  # No budget entry for this make
                }

        # Calculate totals
        total_current = sum(f['current'] for f in budget_fleets.values())
        total_planned = sum(f['planned'] for f in budget_fleets.values())
        total_budget = sum(f['budget'] for f in budget_fleets.values())

        budget_summary = {
            'fleets': budget_fleets,
            'total': {
                'current': total_current,
                'planned': total_planned,
                'projected': total_current + total_planned,
                'budget': total_budget
            } if budget_fleets else None
        }

        return budget_summary

    except Exception as e:
        logger.error(f"Error calculating chain budget: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search-vehicles")
async def search_vehicles(
    office: str = Query(..., description="Office name"),
    search_term: str = Query("", description="Search by VIN, make, or model"),
    limit: int = Query(50, description="Maximum number of results", ge=1, le=100),
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    Search vehicles by VIN, make, or model within an office.

    Returns list of vehicles for autocomplete dropdown in vehicle chain mode.

    Args:
        office: Office to filter vehicles by
        search_term: Partial VIN, make, or model to search
        limit: Maximum number of results to return (default 50)

    Returns:
        Dict with 'vehicles' list containing matching vehicles
    """
    try:
        logger.info(f"Searching vehicles in {office} with term: '{search_term}'")

        # Load vehicles from database for this office
        vehicles_df = db.get_vehicles_by_office(office)

        if vehicles_df.empty:
            logger.warning(f"No vehicles found for office: {office}")
            return {"vehicles": []}

        # Filter by search term if provided
        if search_term:
            search_lower = search_term.lower()
            mask = (
                vehicles_df['vin'].str.lower().str.contains(search_lower, na=False) |
                vehicles_df['make'].str.lower().str.contains(search_lower, na=False) |
                vehicles_df['model'].str.lower().str.contains(search_lower, na=False)
            )
            filtered_df = vehicles_df[mask]
        else:
            filtered_df = vehicles_df

        # Sort by make, then model, then year (descending)
        filtered_df = filtered_df.sort_values(
            by=['make', 'model', 'year'],
            ascending=[True, True, False]
        )

        # Limit results
        result_df = filtered_df.head(limit)

        # Convert to list of dicts
        vehicles_list = []
        for _, row in result_df.iterrows():
            vehicles_list.append({
                'vin': row['vin'],
                'make': row['make'],
                'model': row['model'],
                'year': str(row['year']) if pd.notna(row['year']) else '',
                'trim': row.get('trim', '') if pd.notna(row.get('trim', '')) else '',
                'office': row['office'],
                'in_service_date': row['in_service_date'].isoformat() if pd.notna(row.get('in_service_date')) else None,
                'tier': row.get('tier', '') if pd.notna(row.get('tier', '')) else ''
            })

        logger.info(f"Found {len(vehicles_list)} vehicles matching '{search_term}' in {office}")

        return {
            "vehicles": vehicles_list,
            "total": len(vehicles_list),
            "search_term": search_term,
            "office": office
        }

    except Exception as e:
        logger.error(f"Error searching vehicles: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to search vehicles: {str(e)}")
