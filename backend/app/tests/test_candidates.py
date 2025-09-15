"""
Tests for candidate generation logic.

Tests cover availability filtering, cooldown constraints, partner eligibility,
and edge cases for the build_weekly_candidates function.
"""

import pandas as pd
import pytest
from datetime import datetime, timedelta

from app.solver.candidates import build_weekly_candidates


class TestBuildWeeklyCandidates:
    """Test suite for build_weekly_candidates function."""

    def setup_method(self):
        """Set up test data for each test."""
        # Base week for testing (Monday)
        self.week_start = "2024-01-08"
        self.week_dates = [(datetime(2024, 1, 8) + timedelta(days=i)).strftime("%Y-%m-%d")
                          for i in range(7)]

        # Sample availability data (VIN1 available all 7 days, VIN2 available 3 days)
        self.availability_df = pd.DataFrame([
            {"vin": "VIN1", "date": "2024-01-08", "market": "SEA", "make": "Toyota", "model": "Camry", "available": True},
            {"vin": "VIN1", "date": "2024-01-09", "market": "SEA", "make": "Toyota", "model": "Camry", "available": True},
            {"vin": "VIN1", "date": "2024-01-10", "market": "SEA", "make": "Toyota", "model": "Camry", "available": True},
            {"vin": "VIN1", "date": "2024-01-11", "market": "SEA", "make": "Toyota", "model": "Camry", "available": True},
            {"vin": "VIN1", "date": "2024-01-12", "market": "SEA", "make": "Toyota", "model": "Camry", "available": True},
            {"vin": "VIN1", "date": "2024-01-13", "market": "SEA", "make": "Toyota", "model": "Camry", "available": True},
            {"vin": "VIN1", "date": "2024-01-14", "market": "SEA", "make": "Toyota", "model": "Camry", "available": True},

            {"vin": "VIN2", "date": "2024-01-08", "market": "LAX", "make": "Honda", "model": "Accord", "available": True},
            {"vin": "VIN2", "date": "2024-01-09", "market": "LAX", "make": "Honda", "model": "Accord", "available": False},
            {"vin": "VIN2", "date": "2024-01-10", "market": "LAX", "make": "Honda", "model": "Accord", "available": True},
            {"vin": "VIN2", "date": "2024-01-11", "market": "LAX", "make": "Honda", "model": "Accord", "available": False},
            {"vin": "VIN2", "date": "2024-01-12", "market": "LAX", "make": "Honda", "model": "Accord", "available": True},
            {"vin": "VIN2", "date": "2024-01-13", "market": "LAX", "make": "Honda", "model": "Accord", "available": False},
            {"vin": "VIN2", "date": "2024-01-14", "market": "LAX", "make": "Honda", "model": "Accord", "available": False},

            {"vin": "VIN3", "date": "2024-01-08", "market": "SFO", "make": "Toyota", "model": "Prius", "available": False},
            {"vin": "VIN3", "date": "2024-01-09", "market": "SFO", "make": "Toyota", "model": "Prius", "available": False},
            {"vin": "VIN3", "date": "2024-01-10", "market": "SFO", "make": "Toyota", "model": "Prius", "available": False},
            {"vin": "VIN3", "date": "2024-01-11", "market": "SFO", "make": "Toyota", "model": "Prius", "available": False},
            {"vin": "VIN3", "date": "2024-01-12", "market": "SFO", "make": "Toyota", "model": "Prius", "available": False},
            {"vin": "VIN3", "date": "2024-01-13", "market": "SFO", "make": "Toyota", "model": "Prius", "available": False},
            {"vin": "VIN3", "date": "2024-01-14", "market": "SFO", "make": "Toyota", "model": "Prius", "available": False},
        ])

        # Sample cooldown data
        self.cooldown_df = pd.DataFrame([
            {"person_id": "P1", "make": "Toyota", "model": "Camry", "cooldown_ok": True},
            {"person_id": "P2", "make": "Toyota", "model": "Camry", "cooldown_ok": False},  # Blocked by cooldown
            {"person_id": "P3", "make": "Honda", "model": "Accord", "cooldown_ok": True},
            {"person_id": "P1", "make": "Toyota", "model": "Prius", "cooldown_ok": True},
            {"person_id": "P4", "make": "Toyota", "model": None, "cooldown_ok": False},  # Fallback case
        ])

        # Sample publication data
        self.publication_df = pd.DataFrame([
            {"person_id": "P1", "make": "Toyota", "loans_total_24m": 10, "loans_observed_24m": 8,
             "publications_observed_24m": 6, "publication_rate_observed": 0.75, "coverage": 0.8, "supported": True},
            {"person_id": "P2", "make": "Toyota", "loans_total_24m": 5, "loans_observed_24m": 5,
             "publications_observed_24m": 2, "publication_rate_observed": 0.40, "coverage": 1.0, "supported": True},
            {"person_id": "P3", "make": "Honda", "loans_total_24m": 12, "loans_observed_24m": 0,
             "publications_observed_24m": 0, "publication_rate_observed": None, "coverage": 0.0, "supported": False},
            {"person_id": "P4", "make": "Ford", "loans_total_24m": 3, "loans_observed_24m": 3,
             "publications_observed_24m": 1, "publication_rate_observed": 0.33, "coverage": 1.0, "supported": False},
        ])

        # Sample eligibility data
        self.eligibility_df = pd.DataFrame([
            {"person_id": "P1", "make": "Toyota"},
            {"person_id": "P2", "make": "Toyota"},
            {"person_id": "P3", "make": "Honda"},
            {"person_id": "P5", "make": "Toyota"},  # No publication history
        ])

    def test_includes_when_available_and_cooldown_ok(self):
        """Test that VIN+partner pairs are included when available and cooldown allows."""
        result = build_weekly_candidates(
            self.availability_df,
            self.cooldown_df,
            self.publication_df,
            self.week_start,
            min_available_days=7
        )

        # VIN1 (Toyota Camry, 7 available days) + P1 (cooldown_ok=True) should be included
        vin1_p1 = result[(result['vin'] == 'VIN1') & (result['person_id'] == 'P1')]
        assert len(vin1_p1) == 1
        assert vin1_p1.iloc[0]['available_days'] == 7
        assert vin1_p1.iloc[0]['cooldown_ok'] == True
        assert vin1_p1.iloc[0]['make'] == 'Toyota'
        assert vin1_p1.iloc[0]['market'] == 'SEA'

    def test_excludes_when_insufficient_availability(self):
        """Test that VINs with insufficient available days are excluded."""
        result = build_weekly_candidates(
            self.availability_df,
            self.cooldown_df,
            self.publication_df,
            self.week_start,
            min_available_days=7
        )

        # VIN2 only has 3 available days, should not appear
        vin2_rows = result[result['vin'] == 'VIN2']
        assert len(vin2_rows) == 0

        # VIN3 has 0 available days, should not appear
        vin3_rows = result[result['vin'] == 'VIN3']
        assert len(vin3_rows) == 0

    def test_excludes_when_cooldown_blocks(self):
        """Test that partner+VIN pairs are excluded when cooldown blocks them."""
        result = build_weekly_candidates(
            self.availability_df,
            self.cooldown_df,
            self.publication_df,
            self.week_start,
            min_available_days=7
        )

        # P2 has cooldown_ok=False for Toyota Camry, should not appear
        vin1_p2 = result[(result['vin'] == 'VIN1') & (result['person_id'] == 'P2')]
        assert len(vin1_p2) == 0

    def test_fallback_cooldown_join_on_make_when_model_missing(self):
        """Test cooldown fallback logic when model is missing."""
        # Create test data with None model in VIN
        availability_test = self.availability_df.copy()
        availability_test.loc[availability_test['vin'] == 'VIN1', 'model'] = None

        result = build_weekly_candidates(
            availability_test,
            self.cooldown_df,
            self.publication_df,
            self.week_start,
            min_available_days=7
        )

        # Should still find matches using (person_id, make) fallback
        vin1_matches = result[result['vin'] == 'VIN1']
        assert len(vin1_matches) > 0

    def test_eligibility_optional_fallbacks_to_publication_history(self):
        """Test that when eligibility_df is None, partners come from publication history."""
        result = build_weekly_candidates(
            self.availability_df,
            self.cooldown_df,
            self.publication_df,
            self.week_start,
            eligibility_df=None,  # No eligibility constraints
            min_available_days=7
        )

        # Should include P1 for Toyota (from publication history)
        vin1_p1 = result[(result['vin'] == 'VIN1') & (result['person_id'] == 'P1')]
        assert len(vin1_p1) == 1

    def test_with_eligibility_constraints(self):
        """Test that eligibility_df properly constrains partner selection."""
        result = build_weekly_candidates(
            self.availability_df,
            self.cooldown_df,
            self.publication_df,
            self.week_start,
            eligibility_df=self.eligibility_df,
            min_available_days=7
        )

        # Only partners in eligibility_df should appear
        all_partners = set(result['person_id'].unique())
        eligible_partners = set(self.eligibility_df['person_id'].unique())

        # All result partners should be in eligible set
        assert all_partners.issubset(eligible_partners)

    def test_output_column_format(self):
        """Test that output has exactly the right columns in the right order."""
        result = build_weekly_candidates(
            self.availability_df,
            self.cooldown_df,
            self.publication_df,
            self.week_start,
            min_available_days=7
        )

        expected_columns = [
            "vin", "person_id", "market", "make", "model", "week_start",
            "available_days", "cooldown_ok", "publication_rate_observed", "supported", "coverage"
        ]

        assert list(result.columns) == expected_columns

    def test_empty_inputs_return_empty_dataframe(self):
        """Test that empty inputs return properly formatted empty DataFrame."""
        empty_availability = pd.DataFrame(columns=['vin', 'date', 'market', 'make', 'model', 'available'])
        empty_cooldown = pd.DataFrame(columns=['person_id', 'make', 'model', 'cooldown_ok'])
        empty_publication = pd.DataFrame(columns=['person_id', 'make', 'publication_rate_observed', 'supported', 'coverage'])

        result = build_weekly_candidates(
            empty_availability,
            empty_cooldown,
            empty_publication,
            self.week_start
        )

        assert len(result) == 0
        assert list(result.columns) == [
            "vin", "person_id", "market", "make", "model", "week_start",
            "available_days", "cooldown_ok", "publication_rate_observed", "supported", "coverage"
        ]

    def test_min_available_days_parameter(self):
        """Test that min_available_days parameter works correctly."""
        # VIN2 has exactly 3 available days
        result_strict = build_weekly_candidates(
            self.availability_df,
            self.cooldown_df,
            self.publication_df,
            self.week_start,
            min_available_days=7  # VIN2 should be excluded
        )

        result_relaxed = build_weekly_candidates(
            self.availability_df,
            self.cooldown_df,
            self.publication_df,
            self.week_start,
            min_available_days=3  # VIN2 should be included
        )

        # VIN2 should not appear in strict mode
        assert len(result_strict[result_strict['vin'] == 'VIN2']) == 0

        # VIN2 should appear in relaxed mode
        assert len(result_relaxed[result_relaxed['vin'] == 'VIN2']) > 0

    def test_publication_data_handling(self):
        """Test that publication data is properly joined and null values handled."""
        result = build_weekly_candidates(
            self.availability_df,
            self.cooldown_df,
            self.publication_df,
            self.week_start,
            min_available_days=7
        )

        # Check that publication rates are properly joined
        p1_rows = result[result['person_id'] == 'P1']
        if len(p1_rows) > 0:
            assert p1_rows.iloc[0]['publication_rate_observed'] == 0.75
            assert p1_rows.iloc[0]['supported'] == True
            assert p1_rows.iloc[0]['coverage'] == 0.8

    def test_function_is_deterministic(self):
        """Test that function produces identical results on identical inputs."""
        result1 = build_weekly_candidates(
            self.availability_df,
            self.cooldown_df,
            self.publication_df,
            self.week_start,
            min_available_days=7
        )

        result2 = build_weekly_candidates(
            self.availability_df,
            self.cooldown_df,
            self.publication_df,
            self.week_start,
            min_available_days=7
        )

        pd.testing.assert_frame_equal(result1, result2)

    def test_week_start_parameter(self):
        """Test that week_start parameter correctly filters to target week."""
        # Test with different week
        different_week = "2024-01-15"

        result = build_weekly_candidates(
            self.availability_df,
            self.cooldown_df,
            self.publication_df,
            different_week,
            min_available_days=1
        )

        # Should return empty since our availability data is for 2024-01-08 week
        assert len(result) == 0

        # Original week should work
        result_original = build_weekly_candidates(
            self.availability_df,
            self.cooldown_df,
            self.publication_df,
            self.week_start,
            min_available_days=7
        )

        assert len(result_original) > 0