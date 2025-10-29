"""
Vehicle Chain Builder - Geographic Distance Calculations

This module handles geographic distance calculations between media partners
for same-day handoff optimization in vehicle-centric chains.

Key use case: When vehicle transitions from Partner A → Partner B on same day,
we need to minimize drive distance/time for logistics feasibility.
"""

import logging
from typing import Dict, Tuple, List
from math import radians, cos, sin, asin, sqrt
import pandas as pd

logger = logging.getLogger(__name__)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate great-circle distance between two points using Haversine formula.

    Returns distance in miles.

    Args:
        lat1: Latitude of point 1 (decimal degrees)
        lon1: Longitude of point 1 (decimal degrees)
        lat2: Latitude of point 2 (decimal degrees)
        lon2: Longitude of point 2 (decimal degrees)

    Returns:
        Distance in miles (float)
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))

    # Radius of Earth in miles
    radius_earth_miles = 3956

    distance_miles = c * radius_earth_miles

    return distance_miles


def calculate_distance_matrix(partners_df: pd.DataFrame) -> Dict[Tuple[int, int], float]:
    """
    Calculate pairwise distances between all partners.

    Returns distance matrix as dict: {(partner_id_1, partner_id_2): miles}

    Args:
        partners_df: DataFrame with columns: person_id, latitude, longitude

    Returns:
        Dict mapping (partner_id_1, partner_id_2) tuples to distance in miles
    """
    logger.info(f"Calculating distance matrix for {len(partners_df)} partners")

    distance_matrix = {}

    # Filter partners with valid coordinates
    valid_partners = partners_df[
        partners_df['latitude'].notna() & partners_df['longitude'].notna()
    ].copy()

    if valid_partners.empty:
        logger.warning("No partners with valid latitude/longitude coordinates")
        return distance_matrix

    # Ensure person_id is integer
    valid_partners['person_id'] = valid_partners['person_id'].astype(int)

    # Calculate pairwise distances
    partners_list = valid_partners.to_dict('records')
    total_pairs = len(partners_list) * (len(partners_list) - 1)
    calculated = 0

    for i, p1 in enumerate(partners_list):
        for j, p2 in enumerate(partners_list):
            if i != j:  # Don't calculate distance to self
                p1_id = int(p1['person_id'])
                p2_id = int(p2['person_id'])

                # Calculate distance
                distance = haversine_distance(
                    float(p1['latitude']),
                    float(p1['longitude']),
                    float(p2['latitude']),
                    float(p2['longitude'])
                )

                # Store both directions (should be symmetric)
                distance_matrix[(p1_id, p2_id)] = distance
                calculated += 1

    logger.info(f"Calculated {calculated} pairwise distances ({len(valid_partners)} partners with valid coords)")

    return distance_matrix


def calculate_partner_distances(
    partner_id: int,
    all_partners_df: pd.DataFrame
) -> Dict[int, float]:
    """
    Calculate distances from one partner to all others.

    Args:
        partner_id: Source partner ID
        all_partners_df: DataFrame with all partners (person_id, latitude, longitude)

    Returns:
        Dict mapping partner_id to distance in miles
    """
    # Get source partner
    source = all_partners_df[all_partners_df['person_id'] == partner_id]

    if source.empty:
        logger.warning(f"Partner {partner_id} not found")
        return {}

    source_row = source.iloc[0]

    # Check if source has valid coordinates
    if pd.isna(source_row['latitude']) or pd.isna(source_row['longitude']):
        logger.warning(f"Partner {partner_id} has no valid coordinates")
        return {}

    source_lat = float(source_row['latitude'])
    source_lon = float(source_row['longitude'])

    # Calculate distance to all other partners with valid coords
    distances = {}

    valid_partners = all_partners_df[
        (all_partners_df['person_id'] != partner_id) &
        all_partners_df['latitude'].notna() &
        all_partners_df['longitude'].notna()
    ]

    for _, partner in valid_partners.iterrows():
        target_id = int(partner['person_id'])
        target_lat = float(partner['latitude'])
        target_lon = float(partner['longitude'])

        distance = haversine_distance(source_lat, source_lon, target_lat, target_lon)
        distances[target_id] = distance

    return distances


def get_nearest_partners(
    partner_id: int,
    all_partners_df: pd.DataFrame,
    max_distance: float = None,
    limit: int = None
) -> List[Dict]:
    """
    Get partners sorted by distance from a source partner.

    Args:
        partner_id: Source partner ID
        all_partners_df: DataFrame with all partners
        max_distance: Optional max distance filter (miles)
        limit: Optional limit on number of results

    Returns:
        List of dicts with partner info and distance, sorted by distance ascending
    """
    distances = calculate_partner_distances(partner_id, all_partners_df)

    if not distances:
        return []

    # Build result list
    results = []
    for target_id, distance in distances.items():
        # Apply max distance filter if provided
        if max_distance is not None and distance > max_distance:
            continue

        # Get partner info
        partner = all_partners_df[all_partners_df['person_id'] == target_id]
        if not partner.empty:
            partner_row = partner.iloc[0]
            results.append({
                'person_id': target_id,
                'name': partner_row.get('name', f'Partner {target_id}'),
                'office': partner_row.get('office'),
                'latitude': partner_row.get('latitude'),
                'longitude': partner_row.get('longitude'),
                'distance_miles': round(distance, 2)
            })

    # Sort by distance
    results.sort(key=lambda x: x['distance_miles'])

    # Apply limit if provided
    if limit is not None:
        results = results[:limit]

    return results


def estimate_drive_time(distance_miles: float) -> int:
    """
    Estimate drive time in minutes based on distance.

    Assumes average city driving speed of 20 mph (accounting for traffic, parking, etc.)

    Args:
        distance_miles: Distance in miles

    Returns:
        Estimated drive time in minutes (int)
    """
    # Assume 20 mph average in city
    avg_speed_mph = 20
    drive_time_hours = distance_miles / avg_speed_mph
    drive_time_minutes = drive_time_hours * 60

    return int(round(drive_time_minutes))


def validate_coordinates(partners_df: pd.DataFrame) -> Dict:
    """
    Validate that partners have geocoded coordinates.

    Returns statistics about coordinate coverage.

    Args:
        partners_df: DataFrame with columns: person_id, name, latitude, longitude

    Returns:
        Dict with validation stats
    """
    total = len(partners_df)

    has_lat = partners_df['latitude'].notna().sum()
    has_lon = partners_df['longitude'].notna().sum()
    has_both = (partners_df['latitude'].notna() & partners_df['longitude'].notna()).sum()

    missing_coords = partners_df[
        partners_df['latitude'].isna() | partners_df['longitude'].isna()
    ]

    return {
        'total_partners': total,
        'with_coordinates': has_both,
        'missing_coordinates': total - has_both,
        'coverage_percent': round(has_both / total * 100, 1) if total > 0 else 0,
        'missing_partner_ids': missing_coords['person_id'].tolist() if not missing_coords.empty else []
    }


def score_partners_base(
    partners_df: pd.DataFrame,
    vehicle_make: str,
    approved_makes_df: pd.DataFrame,
    loan_history_df: pd.DataFrame = None
) -> Dict[int, Dict]:
    """
    Calculate base partner scores WITHOUT distance penalty.

    Distance is handled separately by OR-Tools solver for optimal routing.

    Base score components:
    - Engagement level: Active=100, Neutral=50, Dormant=0
    - Publication rate: Based on clips_received in loan history
    - Tier preference: Partner's rank for this make (A+=100, A=75, B=50, C=25)

    Args:
        partners_df: Partners with person_id, name, engagement_level
        vehicle_make: Vehicle make (e.g., 'Audi') for tier lookup
        approved_makes_df: Approved makes with person_id, make, rank
        loan_history_df: Optional - for publication rate calculation

    Returns:
        Dict mapping person_id to score info:
        {
            person_id: {
                'base_score': int,
                'engagement_score': int,
                'publication_score': int,
                'tier_score': int,
                'tier_rank': str,
                'engagement_level': str,
                'publication_rate': float
            }
        }
    """
    logger.info(f"Scoring partners for make: {vehicle_make}")

    scores = {}

    # Convert approved_makes person_id to int (stored as string in DB)
    approved_makes_copy = approved_makes_df.copy()
    approved_makes_copy['person_id'] = pd.to_numeric(approved_makes_copy['person_id'], errors='coerce').astype('Int64')

    # Get tier rankings for this make
    make_ranks = approved_makes_copy[
        approved_makes_copy['make'].str.lower() == vehicle_make.lower()
    ]

    # Create mapping: person_id -> rank
    rank_map = {}
    if not make_ranks.empty:
        for _, row in make_ranks.iterrows():
            pid = int(row['person_id'])
            rank_map[pid] = row['rank']

    logger.info(f"Found {len(rank_map)} partners with tier rankings for {vehicle_make}")

    # Calculate publication rates if loan history provided
    publication_rates = {}
    if loan_history_df is not None and not loan_history_df.empty:
        if 'person_id' in loan_history_df.columns and 'clips_received' in loan_history_df.columns:
            # Group by partner
            for person_id in loan_history_df['person_id'].unique():
                partner_loans = loan_history_df[loan_history_df['person_id'] == person_id]
                total_loans = len(partner_loans)

                if total_loans > 0:
                    # Count loans where clips_received = 1.0 (published)
                    published = partner_loans['clips_received'].apply(
                        lambda x: str(x) == '1.0' if pd.notna(x) else False
                    ).sum()

                    publication_rate = published / total_loans
                    publication_rates[int(person_id)] = publication_rate

    logger.info(f"Calculated publication rates for {len(publication_rates)} partners")

    # Score each partner
    for _, partner in partners_df.iterrows():
        person_id = int(partner['person_id'])

        # 1. Engagement score (0-100)
        engagement_level = partner.get('engagement_level', 'neutral')
        if pd.isna(engagement_level) or not engagement_level:
            engagement_level = 'neutral'

        engagement_level = str(engagement_level).lower()

        if engagement_level == 'active':
            engagement_score = 100
        elif engagement_level == 'neutral':
            engagement_score = 50
        else:  # dormant or unknown
            engagement_score = 0

        # 2. Publication score (0-100)
        # Use publication rate from loan history
        pub_rate = publication_rates.get(person_id, 0.0)
        publication_score = int(pub_rate * 100)  # 0-100 scale

        # 3. Tier score (0-100)
        rank = rank_map.get(person_id)
        if rank == 'A+' or rank == 'A':
            tier_score = 100
        elif rank == 'B':
            tier_score = 75
        elif rank == 'C':
            tier_score = 50
        else:
            # No rank for this make
            tier_score = 0

        # Base score is sum of all components
        base_score = engagement_score + publication_score + tier_score

        scores[person_id] = {
            'base_score': base_score,
            'engagement_score': engagement_score,
            'publication_score': publication_score,
            'tier_score': tier_score,
            'tier_rank': rank if rank else 'N/A',
            'engagement_level': engagement_level,
            'publication_rate': round(pub_rate, 3)
        }

    logger.info(f"Scored {len(scores)} partners (base scores only, no distance penalty)")

    return scores
