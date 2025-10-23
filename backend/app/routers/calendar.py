"""
Calendar view endpoints for visualizing vehicle activity timeline
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import pandas as pd
from datetime import datetime, timedelta
import uuid

from ..services.database import DatabaseService

router = APIRouter(prefix="/api/calendar", tags=["Calendar"])


@router.get("/vehicles")
async def get_all_vehicles(office: str = Query(..., description="Office name")) -> Dict[str, Any]:
    """Get all vehicles for an office (full inventory) with lifecycle dates"""
    db = DatabaseService()
    await db.initialize()

    try:
        response = db.client.table('vehicles')\
            .select('vin, make, model, office, in_service_date, expected_turn_in_date')\
            .eq('office', office)\
            .execute()

        return {
            'office': office,
            'vehicles': response.data if response.data else [],
            'count': len(response.data) if response.data else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await db.close()


@router.get("/partner-tiers")
async def get_partner_tiers(office: str = Query(..., description="Office name")) -> Dict[str, Any]:
    """Get tier rankings for all partners in an office"""
    db = DatabaseService()
    await db.initialize()

    try:
        # Get all partners for this office
        partners_response = db.client.table('media_partners')\
            .select('person_id')\
            .eq('office', office)\
            .execute()

        partner_ids = [int(p['person_id']) for p in partners_response.data] if partners_response.data else []

        # Get approved makes for these partners
        approved_response = db.client.table('approved_makes')\
            .select('person_id, make, rank')\
            .in_('person_id', partner_ids)\
            .execute()

        # Build tier map
        tier_map = {}
        if approved_response.data:
            for row in approved_response.data:
                pid = int(row['person_id'])
                if pid not in tier_map:
                    tier_map[pid] = {}
                tier_map[pid][row['make']] = row['rank']

        return {
            'office': office,
            'tiers': tier_map
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await db.close()


@router.get("/media-partners")
async def get_all_media_partners(office: str = Query(..., description="Office name")) -> Dict[str, Any]:
    """Get all media partners for an office (full inventory) with distances"""
    db = DatabaseService()
    await db.initialize()

    try:
        # Get all partners for this office
        partners_response = db.client.table('media_partners')\
            .select('person_id, name, office, address, latitude, longitude')\
            .eq('office', office)\
            .execute()

        partners = partners_response.data if partners_response.data else []

        # Get office coordinates
        office_response = db.client.table('offices')\
            .select('latitude, longitude')\
            .eq('name', office)\
            .execute()

        if not office_response.data or not office_response.data[0].get('latitude'):
            # Return without distances if office coordinates not found
            for partner in partners:
                if 'person_id' in partner:
                    partner['person_id'] = int(partner['person_id'])
            return {
                'office': office,
                'partners': partners,
                'count': len(partners)
            }

        office_lat = office_response.data[0]['latitude']
        office_lon = office_response.data[0]['longitude']

        # Calculate distances for all partners
        for partner in partners:
            partner['person_id'] = int(partner['person_id'])

            partner_lat = partner.get('latitude')
            partner_lon = partner.get('longitude')

            if partner_lat and partner_lon:
                # Calculate distance using Haversine formula
                from math import radians, sin, cos, sqrt, atan2
                R = 3959  # Earth's radius in miles

                lat1, lon1 = radians(office_lat), radians(office_lon)
                lat2, lon2 = radians(partner_lat), radians(partner_lon)

                dlat = lat2 - lat1
                dlon = lon2 - lon1

                a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                c = 2 * atan2(sqrt(a), sqrt(1-a))
                distance_miles = round(R * c, 1)

                partner['distance_miles'] = distance_miles
                partner['location_type'] = 'local' if distance_miles <= 50 else 'remote'
            else:
                partner['distance_miles'] = None
                partner['location_type'] = None

        return {
            'office': office,
            'partners': partners,
            'count': len(partners)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await db.close()


class SaveScheduleRequest(BaseModel):
    office: str
    week_start: str
    assignments: List[Dict[str, Any]]


@router.get("/activity")
async def get_calendar_activity(
    office: str = Query(..., description="Office name"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    vin: Optional[str] = Query(None, description="Filter by VIN"),
    make: Optional[str] = Query(None, description="Filter by make"),
    person_id: Optional[int] = Query(None, description="Filter by partner ID")
) -> Dict[str, Any]:
    """
    Get all vehicle activity for calendar view.

    Returns combined data from:
    - loan_history (past completed loans)
    - current_activity (active loans)
    - scheduled_assignments (planned future loans)
    """

    db = DatabaseService()
    await db.initialize()

    try:
        start = pd.to_datetime(start_date).date()
        end = pd.to_datetime(end_date).date()
        today = datetime.now().date()

        # 1. Get PAST loans from loan_history
        past_query = db.client.table('loan_history')\
            .select('*')\
            .eq('office', office)\
            .gte('end_date', start_date)\
            .lt('end_date', str(today))

        if vin:
            past_query = past_query.eq('vin', vin)
        if make:
            past_query = past_query.eq('make', make)
        if person_id:
            past_query = past_query.eq('person_id', person_id)

        past_response = past_query.execute()
        past_loans = past_response.data if past_response.data else []

        # 2. Get ACTIVE loans from current_activity (with vehicle info)
        # First get vehicles for the office
        vehicles_response = db.client.table('vehicles')\
            .select('*')\
            .eq('office', office)\
            .execute()
        vehicles_df = pd.DataFrame(vehicles_response.data) if vehicles_response.data else pd.DataFrame()

        if not vehicles_df.empty:
            vins_in_office = vehicles_df['vin'].tolist()

            active_query = db.client.table('current_activity')\
                .select('*')\
                .in_('vehicle_vin', vins_in_office)\
                .lte('start_date', end_date)

            if vin:
                active_query = active_query.eq('vehicle_vin', vin)
            if person_id:
                active_query = active_query.eq('person_id', person_id)

            active_response = active_query.execute()
            active_data = active_response.data if active_response.data else []

            # Join with vehicles to get make/model
            active_df = pd.DataFrame(active_data) if active_data else pd.DataFrame()
            if not active_df.empty and not vehicles_df.empty:
                active_df = active_df.merge(
                    vehicles_df[['vin', 'make', 'model', 'office']],
                    left_on='vehicle_vin',
                    right_on='vin',
                    how='left'
                )

                # Filter by make if specified
                if make:
                    active_df = active_df[active_df['make'] == make]

                active_loans = active_df.to_dict('records')
            else:
                active_loans = []
        else:
            active_loans = []

        # 3. Get PLANNED/PROPOSED loans from scheduled_assignments
        # Include 'planned' (optimizer), 'manual' (chain builder), and 'requested' (sent to FMS)
        # Use overlap logic: show if end_day >= start_date AND start_day <= end_date
        planned_query = db.client.table('scheduled_assignments')\
            .select('*')\
            .eq('office', office)\
            .in_('status', ['planned', 'manual', 'requested'])\
            .gte('end_day', start_date)\
            .lte('start_day', end_date)

        if vin:
            planned_query = planned_query.eq('vin', vin)
        if make:
            planned_query = planned_query.eq('make', make)
        if person_id:
            planned_query = planned_query.eq('person_id', person_id)

        planned_response = planned_query.execute()
        planned_loans = planned_response.data if planned_response.data else []

        # 4. Format responses
        activities = []

        # Build a set of (vin, start_date) from active loans to avoid duplicates
        active_loan_keys = set()
        for loan in active_loans:
            vin = loan.get('vehicle_vin') or loan.get('vin')
            start = loan.get('start_date')
            if vin and start:
                active_loan_keys.add((vin, start))

        # Past loans - check if actually completed or still active
        for loan in past_loans:
            vin = loan.get('vin')
            start_date = loan.get('start_date')

            # Skip if this loan is already in active_loans (avoid duplicates)
            if (vin, start_date) in active_loan_keys:
                continue

            loan_start = pd.to_datetime(start_date).date()
            loan_end = pd.to_datetime(loan.get('end_date')).date()

            # If loan is currently happening (today is between start and end), it's active
            if loan_start <= today <= loan_end:
                status = 'active'
            else:
                status = 'completed'

            activities.append({
                'vin': loan.get('vin'),
                'make': loan.get('make'),
                'model': loan.get('model'),
                'start_date': loan.get('start_date'),
                'end_date': loan.get('end_date'),
                'person_id': loan.get('person_id'),
                'partner_name': loan.get('name'),
                'partner_address': loan.get('partner_address'),
                'region': loan.get('region'),
                'office': loan.get('office'),
                'status': status,
                'activity_type': 'Media Loan',
                'published': loan.get('clips_received') == '1.0'
            })

        # Active loans
        for loan in active_loans:
            activities.append({
                'vin': loan.get('vehicle_vin') or loan.get('vin'),
                'make': loan.get('make'),
                'model': loan.get('model'),
                'start_date': loan.get('start_date'),
                'end_date': loan.get('end_date'),
                'person_id': loan.get('person_id'),
                'partner_name': loan.get('to_field'),
                'partner_address': loan.get('partner_address'),
                'region': loan.get('region'),
                'office': loan.get('office'),
                'status': 'active',
                'activity_type': loan.get('activity_type', 'Loan'),
                'published': False
            })

        # Planned loans - only include if they don't conflict with active/past
        # Build a set of (vin, date_range) tuples for existing activities
        existing_activities = set()
        for activity in activities:
            vin = activity['vin']
            start = pd.to_datetime(activity['start_date']).date()
            end = pd.to_datetime(activity['end_date']).date()
            # Add all dates in the range
            current_date = start
            while current_date <= end:
                existing_activities.add((vin, current_date))
                current_date += timedelta(days=1)

        for loan in planned_loans:
            vin = loan.get('vin')
            start = pd.to_datetime(loan.get('start_day')).date()
            end = pd.to_datetime(loan.get('end_day')).date()

            # Check if this planned activity conflicts with existing activities
            has_conflict = False
            current_date = start
            while current_date <= end:
                if (vin, current_date) in existing_activities:
                    has_conflict = True
                    break
                current_date += timedelta(days=1)

            # Only add if no conflict
            if not has_conflict:
                activities.append({
                    'assignment_id': loan.get('assignment_id'),  # CRITICAL for status changes and delete
                    'vin': loan.get('vin'),
                    'make': loan.get('make'),
                    'model': loan.get('model'),
                    'start_date': loan.get('start_day'),
                    'end_date': loan.get('end_day'),
                    'person_id': loan.get('person_id'),
                    'partner_name': loan.get('partner_name'),
                    'office': loan.get('office'),
                    'status': loan.get('status', 'planned'),  # Use actual status from DB (planned/manual/requested)
                    'activity_type': 'Planned Loan',
                    'optimizer_run_id': loan.get('optimizer_run_id'),
                    'score': loan.get('score'),
                    'published': False
                })

        # Sort by VIN then start date
        activities.sort(key=lambda x: (x['vin'], x['start_date']))

        return {
            'office': office,
            'start_date': start_date,
            'end_date': end_date,
            'activities': activities,
            'counts': {
                'past': len(past_loans),
                'active': len(active_loans),
                'planned': len(planned_loans),
                'total': len(activities)
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await db.close()


@router.post("/save-schedule")
async def save_schedule(request: SaveScheduleRequest) -> Dict[str, Any]:
    """
    Save optimizer results to scheduled_assignments table.
    Replaces any existing planned assignments for this week/office.
    """

    db = DatabaseService()
    await db.initialize()

    try:
        # Generate optimizer run ID
        run_id = str(uuid.uuid4())
        week_start = pd.to_datetime(request.week_start).date()

        # Delete ALL existing planned assignments for this office (not just this week)
        # This prevents clutter from old optimizer runs
        # Manual picks (status='manual') are preserved
        db.client.table('scheduled_assignments')\
            .delete()\
            .eq('office', request.office)\
            .eq('status', 'planned')\
            .execute()

        # Insert new assignments
        assignments_to_insert = []
        for assignment in request.assignments:
            start_day = pd.to_datetime(assignment['start_day']).date()
            end_day = start_day + timedelta(days=7)

            assignments_to_insert.append({
                'vin': assignment['vin'],
                'person_id': assignment['person_id'],
                'start_day': str(start_day),
                'end_day': str(end_day),
                'make': assignment['make'],
                'model': assignment.get('model', ''),
                'office': request.office,
                'partner_name': assignment.get('partner_name', ''),
                'score': assignment.get('score', 0),
                'optimizer_run_id': run_id,
                'week_start': str(week_start),
                'status': 'planned'
            })

        if assignments_to_insert:
            db.client.table('scheduled_assignments').insert(assignments_to_insert).execute()

        return {
            'success': True,
            'optimizer_run_id': run_id,
            'assignments_saved': len(assignments_to_insert),
            'week_start': str(week_start),
            'office': request.office
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await db.close()


class ScheduleAssignmentRequest(BaseModel):
    vin: str
    person_id: int
    start_day: str
    office: str
    week_start: str
    partner_name: str = ""
    make: str = ""
    model: str = ""


@router.post("/schedule-assignment")
async def schedule_manual_assignment(request: ScheduleAssignmentRequest) -> Dict[str, Any]:
    """
    Manually schedule a vehicle assignment to a partner.
    
    Saves to scheduled_assignments table with status='manual' to distinguish
    from optimizer-generated assignments.
    """
    db = DatabaseService()
    await db.initialize()

    try:
        start_day = pd.to_datetime(request.start_day).date()
        end_day = start_day + timedelta(days=7)
        week_start = pd.to_datetime(request.week_start).date()

        # Get vehicle and partner info if not provided
        if not request.make or not request.model:
            vehicle_response = db.client.table('vehicles')\
                .select('make, model')\
                .eq('vin', request.vin)\
                .execute()
            
            if vehicle_response.data:
                request.make = vehicle_response.data[0].get('make', '')
                request.model = vehicle_response.data[0].get('model', '')

        if not request.partner_name:
            partner_response = db.client.table('media_partners')\
                .select('name')\
                .eq('person_id', request.person_id)\
                .execute()
            
            if partner_response.data:
                request.partner_name = partner_response.data[0].get('name', '')

        # Check if this assignment already exists
        existing_response = db.client.table('scheduled_assignments')\
            .select('*')\
            .eq('vin', request.vin)\
            .eq('person_id', request.person_id)\
            .eq('start_day', str(start_day))\
            .eq('office', request.office)\
            .execute()

        if existing_response.data:
            return {
                'success': False,
                'message': 'This assignment already exists'
            }

        # Insert new assignment
        assignment = {
            'vin': request.vin,
            'person_id': request.person_id,
            'start_day': str(start_day),
            'end_day': str(end_day),
            'make': request.make,
            'model': request.model,
            'office': request.office,
            'partner_name': request.partner_name,
            'score': 0,  # Manual assignments don't have optimizer scores
            'optimizer_run_id': None,
            'week_start': str(week_start),
            'status': 'manual'  # Mark as manually created
        }

        db.client.table('scheduled_assignments').insert(assignment).execute()

        return {
            'success': True,
            'message': 'Assignment scheduled successfully',
            'assignment': assignment
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await db.close()

@router.patch("/change-assignment-status/{assignment_id}")
async def change_assignment_status(
    assignment_id: int,
    new_status: str = Query(..., description="New status: 'planned', 'manual', 'requested'")
) -> Dict[str, Any]:
    """
    Change the status of a scheduled assignment.

    Workflow:
    - 'planned' (green) → 'requested' (magenta) when sent to FMS
    - 'manual' (green dashed) → 'requested' (magenta) when sent to FMS
    - Cannot change to 'active' (that comes from current_activity sync)
    """
    db = DatabaseService()
    await db.initialize()

    try:
        # Validate status
        allowed_statuses = ['planned', 'manual', 'requested']
        if new_status not in allowed_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Allowed: {allowed_statuses}"
            )

        # Update the assignment
        result = db.client.table('scheduled_assignments')\
            .update({'status': new_status})\
            .eq('assignment_id', assignment_id)\
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail=f"Assignment {assignment_id} not found")

        return {
            'success': True,
            'message': f'Assignment {assignment_id} status changed to {new_status}',
            'assignment_id': assignment_id,
            'new_status': new_status
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await db.close()


@router.delete("/delete-assignment/{assignment_id}")
async def delete_assignment(assignment_id: int) -> Dict[str, Any]:
    """
    Delete a scheduled assignment (green or magenta bars).
    Cannot delete blue bars (current_activity - those are managed in FMS).
    """
    db = DatabaseService()
    await db.initialize()

    try:
        # First check if assignment exists and is manual
        check_response = db.client.table('scheduled_assignments')\
            .select('*')\
            .eq('assignment_id', assignment_id)\
            .execute()

        if not check_response.data:
            return {
                'success': False,
                'message': 'Assignment not found'
            }

        assignment = check_response.data[0]

        # Allow deletion of green (planned/manual) and magenta (requested) assignments
        # Do NOT allow deletion of blue (active) - those are in FMS
        allowed_delete_statuses = ['manual', 'planned', 'requested']
        if assignment.get('status') not in allowed_delete_statuses:
            return {
                'success': False,
                'message': f'Can only delete scheduled assignments (green/magenta bars), not active assignments (blue bars from FMS)'
            }

        # Delete the assignment
        db.client.table('scheduled_assignments')\
            .delete()\
            .eq('assignment_id', assignment_id)\
            .execute()

        return {
            'success': True,
            'message': 'Assignment deleted successfully'
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await db.close()
