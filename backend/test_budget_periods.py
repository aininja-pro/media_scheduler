"""Tests for monthly budget periods and Dave's spend/budget file formats."""

from app.solver.budget_periods import (
    add_month_period,
    expand_budget_allocation_rows,
    get_month_period,
    months_for_quarter,
    normalize_budgets_to_months,
    parse_spend_csv,
    period_label,
    rolling_display_months,
    rows_for_month,
    split_amount_across,
)
import pandas as pd


def test_get_month_period():
    assert get_month_period("2026-09-03") == (2026, "2026-09")
    assert get_month_period("2026-10-01") == (2026, "2026-10")
    assert get_month_period("2027-01-15") == (2027, "2027-01")


def test_add_month_and_label():
    assert add_month_period("2026-09", 1) == (2026, "2026-10")
    assert add_month_period("2026-12", 1) == (2027, "2027-01")
    assert period_label("2026-09") == "Sep 2026"
    months = rolling_display_months("2026-09-03", 3)
    assert [period for _, period in months] == ["2026-09", "2026-10", "2026-11"]


def test_quarter_split_adds_up():
    assert months_for_quarter(2026, "Q3") == ["2026-07", "2026-08", "2026-09"]
    shares = split_amount_across(4730, 3)
    assert len(shares) == 3
    assert abs(sum(shares) - 4730) < 0.01


def test_expand_quarterly_excel_row():
    rows = expand_budget_allocation_rows(
        [
            {
                "office": "Dallas",
                "fleet": "AUDI",
                "year": 2026,
                "quarter": "Q3",
                "month": None,
                "budget_amount": 2130,
            }
        ]
    )
    assert [row["quarter"] for row in rows] == ["2026-07", "2026-08", "2026-09"]
    assert abs(sum(row["budget_amount"] for row in rows) - 2130) < 0.01


def test_dave_monthly_export_zero_padded_months():
    """DriveShop export uses Month as '01'..'12' and a Tableau footer row."""
    from app.solver.budget_periods import (
        budget_source_rows_from_dataframe,
        is_junk_budget_excel_row,
        month_cell_as_text,
    )

    assert month_cell_as_text("01") == "01"
    assert month_cell_as_text("09") == "09"
    assert month_cell_as_text(9) == "09"
    assert is_junk_budget_excel_row(
        "Applied filters:\nbudget is greater than $0\nYear is greater than 2025",
        None,
        None,
    )

    df = pd.DataFrame(
        [
            {"Office": "Atlanta", "Fleet": "ACURA", "Year": 2026, "Month": "01", "Budget #": 924},
            {"Office": "Atlanta", "Fleet": "ACURA", "Year": 2026, "Month": "09", "Budget #": 413},
            {"Office": "Atlanta", "Fleet": "AUDI", "Year": 2026, "Month": "10", "Budget #": 852},
            {"Office": None, "Fleet": None, "Year": None, "Month": None, "Budget #": None},
            {
                "Office": "Applied filters:\nbudget is greater than $0",
                "Fleet": None,
                "Year": None,
                "Month": None,
                "Budget #": None,
            },
        ]
    )
    source = budget_source_rows_from_dataframe(df)
    assert len(source) == 3
    expanded = expand_budget_allocation_rows(source)
    assert [row["quarter"] for row in expanded] == ["2026-01", "2026-09", "2026-10"]
    assert expanded[0]["budget_amount"] == 924
    assert expanded[1]["office"] == "Atlanta"
    assert expanded[1]["fleet"] == "ACURA"


def test_expand_monthly_excel_row():
    rows = expand_budget_allocation_rows(
        [
            {
                "office": "Dallas",
                "fleet": "AUDI",
                "year": 2026,
                "quarter": None,
                "month": "9",
                "budget_amount": 710,
            }
        ]
    )
    assert rows == [
        {
            "office": "Dallas",
            "fleet": "AUDI",
            "year": 2026,
            "quarter": "2026-09",
            "budget_amount": 710,
            "amount_used": None,
        }
    ]


def test_parse_monthly_spend_csv():
    csv = '''"2026","9","Dallas","AUDI","66.00"\n"2026","9","Los Angeles","AUDI","1,840.79"\n'''
    df = parse_spend_csv(csv)
    assert list(df.columns) == ["office", "fleet", "year", "quarter", "amount_used"]
    dallas = df[df["office"] == "Dallas"].iloc[0]
    assert dallas["quarter"] == "2026-09"
    assert dallas["fleet"] == "AUDI"
    assert int(dallas["year"]) == 2026


def test_parse_spend_csv_strips_bom_from_driveshop_export():
    """
    The live FMS file starts with a UTF-8 BOM. If we miss it, the first
    year does not look like a year and every spend row is skipped.
    """
    csv = '\ufeff"2026","9","Los Angeles","AUDI","1,910.71"\n"2026","9","Los Angeles","MAZDA","4,986.22"\n'
    df = parse_spend_csv(csv)
    assert len(df) == 2
    audi = df[df["fleet"] == "AUDI"].iloc[0]
    assert audi["office"] == "Los Angeles"
    assert audi["quarter"] == "2026-09"
    assert int(audi["year"]) == 2026


def test_parse_spend_csv_with_header_and_bom():
    csv = '\ufeffYear,Month,Office,Fleet,Amount\n2026,9,Los Angeles,AUDI,"1,910.71"\n'
    df = parse_spend_csv(csv)
    assert len(df) == 1
    assert df.iloc[0]["quarter"] == "2026-09"
    assert df.iloc[0]["office"] == "Los Angeles"


def test_normalize_prefers_monthly_and_fills_from_quarter():
    df = pd.DataFrame(
        [
            {
                "office": "Dallas",
                "fleet": "AUDI",
                "year": 2026,
                "quarter": "Q3",
                "budget_amount": 2130,
                "amount_used": 9000,
            },
            {
                "office": "Dallas",
                "fleet": "AUDI",
                "year": 2026,
                "quarter": "2026-09",
                "budget_amount": None,
                "amount_used": 66.0,
            },
        ]
    )
    monthly = normalize_budgets_to_months(df)
    sept = monthly[monthly["quarter"] == "2026-09"].iloc[0]
    assert sept["amount_used"] == 66.0
    assert abs(sept["budget_amount"] - 710) < 0.01
    july = monthly[monthly["quarter"] == "2026-07"].iloc[0]
    assert july["amount_used"] is None or pd.isna(july["amount_used"])


def test_normalize_merges_spend_and_budget_when_fleet_case_differs():
    df = pd.DataFrame(
        [
            {
                "office": "Los Angeles",
                "fleet": "Audi",
                "year": 2026,
                "quarter": "2026-09",
                "budget_amount": 4820,
                "amount_used": None,
            },
            {
                "office": "Los Angeles",
                "fleet": "AUDI",
                "year": 2026,
                "quarter": "2026-09",
                "budget_amount": None,
                "amount_used": 1910.71,
            },
        ]
    )
    monthly = normalize_budgets_to_months(df)
    row = monthly.iloc[0]
    assert row["fleet"] == "AUDI"
    assert abs(row["budget_amount"] - 4820) < 0.01
    assert abs(row["amount_used"] - 1910.71) < 0.01
    matched = rows_for_month(monthly, "los angeles", 2026, "2026-09")
    assert len(matched) == 1
    assert abs(matched.iloc[0]["amount_used"] - 1910.71) < 0.01


def test_nightly_sync_ignores_old_quarterly_spend_file(monkeypatch=None):
    """The old quarterly file must not be what the nightly job pulls."""
    from app.services.nightly_sync import budget_spending_url
    from app.solver.budget_periods import DEFAULT_MONTHLY_SPEND_URL
    import os

    old = os.environ.get("FMS_BUDGET_SPENDING_CSV_URL")
    try:
        os.environ["FMS_BUDGET_SPENDING_CSV_URL"] = (
            "https://reports.driveshop.com/?report=file:/home/deployer/reports/"
            "ai_scheduling/current_spend.rpt&init=csv"
        )
        assert budget_spending_url() == DEFAULT_MONTHLY_SPEND_URL
        assert "current_spend_by_month.rpt" in budget_spending_url()

        os.environ["FMS_BUDGET_SPENDING_CSV_URL"] = DEFAULT_MONTHLY_SPEND_URL
        assert budget_spending_url() == DEFAULT_MONTHLY_SPEND_URL

        os.environ.pop("FMS_BUDGET_SPENDING_CSV_URL", None)
        assert budget_spending_url() == DEFAULT_MONTHLY_SPEND_URL
    finally:
        if old is None:
            os.environ.pop("FMS_BUDGET_SPENDING_CSV_URL", None)
        else:
            os.environ["FMS_BUDGET_SPENDING_CSV_URL"] = old


if __name__ == "__main__":
    test_get_month_period()
    test_add_month_and_label()
    test_quarter_split_adds_up()
    test_expand_quarterly_excel_row()
    test_dave_monthly_export_zero_padded_months()
    test_expand_monthly_excel_row()
    test_parse_monthly_spend_csv()
    test_parse_spend_csv_strips_bom_from_driveshop_export()
    test_parse_spend_csv_with_header_and_bom()
    test_normalize_prefers_monthly_and_fills_from_quarter()
    test_normalize_merges_spend_and_budget_when_fleet_case_differs()
    test_nightly_sync_ignores_old_quarterly_spend_file()
    print("All monthly budget period tests passed")
