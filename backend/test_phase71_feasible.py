"""
Test Phase 7.1: Feasible triples generation for OR-Tools.

This test verifies that we can build the correct set of feasible
(vehicle, partner, start_day) combinations.
"""

import pandas as pd
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.solver.ortools_feasible import (
    build_feasible_triples,
    filter_triples_by_cooldown,
    filter_triples_by_current_activity,
    validate_triple_counts
)
from app.etl.cooldown import compute_cooldown_flags


def test_basic_feasible_triples():
    """Test basic triple generation with simple data."""

    # Create test data
    vehicles = pd.DataFrame([
        {'vin': 'VIN001', 'make': 'Toyota', 'model': 'Camry', 'office': 'Los Angeles'},
        {'vin': 'VIN002', 'make': 'Honda', 'model': 'Accord', 'office': 'Los Angeles'},
        {'vin': 'VIN003', 'make': 'Ford', 'model': 'F150', 'office': 'Denver'},  # Different office
    ])

    partners = pd.DataFrame([
        {'person_id': 'P001', 'name': 'Alice', 'office': 'Los Angeles'},
        {'person_id': 'P002', 'name': 'Bob', 'office': 'Los Angeles'},
        {'person_id': 'P003', 'name': 'Charlie', 'office': 'Denver'},  # Different office
    ])

    # Create availability (all LA vehicles available all week)
    availability = []
    for vin in ['VIN001', 'VIN002']:
        for day in range(7):
            availability.append({
                'vin': vin,
                'date': f'2024-09-{22+day:02d}',
                'available': True
            })

    availability_df = pd.DataFrame(availability)

    # Build triples for LA office
    triples = build_feasible_triples(
        vehicles_df=vehicles,
        partners_df=partners,
        availability_df=availability_df,
        week_start='2024-09-22',
        office='Los Angeles',
        min_available_days=7
    )

    print("Test 1: Basic Feasible Triples")
    print(f"Generated {len(triples)} triples")

    # Should have 2 vehicles × 2 partners × 1 start day (Monday only for 7-day requirement)
    assert len(triples) == 4, f"Expected 4 triples, got {len(triples)}"

    # Check that all are LA office
    for _, _, _, metadata in triples:
        assert metadata['office'] == 'Los Angeles'

    # Check unique counts
    unique_vins = set(t[0] for t in triples)
    unique_partners = set(t[1] for t in triples)
    assert len(unique_vins) == 2, f"Expected 2 unique VINs, got {len(unique_vins)}"
    assert len(unique_partners) == 2, f"Expected 2 unique partners, got {len(unique_partners)}"

    print("✓ Basic triple generation passed")
    return triples


def test_cooldown_filtering():
    """Test that cooldown filtering works correctly."""

    # Create test triples with metadata
    triples = [
        ('VIN001', 'P001', 0, {'make': 'Toyota', 'model': 'Camry', 'office': 'LA'}),
        ('VIN002', 'P001', 0, {'make': 'Honda', 'model': 'Accord', 'office': 'LA'}),
        ('VIN003', 'P002', 0, {'make': 'Toyota', 'model': 'Highlander', 'office': 'LA'}),
    ]

    # Create cooldown data - P001 can't have Toyota Camry
    cooldown_df = pd.DataFrame([
        {'person_id': 'P001', 'make': 'Toyota', 'model': 'Camry', 'cooldown_ok': False},
        {'person_id': 'P001', 'make': 'Honda', 'model': 'Accord', 'cooldown_ok': True},
        {'person_id': 'P002', 'make': 'Toyota', 'model': 'Highlander', 'cooldown_ok': True},
    ])

    # Filter by cooldown
    filtered = filter_triples_by_cooldown(triples, cooldown_df)

    print("\nTest 2: Cooldown Filtering")
    print(f"Filtered from {len(triples)} to {len(filtered)} triples")

    # Should remove the P001-Toyota Camry triple
    assert len(filtered) == 2, f"Expected 2 triples after cooldown, got {len(filtered)}"

    # Check that P001-Toyota Camry is removed
    for vin, person_id, _, metadata in filtered:
        if person_id == 'P001' and metadata['make'] == 'Toyota':
            assert False, "P001-Toyota Camry should have been filtered out"

    print("✓ Cooldown filtering passed")
    return filtered


def test_activity_filtering():
    """Test that current activity filtering works correctly."""

    # Create test triples
    triples = [
        ('VIN001', 'P001', 0, {'make': 'Toyota', 'model': 'Camry'}),
        ('VIN002', 'P002', 0, {'make': 'Honda', 'model': 'Accord'}),
        ('VIN003', 'P003', 0, {'make': 'Ford', 'model': 'F150'}),
    ]

    # P001 has an active vehicle during the week
    current_activity = pd.DataFrame([
        {'person_id': 'P001', 'start_date': '2024-09-20', 'end_date': '2024-09-25'},
    ])

    # Filter by activity
    filtered = filter_triples_by_current_activity(
        triples,
        current_activity,
        week_start='2024-09-22'
    )

    print("\nTest 3: Activity Filtering")
    print(f"Filtered from {len(triples)} to {len(filtered)} triples")

    # Should remove P001
    assert len(filtered) == 2, f"Expected 2 triples after activity filter, got {len(filtered)}"

    # Check that P001 is removed
    for _, person_id, _, _ in filtered:
        assert person_id != 'P001', "P001 should have been filtered out due to active vehicle"

    print("✓ Activity filtering passed")


def test_multi_day_starts():
    """Test that we can generate triples for different start days."""

    vehicles = pd.DataFrame([
        {'vin': 'VIN001', 'make': 'Toyota', 'model': 'Camry', 'office': 'LA'},
    ])

    partners = pd.DataFrame([
        {'person_id': 'P001', 'name': 'Alice', 'office': 'LA'},
    ])

    # Vehicle available all week
    availability = []
    for day in range(7):
        availability.append({
            'vin': 'VIN001',
            'date': f'2024-09-{22+day:02d}',
            'available': True
        })

    availability_df = pd.DataFrame(availability)

    # Build with shorter min days to allow multiple start days
    triples = build_feasible_triples(
        vehicles_df=vehicles,
        partners_df=partners,
        availability_df=availability_df,
        week_start='2024-09-22',
        office='LA',
        min_available_days=3  # Allow 3-day loans
    )

    print("\nTest 4: Multi-day Starts")
    print(f"Generated {len(triples)} triples")

    # Check start days
    start_days = set(t[2] for t in triples)
    print(f"Start days available: {sorted(start_days)}")

    # With 3-day minimum, we should have Monday-Friday starts (0-4)
    assert len(start_days) >= 5, f"Expected at least 5 start days, got {len(start_days)}"

    print("✓ Multi-day start generation passed")


def test_approved_makes_eligibility():
    """Test that approved makes correctly filter eligibility."""

    vehicles = pd.DataFrame([
        {'vin': 'VIN001', 'make': 'Toyota', 'model': 'Camry', 'office': 'LA'},
        {'vin': 'VIN002', 'make': 'Honda', 'model': 'Accord', 'office': 'LA'},
    ])

    partners = pd.DataFrame([
        {'person_id': 'P001', 'name': 'Alice', 'office': 'LA'},
        {'person_id': 'P002', 'name': 'Bob', 'office': 'LA'},
    ])

    # P001 approved for Toyota only, P002 for Honda only
    approved_makes = pd.DataFrame([
        {'person_id': 'P001', 'make': 'Toyota', 'rank': 'A'},
        {'person_id': 'P002', 'make': 'Honda', 'rank': 'B'},
    ])

    # All vehicles available
    availability = []
    for vin in ['VIN001', 'VIN002']:
        for day in range(7):
            availability.append({
                'vin': vin,
                'date': f'2024-09-{22+day:02d}',
                'available': True
            })

    availability_df = pd.DataFrame(availability)

    # Build with approved makes
    triples = build_feasible_triples(
        vehicles_df=vehicles,
        partners_df=partners,
        availability_df=availability_df,
        week_start='2024-09-22',
        office='LA',
        approved_makes_df=approved_makes,
        min_available_days=7
    )

    print("\nTest 5: Approved Makes Eligibility")
    print(f"Generated {len(triples)} triples")

    # Should have 2 triples: P001-Toyota, P002-Honda
    assert len(triples) == 2, f"Expected 2 triples, got {len(triples)}"

    # Check correct pairings
    for vin, person_id, _, metadata in triples:
        if person_id == 'P001':
            assert metadata['make'] == 'Toyota', "P001 should only get Toyota"
            assert metadata['rank'] == 'A', "P001 should have rank A"
        elif person_id == 'P002':
            assert metadata['make'] == 'Honda', "P002 should only get Honda"
            assert metadata['rank'] == 'B', "P002 should have rank B"

    print("✓ Approved makes eligibility passed")


if __name__ == "__main__":
    test_basic_feasible_triples()
    test_cooldown_filtering()
    test_activity_filtering()
    test_multi_day_starts()
    test_approved_makes_eligibility()

    print("\n=== ALL PHASE 7.1 TESTS PASSED ===")
    print("Feasible triples generation is working correctly!")
    print("Ready to proceed to Phase 7.2: Core OR-Tools model")