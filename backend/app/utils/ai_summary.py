"""
Factual summary generation for optimizer results using actual constraint data.
"""

from typing import Dict, Any


def generate_optimizer_summary(solver_result: Dict[str, Any], request_params: Dict[str, Any]) -> str:
    """
    Generate a factual explanation of optimizer results based on actual constraints.

    Args:
        solver_result: Simplified solver result with key metrics
        request_params: The optimization request parameters

    Returns:
        A factual summary explaining the results
    """
    # Extract data
    assignments_count = solver_result.get('assignments_created', 0)
    total_capacity = solver_result.get('total_capacity', 0)
    capacity_by_day = solver_result.get('capacity_by_day', {})
    max_per_week = solver_result.get('max_per_partner_week', 1)
    partners_used = solver_result.get('partners_used', 0)
    office = solver_result.get('office', 'Unknown')

    # Get constraint data if available
    total_partners = solver_result.get('total_partners', 'unknown')
    blocked_partners = solver_result.get('blocked_partners', 'unknown')
    available_partners = solver_result.get('available_partners', 'unknown')

    fill_rate = (assignments_count/total_capacity*100) if total_capacity > 0 else 0

    # Build summary
    lines = []

    # Header with key numbers
    lines.append(f"**Results: {assignments_count} of {total_capacity} slots filled ({fill_rate:.0f}%)**")
    lines.append("")

    # Constraint analysis
    if available_partners != 'unknown':
        theoretical_max = available_partners * max_per_week
        lines.append(f"**Partner Constraint:**")
        lines.append(f"• {available_partners} partners available (out of {total_partners} total)")
        lines.append(f"• {blocked_partners} partners blocked (already have active loans this week)")
        lines.append(f"• Max {max_per_week} vehicle per partner per week")
        lines.append(f"• Theoretical maximum: {theoretical_max} assignments")
        lines.append("")

        if assignments_count < theoretical_max:
            gap = theoretical_max - assignments_count
            lines.append(f"**Gap Analysis:** {gap} assignments below theoretical max due to additional constraints (tier caps, fairness penalties, budget limits, cooldown filters).")
            lines.append("")

    # Day-by-day breakdown
    if capacity_by_day:
        lines.append(f"**Day Distribution:**")
        day_order = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
        day_names = {'mon': 'Mon', 'tue': 'Tue', 'wed': 'Wed', 'thu': 'Thu', 'fri': 'Fri', 'sat': 'Sat', 'sun': 'Sun'}

        for day in day_order:
            if day in capacity_by_day:
                count = capacity_by_day[day]
                if count > 0:
                    lines.append(f"• {day_names[day]}: {count} assignments")
        lines.append("")

    # Recommendation
    if fill_rate < 90 and available_partners != 'unknown' and max_per_week == 1:
        new_max = available_partners * 2
        lines.append(f"**Recommendation:** Increase max_per_partner_per_week to 2 to allow up to {new_max} assignments (would enable {fill_rate + ((new_max - assignments_count) / total_capacity * 100):.0f}% fill rate).")

    return '\n'.join(lines)
