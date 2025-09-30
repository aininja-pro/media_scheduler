"""
UI endpoints for Phase 7 - read-only metrics using existing Phase 7 functions.
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Dict, Any, Optional
from pydantic import BaseModel
import pandas as pd
from datetime import datetime, timedelta
import time

from ..services.database import DatabaseService
from ..solver.ortools_feasible_v2 import build_feasible_start_day_triples
from ..solver.cooldown_filter import apply_cooldown_filter
from ..etl.availability import build_availability_grid
from ..solver.dynamic_capacity import load_capacity_calendar
from ..solver.ortools_solver_v6 import solve_with_all_constraints
from ..solver.ortools_solver_v2 import add_score_to_triples
from ..etl.publication import compute_publication_rate_24m

router = APIRouter(prefix="/ui/phase7", tags=["UI Phase 7"])


class RunRequest(BaseModel):
    office: str
    week_start: str
    seed: int = 42
    rank_weight: float = 1.0  # Partner Quality slider (0.0 - 2.0)
    geo_match: int = 100  # Local Priority slider (0 - 200)
    pub_rate: int = 150  # Publishing Success slider (0 - 300)


@router.post("/run")
async def run_optimizer(request: RunRequest) -> Dict[str, Any]:
    """
    Run Phase 7 optimizer using all implemented constraints.
    Returns assignments with actual start days distributed across the week.
    """

    db = DatabaseService()
    await db.initialize()

    try:
        start_time = time.time()

        # 1. Load all necessary data
        vehicles_response = db.client.table('vehicles').select('*').eq('office', request.office).execute()
        vehicles_df = pd.DataFrame(vehicles_response.data) if vehicles_response.data else pd.DataFrame()

        partners_response = db.client.table('media_partners').select('*').eq('office', request.office).execute()
        partners_df = pd.DataFrame(partners_response.data) if partners_response.data else pd.DataFrame()

        # Load offices with coordinates for distance calculations
        offices_response = db.client.table('offices').select('*').execute()
        offices_df = pd.DataFrame(offices_response.data) if offices_response.data else pd.DataFrame()

        # Load current activity with pagination
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
        if 'vehicle_vin' in current_activity_df.columns:
            current_activity_df = current_activity_df.rename(columns={'vehicle_vin': 'vin'})

        # Load approved makes with pagination
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
        office_partner_ids = set(partners_df['person_id'].tolist()) if not partners_df.empty else set()
        office_approved = approved_makes_df[approved_makes_df['person_id'].isin(office_partner_ids)]

        # Build availability grid
        availability_df = build_availability_grid(
            vehicles_df=vehicles_df,
            activity_df=current_activity_df,
            week_start=request.week_start,
            office=request.office,
            availability_horizon_days=14,
            loan_length_days=7
        )

        if 'day' in availability_df.columns:
            availability_df = availability_df.rename(columns={'day': 'date'})

        # 2. Load capacity for the week using Phase 7.7
        ops_capacity_response = db.client.table('ops_capacity_calendar').select('*').execute()
        ops_capacity_df = pd.DataFrame(ops_capacity_response.data) if ops_capacity_response.data else pd.DataFrame()

        capacity_map, notes_map = load_capacity_calendar(
            ops_capacity_df=ops_capacity_df,
            office=request.office,
            week_start=request.week_start
        )

        # 3. Build feasible triples using Phase 7.1
        triples_pre = build_feasible_start_day_triples(
            vehicles_df=vehicles_df,
            partners_df=partners_df,
            availability_df=availability_df,
            approved_makes_df=office_approved,
            week_start=request.week_start,
            office=request.office,
            offices_df=offices_df  # Pass offices for distance calculation
        )

        # 4. Apply cooldown filter using Phase 7.3
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

        rules_response = db.client.table('rules').select('*').execute()
        rules_df = pd.DataFrame(rules_response.data) if rules_response.data else pd.DataFrame()

        triples_post = apply_cooldown_filter(
            feasible_triples_df=triples_pre,
            loan_history_df=loan_history_df,
            rules_df=rules_df,
            default_cooldown_days=30
        )

        # 4b. Calculate publication rates from loan history
        publication_df = compute_publication_rate_24m(
            loan_history_df=loan_history_df,
            as_of_date=request.week_start,
            window_months=24,
            min_observed=3
        )
        print(f"Publication rates calculated: {len(publication_df)} partner-make combinations")
        if not publication_df.empty:
            print(f"  Avg publication rate: {publication_df['publication_rate'].mean():.2%}")

        # 4c. Add scoring columns using the Phase 7 scoring function
        triples_post = add_score_to_triples(
            triples_df=triples_post,
            partners_df=partners_df,
            publication_df=publication_df
        )

        print(f"\n=== PRE-SOLVER DEBUG ===")
        print(f"Triples to solver: {len(triples_post)} rows")
        print(f"Columns in triples: {list(triples_post.columns)}")
        print(f"Sample triple: {triples_post.iloc[0].to_dict() if not triples_post.empty else 'EMPTY'}")

        # 5. Load budgets
        budgets_response = db.client.table('budgets').select('*').execute()
        budgets_df = pd.DataFrame(budgets_response.data) if budgets_response.data else pd.DataFrame()

        # 6. Run Phase 7 solver with all constraints
        solver_result = solve_with_all_constraints(
            triples_df=triples_post,
            ops_capacity_df=ops_capacity_df,
            approved_makes_df=office_approved,
            loan_history_df=loan_history_df,
            rules_df=rules_df,
            budgets_df=budgets_df,
            week_start=request.week_start,
            office=request.office,

            # Use policy parameters from request
            lambda_cap=800,
            lambda_fair=200,
            fair_step_up=400,
            fair_target=1,
            points_per_dollar=3,
            enforce_budget_hard=False,

            w_rank=request.rank_weight,  # From Partner Quality slider
            w_geo=request.geo_match,  # From Local Priority slider
            w_pub=request.pub_rate,  # From Publishing Success slider
            w_hist=50,

            solver_time_limit_s=30,  # Increased from 10s for 58k triples
            seed=request.seed,
            verbose=True  # Enable to see what's happening
        )

        # 7. Format response
        print(f"\n=== SOLVER RESULT DEBUG ===")
        print(f"Solver status: {solver_result.get('meta', {}).get('solver_status', 'UNKNOWN')}")
        print(f"Assignments count: {len(solver_result.get('selected_assignments', []))}")
        print(f"Objective value: {solver_result.get('objective_value', 0)}")

        # The solver returns a dict with 'selected_assignments' list
        selected_assignments = solver_result.get('selected_assignments', [])

        # Get partner names for enrichment (convert person_id to int for proper lookup)
        partner_names = {}
        if not partners_df.empty:
            for _, partner in partners_df.iterrows():
                pid = partner['person_id']
                # Handle numpy types
                if hasattr(pid, 'item'):
                    pid = pid.item()
                else:
                    pid = int(pid)
                partner_names[pid] = partner['name']

        # Format assignments and count by day
        assignments = []
        starts_by_day = {'mon': 0, 'tue': 0, 'wed': 0, 'thu': 0, 'fri': 0, 'sat': 0, 'sun': 0}

        for assignment in selected_assignments:
            # Count by day of week
            start_day = assignment.get('start_day', request.week_start)
            day_of_week = pd.to_datetime(start_day).dayofweek
            day_names = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
            starts_by_day[day_names[day_of_week]] += 1

            # Format for frontend (convert numpy types to Python native)
            person_id = assignment['person_id']
            # Convert numpy.int64 to Python int
            if hasattr(person_id, 'item'):
                person_id = person_id.item()
            else:
                person_id = int(person_id)

            assignments.append({
                'start_day': start_day,
                'vin': str(assignment['vin']),
                'person_id': person_id,
                'partner_name': partner_names.get(person_id, f"Partner {person_id}"),
                'make': str(assignment['make']),
                'model': str(assignment.get('model', '')),
                'score': int(assignment.get('score', 0))
            })

        # Convert DataFrames to serializable dicts
        # For now, just pass the fairness_metrics which is already a dict
        fairness_metrics = solver_result.get('fairness_metrics', {})

        # Build simple fairness summary from metrics
        fairness_summary = {
            'partners_assigned': fairness_metrics.get('num_partners', 0),
            'max_per_partner': fairness_metrics.get('max_count', 0),
            'gini': fairness_metrics.get('gini', 0)
        }

        # Cap summary - extract violations if any
        cap_summary_df = solver_result.get('cap_summary', pd.DataFrame())
        cap_violations = []
        if not cap_summary_df.empty and hasattr(cap_summary_df, 'to_dict'):
            # Find violations (where assigned > cap)
            for _, row in cap_summary_df.iterrows():
                try:
                    assigned = int(row.get('assigned', 0))
                    cap_val = row.get('cap', 0)
                    # Handle 'unlimited' or other string values
                    if isinstance(cap_val, str):
                        continue  # Skip unlimited caps
                    cap_val = int(cap_val)

                    if assigned > cap_val:
                        cap_violations.append({
                            'tier': f"{row.get('fleet', '')} {row.get('tier', '')}",
                            'count': assigned,
                            'cap': cap_val
                        })
                except (ValueError, TypeError):
                    continue  # Skip rows with invalid data

        cap_summary = {
            'violations': cap_violations,
            'total_penalty': int(cap_summary_df.attrs.get('total_penalty', 0)) if hasattr(cap_summary_df, 'attrs') else 0
        }

        # Budget summary - extract fleet usage
        budget_summary_df = solver_result.get('budget_summary', pd.DataFrame())
        budget_fleets = {}
        budget_total = {'used': 0, 'budget': 0}

        if not budget_summary_df.empty and hasattr(budget_summary_df, 'to_dict'):
            for _, row in budget_summary_df.iterrows():
                fleet = row.get('fleet', 'Unknown')
                budget_fleets[fleet] = {
                    'used': int(row.get('cost_used', 0)),
                    'budget': int(row.get('budget', 0))
                }
                budget_total['used'] += int(row.get('cost_used', 0))
                budget_total['budget'] += int(row.get('budget', 0))

        budget_summary = {
            'fleets': budget_fleets,
            'total': budget_total if budget_fleets else None
        }

        return {
            'status': solver_result.get('meta', {}).get('solver_status', 'UNKNOWN'),
            'solve_time_ms': solver_result.get('timing', {}).get('wall_ms', 0),
            'assignments_count': len(assignments),
            'partners_used': len(set(a['person_id'] for a in assignments)) if assignments else 0,
            'assignments': assignments,
            'starts_by_day': starts_by_day,
            # Pass through converted summaries
            'cap_summary': cap_summary,
            'fairness_summary': fairness_summary,
            'budget_summary': budget_summary,
            'objective_breakdown': solver_result.get('objective_breakdown', {})
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await db.close()


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

        # Load offices with coordinates for distance calculations
        offices_response = db.client.table('offices').select('*').execute()
        offices_df = pd.DataFrame(offices_response.data) if offices_response.data else pd.DataFrame()

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
            office=office,
            offices_df=offices_df  # Pass offices for distance calculation
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