"""
Test to verify model-level cooldown is working correctly.
This should block specific models (e.g., Camry) not entire makes (e.g., Toyota).
"""

import pandas as pd
from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.etl.cooldown import compute_cooldown_flags

def test_model_level_cooldown():
    """Test that cooldown blocks at model level, not make level."""

    # Create test data - partner has recent Toyota Camry loan
    loan_history = pd.DataFrame([
        {
            'activity_id': 'A001',
            'vin': 'VIN123',
            'person_id': 'P001',
            'make': 'Toyota',
            'model': 'Camry',
            'start_date': '2024-08-01',
            'end_date': '2024-08-08',  # Ended 45 days ago from Sept 22
            'clips_received': 1
        }
    ])

    # Configure 30-day cooldown for Toyota
    rules = pd.DataFrame([
        {'make': 'Toyota', 'cooldown_period_days': 30}
    ])

    # Test for Sept 22, 2024 (45 days after loan ended - should be OK)
    week_start = '2024-09-22'

    # Compute cooldown flags
    cooldown_df = compute_cooldown_flags(
        loan_history_df=loan_history,
        rules_df=rules,
        week_start=week_start,
        default_days=60
    )

    print("Cooldown DataFrame:")
    print(cooldown_df)
    print()

    # Check results
    camry_cooldown = cooldown_df[
        (cooldown_df['person_id'] == 'P001') &
        (cooldown_df['make'] == 'Toyota') &
        (cooldown_df['model'] == 'Camry')
    ]

    if not camry_cooldown.empty:
        print(f"Toyota Camry cooldown status: {camry_cooldown['cooldown_ok'].iloc[0]}")
        print(f"Cooldown until: {camry_cooldown['cooldown_until'].iloc[0]}")

    # Now test that a different Toyota model would be allowed
    # Since there's no history for Highlander, it should be OK
    print("\n--- Testing different model (Highlander) ---")

    # Create a vehicle availability scenario
    from app.solver.candidates import build_weekly_candidates

    # Create mock availability data
    availability = pd.DataFrame([
        {
            'vin': 'VIN456',
            'date': pd.Timestamp('2024-09-22') + pd.Timedelta(days=i),
            'market': 'Los Angeles',
            'make': 'Toyota',
            'model': 'Highlander',
            'available': True
        }
        for i in range(7)
    ])

    # Mock publication data
    publication = pd.DataFrame([
        {
            'person_id': 'P001',
            'make': 'Toyota',
            'loans_total_24m': 5,
            'loans_observed_24m': 5,
            'publications_observed_24m': 3,
            'publication_rate_observed': 0.6,
            'coverage': 1.0,
            'supported': True
        }
    ])

    # Build candidates
    candidates = build_weekly_candidates(
        availability_df=availability,
        cooldown_df=cooldown_df,
        publication_df=publication,
        week_start=week_start,
        min_available_days=7
    )

    print(f"Can P001 get Toyota Highlander? {len(candidates) > 0}")
    if not candidates.empty:
        print(f"Available candidates: {len(candidates)}")
        print(candidates[['vin', 'person_id', 'make', 'model', 'cooldown_ok']])

def test_make_level_fallback():
    """Test that cooldown falls back to make level when model is missing."""

    # Create test data - partner has loan with no model specified
    loan_history = pd.DataFrame([
        {
            'activity_id': 'A002',
            'vin': 'VIN789',
            'person_id': 'P002',
            'make': 'Honda',
            'model': None,  # No model specified
            'start_date': '2024-09-01',
            'end_date': '2024-09-08',  # Ended 14 days ago from Sept 22
            'clips_received': 1
        }
    ])

    # Configure 30-day cooldown for Honda
    rules = pd.DataFrame([
        {'make': 'Honda', 'cooldown_period_days': 30}
    ])

    # Test for Sept 22, 2024 (14 days after loan ended - should be blocked)
    week_start = '2024-09-22'

    # Compute cooldown flags
    cooldown_df = compute_cooldown_flags(
        loan_history_df=loan_history,
        rules_df=rules,
        week_start=week_start,
        default_days=60
    )

    print("\n--- Make-level fallback test ---")
    print("Cooldown DataFrame:")
    print(cooldown_df)
    print()

    # Check results - should have make-level cooldown
    honda_cooldown = cooldown_df[
        (cooldown_df['person_id'] == 'P002') &
        (cooldown_df['make'] == 'Honda')
    ]

    if not honda_cooldown.empty:
        print(f"Honda (no model) cooldown status: {honda_cooldown['cooldown_ok'].iloc[0]}")
        print(f"Cooldown until: {honda_cooldown['cooldown_until'].iloc[0]}")
        print(f"Model value: {honda_cooldown['model'].iloc[0]}")

if __name__ == "__main__":
    test_model_level_cooldown()
    test_make_level_fallback()