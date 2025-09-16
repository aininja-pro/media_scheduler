"""
Diagnose why only partners 12439 and 1402 are getting all assignments.
"""

import asyncio
import pandas as pd
from app.services.database import db_service


async def diagnose_partner_dominance():
    """Find out why partners 12439 and 1402 dominate all assignments."""

    await db_service.initialize()

    print(f"\n{'='*80}")
    print(f"DIAGNOSING WHY ONLY 2 PARTNERS GET ASSIGNMENTS")
    print(f"{'='*80}\n")

    # Check partner 12439
    print("PARTNER 12439:")
    partner_12439 = db_service.client.table('media_partners').select('*').eq('person_id', 12439).execute()
    if partner_12439.data:
        p = partner_12439.data[0]
        print(f"  Name: {p.get('name', 'Unknown')}")
        print(f"  Office: {p.get('office', 'Unknown')}")
        print(f"  Status: {p.get('status', 'Unknown')}")

    # Check their approved makes
    approved_12439 = db_service.client.table('approved_makes').select('*').eq('person_id', 12439).execute()
    if approved_12439.data:
        print(f"  Approved for {len(approved_12439.data)} makes:")
        for make_data in approved_12439.data[:5]:
            print(f"    - {make_data['make']}: Rank {make_data['rank']}")

    # Check partner 1402
    print("\nPARTNER 1402:")
    partner_1402 = db_service.client.table('media_partners').select('*').eq('person_id', 1402).execute()
    if partner_1402.data:
        p = partner_1402.data[0]
        print(f"  Name: {p.get('name', 'Unknown')}")
        print(f"  Office: {p.get('office', 'Unknown')}")
        print(f"  Status: {p.get('status', 'Unknown')}")

    # Check their approved makes
    approved_1402 = db_service.client.table('approved_makes').select('*').eq('person_id', 1402).execute()
    if approved_1402.data:
        print(f"  Approved for {len(approved_1402.data)} makes:")
        for make_data in approved_1402.data[:5]:
            print(f"    - {make_data['make']}: Rank {make_data['rank']}")

    # Check how many LA partners have A+ rank for key makes
    print(f"\n{'='*80}")
    print(f"RANK DISTRIBUTION FOR LA PARTNERS")
    print(f"{'='*80}\n")

    # Get LA partners
    la_partners = db_service.client.table('media_partners').select('person_id').eq('office', 'Los Angeles').execute()
    la_partner_ids = [p['person_id'] for p in la_partners.data] if la_partners.data else []

    # Get all approved makes
    all_approved = []
    limit = 1000
    offset = 0
    while True:
        approved_response = db_service.client.table('approved_makes').select('*').range(offset, offset + limit - 1).execute()
        if not approved_response.data:
            break
        all_approved.extend(approved_response.data)
        offset += limit
        if len(approved_response.data) < limit:
            break

    approved_df = pd.DataFrame(all_approved)
    la_approved = approved_df[approved_df['person_id'].isin(la_partner_ids)]

    # Check rank distribution for key makes
    key_makes = ['Volkswagen', 'Hyundai', 'Mazda']
    for make in key_makes:
        make_data = la_approved[la_approved['make'] == make]
        if not make_data.empty:
            rank_dist = make_data['rank'].value_counts()
            print(f"{make}:")
            print(f"  Total partners: {len(make_data)}")
            for rank in ['A+', 'A', 'B', 'C']:
                count = rank_dist.get(rank, 0)
                print(f"    {rank} rank: {count} partners")
                if rank == 'A+' and count > 0:
                    a_plus_partners = make_data[make_data['rank'] == 'A+']['person_id'].tolist()
                    print(f"      A+ partners: {a_plus_partners[:5]}...")

    # Check recent loan history for these partners
    print(f"\n{'='*80}")
    print(f"RECENT ACTIVITY CHECK")
    print(f"{'='*80}\n")

    loan_history = db_service.client.table('loan_history').select('*').execute()
    if loan_history.data:
        loan_df = pd.DataFrame(loan_history.data)

        # Recent loans for partner 12439
        partner_12439_loans = loan_df[loan_df['person_id'] == 12439]
        print(f"Partner 12439 loan history: {len(partner_12439_loans)} total loans")
        if not partner_12439_loans.empty:
            recent_12439 = partner_12439_loans.nlargest(3, 'end_date')
            for _, loan in recent_12439.iterrows():
                print(f"  - {loan['make']} ended {loan['end_date']}")

        # Recent loans for partner 1402
        partner_1402_loans = loan_df[loan_df['person_id'] == 1402]
        print(f"\nPartner 1402 loan history: {len(partner_1402_loans)} total loans")
        if not partner_1402_loans.empty:
            recent_1402 = partner_1402_loans.nlargest(3, 'end_date')
            for _, loan in recent_1402.iterrows():
                print(f"  - {loan['make']} ended {loan['end_date']}")

    # Check scoring formula
    print(f"\n{'='*80}")
    print(f"SCORING ANALYSIS")
    print(f"{'='*80}\n")

    print("Score calculation formula:")
    print("  Base scores by rank:")
    print("    A+: 80 points")
    print("    A:  50 points")
    print("    B:  20 points")
    print("    C:  15 points")
    print("  + Geo bonus: 30 points (if office matches)")
    print("  + History bonus: 0 points (based on publication rate)")
    print()
    print("Partners 12439 and 1402 likely have:")
    print("  - A+ rank (80 points)")
    print("  - Office match (30 points)")
    print("  - Total: 110 points (maximum possible)")

    await db_service.close()
    print(f"\n✅ Diagnosis complete")


if __name__ == "__main__":
    asyncio.run(diagnose_partner_dominance())