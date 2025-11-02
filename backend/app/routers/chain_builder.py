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
import json

from ..services.database import get_database, DatabaseService
from ..chain_builder.exclusions import get_vehicles_not_reviewed, get_model_cooldown_status
from ..chain_builder.vehicle_exclusions import get_partners_not_reviewed
from ..utils.media_costs import get_cost_for_assignment
from ..chain_builder.availability import (
    build_chain_availability_grid,
    get_available_vehicles_for_slot,
    check_slot_availability,
    build_partner_availability_grid,
    check_partner_slot_availability
)
from ..chain_builder.smart_scheduling import adjust_chain_for_existing_commitments
from ..chain_builder.geography import (
    score_partners_base,
    calculate_distance_matrix
)
from ..solver.scoring import compute_candidate_scores
from ..solver.vehicle_chain_solver import (
    solve_vehicle_chain,
    Partner
)
from ..solver.partner_chain_solver import (
    solve_partner_chain,
    ModelPreference
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chain-builder", tags=["chain-builder"])


@router.get("/suggest-chain")
async def suggest_chain(
    person_id: int = Query(..., description="Media partner ID"),
    office: str = Query(..., description="Office name"),
    start_date: str = Query(..., description="Chain start date (YYYY-MM-DD)"),
    num_vehicles: int = Query(4, description="Number of vehicles in chain", ge=1, le=10),
    days_per_loan: int = Query(7, description="Days per loan", ge=1, le=14),
    preferred_makes: Optional[str] = Query(None, description="DEPRECATED: Use model_preferences instead"),
    model_preferences: Optional[str] = Query(None, description='JSON array of model preferences: [{"make":"Honda","model":"Accord"}]'),
    preference_mode: str = Query("prioritize", description="Preference mode: prioritize | strict | ignore"),
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    Suggest optimal vehicle chain for a media partner using OR-Tools CP-SAT.

    NEW: Uses global optimization instead of greedy slot-by-slot selection.
    Supports model preferences with prioritize/strict/ignore modes.

    Returns sequentially available vehicles the partner hasn't reviewed,
    scored and ranked by quality/fit.

    Args:
        person_id: Target media partner ID
        office: Office to pull vehicles from
        start_date: When chain should start (must be weekday)
        num_vehicles: How many vehicles in the chain (default 4)
        days_per_loan: Loan duration in days (default 7)
        model_preferences: JSON string with preferred models (optional)
        preference_mode: How to handle preferences (default "prioritize")

    Returns:
        Dictionary with:
        - chain: List of suggested vehicles with dates
        - partner_info: Partner details
        - optimization_stats: OR-Tools solver statistics
        - diagnostics: Explanation of decisions
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

        # Parse model preferences if provided
        model_prefs = []
        if model_preferences and preference_mode != "ignore":
            try:
                prefs_data = json.loads(model_preferences)
                model_prefs = [ModelPreference(**p) for p in prefs_data]
                logger.info(f"Parsed {len(model_prefs)} model preferences (mode: {preference_mode})")
            except Exception as e:
                logger.error(f"Failed to parse model preferences: {e}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid model_preferences JSON: {e}"
                )

        # Build candidate vehicles DataFrame for all slots
        # (OR-Tools needs to see all candidates at once, not slot-by-slot)
        all_candidate_vins = set()
        for slot_idx, smart_slot in enumerate(smart_slots):
            slot_vins = get_available_vehicles_for_slot(
                slot_index=slot_idx,
                slot_start=smart_slot['start_date'],
                slot_end=smart_slot['end_date'],
                candidate_vins=available_vins,
                availability_df=availability_grid,
                exclude_vins=set()  # Don't exclude yet - OR-Tools handles uniqueness
            )
            all_candidate_vins.update(slot_vins)

        if not all_candidate_vins:
            logger.error("No vehicles available for any slot")
            raise HTTPException(
                status_code=400,
                detail="No vehicles available for any slot in the requested date range"
            )

        # Build candidate DataFrame
        candidate_vehicles_df = vehicles_df[vehicles_df['vin'].isin(all_candidate_vins)].copy()

        # Ensure person_id type matches
        if not partners_df.empty and 'person_id' in partners_df.columns:
            partners_df['person_id'] = partners_df['person_id'].astype(int)

        candidate_vehicles_df['person_id'] = int(person_id)
        candidate_vehicles_df['market'] = office

        # Rename 'office' column to avoid conflict
        if 'office' in candidate_vehicles_df.columns:
            candidate_vehicles_df = candidate_vehicles_df.rename(columns={'office': 'vehicle_office'})

        # Score ALL candidates using optimizer logic
        scored_candidates = compute_candidate_scores(
            candidates_df=candidate_vehicles_df,
            partner_rank_df=approved_makes_df,
            partners_df=partners_df,
            publication_df=pd.DataFrame()  # Empty publication data for now
        )

        if scored_candidates.empty:
            logger.error("No scored candidates after compute_candidate_scores")
            raise HTTPException(
                status_code=400,
                detail="No eligible vehicles found after scoring"
            )

        # Extract scores as dict: {vin: score}
        vehicle_scores = {
            row['vin']: int(row['score'])
            for _, row in scored_candidates.iterrows()
        }

        # Call OR-Tools solver
        logger.info(f"Calling OR-Tools solver with {len(scored_candidates)} candidates, {len(smart_slots)} slots")

        chain_result = solve_partner_chain(
            person_id=int(person_id),
            partner_name=partner_name,
            office=office,
            smart_slots=smart_slots,
            candidate_vehicles_df=scored_candidates,  # Pass scored DataFrame
            vehicle_scores=vehicle_scores,
            model_preferences=model_prefs,
            preference_mode=preference_mode
        )

        if chain_result.status not in ['OPTIMAL', 'FEASIBLE']:
            logger.error(f"Solver failed: {chain_result.status}")
            raise HTTPException(
                status_code=400,
                detail=f"Could not generate optimal chain: {chain_result.optimization_stats.get('error', chain_result.status)}"
            )

        suggested_chain = chain_result.chain
        logger.info(f"OR-Tools generated chain with {len(suggested_chain)} vehicles (status: {chain_result.status})")

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
                ).days + 1 if suggested_chain else 0,
                "preference_mode": preference_mode,
                "preferences_count": len(model_prefs)
            },
            "suggested_chain": suggested_chain,  # NEW: Use suggested_chain key for consistency with Vehicle Chain
            "optimization_stats": chain_result.optimization_stats,  # NEW: OR-Tools solver stats
            "diagnostics": chain_result.diagnostics,  # NEW: Explanation of decisions
            "constraints_applied": {
                "excluded_vins": len(excluded_vins),
                "cooldown_filtered": sum(1 for status in cooldown_status.values() if not status['cooldown_ok']),
                "tier_cap_warnings": 0,
                "availability_checked": True,
                "model_preferences_applied": len(model_prefs) > 0
            },
            "exclusion_details": exclusion_result.get('exclusion_details', []),
            "cooldown_status": {
                f"{make}_{model}": status
                for (make, model), status in cooldown_status.items()
            },
            "slot_availability": slot_availability_counts,
            "message": (
                f"Chain generated using OR-Tools ({chain_result.status}). "
                f"{len(suggested_chain)}/{num_vehicles} vehicles selected. "
                f"{chain_result.optimization_stats.get('preferred_match_count', 0)}/{num_vehicles} match preferences. "
                f"Total score: {chain_result.optimization_stats.get('total_score', 0)}."
            )
        }

    except ValueError as e:
        logger.error(f"Invalid date format: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid date format: {start_date}. Use YYYY-MM-DD")

    except Exception as e:
        logger.error(f"Error suggesting chain: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model-availability")
async def get_model_availability(
    person_id: int = Query(..., description="Media partner ID"),
    office: str = Query(..., description="Office name"),
    start_date: str = Query(..., description="Chain start date (YYYY-MM-DD)"),
    num_vehicles: int = Query(4, description="Number of vehicles in chain", ge=1, le=10),
    days_per_loan: int = Query(8, description="Days per loan", ge=1, le=14),
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    Get availability counts by make/model for ModelSelector UI.

    Returns dictionary mapping make -> {model: count, total: count}
    Used by frontend to display "Honda Accord (5 available)" in dropdown.

    Args:
        person_id: Target media partner ID
        office: Office to pull vehicles from
        start_date: When chain should start
        num_vehicles: How many vehicles in the chain
        days_per_loan: Loan duration in days

    Returns:
        Dictionary like:
        {
            "Honda": {"total": 12, "Accord": 5, "CR-V": 4, "Civic": 3},
            "Toyota": {"total": 8, "Camry": 3, "RAV4": 5}
        }
    """

    try:
        logger.info(f"Loading model availability for partner {person_id}, office {office}")

        # Load vehicles
        vehicles_response = db.client.table('vehicles').select('*').eq('office', office).execute()
        vehicles_df = pd.DataFrame(vehicles_response.data) if vehicles_response.data else pd.DataFrame()

        if vehicles_df.empty:
            return {}

        # Load loan history for exclusions
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

        # Load approved makes for this partner
        logger.info("Loading approved makes for partner")
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

        # Convert person_id to int for comparison
        if not approved_makes_df.empty:
            approved_makes_df['person_id'] = approved_makes_df['person_id'].astype(int)

        # Get makes this partner has approved
        partner_approved = approved_makes_df[approved_makes_df['person_id'] == int(person_id)]
        approved_makes_set = set(partner_approved['make'].unique()) if not partner_approved.empty else set()

        logger.info(f"Partner has {len(approved_makes_set)} approved makes")

        # Filter to available vehicles with approved makes
        available_vehicles = vehicles_df[
            (vehicles_df['vin'].isin(available_vins)) &
            (vehicles_df['make'].isin(approved_makes_set))
        ]

        logger.info(f"After approved_makes filter: {len(available_vehicles)} vehicles available")

        # NOTE: We do NOT filter by date availability here!
        # Rationale: ModelSelector is for PREFERENCES, not availability checking.
        # A vehicle might be busy during Slot 1 but free for Slot 3.
        # OR-Tools solver handles date availability slot-by-slot during chain generation.
        # Filtering here would unnecessarily hide valid preference options.

        # Build availability count by make/model (showing ALL eligible vehicles)
        availability_by_model = {}

        for make in available_vehicles['make'].unique():
            make_vehicles = available_vehicles[available_vehicles['make'] == make]
            availability_by_model[make] = {"total": len(make_vehicles)}

            for model in make_vehicles['model'].unique():
                model_count = len(make_vehicles[make_vehicles['model'] == model])
                availability_by_model[make][model] = model_count

        logger.info(f"Found {len(availability_by_model)} makes with available vehicles")

        return availability_by_model

    except Exception as e:
        logger.error(f"Error getting model availability: {str(e)}")
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


@router.post("/save-vehicle-chain")
async def save_vehicle_chain(
    request: Dict[str, Any],
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    Save vehicle chain to scheduled_assignments table.

    Same table as partner chains, but vehicle-centric perspective.

    Request body:
        {
            "vin": str,
            "vehicle_make": str,
            "vehicle_model": str,
            "office": str,
            "status": str (optional, default='manual', can be 'manual' or 'requested'),
            "chain": [
                {
                    "person_id": int,
                    "partner_name": str,
                    "start_date": str,
                    "end_date": str,
                    "score": int
                }
            ]
        }

    Returns success status and assignment IDs
    """

    try:
        vin = request.get('vin')
        vehicle_make = request.get('vehicle_make')
        vehicle_model = request.get('vehicle_model', '')
        office = request.get('office')
        status = request.get('status', 'manual')  # Default to 'manual', can be 'requested'
        chain_partners = request.get('chain', [])

        if not vin or not office or not chain_partners:
            raise HTTPException(status_code=400, detail="Missing required fields: vin, office, chain")

        logger.info(f"Saving vehicle chain for VIN {vin}: {len(chain_partners)} partners")

        # Insert each partner as a scheduled assignment
        assignments_to_insert = []

        for partner in chain_partners:
            # Calculate week_start (Monday of the week this assignment starts)
            start_date = datetime.strptime(partner['start_date'], '%Y-%m-%d')
            monday = start_date - timedelta(days=start_date.weekday())
            week_start = monday.strftime('%Y-%m-%d')

            assignments_to_insert.append({
                'vin': vin,
                'person_id': int(partner['person_id']),
                'start_day': partner['start_date'],
                'end_day': partner['end_date'],
                'make': vehicle_make,
                'model': vehicle_model,
                'office': office,
                'partner_name': partner.get('partner_name', ''),
                'score': partner.get('score', 0),
                'week_start': week_start,  # Monday of the week
                'status': status  # 'manual' (green) or 'requested' (magenta)
            })

        # Insert all assignments
        if assignments_to_insert:
            result = db.client.table('scheduled_assignments').insert(assignments_to_insert).execute()

            return {
                'success': True,
                'message': f'Vehicle chain saved successfully! {len(assignments_to_insert)} partners added to calendar.',
                'assignments_saved': len(assignments_to_insert),
                'assignment_ids': [a.get('assignment_id') for a in result.data] if result.data else []
            }
        else:
            return {
                'success': False,
                'message': 'No partners to save'
            }

    except Exception as e:
        logger.error(f"Error saving vehicle chain: {str(e)}")
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
        vehicles_response = db.client.table('vehicles').select('*').eq('office', office).execute()
        vehicles_df = pd.DataFrame(vehicles_response.data) if vehicles_response.data else pd.DataFrame()

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
            # Handle in_service_date (might be string or date object)
            in_service_date = row.get('in_service_date')
            if pd.notna(in_service_date):
                if hasattr(in_service_date, 'isoformat'):
                    in_service_date_str = in_service_date.isoformat()
                else:
                    in_service_date_str = str(in_service_date)
            else:
                in_service_date_str = None

            vehicles_list.append({
                'vin': row['vin'],
                'make': row['make'],
                'model': row['model'],
                'year': str(row['year']) if pd.notna(row['year']) else '',
                'trim': row.get('trim', '') if pd.notna(row.get('trim', '')) else '',
                'office': row['office'],
                'in_service_date': in_service_date_str,
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


@router.get("/vehicle-busy-periods")
async def get_vehicle_busy_periods(
    vin: str = Query(..., description="Vehicle VIN"),
    start_date: str = Query(..., description="Start date for search window (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date for search window (YYYY-MM-DD)"),
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    Get vehicle's current and scheduled rental periods.

    Used to find gaps in vehicle's calendar for chain scheduling.
    Returns all active loans and scheduled assignments within the date range.

    Args:
        vin: Vehicle VIN to check
        start_date: Start of date range to check
        end_date: End of date range to check

    Returns:
        Dict with 'vin' and 'busy_periods' list containing rental periods
    """
    try:
        logger.info(f"Getting busy periods for vehicle {vin} from {start_date} to {end_date}")

        # Parse dates
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')

        busy_periods = []

        # Load all partners for name lookups
        partners_response = db.client.table('media_partners').select('person_id, name').execute()
        partners_lookup = {int(p['person_id']): p['name'] for p in partners_response.data} if partners_response.data else {}

        # 1. Get current active loans for this vehicle
        # Note: current_activity doesn't have VIN column, need to get all and filter
        current_activity_response = db.client.table('current_activity').select('*').execute()
        current_activity_df = pd.DataFrame(current_activity_response.data) if current_activity_response.data else pd.DataFrame()

        # Filter by VIN if dataframe has vehicle_vin column (check what column name exists)
        if not current_activity_df.empty:
            # Try different possible column names for VIN
            vin_col = None
            for col in ['vehicle_vin', 'vin', 'VIN']:
                if col in current_activity_df.columns:
                    vin_col = col
                    break

            if vin_col:
                vehicle_activity = current_activity_df[current_activity_df[vin_col] == vin]
            else:
                # No VIN column found, can't filter by vehicle
                logger.warning(f"No VIN column found in current_activity table. Columns: {current_activity_df.columns.tolist()}")
                vehicle_activity = pd.DataFrame()
        else:
            vehicle_activity = pd.DataFrame()

        for _, activity in vehicle_activity.iterrows():
            # Parse dates from activity
            activity_start = datetime.strptime(activity['start_date'], '%Y-%m-%d') if activity.get('start_date') else None
            activity_end = datetime.strptime(activity['end_date'], '%Y-%m-%d') if activity.get('end_date') else None

            # Check if overlaps with our search window
            if activity_start and activity_end:
                if activity_start <= end_dt and activity_end >= start_dt:
                    # Get partner name from person_id
                    person_id = activity.get('person_id')
                    partner_name = activity.get('partner_name')

                    if not partner_name and person_id:
                        # Look up from partners_lookup dictionary
                        partner_name = partners_lookup.get(int(person_id))

                    if not partner_name:
                        # Fallback: use to_field from current_activity
                        partner_name = activity.get('to_field', 'Unknown Partner')

                    busy_periods.append({
                        'start_date': activity['start_date'],
                        'end_date': activity['end_date'],
                        'partner_name': partner_name,
                        'person_id': person_id,
                        'status': 'active'
                    })

        # 2. Get scheduled assignments for this vehicle
        # First try exact match
        scheduled_response = db.client.table('scheduled_assignments').select('*').eq('vin', vin).execute()
        scheduled_assignments = scheduled_response.data if scheduled_response.data else []

        logger.info(f"Found {len(scheduled_assignments)} scheduled assignments for VIN {vin} (exact match)")

        # If no exact match, try case-insensitive or partial match
        if not scheduled_assignments:
            # Get all scheduled assignments and filter client-side
            all_scheduled = db.client.table('scheduled_assignments').select('*').execute()
            if all_scheduled.data:
                scheduled_df = pd.DataFrame(all_scheduled.data)
                if not scheduled_df.empty and 'vin' in scheduled_df.columns:
                    # Case-insensitive match
                    scheduled_df['vin_lower'] = scheduled_df['vin'].str.lower() if scheduled_df['vin'].dtype == 'object' else scheduled_df['vin']
                    matching = scheduled_df[scheduled_df['vin_lower'] == vin.lower()]
                    scheduled_assignments = matching.to_dict('records')
                    logger.info(f"Found {len(scheduled_assignments)} assignments with case-insensitive match")

        for assignment in scheduled_assignments:
            # Parse dates from assignment
            assignment_start = datetime.strptime(assignment['start_day'], '%Y-%m-%d') if assignment.get('start_day') else None
            assignment_end = datetime.strptime(assignment['end_day'], '%Y-%m-%d') if assignment.get('end_day') else None

            # Check if overlaps with our search window
            if assignment_start and assignment_end:
                if assignment_start <= end_dt and assignment_end >= start_dt:
                    busy_periods.append({
                        'assignment_id': assignment.get('assignment_id'),  # CRITICAL: needed for deletion
                        'start_date': assignment['start_day'],
                        'end_date': assignment['end_day'],
                        'partner_name': assignment.get('partner_name', 'Unknown'),
                        'person_id': assignment.get('person_id'),
                        'status': assignment.get('status', 'scheduled')  # 'manual' or 'requested'
                    })

        # Sort by start_date
        busy_periods.sort(key=lambda x: x['start_date'])

        logger.info(f"Found {len(busy_periods)} busy periods for vehicle {vin}")

        return {
            "vin": vin,
            "busy_periods": busy_periods,
            "search_window": {
                "start_date": start_date,
                "end_date": end_date
            },
            "total_periods": len(busy_periods)
        }

    except Exception as e:
        logger.error(f"Error getting vehicle busy periods: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get vehicle busy periods: {str(e)}")


@router.post("/suggest-vehicle-chain")
async def suggest_vehicle_chain(
    vin: str,
    office: str,
    start_date: str,
    num_partners: int = 4,
    days_per_loan: int = 8,
    distance_weight: float = 0.7,
    max_distance_per_hop: float = 50.0,
    distance_cost_per_mile: float = 2.0,
    partner_tier_filter: Optional[str] = None,
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    Auto-generate optimal partner chain for a vehicle using OR-Tools.

    Uses CP-SAT solver to find partner sequence that minimizes travel distance
    while maximizing partner quality (engagement, publication, tier).

    Args:
        vin: Vehicle VIN
        office: Office name
        start_date: Chain start date (YYYY-MM-DD, must be weekday)
        num_partners: Number of partners in chain (default 4)
        days_per_loan: Days per loan (default 8)
        distance_weight: Weight for distance optimization 0.0-1.0 (default 0.7)
        max_distance_per_hop: Hard limit on hop distance in miles (default 50)
        distance_cost_per_mile: Logistics cost per mile (default $2)

    Returns:
        Dict with optimal_chain, optimization_stats, logistics_summary
    """
    try:
        logger.info(f"Suggesting vehicle chain for VIN {vin}, office {office}, starting {start_date}")

        # 1. Validate start_date is weekday
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        if start_dt.weekday() >= 5:  # Saturday = 5, Sunday = 6
            raise HTTPException(
                status_code=400,
                detail=f"Start date must be a weekday (Mon-Fri). {start_date} is a {start_dt.strftime('%A')}"
            )

        # 1b. CRITICAL: Check if vehicle is available during chain period
        from ..solver.vehicle_chain_solver import calculate_slot_dates
        slot_dates_check = calculate_slot_dates(start_date, num_partners, days_per_loan)
        chain_end_date = slot_dates_check[-1].end_date

        # Get vehicle busy periods
        vehicle_busy_response = await get_vehicle_busy_periods(vin, start_date, chain_end_date, db)
        if vehicle_busy_response['busy_periods']:
            # Check for ACTUAL conflicts (not same-day handoffs)
            conflicts = []
            chain_start_dt = datetime.strptime(start_date, '%Y-%m-%d')

            for period in vehicle_busy_response['busy_periods']:
                period_start_dt = datetime.strptime(period['start_date'], '%Y-%m-%d')
                period_end_dt = datetime.strptime(period['end_date'], '%Y-%m-%d')
                chain_end_dt = datetime.strptime(chain_end_date, '%Y-%m-%d')

                # Allow same-day handoff in BOTH directions:
                # 1. Chain can start on day previous loan ends (incoming handoff)
                if chain_start_dt >= period_end_dt:
                    continue

                # 2. Chain can end on day next loan starts (outgoing handoff)
                if chain_end_dt <= period_start_dt:
                    continue

                # Actual conflict exists (overlaps)
                conflicts.append(f"{period['partner_name']} ({period['start_date']} to {period['end_date']})")

            if conflicts:
                raise HTTPException(
                    status_code=409,
                    detail=f"Vehicle {vin} is not available during chain period ({start_date} to {chain_end_date}). Conflicts: {', '.join(conflicts)}"
                )

        # 2. Get vehicle details
        vehicle_response = db.client.table('vehicles').select('*').eq('vin', vin).eq('office', office).execute()
        if not vehicle_response.data:
            raise HTTPException(status_code=404, detail=f"Vehicle {vin} not found in {office}")

        vehicle = vehicle_response.data[0]
        vehicle_make = vehicle['make']
        vehicle_model = vehicle.get('model', '')

        logger.info(f"Vehicle: {vehicle_make} {vehicle_model}")

        # 3. Load all necessary data with pagination

        # Partners
        partners_response = db.client.table('media_partners').select('*').eq('office', office).execute()
        partners_df = pd.DataFrame(partners_response.data) if partners_response.data else pd.DataFrame()

        if partners_df.empty:
            raise HTTPException(status_code=404, detail=f"No partners found for office {office}")

        # Approved makes (with pagination)
        approved_makes = []
        offset = 0
        while True:
            response = db.client.table('approved_makes').select('*').range(offset, offset + 999).execute()
            if not response.data:
                break
            approved_makes.extend(response.data)
            offset += 1000
            if len(response.data) < 1000:
                break

        approved_makes_df = pd.DataFrame(approved_makes) if approved_makes else pd.DataFrame()

        # Loan history (with pagination)
        loan_history = []
        offset = 0
        while True:
            response = db.client.table('loan_history').select('*').range(offset, offset + 999).execute()
            if not response.data:
                break
            loan_history.extend(response.data)
            offset += 1000
            if len(response.data) < 1000:
                break

        loan_history_df = pd.DataFrame(loan_history) if loan_history else pd.DataFrame()

        # Current activity
        current_activity_response = db.client.table('current_activity').select('*').execute()
        current_activity_df = pd.DataFrame(current_activity_response.data) if current_activity_response.data else pd.DataFrame()

        # Scheduled assignments
        scheduled_response = db.client.table('scheduled_assignments').select('*').execute()
        scheduled_df = pd.DataFrame(scheduled_response.data) if scheduled_response.data else pd.DataFrame()

        logger.info(f"Loaded: {len(partners_df)} partners, {len(approved_makes_df)} approved_makes, {len(loan_history_df)} loan history")

        # 4. Get eligible partners (not reviewed, approved for make)
        exclusion_result = get_partners_not_reviewed(
            vin=vin,
            office=office,
            loan_history_df=loan_history_df,
            partners_df=partners_df,
            approved_makes_df=approved_makes_df,
            vehicle_make=vehicle_make
        )

        eligible_partner_ids = exclusion_result['eligible_partners']

        if not eligible_partner_ids:
            raise HTTPException(
                status_code=404,
                detail=f"No eligible partners found. Excluded: {len(exclusion_result['excluded_partners'])}, Ineligible for {vehicle_make}: {len(exclusion_result['ineligible_make'])}"
            )

        logger.info(f"Eligible partners: {len(eligible_partner_ids)}, Excluded: {len(exclusion_result['excluded_partners'])}, Ineligible: {len(exclusion_result['ineligible_make'])}")

        # 4a. Filter by tier if specified
        if partner_tier_filter:
            allowed_tiers = [t.strip() for t in partner_tier_filter.split(',')]
            logger.info(f"Applying tier filter: {allowed_tiers}")

            # Filter approved_makes to only allowed tiers for this vehicle's make
            if not approved_makes_df.empty:
                approved_makes_df['person_id'] = pd.to_numeric(approved_makes_df['person_id'], errors='coerce').astype('Int64')

                # Get partners who have the allowed tier for this vehicle's make
                tier_filtered = approved_makes_df[
                    (approved_makes_df['make'] == vehicle_make) &
                    (approved_makes_df['rank'].isin(allowed_tiers))
                ]
                tier_approved_partner_ids = set(tier_filtered['person_id'].dropna().astype(int).tolist())

                # Intersect with eligible partners
                eligible_partner_ids = set(eligible_partner_ids) & tier_approved_partner_ids
                logger.info(f"After tier filter ({allowed_tiers}): {len(eligible_partner_ids)} partners remaining")

        # 4b. CRITICAL: Filter eligible partners by availability (same as manual mode)
        # Calculate chain end date for availability checking
        from ..solver.vehicle_chain_solver import calculate_slot_dates
        slot_dates = calculate_slot_dates(start_date, num_partners, days_per_loan)
        chain_start = slot_dates[0].start_date
        chain_end = slot_dates[-1].end_date

        logger.info(f"Building partner availability grid from {chain_start} to {chain_end}")

        # Build partner availability grid for entire chain period
        partner_availability_grid = build_partner_availability_grid(
            partners_df=partners_df,
            current_activity_df=current_activity_df,
            scheduled_assignments_df=scheduled_df,
            start_date=chain_start,
            end_date=chain_end,
            office=office
        )

        # Filter out partners who are busy during ANY slot in the chain
        available_partner_ids = []
        unavailable_partners = []
        for partner_id in eligible_partner_ids:
            # Check availability for each slot
            all_slots_available = True
            for slot in slot_dates:
                availability_check = check_partner_slot_availability(
                    person_id=partner_id,
                    slot_start=slot.start_date,
                    slot_end=slot.end_date,
                    availability_df=partner_availability_grid
                )
                if not availability_check['available']:
                    all_slots_available = False
                    unavailable_partners.append({
                        'person_id': partner_id,
                        'conflict_slot': f"{slot.start_date} to {slot.end_date}",
                        'reason': availability_check.get('reason', 'unknown')
                    })
                    break  # No need to check remaining slots

            if all_slots_available:
                available_partner_ids.append(partner_id)

        logger.info(f"Availability filtering: {len(available_partner_ids)} available across all slots, {len(unavailable_partners)} have conflicts")

        if not available_partner_ids:
            raise HTTPException(
                status_code=404,
                detail=f"No partners available for entire chain period ({chain_start} to {chain_end}). All {len(eligible_partner_ids)} eligible partners have scheduling conflicts."
            )

        # Update eligible list to only include available partners
        eligible_partner_ids = available_partner_ids

        # 5. Score partners
        scores = score_partners_base(
            partners_df=partners_df,
            vehicle_make=vehicle_make,
            approved_makes_df=approved_makes_df,
            loan_history_df=loan_history_df
        )

        # 6. Calculate distance matrix for eligible partners
        # IMPORTANT: Convert person_id types to match
        partners_df['person_id'] = partners_df['person_id'].astype(int)
        eligible_partner_ids_int = [int(pid) for pid in eligible_partner_ids]
        eligible_partners_df = partners_df[partners_df['person_id'].isin(eligible_partner_ids_int)]

        distance_matrix = calculate_distance_matrix(eligible_partners_df)

        logger.info(f"Calculated {len(distance_matrix)} pairwise distances")

        # 7. Build Partner objects for solver
        candidates = []
        for _, partner in eligible_partners_df.iterrows():
            person_id = int(partner['person_id'])
            score_data = scores.get(person_id, {})

            candidates.append(Partner(
                person_id=person_id,
                name=partner.get('name', f'Partner {person_id}'),
                address=partner.get('address', ''),
                latitude=partner.get('latitude'),
                longitude=partner.get('longitude'),
                base_score=score_data.get('base_score', 0),
                engagement_level=score_data.get('engagement_level', 'neutral'),
                publication_rate=score_data.get('publication_rate', 0.0),
                tier_rank=score_data.get('tier_rank', 'N/A'),
                available=True
            ))

        logger.info(f"Prepared {len(candidates)} candidate partners for solver")

        # 8. Solve with OR-Tools
        result = solve_vehicle_chain(
            vin=vin,
            vehicle_make=vehicle_make,
            office=office,
            start_date=start_date,
            num_partners=num_partners,
            days_per_loan=days_per_loan,
            candidates=candidates,
            distance_matrix=distance_matrix,
            distance_weight=distance_weight,
            max_distance_per_hop=max_distance_per_hop,
            distance_cost_per_mile=distance_cost_per_mile,
            solver_timeout_seconds=30.0
        )

        # 9. Add office distance to slot 0
        if result.status == 'success' and result.chain:
            # Get office coordinates
            office_response = db.client.table('offices').select('latitude, longitude').eq('name', office).execute()
            if office_response.data and len(office_response.data) > 0:
                office_lat = office_response.data[0].get('latitude')
                office_lng = office_response.data[0].get('longitude')

                # Calculate distance from office to first partner
                if office_lat and office_lng and result.chain[0].get('latitude') and result.chain[0].get('longitude'):
                    from ..chain_builder.geography import haversine_distance
                    office_distance = haversine_distance(
                        office_lat,
                        office_lng,
                        result.chain[0]['latitude'],
                        result.chain[0]['longitude']
                    )
                    result.chain[0]['office_distance'] = round(office_distance, 2)
                    logger.info(f"Slot 0 office distance: {result.chain[0]['office_distance']} mi")

        # 10. Return result
        if result.status == 'success':
            return {
                "status": "success",
                "vehicle_info": {
                    "vin": vin,
                    "make": vehicle_make,
                    "model": vehicle_model,
                    "office": office
                },
                "chain_params": {
                    "start_date": start_date,
                    "num_partners": num_partners,
                    "days_per_loan": days_per_loan,
                    "total_span_days": (datetime.strptime(result.chain[-1]['end_date'], '%Y-%m-%d') - start_dt).days if result.chain else 0
                },
                "optimal_chain": result.chain,
                "optimization_stats": result.optimization_stats,
                "logistics_summary": result.logistics_summary,
                "diagnostics": result.diagnostics,
                "constraints_applied": {
                    "total_partners": len(partners_df),
                    "eligible_partners": len(eligible_partner_ids),
                    "excluded_reviewed": len(exclusion_result['excluded_partners']),
                    "ineligible_make": len(exclusion_result['ineligible_make']),
                    "candidates_with_coords": result.optimization_stats.get('candidates_considered', 0),
                    "distance_weight": distance_weight,
                    "max_distance_per_hop": max_distance_per_hop
                },
                "message": f"Found optimal {num_partners}-partner chain for {vehicle_make} {vehicle_model}"
            }
        else:
            # Infeasible or timeout
            return {
                "status": result.status,
                "vehicle_info": {
                    "vin": vin,
                    "make": vehicle_make,
                    "model": vehicle_model,
                    "office": office
                },
                "chain_params": {
                    "start_date": start_date,
                    "num_partners": num_partners,
                    "days_per_loan": days_per_loan
                },
                "optimal_chain": [],
                "diagnostics": result.diagnostics,
                "message": f"Could not find feasible chain: {result.diagnostics.get('reason', 'Unknown')}"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error suggesting vehicle chain: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to suggest vehicle chain: {str(e)}")


@router.get("/get-partner-slot-options")
async def get_partner_slot_options(
    vin: str = Query(..., description="Vehicle VIN"),
    office: str = Query(..., description="Office name"),
    start_date: str = Query(..., description="Chain start date (YYYY-MM-DD)"),
    num_partners: int = Query(4, description="Total number of partners in chain"),
    days_per_loan: int = Query(8, description="Days per loan"),
    slot_index: int = Query(..., description="Slot index (0-based)"),
    exclude_partner_ids: str = Query("", description="Comma-separated partner IDs already selected"),
    previous_partner_id: Optional[int] = Query(None, description="Partner in previous slot (for distance calc)"),
    previous_partner_lat: Optional[float] = Query(None, description="Previous partner latitude"),
    previous_partner_lng: Optional[float] = Query(None, description="Previous partner longitude"),
    distance_weight: float = Query(0.7, description="Weight for distance penalty"),
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    Returns eligible partners for a specific slot in manual build mode.

    Sorted by distance-adjusted score (if previous partner provided).
    Includes partners without coordinates at bottom with warning.

    Args:
        vin: Vehicle VIN
        office: Office name
        start_date: Chain start date
        num_partners: Total partners in chain
        days_per_loan: Days per loan
        slot_index: Which slot to get options for (0-based)
        exclude_partner_ids: Already-selected partner IDs (comma-separated)
        previous_partner_id: Partner from previous slot (for distance calc)
        previous_partner_lat: Latitude of previous partner
        previous_partner_lng: Longitude of previous partner
        distance_weight: How much to penalize distance (0.0-1.0)

    Returns:
        Dict with eligible_partners list sorted by distance-adjusted score
    """
    try:
        logger.info(f"Getting partner options for slot {slot_index}, VIN {vin}")

        # Validate slot_index
        if slot_index < 0 or slot_index >= num_partners:
            raise HTTPException(
                status_code=400,
                detail=f"slot_index must be 0 to {num_partners - 1}, got {slot_index}"
            )

        # Get vehicle details
        vehicle_response = db.client.table('vehicles').select('*').eq('vin', vin).eq('office', office).execute()
        if not vehicle_response.data:
            raise HTTPException(status_code=404, detail=f"Vehicle {vin} not found in {office}")

        vehicle = vehicle_response.data[0]
        vehicle_make = vehicle['make']

        # Calculate slot dates
        from ..solver.vehicle_chain_solver import calculate_slot_dates
        slot_dates = calculate_slot_dates(start_date, num_partners, days_per_loan)
        target_slot = slot_dates[slot_index]

        logger.info(f"Slot {slot_index}: {target_slot.start_date} to {target_slot.end_date}")

        # CRITICAL: Check vehicle availability for this slot (first time slot 0 loads, check entire chain)
        if slot_index == 0:
            chain_end_date = slot_dates[-1].end_date
            vehicle_busy_response = await get_vehicle_busy_periods(vin, start_date, chain_end_date, db)
            if vehicle_busy_response['busy_periods']:
                # Check for ACTUAL conflicts (not same-day handoffs)
                conflicts = []
                chain_start_dt = datetime.strptime(start_date, '%Y-%m-%d')

                for period in vehicle_busy_response['busy_periods']:
                    period_start_dt = datetime.strptime(period['start_date'], '%Y-%m-%d')
                    period_end_dt = datetime.strptime(period['end_date'], '%Y-%m-%d')
                    chain_end_dt = datetime.strptime(chain_end_date, '%Y-%m-%d')

                    # Allow same-day handoff in BOTH directions:
                    # 1. Chain can start on day previous loan ends (incoming handoff)
                    if chain_start_dt >= period_end_dt:
                        continue

                    # 2. Chain can end on day next loan starts (outgoing handoff)
                    if chain_end_dt <= period_start_dt:
                        continue

                    # Actual conflict exists (overlaps)
                    conflicts.append(f"{period['partner_name']} ({period['start_date']} to {period['end_date']})")

                if conflicts:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Vehicle is not available during chain period ({start_date} to {chain_end_date}). Conflicts: {', '.join(conflicts)}"
                    )

        # Get office coordinates for slot 0 distance calculation
        office_lat = None
        office_lng = None
        if slot_index == 0:
            office_response = db.client.table('offices').select('latitude, longitude').eq('name', office).execute()
            if office_response.data and len(office_response.data) > 0:
                office_lat = office_response.data[0].get('latitude')
                office_lng = office_response.data[0].get('longitude')
                logger.info(f"Office location: ({office_lat}, {office_lng})")

        # Load all data (same as suggest-vehicle-chain)
        partners_response = db.client.table('media_partners').select('*').eq('office', office).execute()
        partners_df = pd.DataFrame(partners_response.data) if partners_response.data else pd.DataFrame()

        if partners_df.empty:
            raise HTTPException(status_code=404, detail=f"No partners found for office {office}")

        # Load approved_makes with pagination
        approved_makes = []
        offset = 0
        while True:
            response = db.client.table('approved_makes').select('*').range(offset, offset + 999).execute()
            if not response.data:
                break
            approved_makes.extend(response.data)
            offset += 1000
            if len(response.data) < 1000:
                break

        approved_makes_df = pd.DataFrame(approved_makes) if approved_makes else pd.DataFrame()

        # Load loan history with pagination
        loan_history = []
        offset = 0
        while True:
            response = db.client.table('loan_history').select('*').range(offset, offset + 999).execute()
            if not response.data:
                break
            loan_history.extend(response.data)
            offset += 1000
            if len(response.data) < 1000:
                break

        loan_history_df = pd.DataFrame(loan_history) if loan_history else pd.DataFrame()

        # Load current activity and scheduled assignments for availability checking
        logger.info("Loading current activity for partner availability check")
        current_activity_response = db.client.table('current_activity').select('*').execute()
        current_activity_df = pd.DataFrame(current_activity_response.data) if current_activity_response.data else pd.DataFrame()

        logger.info("Loading scheduled assignments for partner availability check")
        scheduled_response = db.client.table('scheduled_assignments').select('*').execute()
        scheduled_assignments_df = pd.DataFrame(scheduled_response.data) if scheduled_response.data else pd.DataFrame()

        # Get eligible partners
        exclusion_result = get_partners_not_reviewed(
            vin=vin,
            office=office,
            loan_history_df=loan_history_df,
            partners_df=partners_df,
            approved_makes_df=approved_makes_df,
            vehicle_make=vehicle_make
        )

        eligible_partner_ids = exclusion_result['eligible_partners']

        # Exclude already-selected partners
        if exclude_partner_ids:
            excluded_set = set(int(pid) for pid in exclude_partner_ids.split(',') if pid.strip())
            eligible_partner_ids = [pid for pid in eligible_partner_ids if pid not in excluded_set]
            logger.info(f"Excluded {len(excluded_set)} already-selected partners")

        # CRITICAL: Filter out busy partners (those with active loans or scheduled assignments during this slot)
        # Build partner availability grid for the entire slot period
        partner_availability_grid = build_partner_availability_grid(
            partners_df=partners_df,
            current_activity_df=current_activity_df,
            scheduled_assignments_df=scheduled_assignments_df,
            start_date=target_slot.start_date,
            end_date=target_slot.end_date,
            office=office
        )

        available_partner_ids = []
        unavailable_count = 0
        for partner_id in eligible_partner_ids:
            availability_check = check_partner_slot_availability(
                person_id=partner_id,
                slot_start=target_slot.start_date,
                slot_end=target_slot.end_date,
                availability_df=partner_availability_grid
            )
            if availability_check['available']:
                available_partner_ids.append(partner_id)
            else:
                unavailable_count += 1
                logger.debug(f"Partner {partner_id} unavailable: {availability_check.get('reason', 'unknown')}")

        logger.info(f"Availability check: {len(available_partner_ids)} available, {unavailable_count} unavailable")
        eligible_partner_ids = available_partner_ids

        # Score partners
        scores = score_partners_base(
            partners_df=partners_df,
            vehicle_make=vehicle_make,
            approved_makes_df=approved_makes_df,
            loan_history_df=loan_history_df
        )

        # Build partner list with scoring
        partners_df['person_id'] = partners_df['person_id'].astype(int)
        eligible_partners_df = partners_df[partners_df['person_id'].isin([int(pid) for pid in eligible_partner_ids])]

        partner_options = []

        for _, partner in eligible_partners_df.iterrows():
            person_id = int(partner['person_id'])
            score_data = scores.get(person_id, {})
            base_score = score_data.get('base_score', 0)

            # Calculate distance (from previous partner OR from office for slot 0)
            distance_from_previous = None
            distance_penalty = 0
            has_coordinates = pd.notna(partner.get('latitude')) and pd.notna(partner.get('longitude'))

            if has_coordinates:
                from ..chain_builder.geography import haversine_distance

                if slot_index == 0 and office_lat and office_lng:
                    # Slot 0: Calculate distance from office
                    distance_from_previous = haversine_distance(
                        office_lat,
                        office_lng,
                        float(partner['latitude']),
                        float(partner['longitude'])
                    )
                    distance_from_previous = round(distance_from_previous, 2)
                    # Apply distance penalty for slot 0 too (office distance matters)
                    distance_penalty = int(distance_from_previous * distance_weight * 10)

                elif slot_index > 0 and previous_partner_id and previous_partner_lat and previous_partner_lng:
                    # Slot 1+: Calculate distance from previous partner
                    distance_from_previous = haversine_distance(
                        previous_partner_lat,
                        previous_partner_lng,
                        float(partner['latitude']),
                        float(partner['longitude'])
                    )
                    distance_from_previous = round(distance_from_previous, 2)
                    # Apply distance penalty to score
                    distance_penalty = int(distance_from_previous * distance_weight * 10)

            final_score = base_score - distance_penalty

            partner_options.append({
                'person_id': person_id,
                'name': partner.get('name', f'Partner {person_id}'),
                'address': partner.get('address', 'N/A'),
                'latitude': partner.get('latitude'),
                'longitude': partner.get('longitude'),
                'has_coordinates': has_coordinates,
                'distance_from_previous': distance_from_previous,
                'base_score': base_score,
                'distance_penalty': distance_penalty,
                'final_score': final_score,
                'tier': score_data.get('tier_rank', 'N/A'),
                'engagement_level': score_data.get('engagement_level', 'neutral'),
                'publication_rate': score_data.get('publication_rate', 0.0)
            })

        # Sort by final_score DESC, then put partners without coordinates at bottom
        partner_options_with_coords = [p for p in partner_options if p['has_coordinates']]
        partner_options_without_coords = [p for p in partner_options if not p['has_coordinates']]

        partner_options_with_coords.sort(key=lambda x: x['final_score'], reverse=True)
        partner_options_without_coords.sort(key=lambda x: x['base_score'], reverse=True)

        # Combine: coords first, then no coords
        sorted_partners = partner_options_with_coords + partner_options_without_coords

        logger.info(f"Returning {len(sorted_partners)} partner options for slot {slot_index} (no limit applied)")

        return {
            "status": "success",
            "slot": {
                "index": slot_index,
                "start_date": target_slot.start_date,
                "end_date": target_slot.end_date,
                "actual_duration": target_slot.actual_duration,
                "extended_for_weekend": target_slot.extended_for_weekend
            },
            "office_location": {
                "office_name": office,
                "latitude": office_lat,
                "longitude": office_lng
            } if slot_index == 0 and office_lat and office_lng else None,
            "previous_partner": {
                "person_id": previous_partner_id,
                "latitude": previous_partner_lat,
                "longitude": previous_partner_lng
            } if previous_partner_id else None,
            "eligible_partners": sorted_partners,
            "total_eligible": len(sorted_partners),
            "with_coordinates": len(partner_options_with_coords),
            "without_coordinates": len(partner_options_without_coords),
            "excluded_count": len(exclude_partner_ids.split(',')) if exclude_partner_ids else 0,
            "unavailable_count": unavailable_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting partner slot options: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get partner slot options: {str(e)}")
