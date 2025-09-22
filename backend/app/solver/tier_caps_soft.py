"""
Phase 7.4s: Soft Tier Caps (Penalty-Based)

Implements tier caps as soft constraints using penalties in the objective function
rather than hard constraints. This allows the solver flexibility to exceed caps
when necessary while still preferring to stay within them.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional, Any, List
from ortools.sat.python import cp_model


# Default caps by rank (when no RULES match)
DEFAULT_RANK_CAPS = {
    "A+": None,  # Unlimited (no penalty)
    "A": 100,
    "B": 50,
    "C": 10
}

# Penalty weight for exceeding caps
DEFAULT_LAMBDA_CAP = 800  # Comparable to losing a B-rank assignment


def normalize_rank(rank: Any) -> str:
    """
    Normalize rank to uppercase.

    Since we're in strict eligibility (approved_makes),
    every partner has a rank - no unranked cases.

    Args:
        rank: Raw rank value

    Returns:
        Normalized rank string
    """
    if pd.isna(rank):
        # Should not happen in strict eligibility
        return "C"  # Default to most restrictive if somehow missing

    return str(rank).strip().upper()


def get_cap_for_pair(
    person_id: str,
    make: str,
    rank: Any,
    rules_df: pd.DataFrame
) -> Optional[int]:
    """
    Get cap for a (person, make) pair using simplified rules.

    Logic:
    1. Check RULES for exact (make, rank) match
       - If exists with positive integer → use that cap
       - If exists with 0 or NULL → cap = 0
    2. Use rank defaults:
       - A+ → None (unlimited)
       - A → 100
       - B → 50
       - C → 10

    Args:
        person_id: Partner ID (not used, kept for compatibility)
        make: Vehicle make
        rank: Partner's rank for this make
        rules_df: Rules table with loan_cap_per_year

    Returns:
        Annual cap (0 means very restricted, None means unlimited)
    """
    normalized_rank = normalize_rank(rank)

    # Step 1: Check for exact (make, rank) match in RULES
    if not rules_df.empty and 'loan_cap_per_year' in rules_df.columns and 'rank' in rules_df.columns:
        rule_match = rules_df[
            (rules_df['make'] == make) &
            (rules_df['rank'] == normalized_rank)
        ]

        if not rule_match.empty:
            cap = rule_match.iloc[0]['loan_cap_per_year']
            # 0 or NULL in rules means cap=0 (heavily penalized but not blocked)
            if pd.isna(cap):
                return 0
            return int(cap)

    # Step 2: Use rank defaults (no rule found)
    return DEFAULT_RANK_CAPS.get(normalized_rank, 10)


def count_used_12m(
    person_id: str,
    make: str,
    loan_history_df: pd.DataFrame,
    as_of_date: datetime,
    rolling_window_months: int = 12
) -> int:
    """
    Count loans used in rolling 12-month window.

    Args:
        person_id: Partner ID
        make: Vehicle make
        loan_history_df: Historical loans with end_date or start_date
        as_of_date: Reference date (typically week_start)
        rolling_window_months: Window size in months

    Returns:
        Number of loans in window
    """
    if loan_history_df.empty:
        return 0

    # Calculate window start
    window_start = as_of_date - pd.DateOffset(months=rolling_window_months)

    # Filter to this person and make
    person_make_loans = loan_history_df[
        (loan_history_df['person_id'] == person_id) &
        (loan_history_df['make'] == make)
    ].copy()

    if person_make_loans.empty:
        return 0

    # Use end_date if available, else start_date
    person_make_loans['count_date'] = person_make_loans.apply(
        lambda row: row['end_date'] if pd.notna(row['end_date']) else row['start_date'],
        axis=1
    )

    # Ensure dates are datetime
    person_make_loans['count_date'] = pd.to_datetime(person_make_loans['count_date'])

    # Count loans in window
    in_window = person_make_loans[
        (person_make_loans['count_date'] >= window_start) &
        (person_make_loans['count_date'] < as_of_date)
    ]

    return len(in_window)


def add_soft_tier_cap_penalties(
    model: cp_model.CpModel,
    y_vars: Dict,
    triples_df: pd.DataFrame,
    approved_makes_df: pd.DataFrame,
    loan_history_df: pd.DataFrame,
    rules_df: pd.DataFrame,
    week_start: str,
    lambda_cap: int = DEFAULT_LAMBDA_CAP,
    rolling_window_months: int = 12
) -> Tuple[List, Dict[Tuple[str, str], Dict]]:
    """
    Add soft tier cap penalties to the objective function.

    Instead of hard constraints, we add penalty terms for exceeding caps.
    This allows the solver to exceed caps when necessary but prefers to stay within them.

    Args:
        model: OR-Tools CP model
        y_vars: Assignment decision variables {(v,p,s): BoolVar}
        triples_df: Feasible triples
        approved_makes_df: Partner approvals with ranks
        loan_history_df: Historical loans
        rules_df: Cap rules
        week_start: Week start date
        lambda_cap: Penalty weight for exceeding caps
        rolling_window_months: Window size

    Returns:
        Tuple of (penalty_terms, cap_info)
        - penalty_terms: List of penalty variables to add to objective
        - cap_info: Dictionary with cap details for each (person, make) pair
    """
    week_start_dt = pd.to_datetime(week_start)
    penalty_terms = []

    # Group triples by (person_id, make)
    pair_triples = {}
    for idx, triple in triples_df.iterrows():
        key = (triple['person_id'], triple['make'])
        if key not in pair_triples:
            pair_triples[key] = []

        # Find corresponding y variable
        y_key = (triple['vin'], triple['person_id'], triple['start_day'])
        if y_key in y_vars:
            pair_triples[key].append(y_vars[y_key])

    # Track cap info for reporting
    cap_info = {}
    penalties_added = 0

    print(f"\n=== Adding Soft Tier Cap Penalties ===")
    print(f"  Lambda (penalty weight): {lambda_cap}")

    for (person_id, make), vars_list in pair_triples.items():
        # Get rank
        rank = None
        if not approved_makes_df.empty:
            approval = approved_makes_df[
                (approved_makes_df['person_id'] == person_id) &
                (approved_makes_df['make'] == make)
            ]
            if not approval.empty:
                rank = approval.iloc[0].get('rank', None)

        # Get cap and usage
        used_12m = count_used_12m(
            person_id, make, loan_history_df,
            week_start_dt, rolling_window_months
        )
        cap = get_cap_for_pair(person_id, make, rank, rules_df)

        # Store cap info
        cap_info[(person_id, make)] = {
            'rank': rank,
            'normalized_rank': normalize_rank(rank),
            'used_12m': used_12m,
            'cap': cap,
            'remaining_before': None if cap is None else max(0, cap - used_12m),
            'currently_over': False if cap is None else used_12m > cap
        }

        # If unlimited (cap is None), no penalty needed
        if cap is None:
            continue

        # Calculate penalties for exceeding cap
        # new_pm = sum of assignments for this (person, make) pair
        new_pm = sum(vars_list)

        # Current overage (if already over cap)
        current_overage = max(0, used_12m - cap)

        # Future overage (after new assignments)
        # We need to create an integer variable for this
        future_total = used_12m + new_pm
        future_overage = model.NewIntVar(0, 1000, f'overage_{person_id}_{make}')

        # future_overage = max(0, future_total - cap)
        model.Add(future_overage >= 0)
        model.Add(future_overage >= future_total - cap)

        # Delta overage (only penalize NEW overage, not existing)
        delta_overage = model.NewIntVar(0, 1000, f'delta_overage_{person_id}_{make}')
        model.Add(delta_overage == future_overage - current_overage)

        # Add penalty term (lambda * delta_overage)
        penalty_terms.append(lambda_cap * delta_overage)
        penalties_added += 1

        # Store info about penalty
        cap_info[(person_id, make)]['has_penalty'] = True
        cap_info[(person_id, make)]['current_overage'] = current_overage

    print(f"  Added penalties for {penalties_added} partner-make pairs")

    # Summary stats
    if cap_info:
        at_cap = sum(1 for info in cap_info.values()
                    if info.get('remaining_before') is not None and info['remaining_before'] == 0)
        over_cap = sum(1 for info in cap_info.values() if info.get('currently_over', False))
        unlimited = sum(1 for info in cap_info.values() if info['cap'] is None)

        print(f"  Status: {at_cap} at cap, {over_cap} already over, {unlimited} unlimited")

    return penalty_terms, cap_info


def build_cap_summary_soft(
    selected_assignments: list,
    cap_info: Dict[Tuple[str, str], Dict],
    lambda_cap: int = DEFAULT_LAMBDA_CAP
) -> pd.DataFrame:
    """
    Build summary of cap usage after assignments with soft caps.

    Args:
        selected_assignments: List of selected assignment dictionaries
        cap_info: Cap information from add_soft_tier_cap_penalties
        lambda_cap: Penalty weight used

    Returns:
        DataFrame with cap usage summary including penalties
    """
    # Count assignments per (person_id, make)
    assignment_counts = {}
    for assignment in selected_assignments:
        key = (assignment['person_id'], assignment['make'])
        assignment_counts[key] = assignment_counts.get(key, 0) + 1

    # Build summary rows
    rows = []
    total_penalty = 0

    for (person_id, make), info in cap_info.items():
        assigned = assignment_counts.get((person_id, make), 0)
        cap = info['cap']
        used_before = info['used_12m']
        used_after = used_before + assigned

        # Calculate overages
        if cap is not None:
            overage_before = max(0, used_before - cap)
            overage_after = max(0, used_after - cap)
            delta_overage = overage_after - overage_before
            penalty = delta_overage * lambda_cap
            total_penalty += penalty
        else:
            overage_before = 0
            overage_after = 0
            delta_overage = 0
            penalty = 0

        rows.append({
            'person_id': person_id,
            'make': make,
            'rank': info['rank'],
            'used_12m_before': used_before,
            'cap': cap if cap is not None else 'Unlimited',
            'assigned_this_week': assigned,
            'used_after': used_after,
            'remaining_after': (None if cap is None else max(0, cap - used_after)),
            'overage_before': overage_before,
            'overage_after': overage_after,
            'delta_overage': delta_overage,
            'penalty': penalty
        })

    df = pd.DataFrame(rows)

    # Sort by highest penalty first
    if not df.empty:
        df = df.sort_values(['penalty', 'delta_overage'], ascending=[False, False])

    # Add total penalty as metadata
    df.attrs['total_penalty'] = total_penalty
    df.attrs['lambda_cap'] = lambda_cap

    return df