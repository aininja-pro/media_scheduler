"""
Phase 7.6: Quarterly Budget Constraints

Implements budget awareness for optimization by office × fleet × quarter.
Supports both soft penalties and hard constraints.

"We don't just schedule cars—we honor the purse strings." - Godin
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any, Optional
from ortools.sat.python import cp_model


# Default configuration
DEFAULT_POINTS_PER_DOLLAR = 3  # Penalty points per dollar over budget
DEFAULT_COST_PER_ASSIGNMENT = 1000  # Default cost if not specified

# Fleet name mappings (normalized uppercase)
FLEET_ALIASES = {
    'VW': 'VOLKSWAGEN',
    'CHEVY': 'CHEVROLET',
    'INFINITI': 'INFINITY',
    'MERCEDES': 'MERCEDES-BENZ',
    'MERCEDES BENZ': 'MERCEDES-BENZ',
    'ROLLS ROYCE': 'ROLLS-ROYCE',
    'LAND ROVER': 'LANDROVER',
    'ALFA ROMEO': 'ALFAROMEO'
}


def normalize_fleet_name(make: str) -> str:
    """
    Normalize make name to match fleet name in budgets table.

    Args:
        make: Vehicle make from assignments

    Returns:
        Normalized fleet name (uppercase)
    """
    if pd.isna(make):
        return 'UNKNOWN'

    normalized = str(make).strip().upper()

    # Apply aliases
    if normalized in FLEET_ALIASES:
        return FLEET_ALIASES[normalized]

    # Don't remove hyphens for certain brands that need them
    if 'MERCEDES' in normalized or 'ROLLS' in normalized:
        # Keep the hyphen for these brands
        pass
    else:
        # Remove common suffixes for others
        normalized = normalized.replace('-', '').replace('_', '').replace(' ', '')

    return normalized


def get_quarter_from_date(date_str: str) -> Tuple[int, str]:
    """
    Get year and quarter from a date string.

    Args:
        date_str: Date in YYYY-MM-DD format

    Returns:
        Tuple of (year, quarter) where quarter is 'Q1', 'Q2', 'Q3', or 'Q4'
    """
    date = pd.to_datetime(date_str)
    year = date.year
    month = date.month

    if month <= 3:
        quarter = 'Q1'
    elif month <= 6:
        quarter = 'Q2'
    elif month <= 9:
        quarter = 'Q3'
    else:
        quarter = 'Q4'

    return year, quarter


def load_budgets_for_week(
    budgets_df: pd.DataFrame,
    office: str,
    week_start: str
) -> Dict[Tuple[str, str, int, str], Dict[str, float]]:
    """
    Load relevant budgets for a given week.

    Args:
        budgets_df: DataFrame from budgets table
        office: Target office
        week_start: Monday of the week

    Returns:
        Dict mapping (office, fleet, year, quarter) to budget info
    """
    budgets = {}

    # Determine which quarters the week might span
    week_start_date = pd.to_datetime(week_start)
    week_end_date = week_start_date + timedelta(days=6)

    start_year, start_quarter = get_quarter_from_date(week_start)
    end_year, end_quarter = get_quarter_from_date(str(week_end_date.date()))

    # Get relevant quarters
    relevant_quarters = [(start_year, start_quarter)]
    if (end_year, end_quarter) != (start_year, start_quarter):
        relevant_quarters.append((end_year, end_quarter))

    # Filter budgets
    if not budgets_df.empty:
        office_budgets = budgets_df[budgets_df['office'] == office]

        for _, row in office_budgets.iterrows():
            year = int(row['year'])
            quarter = row['quarter']

            # Check if this budget is relevant
            if (year, quarter) in relevant_quarters:
                fleet = normalize_fleet_name(row['fleet'])
                budget_amount = float(row['budget_amount'])
                amount_used = float(row['amount_used']) if pd.notna(row['amount_used']) else 0.0

                # Calculate remaining budget
                remaining = max(0, budget_amount - amount_used)

                key = (office, fleet, year, quarter)
                budgets[key] = {
                    'budget_amount': budget_amount,
                    'amount_used': amount_used,
                    'remaining': remaining
                }

    return budgets


def add_budget_constraints(
    model: cp_model.CpModel,
    y_vars: Dict,
    triples_df: pd.DataFrame,
    budgets_df: pd.DataFrame,
    office: str,
    week_start: str,
    cost_per_assignment: Dict[str, float] = None,
    points_per_dollar: float = DEFAULT_POINTS_PER_DOLLAR,
    enforce_budget_hard: bool = False,
    enforce_missing_budget: bool = False,
    verbose: bool = True
) -> Tuple[List, Dict[str, Any]]:
    """
    Add budget constraints or penalties to the optimization model.

    Args:
        model: OR-Tools CP model
        y_vars: Assignment decision variables
        triples_df: Feasible triples
        budgets_df: DataFrame from budgets table
        office: Target office
        week_start: Monday of the week
        cost_per_assignment: Cost per assignment by make
        points_per_dollar: Penalty points per dollar over budget
        enforce_budget_hard: If True, use hard constraints; if False, use penalties
        enforce_missing_budget: If True, treat missing budgets as 0
        verbose: Print debug info

    Returns:
        Tuple of (penalty_terms, budget_info)
        - penalty_terms: List of penalty variables (empty if hard mode)
        - budget_info: Dict with budget details
    """

    if verbose:
        print(f"\n=== Adding Budget Constraints (Phase 7.6) ===")
        print(f"  Mode: {'HARD' if enforce_budget_hard else 'SOFT'}")
        print(f"  Points per dollar: {points_per_dollar}")

    # Load relevant budgets
    budgets = load_budgets_for_week(budgets_df, office, week_start)

    if verbose:
        print(f"  Loaded {len(budgets)} budget buckets for {office}")

    # Default costs if not provided
    if cost_per_assignment is None:
        cost_per_assignment = {}

    # Group triples by budget bucket
    bucket_assignments = {}
    for idx, triple in triples_df.iterrows():
        # Determine budget bucket
        fleet = normalize_fleet_name(triple['make'])
        year, quarter = get_quarter_from_date(triple['start_day'])
        bucket_key = (office, fleet, year, quarter)

        if bucket_key not in bucket_assignments:
            bucket_assignments[bucket_key] = []

        # Find corresponding y variable
        y_key = (triple['vin'], triple['person_id'], triple['start_day'])
        if y_key in y_vars:
            # Get cost for this assignment
            cost = cost_per_assignment.get(
                triple['make'],
                DEFAULT_COST_PER_ASSIGNMENT
            )
            bucket_assignments[bucket_key].append((y_vars[y_key], cost))

    # Track budget info
    budget_info = {}
    penalty_terms = []

    # Process each budget bucket
    for bucket_key, assignments in bucket_assignments.items():
        office, fleet, year, quarter = bucket_key

        # Get budget for this bucket
        if bucket_key in budgets:
            budget_data = budgets[bucket_key]
            remaining = budget_data['remaining']
        elif enforce_missing_budget:
            # Treat missing budget as 0
            remaining = 0
            budget_data = {
                'budget_amount': 0,
                'amount_used': 0,
                'remaining': 0
            }
        else:
            # No budget constraint
            continue

        # Calculate planned spend for this bucket
        # planned_spend = Σ(cost * y[assignment])
        spend_terms = []
        for y_var, cost in assignments:
            spend_terms.append(int(cost) * y_var)

        if not spend_terms:
            continue

        # Create integer variable for total spend
        max_possible_spend = sum(cost for _, cost in assignments)
        planned_spend = model.NewIntVar(0, int(max_possible_spend),
                                       f'spend_{fleet}_{year}_{quarter}')
        model.Add(planned_spend == sum(spend_terms))

        # Store budget info
        budget_info[bucket_key] = {
            'budget_data': budget_data,
            'max_possible_spend': max_possible_spend,
            'num_options': len(assignments)
        }

        if enforce_budget_hard:
            # HARD MODE: Add constraint
            model.Add(planned_spend <= int(remaining))
            if verbose:
                print(f"  Hard constraint: {fleet} {year}-{quarter} ≤ ${remaining:,.0f}")

        else:
            # SOFT MODE: Add penalty for overage
            # over_budget = max(0, planned_spend - remaining)
            over_budget = model.NewIntVar(0, int(max_possible_spend),
                                         f'over_{fleet}_{year}_{quarter}')
            model.Add(over_budget >= planned_spend - int(remaining))
            model.Add(over_budget >= 0)

            # Add penalty term
            if points_per_dollar > 0:
                penalty_terms.append(int(points_per_dollar) * over_budget)

            budget_info[bucket_key]['has_penalty'] = True

    if verbose:
        print(f"  Processed {len(bucket_assignments)} budget buckets")
        if not enforce_budget_hard:
            print(f"  Added {len(penalty_terms)} penalty terms")

    return penalty_terms, budget_info


def build_budget_summary(
    selected_assignments: List[Dict[str, Any]],
    budget_info: Dict[Tuple[str, str, int, str], Dict],
    budgets_df: pd.DataFrame,
    office: str,
    cost_per_assignment: Dict[str, float] = None,
    points_per_dollar: float = DEFAULT_POINTS_PER_DOLLAR
) -> pd.DataFrame:
    """
    Build summary of budget usage after assignment.

    Args:
        selected_assignments: List of selected assignments
        budget_info: Budget info from add_budget_constraints
        budgets_df: Original budgets DataFrame
        office: Target office
        cost_per_assignment: Cost per assignment by make
        points_per_dollar: Penalty points per dollar

    Returns:
        DataFrame with budget summary per bucket
    """

    if cost_per_assignment is None:
        cost_per_assignment = {}

    # Calculate actual spend per bucket
    bucket_spend = {}
    for assignment in selected_assignments:
        fleet = normalize_fleet_name(assignment['make'])
        year, quarter = get_quarter_from_date(assignment['start_day'])
        bucket_key = (office, fleet, year, quarter)

        cost = cost_per_assignment.get(
            assignment['make'],
            DEFAULT_COST_PER_ASSIGNMENT
        )

        bucket_spend[bucket_key] = bucket_spend.get(bucket_key, 0) + cost

    # Build summary rows
    rows = []
    total_penalty = 0

    for bucket_key, spend in bucket_spend.items():
        office, fleet, year, quarter = bucket_key

        # Get budget data
        if bucket_key in budget_info:
            budget_data = budget_info[bucket_key]['budget_data']
        else:
            # Look up from original budgets
            budget_match = budgets_df[
                (budgets_df['office'] == office) &
                (budgets_df['fleet'].str.upper() == fleet) &
                (budgets_df['year'] == year) &
                (budgets_df['quarter'] == quarter)
            ]

            if not budget_match.empty:
                row = budget_match.iloc[0]
                budget_data = {
                    'budget_amount': float(row['budget_amount']),
                    'amount_used': float(row['amount_used']) if pd.notna(row['amount_used']) else 0,
                    'remaining': max(0, float(row['budget_amount']) -
                                   (float(row['amount_used']) if pd.notna(row['amount_used']) else 0))
                }
            else:
                budget_data = None

        if budget_data:
            over_budget = max(0, spend - budget_data['remaining'])
            penalty = over_budget * points_per_dollar
            total_penalty += penalty

            rows.append({
                'office': office,
                'fleet': fleet,
                'year': year,
                'quarter': quarter,
                'budget_amount': budget_data['budget_amount'],
                'amount_used': budget_data['amount_used'],
                'remaining_before': budget_data['remaining'],
                'planned_spend': spend,
                'remaining_after': budget_data['remaining'] - spend,
                'over_budget': over_budget,
                'penalty_points': penalty
            })
        else:
            # No budget constraint
            rows.append({
                'office': office,
                'fleet': fleet,
                'year': year,
                'quarter': quarter,
                'budget_amount': None,
                'amount_used': 0,
                'remaining_before': None,
                'planned_spend': spend,
                'remaining_after': None,
                'over_budget': 0,
                'penalty_points': 0
            })

    df = pd.DataFrame(rows)

    # Sort by penalty (highest first)
    if not df.empty:
        df = df.sort_values('penalty_points', ascending=False)

    # Add metadata
    df.attrs['total_budget_penalty'] = total_penalty
    df.attrs['points_per_dollar'] = points_per_dollar

    return df