"""
Unit tests for the availability grid ETL module.
"""

import pytest
import pandas as pd
from datetime import date, datetime
from app.etl.availability import (
    build_availability_grid,
    parse_date_string,
    generate_week_range,
    is_date_in_lifecycle_window,
    has_overlapping_activity
)


class TestAvailabilityHelpers:
    """Test helper functions."""

    def test_parse_date_string(self):
        """Test date string parsing."""
        # String input
        assert parse_date_string("2025-01-13") == date(2025, 1, 13)

        # Date object input (passthrough)
        test_date = date(2025, 1, 13)
        assert parse_date_string(test_date) == test_date

        # DateTime input
        test_datetime = datetime(2025, 1, 13, 10, 30)
        assert parse_date_string(test_datetime) == date(2025, 1, 13)

    def test_generate_week_range(self):
        """Test 7-day week generation."""
        week_days = generate_week_range("2025-01-13")  # Monday
        expected_days = [
            date(2025, 1, 13),  # Mon
            date(2025, 1, 14),  # Tue
            date(2025, 1, 15),  # Wed
            date(2025, 1, 16),  # Thu
            date(2025, 1, 17),  # Fri
            date(2025, 1, 18),  # Sat
            date(2025, 1, 19),  # Sun
        ]
        assert week_days == expected_days

    def test_is_date_in_lifecycle_window(self):
        """Test lifecycle window logic."""
        target = date(2025, 1, 15)  # Wednesday

        # No constraints (both None) - should be available
        assert is_date_in_lifecycle_window(target, None, None) == True

        # Only in_service_date constraint
        assert is_date_in_lifecycle_window(target, date(2025, 1, 10), None) == True  # After in-service
        assert is_date_in_lifecycle_window(target, date(2025, 1, 20), None) == False  # Before in-service

        # Only expected_turn_in_date constraint
        assert is_date_in_lifecycle_window(target, None, date(2025, 1, 20)) == True  # Before turn-in
        assert is_date_in_lifecycle_window(target, None, date(2025, 1, 10)) == False  # After turn-in

        # Both constraints - in window
        assert is_date_in_lifecycle_window(target, date(2025, 1, 10), date(2025, 1, 20)) == True

        # Both constraints - before window
        assert is_date_in_lifecycle_window(target, date(2025, 1, 16), date(2025, 1, 20)) == False

        # Both constraints - after window
        assert is_date_in_lifecycle_window(target, date(2025, 1, 10), date(2025, 1, 14)) == False

    def test_has_overlapping_activity(self):
        """Test activity overlap detection."""
        # Empty activity DataFrame
        empty_df = pd.DataFrame()
        assert has_overlapping_activity("VIN123", date(2025, 1, 15), empty_df) == False

        # Activity DataFrame with overlapping service
        activity_df = pd.DataFrame([
            {
                'vin': 'VIN123',
                'activity_type': 'service',
                'start_date': date(2025, 1, 14),
                'end_date': date(2025, 1, 16)
            },
            {
                'vin': 'VIN456',
                'activity_type': 'loan',
                'start_date': date(2025, 1, 10),
                'end_date': date(2025, 1, 12)
            }
        ])

        # Target date overlaps with VIN123 service
        assert has_overlapping_activity("VIN123", date(2025, 1, 15), activity_df) == True

        # Target date doesn't overlap with VIN456 loan
        assert has_overlapping_activity("VIN456", date(2025, 1, 15), activity_df) == False

        # Non-existent VIN
        assert has_overlapping_activity("VIN999", date(2025, 1, 15), activity_df) == False


class TestBuildAvailabilityGrid:
    """Test the main availability grid builder."""

    def test_no_activities_all_available(self):
        """Test: No activities → all VINs available for all 7 days."""
        # Setup test data - 2 VINs, no activities, no lifecycle constraints
        vehicles_df = pd.DataFrame([
            {'vin': 'VIN001', 'office': 'Austin', 'in_service_date': None, 'expected_turn_in_date': None},
            {'vin': 'VIN002', 'office': 'Austin', 'in_service_date': None, 'expected_turn_in_date': None}
        ])

        activity_df = pd.DataFrame()  # No activities

        result = build_availability_grid(vehicles_df, activity_df, "2025-01-13", "Austin")

        # Should have exactly 14 rows (2 VINs × 7 days)
        assert len(result) == 14

        # All should be available
        assert result['available'].all() == True

        # Check columns and data types
        expected_columns = ['vin', 'day', 'office', 'available']
        assert list(result.columns) == expected_columns

        # Check office is consistent
        assert (result['office'] == 'Austin').all()

        # Check we have both VINs
        vins = result['vin'].unique()
        assert set(vins) == {'VIN001', 'VIN002'}

        # Check we have all 7 days for each VIN
        for vin in vins:
            vin_days = result[result['vin'] == vin]['day'].tolist()
            assert len(vin_days) == 7

    def test_service_activity_blocks_specific_days(self):
        """Test: Service spanning Tue–Wed blocks those days for specific VIN only."""
        # Setup test data
        vehicles_df = pd.DataFrame([
            {'vin': 'VIN001', 'office': 'Austin', 'in_service_date': None, 'expected_turn_in_date': None},
            {'vin': 'VIN002', 'office': 'Austin', 'in_service_date': None, 'expected_turn_in_date': None}
        ])

        # Service activity for VIN001 spanning Tuesday–Wednesday
        activity_df = pd.DataFrame([
            {
                'vin': 'VIN001',
                'activity_type': 'service',
                'start_date': date(2025, 1, 14),  # Tuesday
                'end_date': date(2025, 1, 15)     # Wednesday
            }
        ])

        result = build_availability_grid(vehicles_df, activity_df, "2025-01-13", "Austin")

        # Should have exactly 14 rows (2 VINs × 7 days)
        assert len(result) == 14

        # Check VIN001 availability - should be blocked on Tue/Wed only
        vin001_result = result[result['vin'] == 'VIN001'].copy()
        vin001_result = vin001_result.set_index('day')

        assert vin001_result.loc[date(2025, 1, 13)]['available'] == True   # Mon - available
        assert vin001_result.loc[date(2025, 1, 14)]['available'] == False  # Tue - service
        assert vin001_result.loc[date(2025, 1, 15)]['available'] == False  # Wed - service
        assert vin001_result.loc[date(2025, 1, 16)]['available'] == True   # Thu - available
        assert vin001_result.loc[date(2025, 1, 17)]['available'] == True   # Fri - available

        # Check VIN002 availability - should be all available (not affected by VIN001's service)
        vin002_result = result[result['vin'] == 'VIN002']
        assert vin002_result['available'].all() == True

    def test_lifecycle_window_expected_turn_in(self):
        """Test: expected_turn_in_date = Thursday blocks Fri–Sun for specific VIN."""
        # Setup test data
        vehicles_df = pd.DataFrame([
            {
                'vin': 'VIN001',
                'office': 'Austin',
                'in_service_date': None,
                'expected_turn_in_date': date(2025, 1, 16)  # Thursday
            },
            {
                'vin': 'VIN002',
                'office': 'Austin',
                'in_service_date': None,
                'expected_turn_in_date': None
            }
        ])

        activity_df = pd.DataFrame()  # No activities

        result = build_availability_grid(vehicles_df, activity_df, "2025-01-13", "Austin")

        # Check VIN001 availability - should be blocked after Thursday
        vin001_result = result[result['vin'] == 'VIN001'].copy()
        vin001_result = vin001_result.set_index('day')

        assert vin001_result.loc[date(2025, 1, 13)]['available'] == True   # Mon - available
        assert vin001_result.loc[date(2025, 1, 14)]['available'] == True   # Tue - available
        assert vin001_result.loc[date(2025, 1, 15)]['available'] == True   # Wed - available
        assert vin001_result.loc[date(2025, 1, 16)]['available'] == True   # Thu - available (turn-in day)
        assert vin001_result.loc[date(2025, 1, 17)]['available'] == False  # Fri - after turn-in
        assert vin001_result.loc[date(2025, 1, 18)]['available'] == False  # Sat - after turn-in
        assert vin001_result.loc[date(2025, 1, 19)]['available'] == False  # Sun - after turn-in

        # Check VIN002 availability - should be all available (no lifecycle constraints)
        vin002_result = result[result['vin'] == 'VIN002']
        assert vin002_result['available'].all() == True

    def test_lifecycle_window_in_service_date(self):
        """Test: in_service_date blocks days before service starts."""
        # Setup test data
        vehicles_df = pd.DataFrame([
            {
                'vin': 'VIN001',
                'office': 'Austin',
                'in_service_date': date(2025, 1, 15),  # Wednesday
                'expected_turn_in_date': None
            }
        ])

        activity_df = pd.DataFrame()

        result = build_availability_grid(vehicles_df, activity_df, "2025-01-13", "Austin")

        # Check availability - should be blocked before Wednesday
        vin_result = result.set_index('day')

        assert vin_result.loc[date(2025, 1, 13)]['available'] == False  # Mon - before service
        assert vin_result.loc[date(2025, 1, 14)]['available'] == False  # Tue - before service
        assert vin_result.loc[date(2025, 1, 15)]['available'] == True   # Wed - service date
        assert vin_result.loc[date(2025, 1, 16)]['available'] == True   # Thu - after service
        assert vin_result.loc[date(2025, 1, 17)]['available'] == True   # Fri - after service

    def test_missing_lifecycle_dates_open_ended(self):
        """Test: Missing lifecycle dates don't cause unintended blocking."""
        # Setup test data with None/NaN values
        vehicles_df = pd.DataFrame([
            {'vin': 'VIN001', 'office': 'Austin', 'in_service_date': None, 'expected_turn_in_date': None},
            {'vin': 'VIN002', 'office': 'Austin', 'in_service_date': pd.NaT, 'expected_turn_in_date': pd.NaT}
        ])

        activity_df = pd.DataFrame()

        result = build_availability_grid(vehicles_df, activity_df, "2025-01-13", "Austin")

        # All should be available since no constraints
        assert result['available'].all() == True

    def test_output_format_exact(self):
        """Test: Output has exactly 7 × (# VINs in office) rows with correct columns."""
        # Setup with 3 VINs in target office, 2 VINs in different office
        vehicles_df = pd.DataFrame([
            {'vin': 'VIN001', 'office': 'Austin', 'in_service_date': None, 'expected_turn_in_date': None},
            {'vin': 'VIN002', 'office': 'Austin', 'in_service_date': None, 'expected_turn_in_date': None},
            {'vin': 'VIN003', 'office': 'Austin', 'in_service_date': None, 'expected_turn_in_date': None},
            {'vin': 'VIN004', 'office': 'Dallas', 'in_service_date': None, 'expected_turn_in_date': None},
            {'vin': 'VIN005', 'office': 'Dallas', 'in_service_date': None, 'expected_turn_in_date': None}
        ])

        activity_df = pd.DataFrame()

        result = build_availability_grid(vehicles_df, activity_df, "2025-01-13", "Austin")

        # Should have exactly 21 rows (3 Austin VINs × 7 days)
        assert len(result) == 21

        # Check exact columns
        expected_columns = ['vin', 'day', 'office', 'available']
        assert list(result.columns) == expected_columns

        # Check data types
        assert result['vin'].dtype == 'object'
        assert result['office'].dtype == 'object'
        assert result['available'].dtype == 'bool'

        # Check only Austin VINs are included
        austin_vins = result['vin'].unique()
        assert set(austin_vins) == {'VIN001', 'VIN002', 'VIN003'}

        # Check all office entries are 'Austin'
        assert (result['office'] == 'Austin').all()

        # Check each VIN has exactly 7 days
        for vin in austin_vins:
            vin_rows = result[result['vin'] == vin]
            assert len(vin_rows) == 7

    def test_complex_scenario(self):
        """Test: Combined lifecycle constraints and activities."""
        # Setup complex scenario
        vehicles_df = pd.DataFrame([
            {
                'vin': 'VIN001',
                'office': 'Austin',
                'in_service_date': date(2025, 1, 14),     # Tue
                'expected_turn_in_date': date(2025, 1, 17) # Fri
            },
            {
                'vin': 'VIN002',
                'office': 'Austin',
                'in_service_date': None,
                'expected_turn_in_date': None
            }
        ])

        # VIN002 has loan activity Wed-Thu
        activity_df = pd.DataFrame([
            {
                'vin': 'VIN002',
                'activity_type': 'loan',
                'start_date': date(2025, 1, 15),  # Wed
                'end_date': date(2025, 1, 16)     # Thu
            }
        ])

        result = build_availability_grid(vehicles_df, activity_df, "2025-01-13", "Austin")

        # Check VIN001 - lifecycle window Tue-Fri
        vin001_result = result[result['vin'] == 'VIN001'].copy()
        vin001_result = vin001_result.set_index('day')

        assert vin001_result.loc[date(2025, 1, 13)]['available'] == False  # Mon - before service
        assert vin001_result.loc[date(2025, 1, 14)]['available'] == True   # Tue - in service
        assert vin001_result.loc[date(2025, 1, 15)]['available'] == True   # Wed - in service
        assert vin001_result.loc[date(2025, 1, 16)]['available'] == True   # Thu - in service
        assert vin001_result.loc[date(2025, 1, 17)]['available'] == True   # Fri - turn-in day
        assert vin001_result.loc[date(2025, 1, 18)]['available'] == False  # Sat - after turn-in
        assert vin001_result.loc[date(2025, 1, 19)]['available'] == False  # Sun - after turn-in

        # Check VIN002 - blocked by loan Wed-Thu only
        vin002_result = result[result['vin'] == 'VIN002'].copy()
        vin002_result = vin002_result.set_index('day')

        assert vin002_result.loc[date(2025, 1, 13)]['available'] == True   # Mon - available
        assert vin002_result.loc[date(2025, 1, 14)]['available'] == True   # Tue - available
        assert vin002_result.loc[date(2025, 1, 15)]['available'] == False  # Wed - loan
        assert vin002_result.loc[date(2025, 1, 16)]['available'] == False  # Thu - loan
        assert vin002_result.loc[date(2025, 1, 17)]['available'] == True   # Fri - available
        assert vin002_result.loc[date(2025, 1, 18)]['available'] == True   # Sat - available
        assert vin002_result.loc[date(2025, 1, 19)]['available'] == True   # Sun - available

    def test_non_blocking_activity_types(self):
        """Test: Non-blocking activity types don't affect availability."""
        vehicles_df = pd.DataFrame([
            {'vin': 'VIN001', 'office': 'Austin', 'in_service_date': None, 'expected_turn_in_date': None}
        ])

        # Activity with non-blocking type
        activity_df = pd.DataFrame([
            {
                'vin': 'VIN001',
                'activity_type': 'inspection',  # Not in blocking set
                'start_date': date(2025, 1, 15),
                'end_date': date(2025, 1, 16)
            }
        ])

        result = build_availability_grid(vehicles_df, activity_df, "2025-01-13", "Austin")

        # Should all be available since 'inspection' doesn't block
        assert result['available'].all() == True