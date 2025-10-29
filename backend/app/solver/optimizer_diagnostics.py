"""
Optimizer Diagnostics - Explain why capacity isn't fully utilized.

Provides detailed analysis of:
- Feasibility funnel (how many triples at each stage)
- Constraint bottlenecks (which constraints are blocking assignments)
- Daily capacity utilization breakdown
- Actionable recommendations
"""

import pandas as pd
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta


def build_diagnostics(
    office_triples: pd.DataFrame,
    selected_assignments: List[Dict],
    capacity_map: Dict,
    week_start: str,
    vehicles_df: pd.DataFrame,
    partners_df: pd.DataFrame,
    max_per_partner_per_day: int,
    max_per_partner_per_week: int,
    lambda_fair: int,
    existing_count_by_day: Dict = None,
    active_count_by_partner_day: Dict = None,
    active_vehicles_per_partner: Dict = None,
    verbose: bool = False,
    total_vehicles_raw: int = None,
    total_partners_raw: int = None,
    filtering_stats: Dict = None
) -> Dict[str, Any]:
    """
    Build comprehensive diagnostics explaining optimizer decisions.

    Args:
        office_triples: All feasible triples input to optimizer
        selected_assignments: Assignments chosen by optimizer
        capacity_map: Daily capacity limits
        week_start: Start date of week
        vehicles_df: All vehicles for this office
        partners_df: All partners for this office
        max_per_partner_per_day: Partner-day constraint
        max_per_partner_per_week: Partner-week constraint
        lambda_fair: Fairness penalty weight
        existing_count_by_day: Existing loans per day
        active_count_by_partner_day: Active loans per (partner, day)
        active_vehicles_per_partner: Active vehicles per partner
        verbose: Print diagnostic details

    Returns:
        Dict with diagnostic information
    """
    if existing_count_by_day is None:
        existing_count_by_day = {}
    if active_count_by_partner_day is None:
        active_count_by_partner_day = {}
    if active_vehicles_per_partner is None:
        active_vehicles_per_partner = {}

    week_start_date = pd.to_datetime(week_start).date()

    # Build daily diagnostics
    daily_diagnostics = []

    for day_offset in range(5):  # Mon-Fri
        start_day = week_start_date + timedelta(days=day_offset)
        start_day_str = start_day.strftime('%Y-%m-%d')
        day_name = start_day.strftime('%a %d')

        # Get capacity for this day
        total_capacity = capacity_map.get(start_day, 0)
        existing_count = existing_count_by_day.get(start_day, 0)
        available_capacity = max(0, total_capacity - existing_count)

        # Count triples and assignments for this start day
        day_triples = office_triples[office_triples['start_day'] == start_day_str]
        day_assignments = [a for a in selected_assignments if a['start_day'] == start_day_str]

        # Analyze why capacity not filled
        bottlenecks = _analyze_day_bottlenecks(
            day_triples=day_triples,
            day_assignments=day_assignments,
            available_capacity=available_capacity,
            start_day=start_day,
            vehicles_df=vehicles_df,
            partners_df=partners_df,
            max_per_partner_per_day=max_per_partner_per_day,
            active_count_by_partner_day=active_count_by_partner_day
        )

        # Calculate utilization
        assigned_count = len(day_assignments)
        utilization = (assigned_count / available_capacity * 100) if available_capacity > 0 else 0
        empty_slots = available_capacity - assigned_count

        daily_diagnostics.append({
            'day': day_name,
            'date': start_day_str,
            'total_capacity': total_capacity,
            'existing_count': existing_count,
            'available_capacity': available_capacity,
            'assigned': assigned_count,
            'empty_slots': empty_slots,
            'utilization_pct': round(utilization, 1),
            'feasible_triples': len(day_triples),
            'unique_vehicles': day_triples['vin'].nunique() if not day_triples.empty else 0,
            'unique_partners': day_triples['person_id'].nunique() if not day_triples.empty else 0,
            'bottlenecks': bottlenecks
        })

    # Identify primary bottlenecks across the week
    primary_bottlenecks = _identify_primary_bottlenecks(
        daily_diagnostics=daily_diagnostics,
        office_triples=office_triples,
        selected_assignments=selected_assignments,
        max_per_partner_per_day=max_per_partner_per_day,
        max_per_partner_per_week=max_per_partner_per_week,
        lambda_fair=lambda_fair,
        active_vehicles_per_partner=active_vehicles_per_partner
    )

    # Generate recommendations
    recommendations = _generate_recommendations(
        daily_diagnostics=daily_diagnostics,
        primary_bottlenecks=primary_bottlenecks,
        max_per_partner_per_day=max_per_partner_per_day,
        max_per_partner_per_week=max_per_partner_per_week,
        lambda_fair=lambda_fair
    )

    # Overall summary
    total_capacity = sum(d['available_capacity'] for d in daily_diagnostics)
    total_assigned = sum(d['assigned'] for d in daily_diagnostics)
    total_empty = total_capacity - total_assigned
    overall_utilization = (total_assigned / total_capacity * 100) if total_capacity > 0 else 0

    # Count vehicles/partners in feasible triples (after filtering)
    total_vehicles_feasible = office_triples['vin'].nunique() if not office_triples.empty else 0
    total_partners_feasible = office_triples['person_id'].nunique() if not office_triples.empty else 0

    # Use raw counts if provided, otherwise fall back to feasible counts
    total_vehicles_raw_display = total_vehicles_raw if total_vehicles_raw is not None else total_vehicles_feasible
    total_partners_raw_display = total_partners_raw if total_partners_raw is not None else total_partners_feasible

    # Calculate theoretical maximum assignments given constraints
    # Use RAW counts for theoretical max (what we COULD do if filtering wasn't an issue)
    theoretical_max_weekly = total_vehicles_raw_display  # Each vehicle can only be used once per week (VIN uniqueness)
    if max_per_partner_per_week > 0:
        partner_week_max = total_partners_raw_display * max_per_partner_per_week
        theoretical_max_weekly = min(theoretical_max_weekly, partner_week_max)

    # Calculate if we're resource-constrained
    resource_ratio = theoretical_max_weekly / total_capacity if total_capacity > 0 else 0
    resource_constrained = resource_ratio < 1.1  # Within 10% of theoretical max

    # Build detailed filtering breakdown
    filtering_breakdown = []
    if filtering_stats:
        if filtering_stats.get('vehicles_unavailable', 0) > 0:
            filtering_breakdown.append({
                'reason': 'Not available for 8 consecutive days',
                'count': filtering_stats['vehicles_unavailable'],
                'type': 'vehicles',
                'explanation': 'Vehicle is already on loan or not available for the full 8-day period'
            })
        if filtering_stats.get('partners_cooldown', 0) > 0:
            filtering_breakdown.append({
                'reason': '30-day cooldown period',
                'count': filtering_stats['partners_cooldown'],
                'type': 'partners',
                'explanation': 'Partner recently had a loan for this make within the last 30 days'
            })
        if filtering_stats.get('partners_no_approval', 0) > 0:
            filtering_breakdown.append({
                'reason': 'Not approved for available makes',
                'count': filtering_stats['partners_no_approval'],
                'type': 'partners',
                'explanation': 'Partner not approved for any of the vehicle makes available this week'
            })
        if filtering_stats.get('vehicles_committed', 0) > 0:
            filtering_breakdown.append({
                'reason': 'Already committed to partner',
                'count': filtering_stats['vehicles_committed'],
                'type': 'vehicles',
                'explanation': 'Vehicle manually assigned via Chain Builder'
            })

    # Build constraint note
    constraint_parts = []
    if total_vehicles_raw_display != total_vehicles_feasible or total_partners_raw_display != total_partners_feasible:
        constraint_parts.append(f'{total_vehicles_raw_display} total vehicles → {total_vehicles_feasible} available after filtering')
        constraint_parts.append(f'{total_partners_raw_display} total partners → {total_partners_feasible} eligible')
    else:
        constraint_parts.append(f'{total_vehicles_raw_display} vehicles available')
        constraint_parts.append(f'{total_partners_raw_display} partners eligible')

    constraint_parts.append(f'Max {max_per_partner_per_week} vehicle(s) per partner per week')
    constraint_parts.append(f'Theoretical maximum: ~{theoretical_max_weekly} assignments vs {total_capacity} slots needed')

    if resource_constrained:
        constraint_parts.append('⚠️ Resources are TIGHT - increasing partner limits or vehicle availability would help')
    else:
        constraint_parts.append('✓ Resources sufficient - look for constraint bottlenecks (partner-day limits, cooldown, etc.)')

    return {
        'summary': {
            'total_capacity': total_capacity,
            'total_assigned': total_assigned,
            'total_empty': total_empty,
            'utilization_pct': round(overall_utilization, 1),
            'total_feasible_triples': len(office_triples),
            'total_vehicles_raw': total_vehicles_raw_display,
            'total_partners_raw': total_partners_raw_display,
            'total_vehicles_available': total_vehicles_feasible,
            'total_partners_eligible': total_partners_feasible,
            'vehicles_filtered': total_vehicles_raw_display - total_vehicles_feasible if total_vehicles_raw is not None else 0,
            'partners_filtered': total_partners_raw_display - total_partners_feasible if total_partners_raw is not None else 0,
            'theoretical_max_weekly': theoretical_max_weekly,
            'resource_constrained': resource_constrained,
            'resource_constraint_note': ' • '.join(constraint_parts) if total_capacity > 0 else None,
            'filtering_breakdown': filtering_breakdown
        },
        'daily_diagnostics': daily_diagnostics,
        'primary_bottlenecks': primary_bottlenecks,
        'recommendations': recommendations
    }


def _analyze_day_bottlenecks(
    day_triples: pd.DataFrame,
    day_assignments: List[Dict],
    available_capacity: int,
    start_day,
    vehicles_df: pd.DataFrame,
    partners_df: pd.DataFrame,
    max_per_partner_per_day: int,
    active_count_by_partner_day: Dict
) -> List[Dict[str, Any]]:
    """Analyze why a specific day isn't fully utilized."""
    bottlenecks = []

    if available_capacity == 0:
        bottlenecks.append({
            'type': 'no_capacity',
            'severity': 'info',
            'description': 'No capacity available (fully booked or blackout)',
            'impact': 0
        })
        return bottlenecks

    empty_slots = available_capacity - len(day_assignments)

    if empty_slots == 0:
        bottlenecks.append({
            'type': 'fully_utilized',
            'severity': 'success',
            'description': 'All available capacity utilized',
            'impact': 0
        })
        return bottlenecks

    # Check if we have enough feasible triples
    if len(day_triples) == 0:
        bottlenecks.append({
            'type': 'no_feasible_triples',
            'severity': 'critical',
            'description': 'No feasible vehicle-partner combinations for this day',
            'impact': empty_slots,
            'suggestion': 'Check vehicle availability and partner eligibility'
        })
        return bottlenecks

    if len(day_triples) < available_capacity:
        bottlenecks.append({
            'type': 'insufficient_triples',
            'severity': 'critical',
            'description': f'Only {len(day_triples)} feasible triples, need {available_capacity}',
            'impact': available_capacity - len(day_triples),
            'suggestion': 'Increase vehicle availability or partner eligibility'
        })

    # Check vehicle availability
    unique_vehicles = day_triples['vin'].nunique()
    if unique_vehicles < available_capacity:
        bottlenecks.append({
            'type': 'vehicle_shortage',
            'severity': 'high',
            'description': f'Only {unique_vehicles} vehicles available for this start day',
            'impact': min(empty_slots, available_capacity - unique_vehicles),
            'suggestion': 'Review vehicle availability requirements (min_available_days)'
        })

    # Check partner availability
    unique_partners = day_triples['person_id'].nunique()
    if max_per_partner_per_day > 0:
        max_possible_with_partners = unique_partners * max_per_partner_per_day
        if max_possible_with_partners < available_capacity:
            # Account for partners already at capacity
            available_partners = 0
            for partner_id in day_triples['person_id'].unique():
                existing = active_count_by_partner_day.get((partner_id, start_day), 0)
                slots_left = max_per_partner_per_day - existing
                if slots_left > 0:
                    available_partners += 1

            if available_partners * max_per_partner_per_day < available_capacity:
                bottlenecks.append({
                    'type': 'partner_day_limit',
                    'severity': 'high',
                    'description': f'Partner-day limit: {available_partners} partners × {max_per_partner_per_day} slots = {available_partners * max_per_partner_per_day} max',
                    'impact': min(empty_slots, available_capacity - (available_partners * max_per_partner_per_day)),
                    'suggestion': f'Increase max_per_partner_per_day to 2 (could add ~{available_partners} slots)'
                })

    # Check if optimizer chose not to fill (optimization decision)
    # BUT - be smarter about this. If we're close to the partner-day limit, it's not really an "optimizer decision"
    if len(day_triples) >= available_capacity and empty_slots > 0:
        # Calculate theoretical max given partner-day limits
        if max_per_partner_per_day > 0:
            theoretical_max = unique_partners * max_per_partner_per_day
            # Only call it "optimizer decision" if we have plenty of partners available
            if theoretical_max >= available_capacity * 1.5:  # 50% buffer
                bottlenecks.append({
                    'type': 'optimizer_decision',
                    'severity': 'medium',
                    'description': f'Optimizer chose not to fill {empty_slots} slots (optimizing for score/fairness)',
                    'impact': empty_slots,
                    'suggestion': 'Reduce fairness penalty or adjust scoring weights'
                })
            else:
                # The real issue is partner availability, not optimizer choice
                bottlenecks.append({
                    'type': 'partner_availability_limit',
                    'severity': 'high',
                    'description': f'Limited by partner-day constraint: {unique_partners} partners × {max_per_partner_per_day} slot(s) = {theoretical_max} theoretical max',
                    'impact': empty_slots,
                    'suggestion': f'Increase max_per_partner_per_day to 2 (would enable {unique_partners * 2} possible assignments)'
                })
        else:
            bottlenecks.append({
                'type': 'optimizer_decision',
                'severity': 'medium',
                'description': f'Optimizer chose not to fill {empty_slots} slots (optimizing for score/fairness)',
                'impact': empty_slots,
                'suggestion': 'Reduce fairness penalty or adjust scoring weights'
            })

    return bottlenecks


def _identify_primary_bottlenecks(
    daily_diagnostics: List[Dict],
    office_triples: pd.DataFrame,
    selected_assignments: List[Dict],
    max_per_partner_per_day: int,
    max_per_partner_per_week: int,
    lambda_fair: int,
    active_vehicles_per_partner: Dict
) -> List[Dict[str, Any]]:
    """Identify the top bottlenecks preventing full capacity utilization."""
    bottleneck_counts = {}
    total_impact = {}

    # Aggregate bottlenecks across all days
    for day_diag in daily_diagnostics:
        for bottleneck in day_diag['bottlenecks']:
            btype = bottleneck['type']
            bottleneck_counts[btype] = bottleneck_counts.get(btype, 0) + 1
            total_impact[btype] = total_impact.get(btype, 0) + bottleneck.get('impact', 0)

    # Sort by total impact
    sorted_bottlenecks = sorted(
        bottleneck_counts.keys(),
        key=lambda k: total_impact.get(k, 0),
        reverse=True
    )

    primary = []
    for btype in sorted_bottlenecks[:3]:  # Top 3
        # Get example from daily diagnostics
        example = None
        for day_diag in daily_diagnostics:
            for b in day_diag['bottlenecks']:
                if b['type'] == btype:
                    example = b
                    break
            if example:
                break

        if example:
            primary.append({
                'type': btype,
                'severity': example['severity'],
                'description': example['description'],
                'total_impact': total_impact[btype],
                'affected_days': bottleneck_counts[btype],
                'suggestion': example.get('suggestion', '')
            })

    return primary


def _generate_recommendations(
    daily_diagnostics: List[Dict],
    primary_bottlenecks: List[Dict],
    max_per_partner_per_day: int,
    max_per_partner_per_week: int,
    lambda_fair: int
) -> List[Dict[str, Any]]:
    """Generate actionable recommendations to improve capacity utilization."""
    recommendations = []

    # Calculate total empty slots
    total_empty = sum(d['empty_slots'] for d in daily_diagnostics)

    if total_empty == 0:
        recommendations.append({
            'priority': 'success',
            'action': 'No action needed',
            'description': 'All available capacity is being utilized',
            'estimated_impact': 0
        })
        return recommendations

    # Check for partner-day limit bottleneck
    partner_day_bottleneck = next(
        (b for b in primary_bottlenecks if b['type'] == 'partner_day_limit'),
        None
    )
    if partner_day_bottleneck and max_per_partner_per_day == 1:
        recommendations.append({
            'priority': 'high',
            'action': 'Increase Partner-Day Limit',
            'description': f'Change max vehicles per partner per day from 1 to 2',
            'estimated_impact': f'Could add ~{partner_day_bottleneck["total_impact"]} assignments',
            'implementation': 'Adjust "Max Vehicles per Media Partner per Day" setting to 2'
        })

    # Check for vehicle shortage
    vehicle_bottleneck = next(
        (b for b in primary_bottlenecks if b['type'] == 'vehicle_shortage'),
        None
    )
    if vehicle_bottleneck:
        recommendations.append({
            'priority': 'high',
            'action': 'Review Vehicle Availability Requirements',
            'description': 'Some days have insufficient vehicles available',
            'estimated_impact': f'Could add ~{vehicle_bottleneck["total_impact"]} assignments',
            'implementation': 'Check min_available_days setting (should be 8 for 8-day loans)'
        })

    # Check for fairness optimization
    optimizer_bottleneck = next(
        (b for b in primary_bottlenecks if b['type'] == 'optimizer_decision'),
        None
    )
    if optimizer_bottleneck:
        recommendations.append({
            'priority': 'medium',
            'action': 'Adjust Fairness Settings',
            'description': f'Optimizer prioritizing distribution over capacity (penalty: {lambda_fair})',
            'estimated_impact': f'Could add ~{optimizer_bottleneck["total_impact"]} assignments',
            'implementation': 'Reduce fairness penalty or increase partner limits'
        })

    # Check for insufficient triples
    triples_bottleneck = next(
        (b for b in primary_bottlenecks if b['type'] == 'insufficient_triples'),
        None
    )
    if triples_bottleneck:
        recommendations.append({
            'priority': 'high',
            'action': 'Recruit More Partners',
            'description': 'Not enough eligible vehicle-partner combinations',
            'estimated_impact': f'Need ~{triples_bottleneck["total_impact"]} more partner-vehicle matches',
            'implementation': 'Recruit partners for underserved makes or expand approval ranks'
        })

    return recommendations
