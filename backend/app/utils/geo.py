"""
Geospatial utility functions for distance calculations.
"""

import math
from typing import Optional


def haversine_distance(lat1: Optional[float], lon1: Optional[float],
                       lat2: Optional[float], lon2: Optional[float]) -> Optional[float]:
    """
    Calculate the great circle distance between two points on Earth in miles.
    Uses the Haversine formula.

    Args:
        lat1: Latitude of point 1 in decimal degrees
        lon1: Longitude of point 1 in decimal degrees
        lat2: Latitude of point 2 in decimal degrees
        lon2: Longitude of point 2 in decimal degrees

    Returns:
        Distance in miles, or None if any coordinate is missing
    """
    # Check if any coordinate is None
    if None in (lat1, lon1, lat2, lon2):
        return None

    # Convert to radians
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)

    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.asin(math.sqrt(a))

    # Earth's radius in miles
    radius_miles = 3959.0

    return c * radius_miles


def normalize_distance_score(distance_miles: Optional[float],
                              max_distance: float = 500.0) -> float:
    """
    Convert distance to a normalized score (0-1) where closer is better.

    Args:
        distance_miles: Distance in miles
        max_distance: Maximum distance to consider (default 500 miles)

    Returns:
        Normalized score: 1.0 for distance=0, 0.0 for distance>=max_distance
    """
    if distance_miles is None:
        return 0.0  # No location data = worst score

    if distance_miles >= max_distance:
        return 0.0

    # Linear decay: score = 1 - (distance / max_distance)
    return 1.0 - (distance_miles / max_distance)