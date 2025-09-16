"""
Simplified solver API for UI testing.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any
import time
import asyncio

from ..services.database import get_database, DatabaseService

router = APIRouter(prefix="/solver", tags=["solver"])


@router.get("/generate_schedule")
async def generate_schedule_simple(
    office: str = Query(..., description="Office name"),
    week_start: str = Query(..., description="Week start date (YYYY-MM-DD)"),
    min_available_days: int = Query(5, description="Minimum available days"),
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """Simple schedule generation for UI testing."""

    try:
        # Simulate the 3-stage pipeline for now
        await asyncio.sleep(0.1)  # Simulate processing time

        # Mock data for UI testing
        return {
            'office': office,
            'week_start': week_start,
            'pipeline': {
                'total_duration': 25.8,
                'stage1': {
                    'duration': 25.0,
                    'candidate_count': 29568,
                    'unique_vins': 194,
                    'unique_partners': 153,
                    'unique_makes': 11
                },
                'stage2': {
                    'duration': 0.3,
                    'scored_count': 29568,
                    'score_min': 10,
                    'score_max': 105,
                    'rank_distribution': {
                        'A+': 1103,
                        'A': 3613,
                        'B': 8585,
                        'C': 2461
                    }
                },
                'stage3': {
                    'duration': 0.3,
                    'assignment_count': 15
                }
            },
            'assignments': [
                {
                    'vin': 'HASVW1D4',
                    'person_id': '14402',
                    'partner_name': 'John Smith',
                    'make': 'Volkswagen',
                    'model': 'ID.4',
                    'score': 105,
                    'rank': 'A+',
                    'rank_weight': 100,
                    'geo_bonus': 5,
                    'history_bonus': 0,
                    'tier_usage': '1',
                    'tier_cap': '100',
                    'flags': 'tier_ok|capacity_ok|cooldown_ok|availability_ok'
                },
                {
                    'vin': 'SC203839',
                    'person_id': '14402',
                    'partner_name': 'John Smith',
                    'make': 'Volkswagen',
                    'model': 'Atlas',
                    'score': 105,
                    'rank': 'A+',
                    'rank_weight': 100,
                    'geo_bonus': 5,
                    'history_bonus': 0,
                    'tier_usage': '2',
                    'tier_cap': '100',
                    'flags': 'tier_ok|capacity_ok|cooldown_ok|availability_ok'
                }
            ],
            'summary': {
                'unique_vins': 15,
                'unique_partners': 1,
                'unique_makes': 4
            },
            'constraint_analysis': {
                'tier_caps': 28500,
                'cooldown': 800,
                'geographic': 200,
                'capacity_limits': 53
            },
            'message': 'Successfully generated 15 weekly assignments'
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Schedule generation failed: {str(e)}")