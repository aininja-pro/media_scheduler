"""
Candidate scoring for media scheduling optimization.

This module computes scores for (VIN × partner) candidate pairs based on:
- Rank weights (A+, A, B, C rankings from approved makes)
- Geographic bonuses (market/office alignment)
- History bonuses (past publication performance)
"""

import pandas as pd
from typing import Dict


DEFAULT_RANK_WEIGHTS: Dict[str, int] = {"A+": 100, "A": 70, "B": 40, "C": 10, "UNRANKED": 5}


def compute_candidate_scores(
    candidates_df: pd.DataFrame,   # from Step 1: ["vin","person_id","market","make","model","week_start","available_days","cooldown_ok","publication_rate_observed","supported","coverage"]
    partner_rank_df: pd.DataFrame, # Approved Makes: ["person_id","make","rank"]
    partners_df: pd.DataFrame,     # Media Partners: ["person_id","office","default_loan_region"]  # region is comma- or space-separated list of office codes
    publication_df: pd.DataFrame,  # same as Step 1 input; for history bonus
    rank_weights: Dict[str, int] = None,
    geo_bonus_points: int = 10,
    history_bonus_points: int = 5
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

    p["region_set"] = p.get("default_loan_region", "").map(_parse_regions)

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

    # Final score
    merged["score"] = merged["rank_weight"] + merged["geo_bonus"] + merged["history_bonus"]

    # Column order: original + new
    return merged[candidates_df.columns.tolist() + ["rank", "rank_weight", "geo_bonus", "history_bonus", "score"]]