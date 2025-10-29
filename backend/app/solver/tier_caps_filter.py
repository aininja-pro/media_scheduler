"""
Phase 7.4: Dynamic Tier Caps Filter

Enforces annual loan caps per (partner, make) pair using a rolling 12-month window.
Uses RULES table with fallbacks based on partner rank.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional, Any


# Fallback caps by rank
FALLBACK_RANK_CAPS = {
    "A+": 12,
    "A": 6,
    "B": 2,
    "C": 1
}
FALLBACK_UNRANKED_CAP = 1


def normalize_rank(rank: Any) -> str:
    """
    Normalize rank to uppercase, handle missing/pending as UNRANKED.

    Args:
        rank: Raw rank value

    Returns:
        Normalized rank string
    """
    if pd.isna(rank):
        return "UNRANKED"

    rank_str = str(rank).strip().upper()

    if rank_str in ["", "PENDING", "NONE", "NULL"]:
        return "UNRANKED"

    return rank_str


def get_cap_for_pair(
    person_id: str,
    make: str,
    rank: Any,
    rules_df: pd.DataFrame
) -> int:
    """
    Get cap for a (person, make) pair using precedence rules.

    Precedence:
    1. Rules table (make, rank) → specific cap
    2. Rules table (make only) → specific cap
    3. Fallback by rank
    4. Unranked fallback

    Args:
        person_id: Partner ID
        make: Vehicle make
        rank: Partner's rank for this make
        rules_df: Rules table with loan_cap_per_year

    Returns:
        Annual cap (0 means blocked)
    """
    normalized_rank = normalize_rank(rank)

    if not rules_df.empty and 'loan_cap_per_year' in rules_df.columns:
        # 1. Try (make, rank) match
        if 'rank' in rules_df.columns:
            rule_match = rules_df[
                (rules_df['make'] == make) &
                (rules_df['rank'] == rank)  # Use original rank for exact match
            ]

            if not rule_match.empty:
                cap = rule_match.iloc[0]['loan_cap_per_year']
                # 0 or NULL in rules means blocked (cap=0)
                if pd.isna(cap) or cap == 0:
                    return 0
                return int(cap)

        # 2. Try make-only match
        make_match = rules_df[rules_df['make'] == make]
        if not make_match.empty:
            # If multiple rows for make, take first one without rank requirement
            if 'rank' in rules_df.columns:
                make_only = make_match[make_match['rank'].isna()]
                if not make_only.empty:
                    cap = make_only.iloc[0]['loan_cap_per_year']
                else:
                    # Take first make match if no rank-less row
                    cap = make_match.iloc[0]['loan_cap_per_year']
            else:
                cap = make_match.iloc[0]['loan_cap_per_year']

            # 0 or NULL in rules means blocked
            if pd.isna(cap) or cap == 0:
                return 0
            return int(cap)

    # 3. Fallback by rank
    if normalized_rank in FALLBACK_RANK_CAPS:
        return FALLBACK_RANK_CAPS[normalized_rank]

    # 4. Unranked fallback
    return FALLBACK_UNRANKED_CAP


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


def build_cap_usage_ledger(
    feasible_triples_df: pd.DataFrame,
    approved_makes_df: pd.DataFrame,
    loan_history_df: pd.DataFrame,
    rules_df: pd.DataFrame,
    week_start: str,
    rolling_window_months: int = 12
) -> pd.DataFrame:
    """
    Build ledger of cap usage for all (partner, make) pairs.

    Args:
        feasible_triples_df: Post-cooldown triples
        approved_makes_df: Partner approvals with ranks
        loan_history_df: Historical loans
        rules_df: Cap rules
        week_start: Week start date
        rolling_window_months: Window size

    Returns:
        DataFrame with columns: person_id, make, rank, used_12m, cap, remaining
    """
    week_start_dt = pd.to_datetime(week_start)

    # Get unique (person_id, make) pairs from feasible triples
    pairs = feasible_triples_df[['person_id', 'make']].drop_duplicates()

    ledger_rows = []

    for _, pair in pairs.iterrows():
        person_id = pair['person_id']
        make = pair['make']

        # Get rank from approved_makes
        rank = None
        if not approved_makes_df.empty:
            approval = approved_makes_df[
                (approved_makes_df['person_id'] == person_id) &
                (approved_makes_df['make'] == make)
            ]
            if not approval.empty:
                rank = approval.iloc[0].get('rank', None)

        # Count historical usage
        used_12m = count_used_12m(
            person_id, make, loan_history_df,
            week_start_dt, rolling_window_months
        )

        # Get cap
        cap = get_cap_for_pair(person_id, make, rank, rules_df)

        # Calculate remaining
        remaining = max(0, cap - used_12m)

        ledger_rows.append({
            'person_id': person_id,
            'make': make,
            'rank': rank,
            'normalized_rank': normalize_rank(rank),
            'used_12m': used_12m,
            'cap': cap,
            'remaining': remaining
        })

    return pd.DataFrame(ledger_rows)


def apply_tier_caps_filter(
    feasible_triples_df: pd.DataFrame,
    approved_makes_df: pd.DataFrame,
    loan_history_df: pd.DataFrame,
    rules_df: pd.DataFrame,
    week_start: str,
    rolling_window_months: int = 12
) -> pd.DataFrame:
    """
    Apply tier caps filtering to remove triples that would exceed annual caps.

    This is a pre-solver filter. The actual solver will need the cap constraints
    added as well to ensure the selected assignments respect caps.

    Args:
        feasible_triples_df: Post-cooldown triples from Phase 7.3
        approved_makes_df: Partner approvals with ranks
        loan_history_df: Historical loans
        rules_df: Cap rules with loan_cap_per_year
        week_start: Week start date
        rolling_window_months: Window size

    Returns:
        Filtered DataFrame with cap metadata added
    """
    if feasible_triples_df.empty:
        return feasible_triples_df

    print("\nTier Caps Filter:")
    print(f"  Input triples: {len(feasible_triples_df)}")

    # Build cap usage ledger
    ledger = build_cap_usage_ledger(
        feasible_triples_df, approved_makes_df, loan_history_df,
        rules_df, week_start, rolling_window_months
    )

    # Create lookup for quick access
    cap_lookup = {}
    for _, row in ledger.iterrows():
        key = (row['person_id'], row['make'])
        cap_lookup[key] = {
            'used_12m': row['used_12m'],
            'cap': row['cap'],
            'remaining': row['remaining'],
            'rank': row['rank']
        }

    # Add cap metadata to triples
    result = feasible_triples_df.copy()
    result['used_12m'] = 0
    result['annual_cap'] = 0
    result['cap_remaining'] = 0
    result['cap_ok'] = True

    # Track removals
    removal_reasons = {'zero_cap': 0, 'at_cap': 0}

    for idx, triple in result.iterrows():
        person_id = triple['person_id']
        make = triple['make']
        key = (person_id, make)

        if key in cap_lookup:
            cap_info = cap_lookup[key]
            result.at[idx, 'used_12m'] = cap_info['used_12m']
            result.at[idx, 'annual_cap'] = cap_info['cap']
            result.at[idx, 'cap_remaining'] = cap_info['remaining']

            # Check if this triple should be filtered
            if cap_info['cap'] == 0:
                result.at[idx, 'cap_ok'] = False
                removal_reasons['zero_cap'] += 1
            elif cap_info['remaining'] <= 0:
                result.at[idx, 'cap_ok'] = False
                removal_reasons['at_cap'] += 1

    # Filter to keep only cap_ok=True
    filtered_result = result[result['cap_ok'] == True].copy()

    # Print summary
    print(f"  Output triples: {len(filtered_result)}")
    print(f"  Removed: {len(feasible_triples_df) - len(filtered_result)}")

    if removal_reasons['zero_cap'] + removal_reasons['at_cap'] > 0:
        print(f"\n  Removal reasons:")
        if removal_reasons['zero_cap'] > 0:
            print(f"    Zero cap (blocked): {removal_reasons['zero_cap']}")
        if removal_reasons['at_cap'] > 0:
            print(f"    At cap (used_12m >= cap): {removal_reasons['at_cap']}")

    # Show cap distribution
    if not ledger.empty:
        print(f"\n  Cap distribution:")
        cap_dist = ledger['cap'].value_counts().sort_index()
        for cap, count in cap_dist.items():
            print(f"    Cap {cap}: {count} partner-make pairs")

        # Show some at-cap partners
        at_cap = ledger[ledger['remaining'] == 0]
        if not at_cap.empty:
            print(f"\n  Partners at cap: {len(at_cap)}")
            for _, row in at_cap.head(3).iterrows():
                print(f"    {row['person_id']}: {row['make']} "
                      f"(used {row['used_12m']}/{row['cap']})")

    return filtered_result


def add_cap_constraints_to_solver(
    model,
    y_vars: Dict,
    triples_df: pd.DataFrame,
    approved_makes_df: pd.DataFrame,
    loan_history_df: pd.DataFrame,
    rules_df: pd.DataFrame,
    week_start: str,
    rolling_window_months: int = 12
):
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

    # Add constraint for each pair
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

        # Add constraint: used_12m + sum(new assignments) <= cap
        if cap > 0 and used_12m < cap:
            # Only add if there's room (cap > 0 and not already at cap)
            model.Add(sum(vars_list) <= cap - used_12m)
            constraints_added += 1
        elif cap == 0 or used_12m >= cap:
            # Block all assignments for this pair
            for var in vars_list:
                model.Add(var == 0)
            constraints_added += 1

    print(f"  Added {constraints_added} tier cap constraints")

    return constraints_added