#!/usr/bin/env python3
"""
Check loan_history table schema for clips_received field.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

import pandas as pd
import asyncio
from app.services.database import db_service

async def check_loan_history_schema():
    """Check if clips_received field exists in loan_history table."""

    print("🔌 Checking loan_history table schema...")

    try:
        # Get sample loan history record to check schema
        response = db_service.client.table('loan_history').select('*').limit(5).execute()
        if response.data:
            record = response.data[0]
            print(f"\n📋 Loan history columns ({len(record)} fields):")
            for key in sorted(record.keys()):
                value = record[key]
                print(f"  {key}: {type(value).__name__} = {repr(value)}")

            if 'clips_received' in record:
                print('\n✅ clips_received field EXISTS!')
                print(f'   Type: {type(record["clips_received"]).__name__}')
                print(f'   Value: {repr(record["clips_received"])}')

                # Check distribution of clips_received values
                all_response = db_service.client.table('loan_history').select('clips_received').limit(100).execute()
                if all_response.data:
                    clips_df = pd.DataFrame(all_response.data)
                    print(f'\n📊 clips_received value distribution (sample 100):')
                    value_counts = clips_df['clips_received'].value_counts(dropna=False)
                    for value, count in value_counts.items():
                        print(f'   {repr(value)}: {count} records')

            else:
                print('\n❌ clips_received field MISSING from schema')
                print('   Available fields:', list(record.keys()))
                print('   Need to add this field to loan_history table')

        else:
            print('❌ No loan history data found')

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_loan_history_schema())