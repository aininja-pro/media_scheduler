"""
Phase 7.4: Dynamic Tier Caps (Solver Constraints)

Adds tier cap constraints to the OR-Tools solver to enforce annual loan caps
per (partner, make) pair using a rolling 12-month window.

Pre-filters only explicit cap=0 cases. All other caps are enforced in-solver.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional, Any


# Default caps by rank (when no RULES match)
DEFAULT_RANK_CAPS = {
    "A+": None,  # Unlimited (no constraint)
    "A": 100,
    "B": 50,
    "C": 10
}


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
       - If exists with 0 or NULL → cap = 0 (blocked)
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
        Annual cap (0 means blocked, None means unlimited)
    """
    normalized_rank = normalize_rank(rank)

    # Step 1: Check for exact (make, rank) match in RULES
    if not rules_df.empty and 'loan_cap_per_year' in rules_df.columns and 'rank' in rules_df.columns:
        rule_match = rules_df[
            (rules_df['make'] == make) &
            (rules_df['rank'] == normalized_rank)  # Use normalized rank for comparison
        ]

        if not rule_match.empty:
            cap = rule_match.iloc[0]['loan_cap_per_year']
            # 0 or NULL in rules means blocked (cap=0)
            if pd.isna(cap) or cap == 0:
                return 0
            return int(cap)

    # Step 2: Use rank defaults (no rule found)
    return DEFAULT_RANK_CAPS.get(normalized_rank, 10)  # Default to 10 if rank unknown


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


def prefilter_zero_caps(
    feasible_triples_df: pd.DataFrame,
    approved_makes_df: pd.DataFrame,
    rules_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Pre-filter triples where cap=0 (explicit blocks).

    This is a micro-optimization to reduce solver search space.
    Only filters explicit cap=0 from rules. Everything else goes to solver.

    With simplified rules, we only check exact (make, rank) matches.

    Args:
        feasible_triples_df: Post-cooldown triples
        approved_makes_df: Partner approvals with ranks
        rules_df: Cap rules

    Returns:
        Filtered DataFrame with zero-cap triples removed
    """
    if feasible_triples_df.empty or rules_df.empty:
        return feasible_triples_df

    # Find all (make, rank) rules with cap=0
    zero_cap_pairs = set()

    if 'loan_cap_per_year' in rules_df.columns and 'rank' in rules_df.columns:
        # Check for zero caps (must have exact rank match)
        zero_rules = rules_df[
            (rules_df['loan_cap_per_year'] == 0) |
            (rules_df['loan_cap_per_year'].isna())
        ]

        for _, rule in zero_rules.iterrows():
            make = rule['make']
            rank = normalize_rank(rule['rank']) if pd.notna(rule['rank']) else None

            if rank:
                # Specific (make, rank) block
                zero_cap_pairs.add((make, rank))

    if not zero_cap_pairs:
        return feasible_triples_df

    # Filter triples
    result = feasible_triples_df.copy()
    to_remove = []

    for idx, triple in result.iterrows():
        person_id = triple['person_id']
        make = triple['make']

        # Get rank from approved_makes
        rank = None
        if not approved_makes_df.empty:
            approval = approved_makes_df[
                (approved_makes_df['person_id'] == person_id) &
                (approved_makes_df['make'] == make)
            ]
            if not approval.empty:
                rank = approval.iloc[0].get('rank', None)

        # Check if this triple should be filtered (use normalized rank)
        normalized_rank = normalize_rank(rank) if rank else None
        if (make, normalized_rank) in zero_cap_pairs:  # Specific rank blocked
            to_remove.append(idx)

    if to_remove:
        result = result.drop(to_remove)
        print(f"  Pre-filtered {len(to_remove)} triples with cap=0")

    return result


def add_tier_cap_constraints(
    model,
    y_vars: Dict,
    triples_df: pd.DataFrame,
    approved_makes_df: pd.DataFrame,
    loan_history_df: pd.DataFrame,
    rules_df: pd.DataFrame,
    week_start: str,
    rolling_window_months: int = 12
) -> Dict[Tuple[str, str], Dict]:
    """
    Add tier cap constraints to OR-Tools solver model.

    This ensures that selected assignments respect annual caps.
    Should be called from within the solver after variable creation.

    Args:
        model: OR-Tools CP model
        y_vars: Assignment decision variables {(v,p,s): BoolVar}
        triples_df: Feasible triples
        approved_makes_df: Partner approvals with ranks
        loan_history_df: Historical loans
        rules_df: Cap rules
        week_start: Week start date
        rolling_window_months: Window size

    Returns:
        Dictionary of cap info for each (person_id, make) pair
    """
    week_start_dt = pd.to_datetime(week_start)

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
    constraints_added = 0

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
            'remaining_before': None if cap is None else max(0, cap - used_12m)
        }

        # Add constraint: used_12m + sum(new assignments) <= cap
        if cap is None:
            # Unlimited - no constraint needed
            pass
        elif cap > 0:
            if used_12m < cap:
                # Add constraint if there's room
                remaining = cap - used_12m
                model.Add(sum(vars_list) <= remaining)
                constraints_added += 1
            else:
                # Already at or over cap - block all
                for var in vars_list:
                    model.Add(var == 0)
                constraints_added += 1
        else:
            # cap == 0: Block all assignments for this pair
            for var in vars_list:
                model.Add(var == 0)
            constraints_added += 1

    print(f"  Added {constraints_added} tier cap constraints")

    # Summary stats
    if cap_info:
        at_cap = sum(1 for info in cap_info.values()
                    if info['remaining_before'] is not None and info['remaining_before'] == 0)
        zero_cap = sum(1 for info in cap_info.values() if info['cap'] == 0)
        unlimited = sum(1 for info in cap_info.values() if info['cap'] is None)

        if at_cap > 0 or zero_cap > 0 or unlimited > 0:
            print(f"  Cap status: {at_cap} at cap, {zero_cap} blocked, {unlimited} unlimited")

    return cap_info


def build_cap_summary(
    selected_assignments: list,
    cap_info: Dict[Tuple[str, str], Dict]
) -> pd.DataFrame:
    """
    Build summary of cap usage after assignments.

    Args:
        selected_assignments: List of selected assignment dictionaries
        cap_info: Cap information from add_tier_cap_constraints

    Returns:
        DataFrame with cap usage summary
    """
    # Count assignments per (person_id, make)
    assignment_counts = {}
    for assignment in selected_assignments:
        key = (assignment['person_id'], assignment['make'])
        assignment_counts[key] = assignment_counts.get(key, 0) + 1

    # Build summary rows
    rows = []
    for (person_id, make), info in cap_info.items():
        assigned = assignment_counts.get((person_id, make), 0)

        rows.append({
            'person_id': person_id,
            'make': make,
            'rank': info['rank'],
            'used_12m_before': info['used_12m'],
            'cap': info['cap'] if info['cap'] is not None else 'Unlimited',
            'assigned_this_week': assigned,
            'used_after': info['used_12m'] + assigned,
            'remaining_after': (None if info['cap'] is None else
                              max(0, info['cap'] - info['used_12m'] - assigned))
        })

    df = pd.DataFrame(rows)

    # Sort by most constrained first
    if not df.empty:
        df = df.sort_values(['remaining_after', 'cap'], ascending=[True, True])

    return df