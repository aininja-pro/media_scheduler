"""
UI endpoints for Phase 7 - read-only metrics using existing Phase 7 functions.
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Dict, Any
import pandas as pd
from datetime import datetime, timedelta

from ..services.database import DatabaseService
from ..solver.ortools_feasible_v2 import build_feasible_start_day_triples
from ..solver.cooldown_filter import apply_cooldown_filter
from ..etl.availability import build_availability_grid
from ..solver.dynamic_capacity import load_capacity_calendar

router = APIRouter(prefix="/ui/phase7", tags=["UI Phase 7"])


@router.get("/overview")
async def get_overview(
    office: str = Query(..., description="Office name"),
    week_start: str = Query(..., description="Week start date (YYYY-MM-DD)"),
    min_days: int = Query(7, description="Minimum available days")
) -> Dict[str, Any]:
    """
    Get overview metrics for Phase 7 UI using existing Phase 7 functions.
    Returns real counts without any new business logic.
    """

    db = DatabaseService()
    await db.initialize()

    try:
        week_start_date = pd.to_datetime(week_start)

        # 1. Load vehicles (filter to office)
        vehicles_response = db.client.table('vehicles').select('*').eq('office', office).execute()
        vehicles_df = pd.DataFrame(vehicles_response.data) if vehicles_response.data else pd.DataFrame()
        total_vehicles = len(vehicles_df)

        # 2. Load partners (filter to office)
        partners_response = db.client.table('media_partners').select('*').eq('office', office).execute()
        partners_df = pd.DataFrame(partners_response.data) if partners_response.data else pd.DataFrame()
        total_partners = len(partners_df)

        # 3. Load current activity WITH PAGINATION
        all_activity = []
        offset = 0
        limit = 1000
        while True:
            activity_response = db.client.table('current_activity').select('*').range(offset, offset + limit - 1).execute()
            if not activity_response.data:
                break
            all_activity.extend(activity_response.data)
            if len(activity_response.data) < limit:
                break
            offset += limit

        current_activity_df = pd.DataFrame(all_activity) if all_activity else pd.DataFrame()

        # Rename column to match expected format
        if 'vehicle_vin' in current_activity_df.columns:
            current_activity_df = current_activity_df.rename(columns={'vehicle_vin': 'vin'})

        # 4. Build availability grid using existing function
        availability_df = build_availability_grid(
            vehicles_df=vehicles_df,
            activity_df=current_activity_df,
            week_start=week_start,
            office=office,
            availability_horizon_days=14,  # Need 14 days for proper availability check
            loan_length_days=min_days
        )

        # Rename 'day' to 'date' to match expected format
        if 'day' in availability_df.columns:
            availability_df = availability_df.rename(columns={'day': 'date'})

        # 5. Load approved makes WITH PAGINATION
        all_approved = []
        offset = 0
        limit = 1000
        while True:
            approved_response = db.client.table('approved_makes').select('*').range(offset, offset + limit - 1).execute()
            if not approved_response.data:
                break
            all_approved.extend(approved_response.data)
            if len(approved_response.data) < limit:
                break
            offset += limit

        approved_makes_df = pd.DataFrame(all_approved) if all_approved else pd.DataFrame()

        # Filter to office partners
        office_partner_ids = set(partners_df['person_id'].tolist()) if not partners_df.empty else set()
        office_approved = approved_makes_df[approved_makes_df['person_id'].isin(office_partner_ids)]

        # 6. Generate feasible triples using Phase 7.1
        triples_pre = build_feasible_start_day_triples(
            vehicles_df=vehicles_df,
            partners_df=partners_df,
            availability_df=availability_df,
            approved_makes_df=office_approved,
            week_start=week_start,
            office=office
        )

        # Count unique vehicles and partners in feasible triples (pre-cooldown)
        available_vehicles = triples_pre['vin'].nunique() if not triples_pre.empty else 0
        eligible_partners = triples_pre['person_id'].nunique() if not triples_pre.empty else 0

        # 7. Apply cooldown filter using Phase 7.3
        # Load loan history WITH PAGINATION
        all_loan_history = []
        offset = 0
        limit = 1000
        while True:
            loan_response = db.client.table('loan_history').select('*').range(offset, offset + limit - 1).execute()
            if not loan_response.data:
                break
            all_loan_history.extend(loan_response.data)
            if len(loan_response.data) < limit:
                break
            offset += limit

        loan_history_df = pd.DataFrame(all_loan_history) if all_loan_history else pd.DataFrame()

        # Load rules
        rules_response = db.client.table('rules').select('*').execute()
        rules_df = pd.DataFrame(rules_response.data) if rules_response.data else pd.DataFrame()

        # Apply cooldown filter
        triples_post = apply_cooldown_filter(
            feasible_triples_df=triples_pre,
            loan_history_df=loan_history_df,
            rules_df=rules_df,
            default_cooldown_days=30
        )

        # Calculate metrics as specified
        feasible_triples_pre_cooldown = len(triples_pre)
        feasible_triples_post_cooldown = len(triples_post)
        cooldown_removed_triples = feasible_triples_pre_cooldown - feasible_triples_post_cooldown
        makes_in_scope = triples_post['make'].nunique() if not triples_post.empty else 0

        # 8. Load capacity using Phase 7.7 function
        # First load ops capacity calendar data
        ops_capacity_response = db.client.table('ops_capacity_calendar').select('*').execute()
        ops_capacity_df = pd.DataFrame(ops_capacity_response.data) if ops_capacity_response.data else pd.DataFrame()

        capacity_map, notes_map = load_capacity_calendar(
            ops_capacity_df=ops_capacity_df,
            office=office,
            week_start=week_start
        )

        # Build capacity object for each day
        capacity = {}
        days_map = {
            0: 'mon', 1: 'tue', 2: 'wed', 3: 'thu',
            4: 'fri', 5: 'sat', 6: 'sun'
        }

        for i in range(7):
            day_date = week_start_date + timedelta(days=i)
            day_key = days_map[i]

            # Get capacity from map
            slots = capacity_map.get(day_date.date(), 0 if i >= 5 else 15)  # Default 0 for weekends, 15 for weekdays
            notes = notes_map.get(day_date.date(), None)

            # Add blackout note if slots are 0 and no notes
            if slots == 0 and not notes:
                notes = 'blackout' if i >= 5 else 'blackout'

            capacity[day_key] = {
                'slots': slots,
                'notes': notes
            }

        return {
            "office": office,
            "week_start": week_start,
            "min_available_days": min_days,
            "vehicles": {
                "available": available_vehicles,
                "total": total_vehicles
            },
            "partners": {
                "eligible": eligible_partners,
                "total": total_partners
            },
            "feasible_triples_pre_cooldown": feasible_triples_pre_cooldown,
            "feasible_triples_post_cooldown": feasible_triples_post_cooldown,
            "cooldown_removed_triples": cooldown_removed_triples,
            "makes_in_scope": makes_in_scope,
            "capacity": capacity
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await db.close()