"""
Vehicle booking conflict detection + FMS submission audit log.

Conflict detection answers one question: is this vehicle already booked
(current activity or scheduled assignment) during a proposed date range?
Used at chain-save time and again right before submitting to FMS, because
FMS activity changes daily and a slot that was free when planned may have
been taken since (this exact case burned us: a chain built in July was
rejected by FMS in September because a loan was booked in between).

Date overlap uses exclusive endpoints: a loan ending on day X does NOT
conflict with one starting on day X (back-to-back handoffs are normal).

Author: Ray Rierson
Date: 2026-07-14
"""

from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


def _fmt_date(value: Any) -> str:
    """Trim timestamps like '2026-09-15T00:00:00' down to '2026-09-15'."""
    return str(value)[:10] if value else "?"


def find_vehicle_conflicts(
    client,
    vin: str,
    start_day: str,
    end_day: str,
    exclude_assignment_id: Optional[int] = None,
) -> List[str]:
    """Return human-readable descriptions of bookings that overlap the range.

    Checks both current_activity (real FMS activity, synced nightly) and
    scheduled_assignments (this scheduler's own plans). Empty list = free.
    """
    conflicts: List[str] = []

    # Real FMS activity on this vehicle (loans, service, etc.)
    activity_result = client.table('current_activity') \
        .select('activity_type, to_field, start_date, end_date') \
        .eq('vehicle_vin', vin) \
        .lt('start_date', end_day) \
        .gt('end_date', start_day) \
        .execute()

    for activity in activity_result.data or []:
        conflicts.append(
            f"{activity.get('activity_type') or 'Activity'}: "
            f"{activity.get('to_field') or 'unknown'} "
            f"({_fmt_date(activity.get('start_date'))} to {_fmt_date(activity.get('end_date'))})"
        )

    # Other assignments already planned in this scheduler
    assignment_query = client.table('scheduled_assignments') \
        .select('assignment_id, partner_name, status, start_day, end_day') \
        .eq('vin', vin) \
        .in_('status', ['planned', 'manual', 'requested', 'active']) \
        .lt('start_day', end_day) \
        .gt('end_day', start_day)

    if exclude_assignment_id is not None:
        assignment_query = assignment_query.neq('assignment_id', exclude_assignment_id)

    for assignment in assignment_query.execute().data or []:
        conflicts.append(
            f"Scheduled assignment ({assignment.get('status')}): "
            f"{assignment.get('partner_name') or 'unknown'} "
            f"({assignment.get('start_day')} to {assignment.get('end_day')})"
        )

    return conflicts


def log_fms_submission(
    client,
    *,
    action: str,
    success: bool,
    assignment: Optional[Dict[str, Any]] = None,
    assignment_id: Optional[int] = None,
    requestor_fms_id: Optional[int] = None,
    requestor_email: Optional[str] = None,
    fms_request_id: Optional[int] = None,
    error_detail: Optional[str] = None,
) -> None:
    """Record an FMS submission attempt in fms_submission_log.

    Never raises: the audit trail must not break the submission flow.
    Render's log retention is short; this table is the durable record of
    who sent what to FMS and what happened.
    """
    assignment = assignment or {}
    try:
        client.table('fms_submission_log').insert({
            'assignment_id': assignment_id or assignment.get('assignment_id'),
            'vin': assignment.get('vin'),
            'partner_name': assignment.get('partner_name'),
            'person_id': assignment.get('person_id'),
            'start_day': assignment.get('start_day'),
            'end_day': assignment.get('end_day'),
            'office': assignment.get('office'),
            'action': action,
            'success': success,
            'requestor_fms_id': requestor_fms_id,
            'requestor_email': requestor_email,
            'fms_request_id': fms_request_id,
            'error_detail': error_detail,
        }).execute()
    except Exception as e:
        logger.warning(f"Could not write fms_submission_log entry: {e}")
