"""
Full Integration Test for LA with Fairness - September 22, 2025

Complete pipeline test with soft tier caps AND fairness:
7.1 (Feasible) → 7.3 (Cooldown) → 7.2+7.4s+7.5 (OR-Tools with caps & fairness)

Tests with real LA data for the week of Sept 22-26, 2025.
"""

import asyncio
import pandas as pd
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.database import DatabaseService
from app.solver.ortools_feasible_v2 import build_feasible_start_day_triples
from app.solver.cooldown_filter import apply_cooldown_filter
from app.solver.ortools_solver_v2 import add_score_to_triples
from app.solver.ortools_solver_v5 import solve_with_caps_and_fairness
from app.etl.availability import build_availability_grid


def print_fairness_audit(fairness_summary: pd.DataFrame, fairness_metrics: dict):
    """Print detailed fairness audit report."""

    print("\n" + "="*60)
    print("FAIRNESS AUDIT REPORT")
    print("="*60)

    # Overall metrics
    print(f"\n📊 Distribution Metrics:")
    print(f"   Partners assigned: {fairness_metrics['partners_assigned']}")
    print(f"   Partners with 2+: {fairness_metrics['partners_with_multiple']}")
    print(f"   Max per partner: {fairness_metrics['max_concentration']}")
    print(f"   Avg per partner: {fairness_metrics['avg_assignments']:.2f}")
    print(f"   Gini coefficient: {fairness_metrics['gini_coefficient']:.3f} "
          f"(0=perfect equality, 1=perfect inequality)")
    print(f"   Total fairness penalty: ${fairness_metrics['total_penalty']:,}")

    # Top concentrated partners
    if not fairness_summary.empty:
        concentrated = fairness_summary[fairness_summary['n_assigned'] > 1]
        if not concentrated.empty:
            print(f"\n🎯 Partners with Multiple Assignments:")
            for _, row in concentrated.head(5).iterrows():
                print(f"   {row['person_id']}: {row['n_assigned']} assignments "
                      f"(penalty=${row['fairness_penalty']})")

        # Distribution histogram
        print(f"\n📊 Assignment Distribution:")
        dist_counts = fairness_summary['n_assigned'].value_counts().sort_index()
        for n_assigns, count in dist_counts.items():
            bar = '█' * min(20, count)
            print(f"   {n_assigns} assignment(s): {bar} {count} partners")


async def test_la_fairness_integration():
    """Full integration test for LA with fairness penalties."""

    print("="*80)
    print("FULL INTEGRATION TEST: LA WITH FAIRNESS")
    print("Pipeline: 7.1 → 7.3 → 7.2+7.4s+7.5")
    print("="*80)

    db = DatabaseService()
    await db.initialize()

    office = 'Los Angeles'
    week_start = '2025-09-22'

    # Test different fairness configurations
    configs = [
        {'lambda_fair': 0, 'label': 'No Fairness'},
        {'lambda_fair': 200, 'label': 'Standard Fairness'},
        {'lambda_fair': 400, 'label': 'Strong Fairness'},
        {'lambda_fair': 200, 'fair_step_up': 400, 'label': 'Mode B (Stepped)'}
    ]

    try:
        # Load all data once
        print("\n📥 Loading data...")

        # Load vehicles
        vehicles_response = db.client.table('vehicles').select('*').eq('office', office).execute()
        vehicles_df = pd.DataFrame(vehicles_response.data)

        # Load partners
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

        # Load capacity and taxonomy
        ops_cal_response = db.client.table('ops_capacity_calendar').select('*').execute()
        ops_calendar_df = pd.DataFrame(ops_cal_response.data)

        taxonomy_response = db.client.table('model_taxonomy').select('*').execute()
        taxonomy_df = pd.DataFrame(taxonomy_response.data)

        # Load loan history
        print("Loading loan history...")
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

        # Load rules
        try:
            rules_response = db.client.table('rules').select('*').execute()
            rules_df = pd.DataFrame(rules_response.data)
        except:
            rules_df = pd.DataFrame()

        print(f"✓ Loaded: {len(vehicles_df)} vehicles, {len(partners_df)} partners")

        # Run pipeline once to get triples
        print("\n🔄 Running pipeline...")

        # Phase 7.1: Feasible triples
        triples_71 = build_feasible_start_day_triples(
            vehicles_df=vehicles_df,
            partners_df=partners_df,
            availability_df=availability_df,
            approved_makes_df=approved_la,
            week_start=week_start,
            office=office,
            ops_capacity_df=ops_calendar_df,
            model_taxonomy_df=taxonomy_df,
            start_days=['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
            min_available_days=7,
            default_slots_per_day=15
        )

        # Phase 7.3: Cooldown filter
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

        print(f"✓ Pipeline: {len(triples_71)} → {len(triples_73)} → ready to solve")

        # Test each configuration
        results_comparison = []

        for config in configs:
            print(f"\n{'='*60}")
            print(f"Testing: {config['label']}")
            print('='*60)

            lambda_fair = config.get('lambda_fair', 200)
            fair_step_up = config.get('fair_step_up', 0)

            result = solve_with_caps_and_fairness(
                triples_df=triples_with_scores,
                ops_capacity_df=ops_calendar_df,
                approved_makes_df=approved_la,
                loan_history_df=loan_history_df,
                rules_df=rules_df,
                week_start=week_start,
                office=office,
                loan_length_days=7,
                solver_time_limit_s=10,
                lambda_cap=800,
                lambda_fair=lambda_fair,
                fair_target=1,
                fair_step_up=fair_step_up,
                rolling_window_months=12,
                seed=42,
                verbose=True
            )

            # Collect metrics
            fairness_metrics = result.get('fairness_metrics', {})
            fairness_summary = result.get('fairness_summary', pd.DataFrame())

            config_result = {
                'config': config['label'],
                'lambda_fair': lambda_fair,
                'fair_step_up': fair_step_up,
                'assignments': len(result['selected_assignments']),
                'total_score': result.get('total_score', 0),
                'cap_penalty': result.get('total_cap_penalty', 0),
                'fairness_penalty': result.get('total_fairness_penalty', 0),
                'net_objective': result.get('net_objective', 0),
                'partners_assigned': fairness_metrics.get('partners_assigned', 0),
                'partners_multi': fairness_metrics.get('partners_with_multiple', 0),
                'max_concentration': fairness_metrics.get('max_concentration', 0),
                'gini': fairness_metrics.get('gini_coefficient', 0)
            }
            results_comparison.append(config_result)

            # Print detailed audit for standard config
            if config['label'] == 'Standard Fairness':
                print_fairness_audit(fairness_summary, fairness_metrics)

        # Comparison table
        print("\n" + "="*80)
        print("CONFIGURATION COMPARISON")
        print("="*80)

        comparison_df = pd.DataFrame(results_comparison)
        print("\n")
        print(comparison_df.to_string(index=False))

        # Analysis
        print("\n📊 Key Insights:")

        # Gini improvement
        no_fair_gini = comparison_df[comparison_df['config'] == 'No Fairness']['gini'].iloc[0]
        std_fair_gini = comparison_df[comparison_df['config'] == 'Standard Fairness']['gini'].iloc[0]
        improvement = (no_fair_gini - std_fair_gini) / no_fair_gini * 100

        print(f"   Gini coefficient improved by {improvement:.1f}% with standard fairness")

        # Concentration reduction
        no_fair_multi = comparison_df[comparison_df['config'] == 'No Fairness']['partners_multi'].iloc[0]
        std_fair_multi = comparison_df[comparison_df['config'] == 'Standard Fairness']['partners_multi'].iloc[0]

        if no_fair_multi > std_fair_multi:
            print(f"   Reduced partners with 2+ from {no_fair_multi} to {std_fair_multi}")

        # Trade-off analysis
        no_fair_net = comparison_df[comparison_df['config'] == 'No Fairness']['net_objective'].iloc[0]
        std_fair_net = comparison_df[comparison_df['config'] == 'Standard Fairness']['net_objective'].iloc[0]
        cost = no_fair_net - std_fair_net

        print(f"   Cost of fairness: ${cost:,} in net objective")

        # Validation
        print("\n" + "="*60)
        print("✅ VALIDATION CHECKS")
        print("="*60)

        # Check all configs produced valid results
        all_valid = all(r['assignments'] > 0 for r in results_comparison)
        if all_valid:
            print("✓ All configurations produced valid assignments")

        # Check fairness monotonicity
        fair_penalties = [r['fairness_penalty'] for r in results_comparison[:3]]  # First 3 are increasing lambda
        if all(fair_penalties[i] <= fair_penalties[i+1] for i in range(len(fair_penalties)-1)):
            print("✓ Fairness penalties increase with lambda")

        # Check Mode B stronger
        mode_a = comparison_df[comparison_df['config'] == 'Standard Fairness']['fairness_penalty'].iloc[0]
        mode_b = comparison_df[comparison_df['config'] == 'Mode B (Stepped)']['fairness_penalty'].iloc[0]
        if mode_b >= mode_a:
            print("✓ Mode B produces equal or higher penalties")

        print("\n🎉 Fairness integration test complete!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await db.close()


if __name__ == "__main__":
    print("Running full integration test for LA with fairness...")
    asyncio.run(test_la_fairness_integration())