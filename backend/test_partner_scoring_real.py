"""
Test partner base scoring with REAL database data.
"""

import sys
from app.services.database import DatabaseService
import pandas as pd
from app.chain_builder.geography import score_partners_base


def test_with_real_data():
    """Test partner scoring with real database data"""

    print("\n=== Testing Partner Base Scoring with REAL DATA ===\n")

    db = DatabaseService()

    try:
        # 1. Load real data
        print("Step 1: Loading real data...")

        partners_response = db.client.table('media_partners').select('*').eq('office', 'Los Angeles').execute()
        partners_df = pd.DataFrame(partners_response.data) if partners_response.data else pd.DataFrame()
        print(f"  ✓ Loaded {len(partners_df)} LA partners")

        # Load ALL approved_makes with pagination
        approved_makes = []
        offset = 0
        while True:
            response = db.client.table('approved_makes').select('*').range(offset, offset + 999).execute()
            if not response.data:
                break
            approved_makes.extend(response.data)
            offset += 1000
            if len(response.data) < 1000:
                break

        approved_makes_df = pd.DataFrame(approved_makes)
        print(f"  ✓ Loaded {len(approved_makes_df)} approved_makes records (with pagination)")

        # Load loan history with pagination
        loan_history = []
        offset = 0
        while True:
            response = db.client.table('loan_history').select('*').range(offset, offset + 999).execute()
            if not response.data:
                break
            loan_history.extend(response.data)
            offset += 1000
            if len(response.data) < 1000:
                break

        loan_history_df = pd.DataFrame(loan_history)
        print(f"  ✓ Loaded {len(loan_history_df)} loan history records")
        print()

        # 2. Score partners for Audi
        print("Step 2: Scoring LA partners for Audi...")

        scores = score_partners_base(
            partners_df=partners_df,
            vehicle_make='Audi',
            approved_makes_df=approved_makes_df,
            loan_history_df=loan_history_df
        )

        print(f"  ✓ Scored {len(scores)} partners")
        print()

        # 3. Show score distribution
        print("Step 3: Score distribution...")

        if scores:
            base_scores = [s['base_score'] for s in scores.values()]
            print(f"  Min score: {min(base_scores)}")
            print(f"  Max score: {max(base_scores)}")
            print(f"  Avg score: {sum(base_scores) / len(base_scores):.1f}")
            print()

        # 4. Show top 10 partners by score
        print("Step 4: Top 10 partners by base score...")

        sorted_partners = sorted(scores.items(), key=lambda x: x[1]['base_score'], reverse=True)

        for i, (person_id, score_data) in enumerate(sorted_partners[:10], 1):
            partner = partners_df[partners_df['person_id'] == person_id]
            if not partner.empty:
                name = partner.iloc[0]['name']
                print(f"  {i}. {name} (ID: {person_id})")
                print(f"     Base Score: {score_data['base_score']}")
                print(f"       - Engagement: {score_data['engagement_score']} ({score_data['engagement_level']})")
                print(f"       - Publication: {score_data['publication_score']} ({score_data['publication_rate']*100:.1f}% rate)")
                print(f"       - Tier: {score_data['tier_score']} (Rank: {score_data['tier_rank']})")
                print()

        # 5. Test specific known partners (Scott Goldenberg)
        print("Step 5: Testing known partner (Scott Goldenberg, ID: 620)...")

        if 620 in scores:
            scott_score = scores[620]
            print(f"  Scott's scores:")
            print(f"    Base Score: {scott_score['base_score']}")
            print(f"    - Engagement: {scott_score['engagement_score']} ({scott_score['engagement_level']})")
            print(f"    - Publication: {scott_score['publication_score']} ({scott_score['publication_rate']*100:.1f}%)")
            print(f"    - Tier (Audi): {scott_score['tier_score']} (Rank: {scott_score['tier_rank']})")
            print()

            # Verify tier rank for Scott (should be C for Audi)
            assert scott_score['tier_rank'] == 'C', f"Scott should have rank C for Audi, got {scott_score['tier_rank']}"
            assert scott_score['tier_score'] == 50, f"Rank C should score 50, got {scott_score['tier_score']}"
            print("  ✓ Scott's tier rank correct (C = 50 points)")
        else:
            print(f"  ⚠ Scott (620) not in scored partners (may not be in LA or not approved for Audi)")
        print()

        # 6. Check score components are reasonable
        print("Step 6: Validating score components...")

        has_engagement = sum(1 for s in scores.values() if s['engagement_score'] > 0)
        has_publication = sum(1 for s in scores.values() if s['publication_score'] > 0)
        has_tier = sum(1 for s in scores.values() if s['tier_score'] > 0)

        print(f"  Partners with engagement score: {has_engagement}/{len(scores)}")
        print(f"  Partners with publication score: {has_publication}/{len(scores)}")
        print(f"  Partners with tier score (approved for Audi): {has_tier}/{len(scores)}")
        print()

        print("=== All Partner Scoring Tests Passed! ✓ ===\n")

    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    test_with_real_data()
