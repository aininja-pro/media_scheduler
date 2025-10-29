"""
Phase 7.2 + 7.4: OR-Tools Solver with Tier Cap Constraints

Enhanced solver that includes:
- VIN uniqueness constraint (7.2)
- Daily capacity constraints (7.2)
- Dynamic tier caps per (partner, make) (7.4)
- Score maximization objective
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from ortools.sat.python import cp_model
import time
import hashlib

# Import tier cap utilities
from app.solver.tier_caps import (
    add_tier_cap_constraints,
    prefilter_zero_caps,
    build_cap_summary
)


def solve_with_tier_caps(
    triples_df: pd.DataFrame,
    ops_capacity_df: pd.DataFrame,
    approved_makes_df: pd.DataFrame,
    loan_history_df: pd.DataFrame,
    rules_df: pd.DataFrame,
    week_start: str,
    office: str,
    loan_length_days: int = 7,
    solver_time_limit_s: int = 10,
    rolling_window_months: int = 12,
    seed: int = 42
) -> Dict[str, Any]:
    """
    OR-Tools solver with tier cap constraints (Phase 7.2 + 7.4).

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
        rolling_window_months: Window for cap calculation
        seed: Random seed for determinism

    Returns:
        Dictionary with selected assignments, cap usage, and metadata
    """
    start_time = time.time()

    # Pre-filter explicit cap=0 cases (micro-optimization)
    print("\n=== Phase 7.4: Pre-filtering zero caps ===")
    triples_filtered = prefilter_zero_caps(triples_df, approved_makes_df, rules_df)

    # Filter to target office
    office_triples = triples_filtered[triples_filtered['office'] == office].copy()

    if office_triples.empty:
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
            'cap_summary': pd.DataFrame()
        }

    # Ensure we have scores
    if 'score' not in office_triples.columns:
        raise ValueError("Triples must have 'score' column. Run add_score_to_triples first.")

    # Create the CP-SAT model
    model = cp_model.CpModel()

    # Index triples for easier reference
    office_triples = office_triples.reset_index(drop=True)
    n_triples = len(office_triples)

    print(f"\n=== Phase 7.2: Building OR-Tools model ===")
    print(f"  Triples to optimize: {n_triples}")

    # Decision variables: y[i] = 1 if triple i is selected
    y = {}
    y_by_key = {}  # For tier cap constraints

    for i in range(n_triples):
        row = office_triples.iloc[i]
        y[i] = model.NewBoolVar(f'y_{i}')

        # Also index by (vin, person_id, start_day) for tier caps
        key = (row['vin'], row['person_id'], row['start_day'])
        y_by_key[key] = y[i]

    # === CONSTRAINT 1: VIN Uniqueness ===
    # Each VIN can be assigned at most once
    vin_groups = office_triples.groupby('vin').groups
    for vin, indices in vin_groups.items():
        if len(indices) > 1:
            model.Add(sum(y[i] for i in indices) <= 1)
    print(f"  Added VIN uniqueness constraints for {len(vin_groups)} vehicles")

    # === CONSTRAINT 2: Daily Capacity ===
    # Build capacity map
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
                # Add constraint: sum of starts on this day <= capacity
                model.Add(sum(y[i] for i in indices) <= capacity)

    print(f"  Added capacity constraints for {len(start_day_groups)} start days")

    # === CONSTRAINT 3: Tier Caps (Phase 7.4) ===
    print("\n=== Phase 7.4: Adding tier cap constraints ===")
    cap_info = add_tier_cap_constraints(
        model=model,
        y_vars=y_by_key,
        triples_df=office_triples,
        approved_makes_df=approved_makes_df,
        loan_history_df=loan_history_df,
        rules_df=rules_df,
        week_start=week_start,
        rolling_window_months=rolling_window_months
    )

    # === OBJECTIVE: Maximize total score ===
    objective = sum(int(office_triples.iloc[i]['score']) * y[i] for i in range(n_triples))
    model.Maximize(objective)

    # === SOLVE ===
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

    print(f"  Solver status: {solver_status}")
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        print(f"  Objective value: {solver.ObjectiveValue()}")

    # Extract selected assignments
    selected_assignments = []
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        for i in range(n_triples):
            if solver.Value(y[i]) == 1:
                row = office_triples.iloc[i]

                # Calculate covered days for this loan
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

    # Build cap summary
    cap_summary = build_cap_summary(selected_assignments, cap_info)

    # Calculate daily usage
    daily_usage = []
    starts_per_day = {}

    for assignment in selected_assignments:
        start_day = assignment['start_day']
        starts_per_day[start_day] = starts_per_day.get(start_day, 0) + 1

    # Build daily usage report for the main week
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

    # Calculate objective value
    objective_value = solver.ObjectiveValue() if status in [cp_model.OPTIMAL, cp_model.FEASIBLE] else 0

    # Build response
    response = {
        'meta': {
            'office': office,
            'week_start': week_start,
            'solver_status': solver_status,
            'tier_caps_enabled': True
        },
        'timing': {
            'wall_ms': int((time.time() - start_time) * 1000),
            'nodes_explored': solver.NumBranches()
        },
        'selected_assignments': selected_assignments,
        'daily_usage': daily_usage,
        'objective_value': int(objective_value),
        'cap_summary': cap_summary
    }

    # Print cap utilization summary
    if not cap_summary.empty:
        print("\n=== Tier Cap Utilization ===")
        at_cap = cap_summary[cap_summary['remaining_after'] == 0]
        if not at_cap.empty:
            print(f"  Partners at cap after assignments: {len(at_cap)}")
            for _, row in at_cap.head(3).iterrows():
                print(f"    {row['person_id']}: {row['make']} "
                      f"({row['used_after']}/{row['cap']})")

    return response