"""
Month-based budget periods.

The budgets table still has a `quarter` column. We now store a calendar
month in that column as 'YYYY-MM' (for example '2026-09').

Older rows may still say 'Q1'–'Q4'. Those get split into three equal
months so the scheduler can show Sept / Oct / Nov instead of a quarter.
"""

from __future__ import annotations

import re
from datetime import datetime
from io import StringIO
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

try:
    from zoneinfo import ZoneInfo

    PACIFIC = ZoneInfo("America/Los_Angeles")
except Exception:  # pragma: no cover - zoneinfo is standard on 3.11
    PACIFIC = None

MONTH_ABBREV = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)
MONTH_NAME_TO_NUM = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
LEGACY_QUARTERS = {"Q1", "Q2", "Q3", "Q4"}
MONTH_PERIOD_RE = re.compile(r"^(\d{4})-(\d{2})$")
DISPLAY_MONTH_COUNT = 3


def today_pacific() -> str:
    """Today's date in America/Los_Angeles as YYYY-MM-DD."""
    if PACIFIC is not None:
        return datetime.now(PACIFIC).date().isoformat()
    return datetime.now().date().isoformat()


def is_month_period(value: Any) -> bool:
    """True when value looks like '2026-09'."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    return bool(MONTH_PERIOD_RE.match(str(value).strip()))


def is_legacy_quarter(value: Any) -> bool:
    """True when value is Q1, Q2, Q3, or Q4."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    return str(value).strip().upper() in LEGACY_QUARTERS


def format_month_period(year: int, month: int) -> str:
    """Build the stored period key, e.g. 2026 + 9 → '2026-09'."""
    return f"{int(year)}-{int(month):02d}"


def parse_month_period(period: str) -> Tuple[int, int]:
    """Split '2026-09' into (2026, 9)."""
    match = MONTH_PERIOD_RE.match(str(period).strip())
    if not match:
        raise ValueError(f"Not a month period: {period}")
    return int(match.group(1)), int(match.group(2))


def get_month_period(date_str: str) -> Tuple[int, str]:
    """
    Year and month-period for a loan start date.

    A loan that starts 2026-09-03 is charged to September, not split
    across pickup and return. That matches how Dave described average loans.
    """
    date = pd.to_datetime(date_str)
    year = int(date.year)
    return year, format_month_period(year, int(date.month))


def add_month_period(period: str, offset: int) -> Tuple[int, str]:
    """Move a month period forward or backward. offset=1 turns Sep into Oct."""
    year, month = parse_month_period(period)
    month += offset
    while month > 12:
        month -= 12
        year += 1
    while month < 1:
        month += 12
        year -= 1
    return year, format_month_period(year, month)


def period_label(period: str) -> str:
    """'2026-09' → 'Sep 2026' for the Media Info pills."""
    year, month = parse_month_period(period)
    return f"{MONTH_ABBREV[month - 1]} {year}"


def rolling_display_months(
    anchor_date: Optional[str] = None,
    count: int = DISPLAY_MONTH_COUNT,
) -> List[Tuple[int, str]]:
    """
    The three months Dave asked for: this month, next month, the month after.

    Always anchored to calendar today (Pacific), not the first loan on screen.
    That is why the pills stay on Sep/Oct/Nov in September even if someone
    is planning an October chain.
    """
    if not anchor_date:
        anchor_date = today_pacific()
    year, period = get_month_period(anchor_date)
    months = [(year, period)]
    for i in range(1, count):
        months.append(add_month_period(period, i))
    return months


def months_for_quarter(year: int, quarter: str) -> List[str]:
    """Q3 2026 → ['2026-07', '2026-08', '2026-09']."""
    qnum = int(str(quarter).strip().upper().replace("Q", ""))
    start_month = (qnum - 1) * 3 + 1
    return [format_month_period(year, start_month + i) for i in range(3)]


def split_amount_across(amount: Optional[float], parts: int = 3) -> List[Optional[float]]:
    """
    Split a quarterly budget into equal months.

    Leftover cents go on the last month so Jul+Aug+Sep still add up
    to the original quarter total.
    """
    if amount is None or (isinstance(amount, float) and pd.isna(amount)):
        return [None] * parts
    cents = int(round(float(amount) * 100))
    base, remainder = divmod(cents, parts)
    result = [base] * parts
    result[-1] += remainder
    return [value / 100.0 for value in result]


def parse_month_value(raw: Any) -> Optional[int]:
    """Accept 9, '9', '09', 'Sep', 'September', or '2026-09'."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        month = int(raw)
        if 1 <= month <= 12:
            return month
        return None
    text = str(raw).strip()
    if not text:
        return None
    period_match = MONTH_PERIOD_RE.match(text)
    if period_match:
        return int(period_match.group(2))
    if text.isdigit():
        month = int(text)
        if 1 <= month <= 12:
            return month
        return None
    try:
        month = int(float(text.replace(",", "")))
        if 1 <= month <= 12:
            return month
    except ValueError:
        pass
    return MONTH_NAME_TO_NUM.get(text.lower())


def _looks_like_year(value: Any) -> bool:
    try:
        year = int(float(str(value).replace(",", "").replace('"', "").strip()))
    except (TypeError, ValueError):
        return False
    return 2000 <= year <= 2100


def _first_row_is_header(values: Iterable[Any]) -> bool:
    cells = [str(v).strip().lower() for v in values]
    if cells and _looks_like_year(cells[0]):
        return False
    header_words = {"year", "month", "office", "fleet", "amount", "amount_used", "spend"}
    return any(cell in header_words or cell.startswith("amount") for cell in cells)


def parse_spend_csv(csv_content: str) -> pd.DataFrame:
    """
    Read Dave's monthly spend report (or the older quarterly one).

    New report (no header, quoted fields):
        year, month, office, fleet, amount_used
        "2026","9","Dallas","AUDI","66.00"

    Older report:
        fleet, office, year, quarter, amount_used
    """
    df = pd.read_csv(StringIO(csv_content), header=None, dtype=str)
    if df.empty:
        return pd.DataFrame(columns=["office", "fleet", "year", "quarter", "amount_used"])

    if _first_row_is_header(df.iloc[0].tolist()):
        df = df.iloc[1:].reset_index(drop=True)

    if df.empty:
        return pd.DataFrame(columns=["office", "fleet", "year", "quarter", "amount_used"])

    if df.shape[1] < 5:
        raise ValueError("Spend CSV must have 5 columns")

    df = df.iloc[:, :5].copy()
    first_cell = df.iloc[0, 0]
    if _looks_like_year(first_cell):
        df.columns = ["year", "month", "office", "fleet", "amount_used"]
        periods = []
        years = []
        for _, row in df.iterrows():
            year = int(float(str(row["year"]).replace(",", "").strip()))
            month = parse_month_value(row["month"])
            if month is None:
                raise ValueError(f"Could not read month from {row['month']}")
            years.append(year)
            periods.append(format_month_period(year, month))
        out = pd.DataFrame(
            {
                "office": df["office"].astype(str).str.strip(),
                "fleet": df["fleet"].astype(str).str.strip(),
                "year": years,
                "quarter": periods,
                "amount_used": df["amount_used"],
            }
        )
        return out

    df.columns = ["fleet", "office", "year", "quarter", "amount_used"]
    years = []
    for raw in df["year"]:
        years.append(int(float(str(raw).replace(",", "").strip())))
    return pd.DataFrame(
        {
            "office": df["office"].astype(str).str.strip(),
            "fleet": df["fleet"].astype(str).str.strip(),
            "year": years,
            "quarter": df["quarter"].astype(str).str.strip().str.upper(),
            "amount_used": df["amount_used"],
        }
    )


def _row_key(office: Any, fleet: Any, year: Any, period: str) -> Tuple[str, str, int, str]:
    return (str(office), str(fleet), int(year), period)


def normalize_budgets_to_months(budgets_df: pd.DataFrame) -> pd.DataFrame:
    """
    Return one row per office / fleet / calendar month.

    Monthly rows ('2026-09') win. If a monthly row has no budget_amount yet
    (spend synced first), fill the amount from the matching quarter ÷ 3.
    If only a quarterly row exists, invent three month rows with equal shares
    and amount_used left empty — monthly spend comes from the FMS report.
    """
    if budgets_df is None or budgets_df.empty:
        return pd.DataFrame()

    monthly: Dict[Tuple[str, str, int, str], Dict[str, Any]] = {}
    quarterly_fallback: Dict[Tuple[str, str, int, str], Optional[float]] = {}

    for _, row in budgets_df.iterrows():
        period_raw = row.get("quarter")
        if pd.isna(row.get("year")):
            continue
        year = int(row["year"])
        office = row.get("office")
        fleet = row.get("fleet")
        budget_amount = row.get("budget_amount")
        if pd.isna(budget_amount):
            budget_amount = None
        elif budget_amount is not None:
            budget_amount = float(budget_amount)
        amount_used = row.get("amount_used")
        if pd.isna(amount_used):
            amount_used = None
        elif amount_used is not None:
            amount_used = float(amount_used)

        if is_month_period(period_raw):
            key = _row_key(office, fleet, year, str(period_raw).strip())
            if key in monthly:
                existing = monthly[key]
                if existing.get("budget_amount") is None and budget_amount is not None:
                    existing["budget_amount"] = budget_amount
                if existing.get("amount_used") is None and amount_used is not None:
                    existing["amount_used"] = amount_used
                elif existing.get("amount_used") is not None and amount_used is not None:
                    existing["amount_used"] = float(existing["amount_used"]) + amount_used
                if existing.get("budget_amount") is not None and budget_amount is not None:
                    # Two monthly rows for the same key (rare) — keep the first
                    # budget and ignore a duplicate allocation.
                    pass
            else:
                monthly[key] = {
                    "office": office,
                    "fleet": fleet,
                    "year": year,
                    "quarter": str(period_raw).strip(),
                    "budget_amount": budget_amount,
                    "amount_used": amount_used,
                }
        elif is_legacy_quarter(period_raw):
            shares = split_amount_across(budget_amount, 3)
            for period, share in zip(months_for_quarter(year, str(period_raw)), shares):
                quarterly_fallback[_row_key(office, fleet, year, period)] = share

    for key, share in quarterly_fallback.items():
        if key in monthly:
            if monthly[key].get("budget_amount") is None:
                monthly[key]["budget_amount"] = share
        else:
            office, fleet, year, period = key
            monthly[key] = {
                "office": office,
                "fleet": fleet,
                "year": year,
                "quarter": period,
                "budget_amount": share,
                "amount_used": None,
            }

    if not monthly:
        return pd.DataFrame()
    return pd.DataFrame(list(monthly.values()))


def month_cell_as_text(value: Any) -> Optional[str]:
    """Keep Dave's '01' / '09' month cells as text so Excel does not turn them into dates."""
    parsed = parse_month_value(value)
    if parsed is not None:
        return f"{parsed:02d}"
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def is_junk_budget_excel_row(office: Any, fleet: Any, year: Any) -> bool:
    """Skip blank rows and the 'Applied filters:' footer Tableau puts on exports."""
    office_text = str(office or "").strip()
    if not office_text:
        return True
    lowered = office_text.lower()
    if lowered.startswith("applied filters") or "budget is greater than" in lowered:
        return True
    if year in (None, "") or (isinstance(year, float) and pd.isna(year)):
        return True
    if not str(fleet or "").strip() or str(fleet).strip().lower() == "none":
        return True
    return False


def _lookup_excel_value(row: Any, *names: str) -> Any:
    """Read a cell by header name, ignoring extra spaces and capitalization."""
    lookup = {str(label).strip().lower(): label for label in row.index}
    for name in names:
        key = name.strip().lower()
        if key in lookup:
            return row[lookup[key]]
    return None


def budget_source_rows_from_dataframe(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Turn Dave's budget Excel into source rows.

    Current format (Sept 2026):
        Office, Fleet, Year, Month, Budget #
        Atlanta, ACURA, 2026, 01, 924

    Older format still works:
        Office, Fleet, Year, Quarter, Budget #
    """
    if df is None or df.empty:
        return []

    rows: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        office = _lookup_excel_value(row, "Office")
        fleet = _lookup_excel_value(row, "Fleet")
        year = _lookup_excel_value(row, "Year")
        if is_junk_budget_excel_row(office, fleet, year):
            continue
        try:
            year_int = int(float(str(year).replace(",", "").strip()))
        except (TypeError, ValueError):
            continue
        rows.append(
            {
                "office": str(office).strip(),
                "fleet": str(fleet).strip(),
                "year": year_int,
                "quarter": (
                    str(_lookup_excel_value(row, "Quarter")).strip()
                    if _lookup_excel_value(row, "Quarter") not in (None, "")
                    and not (
                        isinstance(_lookup_excel_value(row, "Quarter"), float)
                        and pd.isna(_lookup_excel_value(row, "Quarter"))
                    )
                    else None
                ),
                "month": month_cell_as_text(_lookup_excel_value(row, "Month")),
                "budget_amount": _lookup_excel_value(row, "Budget #", "Budget", "Budget Amount"),
                "amount_used": None,
            }
        )
    return rows


def expand_budget_allocation_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Turn an Excel upload into monthly records.

    A row with Month 9 becomes one '2026-09' record.
    A row with Quarter Q3 becomes three records (Jul / Aug / Sep),
    each with one-third of Budget #.
    """
    expanded: List[Dict[str, Any]] = []
    for row in rows:
        year = int(row["year"])
        month = parse_month_value(row.get("month"))
        quarter = row.get("quarter")
        if month is not None:
            expanded.append(
                {
                    "office": row["office"],
                    "fleet": row["fleet"],
                    "year": year,
                    "quarter": format_month_period(year, month),
                    "budget_amount": row.get("budget_amount"),
                    "amount_used": None,
                }
            )
            continue
        if is_legacy_quarter(quarter):
            shares = split_amount_across(row.get("budget_amount"), 3)
            for period, share in zip(months_for_quarter(year, str(quarter)), shares):
                expanded.append(
                    {
                        "office": row["office"],
                        "fleet": row["fleet"],
                        "year": year,
                        "quarter": period,
                        "budget_amount": share,
                        "amount_used": None,
                    }
                )
            continue
        if is_month_period(quarter):
            expanded.append(
                {
                    "office": row["office"],
                    "fleet": row["fleet"],
                    "year": year,
                    "quarter": str(quarter).strip(),
                    "budget_amount": row.get("budget_amount"),
                    "amount_used": None,
                }
            )
    return expanded
