"""
Unit tests for the NULL-aware publication rate ETL module.
"""

import pytest
import pandas as pd
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from app.etl.publication import compute_publication_rate_24m


class TestNullAwarePublicationRate:
    """Test the NULL-aware publication rate computation."""

    def test_nulls_do_not_tank_rate(self):
        """Test: NULL clips don't tank the rate - two loans total; one known published, one unknown."""

        lh = pd.DataFrame([
            {"activity_id": "1", "person_id": "1", "make": "Toyota", "start_date": "2025-05-01", "end_date": "2025-05-02", "clips_received": True},
            {"activity_id": "2", "person_id": "1", "make": "Toyota", "start_date": "2025-06-01", "end_date": "2025-06-02", "clips_received": None},
        ])

        out = compute_publication_rate_24m(lh, "2025-09-14", min_observed=1)
        row = out.iloc[0]

        assert row.loans_total_24m == 2
        assert row.loans_observed_24m == 1
        assert row.publications_observed_24m == 1
        assert abs(row.publication_rate_observed - 1.0) < 1e-9
        assert 0.5 - 1e-9 <= row.coverage <= 0.5 + 1e-9

    def test_supported_flag_uses_observed_only(self):
        """Test: Supported flag based on observed loans only."""

        lh = pd.DataFrame([
            {"activity_id": "1", "person_id": "2", "make": "Honda", "start_date": "2025-01-01", "end_date": "2025-01-02", "clips_received": True},
            {"activity_id": "2", "person_id": "2", "make": "Honda", "start_date": "2025-02-01", "end_date": "2025-02-02", "clips_received": None},
            {"activity_id": "3", "person_id": "2", "make": "Honda", "start_date": "2025-03-01", "end_date": "2025-03-02", "clips_received": False},
        ])

        out = compute_publication_rate_24m(lh, "2025-09-14", min_observed=2)
        row = out.iloc[0]

        assert row.loans_total_24m == 3
        assert row.loans_observed_24m == 2  # True and False, not None
        assert bool(row.supported) == True  # 2 >= min_observed(2)

    def test_basic_ratio_with_new_schema(self):
        """Test: Basic ratio with new output schema."""

        as_of_date = "2025-09-14"
        base_date = date(2025, 8, 1)

        loan_history_df = pd.DataFrame([
            {
                'activity_id': 'ACT001',
                'person_id': 'P001',
                'make': 'Toyota',
                'end_date': base_date,
                'clips_received': True
            },
            {
                'activity_id': 'ACT002',
                'person_id': 'P001',
                'make': 'Toyota',
                'end_date': base_date + timedelta(days=10),
                'clips_received': True
            },
            {
                'activity_id': 'ACT003',
                'person_id': 'P001',
                'make': 'Toyota',
                'end_date': base_date + timedelta(days=20),
                'clips_received': False
            }
        ])

        result = compute_publication_rate_24m(loan_history_df, as_of_date)

        assert len(result) == 1
        row = result.iloc[0]
        assert row['person_id'] == 'P001'
        assert row['make'] == 'Toyota'
        assert row['loans_total_24m'] == 3
        assert row['loans_observed_24m'] == 3  # All have non-NULL clips_received
        assert row['publications_observed_24m'] == 2
        assert abs(row['publication_rate_observed'] - 2/3) < 1e-6
        assert row['coverage'] == 1.0  # 100% coverage
        assert bool(row['supported']) == True  # 3 >= min_observed(3)

    def test_partial_coverage(self):
        """Test: Partial coverage scenario with mix of NULL and observed values."""

        as_of_date = "2025-09-14"
        base_date = date(2025, 8, 1)

        loan_history_df = pd.DataFrame([
            # 5 total loans
            {'activity_id': 'ACT001', 'person_id': 'P001', 'make': 'Toyota', 'end_date': base_date, 'clips_received': True},
            {'activity_id': 'ACT002', 'person_id': 'P001', 'make': 'Toyota', 'end_date': base_date + timedelta(days=5), 'clips_received': False},
            {'activity_id': 'ACT003', 'person_id': 'P001', 'make': 'Toyota', 'end_date': base_date + timedelta(days=10), 'clips_received': None},
            {'activity_id': 'ACT004', 'person_id': 'P001', 'make': 'Toyota', 'end_date': base_date + timedelta(days=15), 'clips_received': None},
            {'activity_id': 'ACT005', 'person_id': 'P001', 'make': 'Toyota', 'end_date': base_date + timedelta(days=20), 'clips_received': True},
        ])

        result = compute_publication_rate_24m(loan_history_df, as_of_date, min_observed=3)

        assert len(result) == 1
        row = result.iloc[0]
        assert row['loans_total_24m'] == 5
        assert row['loans_observed_24m'] == 3  # Only non-NULL values
        assert row['publications_observed_24m'] == 2  # 2 True values
        assert abs(row['publication_rate_observed'] - 2/3) < 1e-6  # 2/3 = 66.7%
        assert row['coverage'] == 0.6  # 3/5 = 60% coverage
        assert bool(row['supported']) == True  # 3 >= min_observed(3)

    def test_insufficient_observed_data(self):
        """Test: Insufficient observed data results in supported=False."""

        as_of_date = "2025-09-14"
        base_date = date(2025, 8, 1)

        loan_history_df = pd.DataFrame([
            # Only 2 observed loans, but min_observed=3
            {'activity_id': 'ACT001', 'person_id': 'P001', 'make': 'Toyota', 'end_date': base_date, 'clips_received': True},
            {'activity_id': 'ACT002', 'person_id': 'P001', 'make': 'Toyota', 'end_date': base_date + timedelta(days=5), 'clips_received': False},
            {'activity_id': 'ACT003', 'person_id': 'P001', 'make': 'Toyota', 'end_date': base_date + timedelta(days=10), 'clips_received': None},
            {'activity_id': 'ACT004', 'person_id': 'P001', 'make': 'Toyota', 'end_date': base_date + timedelta(days=15), 'clips_received': None},
        ])

        result = compute_publication_rate_24m(loan_history_df, as_of_date, min_observed=3)

        assert len(result) == 1
        row = result.iloc[0]
        assert row['loans_total_24m'] == 4
        assert row['loans_observed_24m'] == 2  # Only 2 non-NULL
        assert row['publications_observed_24m'] == 1
        assert row['publication_rate_observed'] == 0.5  # 1/2 = 50%
        assert row['coverage'] == 0.5  # 2/4 = 50% coverage
        assert bool(row['supported']) == False  # 2 < min_observed(3)

    def test_empty_dataframe_new_schema(self):
        """Test: Empty input DataFrame returns empty result with correct columns."""

        empty_df = pd.DataFrame(columns=['activity_id', 'person_id', 'make', 'end_date', 'clips_received'])

        result = compute_publication_rate_24m(empty_df, "2025-09-14")

        assert len(result) == 0
        expected_columns = ['person_id', 'make', 'loans_total_24m', 'loans_observed_24m', 'publications_observed_24m',
                           'publication_rate_observed', 'coverage', 'supported', 'window_start', 'window_end']
        assert list(result.columns) == expected_columns

    def test_all_null_clips(self):
        """Test: All NULL clips_received values result in rate=None, coverage=0."""

        as_of_date = "2025-09-14"
        base_date = date(2025, 8, 1)

        loan_history_df = pd.DataFrame([
            {'activity_id': 'ACT001', 'person_id': 'P001', 'make': 'Toyota', 'end_date': base_date, 'clips_received': None},
            {'activity_id': 'ACT002', 'person_id': 'P001', 'make': 'Toyota', 'end_date': base_date + timedelta(days=10), 'clips_received': None},
            {'activity_id': 'ACT003', 'person_id': 'P001', 'make': 'Toyota', 'end_date': base_date + timedelta(days=20), 'clips_received': None},
        ])

        result = compute_publication_rate_24m(loan_history_df, as_of_date)

        assert len(result) == 1
        row = result.iloc[0]
        assert row['loans_total_24m'] == 3
        assert row['loans_observed_24m'] == 0  # All NULL
        assert row['publications_observed_24m'] == 0
        assert row['publication_rate_observed'] is None  # No observed data
        assert row['coverage'] == 0.0  # 0% coverage
        assert bool(row['supported']) == False  # 0 < min_observed