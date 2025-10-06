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

        # 3. Get PLANNED loans from scheduled_assignments
        planned_query = db.client.table('scheduled_assignments')\
            .select('*')\
            .eq('office', office)\
            .eq('status', 'planned')\
            .gte('start_day', start_date)\
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

        # Past loans - check if actually completed or still active
        for loan in past_loans:
            loan_start = pd.to_datetime(loan.get('start_date')).date()
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

        # Planned loans
        for loan in planned_loans:
            activities.append({
                'vin': loan.get('vin'),
                'make': loan.get('make'),
                'model': loan.get('model'),
                'start_date': loan.get('start_day'),
                'end_date': loan.get('end_day'),
                'person_id': loan.get('person_id'),
                'partner_name': loan.get('partner_name'),
                'office': loan.get('office'),
                'status': 'planned',
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

        # Delete existing planned assignments for this week/office
        db.client.table('scheduled_assignments')\
            .delete()\
            .eq('office', request.office)\
            .eq('week_start', str(week_start))\
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
