"""Cross-partner date holds: a saved/requested car is taken for those dates."""

from datetime import date

import pandas as pd

from app.chain_builder.availability import (
    build_chain_availability_grid,
    check_slot_availability,
    get_available_vehicles_for_slot,
)


OFFICE = 'Los Angeles'
THIS_PARTNER = 222
OTHER_PARTNER = 111

VEHICLES = pd.DataFrame([
    {
        'vin': 'VIN_HELD',
        'make': 'Honda',
        'model': 'Accord',
        'office': OFFICE,
        'in_service_date': '2020-01-01',
    },
    {
        'vin': 'VIN_FREE',
        'make': 'Toyota',
        'model': 'Camry',
        'office': OFFICE,
        'in_service_date': '2020-01-01',
    },
])


def _hold(status='requested', vin='VIN_HELD', person_id=OTHER_PARTNER,
          start='2026-08-17', end='2026-08-24'):
    return pd.DataFrame([{
        'vin': vin,
        'person_id': person_id,
        'status': status,
        'start_day': start,
        'end_day': end,
    }])


def _grid(scheduled, person_id=THIS_PARTNER, start='2026-08-17', end='2026-08-31'):
    return build_chain_availability_grid(
        vehicles_df=VEHICLES,
        activity_df=pd.DataFrame(),
        start_date=start,
        num_slots=2,
        days_per_slot=7,
        office=OFFICE,
        end_date=end,
        scheduled_assignments_df=scheduled,
        current_person_id=person_id,
    )


def _slot_free(grid, vin, start, end):
    return check_slot_availability(vin, start, end, grid)['available']


def test_requested_car_is_hidden_from_the_next_media_on_the_same_dates():
    """RK's case: Media A requested the car; Media B must not see it that week."""
    grid = _grid(_hold('requested'))

    assert _slot_free(grid, 'VIN_HELD', '2026-08-17', '2026-08-24') is False
    assert _slot_free(grid, 'VIN_FREE', '2026-08-17', '2026-08-24') is True


def test_saved_green_assignment_also_holds_the_car():
    for status in ('manual', 'planned'):
        grid = _grid(_hold(status))
        assert _slot_free(grid, 'VIN_HELD', '2026-08-17', '2026-08-24') is False, status


def test_same_day_handoff_is_still_allowed():
    """A loan ending Monday does not block a loan starting Monday."""
    grid = _grid(_hold(start='2026-08-17', end='2026-08-24'))

    assert _slot_free(grid, 'VIN_HELD', '2026-08-24', '2026-08-31') is True


def test_later_non_overlapping_week_is_still_available():
    grid = _grid(
        _hold(start='2026-08-17', end='2026-08-24'),
        end='2026-09-07',
    )

    assert _slot_free(grid, 'VIN_HELD', '2026-08-31', '2026-09-07') is True


def test_cancelled_and_completed_do_not_hold_the_car():
    for status in ('cancelled', 'completed', 'rejected'):
        grid = _grid(_hold(status))
        assert _slot_free(grid, 'VIN_HELD', '2026-08-17', '2026-08-24') is True, status


def test_current_partner_can_still_see_their_own_hold():
    """Reopening a slot they already filled should keep the car in the list."""
    grid = _grid(_hold(person_id=THIS_PARTNER), person_id=THIS_PARTNER)

    assert _slot_free(grid, 'VIN_HELD', '2026-08-17', '2026-08-24') is True


def test_iso_timestamp_dates_and_mismatched_vin_types_still_hold():
    scheduled = pd.DataFrame([{
        'vin': ' VIN_HELD ',
        'person_id': str(OTHER_PARTNER),
        'status': 'Requested',
        'start_day': '2026-08-17T00:00:00',
        'end_day': '2026-08-24T00:00:00',
    }])
    grid = _grid(scheduled)

    assert _slot_free(grid, 'VIN_HELD', '2026-08-17', '2026-08-24') is False


def test_slot_options_exclude_the_held_car():
    grid = _grid(_hold('requested'))
    available = get_available_vehicles_for_slot(
        slot_index=0,
        slot_start='2026-08-17',
        slot_end='2026-08-24',
        candidate_vins={'VIN_HELD', 'VIN_FREE'},
        availability_df=grid,
    )

    assert set(available) == {'VIN_FREE'}


def test_true_overlap_mid_week_is_blocked():
    """Media B starting Wednesday into Media A's Mon-Mon loan."""
    grid = _grid(_hold(start='2026-08-17', end='2026-08-24'))

    assert _slot_free(grid, 'VIN_HELD', '2026-08-19', '2026-08-26') is False


def test_dropoff_day_is_marked_available_on_the_grid():
    grid = _grid(_hold(start='2026-08-17', end='2026-08-24'))
    held_days = grid[(grid['vin'] == 'VIN_HELD') & (grid['available'] == False)]
    held_dates = set(held_days['date'].tolist())

    assert date(2026, 8, 17) in held_dates
    assert date(2026, 8, 23) in held_dates
    assert date(2026, 8, 24) not in held_dates
