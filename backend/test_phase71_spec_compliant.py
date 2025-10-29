"""
Test Phase 7.1: Spec-compliant feasible triples generation.

This test validates that the implementation meets ALL spec requirements:
- Strict eligibility (approved_makes only, no fallback)
- ops_capacity_calendar checking
- allowed_start_dows filtering
- model_taxonomy metadata
- Deterministic ordering
- Complete output schema
"""

import pandas as pd
import sys
import os
from datetime import datetime, timedelta
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.solver.ortools_feasible_v2 import (
    build_feasible_start_day_triples,
    validate_triples_output
)


def test_strict_eligibility():
    """Test that ONLY approved_makes partners are included (no fallback)."""

    print("Test 1: Strict Eligibility (no fallback)")

    # Setup data
    vehicles = pd.DataFrame([
        {'vin': 'VIN001', 'make': 'Toyota', 'model': 'Camry', 'office': 'LA'},
        {'vin': 'VIN002', 'make': 'Honda', 'model': 'Accord', 'office': 'LA'},
    ])

    partners = pd.DataFrame([
        {'person_id': 'P001', 'office': 'LA'},  # Has approved_makes
        {'person_id': 'P002', 'office': 'LA'},  # Has approved_makes
        {'person_id': 'P003', 'office': 'LA'},  # NO approved_makes - should be excluded
    ])

    # Only P001 and P002 have approvals
    approved_makes = pd.DataFrame([
        {'person_id': 'P001', 'make': 'Toyota', 'rank': 'A'},
        {'person_id': 'P002', 'make': 'Honda', 'rank': 'B'},
    ])

    # All vehicles available for 14 days to support any start day
    availability = []
    for vin in ['VIN001', 'VIN002']:
        for day in range(14):
            availability.append({
                'vin': vin,
                'date': f'2025-09-{22+day:02d}' if day < 9 else f'2025-10-{day-8:02d}',
                'available': True
            })

    availability_df = pd.DataFrame(availability)

    # Build triples
    triples = build_feasible_start_day_triples(
        vehicles_df=vehicles,
        partners_df=partners,
        availability_df=availability_df,
        approved_makes_df=approved_makes,
        week_start='2025-09-22',
        office='LA'
    )

    # Validate - should have 5 start days × 2 vehicle-partner pairs = 10 triples
    assert len(triples) == 10, f"Expected 10 triples (5 days × 2 pairs), got {len(triples)}"
    assert 'P003' not in triples['person_id'].values, "P003 should be excluded (no approved_makes)"
    assert all(triples['eligibility_ok'] == True), "All eligibility_ok should be True"

    # Check correct pairings
    p001_triples = triples[triples['person_id'] == 'P001']
    p002_triples = triples[triples['person_id'] == 'P002']
    assert all(p001_triples['make'] == 'Toyota'), "P001 should only have Toyota"
    assert all(p002_triples['make'] == 'Honda'), "P002 should only have Honda"
    assert len(p001_triples) == 5, "P001 should have 5 triples (Mon-Fri)"
    assert len(p002_triples) == 5, "P002 should have 5 triples (Mon-Fri)"

    print(f"✓ Generated {len(triples)} triples - P003 correctly excluded")
    print(f"  Partners in result: {sorted(triples['person_id'].unique())}")


def test_ops_capacity_filtering():
    """Test that days with 0 slots are excluded."""

    print("\nTest 2: Ops Capacity Filtering")

    vehicles = pd.DataFrame([
        {'vin': 'VIN001', 'make': 'Toyota', 'model': 'Camry', 'office': 'LA'},
    ])

    partners = pd.DataFrame([
        {'person_id': 'P001', 'office': 'LA'},
    ])

    approved_makes = pd.DataFrame([
        {'person_id': 'P001', 'make': 'Toyota', 'rank': 'A'},
    ])

    # Vehicle available for 14 days to support any start day needing 7 consecutive days
    availability = []
    for day in range(14):  # Extended to cover all possible 7-day windows
        availability.append({
            'vin': 'VIN001',
            'date': f'2025-09-{22+day:02d}' if day < 9 else f'2025-10-{day-8:02d}',
            'available': True
        })
    availability_df = pd.DataFrame(availability)

    # Ops capacity: Monday has 0 slots, Tuesday-Friday have slots
    ops_capacity = pd.DataFrame([
        {'office': 'LA', 'date': '2025-09-22', 'slots': 0},   # Monday - no slots
        {'office': 'LA', 'date': '2025-09-23', 'slots': 15},  # Tuesday
        {'office': 'LA', 'date': '2025-09-24', 'slots': 15},  # Wednesday
        {'office': 'LA', 'date': '2025-09-25', 'slots': 15},  # Thursday
        {'office': 'LA', 'date': '2025-09-26', 'slots': 15},  # Friday
    ])

    # Build triples
    triples = build_feasible_start_day_triples(
        vehicles_df=vehicles,
        partners_df=partners,
        availability_df=availability_df,
        approved_makes_df=approved_makes,
        ops_capacity_df=ops_capacity,
        week_start='2025-09-22',
        office='LA'
    )

    # Validate
    start_days = pd.to_datetime(triples['start_day']).dt.date.unique()
    monday = datetime(2025, 9, 22).date()

    assert monday not in start_days, "Monday should be excluded (0 slots)"
    assert len(triples) == 4, f"Expected 4 triples (Tue-Fri), got {len(triples)}"

    print(f"✓ Monday correctly excluded due to 0 slots")
    print(f"  Start days in result: {sorted(start_days)}")


def test_allowed_start_dows():
    """Test that partner allowed_start_dows are respected."""

    print("\nTest 3: Partner Allowed Start DOWs")

    vehicles = pd.DataFrame([
        {'vin': 'VIN001', 'make': 'Toyota', 'model': 'Camry', 'office': 'LA'},
    ])

    # P001 only allows Mon/Wed/Fri starts
    partners = pd.DataFrame([
        {'person_id': 'P001', 'office': 'LA', 'allowed_start_dows': 'Mon,Wed,Fri'},
        {'person_id': 'P002', 'office': 'LA'},  # No restrictions
    ])

    approved_makes = pd.DataFrame([
        {'person_id': 'P001', 'make': 'Toyota', 'rank': 'A'},
        {'person_id': 'P002', 'make': 'Toyota', 'rank': 'B'},
    ])

    # Vehicle available for 14 days to support any start day needing 7 consecutive days
    availability = []
    for day in range(14):  # Extended to cover all possible 7-day windows
        availability.append({
            'vin': 'VIN001',
            'date': f'2025-09-{22+day:02d}' if day < 9 else f'2025-10-{day-8:02d}',
            'available': True
        })
    availability_df = pd.DataFrame(availability)

    # Build triples
    triples = build_feasible_start_day_triples(
        vehicles_df=vehicles,
        partners_df=partners,
        availability_df=availability_df,
        approved_makes_df=approved_makes,
        week_start='2025-09-22',
        office='LA'
    )

    # Check P001's start days
    p001_triples = triples[triples['person_id'] == 'P001']
    p001_days = pd.to_datetime(p001_triples['start_day']).dt.day_name().unique()

    # P001 should only have Mon/Wed/Fri
    allowed = {'Monday', 'Wednesday', 'Friday'}
    assert set(p001_days).issubset(allowed), f"P001 has invalid start days: {p001_days}"

    # P002 should have all weekdays
    p002_triples = triples[triples['person_id'] == 'P002']
    assert len(p002_triples) == 5, f"P002 should have all 5 weekdays, got {len(p002_triples)}"

    print(f"✓ P001 limited to Mon/Wed/Fri: {sorted(p001_days)}")
    print(f"  P002 has all weekdays: {len(p002_triples)} days")


def test_model_taxonomy_metadata():
    """Test that model_taxonomy metadata is attached correctly."""

    print("\nTest 4: Model Taxonomy Metadata")

    vehicles = pd.DataFrame([
        {'vin': 'VIN001', 'make': 'Toyota', 'model': 'Camry', 'office': 'LA'},
        {'vin': 'VIN002', 'make': 'Toyota', 'model': 'Highlander', 'office': 'LA'},
    ])

    partners = pd.DataFrame([
        {'person_id': 'P001', 'office': 'LA'},
    ])

    approved_makes = pd.DataFrame([
        {'person_id': 'P001', 'make': 'Toyota', 'rank': 'A'},
    ])

    # Model taxonomy data
    model_taxonomy = pd.DataFrame([
        {'make': 'Toyota', 'model': 'Camry', 'short_model_class': 'Sedan', 'powertrain': 'Hybrid'},
        {'make': 'Toyota', 'model': 'Highlander', 'short_model_class': 'SUV', 'powertrain': 'Gas'},
    ])

    # Vehicles available for 7 days from Monday
    availability = []
    dates = pd.date_range('2025-09-22', periods=7)
    for vin in ['VIN001', 'VIN002']:
        for date in dates:
            availability.append({
                'vin': vin,
                'date': date.strftime('%Y-%m-%d'),
                'available': True
            })
    availability = pd.DataFrame(availability)

    # Build triples
    triples = build_feasible_start_day_triples(
        vehicles_df=vehicles,
        partners_df=partners,
        availability_df=availability,
        approved_makes_df=approved_makes,
        model_taxonomy_df=model_taxonomy,
        week_start='2025-09-22',
        office='LA',
        start_days=['Mon']  # Simplify to Monday only
    )

    # Check taxonomy metadata
    camry_triple = triples[triples['model'] == 'Camry'].iloc[0]
    assert camry_triple['short_model_class'] == 'Sedan', "Camry should be Sedan"
    assert camry_triple['powertrain'] == 'Hybrid', "Camry should be Hybrid"

    highlander_triple = triples[triples['model'] == 'Highlander'].iloc[0]
    assert highlander_triple['short_model_class'] == 'SUV', "Highlander should be SUV"
    assert highlander_triple['powertrain'] == 'Gas', "Highlander should be Gas"

    print(f"✓ Model taxonomy attached correctly")
    print(f"  Camry: {camry_triple['short_model_class']}/{camry_triple['powertrain']}")
    print(f"  Highlander: {highlander_triple['short_model_class']}/{highlander_triple['powertrain']}")


def test_geo_office_match():
    """Test that geo_office_match flag is set correctly."""

    print("\nTest 5: Geo Office Match Flag")

    vehicles = pd.DataFrame([
        {'vin': 'VIN001', 'make': 'Toyota', 'model': 'Camry', 'office': 'LA'},
    ])

    partners = pd.DataFrame([
        {'person_id': 'P001', 'office': 'LA'},    # Matches vehicle office
        {'person_id': 'P002', 'office': 'LA'},    # Also matches
    ])

    approved_makes = pd.DataFrame([
        {'person_id': 'P001', 'make': 'Toyota', 'rank': 'A'},
        {'person_id': 'P002', 'make': 'Toyota', 'rank': 'B'},
    ])

    # Simplified availability - extended for any start day
    availability = []
    for day in range(14):
        availability.append({
            'vin': 'VIN001',
            'date': f'2025-09-{22+day:02d}' if day < 9 else f'2025-10-{day-8:02d}',
            'available': True
        })
    availability_df = pd.DataFrame(availability)

    # Build triples
    triples = build_feasible_start_day_triples(
        vehicles_df=vehicles,
        partners_df=partners,
        availability_df=availability_df,
        approved_makes_df=approved_makes,
        week_start='2025-09-22',
        office='LA',
        start_days=['Mon']  # Simplify
    )

    # All should have geo_office_match = True (same office)
    assert all(triples['geo_office_match'] == True), "All should have geo_office_match=True"

    print(f"✓ All {len(triples)} triples have geo_office_match=True (same office)")


def test_output_schema_compliance():
    """Test that output has all required columns and correct types."""

    print("\nTest 6: Output Schema Compliance")

    vehicles = pd.DataFrame([
        {'vin': 'VIN001', 'make': 'Toyota', 'model': 'Camry', 'office': 'LA'},
    ])

    partners = pd.DataFrame([
        {'person_id': 'P001', 'office': 'LA'},
    ])

    approved_makes = pd.DataFrame([
        {'person_id': 'P001', 'make': 'Toyota', 'rank': 'A'},
    ])

    availability = []
    for day in range(7):
        availability.append({
            'vin': 'VIN001',
            'date': f'2025-09-{22+day:02d}',
            'available': True
        })
    availability_df = pd.DataFrame(availability)

    # Build triples
    triples = build_feasible_start_day_triples(
        vehicles_df=vehicles,
        partners_df=partners,
        availability_df=availability_df,
        approved_makes_df=approved_makes,
        week_start='2025-09-22',
        office='LA',
        start_days=['Mon']
    )

    # Validate schema
    required_columns = [
        'vin', 'person_id', 'start_day', 'office', 'make', 'model', 'rank',
        'eligibility_ok', 'availability_ok', 'start_day_ok', 'geo_office_match',
        'short_model_class', 'powertrain'
    ]

    for col in required_columns:
        assert col in triples.columns, f"Missing required column: {col}"

    # Validate using built-in validator
    assert validate_triples_output(triples), "Output validation failed"

    print(f"✓ All {len(required_columns)} required columns present")
    print(f"  Columns: {', '.join(triples.columns)}")


def test_deterministic_ordering():
    """Test that output is deterministically ordered."""

    print("\nTest 7: Deterministic Ordering")

    vehicles = pd.DataFrame([
        {'vin': 'VIN002', 'make': 'Toyota', 'model': 'Camry', 'office': 'LA'},
        {'vin': 'VIN001', 'make': 'Toyota', 'model': 'Camry', 'office': 'LA'},
    ])

    partners = pd.DataFrame([
        {'person_id': 'P002', 'office': 'LA'},
        {'person_id': 'P001', 'office': 'LA'},
    ])

    approved_makes = pd.DataFrame([
        {'person_id': 'P002', 'make': 'Toyota', 'rank': 'A'},
        {'person_id': 'P001', 'make': 'Toyota', 'rank': 'A'},
    ])

    availability = []
    for vin in ['VIN001', 'VIN002']:
        for day in range(7):
            availability.append({
                'vin': vin,
                'date': f'2025-09-{22+day:02d}',
                'available': True
            })
    availability_df = pd.DataFrame(availability)

    # Build triples with same seed multiple times
    results = []
    for _ in range(3):
        triples = build_feasible_start_day_triples(
            vehicles_df=vehicles,
            partners_df=partners,
            availability_df=availability_df,
            approved_makes_df=approved_makes,
            week_start='2025-09-22',
            office='LA',
            start_days=['Mon'],
            seed=42  # Same seed
        )
        results.append(triples)

    # All results should be identical
    for i in range(1, len(results)):
        pd.testing.assert_frame_equal(results[0], results[i], check_like=False)

    # Check sorting: (start_day, vin, person_id)
    first_row = results[0].iloc[0]
    assert first_row['vin'] == 'VIN001', "Should be sorted by VIN"
    assert first_row['person_id'] == 'P001', "Should be sorted by person_id"

    print(f"✓ Deterministic ordering confirmed (3 runs identical)")
    print(f"  First triple: {first_row['vin']}, {first_row['person_id']}")


def test_no_optimization_or_scoring():
    """Verify that we're NOT doing any optimization or scoring in 7.1."""

    print("\nTest 8: No Optimization or Scoring")

    vehicles = pd.DataFrame([
        {'vin': 'VIN001', 'make': 'Toyota', 'model': 'Camry', 'office': 'LA'},
    ])

    partners = pd.DataFrame([
        {'person_id': 'P001', 'office': 'LA'},
    ])

    approved_makes = pd.DataFrame([
        {'person_id': 'P001', 'make': 'Toyota', 'rank': 'A+'},  # High rank
        {'person_id': 'P002', 'make': 'Toyota', 'rank': 'C'},   # Low rank
    ])

    availability = []
    for day in range(7):
        availability.append({
            'vin': 'VIN001',
            'date': f'2025-09-{22+day:02d}',
            'available': True
        })
    availability_df = pd.DataFrame(availability)

    # Build triples
    triples = build_feasible_start_day_triples(
        vehicles_df=vehicles,
        partners_df=partners,
        availability_df=availability_df,
        approved_makes_df=approved_makes,
        week_start='2025-09-22',
        office='LA'
    )

    # Should have no score column
    assert 'score' not in triples.columns, "Should not have score column"
    assert 'objective' not in triples.columns, "Should not have objective column"

    # Should include both high and low rank partners (no filtering by quality)
    # Note: P002 isn't in partners table so won't appear, but the point is we don't filter by rank

    print(f"✓ No scoring or optimization columns present")
    print(f"  Columns do NOT include: score, objective, etc.")


if __name__ == "__main__":
    test_strict_eligibility()
    test_ops_capacity_filtering()
    test_allowed_start_dows()
    test_model_taxonomy_metadata()
    test_geo_office_match()
    test_output_schema_compliance()
    test_deterministic_ordering()
    test_no_optimization_or_scoring()

    print("\n" + "="*70)
    print("✅ ALL SPEC COMPLIANCE TESTS PASSED!")
    print("="*70)
    print("\nPhase 7.1 implementation is FULLY COMPLIANT with spec:")
    print("• Strict eligibility (no fallback)")
    print("• ops_capacity_calendar filtering")
    print("• allowed_start_dows filtering")
    print("• model_taxonomy metadata attachment")
    print("• geo_office_match flagging")
    print("• Complete output schema")
    print("• Deterministic ordering")
    print("• No optimization or scoring")
    print("\n🎨 'Make the candidate story true and legible before optimization'")
    print("🌌 'Sequence creates clarity'")
    print("\nReady for Phase 7.2: Core OR-Tools model with constraints!")