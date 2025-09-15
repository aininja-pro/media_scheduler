"""
Performance tests for candidate generation.

Tests that the build_weekly_candidates function performs well with large datasets.
"""

import pandas as pd
import time
from datetime import datetime, timedelta

from app.solver.candidates import build_weekly_candidates


def test_performance_with_large_dataset():
    """Test performance with a dataset similar to production scale (859 VINs)."""

    # Create large test dataset
    num_vins = 859
    num_partners = 50
    week_start = "2024-01-08"

    print(f"\nTesting performance with {num_vins} VINs and {num_partners} partners...")

    # Generate availability data for full week
    availability_data = []
    makes = ['Toyota', 'Honda', 'Ford', 'Chevrolet', 'Nissan', 'BMW', 'Mercedes', 'Audi']
    markets = ['SEA', 'LAX', 'SFO', 'PDX', 'PHX', 'DEN', 'LAS']

    week_dates = [(datetime(2024, 1, 8) + timedelta(days=i)).strftime("%Y-%m-%d")
                  for i in range(7)]

    for vin_num in range(num_vins):
        vin = f"VIN{vin_num:06d}"
        make = makes[vin_num % len(makes)]
        market = markets[vin_num % len(markets)]

        for date in week_dates:
            # Most VINs are available most days (realistic scenario)
            available = (vin_num + int(date.split('-')[2])) % 10 < 8  # ~80% availability

            availability_data.append({
                'vin': vin,
                'date': date,
                'market': market,
                'make': make,
                'model': f'Model{vin_num % 5}',
                'available': available
            })

    availability_df = pd.DataFrame(availability_data)

    # Generate cooldown data
    cooldown_data = []
    for partner_num in range(num_partners):
        person_id = f"P{partner_num:03d}"
        for make in makes:
            cooldown_data.append({
                'person_id': person_id,
                'make': make,
                'model': f'Model{partner_num % 5}',
                'cooldown_ok': (partner_num + hash(make)) % 5 < 4  # ~80% not in cooldown
            })

    cooldown_df = pd.DataFrame(cooldown_data)

    # Generate publication data
    publication_data = []
    for partner_num in range(num_partners):
        person_id = f"P{partner_num:03d}"
        for make in makes:
            publication_data.append({
                'person_id': person_id,
                'make': make,
                'loans_total_24m': 10 + (partner_num % 20),
                'loans_observed_24m': 8 + (partner_num % 15),
                'publications_observed_24m': 3 + (partner_num % 10),
                'publication_rate_observed': 0.3 + (partner_num % 7) * 0.1,
                'coverage': 0.5 + (partner_num % 5) * 0.1,
                'supported': partner_num % 3 == 0
            })

    publication_df = pd.DataFrame(publication_data)

    # Time the candidate generation
    start_time = time.time()

    result = build_weekly_candidates(
        availability_df,
        cooldown_df,
        publication_df,
        week_start,
        min_available_days=5  # Relaxed for testing
    )

    end_time = time.time()
    execution_time = end_time - start_time

    print(f"Generated {len(result):,} candidate pairs in {execution_time:.3f} seconds")
    print(f"Input: {len(availability_df):,} availability records, {len(cooldown_df):,} cooldown records")
    print(f"Performance: {len(result)/execution_time:.0f} candidates/second")

    # Validate results
    assert len(result) > 0, "Should generate some candidates"
    assert execution_time < 5.0, f"Should complete within 5 seconds, took {execution_time:.3f}s"

    # Validate data integrity
    assert all(result['available_days'] >= 5), "All candidates should meet min_available_days"
    assert all(result['cooldown_ok'] == True), "All candidates should pass cooldown check"

    # Check columns are correct
    expected_columns = [
        "vin", "person_id", "market", "make", "model", "week_start",
        "available_days", "cooldown_ok", "publication_rate_observed", "supported", "coverage"
    ]
    assert list(result.columns) == expected_columns

    print(f"✓ Performance test passed! Generated {len(result):,} valid candidates.")
    return execution_time, len(result)


def test_memory_usage():
    """Test memory usage with large dataset."""
    import psutil
    import os

    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB

    execution_time, num_candidates = test_performance_with_large_dataset()

    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_increase = final_memory - initial_memory

    print(f"Memory usage: {initial_memory:.1f}MB → {final_memory:.1f}MB (+{memory_increase:.1f}MB)")

    # Should not use excessive memory (reasonable threshold)
    assert memory_increase < 100, f"Memory increase too high: {memory_increase:.1f}MB"

    print("✓ Memory usage test passed!")


if __name__ == "__main__":
    test_performance_with_large_dataset()
    test_memory_usage()