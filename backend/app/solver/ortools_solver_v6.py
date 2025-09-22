"""
Phase 7.2 + 7.4s + 7.5 + 7.6: Complete OR-Tools Solver

Includes all constraints:
- VIN uniqueness (7.2) - HARD
- Daily capacity (7.2) - HARD
- Cooldown filtering (7.3) - HARD (pre-filter)
- Soft tier caps (7.4s) - SOFT
- Distribution fairness (7.5) - SOFT
- Quarterly budgets (7.6) - SOFT/HARD

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
    # General
    seed: int = 42,
    verbose: bool = True
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
        seed: Random seed for determinism
        verbose: Print detailed progress

    Returns:
        Dictionary with selected assignments, all summaries, and metadata
    """
    start_time = time.time()

    # Filter to target office
    office_triples = triples_df[triples_df['office'] == office].copy()

    if office_triples.empty:
        return _empty_result(office, week_start, start_time)

    # Ensure we have scores
    if 'score' not in office_triples.columns:
        raise ValueError("Triples must have 'score' column. Run add_score_to_triples first.")

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

    # === HARD CONSTRAINT 2: Daily Capacity ===
    week_start_date = pd.to_datetime(week_start)
    capacity_map = {}

    if not ops_capacity_df.empty:
        office_capacity = ops_capacity_df[ops_capacity_df['office'] == office]
        for _, row in office_capacity.iterrows():
            date = pd.to_datetime(row['date']).date()
            capacity_map[date] = int(row['slots'])

    start_day_groups = office_triples.groupby('start_day').groups
    for start_day_str, indices in start_day_groups.items():
        start_day = pd.to_datetime(start_day_str).date()
        if start_day in capacity_map:
            capacity = capacity_map[start_day]
            if capacity > 0:
                model.Add(sum(y[i] for i in indices) <= capacity)

    if verbose:
        print(f"  Added capacity constraints for {len(start_day_groups)} start days")

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

    # Daily usage
    daily_usage = _calculate_daily_usage(selected_assignments, week_start_date, capacity_map)

    # Objective breakdown
    objective_breakdown = {
        'raw_score': total_score,
        'cap_penalty': total_cap_penalty,
        'fairness_penalty': total_fairness_penalty,
        'budget_penalty': total_budget_penalty,
        'total_penalties': total_penalties,
        'net_score': net_objective
    }

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
        'objective_value': int(solver.ObjectiveValue()) if status in [cp_model.OPTIMAL, cp_model.FEASIBLE] else 0,
        'objective_breakdown': objective_breakdown,
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


def _calculate_daily_usage(
    selected_assignments: List[Dict],
    week_start_date: datetime,
    capacity_map: Dict
) -> List[Dict]:
    """Calculate daily capacity usage."""
    starts_per_day = {}
    for assignment in selected_assignments:
        start_day = assignment['start_day']
        starts_per_day[start_day] = starts_per_day.get(start_day, 0) + 1

    daily_usage = []
    for offset in range(7):
        check_date = week_start_date + timedelta(days=offset)
        date_str = check_date.strftime('%Y-%m-%d')
        capacity = capacity_map.get(check_date.date(), 0)
        used = starts_per_day.get(date_str, 0)

        daily_usage.append({
            'date': date_str,
            'used': used,
            'capacity': capacity,
            'remaining': capacity - used
        })

    return daily_usage