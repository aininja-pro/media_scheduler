"""
Soft Caps Pinch Test
Deliberately creates a constrained scenario to force cap violations and validate penalty behavior.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.solver.ortools_solver_v4 import solve_with_soft_caps


def test_pinch_scenario():
    """
    Create a pinch case:
    - Only 3 makes available (Honda, Toyota, Mazda)
    - Partners mostly at B and C ranks (tight caps)
    - High demand (20 slots/day = 100 total)
    - Partners already near caps
    """

    print("\n" + "="*80)
    print("PINCH SCENARIO: FORCING CAP VIOLATIONS")
    print("="*80)

    # Create limited partner-make pairs (all B and C rank)
    approved_makes = []
    for i in range(10):  # 10 partners
        partner_id = f'PARTNER_{i:03d}'
        for make in ['Honda', 'Toyota', 'Mazda']:
            # Mix of B and C ranks
            rank = 'C' if i < 5 else 'B'
            approved_makes.append({
                'person_id': partner_id,
                'make': make,
                'rank': rank
            })

    approved_df = pd.DataFrame(approved_makes)

    print(f"Setup:")
    print(f"  Partners: 10 (5 C-rank, 5 B-rank)")
    print(f"  Makes: Honda, Toyota, Mazda")
    print(f"  Caps: C=10 loans/year, B=50 loans/year")

    # Create feasible triples (many vehicles available)
    triples = []
    vin_counter = 1

    for day in range(5):  # Mon-Fri
        date = f'2025-09-{22+day:02d}'
        for partner_id in approved_df['person_id'].unique():
            for make in ['Honda', 'Toyota', 'Mazda']:
                # Multiple vehicles per partner-make-day
                for v in range(5):
                    rank = approved_df[
                        (approved_df['person_id'] == partner_id) &
                        (approved_df['make'] == make)
                    ]['rank'].iloc[0]

                    triples.append({
                        'vin': f'VIN_{vin_counter:04d}',
                        'person_id': partner_id,
                        'make': make,
                        'model': 'Model',
                        'office': 'Los Angeles',
                        'start_day': date,
                        'rank': rank,
                        'score': 500 if rank == 'B' else 300  # B better than C
                    })
                    vin_counter += 1

    triples_df = pd.DataFrame(triples)
    print(f"  Triples: {len(triples_df)} options")

    # Create loan history - partners already near caps
    loan_history = []

    for partner_id in approved_df['person_id'].unique():
        is_c_rank = int(partner_id.split('_')[1]) < 5

        for make in ['Honda', 'Toyota', 'Mazda']:
            # C-rank partners: 8/10 cap used
            # B-rank partners: 45/50 cap used
            loans_used = 8 if is_c_rank else 45

            for i in range(loans_used):
                month = (i % 9) + 1
                loan_history.append({
                    'person_id': partner_id,
                    'make': make,
                    'start_date': f'2025-{month:02d}-01',
                    'end_date': f'2025-{month:02d}-08',
                    'office': 'Los Angeles'
                })

    loan_history_df = pd.DataFrame(loan_history)

    print(f"\nPre-existing usage:")
    print(f"  C-rank partners: 8/10 used per make (2 remaining)")
    print(f"  B-rank partners: 45/50 used per make (5 remaining)")

    # High capacity to force violations
    ops_capacity = []
    for day in range(5):
        ops_capacity.append({
            'office': 'Los Angeles',
            'date': f'2025-09-{22+day:02d}',
            'slots': 20  # 20 per day = 100 total
        })
    ops_capacity_df = pd.DataFrame(ops_capacity)

    print(f"\nDemand: 20 slots/day × 5 days = 100 total assignments needed")
    print(f"Available without violation: ~{5*2*3 + 5*5*3} (not enough!)")

    # Test with different lambda values
    lambda_values = [200, 400, 800, 1200, 2000]
    results = []

    print("\n" + "-"*80)
    print("LAMBDA SWEEP RESULTS")
    print("-"*80)

    for lambda_cap in lambda_values:
        result = solve_with_soft_caps(
            triples_df=triples_df,
            ops_capacity_df=ops_capacity_df,
            approved_makes_df=approved_df,
            loan_history_df=loan_history_df,
            rules_df=pd.DataFrame(),  # Use default caps
            week_start='2025-09-22',
            office='Los Angeles',
            loan_length_days=7,
            solver_time_limit_s=10,
            lambda_cap=lambda_cap,
            rolling_window_months=12,
            seed=42
        )

        cap_summary = result.get('cap_summary', pd.DataFrame())

        # Collect metrics
        metrics = {
            'lambda': lambda_cap,
            'assignments': len(result['selected_assignments']),
            'total_score': result.get('total_score', 0),
            'total_penalty': result.get('total_cap_penalty', 0),
            'net_score': result.get('net_objective', 0),
            'pairs_over_cap': 0,
            'total_delta': 0,
            'max_delta': 0
        }

        if not cap_summary.empty:
            over_cap = cap_summary[cap_summary['delta_overage'] > 0]
            metrics['pairs_over_cap'] = len(over_cap)
            metrics['total_delta'] = int(cap_summary['delta_overage'].sum())
            if not over_cap.empty:
                metrics['max_delta'] = int(over_cap['delta_overage'].max())

        results.append(metrics)

        # Print summary
        print(f"\nλ={lambda_cap:4d}: {metrics['assignments']} assigned, "
              f"penalty=${metrics['total_penalty']:,}, "
              f"violations={metrics['pairs_over_cap']}, "
              f"delta={metrics['total_delta']}")

        # Show top violations if any
        if metrics['pairs_over_cap'] > 0 and not cap_summary.empty:
            print(f"  Top violations:")
            for _, row in over_cap.head(3).iterrows():
                print(f"    {row['person_id']} + {row['make']} (Rank {row['rank']}): "
                      f"+{row['delta_overage']} over cap, ${row['penalty']} penalty")

    # Analysis
    print("\n" + "="*80)
    print("ANALYSIS: LAMBDA SENSITIVITY")
    print("="*80)

    df_results = pd.DataFrame(results)

    # Create visualization-friendly table
    print("\n📊 Lambda Impact on Violations:")
    print(df_results[['lambda', 'assignments', 'pairs_over_cap', 'total_delta', 'total_penalty', 'net_score']].to_string(index=False))

    # Check monotonicity
    violations = df_results['pairs_over_cap'].tolist()
    is_monotonic = all(violations[i] >= violations[i+1] for i in range(len(violations)-1))

    print(f"\n✅ Monotonicity check: {'PASS' if is_monotonic else 'FAIL'}")
    print(f"   Violations: {' → '.join(map(str, violations))}")

    # Find knee point (best net score)
    best_idx = df_results['net_score'].idxmax()
    best_lambda = df_results.loc[best_idx, 'lambda']
    best_net = df_results.loc[best_idx, 'net_score']

    print(f"\n🎯 Optimal λ (max net score): {best_lambda} (score={best_net:,})")

    # Calculate penalty as % of score
    df_results['penalty_pct'] = (df_results['total_penalty'] / df_results['total_score'] * 100).round(1)

    print("\n📈 Penalty as % of Total Score:")
    for _, row in df_results.iterrows():
        bar = '█' * int(row['penalty_pct'] / 2)  # Visual bar
        print(f"  λ={int(row['lambda']):4d}: {bar} {row['penalty_pct']:.1f}%")

    return df_results


def create_ui_components(result: dict, lambda_cap: int = 800) -> dict:
    """
    Generate UI components for cap status display.

    Returns dict with formatted strings for UI chips.
    """

    cap_summary = result.get('cap_summary', pd.DataFrame())
    total_penalty = result.get('total_cap_penalty', 0)

    ui_components = {
        'main_chip': '',
        'detail_chip': '',
        'stage_summary': '',
        'warning_badge': None
    }

    # Calculate violations
    pairs_over_cap = 0
    total_delta = 0
    if not cap_summary.empty:
        over_cap = cap_summary[cap_summary['delta_overage'] > 0]
        pairs_over_cap = len(over_cap)
        total_delta = int(cap_summary['delta_overage'].sum())

    # Main status chip
    if pairs_over_cap == 0:
        ui_components['main_chip'] = f"✓ Caps OK (λ={lambda_cap})"
        chip_color = 'green'
    else:
        ui_components['main_chip'] = f"⚠ Over-cap: {pairs_over_cap} (Penalty: ${total_penalty:,})"
        chip_color = 'orange' if total_penalty < 5000 else 'red'

    # Detailed chip for hover/expand
    ui_components['detail_chip'] = (
        f"Tier Caps | λ={lambda_cap} | "
        f"Violations: {pairs_over_cap} | "
        f"Delta: {total_delta} | "
        f"Penalty: ${total_penalty:,}"
    )

    # Stage summary for pipeline view
    removed_by_zero = result.get('removed_by_zero_caps', 0)
    ui_components['stage_summary'] = (
        f"✓ Soft Tier Caps Active\n"
        f"• Removed by zero-cap rules: {removed_by_zero:,}\n"
        f"• Cap penalties: ${total_penalty:,}\n"
        f"• Partners over cap: {pairs_over_cap}"
    )

    # Warning badge if significant violations
    if total_penalty > 5000:
        ui_components['warning_badge'] = {
            'type': 'warning',
            'text': f'High cap penalties: ${total_penalty:,}',
            'color': chip_color,
            'action': 'Review cap violations in audit report'
        }

    return ui_components


if __name__ == "__main__":
    print("Running pinch scenario to force cap violations...")
    results_df = test_pinch_scenario()

    # Demo UI components
    print("\n" + "="*80)
    print("UI COMPONENT EXAMPLES")
    print("="*80)

    # Simulate a result with violations
    mock_result = {
        'cap_summary': pd.DataFrame([
            {'person_id': 'P001', 'delta_overage': 2, 'penalty': 1600},
            {'person_id': 'P002', 'delta_overage': 1, 'penalty': 800},
            {'person_id': 'P003', 'delta_overage': 0, 'penalty': 0}
        ]),
        'total_cap_penalty': 2400,
        'removed_by_zero_caps': 150
    }

    ui = create_ui_components(mock_result, lambda_cap=800)

    print("\n🎯 Main Status Chip:")
    print(f"   {ui['main_chip']}")

    print("\n📊 Hover Details:")
    print(f"   {ui['detail_chip']}")

    print("\n📋 Stage Summary:")
    for line in ui['stage_summary'].split('\n'):
        print(f"   {line}")

    if ui['warning_badge']:
        print("\n⚠️  Warning Badge:")
        print(f"   {ui['warning_badge']['text']}")
        print(f"   Action: {ui['warning_badge']['action']}")