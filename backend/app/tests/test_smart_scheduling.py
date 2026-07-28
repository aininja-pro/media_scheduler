from datetime import datetime

import pandas as pd

from app.chain_builder.smart_scheduling import (
    find_available_slots,
    get_partner_busy_periods,
    summarize_schedule_adjustment,
)


def busy(start, end, label="Existing loan"):
    return {"start": datetime(*start), "end": datetime(*end), "label": label}


def test_partner_chain_seven_days_ends_on_same_weekday():
    slots = find_available_slots(
        busy_periods=[],
        chain_start=datetime(2026, 4, 30),
        chain_end=datetime(2026, 5, 30),
        num_slots=2,
        days_per_slot=7,
    )

    assert slots[0]["start_date"] == "2026-04-30"
    assert slots[0]["end_date"] == "2026-05-07"
    assert slots[1]["start_date"] == "2026-05-07"


# --- avoid mode (default) -------------------------------------------------


def test_avoid_mode_pushes_past_a_conflicting_loan():
    slots = find_available_slots(
        busy_periods=[busy((2026, 5, 4), (2026, 5, 18))],
        chain_start=datetime(2026, 4, 30),
        chain_end=datetime(2026, 7, 30),
        num_slots=1,
        days_per_slot=7,
    )

    assert slots[0]["start_date"] == "2026-05-18"
    assert slots[0]["conflicts"] == []


def test_slot_may_end_the_day_a_loan_begins():
    """Same-day handoff works on both edges, so this slot must not be pushed."""
    slots = find_available_slots(
        busy_periods=[busy((2026, 5, 7), (2026, 5, 21))],
        chain_start=datetime(2026, 4, 30),
        chain_end=datetime(2026, 7, 30),
        num_slots=1,
        days_per_slot=7,
    )

    assert slots[0]["start_date"] == "2026-04-30"
    assert slots[0]["end_date"] == "2026-05-07"


# --- allow_double_booking -------------------------------------------------


def test_double_booking_keeps_the_requested_start_date():
    """The bug Dave reported: a long loan used to push the chain months out."""
    slots = find_available_slots(
        busy_periods=[busy((2026, 5, 4), (2026, 8, 31), "Volkswagen Golf R")],
        chain_start=datetime(2026, 4, 30),
        chain_end=datetime(2026, 7, 30),
        num_slots=3,
        days_per_slot=7,
        allow_double_booking=True,
    )

    assert len(slots) == 3
    assert slots[0]["start_date"] == "2026-04-30"
    assert slots[1]["start_date"] == "2026-05-07"
    assert slots[2]["start_date"] == "2026-05-14"


def test_double_booking_flags_only_the_overlapping_slots():
    slots = find_available_slots(
        busy_periods=[busy((2026, 5, 7), (2026, 5, 14), "Lexus RX 450h+")],
        chain_start=datetime(2026, 4, 30),
        chain_end=datetime(2026, 7, 30),
        num_slots=3,
        days_per_slot=7,
        allow_double_booking=True,
    )

    # Slot 1 ends the day the loan starts, slot 3 starts the day it ends —
    # both are legitimate same-day handoffs.
    assert slots[0]["conflicts"] == []
    assert slots[1]["conflicts"] == ["Lexus RX 450h+"]
    assert slots[2]["conflicts"] == []


def test_double_booking_never_returns_fewer_slots_than_requested():
    slots = find_available_slots(
        busy_periods=[busy((2026, 4, 1), (2027, 4, 1))],
        chain_start=datetime(2026, 4, 30),
        chain_end=datetime(2026, 5, 30),
        num_slots=8,
        days_per_slot=7,
        allow_double_booking=True,
    )

    assert len(slots) == 8
    assert all(s["conflicts"] for s in slots)


def test_slots_still_start_and_end_on_weekdays_when_double_booked():
    slots = find_available_slots(
        busy_periods=[busy((2026, 4, 1), (2027, 4, 1))],
        chain_start=datetime(2026, 5, 2),  # a Saturday
        chain_end=datetime(2026, 12, 30),
        num_slots=4,
        days_per_slot=7,
        allow_double_booking=True,
    )

    for slot in slots:
        for key in ("start_date", "end_date"):
            assert datetime.strptime(slot[key], "%Y-%m-%d").weekday() < 5


# --- busy period collection ----------------------------------------------


def test_cancelled_assignments_do_not_block():
    scheduled = pd.DataFrame([
        {"person_id": 7, "start_day": "2026-05-04", "end_day": "2026-05-11",
         "status": "cancelled", "make": "Toyota", "model": "Camry"},
        {"person_id": 7, "start_day": "2026-05-18", "end_day": "2026-05-25",
         "status": "manual", "make": "Mazda", "model": "CX-90"},
    ])

    periods = get_partner_busy_periods(
        person_id=7,
        current_activity_df=pd.DataFrame(),
        scheduled_assignments_df=scheduled,
        start_date="2026-04-30",
        end_date="2026-07-30",
    )

    assert [p["label"] for p in periods] == ["Mazda CX-90 (2026-05-18 to 2026-05-25)"]


def test_busy_periods_are_scoped_to_the_partner():
    scheduled = pd.DataFrame([
        {"person_id": 7, "start_day": "2026-05-04", "end_day": "2026-05-11",
         "status": "manual", "make": "Toyota", "model": "Camry"},
        {"person_id": 99, "start_day": "2026-05-04", "end_day": "2026-05-11",
         "status": "manual", "make": "Honda", "model": "Accord"},
    ])

    periods = get_partner_busy_periods(
        person_id=7,
        current_activity_df=pd.DataFrame(),
        scheduled_assignments_df=scheduled,
        start_date="2026-04-30",
        end_date="2026-07-30",
    )

    assert len(periods) == 1
    assert "Toyota Camry" in periods[0]["label"]


# --- adjustment summary ---------------------------------------------------


def test_summary_reports_a_moved_start_date():
    slots = find_available_slots(
        busy_periods=[busy((2026, 5, 4), (2026, 5, 18))],
        chain_start=datetime(2026, 4, 30),
        chain_end=datetime(2026, 7, 30),
        num_slots=2,
        days_per_slot=7,
    )
    summary = summarize_schedule_adjustment("2026-04-30", slots, num_requested=2)

    assert summary["start_date_moved"] is True
    assert summary["actual_start_date"] == "2026-05-18"
    assert summary["has_double_booking"] is False


def test_summary_reports_double_booked_slots():
    slots = find_available_slots(
        busy_periods=[busy((2026, 5, 4), (2026, 8, 31), "Volkswagen Golf R")],
        chain_start=datetime(2026, 4, 30),
        chain_end=datetime(2026, 7, 30),
        num_slots=2,
        days_per_slot=7,
        allow_double_booking=True,
    )
    summary = summarize_schedule_adjustment("2026-04-30", slots, num_requested=2)

    assert summary["start_date_moved"] is False
    assert summary["has_double_booking"] is True
    assert summary["double_booked_slots"][0]["conflicts"] == ["Volkswagen Golf R"]
