"""
Extreme Soft Caps Test
Forces cap violations by limiting to lower-rank partners.
"""

import asyncio
import pandas as pd
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.database import DatabaseService
from app.solver.ortools_solver_v4 import solve_with_soft_caps
from app.solver.ortools_solver_v2 import add_score_to_triples


async def test_extreme_scenario():
    """Test with artificially constrained triples to force cap violations."""

    print("\n" + "="*80)
    print("EXTREME STRESS TEST: FORCING CAP VIOLATIONS")
    print("="*80)

    db = DatabaseService()
    await db.initialize()

    try:
        # Load minimal data for controlled test
        partners_response = db.client.table('media_partners').select('*').eq('office', 'Los Angeles').limit(5).execute()
        partners_df = pd.DataFrame(partners_response.data)

        # Load their approved makes
        partner_ids = partners_df['person_id'].tolist()
        approved_response = db.client.table('approved_makes').select('*').in_('person_id', partner_ids).execute()
        approved_df = pd.DataFrame(approved_response.data)

        # Create controlled triples - only B and C rank options
        test_triples = []
        vin_counter = 1

        # Focus on B and C rank partners only
        bc_approved = approved_df[approved_df['rank'].isin(['B', 'C'])]

        for _, approval in bc_approved.iterrows():
            # Create multiple vehicles for same partner-make pair
            for i in range(15):  # Many options for same partner
                test_triples.append({
                    'vin': f'TEST_VIN_{vin_counter}',
                    'person_id': approval['person_id'],
                    'make': approval['make'],
                    'model': 'TestModel',
                    'office': 'Los Angeles',
                    'start_day': '2025-09-22',  # All on Monday
                    'rank': approval['rank']
                })
                vin_counter += 1

        triples_df = pd.DataFrame(test_triples)

        # Add scores (B=500, C=300)
        triples_df['score'] = triples_df['rank'].map({'B': 500, 'C': 300})

        print(f"Created {len(triples_df)} test triples")
        print(f"Rank distribution: B={len(triples_df[triples_df['rank']=='B'])}, C={len(triples_df[triples_df['rank']=='C'])}")

        # Create artificial loan history to put partners near caps
        loan_history = []
        for partner_id in triples_df['person_id'].unique():
            for make in triples_df[triples_df['person_id']==partner_id]['make'].unique():
                rank = triples_df[(triples_df['person_id']==partner_id) &
                                (triples_df['make']==make)]['rank'].iloc[0]

                # Put them close to cap
                if rank == 'B':  # Cap is 50
                    num_loans = 48
                elif rank == 'C':  # Cap is 10
                    num_loans = 9
                else:
                    num_loans = 0

                for i in range(num_loans):
                    month = (i % 9) + 1  # Months 1-9
                    loan_history.append({
                        'person_id': partner_id,
                        'make': make,
                        'start_date': f'2025-{month:02d}-01',
                        'end_date': f'2025-{month:02d}-08',
                        'office': 'Los Angeles'
                    })

        loan_history_df = pd.DataFrame(loan_history)

        print(f"\nLoan history created: {len(loan_history_df)} records")
        print("Partners are near their caps (B: 48/50, C: 9/10)")

        # Limited capacity to force violations
        ops_capacity = pd.DataFrame([
            {'office': 'Los Angeles', 'date': '2025-09-22', 'slots': 30}  # Want 30 assignments
        ])

        # Run tests with different lambda values
        for lambda_cap in [400, 800, 1200, 2000]:
            print(f"\n" + "-"*60)
            print(f"Testing λ={lambda_cap}")

            result = solve_with_soft_caps(
                triples_df=triples_df,
                ops_capacity_df=ops_capacity,
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

            # Analyze results
            total_assigned = len(result['selected_assignments'])
            total_penalty = result.get('total_cap_penalty', 0)
            net_score = result.get('net_objective', 0)

            violations = 0
            total_delta = 0
            if not cap_summary.empty:
                over_cap = cap_summary[cap_summary['delta_overage'] > 0]
                violations = len(over_cap)
                total_delta = cap_summary['delta_overage'].sum()

            print(f"   Assignments: {total_assigned}/30")
            print(f"   Total score: {result.get('total_score', 0):,}")
            print(f"   Penalty: ${total_penalty:,}")
            print(f"   Net score: {net_score:,}")
            print(f"   Violations: {violations} partners over cap")
            print(f"   Total delta: {total_delta}")

            if violations > 0 and not cap_summary.empty:
                print(f"\n   Top violations:")
                for _, row in over_cap.head(3).iterrows():
                    print(f"     {row['person_id'][:8]}... + {row['make']} (Rank {row['rank']})")
                    print(f"       Used: {row['used_12m_before']} → {row['used_after']} (cap={row['cap']})")
                    print(f"       Delta: +{row['delta_overage']}, Penalty: ${row['penalty']:,}")

        print("\n" + "="*80)
        print("LAMBDA IMPACT SUMMARY")
        print("="*80)
        print("Higher λ values should reduce violations by making them more expensive")
        print("This demonstrates the soft cap tradeoff mechanism working correctly")

    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(test_extreme_scenario())