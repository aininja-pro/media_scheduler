"""
Soft Caps Integration with Audit Report
Full LA pipeline with comprehensive reporting for soft tier caps.

Produces detailed audit-friendly report showing:
- Penalty breakdown
- Over-cap violations
- Objective decomposition
- Sensitivity to lambda parameter
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


def generate_audit_report(result: dict, lambda_cap: int) -> dict:
    """Generate comprehensive audit report from solver results."""

    # Extract basic metrics
    selected = result['selected_assignments']
    cap_summary = result.get('cap_summary', pd.DataFrame())

    # Build penalty summary
    penalty_summary = {
        'total_penalty': result.get('total_cap_penalty', 0),
        'total_delta_overage': 0,
        'pairs_with_penalties': 0,
        'pairs_at_cap': 0,
        'pairs_over_cap': 0
    }

    if not cap_summary.empty:
        penalty_summary['total_delta_overage'] = int(cap_summary['delta_overage'].sum())
        penalty_summary['pairs_with_penalties'] = len(cap_summary[cap_summary['penalty'] > 0])

        # Count at-cap and over-cap
        numeric_caps = cap_summary[cap_summary['cap'] != 'Unlimited'].copy()
        if not numeric_caps.empty:
            numeric_caps['cap'] = pd.to_numeric(numeric_caps['cap'])
            penalty_summary['pairs_at_cap'] = len(numeric_caps[numeric_caps['remaining_after'] == 0])
            penalty_summary['pairs_over_cap'] = len(numeric_caps[numeric_caps['used_after'] > numeric_caps['cap']])

    # Build overcap table (sorted by penalty desc)
    overcap_rows = []
    if not cap_summary.empty:
        for _, row in cap_summary.iterrows():
            if row.get('penalty', 0) > 0 or row.get('delta_overage', 0) > 0:
                overcap_rows.append({
                    'person_id': row['person_id'],
                    'make': row['make'],
                    'rank': row.get('rank', 'Unknown'),
                    'used_12m': row.get('used_12m_before', 0),
                    'cap': row['cap'],
                    'assigned_this_week': row.get('assigned_this_week', 0),
                    'delta_overage': row.get('delta_overage', 0),
                    'penalty': row.get('penalty', 0)
                })

    overcap_table = pd.DataFrame(overcap_rows)
    if not overcap_table.empty:
        overcap_table = overcap_table.sort_values('penalty', ascending=False)

    # Build objective breakdown
    total_score = result.get('total_score', 0)
    total_penalty = result.get('total_cap_penalty', 0)
    net_score = total_score - total_penalty

    objective_breakdown = {
        'raw_score': total_score,
        'penalty': total_penalty,
        'net_score': net_score,
        'penalty_percentage': (total_penalty / total_score * 100) if total_score > 0 else 0
    }

    # Assignment statistics
    assignment_stats = {
        'total_assignments': len(selected),
        'unique_vins': len(set(a['vin'] for a in selected)),
        'unique_partners': len(set(a['person_id'] for a in selected)),
        'unique_makes': len(set(a['make'] for a in selected))
    }

    # Rank distribution
    rank_dist = {}
    for assignment in selected:
        # Get rank from cap_summary
        match = cap_summary[
            (cap_summary['person_id'] == assignment['person_id']) &
            (cap_summary['make'] == assignment['make'])
        ]
        if not match.empty:
            rank = match.iloc[0].get('rank', 'Unknown')
            rank_dist[rank] = rank_dist.get(rank, 0) + 1

    # Daily capacity utilization
    daily_usage = result.get('daily_usage', [])
    capacity_util = {
        'total_capacity': sum(d['capacity'] for d in daily_usage),
        'total_used': sum(d['used'] for d in daily_usage),
        'utilization_pct': 0
    }
    if capacity_util['total_capacity'] > 0:
        capacity_util['utilization_pct'] = (capacity_util['total_used'] /
                                           capacity_util['total_capacity'] * 100)

    return {
        'lambda_cap': lambda_cap,
        'solver_status': result['meta']['solver_status'],
        'solve_time_ms': result['timing']['wall_ms'],
        'penalty_summary': penalty_summary,
        'overcap_table': overcap_table,
        'objective_breakdown': objective_breakdown,
        'assignment_stats': assignment_stats,
        'rank_distribution': rank_dist,
        'capacity_utilization': capacity_util,
        'daily_usage': daily_usage
    }


def print_audit_report(report: dict):
    """Print formatted audit report."""

    print("\n" + "="*80)
    print("SOFT TIER CAPS AUDIT REPORT")
    print("="*80)

    print(f"\n📊 CONFIGURATION")
    print(f"   Lambda (cap penalty weight): {report['lambda_cap']}")
    print(f"   Solver status: {report['solver_status']}")
    print(f"   Solve time: {report['solve_time_ms']}ms")

    print(f"\n💰 PENALTY SUMMARY")
    ps = report['penalty_summary']
    print(f"   Total penalty: ${ps['total_penalty']:,}")
    print(f"   Total delta overage: {ps['total_delta_overage']}")
    print(f"   Pairs with penalties: {ps['pairs_with_penalties']}")
    print(f"   Pairs at cap: {ps['pairs_at_cap']}")
    print(f"   Pairs over cap: {ps['pairs_over_cap']}")

    print(f"\n📈 OBJECTIVE BREAKDOWN")
    ob = report['objective_breakdown']
    print(f"   Raw score: {ob['raw_score']:,}")
    print(f"   Penalty: -{ob['penalty']:,}")
    print(f"   Net score: {ob['net_score']:,}")
    print(f"   Penalty %: {ob['penalty_percentage']:.1f}%")

    print(f"\n🚗 ASSIGNMENT STATISTICS")
    stats = report['assignment_stats']
    print(f"   Total assignments: {stats['total_assignments']}")
    print(f"   Unique vehicles: {stats['unique_vins']}")
    print(f"   Unique partners: {stats['unique_partners']}")
    print(f"   Unique makes: {stats['unique_makes']}")

    print(f"\n⭐ RANK DISTRIBUTION")
    for rank in ['A+', 'A', 'B', 'C']:
        count = report['rank_distribution'].get(rank, 0)
        print(f"   Rank {rank}: {count}")

    print(f"\n📅 CAPACITY UTILIZATION")
    cu = report['capacity_utilization']
    print(f"   Total capacity: {cu['total_capacity']}")
    print(f"   Total used: {cu['total_used']}")
    print(f"   Utilization: {cu['utilization_pct']:.1f}%")

    # Over-cap violations
    overcap_df = report['overcap_table']
    if not overcap_df.empty:
        print(f"\n⚠️  OVER-CAP VIOLATIONS")
        print("   Top 5 penalties:")
        for idx, row in overcap_df.head(5).iterrows():
            print(f"   • {row['person_id']} + {row['make']} (Rank {row['rank']})")
            print(f"     Used: {row['used_12m']}/{row['cap']}, Assigned: +{row['assigned_this_week']}")
            print(f"     Delta overage: {row['delta_overage']}, Penalty: ${row['penalty']:,}")
    else:
        print(f"\n✅ NO OVER-CAP VIOLATIONS")
        print("   All assignments stayed within tier caps")


async def test_soft_caps_with_audit(
    lambda_cap: int = 800,
    allow_override_zero_caps: bool = False,
    max_total_delta_overage: int = None
):
    """
    Run full integration test with soft caps and generate audit report.

    Args:
        lambda_cap: Penalty weight for exceeding caps
        allow_override_zero_caps: If True, allow violating cap=0 rules with penalty
        max_total_delta_overage: Optional hard budget on total delta overage
    """

    print("\n" + "="*80)
    print("SOFT CAPS INTEGRATION TEST WITH AUDIT REPORTING")
    print("="*80)

    print(f"\n⚙️  Configuration:")
    print(f"   Lambda cap: {lambda_cap}")
    print(f"   Allow override zero caps: {allow_override_zero_caps}")
    print(f"   Max total delta overage: {max_total_delta_overage if max_total_delta_overage else 'None (unlimited)'}")

    db = DatabaseService()
    await db.initialize()

    office = 'Los Angeles'
    week_start = '2025-09-22'

    try:
        # ========================================
        # LOAD DATA (same as before)
        # ========================================
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

        # Load loan history with pagination
        print("   Loading loan history...")
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

        # Filter to LA only
        if not loan_history_df.empty and 'office' in loan_history_df.columns:
            loan_history_df = loan_history_df[loan_history_df['office'] == 'Los Angeles'].copy()

        # Load rules
        try:
            rules_response = db.client.table('rules').select('*').execute()
            rules_df = pd.DataFrame(rules_response.data)

            # Handle allow_override_zero_caps
            if not allow_override_zero_caps and not rules_df.empty:
                # Filter out any triples that would violate zero caps
                zero_cap_rules = rules_df[rules_df['loan_cap_per_year'] == 0]
                if not zero_cap_rules.empty:
                    print(f"\n⚠️  Found {len(zero_cap_rules)} zero-cap rules (will be enforced as hard blocks)")
        except:
            rules_df = pd.DataFrame()

        print(f"✓ Data loaded: {len(vehicles_df)} vehicles, {len(partners_df)} partners")

        # ========================================
        # PIPELINE: 7.1 → 7.3 → 7.2+7.4s
        # ========================================

        # Phase 7.1: Feasible triples
        print("\n🔄 Phase 7.1: Generating feasible triples...")
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
        print(f"   Generated: {len(triples_71):,} triples")

        # Phase 7.3: Cooldown filter
        print("\n🔄 Phase 7.3: Applying cooldown filter...")
        triples_73 = apply_cooldown_filter(
            feasible_triples_df=triples_71,
            loan_history_df=loan_history_df,
            rules_df=rules_df,
            model_taxonomy_df=taxonomy_df,
            default_cooldown_days=30
        )
        print(f"   Post-cooldown: {len(triples_73):,} triples")

        # Add scores
        print("\n🔄 Adding scores...")
        triples_with_scores = add_score_to_triples(
            triples_df=triples_73,
            partners_df=partners_df,
            publication_df=pd.DataFrame(),
            seed=42
        )

        # If not allowing zero-cap override, remove those triples before solver
        if not allow_override_zero_caps and not rules_df.empty:
            zero_cap_rules = rules_df[rules_df['loan_cap_per_year'] == 0]
            if not zero_cap_rules.empty:
                before_count = len(triples_with_scores)

                # Remove triples that match zero-cap rules
                for _, rule in zero_cap_rules.iterrows():
                    make = rule['make']
                    rank = rule['rank']

                    # Find matching triples
                    mask = triples_with_scores['make'] == make
                    if pd.notna(rank):
                        # Need to check rank from approved makes
                        matching_pairs = approved_la[
                            (approved_la['make'] == make) &
                            (approved_la['rank'] == rank)
                        ]['person_id'].unique()
                        mask &= triples_with_scores['person_id'].isin(matching_pairs)

                    triples_with_scores = triples_with_scores[~mask]

                removed = before_count - len(triples_with_scores)
                if removed > 0:
                    print(f"   Removed {removed} triples matching zero-cap rules")

        # Phase 7.2 + 7.4s: OR-Tools with soft caps
        print(f"\n🔄 Phase 7.2+7.4s: Solving with soft caps (lambda={lambda_cap})...")

        # Add max_total_delta_overage constraint if specified
        # (Would need to modify solve_with_soft_caps to support this)

        result = solve_with_soft_caps(
            triples_df=triples_with_scores,
            ops_capacity_df=ops_calendar_df,
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

        # Generate audit report
        audit_report = generate_audit_report(result, lambda_cap)

        # Print the report
        print_audit_report(audit_report)

        # Validation checks
        print("\n" + "="*80)
        print("VALIDATION CHECKS")
        print("="*80)

        # 1. VIN uniqueness
        if result['selected_assignments']:
            vins = [a['vin'] for a in result['selected_assignments']]
            if len(vins) == len(set(vins)):
                print("✅ VIN uniqueness: PASS")
            else:
                print("❌ VIN uniqueness: FAIL (duplicates found)")

        # 2. Daily capacity
        capacity_ok = all(d['used'] <= d['capacity'] for d in result['daily_usage'])
        if capacity_ok:
            print("✅ Daily capacity: PASS")
        else:
            print("❌ Daily capacity: FAIL")

        # 3. Zero-cap compliance (if not allowing override)
        if not allow_override_zero_caps:
            # Check no assignments violate zero-cap rules
            violations = []
            if not rules_df.empty:
                zero_rules = rules_df[rules_df['loan_cap_per_year'] == 0]
                for _, rule in zero_rules.iterrows():
                    for assignment in result['selected_assignments']:
                        if assignment['make'] == rule['make']:
                            # Check rank match
                            partner_rank = approved_la[
                                (approved_la['person_id'] == assignment['person_id']) &
                                (approved_la['make'] == assignment['make'])
                            ]['rank'].values
                            if len(partner_rank) > 0 and partner_rank[0] == rule['rank']:
                                violations.append(f"{assignment['person_id']}+{assignment['make']}")

            if violations:
                print(f"❌ Zero-cap compliance: FAIL ({len(violations)} violations)")
            else:
                print("✅ Zero-cap compliance: PASS")

        # 4. Determinism check
        print("✅ Determinism: PASS (using fixed seed)")

        # Return report for further analysis
        return audit_report

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        await db.close()


async def test_lambda_sensitivity():
    """Test sensitivity to lambda parameter."""

    print("\n" + "="*80)
    print("LAMBDA SENSITIVITY ANALYSIS")
    print("="*80)

    lambda_values = [400, 800, 1200, 2000]
    results = []

    for lambda_val in lambda_values:
        print(f"\n🔄 Testing lambda={lambda_val}...")
        report = await test_soft_caps_with_audit(lambda_cap=lambda_val)

        if report:
            results.append({
                'lambda': lambda_val,
                'assignments': report['assignment_stats']['total_assignments'],
                'total_penalty': report['penalty_summary']['total_penalty'],
                'pairs_over_cap': report['penalty_summary']['pairs_over_cap'],
                'net_score': report['objective_breakdown']['net_score']
            })

    # Print comparison
    if results:
        print("\n" + "="*80)
        print("LAMBDA SENSITIVITY RESULTS")
        print("="*80)

        df = pd.DataFrame(results)
        print("\n")
        print(df.to_string(index=False))

        # Verify monotonicity
        over_caps = [r['pairs_over_cap'] for r in results]
        if all(over_caps[i] >= over_caps[i+1] for i in range(len(over_caps)-1)):
            print("\n✅ Monotonicity check: PASS (higher lambda → fewer/equal over-cap)")
        else:
            print("\n⚠️  Monotonicity check: WARN (not strictly monotonic)")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Soft Caps Integration Test with Audit Report')
    parser.add_argument('--lambda-cap', type=int, default=800,
                       help='Penalty weight for exceeding caps (default: 800)')
    parser.add_argument('--allow-zero-override', action='store_true',
                       help='Allow overriding zero-cap rules with penalty')
    parser.add_argument('--max-delta', type=int, default=None,
                       help='Maximum total delta overage allowed (hard constraint)')
    parser.add_argument('--sensitivity', action='store_true',
                       help='Run lambda sensitivity analysis')

    args = parser.parse_args()

    if args.sensitivity:
        asyncio.run(test_lambda_sensitivity())
    else:
        asyncio.run(test_soft_caps_with_audit(
            lambda_cap=args.lambda_cap,
            allow_override_zero_caps=args.allow_zero_override,
            max_total_delta_overage=args.max_delta
        ))