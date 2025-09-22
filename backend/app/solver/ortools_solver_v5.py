"""
Phase 7.2 + 7.4s + 7.5: OR-Tools Solver with Soft Caps AND Fairness

Complete solver including:
- VIN uniqueness constraint (7.2) - HARD
- Daily capacity constraints (7.2) - HARD
- Cooldown filtering (7.3) - HARD (pre-filter)
- Soft tier caps with penalties (7.4s) - SOFT
- Fairness penalties for distribution (7.5) - SOFT
- Score maximization objective

"Turn preferences into prices; let the optimizer trade." - Naval
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from ortools.sat.python import cp_model
import time

# Import soft cap utilities
from app.solver.tier_caps_soft import (
    add_soft_tier_cap_penalties,
    build_cap_summary_soft,
    DEFAULT_LAMBDA_CAP
)

# Import fairness utilities
from app.solver.fairness_penalties import (
    add_fairness_penalties,
    build_fairness_summary,
    get_fairness_metrics,
    DEFAULT_FAIR_TARGET,
    DEFAULT_LAMBDA_FAIR
)

from app.solver.ortools_solver_v2 import add_score_to_triples


def solve_with_caps_and_fairness(
    triples_df: pd.DataFrame,
    ops_capacity_df: pd.DataFrame,
    approved_makes_df: pd.DataFrame,
    loan_history_df: pd.DataFrame,
    rules_df: pd.DataFrame,
    week_start: str,
    office: str,
    loan_length_days: int = 7,
    solver_time_limit_s: int = 10,
    lambda_cap: int = DEFAULT_LAMBDA_CAP,
    lambda_fair: int = DEFAULT_LAMBDA_FAIR,
    fair_target: int = DEFAULT_FAIR_TARGET,
    fair_step_up: int = 0,
    rolling_window_months: int = 12,
    seed: int = 42,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    OR-Tools solver with soft tier caps AND fairness penalties (7.2 + 7.4s + 7.5).

    Both tier caps and fairness are soft constraints via objective penalties,
    allowing the solver to trade off between score, cap compliance, and distribution.

    Args:
        triples_df: Feasible triples from Phase 7.3 with 'score' column
        ops_capacity_df: Daily capacity limits
        approved_makes_df: Partner approvals with ranks
        loan_history_df: Historical loans for cap calculation
        rules_df: Cap rules by make/rank
        week_start: Monday of the target week
        office: Target office
        loan_length_days: Length of each loan
        solver_time_limit_s: Time limit for solver
        lambda_cap: Penalty weight for exceeding caps
        lambda_fair: Penalty weight for concentration
        fair_target: Target assignments per partner before penalties
        fair_step_up: Additional penalty for 3rd+ (0 = Mode A)
        rolling_window_months: Window for cap calculation
        seed: Random seed for determinism
        verbose: Print detailed progress

    Returns:
        Dictionary with selected assignments, summaries, and metadata
    """
    start_time = time.time()

    # Filter to target office
    office_triples = triples_df[triples_df['office'] == office].copy()

    if office_triples.empty:
        return {
            'meta': {
                'office': office,
                'week_start': week_start,
                'solver_status': 'INFEASIBLE',
                'soft_caps': True,
                'fairness': True,
                'lambda_cap': lambda_cap,
                'lambda_fair': lambda_fair
            },
            'timing': {
                'wall_ms': int((time.time() - start_time) * 1000),
                'nodes_explored': 0
            },
            'selected_assignments': [],
            'daily_usage': [],
            'objective_value': 0,
            'cap_summary': pd.DataFrame(),
            'fairness_summary': pd.DataFrame(),
            'total_cap_penalty': 0,
            'total_fairness_penalty': 0
        }

    # Ensure we have scores
    if 'score' not in office_triples.columns:
        raise ValueError("Triples must have 'score' column. Run add_score_to_triples first.")

    # Create the CP-SAT model
    model = cp_model.CpModel()

    # Index triples for easier reference
    office_triples = office_triples.reset_index(drop=True)
    n_triples = len(office_triples)

    if verbose:
        print(f"\n=== Phase 7.2 + 7.4s + 7.5: OR-Tools with Caps AND Fairness ===")
        print(f"  Triples to optimize: {n_triples}")
        print(f"  Lambda cap: {lambda_cap}")
        print(f"  Lambda fair: {lambda_fair} (target: {fair_target}/partner)")

    # Decision variables: y[i] = 1 if triple i is selected
    y = {}
    y_by_key = {}  # For penalties

    for i in range(n_triples):
        row = office_triples.iloc[i]
        y[i] = model.NewBoolVar(f'y_{i}')

        # Index by (vin, person_id, start_day) for penalties
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

    # Group triples by start_day
    start_day_groups = office_triples.groupby('start_day').groups

    for start_day_str, indices in start_day_groups.items():
        start_day = pd.to_datetime(start_day_str).date()

        # Get capacity for this day
        if start_day in capacity_map:
            capacity = capacity_map[start_day]
            if capacity > 0:
                model.Add(sum(y[i] for i in indices) <= capacity)

    if verbose:
        print(f"  Added capacity constraints for {len(start_day_groups)} start days")

    # === SOFT CONSTRAINT 1: Tier Cap Penalties (Phase 7.4s) ===
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

    # === SOFT CONSTRAINT 2: Fairness Penalties (Phase 7.5) ===
    fair_penalty_terms, fairness_info = add_fairness_penalties(
        model=model,
        y_vars=y_by_key,
        triples_df=office_triples,
        fair_target=fair_target,
        lambda_fair=lambda_fair,
        fair_step_up=fair_step_up,
        verbose=verbose
    )

    # === OBJECTIVE: Maximize score minus all penalties ===
    # Base score from assignments
    score_terms = [int(office_triples.iloc[i]['score']) * y[i] for i in range(n_triples)]

    # Combine all components
    # Objective = sum(scores) - sum(cap_penalties) - sum(fairness_penalties)
    objective = sum(score_terms)

    if cap_penalty_terms:
        objective -= sum(cap_penalty_terms)

    if fair_penalty_terms:
        objective -= sum(fair_penalty_terms)

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

                selected_assignments.append({
                    'vin': row['vin'],
                    'person_id': row['person_id'],
                    'start_day': row['start_day'],
                    'office': row['office'],
                    'make': row['make'],
                    'model': row['model'],
                    'score': int(row['score']),
                    'covers_days': covers_days
                })

        if verbose:
            print(f"  Selected {len(selected_assignments)} assignments")
            print(f"  Objective value: {solver.ObjectiveValue()}")

    # Build cap summary
    cap_summary = build_cap_summary_soft(selected_assignments, cap_info, lambda_cap)
    total_cap_penalty = cap_summary.attrs.get('total_penalty', 0) if not cap_summary.empty else 0

    # Build fairness summary
    fairness_summary = build_fairness_summary(
        selected_assignments,
        fairness_info,
        fair_target,
        lambda_fair,
        fair_step_up
    )
    total_fairness_penalty = fairness_summary.attrs.get('total_fairness_penalty', 0)

    # Calculate daily usage
    daily_usage = []
    starts_per_day = {}

    for assignment in selected_assignments:
        start_day = assignment['start_day']
        starts_per_day[start_day] = starts_per_day.get(start_day, 0) + 1

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

    # Calculate actual scores and penalties
    total_score = sum(a['score'] for a in selected_assignments)
    net_objective = total_score - total_cap_penalty - total_fairness_penalty

    # Get fairness metrics
    fairness_metrics = get_fairness_metrics(fairness_summary)

    # Print summary if verbose
    if verbose:
        print(f"\n=== Solution Summary ===")
        print(f"  Total score: {total_score:,}")
        print(f"  Cap penalties: -{total_cap_penalty:,}")
        print(f"  Fairness penalties: -{total_fairness_penalty:,}")
        print(f"  Net objective: {net_objective:,}")

        if fairness_metrics['partners_with_multiple'] > 0:
            print(f"\n  Concentration detected:")
            print(f"    Partners with 2+: {fairness_metrics['partners_with_multiple']}")
            print(f"    Max per partner: {fairness_metrics['max_concentration']}")
            print(f"    Gini coefficient: {fairness_metrics['gini_coefficient']:.3f}")

    # Build response
    response = {
        'meta': {
            'office': office,
            'week_start': week_start,
            'solver_status': solver_status,
            'soft_caps': True,
            'fairness': True,
            'lambda_cap': lambda_cap,
            'lambda_fair': lambda_fair,
            'fair_target': fair_target,
            'fair_mode': 'B' if fair_step_up > 0 else 'A'
        },
        'timing': {
            'wall_ms': int((time.time() - start_time) * 1000),
            'nodes_explored': solver.NumBranches()
        },
        'selected_assignments': selected_assignments,
        'daily_usage': daily_usage,
        'objective_value': int(solver.ObjectiveValue()) if status in [cp_model.OPTIMAL, cp_model.FEASIBLE] else 0,
        'total_score': total_score,
        'total_cap_penalty': total_cap_penalty,
        'total_fairness_penalty': total_fairness_penalty,
        'net_objective': net_objective,
        'cap_summary': cap_summary,
        'fairness_summary': fairness_summary,
        'fairness_metrics': fairness_metrics
    }

    return response