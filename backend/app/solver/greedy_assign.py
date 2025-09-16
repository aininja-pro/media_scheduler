"""
Greedy assignment algorithm for media scheduling optimization.

This module implements the core scheduling logic that assigns vehicles to partners
while enforcing hard constraints: no double-booking, tier caps, and daily capacity.
"""

import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Tuple


DEFAULT_TIER_CAPS: Dict[str, int] = {"A+": 999, "A": 6, "B": 2, "C": 0}  # hard caps per 12 months (legacy)

# Fallback caps when no rules exist for a make
FALLBACK_RANK_CAPS = {"A+": 12, "A": 6, "B": 4, "C": 1}
FALLBACK_UNRANKED_CAP = 3


def _norm_rank(x) -> str:
    """Normalize rank, treating missing/pending as UNRANKED."""
    if x is None:
        return "UNRANKED"
    s = str(x).strip().upper().replace("PLUS", "+").replace(" ", "")
    return "UNRANKED" if s in {"", "PENDING", "UNKNOWN", "NA", "NONE"} else s


def _parse_rule_cap(v) -> int:
    """Parse rule cap: 0/NULL means block (cap=0), positive means allow."""
    if v is None:
        return 0
    try:
        iv = int(v)
        return iv if iv > 0 else 0
    except Exception:
        return 0


def _resolve_pair_cap(make: str, rank: str, rules_df) -> int:
    """
    Cap precedence:
      1) RULES(make, rank) -> parse
      2) RULES(make)       -> parse
      3) No rule row:
         a) if rank known -> FALLBACK_RANK_CAPS[rank] (or fallback to C if unknown rank key)
         b) if rank UNRANKED -> FALLBACK_UNRANKED_CAP
    """
    m = (make or "").strip()
    r = _norm_rank(rank)

    if rules_df is not None and not rules_df.empty:
        rules = rules_df.copy()
        rules["make"] = rules["make"].astype(str).str.strip()
        has_rank = "rank" in rules.columns

        if has_rank:
            rules["rank"] = rules["rank"].astype(str).str.upper().str.replace("PLUS", "+").str.replace(" ", "", regex=False)
            row = rules[(rules["make"] == m) & (rules["rank"] == r)]
            if not row.empty:
                return _parse_rule_cap(row["loan_cap_per_year"].iloc[0])

        row2 = rules[rules["make"] == m]
        if not row2.empty and "loan_cap_per_year" in row2.columns:
            return _parse_rule_cap(row2["loan_cap_per_year"].iloc[0])

    # No rule row for this make -> fallbacks
    if r == "UNRANKED":
        return int(FALLBACK_UNRANKED_CAP)
    return int(FALLBACK_RANK_CAPS.get(r, FALLBACK_RANK_CAPS["C"]))


def _week_days(week_start: str) -> List[pd.Timestamp]:
    """Generate 7-day timestamp list starting from week_start Monday."""
    s = pd.to_datetime(week_start)
    return [s + pd.Timedelta(days=i) for i in range(7)]


def _loans_12m_counts(loan_history_df: pd.DataFrame, as_of: str) -> pd.DataFrame:
    """Count historical loans in trailing 12 months per (person_id, make)."""
    if loan_history_df.empty:
        return pd.DataFrame(columns=["person_id", "make", "loans_12m"])

    as_of_dt = pd.to_datetime(as_of)
    start = (as_of_dt - relativedelta(months=12)).normalize()

    df = loan_history_df.copy()

    # Ensure required columns exist
    required_cols = ["person_id", "make"]
    for col in required_cols:
        if col not in df.columns:
            return pd.DataFrame(columns=["person_id", "make", "loans_12m"])

    # Parse date columns
    for c in ("start_date", "end_date"):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")

    # Handle missing date columns
    if "end_date" not in df.columns and "start_date" not in df.columns:
        return pd.DataFrame(columns=["person_id", "make", "loans_12m"])

    if "end_date" in df.columns:
        df["ref_date"] = df["end_date"].where(df["end_date"].notna(),
                                            df["start_date"] if "start_date" in df.columns else df["end_date"])
    else:
        df["ref_date"] = df["start_date"]

    df = df[df["ref_date"].notna()]
    df = df[(df["ref_date"] >= start) & (df["ref_date"] <= as_of_dt)]

    grp = df.groupby(["person_id", "make"], dropna=False).size().reset_index(name="loans_12m")
    return grp


def _loans_12m_by_pair(loan_history_df: pd.DataFrame, as_of: str) -> dict[tuple, int]:
    """Count historical loans in trailing 12 months per (person_id, make) pair."""
    if loan_history_df.empty:
        return {}  # No history = no usage

    as_of_dt = pd.to_datetime(as_of)
    start = (as_of_dt - relativedelta(months=12)).normalize()
    df = loan_history_df.copy()

    # Check required columns exist
    required_cols = ["person_id", "make"]
    if not all(col in df.columns for col in required_cols):
        return {}

    for c in ("start_date", "end_date"):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")

    # Handle ref_date creation safely
    if "end_date" in df.columns and "start_date" in df.columns:
        df["ref_date"] = df["end_date"].where(df["end_date"].notna(), df["start_date"])
    elif "end_date" in df.columns:
        df["ref_date"] = df["end_date"]
    elif "start_date" in df.columns:
        df["ref_date"] = df["start_date"]
    else:
        return {}  # No date columns

    df = df[df["ref_date"].notna() & df["person_id"].notna() & df["make"].notna()]
    df = df[(df["ref_date"] >= start) & (df["ref_date"] <= as_of_dt)]
    return (
        df.groupby(["person_id", "make"], dropna=False).size()
          .rename("loans_12m_pair").to_dict()
    )




def generate_week_schedule(
    candidates_scored_df: pd.DataFrame,  # from Step 2
    loan_history_df: pd.DataFrame,       # raw table for 12m tier counts
    ops_capacity_df: pd.DataFrame,       # office, drivers_per_day
    office: str,
    week_start: str,                     # "YYYY-MM-DD" Monday
    rank_caps: Dict[str, int] | None = None,  # legacy: IGNORE for tier caps now
    rules_df: pd.DataFrame | None = None,    # <— add (supports columns: make, [rank], loan_cap_per_year)
) -> pd.DataFrame:
    """
    Greedy weekly assignment for one office.

    Inputs:
      - candidates_scored_df columns (required subset):
        ["vin","person_id","market","make","model","week_start",
         "available_days","cooldown_ok","rank","score"]
      - loan_history_df columns: ["person_id","make","start_date","end_date"]  # trailing 12m
      - ops_capacity_df columns: ["office","drivers_per_day"]

    Rules enforced:
      - Only consider candidates where market == office and cooldown_ok=True.
      - No double-booking: a VIN can be assigned at most once for the week.
      - Tier caps: (# loans in trailing 12m for (person_id,make)) < CAP[rank].
      - Daily ops capacity: assigned rows per day ≤ drivers_per_day for office.
      - Expand each chosen (vin,person) to 7 daily rows (Mon–Sun).

    Returns DataFrame with columns:
      ["vin","person_id","day","office","make","model","score",
       "flags"]  # flags is a "|" joined string like "tier_ok|capacity_ok|cooldown_ok|availability_ok"
    """
    # Note: rank_caps parameter is legacy and ignored - now using dynamic rules_df caps

    # Handle empty candidates early
    if candidates_scored_df.empty:
        return pd.DataFrame(columns=[
            "vin", "person_id", "day", "office", "make", "model", "score", "flags"
        ])

    # Filter for office + cooldown
    cand = candidates_scored_df.copy()
    cand = cand[(cand["market"].astype(str).str.strip() == office) & (cand["cooldown_ok"] == True)]

    if cand.empty:
        return pd.DataFrame(columns=[
            "vin", "person_id", "day", "office", "make", "model", "score", "flags"
        ])

    # Prepare capacities
    if ops_capacity_df.empty:
        drivers_per_day = 999  # default open
    else:
        cap_row = ops_capacity_df[ops_capacity_df["office"].astype(str).str.strip() == office]
        drivers_per_day = int(cap_row["drivers_per_day"].iloc[0]) if not cap_row.empty else 999  # default open

    days = _week_days(week_start)
    capacity_used = {d.date(): 0 for d in days}

    # Build cap cache using the scored candidates with fallback logic
    pair_caps_cache = {}
    for t in cand[["person_id", "make", "rank"]].drop_duplicates().itertuples(index=False):
        cap = _resolve_pair_cap(make=t.make, rank=getattr(t, "rank", None), rules_df=rules_df)
        pair_caps_cache[(t.person_id, t.make)] = cap

    # Count trailing-12m usage per (person_id, make)
    pair_used = _loans_12m_by_pair(loan_history_df, week_start)

    # Sort candidates by score desc, tie-break by vin/person_id for determinism
    cand = cand.sort_values(by=["score", "vin", "person_id"], ascending=[False, True, True])

    assigned_vins = set()
    out_rows: List[Dict] = []

    for row in cand.itertuples(index=False):
        vin = row.vin
        pid = row.person_id
        make = row.make

        # Rule: no double-booking
        if vin in assigned_vins:
            continue

        # Rule: dynamic tier cap with fallbacks
        cap_dyn = int(pair_caps_cache.get((pid, make), FALLBACK_UNRANKED_CAP))  # should be present
        used_pair = int(pair_used.get((pid, make), 0))

        # HARD BLOCK when used >= cap
        if used_pair >= cap_dyn:
            continue

        # Rule: capacity check (all 7 days must fit)
        if any(capacity_used[d.date()] + 1 > drivers_per_day for d in days):
            continue

        # Assign across all 7 days
        for d in days:
            capacity_used[d.date()] += 1
            out_rows.append({
                "vin": vin,
                "person_id": pid,
                "day": d.date().isoformat(),
                "office": office,
                "make": make,
                "model": row.model,
                "score": int(row.score),
                "flags": "tier_ok|capacity_ok|cooldown_ok|availability_ok"
            })

        assigned_vins.add(vin)
        pair_used[(pid, make)] = used_pair + 1  # increment usage for dynamic tier cap tracking

    return pd.DataFrame(out_rows)