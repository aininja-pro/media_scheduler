"""
Vehicle Chain Solver - OR-Tools CP-SAT Optimization

This module uses Google OR-Tools CP-SAT solver to find optimal partner sequences
for vehicle-centric chains, minimizing travel distance while maximizing partner quality.

Key Problem: Given 1 vehicle and N candidate partners, find the best sequential
assignment that minimizes logistics costs (distance) and maximizes partner quality.

This is a Vehicle Routing Problem (VRP) variant with multi-objective optimization.
"""

import logging
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import pandas as pd
from ortools.sat.python import cp_model

logger = logging.getLogger(__name__)


@dataclass
class Partner:
    """Partner candidate for vehicle chain slot"""
    person_id: int
    name: str
    latitude: Optional[float]
    longitude: Optional[float]
    base_score: int
    engagement_level: str
    publication_rate: float
    tier_rank: str
    available: bool = True


@dataclass
class SlotDates:
    """Date range for a chain slot"""
    slot_index: int
    start_date: str
    end_date: str
    nominal_duration: int
    actual_duration: int
    extended_for_weekend: bool
    handoff_date: Optional[str]


@dataclass
class VehicleChainResult:
    """Result from OR-Tools solver"""
    status: str  # 'success', 'infeasible', 'timeout'
    chain: List[Dict]  # Optimal partner sequence
    optimization_stats: Dict
    logistics_summary: Dict
    diagnostics: Dict
    solver_time_ms: int


def calculate_slot_dates(
    start_date: str,
    num_slots: int,
    days_per_loan: int = 8
) -> List[SlotDates]:
    """
    Calculate slot dates with weekend extension logic.

    Business rule: 8-day loans, extend to Monday if end date falls on weekend.

    Args:
        start_date: Chain start date (YYYY-MM-DD, must be weekday)
        num_slots: Number of partners in chain
        days_per_loan: Nominal loan duration (default 8)

    Returns:
        List of SlotDates objects with actual dates accounting for weekend extensions
    """
    start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()

    # Validate start is weekday
    if start_dt.weekday() >= 5:
        raise ValueError(f"Start date must be weekday, got {start_dt.strftime('%A')}")

    slots = []
    current_start = start_dt

    for i in range(num_slots):
        # Calculate nominal end date
        nominal_end = current_start + timedelta(days=days_per_loan)

        # Apply weekend extension
        actual_end = extend_to_weekday_if_weekend(nominal_end)

        # Calculate actual duration
        actual_duration = (actual_end - current_start).days

        # Handoff date is the end date (same-day pickup for next partner)
        handoff_date = actual_end.strftime('%Y-%m-%d') if i < num_slots - 1 else None

        slots.append(SlotDates(
            slot_index=i,
            start_date=current_start.strftime('%Y-%m-%d'),
            end_date=actual_end.strftime('%Y-%m-%d'),
            nominal_duration=days_per_loan,
            actual_duration=actual_duration,
            extended_for_weekend=(actual_end != nominal_end),
            handoff_date=handoff_date
        ))

        # CRITICAL: Next start = this end (same-day handoff)
        current_start = actual_end

    logger.info(f"Calculated {len(slots)} slot dates, total span: {(current_start - start_dt).days} days")

    return slots


def extend_to_weekday_if_weekend(date) -> datetime.date:
    """
    If date is Saturday or Sunday, extend to following Monday.

    Args:
        date: datetime.date object

    Returns:
        datetime.date (same date if weekday, Monday if weekend)
    """
    if date.weekday() == 5:  # Saturday
        return date + timedelta(days=2)  # → Monday
    elif date.weekday() == 6:  # Sunday
        return date + timedelta(days=1)  # → Monday
    else:
        return date  # Already weekday


def solve_vehicle_chain(
    vin: str,
    vehicle_make: str,
    office: str,
    start_date: str,
    num_partners: int,
    days_per_loan: int,
    candidates: List[Partner],
    distance_matrix: Dict[Tuple[int, int], float],
    distance_weight: float = 0.7,
    max_distance_per_hop: float = 50.0,
    distance_cost_per_mile: float = 2.0,
    solver_timeout_seconds: float = 30.0
) -> VehicleChainResult:
    """
    Solve vehicle chain optimization using OR-Tools CP-SAT.

    Finds optimal sequence of partners that minimizes travel distance
    while maximizing partner quality scores.

    Args:
        vin: Vehicle VIN
        vehicle_make: Vehicle make (for logging)
        office: Office name
        start_date: Chain start date (YYYY-MM-DD, weekday)
        num_partners: Number of partners in chain (4-6 typical)
        days_per_loan: Days per loan (default 8)
        candidates: List of eligible Partner objects
        distance_matrix: Dict[(partner_id_1, partner_id_2)] = miles
        distance_weight: Weight for distance vs quality (0.0-1.0, default 0.7)
        max_distance_per_hop: Hard limit on single hop distance (default 50 miles)
        distance_cost_per_mile: Logistics cost per mile (default $2)
        solver_timeout_seconds: Max solver time (default 30s)

    Returns:
        VehicleChainResult with optimal chain or infeasibility reason
    """
    logger.info(f"Solving vehicle chain for {vin} ({vehicle_make}), {num_partners} partners, starting {start_date}")

    start_time = datetime.now()

    try:
        # 1. Calculate slot dates with weekend extensions
        slot_dates = calculate_slot_dates(start_date, num_partners, days_per_loan)

        # 2. Filter candidates to only those with coordinates (required for distance calculation)
        candidates_with_coords = [
            c for c in candidates
            if c.latitude is not None and c.longitude is not None
        ]

        logger.info(f"Candidates: {len(candidates)} total, {len(candidates_with_coords)} with coordinates")

        if len(candidates_with_coords) < num_partners:
            return VehicleChainResult(
                status='infeasible',
                chain=[],
                optimization_stats={},
                logistics_summary={},
                diagnostics={
                    'reason': f'Insufficient partners with coordinates. Need {num_partners}, have {len(candidates_with_coords)}',
                    'candidates_total': len(candidates),
                    'candidates_with_coords': len(candidates_with_coords)
                },
                solver_time_ms=0
            )

        # 3. Create OR-Tools CP-SAT model
        model = cp_model.CpModel()

        # 4. Decision variables
        # x[partner_id, slot] = 1 if partner assigned to slot
        x = {}
        for candidate in candidates_with_coords:
            for slot in range(num_partners):
                x[candidate.person_id, slot] = model.NewBoolVar(f'x_p{candidate.person_id}_s{slot}')

        # flow[p1, p2, slot] = 1 if chain flows from p1 (slot s) to p2 (slot s+1)
        flow = {}
        for slot in range(num_partners - 1):
            for c1 in candidates_with_coords:
                for c2 in candidates_with_coords:
                    if c1.person_id != c2.person_id:
                        flow[c1.person_id, c2.person_id, slot] = model.NewBoolVar(
                            f'flow_p{c1.person_id}_p{c2.person_id}_s{slot}'
                        )

        logger.info(f"Created {len(x)} assignment variables and {len(flow)} flow variables")

        # 5. HARD CONSTRAINTS

        # Constraint 1: Each slot assigned exactly one partner
        for slot in range(num_partners):
            model.Add(sum(x[c.person_id, slot] for c in candidates_with_coords) == 1)

        # Constraint 2: Each partner used at most once
        for candidate in candidates_with_coords:
            model.Add(sum(x[candidate.person_id, slot] for slot in range(num_partners)) <= 1)

        # Constraint 3: Flow linking - flow[p1,p2,s] = 1 IFF x[p1,s]=1 AND x[p2,s+1]=1
        for slot in range(num_partners - 1):
            for c1 in candidates_with_coords:
                for c2 in candidates_with_coords:
                    if c1.person_id != c2.person_id:
                        # If flow active, both partners must be in sequence
                        model.Add(flow[c1.person_id, c2.person_id, slot] <= x[c1.person_id, slot])
                        model.Add(flow[c1.person_id, c2.person_id, slot] <= x[c2.person_id, slot + 1])
                        # If both partners in sequence, flow must be active
                        model.Add(
                            flow[c1.person_id, c2.person_id, slot] >=
                            x[c1.person_id, slot] + x[c2.person_id, slot + 1] - 1
                        )

        # Constraint 4: Flow conservation - each slot (except last) has exactly one outgoing flow
        for slot in range(num_partners - 1):
            model.Add(
                sum(flow[c1.person_id, c2.person_id, slot]
                    for c1 in candidates_with_coords
                    for c2 in candidates_with_coords
                    if c1.person_id != c2.person_id) == 1
            )

        # Constraint 5: CRITICAL - Max distance per hop (hard constraint)
        infeasible_pairs = 0
        for slot in range(num_partners - 1):
            for c1 in candidates_with_coords:
                for c2 in candidates_with_coords:
                    if c1.person_id != c2.person_id:
                        distance = distance_matrix.get((c1.person_id, c2.person_id), float('inf'))

                        if distance > max_distance_per_hop:
                            # Too far for same-day handoff - mark as infeasible
                            model.Add(flow[c1.person_id, c2.person_id, slot] == 0)
                            infeasible_pairs += 1

        logger.info(f"Distance constraints: {infeasible_pairs} pairs exceed {max_distance_per_hop} mile limit")

        # 6. OBJECTIVE FUNCTION - Weighted combination

        # Create partner score lookup
        score_map = {c.person_id: c.base_score for c in candidates_with_coords}

        # Quality objective (maximize)
        total_quality_score = sum(
            score_map[c.person_id] * x[c.person_id, slot]
            for c in candidates_with_coords
            for slot in range(num_partners)
        )

        # Distance objective (minimize) - convert to cost
        total_distance_cost = sum(
            int(distance_matrix.get((c1.person_id, c2.person_id), 0) * distance_cost_per_mile) *
            flow[c1.person_id, c2.person_id, slot]
            for slot in range(num_partners - 1)
            for c1 in candidates_with_coords
            for c2 in candidates_with_coords
            if c1.person_id != c2.person_id
        )

        # Normalize and combine objectives
        # Quality scores typically 50-250, distance costs $0-$100
        # Scale quality to similar range as distance cost
        quality_weight = int((1 - distance_weight) * 1000)
        distance_weight_scaled = int(distance_weight * 1000)

        model.Maximize(
            quality_weight * total_quality_score - distance_weight_scaled * total_distance_cost
        )

        logger.info(f"Objective: {quality_weight} * quality - {distance_weight_scaled} * distance_cost")

        # 7. SOLVE
        solver = cp_model.CpSolver()
        solver.parameters.random_seed = 42  # Deterministic
        solver.parameters.max_time_in_seconds = solver_timeout_seconds
        solver.parameters.num_search_workers = 4  # Parallel search

        logger.info("Solving model...")
        status = solver.Solve(model)

        solve_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        # 8. EXTRACT SOLUTION
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            logger.info(f"Solution found: {'OPTIMAL' if status == cp_model.OPTIMAL else 'FEASIBLE'}")

            # Extract chain
            chain = []
            total_distance = 0.0
            total_quality = 0

            for slot in range(num_partners):
                # Find which partner is assigned to this slot
                for candidate in candidates_with_coords:
                    if solver.Value(x[candidate.person_id, slot]) == 1:
                        # Found the partner for this slot
                        slot_data = slot_dates[slot]

                        # Find handoff info if not last slot
                        handoff = None
                        if slot < num_partners - 1:
                            for c2 in candidates_with_coords:
                                if candidate.person_id != c2.person_id:
                                    if solver.Value(flow[candidate.person_id, c2.person_id, slot]) == 1:
                                        # Found the next partner
                                        distance = distance_matrix.get((candidate.person_id, c2.person_id), 0)
                                        drive_time = int(distance / 20 * 60)  # 20 mph avg

                                        handoff = {
                                            'date': slot_data.handoff_date,
                                            'from_partner': candidate.name,
                                            'from_partner_id': candidate.person_id,
                                            'to_partner': c2.name,
                                            'to_partner_id': c2.person_id,
                                            'from_location': {
                                                'lat': candidate.latitude,
                                                'lng': candidate.longitude
                                            },
                                            'to_location': {
                                                'lat': c2.latitude,
                                                'lng': c2.longitude
                                            },
                                            'distance_miles': round(distance, 2),
                                            'estimated_drive_time_min': drive_time,
                                            'logistics_cost': round(distance * distance_cost_per_mile, 2)
                                        }

                                        total_distance += distance
                                        break

                        total_quality += candidate.base_score

                        chain.append({
                            'slot': slot,
                            'person_id': candidate.person_id,
                            'name': candidate.name,
                            'start_date': slot_data.start_date,
                            'end_date': slot_data.end_date,
                            'nominal_duration': slot_data.nominal_duration,
                            'actual_duration': slot_data.actual_duration,
                            'extended_for_weekend': slot_data.extended_for_weekend,
                            'handoff': handoff,
                            'score': candidate.base_score,
                            'tier': candidate.tier_rank,
                            'engagement_level': candidate.engagement_level,
                            'publication_rate': candidate.publication_rate,
                            'latitude': candidate.latitude,
                            'longitude': candidate.longitude
                        })
                        break

            # Calculate logistics summary
            num_handoffs = num_partners - 1
            avg_distance = total_distance / num_handoffs if num_handoffs > 0 else 0
            total_drive_time = int(total_distance / 20 * 60)  # 20 mph avg
            total_logistics_cost = total_distance * distance_cost_per_mile

            # Find longest hop
            longest_hop = None
            if chain:
                handoffs = [slot['handoff'] for slot in chain if slot['handoff']]
                if handoffs:
                    longest = max(handoffs, key=lambda h: h['distance_miles'])
                    longest_hop = {
                        'from': longest['from_partner'],
                        'to': longest['to_partner'],
                        'distance': longest['distance_miles']
                    }

            logistics_summary = {
                'total_distance_miles': round(total_distance, 2),
                'average_distance_miles': round(avg_distance, 2),
                'total_drive_time_min': total_drive_time,
                'total_logistics_cost': round(total_logistics_cost, 2),
                'num_handoffs': num_handoffs,
                'longest_hop': longest_hop,
                'all_hops_within_limit': all(
                    slot['handoff']['distance_miles'] <= max_distance_per_hop
                    for slot in chain if slot['handoff']
                ) if chain else True
            }

            optimization_stats = {
                'status': 'optimal' if status == cp_model.OPTIMAL else 'feasible',
                'total_quality_score': total_quality,
                'average_quality_score': int(total_quality / num_partners) if num_partners > 0 else 0,
                'objective_value': int(solver.ObjectiveValue()),
                'solver_time_ms': solve_time_ms,
                'candidates_considered': len(candidates_with_coords),
                'distance_weight_used': distance_weight,
                'quality_weight_used': 1 - distance_weight
            }

            diagnostics = {
                'distance_weight': distance_weight,
                'quality_weight': 1 - distance_weight,
                'infeasible_pairs': infeasible_pairs,
                'max_distance_limit': max_distance_per_hop
            }

            return VehicleChainResult(
                status='success',
                chain=chain,
                optimization_stats=optimization_stats,
                logistics_summary=logistics_summary,
                diagnostics=diagnostics,
                solver_time_ms=solve_time_ms
            )

        elif status == cp_model.INFEASIBLE:
            logger.warning("No feasible solution found")
            return VehicleChainResult(
                status='infeasible',
                chain=[],
                optimization_stats={},
                logistics_summary={},
                diagnostics={
                    'reason': 'No feasible partner sequence found within distance constraints',
                    'candidates': len(candidates_with_coords),
                    'max_distance_per_hop': max_distance_per_hop,
                    'infeasible_pairs': infeasible_pairs
                },
                solver_time_ms=solve_time_ms
            )

        else:  # TIMEOUT or other
            logger.warning(f"Solver status: {status}")
            return VehicleChainResult(
                status='timeout',
                chain=[],
                optimization_stats={},
                logistics_summary={},
                diagnostics={
                    'reason': f'Solver did not complete: status={status}',
                    'solver_time_ms': solve_time_ms
                },
                solver_time_ms=solve_time_ms
            )

    except Exception as e:
        logger.error(f"Error solving vehicle chain: {str(e)}")
        return VehicleChainResult(
            status='error',
            chain=[],
            optimization_stats={},
            logistics_summary={},
            diagnostics={'reason': f'Error: {str(e)}'},
            solver_time_ms=0
        )
