"""
UI endpoints for Phase 7 - read-only metrics using existing Phase 7 functions.
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Dict, Any, Optional
from pydantic import BaseModel
import pandas as pd
from datetime import datetime, timedelta
import time
import logging

from ..services.database import DatabaseService
from ..solver.ortools_feasible_v2 import build_feasible_start_day_triples
from ..solver.cooldown_filter import apply_cooldown_filter
from ..etl.availability import build_availability_grid
from ..solver.dynamic_capacity import load_capacity_calendar
from ..solver.ortools_solver_v6 import solve_with_all_constraints
from ..solver.ortools_solver_v2 import add_score_to_triples
from ..etl.publication import compute_publication_rate_24m, compute_recency_scores
from ..utils.geocoding import get_distance_from_office

router = APIRouter(prefix="/ui/phase7", tags=["UI Phase 7"])
logger = logging.getLogger(__name__)


def calculate_cost_per_make(budgets_df: pd.DataFrame, loan_history_df: pd.DataFrame, office: str) -> Dict[str, float]:
    """
    Calculate average cost per assignment by make/fleet from historical budget data.
    Uses total amount_used from budgets table divided by loan count from loan_history.

    Returns dict mapping make name (uppercase) to average cost per loan.
    """
    cost_per_make = {}

    if budgets_df.empty or loan_history_df.empty:
        return cost_per_make

    # Filter to office
    office_budgets = budgets_df[budgets_df['office'] == office]
    office_loans = loan_history_df[loan_history_df['office'] == office]

    # For each fleet in budgets
    for fleet in office_budgets['fleet'].unique():
        # Sum all amount_used for this fleet across all quarters
        fleet_budgets = office_budgets[office_budgets['fleet'] == fleet]
        total_spent = fleet_budgets['amount_used'].sum()

        # Count loans for this make (match make to fleet, case-insensitive)
        fleet_loans = office_loans[office_loans['make'].str.upper() == fleet.upper()]
        loan_count = len(fleet_loans)

        if loan_count > 0:
            avg_cost = total_spent / loan_count
            cost_per_make[fleet.upper()] = float(avg_cost)
            print(f"  {fleet}: ${avg_cost:.2f} per loan ({loan_count} loans, ${total_spent:.2f} total spent)")

    return cost_per_make


class RunRequest(BaseModel):
    office: str
    week_start: str
    seed: int = 42
    rank_weight: float = 1.0  # Partner Quality slider (0.0 - 2.0)
    geo_match: int = 100  # Local Priority slider (0 - 200)
    pub_rate: int = 150  # Publishing Success slider (0 - 300)
    engagement_priority: int = 50  # Engagement Priority slider (0-100: 0=dormant, 50=neutral, 100=momentum)
    max_per_partner_per_day: int = 1  # Max vehicles per partner per day (0=unlimited, 1=default)
    max_per_partner_per_week: int = 2  # Max vehicles per partner per week (0=unlimited, 2=default)
    prefer_normal_days: bool = False  # Prioritize Partner Normal Days toggle
    daily_capacities: Optional[Dict[str, int]] = None  # Daily capacity overrides from UI


@router.post("/run")
async def run_optimizer(request: RunRequest) -> Dict[str, Any]:
    """
    Run Phase 7 optimizer using all implemented constraints.
    Returns assignments with actual start days distributed across the week.
    """
    print(f"\n=== RUN OPTIMIZER CALLED ===")
    print(f"Request daily_capacities: {request.daily_capacities}")
    print(f"Request dict: {request.dict()}")

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

        # Override capacity with UI settings if provided
        print(f"DEBUG: daily_capacities from request: {request.daily_capacities}")
        if request.daily_capacities:
            print(f"DEBUG: Overriding capacities with UI values")
            week_start_date = pd.to_datetime(request.week_start)

            # Map day names to offsets: mon=0, tue=1, etc.
            day_offset_map = {
                'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3,
                'fri': 4, 'sat': 5, 'sun': 6
            }

            for day_key, capacity_value in request.daily_capacities.items():
                if day_key in day_offset_map:
                    day_offset = day_offset_map[day_key]
                    target_date = (week_start_date + timedelta(days=day_offset)).date()

                    if target_date in capacity_map:
                        old_value = capacity_map[target_date]
                        capacity_map[target_date] = capacity_value
                        print(f"  Override {day_key} ({target_date}) capacity from {old_value} to {capacity_value} slots")
                    else:
                        print(f"  Warning: {day_key} ({target_date}) not found in capacity_map")
                else:
                    print(f"  Warning: Unknown day key '{day_key}'")
        else:
            print(f"DEBUG: No daily_capacities override provided, using defaults")

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

        # 4a. Filter out partner-VIN combinations that already exist in current_activity
        # This prevents suggesting the same vehicle to the same partner twice in the same window
        if not current_activity_df.empty and not triples_post.empty:
            # Create set of existing (person_id, vin) pairs
            existing_pairs = set(
                zip(current_activity_df['person_id'], current_activity_df['vin'])
            )
            # Filter out triples that match existing pairs
            pre_filter_count = len(triples_post)
            triples_post = triples_post[
                ~triples_post.apply(
                    lambda row: (row['person_id'], row['vin']) in existing_pairs,
                    axis=1
                )
            ].copy()
            filtered_count = pre_filter_count - len(triples_post)
            if filtered_count > 0:
                print(f"  Filtered {filtered_count} triples with existing partner-VIN combinations")

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

        # 4c. Calculate recency scores (days since last loan)
        recency_df = compute_recency_scores(
            loan_history_df=loan_history_df,
            as_of_date=request.week_start
        )
        print(f"Recency scores calculated: {len(recency_df)} partner-make combinations")
        if not recency_df.empty:
            print(f"  Avg days since last loan: {recency_df['days_since_last_loan'].mean():.0f}")

        # 4d. Add scoring columns using the Phase 7 scoring function
        triples_post = add_score_to_triples(
            triples_df=triples_post,
            partners_df=partners_df,
            publication_df=publication_df
        )

        # 4e. Merge recency data into triples
        if not recency_df.empty:
            triples_post = triples_post.merge(
                recency_df[['person_id', 'make', 'days_since_last_loan']],
                on=['person_id', 'make'],
                how='left'
            )

        print(f"\n=== PRE-SOLVER DEBUG ===")
        print(f"Triples to solver: {len(triples_post)} rows")
        print(f"Columns in triples: {list(triples_post.columns)}")
        print(f"Sample triple: {triples_post.iloc[0].to_dict() if not triples_post.empty else 'EMPTY'}")

        # 5. Load budgets
        budgets_response = db.client.table('budgets').select('*').execute()
        budgets_df = pd.DataFrame(budgets_response.data) if budgets_response.data else pd.DataFrame()

        # Calculate actual cost per make from historical data
        cost_per_assignment = calculate_cost_per_make(budgets_df, loan_history_df, request.office)
        print(f"Calculated cost_per_assignment: {cost_per_assignment}")

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
            w_recency=abs(request.engagement_priority - 50) * 2,  # Weight magnitude (0-100, scaled from slider distance)
            engagement_mode=('dormant' if request.engagement_priority < 45 else
                           'momentum' if request.engagement_priority > 55 else
                           'neutral'),  # From Engagement Priority slider
            max_per_partner_per_day=request.max_per_partner_per_day,  # Max vehicles per partner per day
            max_per_partner_per_week=request.max_per_partner_per_week,  # Max vehicles per partner per week
            w_preferred_day=150 if request.prefer_normal_days else 0,  # Preferred Day toggle

            cost_per_assignment=cost_per_assignment,  # Actual costs from budget history
            solver_time_limit_s=30,  # Increased from 10s for 58k triples
            seed=request.seed,
            verbose=True,  # Enable to see what's happening
            db_client=db.client,  # Pass database client for querying current_activity
            capacity_map_override=capacity_map  # Pass the modified capacity map with UI overrides
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
        capacity_by_day = {'mon': 0, 'tue': 0, 'wed': 0, 'thu': 0, 'fri': 0, 'sat': 0, 'sun': 0}

        # Extract capacity from capacity_map
        week_start_date = pd.to_datetime(request.week_start)
        day_names = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
        for day_offset, day_name in enumerate(day_names):
            target_date = (week_start_date + timedelta(days=day_offset)).date()
            capacity_by_day[day_name] = capacity_map.get(target_date, 0)

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

        # Build comprehensive fairness summary from metrics
        fairness_summary = {
            'partners_assigned': fairness_metrics.get('partners_assigned', 0),
            'max_per_partner': fairness_metrics.get('max_concentration', 0),
            'partners_with_multiple': fairness_metrics.get('partners_with_multiple', 0),
            'gini': fairness_metrics.get('gini_coefficient', 0),
            'gini_coefficient': fairness_metrics.get('gini_coefficient', 0),
            'hhi': fairness_metrics.get('hhi', 0),
            'top_1_share': fairness_metrics.get('top_1_share', 0),
            'top_5_share': fairness_metrics.get('top_5_share', 0),
            'avg_assignments': fairness_metrics.get('avg_assignments', 0),
            'concentration_ratio': fairness_metrics.get('concentration_ratio', 0)
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

        # Budget summary - show ALL fleets from budgets table for current quarter
        # Determine quarter from week_start
        week_start_dt = datetime.strptime(request.week_start, '%Y-%m-%d')
        current_year = week_start_dt.year
        current_month = week_start_dt.month
        current_quarter = f'Q{((current_month - 1) // 3) + 1}'

        budget_fleets = {}
        budget_total = {'used': 0, 'budget': 0}

        # Get ALL budgets for this office and quarter
        quarter_budgets = budgets_df[
            (budgets_df['office'] == request.office) &
            (budgets_df['year'] == current_year) &
            (budgets_df['quarter'] == current_quarter)
        ]

        # Create a lookup for planned spend by fleet from solver results
        planned_by_fleet = {}
        budget_summary_df = solver_result.get('budget_summary', pd.DataFrame())
        if not budget_summary_df.empty:
            for _, row in budget_summary_df.iterrows():
                fleet = row.get('fleet', 'Unknown')
                planned_spend = float(row.get('planned_spend', 0))
                planned_by_fleet[fleet] = planned_spend

        # Build budget summary for ALL fleets in the quarter
        # Track totals separately for current, planned, and projected
        budget_total_current = 0
        budget_total_planned = 0

        for _, row in quarter_budgets.iterrows():
            fleet = row['fleet']
            current_used = float(row['amount_used']) if pd.notna(row['amount_used']) else 0
            budget_amount = float(row['budget_amount']) if pd.notna(row['budget_amount']) else 0
            planned_spend = planned_by_fleet.get(fleet, 0)

            budget_fleets[fleet] = {
                'current': int(current_used),
                'planned': int(planned_spend),
                'projected': int(current_used + planned_spend),
                'budget': int(budget_amount)
            }
            budget_total_current += int(current_used)
            budget_total_planned += int(planned_spend)
            budget_total['budget'] += int(budget_amount)

        # Set total with breakdown
        budget_total['current'] = budget_total_current
        budget_total['planned'] = budget_total_planned
        budget_total['projected'] = budget_total_current + budget_total_planned

        budget_summary = {
            'fleets': budget_fleets,
            'total': budget_total if budget_fleets else None
        }

        result = {
            'status': solver_result.get('meta', {}).get('solver_status', 'UNKNOWN'),
            'solve_time_ms': solver_result.get('timing', {}).get('wall_ms', 0),
            'assignments_count': len(assignments),
            'partners_used': len(set(a['person_id'] for a in assignments)) if assignments else 0,
            'assignments': assignments,
            'starts_by_day': starts_by_day,
            'capacity_by_day': capacity_by_day,  # Add capacity info for frontend
            # Pass through converted summaries
            'cap_summary': cap_summary,
            'fairness_summary': fairness_summary,
            'budget_summary': budget_summary,
            'objective_breakdown': solver_result.get('objective_breakdown', {})
        }

        # Save assignments to scheduled_assignments table for calendar view
        if assignments:
            import uuid
            run_id = str(uuid.uuid4())
            week_start_date = pd.to_datetime(request.week_start).date()

            # Delete ALL existing planned assignments for this office (not just this week)
            # This prevents clutter from old optimizer runs
            # Manual picks (status='manual') are preserved
            db.client.table('scheduled_assignments')\
                .delete()\
                .eq('office', request.office)\
                .eq('status', 'planned')\
                .execute()

            # Insert new assignments
            assignments_to_insert = []
            for assignment in selected_assignments:
                start_day = pd.to_datetime(assignment['start_day']).date()
                end_day = start_day + timedelta(days=7)

                assignments_to_insert.append({
                    'vin': assignment['vin'],
                    'person_id': int(assignment['person_id']),
                    'start_day': str(start_day),
                    'end_day': str(end_day),
                    'make': assignment['make'],
                    'model': assignment.get('model', ''),
                    'office': request.office,
                    'partner_name': partner_names.get(int(assignment['person_id']), f"Partner {assignment['person_id']}"),
                    'score': int(assignment.get('score', 0)),
                    'optimizer_run_id': run_id,
                    'week_start': str(week_start_date),
                    'status': 'planned'
                })

            if assignments_to_insert:
                db.client.table('scheduled_assignments').insert(assignments_to_insert).execute()

            result['optimizer_run_id'] = run_id

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await db.close()


@router.get("/vehicle-context/{vin}")
async def get_vehicle_context(vin: str) -> Dict[str, Any]:
    """
    Get context information for a specific vehicle including previous and next activities.
    """
    db = DatabaseService()
    await db.initialize()

    try:
        # Get current time for comparison
        now = datetime.now()

        # Load current and recent activities for this VIN
        activity_response = db.client.table('current_activity')\
            .select('*')\
            .eq('vehicle_vin', vin)\
            .order('start_date', desc=False)\
            .execute()

        activities_df = pd.DataFrame(activity_response.data) if activity_response.data else pd.DataFrame()

        # Load loan history for this VIN
        loan_response = db.client.table('loan_history')\
            .select('*')\
            .eq('vin', vin)\
            .order('start_date', desc=True)\
            .limit(10)\
            .execute()

        loans_df = pd.DataFrame(loan_response.data) if loan_response.data else pd.DataFrame()

        # Combine activities and loans into a timeline
        timeline = []

        # Add activities
        if not activities_df.empty:
            for _, activity in activities_df.iterrows():
                start = pd.to_datetime(activity.get('start_date'))
                end = pd.to_datetime(activity.get('end_date')) if pd.notna(activity.get('end_date')) else None

                timeline.append({
                    'type': 'activity',
                    'activity_type': activity.get('activity_type', 'Unknown'),
                    'start_date': start.isoformat() if pd.notna(start) else None,
                    'end_date': end.isoformat() if end else None,
                    'person_id': activity.get('person_id'),
                    'to_field': activity.get('to_field')
                })

        # Add loan history
        if not loans_df.empty:
            for _, loan in loans_df.iterrows():
                start = pd.to_datetime(loan.get('start_date'))
                end = pd.to_datetime(loan.get('end_date')) if pd.notna(loan.get('end_date')) else None

                timeline.append({
                    'type': 'loan',
                    'activity_type': 'Media Loan',
                    'start_date': start.isoformat() if pd.notna(start) else None,
                    'end_date': end.isoformat() if end else None,
                    'person_id': loan.get('person_id'),
                    'make': loan.get('make'),
                    'published': loan.get('published', False)
                })

        # Sort timeline by start date
        timeline.sort(key=lambda x: x['start_date'] if x['start_date'] else '9999-01-01')

        # Find previous and next activity relative to now
        previous_activity = None
        next_activity = None

        for item in timeline:
            start = pd.to_datetime(item['start_date']) if item['start_date'] else None
            end = pd.to_datetime(item['end_date']) if item['end_date'] else None

            if start and start < now:
                previous_activity = item
            elif start and start >= now and next_activity is None:
                next_activity = item

        # Get vehicle info
        vehicle_response = db.client.table('vehicles')\
            .select('*')\
            .eq('vin', vin)\
            .execute()

        vehicle_info = vehicle_response.data[0] if vehicle_response.data else {}

        # Format mileage
        current_mileage = vehicle_info.get('current_mileage')
        if current_mileage and pd.notna(current_mileage):
            mileage_str = f"{int(current_mileage):,} mi"
        else:
            mileage_str = 'N/A'

        # Determine last known location
        # Check if vehicle has current activity (active loan)
        if not activities_df.empty:
            # Find most recent activity with to_field
            recent_activity = activities_df[activities_df['to_field'].notna()].sort_values('start_date', ascending=False)

            if not recent_activity.empty:
                to_field = recent_activity.iloc[0]['to_field']

                # Look up partner info
                partner_response = db.client.table('media_partners')\
                    .select('*')\
                    .eq('person_id', to_field)\
                    .execute()

                if partner_response.data:
                    partner = partner_response.data[0]
                    partner_name = partner.get('name', f'Partner {to_field}')
                    partner_office = partner.get('office', 'Unknown')

                    # Check if activity is still active (end_date is None or in future)
                    end_date = recent_activity.iloc[0].get('end_date')
                    is_active = pd.isna(end_date) or pd.to_datetime(end_date) >= now

                    if is_active:
                        last_known_location = f"At {partner_name} ({partner_office})"
                        location_type = "active_loan"
                    else:
                        last_known_location = f"Last seen at {partner_name} ({partner_office})"
                        location_type = "last_partner"
                else:
                    last_known_location = f"Unknown partner location"
                    location_type = "unknown"
            else:
                # No to_field in activities, assume at home office
                last_known_location = f"Home Office ({vehicle_info.get('office', 'Unknown')})"
                location_type = "home_office"
        else:
            # No activities found, assume at home office
            last_known_location = f"Home Office ({vehicle_info.get('office', 'Unknown')})"
            location_type = "home_office"

        return {
            'vin': vin,
            'make': vehicle_info.get('make'),
            'model': vehicle_info.get('model'),
            'office': vehicle_info.get('office'),
            'mileage': mileage_str,
            'last_known_location': last_known_location,
            'location_type': location_type,
            'previous_activity': previous_activity,
            'next_activity': next_activity,
            'timeline': timeline
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
        week_end_date = week_start_date + timedelta(days=6)
        week_end_str = week_end_date.strftime('%Y-%m-%d')

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

        # 3. Load current activity WITH PAGINATION (filter to this week, then filter by office via vehicle)
        all_activity = []
        offset = 0
        limit = 1000
        while True:
            activity_response = db.client.table('current_activity')\
                .select('*')\
                .gte('start_date', week_start)\
                .lte('start_date', week_end_str)\
                .range(offset, offset + limit - 1)\
                .execute()
            if not activity_response.data:
                break
            all_activity.extend(activity_response.data)
            if len(activity_response.data) < limit:
                break
            offset += limit

        current_activity_df = pd.DataFrame(all_activity) if all_activity else pd.DataFrame()

        # Filter to this office by joining with vehicles
        if not current_activity_df.empty and not vehicles_df.empty:
            # Create a mapping of VIN to office from vehicles
            vin_to_office = dict(zip(vehicles_df['vin'], vehicles_df['office']))

            # Add office column to current_activity
            vin_col = 'vehicle_vin' if 'vehicle_vin' in current_activity_df.columns else 'vin'
            current_activity_df['office'] = current_activity_df[vin_col].map(vin_to_office)

            # Filter to this office
            current_activity_df = current_activity_df[current_activity_df['office'] == office].copy()

        logger.info(f"Loaded {len(current_activity_df)} current activities for {office} week starting {week_start}")

        # Rename column to match expected format
        if 'vehicle_vin' in current_activity_df.columns:
            current_activity_df = current_activity_df.rename(columns={'vehicle_vin': 'vin'})

        # Load scheduled assignments ONLY with status='manual' (Chain Builder real picks)
        # Exclude status='planned' (optimizer suggestions - those are just recommendations, don't reduce capacity)
        manual_scheduled_response = db.client.table('scheduled_assignments')\
            .select('*')\
            .eq('office', office)\
            .eq('status', 'manual')\
            .gte('start_day', week_start)\
            .lte('start_day', week_end_str)\
            .execute()
        manual_scheduled_df = pd.DataFrame(manual_scheduled_response.data) if manual_scheduled_response.data else pd.DataFrame()

        logger.info(f"Found {len(manual_scheduled_df)} manual assignments (Chain Builder) for {office} week starting {week_start}")

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

        # 8b. Count already-scheduled activities per day (current_activity + scheduled_assignments)
        existing_by_day = {'mon': 0, 'tue': 0, 'wed': 0, 'thu': 0, 'fri': 0, 'sat': 0, 'sun': 0}

        # Count current activities that START in this week AND match this office
        if not current_activity_df.empty and 'start_date' in current_activity_df.columns:
            # Filter to this office if office column exists
            office_activity_df = current_activity_df
            if 'office' in current_activity_df.columns:
                office_activity_df = current_activity_df[current_activity_df['office'] == office]

            for _, activity in office_activity_df.iterrows():
                try:
                    start_date_str = activity['start_date']
                    if pd.isna(start_date_str):
                        continue

                    # Parse start date
                    if isinstance(start_date_str, str):
                        start_dt = pd.to_datetime(start_date_str).date()
                    else:
                        start_dt = pd.to_datetime(start_date_str).date()

                    # Check if it's in this week
                    days_diff = (start_dt - week_start_date.date()).days
                    if 0 <= days_diff < 7:
                        day_key = days_map[days_diff]
                        existing_by_day[day_key] += 1
                except Exception as e:
                    continue  # Skip malformed dates

            logger.info(f"Current activity starts this week: {existing_by_day}")

        # Count manual scheduled assignments that START in this week (already filtered by query above)
        if not manual_scheduled_df.empty and 'start_day' in manual_scheduled_df.columns:
            for _, assignment in manual_scheduled_df.iterrows():
                try:
                    start_date_str = assignment['start_day']
                    if pd.isna(start_date_str):
                        continue

                    # Parse start date
                    if isinstance(start_date_str, str):
                        start_dt = pd.to_datetime(start_date_str).date()
                    else:
                        start_dt = pd.to_datetime(start_date_str).date()

                    # Check if it's in this week (should always be true due to query filter, but double-check)
                    days_diff = (start_dt - week_start_date.date()).days
                    if 0 <= days_diff < 7:
                        day_key = days_map[days_diff]
                        existing_by_day[day_key] += 1
                except Exception as e:
                    continue  # Skip malformed dates

            logger.info(f"Scheduled assignments starts this week: {existing_by_day}")
            logger.info(f"Total existing schedule breakdown: {existing_by_day}")

        # 9. Load budget status for current quarter and YTD
        budgets_response = db.client.table('budgets').select('*').eq('office', office).execute()
        budgets_df = pd.DataFrame(budgets_response.data) if budgets_response.data else pd.DataFrame()

        # Determine quarter from week_start
        week_start_dt = datetime.strptime(week_start, '%Y-%m-%d')
        current_year = week_start_dt.year
        current_month = week_start_dt.month
        current_quarter = f'Q{((current_month - 1) // 3) + 1}'

        # Build budget summary by fleet
        budget_by_fleet = {}
        ytd_totals = {'budget': 0, 'used': 0}
        current_quarter_totals = {'budget': 0, 'used': 0}

        if not budgets_df.empty:
            # Filter to current year
            year_budgets = budgets_df[budgets_df['year'] == current_year]

            for fleet in year_budgets['fleet'].unique():
                fleet_budgets = year_budgets[year_budgets['fleet'] == fleet]

                # YTD totals
                ytd_budget = fleet_budgets['budget_amount'].sum()
                ytd_used = fleet_budgets['amount_used'].sum()

                # Current quarter
                quarter_budgets = fleet_budgets[fleet_budgets['quarter'] == current_quarter]
                q_budget = quarter_budgets['budget_amount'].sum() if not quarter_budgets.empty else 0
                q_used = quarter_budgets['amount_used'].sum() if not quarter_budgets.empty else 0

                budget_by_fleet[fleet] = {
                    'ytd_budget': float(ytd_budget),
                    'ytd_used': float(ytd_used),
                    'ytd_remaining': float(ytd_budget - ytd_used),
                    'current_quarter': current_quarter,
                    'quarter_budget': float(q_budget),
                    'quarter_used': float(q_used),
                    'quarter_remaining': float(q_budget - q_used)
                }

                ytd_totals['budget'] += ytd_budget
                ytd_totals['used'] += ytd_used
                current_quarter_totals['budget'] += q_budget
                current_quarter_totals['used'] += q_used

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
            "capacity": capacity,
            "existing_schedule": existing_by_day,  # Already-scheduled count per day
            "budget_status": {
                "year": current_year,
                "current_quarter": current_quarter,
                "by_fleet": budget_by_fleet,
                "ytd_totals": {
                    'budget': float(ytd_totals['budget']),
                    'used': float(ytd_totals['used']),
                    'remaining': float(ytd_totals['budget'] - ytd_totals['used'])
                },
                "quarter_totals": {
                    'budget': float(current_quarter_totals['budget']),
                    'used': float(current_quarter_totals['used']),
                    'remaining': float(current_quarter_totals['budget'] - current_quarter_totals['used'])
                }
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await db.close()

@router.delete("/clear-optimizer-suggestions")
async def clear_optimizer_suggestions(
    office: str = Query(..., description="Office name")
) -> Dict[str, Any]:
    """
    Clear all optimizer suggestions (status='planned') for a specific office.

    This removes green bars from the calendar that were generated by previous
    optimizer runs. Does NOT remove manual assignments (status='manual').
    """
    db = DatabaseService()
    await db.initialize()

    try:
        # Delete all planned assignments for this office
        result = db.client.table('scheduled_assignments')\
            .delete()\
            .eq('office', office)\
            .eq('status', 'planned')\
            .execute()

        deleted_count = len(result.data) if result.data else 0

        logger.info(f"Cleared {deleted_count} optimizer suggestions for {office}")

        return {
            "success": True,
            "message": f"Cleared {deleted_count} optimizer suggestions for {office}",
            "deleted_count": deleted_count
        }

    except Exception as e:
        logger.error(f"Error clearing optimizer suggestions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        await db.close()


@router.get("/office-default-capacity")
async def get_office_default_capacity(
    office: str = Query(..., description="Office name")
) -> Dict[str, Any]:
    """
    Get the default daily capacity for a specific office from ops_capacity table.

    Returns default drivers_per_day which represents weekday capacity.
    Weekend capacity defaults to 0.
    """
    db = DatabaseService()
    await db.initialize()

    try:
        # Get office's default capacity
        capacity_response = db.client.table('ops_capacity')\
            .select('*')\
            .eq('office', office)\
            .execute()

        if not capacity_response.data or len(capacity_response.data) == 0:
            # Return sensible defaults if office not found
            return {
                "office": office,
                "daily_capacities": {
                    "mon": 15,
                    "tue": 15,
                    "wed": 15,
                    "thu": 15,
                    "fri": 15,
                    "sat": 0,
                    "sun": 0
                },
                "default_found": False
            }

        office_data = capacity_response.data[0]
        drivers_per_day = office_data.get('drivers_per_day', 15)

        return {
            "office": office,
            "daily_capacities": {
                "mon": drivers_per_day,
                "tue": drivers_per_day,
                "wed": drivers_per_day,
                "thu": drivers_per_day,
                "fri": drivers_per_day,
                "sat": 0,  # Weekends default to 0
                "sun": 0
            },
            "default_found": True,
            "drivers_per_day": drivers_per_day
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await db.close()

@router.get("/partner-distance")
async def get_partner_distance(
    person_id: int = Query(..., description="Partner person_id"),
    office: str = Query(..., description="Office name")
) -> Dict[str, Any]:
    """
    Calculate distance from partner to office using cached lat/lon from media_partners table.

    Returns distance in miles and location type (local/remote).
    """
    db = DatabaseService()
    await db.initialize()

    try:
        # Get office coordinates
        office_response = db.client.table('offices').select('latitude, longitude').eq('name', office).execute()

        if not office_response.data or len(office_response.data) == 0:
            raise HTTPException(status_code=404, detail=f"Office '{office}' not found")

        office_data = office_response.data[0]
        office_lat = office_data['latitude']
        office_lon = office_data['longitude']

        if not office_lat or not office_lon:
            raise HTTPException(status_code=400, detail=f"Office '{office}' does not have coordinates")

        # Get partner coordinates from media_partners table
        partner_response = db.client.table('media_partners')\
            .select('latitude, longitude')\
            .eq('person_id', person_id)\
            .eq('office', office)\
            .execute()

        if not partner_response.data or len(partner_response.data) == 0:
            return {
                "success": False,
                "message": "Partner not found in media_partners table"
            }

        partner_data = partner_response.data[0]
        partner_lat = partner_data.get('latitude')
        partner_lon = partner_data.get('longitude')

        if not partner_lat or not partner_lon:
            return {
                "success": False,
                "message": "Partner does not have cached coordinates. Please re-ingest media_partners to geocode."
            }

        # Calculate distance using Haversine formula
        from ..utils.geocoding import calculate_distance

        distance = calculate_distance(office_lat, office_lon, partner_lat, partner_lon)
        location_type = 'local' if distance < 50 else 'remote'

        return {
            "success": True,
            "distance_miles": round(distance, 1),
            "location_type": location_type,
            "partner_latitude": partner_lat,
            "partner_longitude": partner_lon
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await db.close()


@router.get("/vehicle-chains/{vin}")
async def get_vehicle_chaining_opportunities(
    vin: str,
    office: str = Query(..., description="Office name"),
    max_distance: float = Query(50, description="Maximum distance in miles for chaining candidates")
) -> Dict[str, Any]:
    """
    Get nearby partner chaining opportunities for a vehicle currently on loan.

    Returns partners within max_distance from the vehicle's current location,
    filtered by approved makes and sorted by distance.
    """
    db = DatabaseService()
    await db.initialize()

    try:
        # 1. Find vehicle's current location (which partner they're with)
        activity_response = db.client.table('current_activity')\
            .select('*')\
            .eq('vehicle_vin', vin)\
            .order('start_date', desc=True)\
            .limit(1)\
            .execute()

        if not activity_response.data or len(activity_response.data) == 0:
            return {
                "success": False,
                "message": "Vehicle has no current activity - cannot determine location for chaining"
            }

        current_activity = activity_response.data[0]
        current_partner_id = current_activity.get('person_id') or current_activity.get('to_field')

        if not current_partner_id:
            return {
                "success": False,
                "message": "Cannot determine current partner location"
            }

        # 2. Get current partner's coordinates
        current_partner_response = db.client.table('media_partners')\
            .select('*')\
            .eq('person_id', current_partner_id)\
            .eq('office', office)\
            .execute()

        if not current_partner_response.data:
            return {
                "success": False,
                "message": "Current partner not found"
            }

        current_partner = current_partner_response.data[0]
        current_lat = current_partner.get('latitude')
        current_lon = current_partner.get('longitude')

        if not current_lat or not current_lon:
            return {
                "success": False,
                "message": "Current partner does not have coordinates - cannot calculate chaining distances"
            }

        # 3. Get vehicle make to filter approved partners
        vehicle_response = db.client.table('vehicles')\
            .select('make')\
            .eq('vin', vin)\
            .execute()

        if not vehicle_response.data:
            return {
                "success": False,
                "message": "Vehicle not found"
            }

        vehicle_make = vehicle_response.data[0]['make']

        # 4. Get all partners for this office with approved make
        approved_response = db.client.table('approved_makes')\
            .select('person_id')\
            .eq('make', vehicle_make)\
            .execute()

        if not approved_response.data:
            return {
                "success": True,
                "message": f"No partners approved for {vehicle_make}",
                "current_partner": {
                    "person_id": current_partner_id,
                    "name": current_partner.get('name'),
                    "latitude": current_lat,
                    "longitude": current_lon
                },
                "nearby_partners": []
            }

        approved_partner_ids = [row['person_id'] for row in approved_response.data]

        # 5. Get all partners in office with coordinates
        partners_response = db.client.table('media_partners')\
            .select('*')\
            .eq('office', office)\
            .execute()

        if not partners_response.data:
            return {
                "success": True,
                "current_partner": {
                    "person_id": current_partner_id,
                    "name": current_partner.get('name'),
                    "latitude": current_lat,
                    "longitude": current_lon
                },
                "nearby_partners": []
            }

        # 6. Calculate distances to all approved partners with coordinates
        from ..utils.geocoding import calculate_distance

        nearby_partners = []
        for partner in partners_response.data:
            # Skip current partner
            if partner['person_id'] == current_partner_id:
                continue

            # Only include approved partners
            if partner['person_id'] not in approved_partner_ids:
                continue

            partner_lat = partner.get('latitude')
            partner_lon = partner.get('longitude')

            if not partner_lat or not partner_lon:
                continue

            # Calculate distance from current location
            distance = calculate_distance(current_lat, current_lon, partner_lat, partner_lon)

            # Filter by max distance
            if distance <= max_distance:
                nearby_partners.append({
                    "person_id": partner['person_id'],
                    "name": partner['name'],
                    "distance_miles": round(distance, 1),
                    "latitude": partner_lat,
                    "longitude": partner_lon,
                    "region": partner.get('region'),
                    "address": partner.get('address')
                })

        # Sort by distance
        nearby_partners.sort(key=lambda x: x['distance_miles'])

        return {
            "success": True,
            "vehicle_make": vehicle_make,
            "current_partner": {
                "person_id": current_partner_id,
                "name": current_partner.get('name'),
                "latitude": current_lat,
                "longitude": current_lon
            },
            "nearby_partners": nearby_partners[:10]  # Limit to top 10 nearest
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await db.close()


@router.get("/partner-day-candidates")
async def get_partner_day_candidates(
    person_id: int = Query(..., description="Partner person_id"),
    date: str = Query(..., description="Target date (YYYY-MM-DD)"),
    office: str = Query(..., description="Office name")
) -> Dict[str, Any]:
    """
    Get top vehicle candidates for a specific partner on a specific day.

    Returns ranked list of vehicles with scores, distances, and availability.
    Used by Partner Scheduling UI to show "best matches" for manual scheduling.
    """
    db = DatabaseService()
    await db.initialize()

    try:
        target_date = pd.to_datetime(date).date()

        # 1. Get partner info
        partner_response = db.client.table('media_partners')\
            .select('*')\
            .eq('person_id', person_id)\
            .eq('office', office)\
            .execute()

        if not partner_response.data:
            raise HTTPException(status_code=404, detail="Partner not found")

        partner = partner_response.data[0]

        # 2. Get vehicles for office
        vehicles_response = db.client.table('vehicles')\
            .select('*')\
            .eq('office', office)\
            .execute()

        if not vehicles_response.data:
            return {
                "success": True,
                "partner": partner,
                "candidates": [],
                "message": "No vehicles available for this office"
            }

        vehicles_df = pd.DataFrame(vehicles_response.data)

        # Convert lifecycle date columns (required by build_availability_grid)
        for date_col in ['in_service_date', 'expected_turn_in_date']:
            if date_col in vehicles_df.columns:
                vehicles_df[date_col] = pd.to_datetime(vehicles_df[date_col], errors='coerce').dt.date

        # Calculate week_start (Monday of the target date's week)
        week_start = target_date - timedelta(days=target_date.weekday())
        week_end = week_start + timedelta(days=6)
        week_start_str = week_start.strftime('%Y-%m-%d')

        # 3. Get current activity for availability check
        active_response = db.client.table('current_activity')\
            .select('*')\
            .execute()

        if active_response.data:
            activity_df = pd.DataFrame(active_response.data)
            # Map vehicle_vin to vin for compatibility
            if 'vehicle_vin' in activity_df.columns:
                activity_df['vin'] = activity_df['vehicle_vin']
            # Convert date columns
            for date_col in ['start_date', 'end_date']:
                if date_col in activity_df.columns:
                    activity_df[date_col] = pd.to_datetime(activity_df[date_col], errors='coerce').dt.date
        else:
            activity_df = pd.DataFrame()

        # 4. Use SAME availability logic as optimizer
        availability_df = build_availability_grid(
            vehicles_df=vehicles_df,
            activity_df=activity_df,
            week_start=week_start_str,
            office=office
        )

        # Filter to vehicles available on target date
        available_on_target = availability_df[
            (availability_df['day'] == target_date) &
            (availability_df['available'] == True)
        ]

        if available_on_target.empty:
            return {
                "success": True,
                "partner": partner,
                "candidates": [],
                "message": "No vehicles available on this date"
            }

        available_vins = available_on_target['vin'].tolist()

        # 5. Get approved makes for this partner
        approved_response = db.client.table('approved_makes')\
            .select('*')\
            .eq('person_id', person_id)\
            .execute()

        if not approved_response.data:
            return {
                "success": True,
                "partner": partner,
                "candidates": [],
                "message": "Partner has no approved makes"
            }

        approved_makes = [row['make'] for row in approved_response.data]
        approved_df = pd.DataFrame(approved_response.data)

        # Filter to vehicles that are both available AND approved for this partner
        available_vehicles = vehicles_df[
            (vehicles_df['vin'].isin(available_vins)) &
            (vehicles_df['make'].isin(approved_makes))
        ].copy()

        if available_vehicles.empty:
            return {
                "success": True,
                "partner": partner,
                "candidates": [],
                "message": "No available vehicles match partner's approved makes"
            }

        # 5. Calculate scores
        rank_map = {}
        for row in approved_response.data:
            rank_map[row['make']] = row.get('rank', 3)

        available_vehicles['rank'] = available_vehicles['make'].map(rank_map).fillna('C')

        # Base score from rank (handle both numeric and letter ranks)
        def get_rank_score(rank):
            if pd.isna(rank):
                return 250
            rank_str = str(rank).upper()
            if rank_str.startswith('A'):
                return 1000
            elif rank_str in ['B', 'TB', '2']:
                return 500
            elif rank_str in ['C', 'TC', '3']:
                return 250
            elif rank_str in ['D', 'TD', '4']:
                return 100
            return 250

        available_vehicles['base_score'] = available_vehicles['rank'].apply(get_rank_score)

        # 6. Get partner publication rate
        loan_history_response = db.client.table('loan_history')\
            .select('*')\
            .eq('person_id', person_id)\
            .execute()

        publication_rate = 0.5
        if loan_history_response.data:
            history_df = pd.DataFrame(loan_history_response.data)
            if 'clips_received' in history_df.columns:
                published = history_df['clips_received'].apply(lambda x: str(x) == '1.0' if pd.notna(x) else False).sum()
                total = len(history_df)
                publication_rate = published / total if total > 0 else 0.5

        # Add publication bonus
        available_vehicles['pub_bonus'] = int(publication_rate * 200)

        # Final score
        available_vehicles['score'] = (
            available_vehicles['base_score'] +
            available_vehicles['pub_bonus']
        )

        # Get vehicle history (recent loans)
        all_vins = available_vehicles['vin'].tolist()
        vehicle_history_response = db.client.table('loan_history')\
            .select('vin, person_id, start_date, end_date, clips_received')\
            .in_('vin', all_vins)\
            .order('start_date', desc=True)\
            .limit(100)\
            .execute()

        vehicle_history_map = {}
        if vehicle_history_response.data:
            history_df = pd.DataFrame(vehicle_history_response.data)
            for vin in all_vins:
                vin_history = history_df[history_df['vin'] == vin].head(3)  # Last 3 loans
                if not vin_history.empty:
                    vehicle_history_map[vin] = vin_history.to_dict('records')

        # Sort and format
        available_vehicles = available_vehicles.sort_values('score', ascending=False)

        # Get all approved_makes to calculate competition (no office filter - approved_makes doesn't have office column)
        all_approved_response = db.client.table('approved_makes')\
            .select('*')\
            .execute()

        all_approved_df = pd.DataFrame(all_approved_response.data) if all_approved_response.data else pd.DataFrame()

        # Get partner's current week assignments to calculate weekly count
        current_assignments_response = db.client.table('scheduled_assignments')\
            .select('*')\
            .eq('person_id', person_id)\
            .eq('office', office)\
            .gte('start_day', str(week_start))\
            .lte('start_day', str(week_end))\
            .execute()

        partner_weekly_count = len(current_assignments_response.data) if current_assignments_response.data else 0

        # Get week's tier slot usage
        week_assignments_response = db.client.table('scheduled_assignments')\
            .select('vin')\
            .eq('office', office)\
            .gte('start_day', str(week_start))\
            .lte('start_day', str(week_end))\
            .execute()

        week_vins = [a['vin'] for a in week_assignments_response.data] if week_assignments_response.data else []
        week_vehicles = vehicles_df[vehicles_df['vin'].isin(week_vins)] if week_vins else pd.DataFrame()

        # Count tier usage
        tier_counts = {}
        if not week_vehicles.empty:
            for make in week_vehicles['make'].unique():
                make_approved = all_approved_df[all_approved_df['make'] == make]
                if not make_approved.empty:
                    rank = make_approved.iloc[0].get('rank', 'C')
                    tier_counts[rank] = tier_counts.get(rank, 0) + 1

        # Get partner's historical make performance
        make_performance = {}
        if loan_history_response.data:
            history_df = pd.DataFrame(loan_history_response.data)
            if 'make' in history_df.columns and 'clips_received' in history_df.columns:
                for make in history_df['make'].unique():
                    make_loans = history_df[history_df['make'] == make]
                    published = make_loans['clips_received'].apply(
                        lambda x: str(x) == '1.0' if pd.notna(x) else False
                    ).sum()
                    total = len(make_loans)
                    make_performance[make] = round(published / total, 2) if total > 0 else 0

        candidates = []
        for idx, vehicle in available_vehicles.head(20).iterrows():
            # Calculate competition (how many other partners approved for this make)
            vehicle_make = vehicle['make']
            competition_count = 0
            if not all_approved_df.empty:
                make_approvals = all_approved_df[all_approved_df['make'] == vehicle_make]
                competition_count = len(make_approvals['person_id'].unique()) - 1  # Exclude this partner

            # Determine if exclusive
            is_exclusive = competition_count == 0

            # Get make-specific publication rate
            make_pub_rate = make_performance.get(vehicle_make, publication_rate)

            # Build recommendation reasoning - ONLY show UNIQUE/MEANINGFUL info
            reasons = []
            badge = None

            if is_exclusive:
                reasons.append(f"Exclusive to this partner")
                badge = "EXCLUSIVE"
            elif idx == 0:
                badge = "TOP PICK"
            elif idx == 1:
                badge = "STRONG ALTERNATIVE"

            # Only show competition if it's VERY LOW (under 5 = rare opportunity)
            if competition_count == 0:
                badge = "EXCLUSIVE"
                reasons.append(f"No other partners eligible")
            elif competition_count > 0 and competition_count < 5:
                reasons.append(f"Limited competition ({competition_count} partners)")

            # Show make preference ONLY if significantly different from overall rate
            # (i.e., partner performs BETTER with this make than their average)
            if make_pub_rate > publication_rate + 0.15:  # 15% better than average
                reasons.append(f"Partner excels with {vehicle_make} ({int(make_pub_rate * 100)}% vs {int(publication_rate * 100)}% avg)")

            # If still no reasons, just leave it empty - the score/tier speaks for itself

            # Impact analysis
            vehicle_rank = vehicle.get('rank', 'C')
            tier_used = tier_counts.get(vehicle_rank, 0)

            impact_warnings = []
            if partner_weekly_count >= 2:
                impact_warnings.append("Partner at weekly limit (2/2)")
            elif partner_weekly_count == 1:
                impact_warnings.append("Will reach weekly limit (2/2)")

            if vehicle_rank in ['A+', 'A'] and tier_used >= 8:
                impact_warnings.append(f"High {vehicle_rank}-tier usage this week")

            # Get vehicle history for this VIN
            vin_history = vehicle_history_map.get(vehicle['vin'], [])
            history_summary = None
            if vin_history:
                total_loans = len(vin_history)
                published = sum(1 for h in vin_history if str(h.get('clips_received')) == '1.0')
                pub_rate = published / total_loans if total_loans > 0 else 0
                last_loan = vin_history[0] if vin_history else None
                history_summary = {
                    'total_loans': total_loans,
                    'published': published,
                    'pub_rate': pub_rate,
                    'last_loan_date': last_loan.get('start_date') if last_loan else None
                }

            candidates.append({
                'vin': vehicle['vin'],
                'make': vehicle['make'],
                'model': vehicle.get('model', ''),
                'year': vehicle.get('year'),
                'rank': vehicle.get('rank', 'C'),
                'score': int(vehicle['score']),
                'base_score': int(vehicle['base_score']),
                'pub_bonus': int(vehicle['pub_bonus']),
                'availability': 'Available on ' + date,
                'competition_count': competition_count,
                'is_exclusive': is_exclusive,
                'badge': badge,
                'reasons': reasons,
                'make_pub_rate': make_pub_rate,
                'impact_warnings': impact_warnings,
                'history': history_summary
            })

        return {
            "success": True,
            "partner": {
                "person_id": partner['person_id'],
                "name": partner['name'],
                "office": partner['office'],
                "address": partner.get('address'),
                "region": partner.get('region'),
                "publication_rate": round(publication_rate, 2)
            },
            "target_date": date,
            "candidates": candidates,
            "total_available": len(available_vehicles),
            "partner_insights": {
                "weekly_count": partner_weekly_count,
                "weekly_limit": 2,
                "publication_rate": round(publication_rate, 2),
                "make_performance": make_performance,
                "tier_usage": tier_counts
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await db.close()


@router.get("/partner-intelligence")
async def get_partner_intelligence(
    person_id: int = Query(..., description="Partner person_id"),
    office: str = Query(..., description="Office name")
) -> Dict[str, Any]:
    """
    Get comprehensive intelligence data for a specific partner.

    Returns:
    - Partner stats (publication rate, total loans, last loan date, cooldown status)
    - Approved makes with ranks
    - Recent loan history (last 10 loans)
    - Scheduled assignments (upcoming calendar)
    - Current active loans
    """
    db = DatabaseService()
    await db.initialize()

    try:
        # 1. Get partner info
        partner_response = db.client.table('media_partners')\
            .select('*')\
            .eq('person_id', person_id)\
            .eq('office', office)\
            .execute()

        if not partner_response.data:
            raise HTTPException(status_code=404, detail="Partner not found")

        partner = partner_response.data[0]

        # 2. Get loan history for stats
        loan_history_response = db.client.table('loan_history')\
            .select('*')\
            .eq('person_id', person_id)\
            .order('start_date', desc=True)\
            .limit(100)\
            .execute()

        loan_history_df = pd.DataFrame(loan_history_response.data) if loan_history_response.data else pd.DataFrame()

        # Calculate stats
        total_loans = len(loan_history_df)
        publication_rate = 0.0
        avg_clips = 0.0
        last_loan_date = None

        if not loan_history_df.empty:
            # Publication rate
            if 'clips_received' in loan_history_df.columns:
                published = loan_history_df['clips_received'].apply(
                    lambda x: str(x) == '1.0' if pd.notna(x) else False
                ).sum()
                publication_rate = published / total_loans if total_loans > 0 else 0.0

            # Last loan date
            if 'end_date' in loan_history_df.columns:
                last_end = pd.to_datetime(loan_history_df['end_date']).max()
                if pd.notna(last_end):
                    last_loan_date = last_end.date()

        # 3. Get approved makes
        approved_response = db.client.table('approved_makes')\
            .select('*')\
            .eq('person_id', person_id)\
            .execute()

        approved_makes = []
        if approved_response.data:
            for row in approved_response.data:
                approved_makes.append({
                    'make': row['make'],
                    'rank': row.get('rank', 3)
                })

        # Sort by rank
        approved_makes.sort(key=lambda x: x['rank'])

        # 4. Get recent loan history (last 6 months) with full vehicle details
        recent_loans = []
        if not loan_history_df.empty and len(loan_history_df) > 0:
            # Filter to last 6 months
            six_months_ago = datetime.now().date() - timedelta(days=180)
            recent_df = loan_history_df[
                pd.to_datetime(loan_history_df['start_date']) >= pd.Timestamp(six_months_ago)
            ]

            for _, loan in recent_df.head(10).iterrows():
                published = False
                if 'clips_received' in loan and pd.notna(loan['clips_received']):
                    published = str(loan['clips_received']) == '1.0'

                recent_loans.append({
                    'vin': loan.get('vin') if pd.notna(loan.get('vin')) else None,
                    'make': loan.get('make'),
                    'model': loan.get('model') if pd.notna(loan.get('model')) else None,
                    'start_date': str(loan.get('start_date')) if pd.notna(loan.get('start_date')) else None,
                    'end_date': str(loan.get('end_date')) if pd.notna(loan.get('end_date')) else None,
                    'published': published,
                    'clips_count': int(loan.get('clips_count', 0)) if pd.notna(loan.get('clips_count')) else 0
                })

        # 5. Get scheduled assignments (upcoming)
        today = datetime.now().date()
        scheduled_response = db.client.table('scheduled_assignments')\
            .select('*')\
            .eq('person_id', person_id)\
            .eq('office', office)\
            .gte('start_day', str(today))\
            .order('start_day')\
            .execute()

        upcoming_assignments = []
        if scheduled_response.data:
            for assignment in scheduled_response.data:
                upcoming_assignments.append({
                    'assignment_id': assignment.get('assignment_id'),
                    'vin': assignment['vin'],
                    'make': assignment.get('make'),
                    'model': assignment.get('model'),
                    'year': assignment.get('year'),
                    'start_day': assignment['start_day'],
                    'end_day': assignment['end_day'],
                    'status': assignment.get('status', 'planned'),  # Default to 'planned' if not set
                    'score': assignment.get('score', 0)
                })

        # 6. Get current active loans with vehicle details
        # Use > instead of >= to exclude loans that ended yesterday or earlier
        active_response = db.client.table('current_activity')\
            .select('*')\
            .eq('person_id', person_id)\
            .gt('end_date', str(today))\
            .execute()

        current_loans = []
        if active_response.data:
            for activity in active_response.data:
                # Get vehicle make/model from vehicles table
                vin = activity.get('vehicle_vin')
                make, model = None, None
                if vin:
                    try:
                        vehicle_response = db.client.table('vehicles')\
                            .select('make, model')\
                            .eq('vin', vin)\
                            .execute()
                        if vehicle_response.data:
                            make = vehicle_response.data[0].get('make')
                            model = vehicle_response.data[0].get('model')
                    except Exception as e:
                        logger.warning(f"Could not fetch vehicle details for VIN {vin}: {e}")

                current_loans.append({
                    'vehicle_vin': vin,
                    'make': make,
                    'model': model,
                    'start_date': activity.get('start_date'),
                    'end_date': activity.get('end_date')
                })

        return {
            "success": True,
            "partner": {
                "person_id": partner['person_id'],
                "name": partner['name'],
                "office": partner['office'],
                "address": partner.get('address')
            },
            "stats": {
                "total_loans": total_loans,
                "publication_rate": round(publication_rate, 3),
                "avg_clips": round(avg_clips, 2),
                "last_loan_date": str(last_loan_date) if last_loan_date else None
            },
            "approved_makes": approved_makes,
            "recent_loans": recent_loans,
            "upcoming_assignments": upcoming_assignments,
            "current_loans": current_loans
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await db.close()
