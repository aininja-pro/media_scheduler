"""
Phase 7.3: Cooldown Constraint Filter

Removes feasible triples that violate cooldown windows based on partner's
loan history with intelligent grouping (class+powertrain > model > make).
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any


def build_cooldown_ledger(
    loan_history_df: pd.DataFrame,
    model_taxonomy_df: pd.DataFrame = None
) -> Dict[Tuple[str, ...], datetime]:
    """
    Build a ledger of last loan end dates for each partner and grouping.

    Args:
        loan_history_df: DataFrame with columns:
            person_id, make, model, model_short_name (optional),
            start_date, end_date
        model_taxonomy_df: Optional taxonomy for model classification

    Returns:
        Dictionary mapping (group_type, person_id, ...) to last_end_date
    """
    ledger = {}

    if loan_history_df.empty:
        return ledger

    # Add taxonomy data if available
    if model_taxonomy_df is not None and not model_taxonomy_df.empty:
        if 'model' in loan_history_df.columns and 'model' in model_taxonomy_df.columns:
            loan_history_df = loan_history_df.merge(
                model_taxonomy_df[['model', 'short_model_class', 'powertrain']].drop_duplicates(),
                on='model',
                how='left',
                suffixes=('', '_tax')
            )

    # Ensure date columns are datetime
    for date_col in ['start_date', 'end_date']:
        if date_col in loan_history_df.columns:
            loan_history_df[date_col] = pd.to_datetime(loan_history_df[date_col])

    # For each loan, determine the end date (prefer end_date, fallback to start_date)
    loan_history_df['last_end'] = loan_history_df.apply(
        lambda row: row['end_date'] if pd.notna(row['end_date']) else row['start_date'],
        axis=1
    )

    # Build ledger for each grouping level
    for _, loan in loan_history_df.iterrows():
        person_id = loan['person_id']
        last_end = loan['last_end']

        if pd.isna(last_end):
            continue

        # 1. Class + Powertrain level
        if pd.notna(loan.get('short_model_class')) and pd.notna(loan.get('powertrain')):
            key = ("CLASS_PWR", person_id, loan['short_model_class'], loan['powertrain'])
            if key not in ledger or last_end > ledger[key]:
                ledger[key] = last_end

        # 2. Model level
        if pd.notna(loan.get('model')):
            key = ("MODEL", person_id, loan['model'])
            if key not in ledger or last_end > ledger[key]:
                ledger[key] = last_end

        # 3. Make level
        if pd.notna(loan.get('make')):
            key = ("MAKE", person_id, loan['make'])
            if key not in ledger or last_end > ledger[key]:
                ledger[key] = last_end

    return ledger


def get_cooldown_days(make: str, rules_df: pd.DataFrame, default_cooldown_days: int = 30) -> int:
    """
    Get cooldown days for a make from rules table.

    Args:
        make: Vehicle make
        rules_df: DataFrame with columns: make, cooldown_period
        default_cooldown_days: Default if not in rules or NULL

    Returns:
        Cooldown days (0 means disabled)
    """
    if rules_df.empty or 'cooldown_period' not in rules_df.columns:
        return default_cooldown_days

    make_rule = rules_df[rules_df['make'] == make]

    if make_rule.empty:
        return default_cooldown_days

    cooldown = make_rule.iloc[0]['cooldown_period']

    # 0 means disabled
    if cooldown == 0:
        return 0

    # NULL/NaN means use default
    if pd.isna(cooldown):
        return default_cooldown_days

    return int(cooldown)


def check_cooldown(
    triple: pd.Series,
    ledger: Dict[Tuple[str, ...], datetime],
    cooldown_days: int
) -> Tuple[bool, Optional[str], Optional[datetime]]:
    """
    Check if a triple violates cooldown constraints.

    Args:
        triple: Row from feasible triples with person_id, start_day, etc.
        ledger: Cooldown ledger from build_cooldown_ledger
        cooldown_days: Number of days for cooldown

    Returns:
        Tuple of (cooldown_ok, cooldown_basis, cooldown_until)
    """
    # If cooldown disabled (0 days), always allow
    if cooldown_days == 0:
        return True, None, None

    person_id = triple['person_id']
    start_day = pd.to_datetime(triple['start_day'])

    # Try groupings in precedence order
    # 1. Model (most specific - blocks same model only)
    if pd.notna(triple.get('model')):
        key = ("MODEL", person_id, triple['model'])
        if key in ledger:
            last_end = ledger[key]
            cooldown_until = last_end + timedelta(days=cooldown_days)
            if start_day < cooldown_until:
                return False, "model", cooldown_until
            else:
                return True, "model", cooldown_until

    # 2. Make (fallback when model not available)
    if pd.notna(triple.get('make')):
        key = ("MAKE", person_id, triple['make'])
        if key in ledger:
            last_end = ledger[key]
            cooldown_until = last_end + timedelta(days=cooldown_days)
            if start_day < cooldown_until:
                return False, "make", cooldown_until
            else:
                return True, "make", cooldown_until

    # No history found at any level - allow
    return True, None, None


def apply_cooldown_filter(
    feasible_triples_df: pd.DataFrame,
    loan_history_df: pd.DataFrame,
    rules_df: pd.DataFrame = None,
    model_taxonomy_df: pd.DataFrame = None,
    default_cooldown_days: int = 30
) -> pd.DataFrame:
    """
    Apply cooldown filtering to feasible triples.

    Args:
        feasible_triples_df: Triples from Phase 7.1
        loan_history_df: Media loan history
        rules_df: Cooldown rules by make
        default_cooldown_days: Default cooldown period

    Returns:
        Filtered DataFrame with cooldown columns added
    """
    if feasible_triples_df.empty:
        return feasible_triples_df

    # Build the cooldown ledger
    ledger = build_cooldown_ledger(loan_history_df, model_taxonomy_df)

    # Initialize results
    result = feasible_triples_df.copy()
    result['cooldown_ok'] = True
    result['cooldown_basis'] = None
    result['cooldown_until'] = pd.NaT

    # Track removals by basis
    removal_counts = {'model': 0, 'make': 0}

    # Check each triple
    for idx, triple in result.iterrows():
        make = triple['make']

        # Get cooldown days for this make
        cooldown_days = get_cooldown_days(make, rules_df, default_cooldown_days)

        # Check cooldown
        ok, basis, until = check_cooldown(triple, ledger, cooldown_days)

        result.at[idx, 'cooldown_ok'] = ok
        result.at[idx, 'cooldown_basis'] = basis
        result.at[idx, 'cooldown_until'] = until

        if not ok:
            removal_counts[basis] = removal_counts.get(basis, 0) + 1

    # Filter to keep only cooldown_ok=True
    filtered_result = result[result['cooldown_ok'] == True].copy()

    # Print summary
    print(f"\nCooldown Filter Summary:")
    print(f"  Input triples: {len(feasible_triples_df)}")
    print(f"  Output triples: {len(filtered_result)}")
    print(f"  Removed: {len(feasible_triples_df) - len(filtered_result)}")

    if removal_counts['model'] + removal_counts['make'] > 0:
        print(f"\nRemovals by basis:")
        for basis, count in removal_counts.items():
            if count > 0:
                print(f"  {basis}: {count}")

        # Top impacted partners
        if len(result[result['cooldown_ok'] == False]) > 0:
            removed = result[result['cooldown_ok'] == False]
            top_partners = removed['person_id'].value_counts().head(5)
            if len(top_partners) > 0:
                print(f"\nTop impacted partners:")
                for pid, count in top_partners.items():
                    print(f"  {pid}: {count} triples removed")

            # Top impacted makes
            top_makes = removed['make'].value_counts().head(5)
            if len(top_makes) > 0:
                print(f"\nTop impacted makes:")
                for make, count in top_makes.items():
                    print(f"  {make}: {count} triples removed")

    return filtered_result