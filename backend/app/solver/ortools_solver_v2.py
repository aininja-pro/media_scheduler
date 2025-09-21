"""
Phase 7.2: Core OR-Tools CP-SAT Solver Implementation

This module implements the core optimization model with:
- VIN uniqueness constraint (each vehicle assigned at most once)
- Daily capacity constraints (respect slot limits)
- Score maximization objective
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from ortools.sat.python import cp_model
import time
import hashlib


def add_score_to_triples(
    triples_df: pd.DataFrame,
    partners_df: pd.DataFrame,
    publication_df: pd.DataFrame = None,
    rank_weights: Dict[str, int] = None,
    geo_bonus_points: int = 100,
    history_bonus_points: int = 50,
    seed: int = 42
) -> pd.DataFrame:
    """
    Add scoring columns to feasible triples.

    Uses simplified scoring based on what's available in triples:
    - rank_weight: Based on rank column
    - geo_bonus: Based on geo_office_match flag
    - history_bonus: If publication data available
    - Deterministic micro tie-breakers
    """
    if rank_weights is None:
        rank_weights = {"A+": 1000, "A": 700, "B": 400, "C": 100, "UNRANKED": 50}

    result = triples_df.copy()

    # Rank weight (already have rank column from feasible triples)
    result['rank_weight'] = result['rank'].map(
        lambda x: rank_weights.get(str(x).upper(), rank_weights.get("UNRANKED", 50))
    ).fillna(50).astype(int)

    # Geo bonus (use geo_office_match flag if present)
    if 'geo_office_match' in result.columns:
        result['geo_bonus'] = result['geo_office_match'].astype(int) * geo_bonus_points
    else:
        # Fallback: check if we have office info
        if 'office' in result.columns and 'office' in partners_df.columns:
            partner_offices = partners_df[['person_id', 'office']].drop_duplicates()
            result = result.merge(partner_offices, on='person_id', how='left', suffixes=('', '_partner'))
            result['geo_bonus'] = (result['office'] == result.get('office_partner', '')).astype(int) * geo_bonus_points
        else:
            result['geo_bonus'] = 0

    # History bonus (if publication data available)
    result['history_bonus'] = 0
    if publication_df is not None and not publication_df.empty:
        if 'publications_observed_24m' in publication_df.columns:
            pub_data = publication_df[['person_id', 'make', 'publications_observed_24m']].copy()
            pub_data = pub_data.groupby(['person_id', 'make'])['publications_observed_24m'].max().reset_index()
            result = result.merge(
                pub_data,
                on=['person_id', 'make'],
                how='left',
                suffixes=('', '_pub')
            )
            result['history_bonus'] = (
                result.get('publications_observed_24m', 0).fillna(0) >= 1
            ).astype(int) * history_bonus_points

    # Add deterministic tie-breakers based on hash
    np.random.seed(seed)

    # Model diversity bonus (0-50)
    if 'model' in result.columns:
        result['model_bonus'] = result['model'].apply(
            lambda x: abs(hash(str(x) + str(seed))) % 51 if pd.notna(x) else 25
        )
    else:
        result['model_bonus'] = 25

    # VIN hash bonus (0-20)
    if 'vin' in result.columns:
        result['vin_bonus'] = result['vin'].apply(
            lambda x: abs(hash(str(x) + str(seed))) % 21 if pd.notna(x) else 10
        )
    else:
        result['vin_bonus'] = 10

    # Compute total score
    result['score'] = (
        result['rank_weight'] +
        result['geo_bonus'] +
        result['history_bonus'] +
        result['model_bonus'] +
        result['vin_bonus']
    ).astype(int)

    return result


def solve_core_assignment(
    triples_df: pd.DataFrame,
    ops_capacity_df: pd.DataFrame,
    week_start: str,
    office: str,
    loan_length_days: int = 7,
    solver_time_limit_s: int = 10,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Phase 7.2: Core OR-Tools solver with VIN uniqueness and daily capacity constraints.

    Args:
        triples_df: Feasible triples from Phase 7.1 with 'score' column
        ops_capacity_df: Daily capacity limits (office, date, slots)
        week_start: Monday of the target week (YYYY-MM-DD)
        office: Target office
        loan_length_days: Length of each loan (default 7)
        solver_time_limit_s: Time limit for solver (default 10)
        seed: Random seed for determinism

    Returns:
        Dictionary with:
        - meta: office, week_start, solver_status
        - timing: wall_ms, nodes_explored
        - selected_assignments: List of chosen triples
        - daily_usage: Usage per day
        - objective_value: Total score
    """
    start_time = time.time()

    # Filter to target office
    office_triples = triples_df[triples_df['office'] == office].copy()

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
            'objective_value': 0
        }

    # Ensure we have scores
    if 'score' not in office_triples.columns:
        raise ValueError("Triples must have 'score' column. Run add_score_to_triples first.")

    # Create the CP-SAT model
    model = cp_model.CpModel()

    # Index triples for easier reference
    office_triples = office_triples.reset_index(drop=True)
    n_triples = len(office_triples)

    # Decision variables: y[i] = 1 if triple i is selected
    y = {}
    for i in range(n_triples):
        y[i] = model.NewBoolVar(f'y_{i}')

    # Constraint 1: VIN Uniqueness
    # Group triples by VIN
    vin_groups = office_triples.groupby('vin').groups
    for vin, indices in vin_groups.items():
        # Each VIN can be assigned at most once
        model.Add(sum(y[i] for i in indices) <= 1)

    # Constraint 2: Start-Day Capacity (delivery capability)
    # Only constrain the number of loans STARTING on each day, not occupancy
    week_start_date = pd.to_datetime(week_start)

    # Build capacity map
    capacity_map = {}
    if ops_capacity_df is not None and not ops_capacity_df.empty:
        office_capacity = ops_capacity_df[ops_capacity_df['office'] == office].copy()
        for _, row in office_capacity.iterrows():
            capacity_map[pd.to_datetime(row['date']).date()] = int(row['slots'])

    # Default capacity for missing days (0 for weekends)
    default_capacity = 0

    # Group triples by start day
    start_day_groups = office_triples.groupby('start_day').groups

    # For each start day, constrain the number of loans that can start
    for start_day_str, indices in start_day_groups.items():
        start_date = pd.to_datetime(start_day_str).date()

        # Get capacity for this start day (0 for weekends by default)
        capacity = capacity_map.get(start_date, default_capacity)

        # Skip if no capacity (e.g., weekends)
        if capacity == 0:
            # Force all assignments for this day to 0
            for i in indices:
                model.Add(y[i] == 0)
        else:
            # Add constraint: number of starts on this day <= capacity
            model.Add(sum(y[i] for i in indices) <= capacity)

    # Objective: Maximize total score
    objective_terms = []
    for i in range(n_triples):
        score = int(office_triples.iloc[i]['score'])
        objective_terms.append(score * y[i])

    model.Maximize(sum(objective_terms))

    # Set solver parameters
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = solver_time_limit_s
    solver.parameters.random_seed = seed
    solver.parameters.num_search_workers = 1  # For determinism

    # Solve
    status = solver.Solve(model)

    # Extract status
    status_map = {
        cp_model.OPTIMAL: 'OPTIMAL',
        cp_model.FEASIBLE: 'FEASIBLE',
        cp_model.INFEASIBLE: 'INFEASIBLE',
        cp_model.MODEL_INVALID: 'MODEL_INVALID',
        cp_model.UNKNOWN: 'TIME_LIMIT'
    }
    solver_status = status_map.get(status, 'UNKNOWN')

    # Extract solution
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

    # Calculate daily usage (based on STARTS, not occupancy)
    daily_usage = []
    starts_per_day = {}

    # Count starts per day
    for assignment in selected_assignments:
        start_day = assignment['start_day']
        starts_per_day[start_day] = starts_per_day.get(start_day, 0) + 1

    # Build daily usage report for the main week
    for offset in range(7):  # Just report the main week
        check_date = week_start_date + timedelta(days=offset)
        date_str = check_date.strftime('%Y-%m-%d')

        capacity = capacity_map.get(check_date.date(), 0)  # Default 0 for missing days
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
            'solver_status': solver_status
        },
        'timing': {
            'wall_ms': int((time.time() - start_time) * 1000),
            'nodes_explored': solver.NumBranches() if hasattr(solver, 'NumBranches') else 0
        },
        'selected_assignments': selected_assignments,
        'daily_usage': daily_usage,
        'objective_value': int(objective_value)
    }

    return response