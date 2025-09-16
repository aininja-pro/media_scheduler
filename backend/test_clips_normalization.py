"""
Test the updated clips_received normalization logic.
"""

import pandas as pd


def _normalize_clips_value(x):
    """Updated normalization function (copied from publication.py)"""
    if x is None or pd.isna(x):
        return pd.NA

    x_str = str(x).strip().lower()

    # Handle explicit text values
    if x_str in {"true", "yes"}:
        return True
    if x_str in {"false", "no"}:
        return False
    if x_str in {"", "none", "null", "nan"}:
        return pd.NA

    # Handle numeric values - any non-zero number is published
    try:
        numeric_val = float(x_str)
        return numeric_val != 0.0  # True if non-zero, False if exactly 0
    except (ValueError, TypeError):
        # If not numeric, treat as unknown
        return pd.NA


def test_normalization():
    """Test various clips_received values."""
    print("Testing clips_received normalization logic:")
    print("=" * 50)

    test_values = [
        "1.0",    # Current data
        "4.0",    # Multiple clips
        "0.0",    # No clips
        "0",      # Zero
        "1",      # Single clip
        "10",     # Many clips
        "true",   # Text true
        "false",  # Text false
        "yes",    # Text yes
        "no",     # Text no
        "",       # Empty
        None,     # Null
        "null",   # Text null
        "invalid" # Invalid text
    ]

    for value in test_values:
        result = _normalize_clips_value(value)
        print(f"  '{value}' → {result}")

    print("\n" + "=" * 50)
    print("Business Logic Summary:")
    print("  - Any non-zero number (1.0, 4.0, 10) → True (published)")
    print("  - Zero (0, 0.0) → False (not published)")
    print("  - NULL/empty/invalid → pd.NA (unknown/excluded)")


if __name__ == "__main__":
    test_normalization()