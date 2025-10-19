"""
Media cost lookup utility - Real cost per media partner per make

Uses historical data from "Media Cost Per Loan.xlsx" to calculate
accurate budget projections instead of flat $1,000 default.

Three-tier lookup:
1. Exact match (person_id + make) - most accurate
2. Partner average (person_id avg across all makes) - fallback
3. Default base cost ($400) - last resort
"""

import json
import os
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Default base cost when no data available
DEFAULT_BASE_COST = 400.0

# Global cache for cost data
_cost_data_cache: Optional[Dict] = None


def load_media_cost_data() -> Dict:
    """
    Load media cost data from JSON file.

    Returns dictionary structure:
    {
        "14096": {
            "name": "Aubernon, Cameron",
            "avg": 698.57,
            "makes": {
                "Acura": 730.39,
                "Toyota": 716.67,
                ...
            }
        },
        ...
    }
    """
    global _cost_data_cache

    # Return cached data if already loaded
    if _cost_data_cache is not None:
        return _cost_data_cache

    # Load from file
    data_path = os.path.join(
        os.path.dirname(__file__),
        '..',
        '..',
        'data',
        'media_costs_per_loan.json'
    )

    try:
        with open(data_path, 'r') as f:
            _cost_data_cache = json.load(f)
            logger.info(f"Loaded cost data for {len(_cost_data_cache)} media partners")
            return _cost_data_cache
    except FileNotFoundError:
        logger.warning(f"Media cost file not found at {data_path}, using default costs")
        return {}
    except Exception as e:
        logger.error(f"Error loading media cost data: {e}")
        return {}


def get_cost_for_assignment(
    person_id: int,
    make: str,
    default_cost: float = DEFAULT_BASE_COST
) -> Dict[str, any]:
    """
    Get cost for a specific media partner + make assignment.

    Uses 3-tier lookup:
    1. Exact match: person_id + make in cost data
    2. Partner average: person_id exists but make not found
    3. Default: person_id not in cost data

    Args:
        person_id: Media partner ID
        make: Vehicle make (e.g., "Toyota", "Honda")
        default_cost: Fallback cost if no data found

    Returns:
        Dictionary with:
        - cost: Dollar amount
        - tier: "exact" | "partner_avg" | "default"
        - source: Description of where cost came from
    """
    cost_data = load_media_cost_data()

    person_id_str = str(person_id)

    # Tier 3: Default (partner not found)
    if person_id_str not in cost_data:
        return {
            'cost': default_cost,
            'tier': 'default',
            'source': f'Default base cost (partner {person_id} not in cost data)'
        }

    partner = cost_data[person_id_str]
    partner_name = partner.get('name', f'Partner {person_id}')

    # Tier 1: Exact match (partner + make)
    if make in partner.get('makes', {}):
        cost = partner['makes'][make]
        return {
            'cost': cost,
            'tier': 'exact',
            'source': f'{partner_name} + {make} (exact match)'
        }

    # Tier 2: Partner average (partner found, but not this make)
    if partner.get('avg') is not None:
        cost = partner['avg']
        return {
            'cost': cost,
            'tier': 'partner_avg',
            'source': f'{partner_name} average (no {make} data)'
        }

    # Fallback to default if avg is also missing
    return {
        'cost': default_cost,
        'tier': 'default',
        'source': f'Default base cost ({partner_name} has no cost data)'
    }


def calculate_assignment_costs(assignments: list) -> Dict:
    """
    Calculate costs for a list of assignments.

    Args:
        assignments: List of dicts with person_id, make keys

    Returns:
        Dictionary with:
        - total_cost: Sum of all assignment costs
        - by_tier: Breakdown by lookup tier
        - details: List of per-assignment costs
    """
    total_cost = 0.0
    tier_counts = {'exact': 0, 'partner_avg': 0, 'default': 0}
    details = []

    for assignment in assignments:
        person_id = assignment.get('person_id')
        make = assignment.get('make')

        if not person_id or not make:
            continue

        cost_info = get_cost_for_assignment(person_id, make)
        total_cost += cost_info['cost']
        tier_counts[cost_info['tier']] += 1

        details.append({
            'person_id': person_id,
            'partner_name': assignment.get('partner_name', ''),
            'make': make,
            'model': assignment.get('model', ''),
            'cost': cost_info['cost'],
            'tier': cost_info['tier'],
            'source': cost_info['source']
        })

    return {
        'total_cost': total_cost,
        'average_cost': total_cost / len(assignments) if assignments else 0,
        'tier_breakdown': tier_counts,
        'details': details
    }


if __name__ == '__main__':
    # Test the lookup function
    print("Testing cost lookup function:")

    # Test 1: Exact match
    result1 = get_cost_for_assignment(14096, 'Toyota')
    print(f"\n1. Exact match: {result1}")

    # Test 2: Partner avg (make not found)
    result2 = get_cost_for_assignment(14096, 'Lamborghini')
    print(f"\n2. Partner avg: {result2}")

    # Test 3: Default (partner not found)
    result3 = get_cost_for_assignment(99999, 'Honda')
    print(f"\n3. Default: {result3}")

    # Test 4: Batch calculation
    test_assignments = [
        {'person_id': 14096, 'make': 'Toyota', 'partner_name': 'Aubernon, Cameron'},
        {'person_id': 17658, 'make': 'Honda', 'partner_name': 'Aaron, John'},
        {'person_id': 99999, 'make': 'Mazda', 'partner_name': 'Unknown Person'},
    ]

    result4 = calculate_assignment_costs(test_assignments)
    print(f"\n4. Batch calculation:")
    print(f"   Total: ${result4['total_cost']:.2f}")
    print(f"   Average: ${result4['average_cost']:.2f}")
    print(f"   Tier breakdown: {result4['tier_breakdown']}")
