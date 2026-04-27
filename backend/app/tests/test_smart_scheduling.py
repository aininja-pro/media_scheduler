from datetime import datetime

from app.chain_builder.smart_scheduling import find_available_slots


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
