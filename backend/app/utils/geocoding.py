"""
Geocoding utilities using Google Maps API
"""
import os
import requests
from typing import Optional, Tuple
import math

GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', 'AIzaSyBHy38SahWmFPNToFU8IWlH2NeKScPcCCo')


def geocode_address(address: str) -> Optional[Tuple[float, float]]:
    """
    Geocode an address using Google Maps Geocoding API.

    Args:
        address: Street address to geocode

    Returns:
        Tuple of (latitude, longitude) or None if geocoding fails
    """
    if not address or address == 'N/A':
        return None

    try:
        url = 'https://maps.googleapis.com/maps/api/geocode/json'
        params = {
            'address': address,
            'key': GOOGLE_MAPS_API_KEY
        }

        response = requests.get(url, params=params, timeout=5)
        data = response.json()

        if data['status'] == 'OK' and len(data['results']) > 0:
            location = data['results'][0]['geometry']['location']
            return (location['lat'], location['lng'])

        return None
    except Exception as e:
        print(f"Geocoding error for '{address}': {e}")
        return None


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points using Haversine formula.

    Args:
        lat1, lon1: First point coordinates
        lat2, lon2: Second point coordinates

    Returns:
        Distance in miles
    """
    # Earth's radius in miles
    R = 3959.0

    # Convert to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c
    return distance


def get_distance_from_office(partner_address: str, office_lat: float, office_lon: float) -> Optional[dict]:
    """
    Calculate distance from partner address to office.

    Args:
        partner_address: Partner's street address
        office_lat: Office latitude
        office_lon: Office longitude

    Returns:
        Dict with distance_miles and location_type ('local' or 'remote')
    """
    coords = geocode_address(partner_address)
    if not coords:
        return None

    partner_lat, partner_lon = coords
    distance = calculate_distance(office_lat, office_lon, partner_lat, partner_lon)

    # Classify as local (<50 miles) or remote (>=50 miles)
    location_type = 'local' if distance < 50 else 'remote'

    return {
        'distance_miles': round(distance, 1),
        'location_type': location_type,
        'partner_latitude': partner_lat,
        'partner_longitude': partner_lon
    }
