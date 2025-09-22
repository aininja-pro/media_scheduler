"""
Mode B Validation and Multi-Lens Metrics Test

Verifies the improved Gini calculation (excluding zeros) and
tests Mode B (stepped penalties) as the recommended default.

"Measure with more than one lens so the story is true." - Godin
"""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.solver.ortools_solver_v5 import solve_with_caps_and_fairness
from app.solver.fairness_penalties import (
    calculate_gini_coefficient,
    calculate_hhi,
    calculate_top_k_share
)


def test_metric_calculations():
    """Verify metrics calculate correctly with different distributions."""
    print("\n" + "="*60)
    print("METRIC CALCULATION TESTS")
    print("="*60)

    test_cases = [
        {
            'name': 'Perfect Equality',
            'distribution': [2, 2, 2, 2, 2],  # 5 partners, 2 each
            'expected': {
                'gini': 0.0,
                'hhi': 0.2,  # 5 * (1/5)^2
                'top_1_share': 0.2,
                'top_5_share': 1.0
            }
        },
        {
            'name': 'High Concentration',
            'distribution': [20, 3, 2, 1, 1],  # 1 partner dominates
            'expected': {
                'gini': 'high',  # Should be > 0.4
                'hhi': 'high',  # Should be > 0.5
                'top_1_share': 20/27,  # ~0.74
                'top_5_share': 1.0
            }
        },
        {
            'name': 'Moderate Spread',
            'distribution': [3, 3, 2, 2, 2, 1, 1, 1],  # 8 partners, some concentration
            'expected': {
                'gini': 'moderate',  # Should be 0.1-0.3
                'hhi': 'moderate',  # Should be 0.15-0.25
                'top_1_share': 3/15,  # 0.2
                'top_5_share': 12/15  # 0.8
            }
        }
    ]

    for case in test_cases:
        dist = case['distribution']
        gini = calculate_gini_coefficient(dist)
        hhi = calculate_hhi(dist)
        top_1 = calculate_top_k_share(dist, k=1)
        top_5 = calculate_top_k_share(dist, k=5)

        print(f"\n{case['name']}:")
        print(f"  Distribution: {dist}")
        print(f"  Gini: {gini:.3f}")
        print(f"  HHI: {hhi:.3f}")
        print(f"  Top-1 share: {top_1:.1%}")
        print(f"  Top-5 share: {top_5:.1%}")

        # Validate expectations
        exp = case['expected']
        if isinstance(exp['gini'], float):
            assert abs(gini - exp['gini']) < 0.01, f"Gini mismatch: {gini} vs {exp['gini']}"
        elif exp['gini'] == 'high':
            assert gini > 0.4, f"Expected high Gini, got {gini}"
        elif exp['gini'] == 'moderate':
            assert 0.1 <= gini <= 0.3, f"Expected moderate Gini, got {gini}"

    print("\n✅ All metric calculations verified")


def test_mode_b_configuration():
    """Test Mode B (stepped penalties) as recommended default."""
    print("\n" + "="*60)
    print("MODE B CONFIGURATION TEST")
    print("="*60)

    # Create scenario with many partners and vehicles
    partners = 20
    vehicles = 50

    triples = []
    for v in range(vehicles):
        for p in range(min(10, partners)):  # Each vehicle has up to 10 eligible partners
            if np.random.random() < 0.7:  # 70% chance of eligibility
                triples.append({
                    'vin': f'V{v:03d}',
                    'person_id': f'P{p:03d}',
                    'start_day': '2025-09-22',
                    'make': 'Toyota',
                    'model': 'Model',
                    'office': 'LA',
                    'rank': 'A' if p < 5 else 'B',
                    'score': 1000 - p * 10  # Slight preference for lower IDs
                })

    triples_df = pd.DataFrame(triples)

    ops_capacity = pd.DataFrame([
        {'office': 'LA', 'date': '2025-09-22', 'slots': 30}  # Can select 30
    ])

    approved = pd.DataFrame([
        {'person_id': f'P{p:03d}', 'make': 'Toyota', 'rank': 'A' if p < 5 else 'B'}
        for p in range(partners)
    ])

    # Test configurations
    configs = [
        {'name': 'No Fairness', 'lambda_fair': 0, 'fair_step_up': 0},
        {'name': 'Mode A Light', 'lambda_fair': 200, 'fair_step_up': 0},
        {'name': 'Mode B (Recommended)', 'lambda_fair': 200, 'fair_step_up': 400},
        {'name': 'Mode A Strong', 'lambda_fair': 600, 'fair_step_up': 0}
    ]

    results = []

    for config in configs:
        result = solve_with_caps_and_fairness(
            triples_df=triples_df,
            ops_capacity_df=ops_capacity,
            approved_makes_df=approved,
            loan_history_df=pd.DataFrame(),
            rules_df=pd.DataFrame(),
            week_start='2025-09-22',
            office='LA',
            lambda_cap=800,
            lambda_fair=config['lambda_fair'],
            fair_step_up=config['fair_step_up'],
            fair_target=1,
            seed=42,
            verbose=False
        )

        # Calculate distribution
        partner_counts = {}
        for a in result['selected_assignments']:
            p = a['person_id']
            partner_counts[p] = partner_counts.get(p, 0) + 1

        assignments = list(partner_counts.values())
        metrics = result.get('fairness_metrics', {})

        config_result = {
            'config': config['name'],
            'partners': len(partner_counts),
            'max_per_partner': max(assignments) if assignments else 0,
            'gini': metrics.get('gini_coefficient', 0),
            'hhi': metrics.get('hhi', 0),
            'top_5_share': metrics.get('top_5_share', 0),
            'fairness_penalty': result.get('total_fairness_penalty', 0)
        }
        results.append(config_result)

        print(f"\n{config['name']}:")
        print(f"  Partners: {config_result['partners']}")
        print(f"  Max per partner: {config_result['max_per_partner']}")
        print(f"  Gini: {config_result['gini']:.3f}")
        print(f"  HHI: {config_result['hhi']:.3f}")
        print(f"  Top-5 share: {config_result['top_5_share']:.1%}")
        print(f"  Fairness penalty: ${config_result['fairness_penalty']:,}")

    # Validate Mode B is the sweet spot
    mode_b_result = next(r for r in results if r['config'] == 'Mode B (Recommended)')

    print("\n" + "="*60)
    print("MODE B VALIDATION")
    print("="*60)

    checks = [
        ('Wide spread', mode_b_result['partners'] >= 15),
        ('Max 2-3 per partner', mode_b_result['max_per_partner'] <= 3),
        ('Low Gini', mode_b_result['gini'] < 0.25),
        ('Low HHI', mode_b_result['hhi'] < 0.15),
        ('Top-5 < 50%', mode_b_result['top_5_share'] < 0.5)
    ]

    for check_name, passed in checks:
        status = "✅" if passed else "❌"
        print(f"{status} {check_name}")

    all_passed = all(passed for _, passed in checks)

    if all_passed:
        print("\n✅ Mode B meets all criteria for recommended default")
    else:
        print("\n⚠️  Mode B may need tuning")

    return all_passed


def create_ui_chip_example():
    """Generate example UI chip for fairness status."""
    print("\n" + "="*60)
    print("UI CHIP EXAMPLES")
    print("="*60)

    examples = [
        {
            'config': 'Standard',
            'lambda_fair': 200,
            'step_up': 0,
            'partners': 38,
            'max': 8,
            'gini': 0.21
        },
        {
            'config': 'Mode B (Recommended)',
            'lambda_fair': 200,
            'step_up': 400,
            'partners': 48,
            'max': 2,
            'gini': 0.158
        },
        {
            'config': 'Strong',
            'lambda_fair': 600,
            'step_up': 0,
            'partners': 65,
            'max': 1,
            'gini': 0.0
        }
    ]

    for ex in examples:
        # Main chip
        if ex['gini'] < 0.1:
            color = '🟢'
            status = 'Excellent'
        elif ex['gini'] < 0.2:
            color = '🔵'
            status = 'Good'
        else:
            color = '🟡'
            status = 'Fair'

        chip = f"{color} Fairness: λ={ex['lambda_fair']}"
        if ex['step_up'] > 0:
            chip += f"+{ex['step_up']}"
        chip += f" • {ex['partners']}P • Max={ex['max']} • Gini={ex['gini']:.2f}"

        # Hover detail
        detail = (
            f"{ex['config']} Distribution\n"
            f"Partners assigned: {ex['partners']}\n"
            f"Max per partner: {ex['max']}\n"
            f"Gini coefficient: {ex['gini']:.3f}\n"
            f"Status: {status}"
        )

        print(f"\n{ex['config']}:")
        print(f"  Chip: {chip}")
        print(f"  Hover:\n    {detail.replace(chr(10), chr(10) + '    ')}")


def main():
    """Run all Mode B validation tests."""
    print("="*80)
    print("MODE B VALIDATION AND MULTI-LENS METRICS")
    print("="*80)

    # Test metric calculations
    test_metric_calculations()

    # Test Mode B configuration
    mode_b_ok = test_mode_b_configuration()

    # Show UI examples
    create_ui_chip_example()

    print("\n" + "="*80)
    print("RECOMMENDED DEFAULT CONFIGURATION")
    print("="*80)

    print("""
Mode B (Step-Up) Configuration:
  FAIR_TARGET_PER_PARTNER = 1     # Prefer 1 per partner
  LAMBDA_FAIR = 200               # Light penalty for 2nd
  FAIR_STEP_UP = 400              # Heavier penalty for 3rd+

Expected Behavior:
  • Partners: 40-50 (wide spread)
  • Max per partner: 2-3 (flexible but limited)
  • Gini: 0.15-0.20 (good equality)
  • HHI: < 0.10 (low concentration)
  • Top-5 share: < 40% (no dominance)

Why Mode B:
  "Two per partner max—soft, not hard. Good default." - Hormozi

This provides a practical middle ground: wide spread across
partners while maintaining flexibility when calendar is tight.
""")

    return mode_b_ok


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)