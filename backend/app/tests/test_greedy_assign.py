"""
Tests for greedy assignment algorithm.

Tests cover scoring-based assignment, constraint enforcement, and edge cases
for the generate_week_schedule function.
"""

import pandas as pd
import pytest

from app.solver.greedy_assign import generate_week_schedule, DEFAULT_TIER_CAPS


def _mk(df):
    """Helper to create DataFrame from list of dicts."""
    return pd.DataFrame(df)


class TestGenerateWeekSchedule:
    """Test suite for generate_week_schedule function."""

    def test_picks_highest_score_and_no_double_booking(self):
        """Test that highest scoring candidate gets the VIN and no double-booking occurs."""
        c = _mk([
            {"vin": "v1", "person_id": 1, "market": "LA", "make": "Toyota", "model": "Camry", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "A", "score": 70},
            {"vin": "v1", "person_id": 2, "market": "LA", "make": "Toyota", "model": "Camry", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "A+", "score": 100},
        ])
        lh = _mk([])
        ops = _mk([{"office": "LA", "drivers_per_day": 10}])
        out = generate_week_schedule(c, lh, ops, office="LA", week_start="2025-09-08")

        # v1 should be assigned once to pid=2 (higher score)
        assert set((r["vin"], r["person_id"]) for _, r in out.iterrows()) == {("v1", 2)}
        assert len(out) == 7  # 7 daily rows

    def test_enforces_tier_caps(self):
        """Test that tier caps prevent assignments when 12-month limit is reached."""
        c = _mk([
            {"vin": "v1", "person_id": 10, "market": "LA", "make": "Mazda", "model": "CX-5", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "B", "score": 40},
            {"vin": "v2", "person_id": 10, "market": "LA", "make": "Mazda", "model": "CX-50", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "B", "score": 40},
            {"vin": "v3", "person_id": 10, "market": "LA", "make": "Mazda", "model": "CX-90", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "B", "score": 40},
        ])
        # partner 10 already has 2 Mazda loans in last 12m -> cap for B is 2, so zero room
        lh = _mk([
            {"person_id": 10, "make": "Mazda", "start_date": "2025-05-01", "end_date": "2025-05-07"},
            {"person_id": 10, "make": "Mazda", "start_date": "2025-03-01", "end_date": "2025-03-07"},
        ])
        ops = _mk([{"office": "LA", "drivers_per_day": 10}])
        out = generate_week_schedule(c, lh, ops, office="LA", week_start="2025-09-08")
        assert out.empty  # cap blocks all three

    def test_enforces_daily_capacity(self):
        """Test that daily capacity limits are enforced."""
        c = _mk([
            {"vin": "v1", "person_id": 1, "market": "LA", "make": "Toyota", "model": "RAV4", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "A", "score": 70},
            {"vin": "v2", "person_id": 2, "market": "LA", "make": "Toyota", "model": "Camry", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "A", "score": 70},
        ])
        lh = _mk([])
        ops = _mk([{"office": "LA", "drivers_per_day": 1}])  # only one per day
        out = generate_week_schedule(c, lh, ops, office="LA", week_start="2025-09-08")

        # only the first (by deterministic tie-break) should fill the entire week
        pairs = set((r["vin"], r["person_id"]) for _, r in out.iterrows())
        assert len(pairs) == 1
        assert len(out) == 7

    def test_filters_by_office_and_cooldown(self):
        """Test that only candidates from target office with cooldown_ok=True are considered."""
        c = _mk([
            {"vin": "v1", "person_id": 1, "market": "SF", "make": "Toyota", "model": "Camry", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "A", "score": 90},  # Wrong office
            {"vin": "v2", "person_id": 2, "market": "LA", "make": "Honda", "model": "Accord", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": False, "rank": "A", "score": 85},  # Cooldown blocked
            {"vin": "v3", "person_id": 3, "market": "LA", "make": "Mazda", "model": "CX-5", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "A", "score": 80},  # Valid
        ])
        lh = _mk([])
        ops = _mk([{"office": "LA", "drivers_per_day": 10}])
        out = generate_week_schedule(c, lh, ops, office="LA", week_start="2025-09-08")

        # Only v3 should be assigned (correct office + cooldown_ok)
        assert set((r["vin"], r["person_id"]) for _, r in out.iterrows()) == {("v3", 3)}
        assert len(out) == 7

    def test_deterministic_sorting(self):
        """Test that sorting is deterministic for tie-breaking."""
        c = _mk([
            {"vin": "v2", "person_id": 2, "market": "LA", "make": "Toyota", "model": "Camry", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "A", "score": 70},
            {"vin": "v1", "person_id": 1, "market": "LA", "make": "Toyota", "model": "Camry", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "A", "score": 70},  # Same score
        ])
        lh = _mk([])
        ops = _mk([{"office": "LA", "drivers_per_day": 10}])
        out = generate_week_schedule(c, lh, ops, office="LA", week_start="2025-09-08")

        # With identical scores and sufficient capacity, both should be assigned (different VINs)
        # But deterministic ordering should be consistent
        assignments = set((r["vin"], r["person_id"]) for _, r in out.iterrows())
        assert len(assignments) == 2  # Both different VINs should be assigned
        assert ("v1", 1) in assignments
        assert ("v2", 2) in assignments

    def test_tier_cap_edge_cases(self):
        """Test tier cap edge cases and rank fallbacks."""
        c = _mk([
            {"vin": "v1", "person_id": 1, "market": "LA", "make": "Toyota", "model": "Camry", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "UNKNOWN", "score": 50},  # Unknown rank
            {"vin": "v2", "person_id": 2, "market": "LA", "make": "Honda", "model": "Accord", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "A+", "score": 100},  # A+ rank (high cap)
        ])
        lh = _mk([])
        ops = _mk([{"office": "LA", "drivers_per_day": 10}])
        out = generate_week_schedule(c, lh, ops, office="LA", week_start="2025-09-08")

        # v2 (A+ rank) should be assigned, v1 (UNKNOWN→C rank, cap=0) should be blocked
        assert set((r["vin"], r["person_id"]) for _, r in out.iterrows()) == {("v2", 2)}

    def test_multiple_assignments_within_constraints(self):
        """Test multiple assignments when constraints allow."""
        c = _mk([
            {"vin": "v1", "person_id": 1, "market": "LA", "make": "Toyota", "model": "Camry", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "A", "score": 90},
            {"vin": "v2", "person_id": 2, "market": "LA", "make": "Honda", "model": "Accord", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "A", "score": 80},
            {"vin": "v3", "person_id": 3, "market": "LA", "make": "Mazda", "model": "CX-5", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "B", "score": 70},
        ])
        lh = _mk([])  # No historical loans
        ops = _mk([{"office": "LA", "drivers_per_day": 10}])  # High capacity
        out = generate_week_schedule(c, lh, ops, office="LA", week_start="2025-09-08")

        # All three should be assigned (sufficient capacity and tier limits)
        assignments = set((r["vin"], r["person_id"]) for _, r in out.iterrows())
        assert assignments == {("v1", 1), ("v2", 2), ("v3", 3)}
        assert len(out) == 21  # 3 VINs × 7 days

    def test_empty_inputs_return_empty_schedule(self):
        """Test that empty inputs return properly formatted empty DataFrame."""
        empty_candidates = _mk([])
        lh = _mk([])
        ops = _mk([{"office": "LA", "drivers_per_day": 10}])
        out = generate_week_schedule(empty_candidates, lh, ops, office="LA", week_start="2025-09-08")

        assert out.empty
        assert list(out.columns) == ["vin", "person_id", "day", "office", "make", "model", "score", "flags"]

    def test_missing_office_capacity_uses_default(self):
        """Test that missing office capacity defaults to high limit."""
        c = _mk([
            {"vin": "v1", "person_id": 1, "market": "UNKNOWN", "make": "Toyota", "model": "Camry", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "A", "score": 70}
        ])
        lh = _mk([])
        empty_ops = _mk([])  # No capacity data
        out = generate_week_schedule(c, lh, empty_ops, office="UNKNOWN", week_start="2025-09-08")

        # Should still work with default capacity (999)
        assert len(out) == 7

    def test_output_column_format(self):
        """Test that output has exactly the right columns in the right order."""
        c = _mk([
            {"vin": "v1", "person_id": 1, "market": "LA", "make": "Toyota", "model": "Camry", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "A", "score": 70}
        ])
        lh = _mk([])
        ops = _mk([{"office": "LA", "drivers_per_day": 10}])
        out = generate_week_schedule(c, lh, ops, office="LA", week_start="2025-09-08")

        expected_columns = ["vin", "person_id", "day", "office", "make", "model", "score", "flags"]
        assert list(out.columns) == expected_columns

    def test_flags_format(self):
        """Test that flags are properly formatted as pipe-separated string."""
        c = _mk([
            {"vin": "v1", "person_id": 1, "market": "LA", "make": "Toyota", "model": "Camry", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "A", "score": 70}
        ])
        lh = _mk([])
        ops = _mk([{"office": "LA", "drivers_per_day": 10}])
        out = generate_week_schedule(c, lh, ops, office="LA", week_start="2025-09-08")

        if not out.empty:
            flags = out.iloc[0]["flags"]
            assert flags == "tier_ok|capacity_ok|cooldown_ok|availability_ok"

    def test_week_days_generation(self):
        """Test that exactly 7 days are generated starting from Monday."""
        c = _mk([
            {"vin": "v1", "person_id": 1, "market": "LA", "make": "Toyota", "model": "Camry", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "A", "score": 70}
        ])
        lh = _mk([])
        ops = _mk([{"office": "LA", "drivers_per_day": 10}])
        out = generate_week_schedule(c, lh, ops, office="LA", week_start="2025-09-08")

        assert len(out) == 7  # Exactly 7 days
        days = sorted(out["day"].unique())
        expected_days = ["2025-09-08", "2025-09-09", "2025-09-10", "2025-09-11", "2025-09-12", "2025-09-13", "2025-09-14"]
        assert days == expected_days

    def test_custom_tier_caps(self):
        """Test that custom tier caps are respected."""
        c = _mk([
            {"vin": "v1", "person_id": 1, "market": "LA", "make": "Toyota", "model": "Camry", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "A", "score": 70},
            {"vin": "v2", "person_id": 1, "market": "LA", "make": "Toyota", "model": "RAV4", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "A", "score": 70},
        ])
        # Partner 1 has 1 Toyota loan in last 12m
        lh = _mk([
            {"person_id": 1, "make": "Toyota", "start_date": "2025-05-01", "end_date": "2025-05-07"}
        ])
        ops = _mk([{"office": "LA", "drivers_per_day": 10}])

        # Custom cap: A rank only gets 1 Toyota per 12m (vs default 6)
        custom_caps = {"A+": 999, "A": 1, "B": 2, "C": 0}
        out = generate_week_schedule(c, lh, ops, office="LA", week_start="2025-09-08", rank_caps=custom_caps)

        # Should be empty because partner 1 already has 1/1 Toyota loans
        assert out.empty

    def test_function_is_deterministic(self):
        """Test that function produces identical results on identical inputs."""
        c = _mk([
            {"vin": "v1", "person_id": 1, "market": "LA", "make": "Toyota", "model": "Camry", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "A", "score": 70},
            {"vin": "v2", "person_id": 2, "market": "LA", "make": "Honda", "model": "Accord", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "B", "score": 60},
        ])
        lh = _mk([])
        ops = _mk([{"office": "LA", "drivers_per_day": 5}])

        result1 = generate_week_schedule(c, lh, ops, office="LA", week_start="2025-09-08")
        result2 = generate_week_schedule(c, lh, ops, office="LA", week_start="2025-09-08")

        pd.testing.assert_frame_equal(result1, result2)

    def test_handles_missing_rank(self):
        """Test that missing rank defaults to 'C' with appropriate cap."""
        c = _mk([
            {"vin": "v1", "person_id": 1, "market": "LA", "make": "Toyota", "model": "Camry", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": None, "score": 70}
        ])
        lh = _mk([])
        ops = _mk([{"office": "LA", "drivers_per_day": 10}])
        out = generate_week_schedule(c, lh, ops, office="LA", week_start="2025-09-08")

        # Should be empty because None rank → "C" → cap=0
        assert out.empty

    def test_12_month_window_calculation(self):
        """Test that 12-month window is calculated correctly."""
        c = _mk([
            {"vin": "v1", "person_id": 1, "market": "LA", "make": "Toyota", "model": "Camry", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "A", "score": 70}
        ])

        # Loan from 13 months ago (should NOT count toward cap)
        lh = _mk([
            {"person_id": 1, "make": "Toyota", "start_date": "2024-08-01", "end_date": "2024-08-07"}  # 13+ months ago
        ])
        ops = _mk([{"office": "LA", "drivers_per_day": 10}])
        out = generate_week_schedule(c, lh, ops, office="LA", week_start="2025-09-08")

        # Should be assigned because old loan doesn't count
        assert len(out) == 7

    def test_dynamic_tier_cap_uses_make_and_rank(self):
        """Test that dynamic tier caps use make+rank from rules table."""
        cand = pd.DataFrame([
            {"vin": "v1", "person_id": 101, "market": "LA", "make": "Toyota", "model": "RAV4", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "A", "score": 70},
            {"vin": "v2", "person_id": 101, "market": "LA", "make": "Toyota", "model": "Camry", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "A", "score": 69},
            {"vin": "v3", "person_id": 101, "market": "LA", "make": "Toyota", "model": "Prius", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "A", "score": 68},
        ])
        lh = pd.DataFrame([])  # no historical usage
        ops = pd.DataFrame([{"office": "LA", "drivers_per_day": 10}])

        # RULES per make+rank: Toyota/A cap=2
        rules = pd.DataFrame([{"make": "Toyota", "rank": "A", "loan_cap_per_year": 2}])

        out = generate_week_schedule(cand, lh, ops, office="LA", week_start="2025-09-08", rules_df=rules)
        # only 2 assignments allowed for (101, Toyota) despite 3 candidates
        pairs = sorted(set((r["vin"], r["person_id"]) for _, r in out.iterrows()))
        assert len(pairs) == 2

    def test_dynamic_tier_cap_zero_or_null_blocks_assignments(self):
        """Test that zero or null caps block all assignments."""
        cand = pd.DataFrame([
            {"vin": "v1", "person_id": 202, "market": "LA", "make": "Mazda", "model": "CX-5", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "B", "score": 50},
            {"vin": "v2", "person_id": 202, "market": "LA", "make": "Mazda", "model": "CX-50", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "B", "score": 49},
        ])
        lh = pd.DataFrame([])
        ops = pd.DataFrame([{"office": "LA", "drivers_per_day": 10}])

        # 0 ⇒ no assignments
        rules0 = pd.DataFrame([{"make": "Mazda", "rank": "B", "loan_cap_per_year": 0}])
        out0 = generate_week_schedule(cand, lh, ops, office="LA", week_start="2025-09-08", rules_df=rules0)
        assert len(out0) == 0

        # NULL ⇒ no assignments
        rulesN = pd.DataFrame([{"make": "Mazda", "rank": "B", "loan_cap_per_year": None}])
        outN = generate_week_schedule(cand, lh, ops, office="LA", week_start="2025-09-08", rules_df=rulesN)
        assert len(outN) == 0

    def test_rules_without_rank_applies_same_cap_for_all_ranks_of_make(self):
        """Test that rules without rank column apply same cap to all ranks of that make."""
        cand = pd.DataFrame([
            {"vin": "v1", "person_id": 303, "market": "LA", "make": "Hyundai", "model": "Tucson", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "A", "score": 70},
            {"vin": "v2", "person_id": 303, "market": "LA", "make": "Hyundai", "model": "Elantra", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "C", "score": 30},
        ])
        lh = pd.DataFrame([])
        ops = pd.DataFrame([{"office": "LA", "drivers_per_day": 10}])

        # Rules has make-only cap (no rank column) => apply same cap to all ranks for that make
        rules = pd.DataFrame([{"make": "Hyundai", "loan_cap_per_year": 1}])
        out = generate_week_schedule(cand, lh, ops, office="LA", week_start="2025-09-08", rules_df=rules)
        assert len(set((r["vin"], r["person_id"]) for _, r in out.iterrows())) == 1

    def test_complex_scenario(self):
        """Test complex scenario with multiple constraints."""
        c = _mk([
            {"vin": "v1", "person_id": 1, "market": "LA", "make": "Toyota", "model": "Camry", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "A+", "score": 100},
            {"vin": "v2", "person_id": 2, "market": "LA", "make": "Toyota", "model": "RAV4", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "A", "score": 90},
            {"vin": "v3", "person_id": 3, "market": "LA", "make": "Honda", "model": "Accord", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "B", "score": 80},
            {"vin": "v4", "person_id": 2, "market": "LA", "make": "Toyota", "model": "Highlander", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "rank": "A", "score": 85},
        ])

        # Partner 2 already has 5 Toyota loans (at A cap of 6)
        lh = _mk([
            {"person_id": 2, "make": "Toyota", "start_date": "2025-01-01", "end_date": "2025-01-07"},
            {"person_id": 2, "make": "Toyota", "start_date": "2025-02-01", "end_date": "2025-02-07"},
            {"person_id": 2, "make": "Toyota", "start_date": "2025-03-01", "end_date": "2025-03-07"},
            {"person_id": 2, "make": "Toyota", "start_date": "2025-04-01", "end_date": "2025-04-07"},
            {"person_id": 2, "make": "Toyota", "start_date": "2025-05-01", "end_date": "2025-05-07"}
        ])
        ops = _mk([{"office": "LA", "drivers_per_day": 3}])  # Capacity for 3 assignments

        out = generate_week_schedule(c, lh, ops, office="LA", week_start="2025-09-08")

        assignments = set((r["vin"], r["person_id"]) for _, r in out.iterrows())

        # With capacity=3, should get v1 (score 100), v2 (score 90), v3 (score 80)
        # v4 should be blocked by v2 double-booking (same person_id, same make)
        assert ("v1", 1) in assignments  # A+ rank, highest score
        assert ("v2", 2) in assignments  # A rank, second highest score
        assert ("v3", 3) in assignments  # B rank, third highest score
        assert ("v4", 2) not in assignments  # Blocked: same person as v2, same make

        assert len(out) == 21  # 3 assignments × 7 days