"""
Unit tests for the cooldown flags ETL module.
"""

import pytest
import pandas as pd
from datetime import date, timedelta
from app.etl.cooldown import compute_cooldown_flags


class TestCooldownFlags:
    """Test cooldown flags computation with various scenarios."""

    def test_blocks_within_window(self):
        """Test: Blocks within window - last_end_date = 30 days before week_start, cooldown_days=60 → cooldown_ok=False."""

        # Setup: loan ended 30 days ago, cooldown is 60 days
        week_start = "2025-09-08"  # Monday
        end_date = date(2025, 9, 8) - timedelta(days=30)  # 30 days before

        loan_history_df = pd.DataFrame([
            {
                'activity_id': 'ACT001',
                'vin': 'VIN123',
                'person_id': 'P001',
                'make': 'Toyota',
                'model': 'Camry',
                'start_date': end_date - timedelta(days=7),
                'end_date': end_date,
                'clips_received': 5
            }
        ])

        rules_df = pd.DataFrame([
            {'make': 'Toyota', 'cooldown_period_days': 60}
        ])

        result = compute_cooldown_flags(loan_history_df, rules_df, week_start)

        assert len(result) == 1
        row = result.iloc[0]
        assert row['person_id'] == 'P001'
        assert row['make'] == 'Toyota'
        assert row['model'] == 'Camry'
        assert row['cooldown_ok'] == False  # Still in cooldown
        assert row['cooldown_days_used'] == 60
        # cooldown_until should be end_date + 60 days
        expected_until = end_date + timedelta(days=60)
        assert row['cooldown_until'] == expected_until

    def test_passes_after_window(self):
        """Test: Passes after window - last_end_date = 70 days before, cooldown_days=60 → cooldown_ok=True."""

        # Setup: loan ended 70 days ago, cooldown is 60 days
        week_start = "2025-09-08"  # Monday
        end_date = date(2025, 9, 8) - timedelta(days=70)  # 70 days before

        loan_history_df = pd.DataFrame([
            {
                'activity_id': 'ACT001',
                'vin': 'VIN123',
                'person_id': 'P001',
                'make': 'Toyota',
                'model': 'Camry',
                'start_date': end_date - timedelta(days=7),
                'end_date': end_date,
                'clips_received': 5
            }
        ])

        rules_df = pd.DataFrame([
            {'make': 'Toyota', 'cooldown_period_days': 60}
        ])

        result = compute_cooldown_flags(loan_history_df, rules_df, week_start)

        assert len(result) == 1
        row = result.iloc[0]
        assert row['person_id'] == 'P001'
        assert row['make'] == 'Toyota'
        assert row['model'] == 'Camry'
        assert row['cooldown_ok'] == True  # Cooldown period has passed
        assert row['cooldown_days_used'] == 60
        expected_until = end_date + timedelta(days=60)
        assert row['cooldown_until'] == expected_until

    def test_no_history(self):
        """Test: No history - no prior loans for that (person, make, model) → cooldown_ok=True, cooldown_until=NaT."""

        # Setup: empty loan history
        loan_history_df = pd.DataFrame(columns=[
            'activity_id', 'vin', 'person_id', 'make', 'model', 'start_date', 'end_date', 'clips_received'
        ])

        rules_df = pd.DataFrame([
            {'make': 'Toyota', 'cooldown_period_days': 60}
        ])

        result = compute_cooldown_flags(loan_history_df, rules_df, "2025-09-08")

        # Should return empty DataFrame since no history
        assert len(result) == 0

    def test_disabled_by_rule(self):
        """Test: Disabled by rule - cooldown_period_days=0 for the make → always cooldown_ok=True regardless of history."""

        # Setup: recent loan but cooldown disabled (0 days)
        week_start = "2025-09-08"
        end_date = date(2025, 9, 7)  # Just yesterday

        loan_history_df = pd.DataFrame([
            {
                'activity_id': 'ACT001',
                'vin': 'VIN123',
                'person_id': 'P001',
                'make': 'Toyota',
                'model': 'Camry',
                'start_date': end_date - timedelta(days=7),
                'end_date': end_date,
                'clips_received': 5
            }
        ])

        rules_df = pd.DataFrame([
            {'make': 'Toyota', 'cooldown_period_days': 0}  # Disabled
        ])

        result = compute_cooldown_flags(loan_history_df, rules_df, week_start)

        assert len(result) == 1
        row = result.iloc[0]
        assert row['person_id'] == 'P001'
        assert row['make'] == 'Toyota'
        assert row['model'] == 'Camry'
        assert row['cooldown_ok'] == True  # Always OK when disabled
        assert row['cooldown_days_used'] == 0  # No days used
        assert pd.isna(row['cooldown_until'])  # NaT when disabled

    def test_model_grain_behavior(self):
        """Test: Model-grain behavior - Partner has recent (make=Toyota, model=Camry) but we evaluate (make=Toyota, model=Corolla) → the Corolla row is unaffected."""

        # Setup: Partner has recent Camry loan, but we have Corolla history too
        week_start = "2025-09-08"
        recent_date = date(2025, 9, 7)  # Yesterday
        old_date = date(2025, 7, 1)    # 2 months ago

        loan_history_df = pd.DataFrame([
            {
                'activity_id': 'ACT001',
                'vin': 'VIN123',
                'person_id': 'P001',
                'make': 'Toyota',
                'model': 'Camry',
                'start_date': recent_date - timedelta(days=7),
                'end_date': recent_date,  # Recent - should block
                'clips_received': 5
            },
            {
                'activity_id': 'ACT002',
                'vin': 'VIN456',
                'person_id': 'P001',
                'make': 'Toyota',
                'model': 'Corolla',
                'start_date': old_date - timedelta(days=7),
                'end_date': old_date,  # Old - should not block
                'clips_received': 3
            }
        ])

        rules_df = pd.DataFrame([
            {'make': 'Toyota', 'cooldown_period_days': 30}
        ])

        result = compute_cooldown_flags(loan_history_df, rules_df, week_start)

        # Should have 2 rows - one for each model
        assert len(result) == 2

        # Find Camry row
        camry_row = result[result['model'] == 'Camry'].iloc[0]
        assert camry_row['person_id'] == 'P001'
        assert camry_row['make'] == 'Toyota'
        assert camry_row['cooldown_ok'] == False  # Recent loan blocks

        # Find Corolla row
        corolla_row = result[result['model'] == 'Corolla'].iloc[0]
        assert corolla_row['person_id'] == 'P001'
        assert corolla_row['make'] == 'Toyota'
        assert corolla_row['cooldown_ok'] == True  # Old loan doesn't block

    def test_model_missing_fallback(self):
        """Test: Model missing (fallback) - History rows with model=None build cooldown at (person, make) grain."""

        # Setup: loans with missing model field
        week_start = "2025-09-08"
        end_date = date(2025, 8, 20)  # 19 days ago

        loan_history_df = pd.DataFrame([
            {
                'activity_id': 'ACT001',
                'vin': 'VIN123',
                'person_id': 'P001',
                'make': 'Toyota',
                'model': None,  # Missing model
                'start_date': end_date - timedelta(days=7),
                'end_date': end_date,
                'clips_received': 5
            },
            {
                'activity_id': 'ACT002',
                'vin': 'VIN456',
                'person_id': 'P001',
                'make': 'Toyota',
                'model': '',  # Empty string should become None
                'start_date': end_date - timedelta(days=14),
                'end_date': end_date - timedelta(days=7),
                'clips_received': 3
            }
        ])

        rules_df = pd.DataFrame([
            {'make': 'Toyota', 'cooldown_period_days': 30}
        ])

        result = compute_cooldown_flags(loan_history_df, rules_df, week_start)

        # Should have 1 row for (person, make) grain with model=None
        assert len(result) == 1
        row = result.iloc[0]
        assert row['person_id'] == 'P001'
        assert row['make'] == 'Toyota'
        assert pd.isna(row['model'])  # Should be None for fallback grain
        assert row['cooldown_ok'] == False  # 19 days < 30 days cooldown
        assert row['cooldown_days_used'] == 30

    def test_multiple_partners_and_makes(self):
        """Test: Multiple partners and makes with different cooldown rules."""

        week_start = "2025-09-08"
        recent_date = date(2025, 8, 25)  # 14 days ago

        loan_history_df = pd.DataFrame([
            {
                'activity_id': 'ACT001',
                'vin': 'VIN123',
                'person_id': 'P001',
                'make': 'Toyota',
                'model': 'Camry',
                'start_date': recent_date - timedelta(days=7),
                'end_date': recent_date,
                'clips_received': 5
            },
            {
                'activity_id': 'ACT002',
                'vin': 'VIN456',
                'person_id': 'P002',
                'make': 'Honda',
                'model': 'Accord',
                'start_date': recent_date - timedelta(days=7),
                'end_date': recent_date,
                'clips_received': 3
            }
        ])

        rules_df = pd.DataFrame([
            {'make': 'Toyota', 'cooldown_period_days': 30},  # 30 days
            {'make': 'Honda', 'cooldown_period_days': 10}    # 10 days
        ])

        result = compute_cooldown_flags(loan_history_df, rules_df, week_start)

        assert len(result) == 2

        # Toyota should still be in cooldown (14 < 30)
        toyota_row = result[result['make'] == 'Toyota'].iloc[0]
        assert toyota_row['cooldown_ok'] == False

        # Honda should be out of cooldown (14 > 10)
        honda_row = result[result['make'] == 'Honda'].iloc[0]
        assert honda_row['cooldown_ok'] == True

    def test_default_cooldown_days(self):
        """Test: Default cooldown days when make not in rules."""

        week_start = "2025-09-08"
        end_date = date(2025, 8, 1)  # 38 days ago

        loan_history_df = pd.DataFrame([
            {
                'activity_id': 'ACT001',
                'vin': 'VIN123',
                'person_id': 'P001',
                'make': 'BMW',  # Not in rules
                'model': 'X5',
                'start_date': end_date - timedelta(days=7),
                'end_date': end_date,
                'clips_received': 5
            }
        ])

        rules_df = pd.DataFrame([
            {'make': 'Toyota', 'cooldown_period_days': 30}  # BMW not included
        ])

        result = compute_cooldown_flags(loan_history_df, rules_df, week_start, default_days=60)

        assert len(result) == 1
        row = result.iloc[0]
        assert row['person_id'] == 'P001'
        assert row['make'] == 'BMW'
        assert row['model'] == 'X5'
        assert row['cooldown_days_used'] == 60  # Used default
        assert row['cooldown_ok'] == False  # 38 days < 60 days

    def test_exact_boundary_conditions(self):
        """Test: Exact boundary - week_start == cooldown_until should be OK."""

        # Setup: loan ended exactly cooldown_days ago
        week_start = "2025-09-08"
        cooldown_days = 30
        end_date = date(2025, 9, 8) - timedelta(days=cooldown_days)  # Exactly 30 days ago

        loan_history_df = pd.DataFrame([
            {
                'activity_id': 'ACT001',
                'vin': 'VIN123',
                'person_id': 'P001',
                'make': 'Toyota',
                'model': 'Camry',
                'start_date': end_date - timedelta(days=7),
                'end_date': end_date,
                'clips_received': 5
            }
        ])

        rules_df = pd.DataFrame([
            {'make': 'Toyota', 'cooldown_period_days': cooldown_days}
        ])

        result = compute_cooldown_flags(loan_history_df, rules_df, week_start)

        assert len(result) == 1
        row = result.iloc[0]
        assert row['cooldown_ok'] == True  # week_start == cooldown_until should be OK (inclusive)

    def test_missing_rules_uses_default(self):
        """Test: Missing rules table uses default cooldown days."""

        week_start = "2025-09-08"
        end_date = date(2025, 8, 20)  # 19 days ago

        loan_history_df = pd.DataFrame([
            {
                'activity_id': 'ACT001',
                'vin': 'VIN123',
                'person_id': 'P001',
                'make': 'Toyota',
                'model': 'Camry',
                'start_date': end_date - timedelta(days=7),
                'end_date': end_date,
                'clips_received': 5
            }
        ])

        # Empty rules table
        rules_df = pd.DataFrame(columns=['make', 'cooldown_period_days'])

        result = compute_cooldown_flags(loan_history_df, rules_df, week_start, default_days=30)

        assert len(result) == 1
        row = result.iloc[0]
        assert row['cooldown_days_used'] == 30  # Used default
        assert row['cooldown_ok'] == False  # 19 < 30

    def test_invalid_date_format(self):
        """Test: Invalid week_start format raises ValueError."""

        loan_history_df = pd.DataFrame(columns=[
            'activity_id', 'vin', 'person_id', 'make', 'model', 'start_date', 'end_date', 'clips_received'
        ])
        rules_df = pd.DataFrame(columns=['make', 'cooldown_period_days'])

        with pytest.raises(ValueError, match="week_start must be in YYYY-MM-DD format"):
            compute_cooldown_flags(loan_history_df, rules_df, "invalid-date")

    def test_most_recent_loan_wins(self):
        """Test: Most recent end_date is used for cooldown calculation."""

        week_start = "2025-09-08"
        old_date = date(2025, 7, 1)    # 2+ months ago
        recent_date = date(2025, 8, 25)  # 14 days ago

        loan_history_df = pd.DataFrame([
            {
                'activity_id': 'ACT001',
                'vin': 'VIN123',
                'person_id': 'P001',
                'make': 'Toyota',
                'model': 'Camry',
                'start_date': old_date - timedelta(days=7),
                'end_date': old_date,  # Older loan
                'clips_received': 5
            },
            {
                'activity_id': 'ACT002',
                'vin': 'VIN456',
                'person_id': 'P001',
                'make': 'Toyota',
                'model': 'Camry',
                'start_date': recent_date - timedelta(days=7),
                'end_date': recent_date,  # More recent loan - should be used
                'clips_received': 3
            }
        ])

        rules_df = pd.DataFrame([
            {'make': 'Toyota', 'cooldown_period_days': 30}
        ])

        result = compute_cooldown_flags(loan_history_df, rules_df, week_start)

        assert len(result) == 1
        row = result.iloc[0]
        assert row['cooldown_ok'] == False  # Based on recent date (14 < 30)
        # cooldown_until should be based on the more recent end_date
        expected_until = recent_date + timedelta(days=30)
        assert row['cooldown_until'] == expected_until