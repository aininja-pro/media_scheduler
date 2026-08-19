"""
Pagination utilities for Supabase to handle tables with >1000 rows.

Prevents silent data truncation issues.
"""

import pandas as pd
from typing import List, Optional

# Supabase returns at most 1000 rows unless the project max is raised.
# Stay at 1000 so a "full page" always means "there may be more."
DEFAULT_PAGE_SIZE = 1000

# Rows that occupy a vehicle for other partners. Completed/cancelled/rejected
# are history and must not hide the car.
BLOCKING_ASSIGNMENT_STATUSES = ['planned', 'manual', 'requested', 'active']


def fetch_all_rows(
    db_client,
    table_name: str,
    select: str = '*',
    filters: Optional[List[tuple]] = None,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> pd.DataFrame:
    """Fetch every matching row, paging past Supabase's 1000-row cap.

    filters: optional list of (column, op, value) tuples.
    ops: eq, gte, lte, in
    """
    all_rows = []
    offset = 0

    while True:
        query = db_client.table(table_name).select(select)

        if filters:
            for col, op, val in filters:
                if op == 'eq':
                    query = query.eq(col, val)
                elif op == 'gte':
                    query = query.gte(col, val)
                elif op == 'lte':
                    query = query.lte(col, val)
                elif op == 'in':
                    query = query.in_(col, val)

        response = query.range(offset, offset + page_size - 1).execute()

        if not response.data:
            break

        all_rows.extend(response.data)

        if len(response.data) < page_size:
            break

        offset += page_size

    return pd.DataFrame(all_rows)


def fetch_blocking_scheduled_assignments(
    db_client,
    select: str = '*',
) -> pd.DataFrame:
    """All green/magenta/blue assignments that should hold a vehicle.

    Filtering by status in the query matters: if we loaded the whole table
    unpaged, the first 1000 rows were often old completed ones, and newer
    requested rows never made it into the availability check.
    """
    return fetch_all_rows(
        db_client,
        'scheduled_assignments',
        select=select,
        filters=[('status', 'in', BLOCKING_ASSIGNMENT_STATUSES)],
    )


async def fetch_all_pages(
    db_client,
    table_name: str,
    select: str = '*',
    filters: Optional[List[tuple]] = None,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> pd.DataFrame:
    """Async wrapper around fetch_all_rows for existing callers."""
    return fetch_all_rows(
        db_client,
        table_name,
        select=select,
        filters=filters,
        page_size=page_size,
    )


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