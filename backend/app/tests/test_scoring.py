"""
Tests for candidate scoring logic.

Tests cover rank weights, geographic bonuses, history bonuses, and edge cases
for the compute_candidate_scores function.
"""

import pandas as pd
import pytest

from app.solver.scoring import compute_candidate_scores, DEFAULT_RANK_WEIGHTS


def _mk(df):
    """Helper to create DataFrame from list of dicts."""
    return pd.DataFrame(df)


class TestComputeCandidateScores:
    """Test suite for compute_candidate_scores function."""

    def setup_method(self):
        """Set up test data for each test."""
        # Base candidate data
        self.candidates_df = _mk([
            {
                "vin": "v1",
                "person_id": 1,
                "market": "LA",
                "make": "Toyota",
                "model": "Camry",
                "week_start": "2025-09-08",
                "available_days": 7,
                "cooldown_ok": True,
                "publication_rate_observed": None,
                "supported": False,
                "coverage": 0
            }
        ])

        # Base partner ranks
        self.partner_rank_df = _mk([
            {"person_id": 1, "make": "Toyota", "rank": "A"}
        ])

        # Base partners data
        self.partners_df = _mk([
            {"person_id": 1, "office": "LA", "default_loan_region": "LA,SF"}
        ])

        # Base publication data
        self.publication_df = _mk([
            {"person_id": 1, "make": "Toyota", "publications_observed_24m": 0}
        ])

    def test_rank_weights_and_defaults(self):
        """Test that rank weights are applied correctly and missing ranks default to 'C'."""
        out = compute_candidate_scores(
            self.candidates_df,
            self.partner_rank_df,
            self.partners_df,
            self.publication_df
        )
        row = out.iloc[0]
        assert row["rank"] == "A"
        assert row["rank_weight"] == DEFAULT_RANK_WEIGHTS["A"]

    def test_missing_rank_defaults_to_c(self):
        """Test that missing ranks default to 'C' with appropriate weight."""
        # Empty ranks dataframe
        empty_ranks = _mk([])

        out = compute_candidate_scores(
            self.candidates_df,
            empty_ranks,
            self.partners_df,
            self.publication_df
        )
        row = out.iloc[0]
        assert row["rank"] == "C"
        assert row["rank_weight"] == DEFAULT_RANK_WEIGHTS["C"]

    def test_all_rank_levels(self):
        """Test all rank levels (A+, A, B, C) are handled correctly."""
        candidates = _mk([
            {"vin": "v1", "person_id": 1, "market": "LA", "make": "Toyota", "model": "Camry", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "publication_rate_observed": None, "supported": False, "coverage": 0},
            {"vin": "v2", "person_id": 2, "market": "LA", "make": "Honda", "model": "Accord", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "publication_rate_observed": None, "supported": False, "coverage": 0},
            {"vin": "v3", "person_id": 3, "market": "LA", "make": "Mazda", "model": "CX-5", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "publication_rate_observed": None, "supported": False, "coverage": 0},
            {"vin": "v4", "person_id": 4, "market": "LA", "make": "Hyundai", "model": "Tucson", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "publication_rate_observed": None, "supported": False, "coverage": 0}
        ])

        ranks = _mk([
            {"person_id": 1, "make": "Toyota", "rank": "A+"},
            {"person_id": 2, "make": "Honda", "rank": "A"},
            {"person_id": 3, "make": "Mazda", "rank": "B"},
            {"person_id": 4, "make": "Hyundai", "rank": "C"}
        ])

        partners = _mk([
            {"person_id": 1, "office": "LA", "default_loan_region": ""},
            {"person_id": 2, "office": "LA", "default_loan_region": ""},
            {"person_id": 3, "office": "LA", "default_loan_region": ""},
            {"person_id": 4, "office": "LA", "default_loan_region": ""}
        ])

        pub = _mk([
            {"person_id": 1, "make": "Toyota", "publications_observed_24m": 0},
            {"person_id": 2, "make": "Honda", "publications_observed_24m": 0},
            {"person_id": 3, "make": "Mazda", "publications_observed_24m": 0},
            {"person_id": 4, "make": "Hyundai", "publications_observed_24m": 0}
        ])

        out = compute_candidate_scores(candidates, ranks, partners, pub)

        assert out.iloc[0]["rank"] == "A+"
        assert out.iloc[0]["rank_weight"] == DEFAULT_RANK_WEIGHTS["A+"]
        assert out.iloc[1]["rank"] == "A"
        assert out.iloc[1]["rank_weight"] == DEFAULT_RANK_WEIGHTS["A"]
        assert out.iloc[2]["rank"] == "B"
        assert out.iloc[2]["rank_weight"] == DEFAULT_RANK_WEIGHTS["B"]
        assert out.iloc[3]["rank"] == "C"
        assert out.iloc[3]["rank_weight"] == DEFAULT_RANK_WEIGHTS["C"]

    def test_geo_bonus_from_office_or_region(self):
        """Test geo bonus awarded when market matches office or is in default_loan_region."""
        candidates = _mk([
            {"vin": "v1", "person_id": 2, "market": "SEA", "make": "Mazda", "model": "CX-5", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "publication_rate_observed": None, "supported": False, "coverage": 0}
        ])
        ranks = _mk([
            {"person_id": 2, "make": "Mazda", "rank": "B"}
        ])
        partners = _mk([
            {"person_id": 2, "office": "LA", "default_loan_region": "SEA,PDX"}  # region includes SEA
        ])
        pub = _mk([
            {"person_id": 2, "make": "Mazda", "publications_observed_24m": 0}
        ])

        out = compute_candidate_scores(candidates, ranks, partners, pub, geo_bonus_points=10)
        assert out.iloc[0]["geo_bonus"] == 10

    def test_geo_bonus_from_office_match(self):
        """Test geo bonus awarded when market exactly matches partner office."""
        candidates = _mk([
            {"vin": "v1", "person_id": 1, "market": "Miami", "make": "Toyota", "model": "Camry", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "publication_rate_observed": None, "supported": False, "coverage": 0}
        ])
        ranks = _mk([
            {"person_id": 1, "make": "Toyota", "rank": "A"}
        ])
        partners = _mk([
            {"person_id": 1, "office": "Miami", "default_loan_region": ""}  # office matches market
        ])
        pub = _mk([
            {"person_id": 1, "make": "Toyota", "publications_observed_24m": 0}
        ])

        out = compute_candidate_scores(candidates, ranks, partners, pub, geo_bonus_points=15)
        assert out.iloc[0]["geo_bonus"] == 15

    def test_no_geo_bonus_when_no_match(self):
        """Test no geo bonus when market matches neither office nor region."""
        candidates = _mk([
            {"vin": "v1", "person_id": 1, "market": "Denver", "make": "Toyota", "model": "Camry", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "publication_rate_observed": None, "supported": False, "coverage": 0}
        ])
        ranks = _mk([
            {"person_id": 1, "make": "Toyota", "rank": "A"}
        ])
        partners = _mk([
            {"person_id": 1, "office": "LA", "default_loan_region": "SF,SEA"}  # Denver not in either
        ])
        pub = _mk([
            {"person_id": 1, "make": "Toyota", "publications_observed_24m": 0}
        ])

        out = compute_candidate_scores(candidates, ranks, partners, pub)
        assert out.iloc[0]["geo_bonus"] == 0

    def test_history_bonus_when_published_observed(self):
        """Test history bonus awarded when publications_observed_24m >= 1."""
        candidates = _mk([
            {"vin": "v1", "person_id": 3, "market": "LA", "make": "Hyundai", "model": "Tucson", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "publication_rate_observed": 0.5, "supported": True, "coverage": 1.0}
        ])
        ranks = _mk([
            {"person_id": 3, "make": "Hyundai", "rank": "C"}  # lowest rank
        ])
        partners = _mk([
            {"person_id": 3, "office": "LA", "default_loan_region": ""}
        ])
        pub = _mk([
            {"person_id": 3, "make": "Hyundai", "publications_observed_24m": 2}  # prior pubs
        ])

        out = compute_candidate_scores(candidates, ranks, partners, pub, history_bonus_points=5)
        assert out.iloc[0]["history_bonus"] == 5
        # LA office matches market → geo +10, plus history +5, plus rank weight for C
        assert out.iloc[0]["score"] == out.iloc[0]["rank_weight"] + 5 + 10

    def test_no_history_bonus_when_no_publications(self):
        """Test no history bonus when publications_observed_24m < 1."""
        candidates = _mk([
            {"vin": "v1", "person_id": 1, "market": "LA", "make": "Toyota", "model": "Camry", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "publication_rate_observed": None, "supported": False, "coverage": 0}
        ])
        ranks = _mk([
            {"person_id": 1, "make": "Toyota", "rank": "A"}
        ])
        partners = _mk([
            {"person_id": 1, "office": "SF", "default_loan_region": ""}  # No geo match
        ])
        pub = _mk([
            {"person_id": 1, "make": "Toyota", "publications_observed_24m": 0}  # No publications
        ])

        out = compute_candidate_scores(candidates, ranks, partners, pub)
        assert out.iloc[0]["history_bonus"] == 0
        # Only rank weight, no bonuses
        assert out.iloc[0]["score"] == DEFAULT_RANK_WEIGHTS["A"]

    def test_custom_scoring_parameters(self):
        """Test custom rank weights and bonus points."""
        custom_weights = {"A+": 200, "A": 150, "B": 100, "C": 50}

        out = compute_candidate_scores(
            self.candidates_df,
            self.partner_rank_df,
            self.partners_df,
            self.publication_df,
            rank_weights=custom_weights,
            geo_bonus_points=25,
            history_bonus_points=15
        )

        row = out.iloc[0]
        assert row["rank_weight"] == custom_weights["A"]
        assert row["geo_bonus"] == 25  # LA matches
        assert row["history_bonus"] == 0  # No publications

    def test_column_order_preservation(self):
        """Test that original columns are preserved and new columns added in correct order."""
        out = compute_candidate_scores(
            self.candidates_df,
            self.partner_rank_df,
            self.partners_df,
            self.publication_df
        )

        original_cols = self.candidates_df.columns.tolist()
        new_cols = ["rank", "rank_weight", "geo_bonus", "history_bonus", "score"]
        expected_cols = original_cols + new_cols

        assert list(out.columns) == expected_cols

    def test_region_parsing_edge_cases(self):
        """Test various formats for default_loan_region parsing."""
        candidates = _mk([
            {"vin": "v1", "person_id": 1, "market": "SEA", "make": "Toyota", "model": "Camry", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "publication_rate_observed": None, "supported": False, "coverage": 0},
            {"vin": "v2", "person_id": 2, "market": "PDX", "make": "Honda", "model": "Accord", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "publication_rate_observed": None, "supported": False, "coverage": 0},
            {"vin": "v3", "person_id": 3, "market": "DEN", "make": "Mazda", "model": "CX-5", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "publication_rate_observed": None, "supported": False, "coverage": 0}
        ])

        ranks = _mk([
            {"person_id": 1, "make": "Toyota", "rank": "A"},
            {"person_id": 2, "make": "Honda", "rank": "A"},
            {"person_id": 3, "make": "Mazda", "rank": "A"}
        ])

        partners = _mk([
            {"person_id": 1, "office": "LA", "default_loan_region": "SEA,PDX,SFO"},  # comma-separated
            {"person_id": 2, "office": "LA", "default_loan_region": "PDX; DEN"},     # semicolon-separated
            {"person_id": 3, "office": "LA", "default_loan_region": None}            # None/null
        ])

        pub = _mk([
            {"person_id": 1, "make": "Toyota", "publications_observed_24m": 0},
            {"person_id": 2, "make": "Honda", "publications_observed_24m": 0},
            {"person_id": 3, "make": "Mazda", "publications_observed_24m": 0}
        ])

        out = compute_candidate_scores(candidates, ranks, partners, pub, geo_bonus_points=10)

        # SEA should match person_id 1's region
        assert out.iloc[0]["geo_bonus"] == 10
        # PDX should match person_id 2's region (semicolon format)
        assert out.iloc[1]["geo_bonus"] == 10
        # DEN should not match person_id 3 (None region)
        assert out.iloc[2]["geo_bonus"] == 0

    def test_missing_publication_data(self):
        """Test handling when publication data is missing for some candidates."""
        empty_pub = _mk([])  # No publication data

        out = compute_candidate_scores(
            self.candidates_df,
            self.partner_rank_df,
            self.partners_df,
            empty_pub
        )

        row = out.iloc[0]
        assert row["history_bonus"] == 0
        assert row["score"] == row["rank_weight"] + row["geo_bonus"]  # No history bonus

    def test_rank_normalization(self):
        """Test that rank values are properly normalized (uppercase, space removal, etc)."""
        ranks = _mk([
            {"person_id": 1, "make": "Toyota", "rank": "a+"},  # lowercase
            {"person_id": 2, "make": "Honda", "rank": "A "},  # trailing space
            {"person_id": 3, "make": "Mazda", "rank": "b"},   # lowercase
        ])

        candidates = _mk([
            {"vin": "v1", "person_id": 1, "market": "LA", "make": "Toyota", "model": "Camry", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "publication_rate_observed": None, "supported": False, "coverage": 0},
            {"vin": "v2", "person_id": 2, "market": "LA", "make": "Honda", "model": "Accord", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "publication_rate_observed": None, "supported": False, "coverage": 0},
            {"vin": "v3", "person_id": 3, "market": "LA", "make": "Mazda", "model": "CX-5", "week_start": "2025-09-08", "available_days": 7, "cooldown_ok": True, "publication_rate_observed": None, "supported": False, "coverage": 0}
        ])

        partners = _mk([
            {"person_id": 1, "office": "LA", "default_loan_region": ""},
            {"person_id": 2, "office": "LA", "default_loan_region": ""},
            {"person_id": 3, "office": "LA", "default_loan_region": ""}
        ])

        pub = _mk([
            {"person_id": 1, "make": "Toyota", "publications_observed_24m": 0},
            {"person_id": 2, "make": "Honda", "publications_observed_24m": 0},
            {"person_id": 3, "make": "Mazda", "publications_observed_24m": 0}
        ])

        out = compute_candidate_scores(candidates, ranks, partners, pub)

        assert out.iloc[0]["rank"] == "A+"
        assert out.iloc[0]["rank_weight"] == DEFAULT_RANK_WEIGHTS["A+"]
        assert out.iloc[1]["rank"] == "A"
        assert out.iloc[1]["rank_weight"] == DEFAULT_RANK_WEIGHTS["A"]
        assert out.iloc[2]["rank"] == "B"
        assert out.iloc[2]["rank_weight"] == DEFAULT_RANK_WEIGHTS["B"]

    def test_function_is_pure_and_deterministic(self):
        """Test that function is pure and produces identical results on identical inputs."""
        result1 = compute_candidate_scores(
            self.candidates_df,
            self.partner_rank_df,
            self.partners_df,
            self.publication_df
        )

        result2 = compute_candidate_scores(
            self.candidates_df,
            self.partner_rank_df,
            self.partners_df,
            self.publication_df
        )

        pd.testing.assert_frame_equal(result1, result2)

    def test_large_dataset_performance(self):
        """Test that function performs well with larger datasets."""
        import time

        # Create larger test dataset
        num_candidates = 1000
        candidates = []
        ranks = []
        partners = []
        pubs = []

        makes = ['Toyota', 'Honda', 'Ford', 'Mazda', 'Hyundai']
        offices = ['LA', 'SF', 'SEA', 'PDX', 'DEN']
        rank_levels = ['A+', 'A', 'B', 'C']

        # Track unique combinations to avoid duplicates
        seen_ranks = set()
        seen_partners = set()
        seen_pubs = set()

        for i in range(num_candidates):
            person_id = i % 100 + 1  # 100 unique partners
            make = makes[i % len(makes)]
            market = offices[i % len(offices)]

            candidates.append({
                "vin": f"VIN{i:06d}",
                "person_id": person_id,
                "market": market,
                "make": make,
                "model": f"Model{i%5}",
                "week_start": "2025-09-08",
                "available_days": 7,
                "cooldown_ok": True,
                "publication_rate_observed": None,
                "supported": False,
                "coverage": 0
            })

            # Add rank data (avoid duplicates)
            rank_key = (person_id, make)
            if rank_key not in seen_ranks:
                seen_ranks.add(rank_key)
                ranks.append({
                    "person_id": person_id,
                    "make": make,
                    "rank": rank_levels[i % len(rank_levels)]
                })

            # Add partner data (avoid duplicates)
            if person_id not in seen_partners:
                seen_partners.add(person_id)
                partners.append({
                    "person_id": person_id,
                    "office": offices[i % len(offices)],
                    "default_loan_region": f"{offices[(i+1) % len(offices)]},{offices[(i+2) % len(offices)]}"
                })

            # Add publication data (avoid duplicates)
            pub_key = (person_id, make)
            if pub_key not in seen_pubs:
                seen_pubs.add(pub_key)
                pubs.append({
                    "person_id": person_id,
                    "make": make,
                    "publications_observed_24m": i % 5  # 0-4 publications
                })

        candidates_df = pd.DataFrame(candidates)
        ranks_df = pd.DataFrame(ranks)
        partners_df = pd.DataFrame(partners)
        pub_df = pd.DataFrame(pubs)

        start_time = time.time()
        result = compute_candidate_scores(candidates_df, ranks_df, partners_df, pub_df)
        end_time = time.time()

        execution_time = end_time - start_time
        print(f"\nScored {len(result)} candidates in {execution_time:.3f} seconds")

        # Validate results
        assert len(result) == num_candidates
        assert all(col in result.columns for col in ["rank", "rank_weight", "geo_bonus", "history_bonus", "score"])
        assert execution_time < 2.0, f"Performance too slow: {execution_time:.3f}s"