"""
Pagination utilities for Supabase to handle tables with >1000 rows.

Prevents silent data truncation issues.
"""

import pandas as pd
from typing import Any, List, Optional


async def fetch_all_pages(
    db_client,
    table_name: str,
    select: str = '*',
    filters: Optional[List[tuple]] = None,
    page_size: int = 5000
) -> pd.DataFrame:
    """
    Fetch all rows from a table with pagination.

    Args:
        db_client: Supabase client
        table_name: Name of table to query
        select: Columns to select (default '*')
        filters: Optional list of (column, op, value) tuples
        page_size: Rows per page (default 5000)

    Returns:
        DataFrame with all rows
    """
    all_rows = []
    offset = 0

    while True:
        query = db_client.table(table_name).select(select)

        # Apply filters if provided
        if filters:
            for col, op, val in filters:
                if op == 'eq':
                    query = query.eq(col, val)
                elif op == 'gte':
                    query = query.gte(col, val)
                elif op == 'lte':
                    query = query.lte(col, val)
                # Add more operators as needed

        # Paginate
        response = query.range(offset, offset + page_size - 1).execute()

        if not response.data:
            break

        all_rows.extend(response.data)

        # Check if we got a full page
        if len(response.data) < page_size:
            break

        offset += page_size

    return pd.DataFrame(all_rows)


def verify_no_truncation(df: pd.DataFrame, table_name: str) -> bool:
    """
    Verify that a DataFrame doesn't have exactly 1000 rows (likely truncated).

    Args:
        df: DataFrame to check
        table_name: Name of source table for error message

    Returns:
        True if safe, raises error if likely truncated
    """
    if len(df) == 1000:
        raise ValueError(
            f"Table '{table_name}' returned exactly 1000 rows - likely truncated! "
            f"Use pagination to fetch all data."
        )
    return True