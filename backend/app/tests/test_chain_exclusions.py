"""Hide cars a partner already has — past, current, or upcoming."""

import pandas as pd

from app.chain_builder.exclusions import get_vehicles_not_reviewed


OFFICE_VEHICLES = pd.DataFrame([
    {'vin': 'VIN_PAST', 'make': 'Honda', 'model': 'Accord', 'office': 'New York'},
    {'vin': 'VIN_FUTURE_FMS', 'make': 'Toyota', 'model': 'Camry', 'office': 'New York'},
    {'vin': 'VIN_SCHEDULED', 'make': 'Audi', 'model': 'A4', 'office': 'New York'},
    {'vin': 'VIN_CANCELLED', 'make': 'BMW', 'model': '3 Series', 'office': 'New York'},
    {'vin': 'VIN_OTHER_PERSON', 'make': 'Ford', 'model': 'Mustang', 'office': 'New York'},
    {'vin': 'VIN_FREE', 'make': 'Subaru', 'model': 'Outback', 'office': 'New York'},
])

PARTNER_ID = 1001
OTHER_ID = 2002


def _exclude(**kwargs):
    defaults = dict(
        person_id=PARTNER_ID,
        office='New York',
        loan_history_df=pd.DataFrame(),
        vehicles_df=OFFICE_VEHICLES,
    )
    defaults.update(kwargs)
    return get_vehicles_not_reviewed(**defaults)


def test_past_loan_history_still_hides_the_car():
    history = pd.DataFrame([
        {'person_id': PARTNER_ID, 'vin': 'VIN_PAST', 'start_date': '2025-01-01', 'end_date': '2025-01-08'},
    ])
    result = _exclude(loan_history_df=history)

    assert 'VIN_PAST' in result['excluded_vins']
    assert 'VIN_FREE' in result['available_vins']


def test_future_fms_loan_hides_the_car_even_with_no_history():
    """Dave's NY case: she is already booked in this VIN later this month."""
    activity = pd.DataFrame([
        {
            'person_id': PARTNER_ID,
            'vehicle_vin': 'VIN_FUTURE_FMS',
            'activity_type': 'loan',
            'start_date': '2026-08-24',
            'end_date': '2026-08-31',
        }
    ])
    result = _exclude(current_activity_df=activity)

    assert 'VIN_FUTURE_FMS' in result['excluded_vins']
    assert 'VIN_FREE' in result['available_vins']


def test_future_scheduled_assignment_hides_the_car():
    scheduled = pd.DataFrame([
        {
            'person_id': PARTNER_ID,
            'vin': 'VIN_SCHEDULED',
            'status': 'planned',
            'start_day': '2026-08-24',
            'end_day': '2026-08-31',
        }
    ])
    result = _exclude(scheduled_assignments_df=scheduled)

    assert 'VIN_SCHEDULED' in result['excluded_vins']
    assert 'VIN_FREE' in result['available_vins']


def test_cancelled_assignment_does_not_hide_the_car():
    scheduled = pd.DataFrame([
        {
            'person_id': PARTNER_ID,
            'vin': 'VIN_CANCELLED',
            'status': 'cancelled',
            'start_day': '2026-08-24',
            'end_day': '2026-08-31',
        }
    ])
    result = _exclude(scheduled_assignments_df=scheduled)

    assert 'VIN_CANCELLED' in result['available_vins']


def test_someone_elses_future_loan_does_not_hide_the_car():
    activity = pd.DataFrame([
        {
            'person_id': OTHER_ID,
            'vehicle_vin': 'VIN_OTHER_PERSON',
            'activity_type': 'loan',
            'start_date': '2026-08-24',
            'end_date': '2026-08-31',
        }
    ])
    result = _exclude(current_activity_df=activity)

    assert 'VIN_OTHER_PERSON' in result['available_vins']


def test_keep_vins_leaves_the_current_slot_car_in_the_list():
    scheduled = pd.DataFrame([
        {
            'person_id': PARTNER_ID,
            'vin': 'VIN_SCHEDULED',
            'status': 'manual',
            'start_day': '2026-08-24',
            'end_day': '2026-08-31',
        }
    ])
    result = _exclude(
        scheduled_assignments_df=scheduled,
        keep_vins={'VIN_SCHEDULED'},
    )

    assert 'VIN_SCHEDULED' in result['available_vins']


def test_empty_sources_leave_every_office_car_available():
    result = _exclude()

    assert result['excluded_vins'] == set()
    assert result['available_vehicle_count'] == len(OFFICE_VEHICLES)
