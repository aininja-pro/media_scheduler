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
