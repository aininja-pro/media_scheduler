"""
Phase 7.8: Objective Shaping (Weights, not filters)

Make scoring knobs explicit for intuitive control without changing feasibility.
Only shapes the objective function, keeps all hard constraints as-is.
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional, Any

from ..utils.geo import normalize_distance_score


# Default weights for objective components
DEFAULT_W_RANK = 1.0      # Multiplier for rank_weight (already 500-1000)
DEFAULT_W_GEO = 100       # Bonus for same-office match
DEFAULT_W_PUB = 150       # Bonus for publication rate (0-1 normalized)
DEFAULT_W_RECENCY = 50    # Weight for engagement recency (replaces history)
DEFAULT_W_PREFERRED_DAY = 0  # Weight for preferred day match (0=off by default)


def apply_objective_shaping(
    triples_df: pd.DataFrame,
    w_rank: float = DEFAULT_W_RANK,
    w_geo: float = DEFAULT_W_GEO,
    w_pub: float = DEFAULT_W_PUB,
    w_recency: float = DEFAULT_W_RECENCY,
    engagement_mode: str = 'neutral',  # 'dormant', 'neutral', or 'momentum'
    w_preferred_day: float = DEFAULT_W_PREFERRED_DAY,
    verbose: bool = False
) -> pd.DataFrame:
    """
    Apply objective shaping to compute shaped scores.

    Args:
        triples_df: DataFrame with columns:
            - rank_weight: Base score from rank (e.g., 500-1000)
            - distance_miles: Distance between partner and office (preferred)
            - geo_office_match: 0/1 for same office (legacy fallback)
            - pub_rate_24m: Publication rate 0-1 or 0-100
            - days_since_last_loan: Days since partner's last loan for this make
            - Additional columns preserved
        w_rank: Weight for rank component
        w_geo: Weight for geographic proximity (uses distance if available)
        w_pub: Weight for publication rate
        w_recency: Weight for engagement recency
        engagement_mode: How to score recency
            - 'dormant': Favor partners who haven't had recent loans (re-engage)
            - 'neutral': No recency preference
            - 'momentum': Favor recently active partners (maintain momentum)
        verbose: Print shaping details

    Returns:
        DataFrame with 'score_shaped' column added
    """
    df = triples_df.copy()

    # Validate required columns
    required_cols = ['rank_weight']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    # Initialize optional columns if missing
    if 'geo_office_match' not in df.columns:
        df['geo_office_match'] = 0
    if 'pub_rate_24m' not in df.columns:
        df['pub_rate_24m'] = 0
    if 'days_since_last_loan' not in df.columns:
        df['days_since_last_loan'] = None
    if 'preferred_day_match' not in df.columns:
        df['preferred_day_match'] = False

    # Normalize publication rate if it's in percentage (0-100)
    pub_rate_normalized = df['pub_rate_24m'].copy()
    if pub_rate_normalized.max() > 1.0:
        pub_rate_normalized = pub_rate_normalized / 100.0

    # Calculate geographic proximity score
    # Prefer distance_miles if available, otherwise fall back to binary geo_office_match
    if 'distance_miles' in df.columns:
        # Convert distance to normalized score (0-1 where closer is better)
        # Handle NaN values by falling back to geo_office_match for those rows
        def calc_geo_score(row):
            dist = row.get('distance_miles')
            if pd.notna(dist):
                return float(normalize_distance_score(dist, max_distance=500.0))
            else:
                # Fallback to binary match when distance is unavailable
                match_val = row.get('geo_office_match', 0)
                # Convert boolean to int/float if needed
                if isinstance(match_val, bool):
                    return float(match_val)
                return float(match_val) if match_val else 0.0

        geo_score = df.apply(calc_geo_score, axis=1).astype(float)
    else:
        # Fallback to binary match for backward compatibility
        # Ensure numeric conversion
        geo_score = pd.to_numeric(df['geo_office_match'], errors='coerce').fillna(0.0)

    # Calculate engagement recency score
    def calc_recency_score(days_since):
        """
        Calculate recency score based on engagement mode.

        dormant mode: Favor partners who haven't had loans recently (re-engage)
        neutral mode: No recency preference
        momentum mode: Favor recently active partners (maintain momentum)
        """
        if pd.isna(days_since):
            # No history - treat as neutral (0.5 score)
            return 0.5

        if engagement_mode == 'dormant':
            # Older = better (up to 90 days gets full score)
            return min(1.0, days_since / 90.0)
        elif engagement_mode == 'momentum':
            # Newer = better (within 30 days gets full score)
            return max(0.0, (30 - days_since) / 30.0)
        else:  # neutral
            return 0.0  # No recency weight

    recency_score = df['days_since_last_loan'].apply(calc_recency_score).astype(float)

    # Calculate preferred day score (simple binary: 1 if match, 0 if not)
    preferred_day_score = pd.to_numeric(df['preferred_day_match'], errors='coerce').fillna(0.0).astype(float)

    # Add tiny deterministic tie-breaker based on VIN/person hash
    # This ensures deterministic selection when scores are equal
    if 'vin' in df.columns and 'person_id' in df.columns:
        # Create deterministic hash from VIN and person_id
        df['_tiebreaker'] = df.apply(
            lambda row: hash(f"{row['vin']}_{row['person_id']}") % 10000 / 1000000.0,
            axis=1
        )
    else:
        df['_tiebreaker'] = 0

    # Compute shaped score
    df['score_shaped'] = (
        w_rank * df['rank_weight'] +
        w_geo * geo_score +
        w_pub * pub_rate_normalized +
        w_recency * recency_score +
        w_preferred_day * preferred_day_score +
        df['_tiebreaker']  # Tiny deterministic noise
    )

    # Round to avoid floating point issues
    df['score_shaped'] = df['score_shaped'].round(6)

    # Store component contributions for reporting
    df['_score_rank'] = w_rank * df['rank_weight']
    df['_score_geo'] = w_geo * geo_score
    df['_score_pub'] = w_pub * pub_rate_normalized
    df['_score_recency'] = w_recency * recency_score
    df['_score_preferred_day'] = w_preferred_day * preferred_day_score

    if verbose:
        print(f"\n=== Objective Shaping Applied ===")
        print(f"  Weights: rank={w_rank}, geo={w_geo}, pub={w_pub}, recency={w_recency}, preferred_day={w_preferred_day}")
        print(f"  Engagement mode: {engagement_mode}")
        print(f"  Triples: {len(df):,}")
        print(f"  Score range: {df['score_shaped'].min():.1f} - {df['score_shaped'].max():.1f}")

        # Sample statistics
        if 'distance_miles' in df.columns:
            valid_distances = df[df['distance_miles'].notna()]['distance_miles']
            if len(valid_distances) > 0:
                print(f"  Distance range: {valid_distances.min():.1f} - {valid_distances.max():.1f} miles")
                print(f"  Avg distance: {valid_distances.mean():.1f} miles")
            print(f"  With distance: {valid_distances.count():,} ({valid_distances.count()/len(df)*100:.1f}%)")
        else:
            geo_matches = df['geo_office_match'].sum()
            print(f"  Geo matches: {geo_matches:,} ({geo_matches/len(df)*100:.1f}%)")

        avg_pub_rate = pub_rate_normalized.mean()
        print(f"  Avg pub rate: {avg_pub_rate:.3f}")

        # Recency statistics
        if 'days_since_last_loan' in df.columns:
            valid_recency = df[df['days_since_last_loan'].notna()]['days_since_last_loan']
            if len(valid_recency) > 0:
                print(f"  Days since last loan: min={valid_recency.min():.0f}, max={valid_recency.max():.0f}, avg={valid_recency.mean():.0f}")
            print(f"  With recency data: {valid_recency.count():,} ({valid_recency.count()/len(df)*100:.1f}%)")

        # Preferred day statistics
        preferred_day_matches = df['preferred_day_match'].sum()
        print(f"  Preferred day matches: {preferred_day_matches:,} ({preferred_day_matches/len(df)*100:.1f}%)")

    return df


def build_shaping_breakdown(
    selected_assignments: list,
    w_rank: float = DEFAULT_W_RANK,
    w_geo: float = DEFAULT_W_GEO,
    w_pub: float = DEFAULT_W_PUB,
    w_recency: float = DEFAULT_W_RECENCY
) -> Dict[str, Any]:
    """
    Build breakdown of objective components for selected assignments.

    Args:
        selected_assignments: List of selected assignment dicts
        w_rank: Weight for rank component
        w_geo: Weight for geographic match
        w_pub: Weight for publication rate
        w_recency: Weight for engagement recency

    Returns:
        Dict with component sums and statistics
    """
    if not selected_assignments:
        return {
            'weights': {
                'w_rank': w_rank,
                'w_geo': w_geo,
                'w_pub': w_pub,
                'w_recency': w_recency
            },
            'components': {
                'rank_total': 0,
                'geo_total': 0,
                'pub_total': 0,
                'recency_total': 0,
                'total': 0
            },
            'counts': {
                'geo_matches': 0,
                'with_recency_data': 0,
                'avg_pub_rate': 0
            }
        }

    # Calculate component sums
    rank_total = sum(a.get('_score_rank', 0) for a in selected_assignments)
    geo_total = sum(a.get('_score_geo', 0) for a in selected_assignments)
    pub_total = sum(a.get('_score_pub', 0) for a in selected_assignments)
    recency_total = sum(a.get('_score_recency', 0) for a in selected_assignments)

    # Calculate counts
    geo_matches = sum(1 for a in selected_assignments if a.get('geo_office_match', 0) == 1)
    with_recency_data = sum(1 for a in selected_assignments if a.get('days_since_last_loan') is not None)

    # Calculate average publication rate
    pub_rates = [a.get('pub_rate_24m', 0) for a in selected_assignments]
    if pub_rates:
        # Normalize if needed
        max_rate = max(pub_rates)
        if max_rate > 1.0:
            pub_rates = [r / 100.0 for r in pub_rates]
        avg_pub_rate = sum(pub_rates) / len(pub_rates)
    else:
        avg_pub_rate = 0

    return {
        'weights': {
            'w_rank': w_rank,
            'w_geo': w_geo,
            'w_pub': w_pub,
            'w_recency': w_recency
        },
        'components': {
            'rank_total': round(rank_total, 2),
            'geo_total': round(geo_total, 2),
            'pub_total': round(pub_total, 2),
            'recency_total': round(recency_total, 2),
            'total': round(rank_total + geo_total + pub_total + recency_total, 2)
        },
        'counts': {
            'geo_matches': geo_matches,
            'with_recency_data': with_recency_data,
            'avg_pub_rate': round(avg_pub_rate, 3)
        }
    }


def validate_monotonicity(
    triples_df: pd.DataFrame,
    weight_name: str,
    weight_values: list,
    metric_fn: callable,
    verbose: bool = False
) -> Tuple[bool, list]:
    """
    Validate that increasing a weight produces monotonic response in metric.

    Args:
        triples_df: Input triples DataFrame
        weight_name: Name of weight to vary ('w_geo', 'w_pub', etc)
        weight_values: List of weight values to test
        metric_fn: Function that takes shaped_df and returns metric value
        verbose: Print validation details

    Returns:
        Tuple of (is_monotonic, metric_values)
    """
    metric_values = []

    for w_val in weight_values:
        # Set weights
        weights = {
            'w_rank': DEFAULT_W_RANK,
            'w_geo': DEFAULT_W_GEO,
            'w_pub': DEFAULT_W_PUB,
            'w_recency': DEFAULT_W_RECENCY
        }
        weights[weight_name] = w_val

        # Apply shaping
        shaped_df = apply_objective_shaping(
            triples_df,
            **weights,
            verbose=False
        )

        # Calculate metric
        metric = metric_fn(shaped_df)
        metric_values.append(metric)

        if verbose:
            print(f"  {weight_name}={w_val}: metric={metric:.3f}")

    # Check monotonicity
    is_monotonic = all(
        metric_values[i] <= metric_values[i+1]
        for i in range(len(metric_values)-1)
    )

    return is_monotonic, metric_values