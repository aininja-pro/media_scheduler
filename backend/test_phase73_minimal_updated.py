"""
Updated minimal test suite for Phase 7.3 with MODEL priority and 30-day default.

Tests cooldown logic with model-level priority and safe fallbacks.
"""

import pandas as pd
from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.solver.cooldown_filter import apply_cooldown_filter, build_cooldown_ledger, get_cooldown_days


def test_a_within_window_blocks():
    """Test A: History 15 days ago, cooldown=30 blocks starts before day 30."""
    print("\n" + "="*60)
    print("TEST A: WITHIN WINDOW BLOCKS (30-day cooldown)")
    print("="*60)

    # Create loan history: ended 15 days ago
    today = datetime(2025, 9, 22)
    loan_history = pd.DataFrame([{
        'person_id': 'P001',
        'make': 'Toyota',
        'model': 'Camry',
        'short_model_class': 'MidSize',
        'powertrain': 'Hybrid',
        'start_date': today - timedelta(days=22),
        'end_date': today - timedelta(days=15)  # Ended 15 days ago
    }])

    # Create triples for different start days
    triples = pd.DataFrame([
        # Monday - 0 days from today (15 days after loan) - BLOCKED
        {'vin': 'V1', 'person_id': 'P001', 'start_day': today,
         'make': 'Toyota', 'model': 'Camry', 'short_model_class': 'MidSize', 'powertrain': 'Hybrid'},

        # Tuesday - 1 day from today (16 days after loan) - BLOCKED
        {'vin': 'V2', 'person_id': 'P001', 'start_day': today + timedelta(days=1),
         'make': 'Toyota', 'model': 'Camry', 'short_model_class': 'MidSize', 'powertrain': 'Hybrid'},

        # Day 30 - exactly at boundary (30 days after loan) - ALLOWED
        {'vin': 'V3', 'person_id': 'P001', 'start_day': today + timedelta(days=15),
         'make': 'Toyota', 'model': 'Camry', 'short_model_class': 'MidSize', 'powertrain': 'Hybrid'},

        # Day 31 - after cooldown (31 days after loan) - ALLOWED
        {'vin': 'V4', 'person_id': 'P001', 'start_day': today + timedelta(days=16),
         'make': 'Toyota', 'model': 'Camry', 'short_model_class': 'MidSize', 'powertrain': 'Hybrid'},
    ])

    # Use default 30-day cooldown
    rules = pd.DataFrame()  # Empty rules will use default

    result = apply_cooldown_filter(
        feasible_triples_df=triples,
        loan_history_df=loan_history,
        rules_df=rules,
        default_cooldown_days=30
    )

    print(f"Input triples: {len(triples)}")
    print(f"Output triples: {len(result)}")

    # Check specific cases
    allowed_vins = set(result['vin'].tolist())

    mon_blocked = 'V1' not in allowed_vins
    tue_blocked = 'V2' not in allowed_vins
    day60_allowed = 'V3' in allowed_vins
    day61_allowed = 'V4' in allowed_vins

    print(f"Monday (15 days after): {'Blocked' if mon_blocked else 'Allowed'}")
    print(f"Tuesday (16 days after): {'Blocked' if tue_blocked else 'Allowed'}")
    print(f"Day 30 (boundary): {'Allowed' if day60_allowed else 'Blocked'}")
    print(f"Day 31 (after): {'Allowed' if day61_allowed else 'Blocked'}")

    if mon_blocked and tue_blocked and day60_allowed and day61_allowed:
        print("✅ PASS: Cooldown window correctly enforced")
        return True
    else:
        print("❌ FAIL: Cooldown window not working correctly")
        return False


def test_b_disabled_by_rule():
    """Test B: cooldown_period_days=0 disables cooldown for that make."""
    print("\n" + "="*60)
    print("TEST B: DISABLED BY RULE")
    print("="*60)

    today = datetime(2025, 9, 22)

    # Loan history: ended yesterday
    loan_history = pd.DataFrame([{
        'person_id': 'P001',
        'make': 'Toyota',
        'model': 'Camry',
        'short_model_class': 'MidSize',
        'powertrain': 'Hybrid',
        'start_date': today - timedelta(days=8),
        'end_date': today - timedelta(days=1)  # Ended yesterday
    }])

    # Triple starting today (normally would be blocked)
    triples = pd.DataFrame([
        {'vin': 'V1', 'person_id': 'P001', 'start_day': today,
         'make': 'Toyota', 'model': 'Camry', 'short_model_class': 'MidSize', 'powertrain': 'Hybrid'},
    ])

    # Rule: cooldown disabled for Toyota
    rules = pd.DataFrame([
        {'make': 'Toyota', 'cooldown_period': 0}
    ])

    result = apply_cooldown_filter(
        feasible_triples_df=triples,
        loan_history_df=loan_history,
        rules_df=rules,
        default_cooldown_days=30
    )

    print(f"Input triples: {len(triples)}")
    print(f"Output triples: {len(result)}")

    if len(result) == 1:
        print("✅ PASS: Cooldown disabled by rule (0 days)")
        return True
    else:
        print("❌ FAIL: Triple removed despite cooldown=0")
        return False


def test_c_model_precedence():
    """Test C: Model takes precedence (updated from class+powertrain)."""
    print("\n" + "="*60)
    print("TEST C: MODEL PRECEDENCE (Updated)")
    print("="*60)

    today = datetime(2025, 9, 22)

    # Loan history: Same MODEL, different make for comparison
    loan_history = pd.DataFrame([
        {
            'person_id': 'P001',
            'make': 'Toyota',
            'model': 'Camry',  # Same model
            'short_model_class': 'MidSize',
            'powertrain': 'Hybrid',
            'start_date': today - timedelta(days=20),
            'end_date': today - timedelta(days=15)  # 15 days ago
        },
        {
            # Different make entirely (older)
            'person_id': 'P001',
            'make': 'Honda',
            'model': 'Accord',  # Different make and model
            'short_model_class': 'MidSize',
            'powertrain': 'Gas',
            'start_date': today - timedelta(days=60),
            'end_date': today - timedelta(days=50)  # 50 days ago
        }
    ])

    # Triple: Same model as recent loan
    triples_same_model = pd.DataFrame([
        {
            'vin': 'V1',
            'person_id': 'P001',
            'start_day': today,  # 15 days after Camry loan
            'make': 'Toyota',
            'model': 'Camry',  # Same model - SHOULD BE BLOCKED
            'short_model_class': 'MidSize',
            'powertrain': 'Gas'  # Different powertrain doesn't matter
        }
    ])

    # Triple: Different model, DIFFERENT make (to avoid make fallback)
    triples_diff_model = pd.DataFrame([
        {
            'vin': 'V2',
            'person_id': 'P001',
            'start_day': today,  # 15 days after Toyota Camry
            'make': 'Honda',
            'model': 'CR-V',  # Different make and model - SHOULD BE ALLOWED
            'short_model_class': 'SUV',
            'powertrain': 'Gas'
        }
    ])

    rules = pd.DataFrame()  # Use default 30 days

    # Test same model (should be blocked)
    result_same = apply_cooldown_filter(
        feasible_triples_df=triples_same_model,
        loan_history_df=loan_history,
        rules_df=rules,
        default_cooldown_days=30
    )

    # Test different model (should be allowed)
    result_diff = apply_cooldown_filter(
        feasible_triples_df=triples_diff_model,
        loan_history_df=loan_history,
        rules_df=rules,
        default_cooldown_days=30
    )

    print(f"Same model (Toyota Camry): {len(result_same)} triples")
    print(f"Different make/model (Honda CR-V): {len(result_diff)} triples")

    if len(result_same) == 0 and len(result_diff) == 1:
        print("✅ PASS: Model-level precedence working (blocks same model, allows different)")
        return True
    else:
        print("❌ FAIL: Model precedence not working correctly")
        return False


def test_d_fallback():
    """Test D: Falls back to make when model not in history."""
    print("\n" + "="*60)
    print("TEST D: FALLBACK TO MAKE")
    print("="*60)

    today = datetime(2025, 9, 22)

    # Loan history: Only make info, no model
    loan_history = pd.DataFrame([{
        'person_id': 'P001',
        'make': 'Toyota',
        'model': None,  # No model info
        'short_model_class': None,  # No class info
        'powertrain': None,  # No powertrain info
        'start_date': today - timedelta(days=22),
        'end_date': today - timedelta(days=15)  # 15 days ago
    }])

    # Create two triples
    triples = pd.DataFrame([
        # Triple 1: Within cooldown window (15 days < 30) - BLOCKED
        {
            'vin': 'V1',
            'person_id': 'P001',
            'start_day': today,
            'make': 'Toyota',
            'model': 'Camry',
            'short_model_class': 'MidSize',
            'powertrain': 'Hybrid'
        },
        # Triple 2: After cooldown window (50 days > 30) - ALLOWED
        {
            'vin': 'V2',
            'person_id': 'P001',
            'start_day': today + timedelta(days=20),  # 35 days after loan
            'make': 'Toyota',
            'model': 'Camry',
            'short_model_class': 'MidSize',
            'powertrain': 'Hybrid'
        }
    ])

    rules = pd.DataFrame()  # Use default 30 days

    result = apply_cooldown_filter(
        feasible_triples_df=triples,
        loan_history_df=loan_history,
        rules_df=rules,
        default_cooldown_days=30
    )

    print(f"Input triples: {len(triples)}")
    print(f"Output triples: {len(result)}")

    allowed_vins = set(result['vin'].tolist())
    v1_blocked = 'V1' not in allowed_vins
    v2_allowed = 'V2' in allowed_vins

    print(f"V1 (15 days after, make fallback): {'Blocked' if v1_blocked else 'Allowed'}")
    print(f"V2 (35 days after, make fallback): {'Allowed' if v2_allowed else 'Blocked'}")

    if v1_blocked and v2_allowed:
        print("✅ PASS: Make-level fallback working correctly")
        return True
    else:
        print("❌ FAIL: Make-level fallback not working")
        return False


def main():
    """Run all minimal tests."""
    print("="*80)
    print("PHASE 7.3 MINIMAL TEST SUITE (UPDATED)")
    print("Model priority + 30-day default")
    print("="*80)

    results = []

    # Run each test
    results.append(("Within Window Blocks", test_a_within_window_blocks()))
    results.append(("Disabled by Rule", test_b_disabled_by_rule()))
    results.append(("Model Precedence", test_c_model_precedence()))
    results.append(("Fallback to Make", test_d_fallback()))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{name}: {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)