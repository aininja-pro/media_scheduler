"""
Soft Caps Stress Test
Forces cap tradeoffs by reducing capacity to exercise penalty system.
"""

import asyncio
import pandas as pd
from datetime import datetime, timedelta
import sys
import os
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.database import DatabaseService
from app.solver.ortools_feasible_v2 import build_feasible_start_day_triples
from app.solver.cooldown_filter import apply_cooldown_filter
from app.solver.ortools_solver_v2 import add_score_to_triples
from app.solver.ortools_solver_v4 import solve_with_soft_caps
from app.etl.availability import build_availability_grid


async def run_stress_test(daily_slots: int = 8, lambda_cap: int = 800):
    """
    Run stress test with reduced capacity to force cap violations.

    Args:
        daily_slots: Reduced daily capacity (default 8 vs normal 15)
        lambda_cap: Penalty weight
    """

    db = DatabaseService()
    await db.initialize()

    office = 'Los Angeles'
    week_start = '2025-09-22'

    try:
        # Load all data (same as before)
        vehicles_response = db.client.table('vehicles').select('*').eq('office', office).execute()
        vehicles_df = pd.DataFrame(vehicles_response.data)

        partners_response = db.client.table('media_partners').select('*').eq('office', office).execute()
        partners_df = pd.DataFrame(partners_response.data)

        # Load approved makes with pagination
        all_approved = []
        limit = 1000
        offset = 0
        while True:
            approved_response = db.client.table('approved_makes').select('*').range(offset, offset + limit - 1).execute()
            if not approved_response.data:
                break
            all_approved.extend(approved_response.data)
            offset += limit
            if len(approved_response.data) < limit:
                break

        approved_df = pd.DataFrame(all_approved)
        la_partner_ids = set(partners_df['person_id'].tolist())
        approved_la = approved_df[approved_df['person_id'].isin(la_partner_ids)]

        # Build availability
        activity_response = db.client.table('current_activity').select('*').execute()
        activity_df = pd.DataFrame(activity_response.data)
        if 'vehicle_vin' in activity_df.columns:
            activity_df = activity_df.rename(columns={'vehicle_vin': 'vin'})

        availability_df = build_availability_grid(
            vehicles_df=vehicles_df,
            activity_df=activity_df,
            week_start=week_start,
            office=office,
            availability_horizon_days=14
        )
        availability_df = availability_df.rename(columns={'day': 'date'})

        # Load loan history
        all_loan_history = []
        limit = 1000
        offset = 0
        while True:
            history_response = db.client.table('loan_history').select('*').range(offset, offset + limit - 1).execute()
            if not history_response.data:
                break
            all_loan_history.extend(history_response.data)
            offset += limit
            if len(history_response.data) < limit:
                break

        loan_history_df = pd.DataFrame(all_loan_history)
        if not loan_history_df.empty and 'office' in loan_history_df.columns:
            loan_history_df = loan_history_df[loan_history_df['office'] == 'Los Angeles'].copy()

        # Load rules and taxonomy
        try:
            rules_response = db.client.table('rules').select('*').execute()
            rules_df = pd.DataFrame(rules_response.data)
        except:
            rules_df = pd.DataFrame()

        taxonomy_response = db.client.table('model_taxonomy').select('*').execute()
        taxonomy_df = pd.DataFrame(taxonomy_response.data)

        # ============================================
        # CREATE STRESSED CAPACITY (reduced slots)
        # ============================================
        ops_cal_response = db.client.table('ops_capacity_calendar').select('*').execute()
        ops_calendar_df = pd.DataFrame(ops_cal_response.data)

        # Override capacity to stress the system
        stressed_capacity = []
        week_start_date = pd.to_datetime(week_start)
        for day_offset in range(5):  # Mon-Fri
            date = week_start_date + timedelta(days=day_offset)
            stressed_capacity.append({
                'office': office,
                'date': date.strftime('%Y-%m-%d'),
                'slots': daily_slots  # Reduced from 15 to force tradeoffs
            })

        stressed_capacity_df = pd.DataFrame(stressed_capacity)

        print(f"\n🔥 STRESS TEST: {daily_slots} slots/day (vs normal 15)")
        print(f"   Total capacity: {daily_slots * 5} (vs normal 75)")
        print(f"   Lambda: {lambda_cap}")

        # Run pipeline with stressed capacity
        triples_71 = build_feasible_start_day_triples(
            vehicles_df=vehicles_df,
            partners_df=partners_df,
            availability_df=availability_df,
            approved_makes_df=approved_la,
            week_start=week_start,
            office=office,
            ops_capacity_df=stressed_capacity_df,  # Use stressed capacity
            model_taxonomy_df=taxonomy_df,
            start_days=['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
            min_available_days=7,
            default_slots_per_day=daily_slots  # Reduced default
        )

        # Apply cooldown
        triples_73 = apply_cooldown_filter(
            feasible_triples_df=triples_71,
            loan_history_df=loan_history_df,
            rules_df=rules_df,
            model_taxonomy_df=taxonomy_df,
            default_cooldown_days=30
        )

        # Add scores
        triples_with_scores = add_score_to_triples(
            triples_df=triples_73,
            partners_df=partners_df,
            publication_df=pd.DataFrame(),
            seed=42
        )

        # Remove zero-cap triples
        if not rules_df.empty:
            zero_cap_rules = rules_df[rules_df['loan_cap_per_year'] == 0]
            if not zero_cap_rules.empty:
                before_count = len(triples_with_scores)
                for _, rule in zero_cap_rules.iterrows():
                    make = rule['make']
                    rank = rule['rank']
                    mask = triples_with_scores['make'] == make
                    if pd.notna(rank):
                        matching_pairs = approved_la[
                            (approved_la['make'] == make) &
                            (approved_la['rank'] == rank)
                        ]['person_id'].unique()
                        mask &= triples_with_scores['person_id'].isin(matching_pairs)
                    triples_with_scores = triples_with_scores[~mask]

        # Solve with soft caps
        result = solve_with_soft_caps(
            triples_df=triples_with_scores,
            ops_capacity_df=stressed_capacity_df,  # Stressed capacity
            approved_makes_df=approved_la,
            loan_history_df=loan_history_df,
            rules_df=rules_df,
            week_start=week_start,
            office=office,
            loan_length_days=7,
            solver_time_limit_s=10,
            lambda_cap=lambda_cap,
            rolling_window_months=12,
            seed=42
        )

        # Extract metrics
        cap_summary = result.get('cap_summary', pd.DataFrame())

        metrics = {
            'daily_slots': daily_slots,
            'lambda': lambda_cap,
            'assignments': len(result['selected_assignments']),
            'total_score': result.get('total_score', 0),
            'total_penalty': result.get('total_cap_penalty', 0),
            'net_score': result.get('net_objective', 0),
            'pairs_over_cap': 0,
            'max_delta': 0,
            'total_delta': 0
        }

        if not cap_summary.empty:
            over_cap = cap_summary[cap_summary['delta_overage'] > 0]
            metrics['pairs_over_cap'] = len(over_cap)
            metrics['total_delta'] = int(cap_summary['delta_overage'].sum())
            if not over_cap.empty:
                metrics['max_delta'] = int(over_cap['delta_overage'].max())

        # Print detailed results
        print(f"\n📊 RESULTS (λ={lambda_cap}, slots={daily_slots}):")
        print(f"   Assignments: {metrics['assignments']}/{daily_slots * 5}")
        print(f"   Total score: {metrics['total_score']:,}")
        print(f"   Total penalty: ${metrics['total_penalty']:,}")
        print(f"   Net score: {metrics['net_score']:,}")
        print(f"   Pairs over cap: {metrics['pairs_over_cap']}")

        if metrics['pairs_over_cap'] > 0:
            print(f"\n⚠️  CAP VIOLATIONS:")
            for _, row in cap_summary[cap_summary['delta_overage'] > 0].head(5).iterrows():
                print(f"   {row['person_id']} + {row['make']} (Rank {row['rank']})")
                print(f"     Cap: {row['cap']}, Used: {row['used_12m_before']} → {row['used_after']}")
                print(f"     Delta: +{row['delta_overage']}, Penalty: ${row['penalty']:,}")

        return metrics

    finally:
        await db.close()


async def run_lambda_sweep():
    """Run lambda sweep on stressed scenario to find optimal value."""

    print("\n" + "="*80)
    print("LAMBDA SWEEP ON STRESSED SCENARIO")
    print("="*80)

    # Test different combinations
    test_configs = [
        # Normal capacity - should have no penalties
        (15, 400), (15, 800), (15, 1200),

        # Moderate stress - 10 slots/day (50 total vs 75 normal)
        (10, 400), (10, 800), (10, 1200), (10, 2000),

        # High stress - 8 slots/day (40 total vs 75 normal)
        (8, 400), (8, 800), (8, 1200), (8, 2000),

        # Extreme stress - 5 slots/day (25 total vs 75 normal)
        (5, 400), (5, 800), (5, 1200), (5, 2000)
    ]

    results = []

    for daily_slots, lambda_val in test_configs:
        print(f"\n🔄 Testing: {daily_slots} slots/day, λ={lambda_val}...")
        metrics = await run_stress_test(daily_slots, lambda_val)
        results.append(metrics)

    # Create results DataFrame
    df = pd.DataFrame(results)

    # Analysis by capacity level
    print("\n" + "="*80)
    print("LAMBDA SWEEP RESULTS")
    print("="*80)

    for slots in df['daily_slots'].unique():
        subset = df[df['daily_slots'] == slots]
        print(f"\n📊 Capacity: {slots} slots/day ({slots*5} total)")
        print(subset[['lambda', 'assignments', 'net_score', 'total_penalty', 'pairs_over_cap']].to_string(index=False))

        # Check monotonicity
        over_caps = subset['pairs_over_cap'].tolist()
        if len(over_caps) > 1:
            if all(over_caps[i] >= over_caps[i+1] for i in range(len(over_caps)-1)):
                print("   ✅ Monotonic: Higher λ → fewer/equal violations")
            else:
                print("   ⚠️  Non-monotonic behavior detected")

        # Find the "knee" - best net score
        best_idx = subset['net_score'].idxmax()
        best_row = subset.loc[best_idx]
        print(f"   🎯 Best net score: λ={best_row['lambda']}, score={best_row['net_score']:,}")

    # Save results to JSON for analysis
    results_json = {
        'timestamp': datetime.now().isoformat(),
        'test_configs': test_configs,
        'results': results,
        'summary': {
            'normal_capacity': df[df['daily_slots'] == 15]['total_penalty'].sum(),
            'moderate_stress': df[df['daily_slots'] == 10]['total_penalty'].sum(),
            'high_stress': df[df['daily_slots'] == 8]['total_penalty'].sum(),
            'extreme_stress': df[df['daily_slots'] == 5]['total_penalty'].sum()
        }
    }

    with open('soft_caps_stress_results.json', 'w') as f:
        json.dump(results_json, f, indent=2)

    print(f"\n💾 Results saved to soft_caps_stress_results.json")

    # Policy recommendations
    print("\n" + "="*80)
    print("POLICY RECOMMENDATIONS")
    print("="*80)

    print("\n📋 Default Settings:")
    print("   • allow_override_zero_caps = False (enforce hard blocks)")
    print("   • LAMBDA_CAP = 800 (balanced penalty weight)")
    print("   • max_total_delta_overage = None (no hard budget)")

    print("\n🎛️  Tuning Guide:")
    print("   • λ=400: Permissive (allows more violations)")
    print("   • λ=800: Balanced (default recommendation)")
    print("   • λ=1200: Restrictive (strongly discourages violations)")
    print("   • λ=2000: Very restrictive (almost no violations)")

    # Find overall best lambda across stress levels
    avg_by_lambda = df.groupby('lambda').agg({
        'net_score': 'mean',
        'total_penalty': 'mean',
        'pairs_over_cap': 'mean'
    }).round(0)

    print("\n📊 Average Performance by Lambda:")
    print(avg_by_lambda.to_string())

    return df


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Soft Caps Stress Test')
    parser.add_argument('--slots', type=int, default=8,
                       help='Daily slot capacity (normal=15, stress=8)')
    parser.add_argument('--lambda-cap', type=int, default=800,
                       help='Penalty weight')
    parser.add_argument('--sweep', action='store_true',
                       help='Run full lambda sweep')

    args = parser.parse_args()

    if args.sweep:
        asyncio.run(run_lambda_sweep())
    else:
        asyncio.run(run_stress_test(args.slots, args.lambda_cap))