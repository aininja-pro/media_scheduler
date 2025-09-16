"""
Test actual assignments being made by the solver.
"""

import asyncio
import requests
import json


async def test_actual_assignments():
    """Call the solver API for different weeks and compare results."""

    print(f"\n{'='*80}")
    print("TESTING ACTUAL SOLVER ASSIGNMENTS")
    print(f"{'='*80}\n")

    # Test weeks
    test_cases = [
        ('Los Angeles', '2024-09-16'),
        ('Los Angeles', '2024-09-23'),
        ('Los Angeles', '2024-09-30'),
        ('Los Angeles', '2024-10-07'),
    ]

    base_url = 'http://localhost:8081/api/solver/generate_schedule'

    for office, week_start in test_cases:
        print(f"\n{'-'*60}")
        print(f"Testing: {office}, Week of {week_start}")
        print(f"{'-'*60}")

        params = {
            'office': office,
            'week_start': week_start,
            'min_available_days': 5,
            'enable_tier_caps': 'true',
            'enable_cooldown': 'true',
            'enable_capacity': 'true',
            'enable_geo_constraints': 'true',
            'enable_vehicle_lifecycle': 'true'
        }

        try:
            response = requests.get(base_url, params=params)

            if response.status_code == 200:
                data = response.json()

                # Extract key metrics
                stage1 = data.get('pipeline', {}).get('stage1', {})
                stage3 = data.get('pipeline', {}).get('stage3', {})
                assignments = data.get('assignments', [])

                print(f"\nStage 1 Results:")
                print(f"  - Candidate count: {stage1.get('candidate_count', 0):,}")
                print(f"  - Unique VINs: {stage1.get('unique_vins', 0)}")
                print(f"  - Unique partners: {stage1.get('unique_partners', 0)}")

                print(f"\nFinal Assignments: {len(assignments)}")

                if assignments:
                    # Show first few assignments
                    print(f"\nFirst 5 assignments:")
                    for i, assignment in enumerate(assignments[:5], 1):
                        print(f"  {i}. VIN: {assignment['vin'][-8:]}, Partner: {assignment['person_id']}, Make: {assignment['make']}, Score: {assignment['score']}")

                    # Check for duplicates across weeks
                    assignment_keys = [(a['vin'], a['person_id']) for a in assignments]
                    print(f"\nUnique assignments: {len(set(assignment_keys))}")

                    # Check VIN diversity
                    unique_vins = set(a['vin'] for a in assignments)
                    unique_partners = set(a['person_id'] for a in assignments)
                    print(f"Unique VINs in assignments: {len(unique_vins)}")
                    print(f"Unique partners in assignments: {len(unique_partners)}")

                # Check constraint analysis
                constraint_analysis = data.get('constraint_analysis', {})
                if constraint_analysis:
                    print(f"\nConstraint rejections:")
                    for constraint, count in constraint_analysis.items():
                        print(f"  - {constraint}: {count:,}")

            else:
                print(f"Error: {response.status_code}")
                print(response.json())

        except Exception as e:
            print(f"Error calling API: {e}")

    print(f"\n✅ Test complete")


if __name__ == "__main__":
    asyncio.run(test_actual_assignments())