"""
Check what loan history and current activity data we have.
"""

import asyncio
import pandas as pd
from datetime import datetime
from app.services.database import DatabaseService


async def check_loan_data():
    db = DatabaseService()
    await db.initialize()

    print("="*80)
    print("CHECKING LOAN HISTORY AND CURRENT ACTIVITY")
    print("="*80)

    try:
        # 1. Check loan_history table WITH PAGINATION
        print("\n1. Checking loan_history table (with pagination)...")
        try:
            # Load ALL loan_history with pagination
            all_loan_history = []
            limit = 1000
            offset = 0

            while True:
                loan_history_response = db.client.table('loan_history').select('*').range(offset, offset + limit - 1).execute()
                if not loan_history_response.data:
                    break
                all_loan_history.extend(loan_history_response.data)
                print(f"   Loading... {len(all_loan_history)} records")
                offset += limit
                if len(loan_history_response.data) < limit:
                    break

            loan_history_df = pd.DataFrame(all_loan_history)

            print(f"   ✓ Found {len(loan_history_df)} records in loan_history")
            if not loan_history_df.empty:
                print(f"   Columns: {list(loan_history_df.columns)}")

                # Check for media loans
                if 'loan_type' in loan_history_df.columns:
                    media_loans = loan_history_df[loan_history_df['loan_type'] == 'media']
                    print(f"   Media loans: {len(media_loans)}")

                # Sample data
                print("\n   Sample records:")
                print(loan_history_df.head(3).to_string())

                # Check date ranges
                if 'start_date' in loan_history_df.columns:
                    loan_history_df['start_date'] = pd.to_datetime(loan_history_df['start_date'])
                    print(f"\n   Date range: {loan_history_df['start_date'].min()} to {loan_history_df['start_date'].max()}")

                # Check LA partners
                if 'person_id' in loan_history_df.columns:
                    unique_partners = loan_history_df['person_id'].nunique()
                    print(f"   Unique partners with history: {unique_partners}")

                    # Check LA-specific loans
                    if 'office' in loan_history_df.columns:
                        la_loans = loan_history_df[loan_history_df['office'] == 'Los Angeles']
                        print(f"   Los Angeles loans: {len(la_loans)}")

                        # Recent LA loans that would cause cooldown
                        if 'end_date' in la_loans.columns:
                            la_loans['end_date'] = pd.to_datetime(la_loans['end_date'])
                            # For Sept 22, 2025 week, 60-day cooldown means loans ending after July 24
                            cooldown_cutoff = pd.Timestamp('2025-07-24')
                            recent_la = la_loans[la_loans['end_date'] > cooldown_cutoff]
                            print(f"   Recent LA loans (potential cooldown): {len(recent_la)}")

                            if len(recent_la) > 0:
                                print(f"   Unique LA partners with recent loans: {recent_la['person_id'].nunique()}")
                                print("\n   Sample recent LA loans:")
                                cols = ['person_id', 'make', 'model', 'start_date', 'end_date']
                                print(recent_la[cols].head(5).to_string())

        except Exception as e:
            print(f"   ❌ Error accessing loan_history: {e}")

        # 2. Check current_activity table WITH PAGINATION
        print("\n2. Checking current_activity table (with pagination)...")
        try:
            # Load ALL current_activity with pagination
            all_activity = []
            limit = 1000
            offset = 0

            while True:
                activity_response = db.client.table('current_activity').select('*').range(offset, offset + limit - 1).execute()
                if not activity_response.data:
                    break
                all_activity.extend(activity_response.data)
                if len(all_activity) % 1000 == 0:
                    print(f"   Loading... {len(all_activity)} records")
                offset += limit
                if len(activity_response.data) < limit:
                    break

            activity_df = pd.DataFrame(all_activity)

            print(f"   ✓ Found {len(activity_df)} records in current_activity")
            if not activity_df.empty:
                print(f"   Columns: {list(activity_df.columns)}")

                # Check activity types
                if 'activity_type' in activity_df.columns:
                    activity_types = activity_df['activity_type'].value_counts()
                    print(f"\n   Activity types:")
                    for atype, count in activity_types.items():
                        print(f"     {atype}: {count}")

                # Check for loan activities
                if 'activity_type' in activity_df.columns:
                    loan_activities = activity_df[activity_df['activity_type'] == 'loan']
                    print(f"\n   Loan activities: {len(loan_activities)}")

                    if len(loan_activities) > 0 and 'partner_id' in loan_activities.columns:
                        print(f"   Partners with active loans: {loan_activities['partner_id'].nunique()}")

                # Sample data
                print("\n   Sample loan records:")
                if 'activity_type' in activity_df.columns:
                    loans = activity_df[activity_df['activity_type'] == 'loan']
                    if not loans.empty:
                        print(loans.head(3).to_string())

        except Exception as e:
            print(f"   ❌ Error accessing current_activity: {e}")

        # 3. Check loans table (mentioned in ChatGPT plan)
        print("\n3. Checking loans table...")
        try:
            loans_response = db.client.table('loans').select('*').execute()
            loans_df = pd.DataFrame(loans_response.data)

            print(f"   ✓ Found {len(loans_df)} records in loans table")
            if not loans_df.empty:
                print(f"   Columns: {list(loans_df.columns)}")

                # Sample data
                print("\n   Sample records:")
                print(loans_df.head(3).to_string())

        except Exception as e:
            print(f"   ❌ No loans table found: {e}")

        # 4. Check for loan_history_media_view
        print("\n4. Checking loan_history_media_view...")
        try:
            view_response = db.client.table('loan_history_media_view').select('*').execute()
            view_df = pd.DataFrame(view_response.data)

            print(f"   ✓ Found {len(view_df)} records in loan_history_media_view")
            if not view_df.empty:
                print(f"   Columns: {list(view_df.columns)}")

        except Exception as e:
            print(f"   ❌ No loan_history_media_view found: {e}")

        # 5. Try to construct media loan history from current_activity
        print("\n5. Constructing media loan history from current_activity...")
        if not activity_df.empty and 'activity_type' in activity_df.columns:
            loan_activities = activity_df[activity_df['activity_type'] == 'loan'].copy()

            if not loan_activities.empty:
                print(f"   Found {len(loan_activities)} loan activities")

                # Check what columns we have
                useful_cols = ['vin', 'vehicle_vin', 'partner_id', 'person_id',
                              'start_date', 'end_date', 'make', 'model']
                available_cols = [col for col in useful_cols if col in loan_activities.columns]
                print(f"   Available columns: {available_cols}")

                # Get vehicle info if needed
                if 'vin' in loan_activities.columns or 'vehicle_vin' in loan_activities.columns:
                    vin_col = 'vehicle_vin' if 'vehicle_vin' in loan_activities.columns else 'vin'

                    # Join with vehicles to get make/model
                    vehicles_response = db.client.table('vehicles').select('vin,make,model').execute()
                    vehicles_df = pd.DataFrame(vehicles_response.data)

                    loan_activities = loan_activities.merge(
                        vehicles_df,
                        left_on=vin_col,
                        right_on='vin',
                        how='left',
                        suffixes=('', '_vehicle')
                    )

                    # Use vehicle make/model if not present
                    if 'make' not in loan_activities.columns and 'make_vehicle' in loan_activities.columns:
                        loan_activities['make'] = loan_activities['make_vehicle']
                    if 'model' not in loan_activities.columns and 'model_vehicle' in loan_activities.columns:
                        loan_activities['model'] = loan_activities['model_vehicle']

                print(f"\n   Enhanced loan history with vehicle info:")
                print(f"   Records with make: {loan_activities['make'].notna().sum()}")
                print(f"   Records with model: {loan_activities['model'].notna().sum()}")

                # Recent loans that might cause cooldown (for Sept 22, 2025 week)
                if 'end_date' in loan_activities.columns:
                    loan_activities['end_date'] = pd.to_datetime(loan_activities['end_date'])
                    # For Sept 22, 2025 starts, cooldown of 60 days means loans ending after July 24, 2025 would block
                    cooldown_cutoff = pd.Timestamp('2025-07-24')  # 60 days before Sept 22
                    recent_loans = loan_activities[loan_activities['end_date'] > cooldown_cutoff]
                    print(f"\n   Recent loans (ended after July 24, 2025): {len(recent_loans)}")

                    if len(recent_loans) > 0:
                        print("\n   Recent loan samples:")
                        cols_to_show = ['partner_id', 'make', 'model', 'start_date', 'end_date']
                        cols_to_show = [c for c in cols_to_show if c in recent_loans.columns]
                        print(recent_loans[cols_to_show].head(5).to_string())

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await db.close()

    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(check_loan_data())