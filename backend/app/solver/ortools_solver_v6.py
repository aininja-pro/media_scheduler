"""
Phase 7.2 + 7.4s + 7.5 + 7.6 + 7.7 + 7.8: Complete OR-Tools Solver

Includes all constraints:
- VIN uniqueness (7.2) - HARD
- Daily capacity (7.2/7.7) - HARD (with dynamic day-specific slots)
- Cooldown filtering (7.3) - HARD (pre-filter)
- Soft tier caps (7.4s) - SOFT
- Distribution fairness (7.5) - SOFT
- Quarterly budgets (7.6) - SOFT/HARD
- Objective shaping (7.8) - Configurable weights

"Price the tradeoff by default; forbid only when policy demands." - Naval
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from ortools.sat.python import cp_model
import time

# Import all constraint modules
from app.solver.tier_caps_soft import (
    add_soft_tier_cap_penalties,
    build_cap_summary_soft,
    DEFAULT_LAMBDA_CAP
)

from app.solver.fairness_penalties import (
    add_fairness_penalties,
    build_fairness_summary,
    get_fairness_metrics,
    DEFAULT_FAIR_TARGET,
    DEFAULT_LAMBDA_FAIR
)

from app.solver.budget_constraints import (
    add_budget_constraints,
    build_budget_summary,
    normalize_fleet_name,
    DEFAULT_POINTS_PER_DOLLAR,
    DEFAULT_COST_PER_ASSIGNMENT
)

from app.solver.dynamic_capacity import (
    load_capacity_calendar,
    identify_special_days,
    build_capacity_report,
    validate_capacity_compliance
)

from app.solver.objective_shaping import (
    apply_objective_shaping,
    build_shaping_breakdown,
    DEFAULT_W_RANK,
    DEFAULT_W_GEO,
    DEFAULT_W_PUB,
    DEFAULT_W_RECENCY
)

from app.solver.ortools_solver_v2 import add_score_to_triples


def solve_with_all_constraints(
    triples_df: pd.DataFrame,
    ops_capacity_df: pd.DataFrame,
    approved_makes_df: pd.DataFrame,
    loan_history_df: pd.DataFrame,
    rules_df: pd.DataFrame,
    budgets_df: pd.DataFrame,
    week_start: str,
    office: str,
    # Core parameters
    loan_length_days: int = 7,
    solver_time_limit_s: int = 10,
    # Tier cap parameters
    lambda_cap: int = DEFAULT_LAMBDA_CAP,
    rolling_window_months: int = 12,
    # Fairness parameters
    lambda_fair: int = DEFAULT_LAMBDA_FAIR,
    fair_target: int = DEFAULT_FAIR_TARGET,
    fair_step_up: int = 0,
    # Budget parameters
    cost_per_assignment: Dict[str, float] = None,
    points_per_dollar: float = DEFAULT_POINTS_PER_DOLLAR,
    enforce_budget_hard: bool = False,
    enforce_missing_budget: bool = False,
    # Partner-day constraint
    max_per_partner_per_day: int = 1,
    # Partner-week constraint
    max_per_partner_per_week: int = 1,
    # Objective shaping parameters
    w_rank: float = DEFAULT_W_RANK,
    w_geo: float = DEFAULT_W_GEO,
    w_pub: float = DEFAULT_W_PUB,
    w_recency: float = DEFAULT_W_RECENCY,
    engagement_mode: str = 'neutral',
    w_preferred_day: float = 0,  # Weight for preferred day match (0=off)
    # General
    seed: int = 42,
    verbose: bool = True,
    # Database client for querying current activity
    db_client = None,
    # Capacity override from UI
    capacity_map_override: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Complete OR-Tools solver with all phases (7.2 through 7.6).

    Args:
        triples_df: Feasible triples from Phase 7.3 with 'score' column
        ops_capacity_df: Daily capacity limits
        approved_makes_df: Partner approvals with ranks
        loan_history_df: Historical loans for cap calculation
        rules_df: Cap rules by make/rank
        budgets_df: Quarterly budgets by office/fleet
        week_start: Monday of the target week
        office: Target office
        loan_length_days: Length of each loan
        solver_time_limit_s: Time limit for solver
        lambda_cap: Penalty weight for tier caps
        rolling_window_months: Window for cap calculation
        lambda_fair: Penalty weight for fairness
        fair_target: Target assignments per partner
        fair_step_up: Additional penalty for 3rd+ (Mode B)
        cost_per_assignment: Cost per assignment by make
        points_per_dollar: Penalty points per dollar over budget
        enforce_budget_hard: If True, hard budget constraints
        enforce_missing_budget: If True, treat missing budgets as 0
        max_per_partner_per_day: Max vehicles per partner per start day (0=unlimited, default=1)
        seed: Random seed for determinism
        verbose: Print detailed progress
        db_client: Supabase client for querying current_activity (optional)

    Returns:
        Dictionary with selected assignments, all summaries, and metadata
    """
    start_time = time.time()

    # Filter to target office
    office_triples = triples_df[triples_df['office'] == office].copy()

    if office_triples.empty:
        return _empty_result(office, week_start, start_time)

    # Apply objective shaping (Phase 7.8)
    office_triples = apply_objective_shaping(
        office_triples,
        w_rank=w_rank,
        w_geo=w_geo,
        w_pub=w_pub,
        w_recency=w_recency,
        engagement_mode=engagement_mode,
        w_preferred_day=w_preferred_day,
        verbose=verbose
    )

    # Use shaped score instead of original score
    if 'score_shaped' in office_triples.columns:
        office_triples['score'] = office_triples['score_shaped']
    elif 'score' not in office_triples.columns:
        raise ValueError("Triples must have 'score' or 'score_shaped' column.")

    # Create the CP-SAT model
    model = cp_model.CpModel()

    # Index triples
    office_triples = office_triples.reset_index(drop=True)
    n_triples = len(office_triples)

    if verbose:
        print(f"\n=== Phase 7 Complete: OR-Tools with All Constraints ===")
        print(f"  Triples to optimize: {n_triples}")
        print(f"  Constraints: VIN + Capacity (HARD), Caps + Fairness + Budget (SOFT/HARD)")

    # Decision variables: y[i] = 1 if triple i is selected
    y = {}
    y_by_key = {}

    for i in range(n_triples):
        row = office_triples.iloc[i]
        y[i] = model.NewBoolVar(f'y_{i}')

        key = (row['vin'], row['person_id'], row['start_day'])
        y_by_key[key] = y[i]

    # === HARD CONSTRAINT 1: VIN Uniqueness ===
    vin_groups = office_triples.groupby('vin').groups
    for vin, indices in vin_groups.items():
        if len(indices) > 1:
            model.Add(sum(y[i] for i in indices) <= 1)

    if verbose:
        print(f"  Added VIN uniqueness constraints for {len(vin_groups)} vehicles")

    # === HARD CONSTRAINT 2: Daily Capacity (7.7 Dynamic) ===
    week_start_date = pd.to_datetime(week_start)

    # Load dynamic capacity calendar with day-specific slots
    # Use override from UI if provided, otherwise load from database
    if capacity_map_override is not None:
        capacity_map = capacity_map_override
        notes_map = {}  # No notes when using UI override
        if verbose:
            print(f"  Using capacity override from UI")
    else:
        capacity_map, notes_map = load_capacity_calendar(
            ops_capacity_df=ops_capacity_df,
            office=office,
            week_start=week_start
        )

    # Count existing activities per start day to reduce available capacity
    existing_count_by_day = {}

    print(f"DEBUG: Checking for existing activities to reduce capacity (db_client={'present' if db_client else 'MISSING'})")

    if db_client:
        try:
            # Calculate week end date
            week_end_date = week_start_date + timedelta(days=6)

            # Query current_activity for activities starting in this week
            # Note: current_activity doesn't have office column, so we get all and filter by VIN later
            print(f"DEBUG: Querying current_activity from {week_start_date.date()} to {week_end_date.date()}")
            existing_response = db_client.table('current_activity')\
                .select('start_date, vehicle_vin')\
                .gte('start_date', str(week_start_date.date()))\
                .lte('start_date', str(week_end_date.date()))\
                .execute()

            print(f"DEBUG: Found {len(existing_response.data) if existing_response.data else 0} current_activity records")

            # Get ALL VINs for this office by querying vehicles table
            # (office_triples only has available vehicles, we need ALL office vehicles to filter activities)
            try:
                vehicles_response = db_client.table('vehicles')\
                    .select('vin')\
                    .eq('office', office)\
                    .execute()
                office_vins = set(v['vin'] for v in vehicles_response.data) if vehicles_response.data else set()
                print(f"DEBUG: Office has {len(office_vins)} total VINs (from vehicles table)")
            except Exception as ve:
                print(f"DEBUG: Could not load office vehicles, using triples VINs: {ve}")
                office_vins = set(office_triples['vin'].unique()) if not office_triples.empty else set()
                print(f"DEBUG: Office has {len(office_vins)} unique VINs (from triples)")

            # Count by start day (only for this office's vehicles)
            filtered_count = 0
            total_count = 0
            if existing_response.data:
                for activity in existing_response.data:
                    total_count += 1
                    vehicle_vin = activity.get('vehicle_vin')

                    # Only count if this vehicle belongs to this office
                    if vehicle_vin not in office_vins:
                        continue

                    filtered_count += 1
                    start_date_str = activity.get('start_date')
                    if start_date_str:
                        start_dt = pd.to_datetime(start_date_str).date()
                        existing_count_by_day[start_dt] = existing_count_by_day.get(start_dt, 0) + 1

                print(f"DEBUG: Filtered {filtered_count}/{total_count} activities to this office")

            # Also count manual scheduled assignments (Chain Builder picks)
            manual_response = db_client.table('scheduled_assignments')\
                .select('start_day')\
                .eq('office', office)\
                .eq('status', 'manual')\
                .gte('start_day', str(week_start_date.date()))\
                .lte('start_day', str(week_end_date.date()))\
                .execute()

            if manual_response.data:
                for assignment in manual_response.data:
                    start_date_str = assignment.get('start_day')
                    if start_date_str:
                        start_dt = pd.to_datetime(start_date_str).date()
                        existing_count_by_day[start_dt] = existing_count_by_day.get(start_dt, 0) + 1

            print(f"DEBUG: existing_count_by_day = {existing_count_by_day}")
            if verbose and existing_count_by_day:
                print(f"  Found existing activities reducing capacity: {existing_count_by_day}")
        except Exception as e:
            if verbose:
                print(f"  Warning: Could not query existing activities for capacity: {e}")

    # Apply capacity constraints (reduced by existing activities)
    start_day_groups = office_triples.groupby('start_day').groups
    for start_day_str, indices in start_day_groups.items():
        start_day = pd.to_datetime(start_day_str).date()
        if start_day in capacity_map:
            total_capacity = capacity_map[start_day]
            existing_count = existing_count_by_day.get(start_day, 0)
            available_capacity = max(0, total_capacity - existing_count)

            # Capacity 0 = blackout day or fully booked, no assignments allowed
            if available_capacity >= 0:
                model.Add(sum(y[i] for i in indices) <= available_capacity)
                if verbose and existing_count > 0:
                    print(f"  {start_day}: {total_capacity} capacity - {existing_count} existing = {available_capacity} available")

    if verbose:
        # Identify special days
        special_days = identify_special_days(capacity_map, notes_map)
        print(f"  Added capacity constraints for {len(start_day_groups)} start days")
        if special_days['blackouts']:
            print(f"  - {len(special_days['blackouts'])} blackout days")
        if special_days['travel_days']:
            print(f"  - {len(special_days['travel_days'])} travel days")
        if special_days['reduced_capacity']:
            print(f"  - {len(special_days['reduced_capacity'])} reduced capacity days")

    # === HARD CONSTRAINT 3: Max Vehicles per Partner per Day ===
    # Query current_activity to get existing active loans
    active_count_by_partner_day = {}

    if db_client and max_per_partner_per_day > 0:
        try:
            # Calculate week end date
            week_end_date = week_start_date + timedelta(days=6)

            # Query current_activity for loans that overlap with target week
            active_response = db_client.table('current_activity')\
                .select('person_id, start_date, end_date')\
                .lte('start_date', str(week_end_date.date()))\
                .gte('end_date', str(week_start_date.date()))\
                .execute()

            if active_response.data:
                # Build dictionary of active loan counts by (partner, date)
                for loan in active_response.data:
                    person_id = loan.get('person_id')
                    start_date = pd.to_datetime(loan.get('start_date')).date()
                    end_date = pd.to_datetime(loan.get('end_date')).date()

                    if not person_id:
                        continue

                    # For each day this loan covers in the target week
                    current_date = max(start_date, week_start_date.date())
                    end_check = min(end_date, week_end_date.date())

                    while current_date <= end_check:
                        key = (person_id, current_date)
                        active_count_by_partner_day[key] = active_count_by_partner_day.get(key, 0) + 1
                        current_date += timedelta(days=1)

                if verbose and active_count_by_partner_day:
                    existing_conflicts = len(active_count_by_partner_day)
                    print(f"  Found {existing_conflicts} (partner, day) combinations with existing active loans")
        except Exception as e:
            if verbose:
                print(f"  Warning: Could not query current_activity: {e}")

    # Group by (person_id, start_day) to enforce max vehicles per partner per start day
    partner_day_groups = office_triples.groupby(['person_id', 'start_day']).groups

    if max_per_partner_per_day > 0:  # 0 = unlimited
        blocked_count = 0
        reduced_count = 0

        for (person_id, start_day), indices in partner_day_groups.items():
            # Check if partner already has active loans on this start_day
            start_day_date = pd.to_datetime(start_day).date()
            existing_count = active_count_by_partner_day.get((person_id, start_day_date), 0)
            available_slots = max_per_partner_per_day - existing_count

            if available_slots <= 0:
                # Partner already at max capacity - block all new assignments for this day
                model.Add(sum(y[i] for i in indices) == 0)
                blocked_count += 1
            elif len(indices) > available_slots:
                # Partner has some slots left, but fewer than total candidates
                model.Add(sum(y[i] for i in indices) <= available_slots)
                reduced_count += 1
            elif len(indices) > max_per_partner_per_day:
                # No existing loans, apply normal constraint
                model.Add(sum(y[i] for i in indices) <= max_per_partner_per_day)

        if verbose:
            multi_option_groups = sum(1 for indices in partner_day_groups.values() if len(indices) > max_per_partner_per_day)
            print(f"  Added partner-day constraints: max {max_per_partner_per_day} vehicle(s) per partner per day")
            print(f"  - {len(partner_day_groups)} unique (partner, day) combinations in optimizer")
            print(f"  - {blocked_count} combinations blocked due to existing active loans")
            print(f"  - {reduced_count} combinations with reduced capacity due to existing loans")
            print(f"  - {multi_option_groups} combinations constrained by normal limit")
    else:
        if verbose:
            print(f"  No partner-day constraint (unlimited vehicles per partner per day)")

    # === HARD CONSTRAINT 4: Max Vehicles per Partner per Week ===
    # Group by person_id to enforce max vehicles per partner for the entire week
    # IMPORTANT: Must account for existing active loans, not just new assignments
    partner_week_groups = office_triples.groupby('person_id').groups

    # Count existing active vehicles per partner for this week
    active_vehicles_per_partner = {}
    if db_client and max_per_partner_per_week > 0:
        try:
            # Query current_activity for loans overlapping this week
            active_response = db_client.table('current_activity')\
                .select('person_id, vehicle_vin, start_date, end_date')\
                .lte('start_date', str(week_end_date.date()))\
                .gte('end_date', str(week_start_date.date()))\
                .execute()

            if active_response.data:
                # Count unique vehicles per partner during this week
                for loan in active_response.data:
                    person_id = loan.get('person_id')
                    if person_id:
                        active_vehicles_per_partner[person_id] = active_vehicles_per_partner.get(person_id, 0) + 1

                if verbose and active_vehicles_per_partner:
                    print(f"  Found {len(active_vehicles_per_partner)} partners with existing active loans this week")
        except Exception as e:
            if verbose:
                print(f"  Warning: Could not query current_activity for week constraint: {e}")

    if max_per_partner_per_week > 0:  # 0 = unlimited
        constrained_partners = 0
        blocked_partners = 0

        for person_id, indices in partner_week_groups.items():
            # Check how many vehicles this partner already has active this week
            existing_count = active_vehicles_per_partner.get(person_id, 0)
            available_slots = max_per_partner_per_week - existing_count

            if available_slots <= 0:
                # Partner already at max - block all new assignments
                model.Add(sum(y[i] for i in indices) == 0)
                blocked_partners += 1
            elif len(indices) > available_slots:
                # Partner has some slots left
                model.Add(sum(y[i] for i in indices) <= available_slots)
                constrained_partners += 1
            elif len(indices) > max_per_partner_per_week:
                # No existing loans, apply normal constraint
                model.Add(sum(y[i] for i in indices) <= max_per_partner_per_week)
                constrained_partners += 1

        if verbose:
            print(f"  Added partner-week constraints: max {max_per_partner_per_week} vehicle(s) per partner per week")
            print(f"  - {len(partner_week_groups)} unique partners in optimizer")
            print(f"  - {blocked_partners} partners blocked (already at max from existing loans)")
            print(f"  - {constrained_partners} partners constrained")
    else:
        if verbose:
            print(f"  No partner-week constraint (unlimited vehicles per partner per week)")

    # === SOFT CONSTRAINT 1: Tier Caps (7.4s) ===
    cap_penalty_terms, cap_info = add_soft_tier_cap_penalties(
        model=model,
        y_vars=y_by_key,
        triples_df=office_triples,
        approved_makes_df=approved_makes_df,
        loan_history_df=loan_history_df,
        rules_df=rules_df,
        week_start=week_start,
        lambda_cap=lambda_cap,
        rolling_window_months=rolling_window_months
    )

    # === SOFT CONSTRAINT 2: Fairness (7.5) ===
    fair_penalty_terms, fairness_info = add_fairness_penalties(
        model=model,
        y_vars=y_by_key,
        triples_df=office_triples,
        fair_target=fair_target,
        lambda_fair=lambda_fair,
        fair_step_up=fair_step_up,
        verbose=verbose
    )

    # === CONSTRAINT 3: Budgets (7.6) - SOFT or HARD ===
    budget_penalty_terms, budget_info = add_budget_constraints(
        model=model,
        y_vars=y_by_key,
        triples_df=office_triples,
        budgets_df=budgets_df,
        office=office,
        week_start=week_start,
        cost_per_assignment=cost_per_assignment,
        points_per_dollar=points_per_dollar,
        enforce_budget_hard=enforce_budget_hard,
        enforce_missing_budget=enforce_missing_budget,
        verbose=verbose
    )

    # === OBJECTIVE: Maximize score minus all penalties ===
    score_terms = [int(office_triples.iloc[i]['score']) * y[i] for i in range(n_triples)]
    objective = sum(score_terms)

    # Subtract all penalty terms
    all_penalties = cap_penalty_terms + fair_penalty_terms + budget_penalty_terms
    if all_penalties:
        objective -= sum(all_penalties)

    model.Maximize(objective)

    # === SOLVE ===
    if verbose:
        print("\n=== Solving with OR-Tools CP-SAT ===")

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = solver_time_limit_s
    solver.parameters.random_seed = seed
    solver.parameters.num_search_workers = 1  # Determinism

    status = solver.Solve(model)

    # Map status
    status_map = {
        cp_model.OPTIMAL: 'OPTIMAL',
        cp_model.FEASIBLE: 'FEASIBLE',
        cp_model.INFEASIBLE: 'INFEASIBLE',
        cp_model.MODEL_INVALID: 'MODEL_INVALID',
        cp_model.UNKNOWN: 'UNKNOWN'
    }
    solver_status = status_map.get(status, 'UNKNOWN')

    if verbose:
        print(f"  Solver status: {solver_status}")

    # Extract selected assignments
    selected_assignments = []
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        for i in range(n_triples):
            if solver.Value(y[i]) == 1:
                row = office_triples.iloc[i]

                # Calculate covered days
                start_date = pd.to_datetime(row['start_day'])
                covers_days = [
                    (start_date + timedelta(days=d)).strftime('%Y-%m-%d')
                    for d in range(loan_length_days)
                ]

                # Get cost for this assignment
                if cost_per_assignment:
                    est_cost = cost_per_assignment.get(row['make'], DEFAULT_COST_PER_ASSIGNMENT)
                else:
                    est_cost = DEFAULT_COST_PER_ASSIGNMENT

                selected_assignments.append({
                    'vin': row['vin'],
                    'person_id': row['person_id'],
                    'start_day': row['start_day'],
                    'office': row['office'],
                    'make': row['make'],
                    'model': row['model'],
                    'score': int(row['score']),
                    'estimated_cost': est_cost,
                    'fleet': normalize_fleet_name(row['make']),
                    'covers_days': covers_days
                })

        if verbose:
            print(f"  Selected {len(selected_assignments)} assignments")

    # Build summaries
    cap_summary = build_cap_summary_soft(selected_assignments, cap_info, lambda_cap)
    total_cap_penalty = cap_summary.attrs.get('total_penalty', 0) if not cap_summary.empty else 0

    fairness_summary = build_fairness_summary(
        selected_assignments, fairness_info, fair_target, lambda_fair, fair_step_up
    )
    total_fairness_penalty = fairness_summary.attrs.get('total_fairness_penalty', 0)

    budget_summary = build_budget_summary(
        selected_assignments, budget_info, budgets_df, office,
        cost_per_assignment, points_per_dollar
    )
    total_budget_penalty = budget_summary.attrs.get('total_budget_penalty', 0)

    # Calculate metrics
    total_score = sum(a['score'] for a in selected_assignments)
    total_penalties = total_cap_penalty + total_fairness_penalty + total_budget_penalty
    net_objective = total_score - total_penalties

    fairness_metrics = get_fairness_metrics(fairness_summary)

    # Daily usage with dynamic capacity report
    capacity_report = build_capacity_report(
        selected_assignments=selected_assignments,
        capacity_map=capacity_map,
        notes_map=notes_map,
        week_start=week_start
    )
    daily_usage = capacity_report['daily_usage']

    # Objective breakdown
    objective_breakdown = {
        'raw_score': total_score,
        'cap_penalty': total_cap_penalty,
        'fairness_penalty': total_fairness_penalty,
        'budget_penalty': total_budget_penalty,
        'total_penalties': total_penalties,
        'net_score': net_objective
    }

    # Shaping breakdown (Phase 7.8)
    shaping_breakdown = build_shaping_breakdown(
        selected_assignments,
        w_rank=w_rank,
        w_geo=w_geo,
        w_pub=w_pub,
        w_recency=w_recency
    )

    if verbose:
        print(f"\n=== Solution Summary ===")
        print(f"  Total score: {total_score:,}")
        print(f"  Cap penalty: -{total_cap_penalty:,}")
        print(f"  Fairness penalty: -{total_fairness_penalty:,}")
        print(f"  Budget penalty: -{total_budget_penalty:,.0f}")
        print(f"  Net objective: {net_objective:,}")

    # Build response
    return {
        'meta': {
            'office': office,
            'week_start': week_start,
            'solver_status': solver_status,
            'soft_caps': True,
            'fairness': True,
            'budgets': 'HARD' if enforce_budget_hard else 'SOFT',
            'lambda_cap': lambda_cap,
            'lambda_fair': lambda_fair,
            'points_per_dollar': points_per_dollar
        },
        'timing': {
            'wall_ms': int((time.time() - start_time) * 1000),
            'nodes_explored': solver.NumBranches()
        },
        'selected_assignments': selected_assignments,
        'daily_usage': daily_usage,
        'capacity_notes': capacity_report.get('capacity_notes', []),
        'special_days': capacity_report.get('special_days', {}),
        'objective_value': int(solver.ObjectiveValue()) if status in [cp_model.OPTIMAL, cp_model.FEASIBLE] else 0,
        'objective_breakdown': objective_breakdown,
        'shaping_breakdown': shaping_breakdown,
        'cap_summary': cap_summary,
        'fairness_summary': fairness_summary,
        'fairness_metrics': fairness_metrics,
        'budget_summary': budget_summary
    }


def _empty_result(office: str, week_start: str, start_time: float) -> Dict[str, Any]:
    """Generate empty result for infeasible case."""
    return {
        'meta': {
            'office': office,
            'week_start': week_start,
            'solver_status': 'INFEASIBLE'
        },
        'timing': {
            'wall_ms': int((time.time() - start_time) * 1000),
            'nodes_explored': 0
        },
        'selected_assignments': [],
        'daily_usage': [],
        'objective_value': 0,
        'objective_breakdown': {
            'raw_score': 0,
            'cap_penalty': 0,
            'fairness_penalty': 0,
            'budget_penalty': 0,
            'total_penalties': 0,
            'net_score': 0
        },
        'cap_summary': pd.DataFrame(),
        'fairness_summary': pd.DataFrame(),
        'fairness_metrics': {},
        'budget_summary': pd.DataFrame()
    }


# Note: _calculate_daily_usage removed - replaced by dynamic_capacity.build_capacity_report