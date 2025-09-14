"""
ETL module for computing cooldown flags based on loan history and rules.

This module determines which partner-make-model combinations are in cooldown
based on recent loan activity and configured cooldown periods.
"""

from datetime import date, datetime, timedelta
from typing import Dict, Any
import pandas as pd
import numpy as np


def compute_cooldown_flags(
    loan_history_df: pd.DataFrame,
    rules_df: pd.DataFrame,
    week_start: str,
    default_days: int = 60
) -> pd.DataFrame:
    """
    Compute cooldown flags for partner-make-model combinations.

    Determines whether each partner (person_id) is in cooldown for specific
    make/model combinations based on their recent loan history and configured
    cooldown periods from the Rules table.

    Business Logic:
    - Primary grain: (person_id, make, model) when model is non-empty
    - Fallback grain: (person_id, make) when model is null/empty
    - Block when week_start < cooldown_until (exclusive)
    - Allow when week_start >= cooldown_until (inclusive) or no prior history

    Args:
        loan_history_df: DataFrame with columns:
            - activity_id, vin, person_id, make, model, start_date, end_date, clips_received
        rules_df: DataFrame with columns:
            - make, cooldown_period_days (0 or null => disabled)
        week_start: Target week start date in YYYY-MM-DD format (Monday)
        default_days: Default cooldown period if not specified in rules (default: 60)

    Returns:
        DataFrame with columns:
        - person_id: Partner identifier
        - make: Vehicle make
        - model: Vehicle model (may be None for make-only grain)
        - cooldown_until: Date until which partner is in cooldown (NaT if no cooldown)
        - cooldown_ok: True if partner can receive loans, False if in cooldown
        - cooldown_days_used: Number of cooldown days applied (0 if disabled)

        Grain: One row per observed (person_id, make, model) combination in loan history,
        plus (person_id, make) rows where model was missing.
    """

    # Parse week_start as date first (validate input)
    try:
        week_start_date = datetime.strptime(week_start, '%Y-%m-%d').date()
    except ValueError:
        raise ValueError(f"week_start must be in YYYY-MM-DD format, got: {week_start}")

    # Validate inputs
    if loan_history_df.empty:
        return pd.DataFrame(columns=[
            'person_id', 'make', 'model', 'cooldown_until', 'cooldown_ok', 'cooldown_days_used'
        ])

    # Create cooldown days lookup from rules
    cooldown_days_map = {}
    if not rules_df.empty:
        for _, rule in rules_df.iterrows():
            make = rule.get('make', '').strip()
            cooldown_days = rule.get('cooldown_period_days')

            if make:
                if pd.isna(cooldown_days):
                    cooldown_days_map[make] = default_days
                else:
                    cooldown_days_map[make] = int(cooldown_days)

    # Copy loan history and clean data
    history_df = loan_history_df.copy()

    # Ensure required columns exist
    required_cols = ['person_id', 'make', 'end_date']
    missing_cols = [col for col in required_cols if col not in history_df.columns]
    if missing_cols:
        raise ValueError(f"loan_history_df missing required columns: {missing_cols}")

    # Add model column if it doesn't exist
    if 'model' not in history_df.columns:
        history_df['model'] = None

    # Clean and prepare data
    history_df['person_id'] = history_df['person_id'].astype(str).str.strip()
    history_df['make'] = history_df['make'].astype(str).str.strip()

    # Handle model column - normalize None, empty strings, and 'None' strings to NaN
    # First, handle the existing None values by creating a mask before string conversion
    original_none_mask = history_df['model'].isna()

    # Convert to string for cleaning
    history_df['model'] = history_df['model'].astype(str).str.strip()

    # Convert various "empty" representations to NaN
    empty_mask = (history_df['model'] == '') | (history_df['model'] == 'None') | (history_df['model'] == 'nan')
    combined_mask = original_none_mask | empty_mask

    history_df.loc[combined_mask, 'model'] = None

    # Convert end_date to datetime
    history_df['end_date'] = pd.to_datetime(history_df['end_date'], errors='coerce').dt.date

    # Remove rows with invalid end_date
    history_df = history_df.dropna(subset=['end_date'])

    if history_df.empty:
        return pd.DataFrame(columns=[
            'person_id', 'make', 'model', 'cooldown_until', 'cooldown_ok', 'cooldown_days_used'
        ])

    # Find all unique grains in the data
    grains = []

    # Primary grain: (person_id, make, model) where model is not None
    primary_grain = history_df[history_df['model'].notna()][['person_id', 'make', 'model']].drop_duplicates()
    for _, row in primary_grain.iterrows():
        grains.append({
            'person_id': row['person_id'],
            'make': row['make'],
            'model': row['model'],
            'grain_type': 'primary'
        })

    # Fallback grain: (person_id, make) where model is None - only one row per combination
    fallback_candidates = history_df[history_df['model'].isna()][['person_id', 'make']].drop_duplicates()
    for _, row in fallback_candidates.iterrows():
        grains.append({
            'person_id': row['person_id'],
            'make': row['make'],
            'model': None,
            'grain_type': 'fallback'
        })

    # Process each grain
    results = []

    for grain in grains:
        person_id = grain['person_id']
        make = grain['make']
        model = grain['model']

        # Get cooldown days for this make
        cooldown_days = cooldown_days_map.get(make, default_days)

        # If cooldown is explicitly disabled (0 days), mark as OK
        if cooldown_days == 0:
            results.append({
                'person_id': person_id,
                'make': make,
                'model': model,
                'cooldown_until': pd.NaT,
                'cooldown_ok': True,
                'cooldown_days_used': 0
            })
            continue

        # Find matching loan history for this grain
        if model is not None:
            # Primary grain: exact match on (person_id, make, model)
            grain_history = history_df[
                (history_df['person_id'] == person_id) &
                (history_df['make'] == make) &
                (history_df['model'] == model)
            ]
        else:
            # Fallback grain: match on (person_id, make) where model is None
            # This includes all rows where model was originally None or converted from empty string
            grain_history = history_df[
                (history_df['person_id'] == person_id) &
                (history_df['make'] == make) &
                (history_df['model'].isna())
            ]

        if grain_history.empty:
            # No history for this grain - no cooldown
            results.append({
                'person_id': person_id,
                'make': make,
                'model': model,
                'cooldown_until': pd.NaT,
                'cooldown_ok': True,
                'cooldown_days_used': cooldown_days
            })
            continue

        # Find most recent end_date for this grain
        most_recent_end = grain_history['end_date'].max()

        # Calculate cooldown_until
        cooldown_until = most_recent_end + timedelta(days=cooldown_days)

        # Evaluate cooldown status
        # Block if week_start < cooldown_until (exclusive)
        # Allow if week_start >= cooldown_until (inclusive)
        cooldown_ok = week_start_date >= cooldown_until

        results.append({
            'person_id': person_id,
            'make': make,
            'model': model,
            'cooldown_until': cooldown_until,
            'cooldown_ok': cooldown_ok,
            'cooldown_days_used': cooldown_days
        })

    # Convert results to DataFrame
    result_df = pd.DataFrame(results)

    # Ensure proper column order
    if not result_df.empty:
        result_df = result_df[['person_id', 'make', 'model', 'cooldown_until', 'cooldown_ok', 'cooldown_days_used']]

    return result_df