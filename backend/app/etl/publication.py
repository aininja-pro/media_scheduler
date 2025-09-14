"""
ETL module for computing publication rates based on loan history.

This module calculates 24-month rolling publication rates for partner-make
combinations based on their loan history and clips received.
"""

from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import Optional
import pandas as pd


def compute_publication_rate_24m(
    loan_history_df: pd.DataFrame,
    as_of_date: Optional[str] = None,
    window_months: int = 24,
    min_observed: int = 3
) -> pd.DataFrame:
    """
    Rolling 24m publication rate with NULL-aware logic.

    - clips_received: True/False/NULL
      * True  -> published
      * False -> not published
      * NULL  -> unknown (excluded from observed denominator)
    - Outputs include coverage and support flags.
    - Grain: (person_id, make) combination.

    Args:
        loan_history_df: DataFrame with columns:
            - activity_id, vin, person_id, make, model, start_date, end_date, clips_received
        as_of_date: End date for window in YYYY-MM-DD format (default: today)
        window_months: Length of rolling window in months (default: 24)
        min_observed: Minimum observed loans for supported=True (default: 3)

    Returns:
        DataFrame with columns:
        - person_id: Partner identifier
        - make: Vehicle make
        - loans_total_24m: All loans in window
        - loans_observed_24m: Loans with clips_received not NULL
        - publications_observed_24m: Loans with clips_received = TRUE
        - publication_rate_observed: Rate based on observed data only (None if no observed)
        - coverage: loans_observed / loans_total (0-1)
        - supported: True if loans_observed >= min_observed
        - window_start: Start of analysis window
        - window_end: End of analysis window

        Grain: One row per (person_id, make) combination that has loans in the window
    """

    # dates
    as_of = pd.to_datetime(as_of_date or datetime.today().date()).normalize()
    window_start = (as_of - relativedelta(months=window_months)).normalize()

    df = loan_history_df.copy()

    # parse dates
    for col in ("start_date", "end_date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    df["ref_date"] = df["end_date"].where(df["end_date"].notna(),
                                      df["start_date"] if "start_date" in df.columns else df["end_date"])
    df = df[df["ref_date"].notna() & df["person_id"].notna()]
    df = df[(df["ref_date"] >= window_start) & (df["ref_date"] <= as_of)]

    if df.empty:
        return pd.DataFrame(columns=[
            'person_id', 'make', 'loans_total_24m', 'loans_observed_24m', 'publications_observed_24m',
            'publication_rate_observed', 'coverage', 'supported', 'window_start', 'window_end'
        ])

    # normalize clips tri-state without forcing NULL->False
    if "clips_received" not in df.columns:
        df["clips_received"] = pd.NA
    # map common string/number forms; keep NA as NA
    df["clips_received_norm"] = (
        df["clips_received"]
        .map(lambda x: True if str(x).strip().lower() in {"true","1","yes"} else
                       False if str(x).strip().lower() in {"false","0","no"} else pd.NA)
    )

    group_cols = [c for c in ["person_id","make"] if c in df.columns]  # preserve grain

    # totals in window
    totals = df.groupby(group_cols, dropna=False).agg(
        loans_total_24m=("activity_id","count")
    )

    # observed subset (clips not null)
    obs = df[df["clips_received_norm"].notna()].assign(
        published=lambda x: x["clips_received_norm"].astype(bool)
    ).groupby(group_cols, dropna=False).agg(
        loans_observed_24m=("activity_id","count"),
        publications_observed_24m=("published","sum")
    )

    out = totals.join(obs, how="left").fillna(
        {"loans_observed_24m":0, "publications_observed_24m":0}
    ).reset_index()

    # metrics
    out["publication_rate_observed"] = out.apply(
        lambda r: (r["publications_observed_24m"] / r["loans_observed_24m"])
                  if r["loans_observed_24m"] > 0 else None, axis=1
    )
    out["coverage"] = out.apply(
        lambda r: (r["loans_observed_24m"] / r["loans_total_24m"])
                  if r["loans_total_24m"] > 0 else None, axis=1
    )
    out["supported"] = out["loans_observed_24m"] >= min_observed
    out["window_start"] = window_start.date()
    out["window_end"] = as_of.date()

    return out[
        group_cols
        + ["loans_total_24m","loans_observed_24m","publications_observed_24m",
           "publication_rate_observed","coverage","supported","window_start","window_end"]
    ]


def _normalize_clips_received(value) -> bool:
    """
    Normalize clips_received values to boolean.

    Accepts various truthy/falsy representations and converts to bool.
    Returns False for None/NaN/empty values.

    Args:
        value: Input value to normalize

    Returns:
        Boolean representing whether clips were received
    """
    if value is None or pd.isna(value):
        return False

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        v_lower = value.lower().strip()
        if v_lower in ['true', '1', 'yes', 'y']:
            return True
        elif v_lower in ['false', '0', 'no', 'n', '']:
            return False
        else:
            # For other strings, treat as falsy to be conservative
            return False

    if isinstance(value, (int, float)):
        return bool(value)

    # For any other type, treat as falsy
    return False