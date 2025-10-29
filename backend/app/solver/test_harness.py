"""
Test harness for OR-Tools solver with seedable runs and time limits.

This module provides utilities for reproducible testing and benchmarking
of the scheduling optimization algorithms.
"""

import time
import random
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import hashlib
import json


class TestHarness:
    """Test harness for reproducible solver runs."""

    def __init__(self, seed: Optional[int] = None, time_limit: float = 10.0):
        """
        Initialize test harness.

        Args:
            seed: Random seed for reproducibility (None = use system time)
            time_limit: Maximum solver runtime in seconds (default: 10.0)
        """
        self.seed = seed if seed is not None else int(time.time())
        self.time_limit = time_limit
        self.metrics = {}
        self.run_history = []

    def set_seed(self):
        """Set random seeds for all random number generators."""
        random.seed(self.seed)
        np.random.seed(self.seed)
        # OR-Tools seed will be set when creating solver

    def start_timer(self) -> float:
        """Start timing a solver run."""
        return time.time()

    def check_timeout(self, start_time: float) -> bool:
        """Check if time limit has been exceeded."""
        return (time.time() - start_time) > self.time_limit

    def log_run(self, solver_name: str, result: Dict[str, Any], runtime: float):
        """Log a solver run for comparison."""
        run_data = {
            'timestamp': datetime.now().isoformat(),
            'solver': solver_name,
            'seed': self.seed,
            'runtime': runtime,
            'assignments': len(result.get('assignments', [])),
            'total_score': result.get('total_score', 0),
            'result_hash': self._hash_result(result)
        }
        self.run_history.append(run_data)
        return run_data

    def _hash_result(self, result: Dict[str, Any]) -> str:
        """Create deterministic hash of solver result."""
        # Sort assignments for consistent hashing
        assignments = result.get('assignments', [])
        if assignments:
            sorted_assignments = sorted(
                assignments,
                key=lambda x: (x.get('vin', ''), x.get('person_id', ''))
            )
            hash_str = json.dumps(sorted_assignments, sort_keys=True)
        else:
            hash_str = "empty"
        return hashlib.md5(hash_str.encode()).hexdigest()

    def compare_solutions(
        self,
        greedy_result: Dict[str, Any],
        ortools_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare greedy and OR-Tools solutions."""
        comparison = {
            'greedy_assignments': len(greedy_result.get('assignments', [])),
            'ortools_assignments': len(ortools_result.get('assignments', [])),
            'greedy_score': greedy_result.get('total_score', 0),
            'ortools_score': ortools_result.get('total_score', 0),
            'score_improvement': 0,
            'same_solution': False
        }

        # Calculate improvement
        if comparison['greedy_score'] > 0:
            improvement = (comparison['ortools_score'] - comparison['greedy_score']) / comparison['greedy_score'] * 100
            comparison['score_improvement'] = round(improvement, 2)

        # Check if solutions are identical
        comparison['same_solution'] = (
            self._hash_result(greedy_result) == self._hash_result(ortools_result)
        )

        return comparison

    def validate_constraints(
        self,
        assignments: list,
        constraints: Dict[str, Any]
    ) -> Tuple[bool, list]:
        """
        Validate that assignments satisfy all constraints.

        Returns:
            (is_valid, violations_list)
        """
        violations = []

        # Check one VIN per week
        vins = [a.get('vin') for a in assignments]
        if len(vins) != len(set(vins)):
            violations.append("Duplicate VIN assignments")

        # Check one partner per week
        partners = [a.get('person_id') for a in assignments]
        if len(partners) != len(set(partners)):
            violations.append("Partner assigned multiple vehicles")

        # Check daily capacity
        daily_cap = constraints.get('daily_capacity', 15)
        if len(assignments) > daily_cap:
            violations.append(f"Exceeds daily capacity ({len(assignments)} > {daily_cap})")

        # Check cooldown violations
        for assignment in assignments:
            if not assignment.get('cooldown_ok', True):
                violations.append(f"Cooldown violation: {assignment.get('person_id')} - {assignment.get('make')}")

        # Check tier cap violations
        partner_make_counts = {}
        for assignment in assignments:
            key = (assignment.get('person_id'), assignment.get('make'))
            partner_make_counts[key] = partner_make_counts.get(key, 0) + 1

        for (person_id, make), count in partner_make_counts.items():
            cap = constraints.get('tier_caps', {}).get(make, {}).get(person_id)
            if cap and count > cap:
                violations.append(f"Tier cap violation: {person_id} has {count} {make} (cap: {cap})")

        return len(violations) == 0, violations

    def generate_metrics(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive metrics for a solution."""
        assignments = result.get('assignments', [])

        metrics = {
            'total_assignments': len(assignments),
            'total_score': result.get('total_score', 0),
            'avg_score': 0,
            'make_diversity': 0,
            'partner_diversity': 0,
            'office_utilization': {}
        }

        if assignments:
            # Average score
            scores = [a.get('score', 0) for a in assignments]
            metrics['avg_score'] = sum(scores) / len(scores) if scores else 0

            # Make diversity (unique makes / total)
            makes = [a.get('make') for a in assignments]
            metrics['make_diversity'] = len(set(makes)) / len(makes) if makes else 0

            # Partner diversity
            partners = [a.get('person_id') for a in assignments]
            metrics['partner_diversity'] = len(set(partners)) / len(partners) if partners else 0

            # Office utilization
            for assignment in assignments:
                office = assignment.get('office', 'Unknown')
                metrics['office_utilization'][office] = metrics['office_utilization'].get(office, 0) + 1

        return metrics

    def export_comparison(self, filename: str = 'solver_comparison.json'):
        """Export run history and comparisons to JSON file."""
        export_data = {
            'seed': self.seed,
            'time_limit': self.time_limit,
            'run_history': self.run_history,
            'metrics': self.metrics
        }

        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)

        print(f"Comparison data exported to {filename}")


class SolverBenchmark:
    """Benchmark utilities for solver performance testing."""

    def __init__(self, test_cases: list):
        """
        Initialize benchmark suite.

        Args:
            test_cases: List of test case configurations
        """
        self.test_cases = test_cases
        self.results = []

    def run_benchmark(self, greedy_solver, ortools_solver, harness: TestHarness):
        """Run benchmark suite on both solvers."""
        for i, test_case in enumerate(self.test_cases):
            print(f"Running test case {i+1}/{len(self.test_cases)}: {test_case.get('name', 'Unnamed')}")

            # Set seed for reproducibility
            harness.set_seed()

            # Run greedy solver
            start = harness.start_timer()
            greedy_result = greedy_solver(test_case)
            greedy_time = time.time() - start

            # Run OR-Tools solver
            start = harness.start_timer()
            ortools_result = ortools_solver(test_case, seed=harness.seed, time_limit=harness.time_limit)
            ortools_time = time.time() - start

            # Compare results
            comparison = harness.compare_solutions(greedy_result, ortools_result)
            comparison['greedy_time'] = greedy_time
            comparison['ortools_time'] = ortools_time
            comparison['test_case'] = test_case.get('name', f'Test {i+1}')

            self.results.append(comparison)

            # Log runs
            harness.log_run('greedy', greedy_result, greedy_time)
            harness.log_run('ortools', ortools_result, ortools_time)

        return self.results

    def print_summary(self):
        """Print benchmark summary."""
        if not self.results:
            print("No benchmark results available")
            return

        print("\n=== BENCHMARK SUMMARY ===\n")
        print(f"Total test cases: {len(self.results)}")

        # Average improvements
        improvements = [r['score_improvement'] for r in self.results]
        avg_improvement = sum(improvements) / len(improvements) if improvements else 0
        print(f"Average score improvement: {avg_improvement:.2f}%")

        # Time comparisons
        greedy_times = [r['greedy_time'] for r in self.results]
        ortools_times = [r['ortools_time'] for r in self.results]
        print(f"Average greedy time: {sum(greedy_times)/len(greedy_times):.3f}s")
        print(f"Average OR-Tools time: {sum(ortools_times)/len(ortools_times):.3f}s")

        # Detailed results
        print("\nDetailed Results:")
        print("-" * 70)
        for result in self.results:
            print(f"Test: {result['test_case']}")
            print(f"  Greedy:   {result['greedy_assignments']} assignments, "
                  f"score: {result['greedy_score']}, time: {result['greedy_time']:.3f}s")
            print(f"  OR-Tools: {result['ortools_assignments']} assignments, "
                  f"score: {result['ortools_score']}, time: {result['ortools_time']:.3f}s")
            print(f"  Improvement: {result['score_improvement']:.2f}%")
            if result['same_solution']:
                print(f"  Same solution: Yes")
            print()


def create_test_data(
    num_vehicles: int = 100,
    num_partners: int = 50,
    num_makes: int = 10
) -> Dict[str, pd.DataFrame]:
    """Create synthetic test data for solver testing."""

    # Create vehicles
    vehicles = []
    for i in range(num_vehicles):
        vehicles.append({
            'vin': f'VIN_{i:04d}',
            'make': f'Make_{i % num_makes}',
            'model': f'Model_{(i // 2) % 5}',
            'office': 'Test Office'
        })

    # Create partners
    partners = []
    for i in range(num_partners):
        partners.append({
            'person_id': f'P_{i:04d}',
            'name': f'Partner {i}',
            'office': 'Test Office',
            'rank': random.choice(['A+', 'A', 'B', 'C'])
        })

    # Create availability (all vehicles available)
    availability = []
    for vehicle in vehicles:
        for day in range(7):
            availability.append({
                'vin': vehicle['vin'],
                'date': f'2024-09-{22+day:02d}',
                'available': True,
                'make': vehicle['make'],
                'model': vehicle['model']
            })

    return {
        'vehicles': pd.DataFrame(vehicles),
        'partners': pd.DataFrame(partners),
        'availability': pd.DataFrame(availability)
    }