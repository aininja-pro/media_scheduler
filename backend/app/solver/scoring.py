"""
Candidate scoring for media scheduling optimization.

This module computes scores for (VIN × partner) candidate pairs based on:
- Rank weights (A+, A, B, C rankings from approved makes)
- Geographic bonuses (market/office alignment)
- History bonuses (past publication performance)
"""

import pandas as pd
from typing import Dict


DEFAULT_RANK_WEIGHTS: Dict[str, int] = {"A+": 1000, "A": 700, "B": 400, "C": 100, "UNRANKED": 50}


def compute_candidate_scores(
    candidates_df: pd.DataFrame,   # from Step 1: ["vin","person_id","market","make","model","week_start","available_days","cooldown_ok","publication_rate_observed","supported","coverage"]
    partner_rank_df: pd.DataFrame, # Approved Makes: ["person_id","make","rank"]
    partners_df: pd.DataFrame,     # Media Partners: ["person_id","office","default_loan_region"]  # region is comma- or space-separated list of office codes
    publication_df: pd.DataFrame,  # same as Step 1 input; for history bonus
    rank_weights: Dict[str, int] = None,
    geo_bonus_points: int = 100,
    history_bonus_points: int = 50,
    chaining_bonus_points: int = 200,
    current_activity_df: pd.DataFrame = None  # Optional: existing active loans for chaining bonus
) -> pd.DataFrame:
    """
    Returns candidates_df with added columns:
      rank: str in {A+,A,B,C} (fallback 'C' if missing)
      rank_weight: int
      geo_bonus: int (vehicle market equals partner office OR in default_loan_region)
      history_bonus: int (publication_df shows >=1 publications_observed_24m for (person_id, make); optional gate on supported)
      score: int = rank_weight + geo_bonus + history_bonus

    Rules:
      - Join rank on (person_id, make). Missing rank -> 'C'.
      - Geo bonus if candidates_df.market == partners_df.office OR market ∈ default_loan_region set.
      - History bonus if publication_df[(person_id, make)].publications_observed_24m >= 1.
      - Keep rows as-is; this function does NOT filter or assign.
      - Preserve all original columns; append new ones exactly in this order at the end:
        ["rank","rank_weight","geo_bonus","history_bonus","score"].
    """
    rank_weights = rank_weights or DEFAULT_RANK_WEIGHTS

    # Prepare partner region set
    p = partners_df.copy()
    p["office"] = p["office"].astype(str).str.strip()

    # parse default_loan_region -> set of codes
    def _parse_regions(x):
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return set()
        s = str(x).replace(";", ",").replace("|", ",")
        parts = [t.strip() for t in s.split(",") if t.strip()]
        return set(parts)

    if "default_loan_region" in p.columns:
        p["region_set"] = p["default_loan_region"].map(_parse_regions)
    else:
        p["region_set"] = [set() for _ in range(len(p))]

    # Rank join
    r = partner_rank_df.copy()
    if not r.empty:
        r["rank"] = r["rank"].astype(str).str.upper().str.replace("PLUS", "+", regex=False).str.replace(" ", "")
        merged = candidates_df.merge(r[["person_id", "make", "rank"]], on=["person_id", "make"], how="left")
    else:
        merged = candidates_df.copy()
        merged["rank"] = None

    # Import rank normalization from greedy_assign
    from .greedy_assign import _norm_rank

    merged["rank"] = merged["rank"].apply(_norm_rank)
    merged["rank_weight"] = merged["rank"].map(lambda x: rank_weights.get(x, rank_weights.get("UNRANKED", 5))).astype(int)

    # Geo bonus
    mp = p[["person_id", "office", "region_set"]]
    merged = merged.merge(mp, on="person_id", how="left", suffixes=("", ""))
    merged["market"] = merged["market"].astype(str).str.strip()
    merged["office"] = merged["office"].astype(str).str.strip()
    # Handle NaN region_set values
    def _check_region_match(row):
        if pd.isna(row["region_set"]) or not isinstance(row["region_set"], set):
            return False
        return row["market"] in row["region_set"]

    merged["geo_bonus"] = (
        (merged["market"] == merged["office"]) |
        merged.apply(_check_region_match, axis=1)
    ).astype(int) * int(geo_bonus_points)

    # History bonus (observed publications >=1)
    if not publication_df.empty and "publications_observed_24m" in publication_df.columns:
        pub = publication_df[["person_id", "make", "publications_observed_24m"]].copy()
        pub.columns = ["person_id", "make", "pubs"]
        merged = merged.merge(pub, on=["person_id", "make"], how="left")
        merged["pubs"] = merged["pubs"].fillna(0).astype(int)
    else:
        merged["pubs"] = 0

    merged["history_bonus"] = (merged["pubs"] >= 1).astype(int) * int(history_bonus_points)

    # Add publication rate bonus (0-100 based on publication_rate_observed)
    if "publication_rate_observed" in merged.columns:
        # publication_rate_observed is 0-1, convert to 0-100 scale
        merged["pub_rate_bonus"] = (merged["publication_rate_observed"].fillna(0) * 100).astype(int)
    else:
        merged["pub_rate_bonus"] = 0

    # Add model diversity bonus (hash model name to get pseudo-random 0-50 bonus)
    # This helps break ties and distribute different models
    if "model" in merged.columns:
        merged["model_bonus"] = merged["model"].apply(
            lambda x: abs(hash(str(x))) % 51 if pd.notna(x) else 25
        )
    else:
        merged["model_bonus"] = 25

    # Add VIN hash bonus (0-20) for final tie-breaking that's not just alphabetical
    if "vin" in merged.columns:
        merged["vin_bonus"] = merged["vin"].apply(
            lambda x: abs(hash(str(x))) % 21 if pd.notna(x) else 10
        )
    else:
        merged["vin_bonus"] = 10

    # Add chaining bonus (encourages back-to-back assignments to same partner)
    merged["chaining_bonus"] = 0
    if current_activity_df is not None and not current_activity_df.empty and "start_day" in merged.columns:
        from datetime import datetime, timedelta

        # Build dict of {person_id: [end_dates]} from current activity
        partner_loan_ends = {}
        for _, loan in current_activity_df.iterrows():
            person_id = loan.get('person_id')
            end_date = loan.get('end_date')
            if person_id and end_date:
                if person_id not in partner_loan_ends:
                    partner_loan_ends[person_id] = []
                # Convert to date object for comparison
                if isinstance(end_date, str):
                    end_date = pd.to_datetime(end_date).date()
                elif hasattr(end_date, 'date'):
                    end_date = end_date.date()
                partner_loan_ends[person_id].append(end_date)

        # Check each candidate for chaining opportunity
        def check_chaining(row):
            person_id = row['person_id']
            start_day = row['start_day']

            if person_id not in partner_loan_ends:
                return 0

            # Convert start_day to date
            if isinstance(start_day, str):
                start_date = pd.to_datetime(start_day).date()
            elif hasattr(start_day, 'date'):
                start_date = start_day.date()
            else:
                start_date = start_day

            # Check if any existing loan ends within 2 days before this start
            for end_date in partner_loan_ends[person_id]:
                days_gap = (start_date - end_date).days
                # Gap of 1 day = perfect chain (loan ends Mon, new starts Tue)
                # Gap of 0 = same day (blocked by overlap constraint anyway)
                # Gap of 2 = small gap, still good
                if 1 <= days_gap <= 2:
                    return chaining_bonus_points
            return 0

        merged["chaining_bonus"] = merged.apply(check_chaining, axis=1)

    # Final score with more components for better differentiation
    merged["score"] = (
        merged["rank_weight"] +
        merged["geo_bonus"] +
        merged["history_bonus"] +
        merged["pub_rate_bonus"] +
        merged["model_bonus"] +
        merged["vin_bonus"] +
        merged["chaining_bonus"]
    )

    # Column order: original + new
    return merged[candidates_df.columns.tolist() + [
        "rank", "rank_weight", "geo_bonus", "history_bonus",
        "pub_rate_bonus", "model_bonus", "vin_bonus", "chaining_bonus", "score"
    ]]