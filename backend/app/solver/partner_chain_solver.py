"""
Partner Chain OR-Tools Solver

This module uses Google OR-Tools CP-SAT to optimize vehicle selection for partner chains.
Similar to vehicle_chain_solver.py but optimizes vehicles for one partner instead of partners for one vehicle.

Key Differences from Greedy Algorithm:
- Global optimization (considers all slots simultaneously)
- Multi-objective balancing (quality + diversity + preferences)
- Constraint satisfaction (no duplicate models, avoid consecutive same make)
- Explainable decisions (diagnostics show why vehicles selected)

Decision Variables:
    x[vin, slot] = 1 if vehicle assigned to slot

Hard Constraints:
    1. Each slot assigned exactly one vehicle
    2. Each vehicle used at most once
    3. Vehicle available during slot dates
    4. No duplicate models in chain
    5. STRICT mode: Only preferred models (if specified)

Soft Objectives:
    1. Maximize total quality score (tier rank + geo + history + publication)
    2. Minimize consecutive same-make penalty (diversity)
    3. Maximize preference bonus (boost preferred models)
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Set, Tuple
import pandas as pd
import logging
from datetime import datetime
from ortools.sat.python import cp_model

logger = logging.getLogger(__name__)


@dataclass
class ModelPreference:
    """User-specified model preference for chain building"""
    make: str
    model: str
    boost_score: int = 800  # Points to add if "prioritize" mode


@dataclass
class Vehicle:
    """Vehicle candidate for partner chain"""
    vin: str
    make: str
    model: str
    year: str
    score: int
    rank: str  # A+, A, B, C
    slot_index: int
    start_date: str
    end_date: str
    available: bool = True


@dataclass
class PartnerChainResult:
    """Result from OR-Tools solver"""
    status: str  # 'OPTIMAL' | 'FEASIBLE' | 'INFEASIBLE' | 'MODEL_INVALID'
    chain: List[Dict]  # Selected vehicles with slot assignments
    optimization_stats: Dict
    solver_time_ms: int
    diagnostics: Optional[Dict] = None


def group_vehicles_by_model(vehicles_df: pd.DataFrame) -> Dict[Tuple[str, str], List[str]]:
    """
    Group VINs by (make, model).

    Args:
        vehicles_df: DataFrame with columns: vin, make, model

    Returns:
        Dictionary mapping (make, model) -> [list of VINs]
        Example: {('Honda', 'Accord'): ['VIN1', 'VIN2', ...]}
    """
    model_to_vins = {}

    for _, row in vehicles_df.iterrows():
        make = str(row.get('make', 'Unknown'))
        model = str(row.get('model', 'Unknown'))
        vin = str(row['vin'])

        key = (make, model)
        if key not in model_to_vins:
            model_to_vins[key] = []
        model_to_vins[key].append(vin)

    return model_to_vins


def group_vehicles_by_make(vehicles_df: pd.DataFrame) -> Dict[str, List[str]]:
    """
    Group VINs by make.

    Args:
        vehicles_df: DataFrame with columns: vin, make

    Returns:
        Dictionary mapping make -> [list of VINs]
        Example: {'Honda': ['VIN1', 'VIN2', ...]}
    """
    make_to_vins = {}

    for _, row in vehicles_df.iterrows():
        make = str(row.get('make', 'Unknown'))
        vin = str(row['vin'])

        if make not in make_to_vins:
            make_to_vins[make] = []
        make_to_vins[make].append(vin)

    return make_to_vins


def get_preferred_vins(
    model_preferences: List[ModelPreference],
    vehicles_df: pd.DataFrame
) -> Set[str]:
    """
    Get VINs matching preferred models.

    Args:
        model_preferences: List of ModelPreference objects
        vehicles_df: DataFrame with columns: vin, make, model

    Returns:
        Set of VINs that match preferred models
    """
    preferred_vins = set()

    for pref in model_preferences:
        matching = vehicles_df[
            (vehicles_df['make'] == pref.make) &
            (vehicles_df['model'] == pref.model)
        ]
        preferred_vins.update(matching['vin'].tolist())

    return preferred_vins


def calculate_preference_bonus(
    vin: str,
    vehicles_df: pd.DataFrame,
    model_preferences: List[ModelPreference]
) -> int:
    """
    Calculate bonus for preferred vehicle.

    Args:
        vin: Vehicle VIN
        vehicles_df: DataFrame with vehicle info
        model_preferences: List of preferences

    Returns:
        800 if vehicle matches preference, 0 otherwise
    """
    if not model_preferences:
        return 0

    vehicle = vehicles_df[vehicles_df['vin'] == vin]
    if vehicle.empty:
        return 0

    make = vehicle.iloc[0]['make']
    model = vehicle.iloc[0]['model']

    for pref in model_preferences:
        if pref.make == make and pref.model == model:
            return pref.boost_score

    return 0


def solve_partner_chain(
    person_id: int,
    partner_name: str,
    office: str,
    smart_slots: List[Dict],
    candidate_vehicles_df: pd.DataFrame,
    vehicle_scores: Dict[str, int],
    model_preferences: Optional[List[ModelPreference]] = None,
    preference_mode: str = "prioritize",
    diversity_weight: float = 150.0,
    min_quality_threshold: int = 400,
    max_solve_time_seconds: int = 30
) -> PartnerChainResult:
    """
    Solve partner chain using OR-Tools CP-SAT.

    Args:
        person_id: Partner ID
        partner_name: Partner name
        office: Office name
        smart_slots: List of slot dicts with start_date, end_date, available (from smart_scheduling)
        candidate_vehicles_df: DataFrame of eligible vehicles (already filtered by availability)
        vehicle_scores: Dict mapping VIN -> base score (from compute_candidate_scores)
        model_preferences: Optional list of ModelPreference objects
        preference_mode: "prioritize" | "strict" | "ignore"
        diversity_weight: Penalty per consecutive same-make pair (default 150)
        min_quality_threshold: Minimum acceptable vehicle score
        max_solve_time_seconds: Solver timeout

    Returns:
        PartnerChainResult with optimal chain or error status
    """

    start_time = datetime.now()
    logger.info(f"Starting Partner Chain solver for {partner_name} ({len(smart_slots)} slots, {len(candidate_vehicles_df)} candidates)")

    # Validate inputs
    if candidate_vehicles_df.empty:
        logger.error("No candidate vehicles provided")
        return PartnerChainResult(
            status='MODEL_INVALID',
            chain=[],
            optimization_stats={'error': 'No candidate vehicles'},
            solver_time_ms=0
        )

    if not smart_slots:
        logger.error("No smart slots provided")
        return PartnerChainResult(
            status='MODEL_INVALID',
            chain=[],
            optimization_stats={'error': 'No smart slots'},
            solver_time_ms=0
        )

    num_slots = len(smart_slots)
    candidate_vins = candidate_vehicles_df['vin'].tolist()

    # Group vehicles by model and make
    model_to_vins = group_vehicles_by_model(candidate_vehicles_df)
    make_to_vins = group_vehicles_by_make(candidate_vehicles_df)

    # Get preferred VINs if applicable
    preferred_vins = set()
    if model_preferences and preference_mode != "ignore":
        preferred_vins = get_preferred_vins(model_preferences, candidate_vehicles_df)
        logger.info(f"Found {len(preferred_vins)} preferred vehicles (mode: {preference_mode})")

    # Apply preference boost to scores
    adjusted_scores = {}
    for vin in candidate_vins:
        base_score = vehicle_scores.get(vin, 0)

        if preference_mode == "prioritize" and vin in preferred_vins:
            adjusted_scores[vin] = base_score + 800
        else:
            adjusted_scores[vin] = base_score

    # Create CP-SAT model
    model = cp_model.CpModel()

    # Decision variables: x[vin, slot] = 1 if vehicle assigned to slot
    x = {}
    for vin in candidate_vins:
        for slot_idx in range(num_slots):
            x[vin, slot_idx] = model.NewBoolVar(f'x_{vin}_{slot_idx}')

    # HARD CONSTRAINT 1: Each slot assigned exactly one vehicle
    for slot_idx in range(num_slots):
        model.Add(sum(x[vin, slot_idx] for vin in candidate_vins) == 1)

    # HARD CONSTRAINT 2: Each vehicle used at most once
    for vin in candidate_vins:
        model.Add(sum(x[vin, slot_idx] for slot_idx in range(num_slots)) <= 1)

    # HARD CONSTRAINT 3: No duplicate models in chain
    for (make, model_name), vins in model_to_vins.items():
        # At most 1 vehicle with this make/model in entire chain
        model.Add(
            sum(x[vin, slot_idx] for vin in vins for slot_idx in range(num_slots)) <= 1
        )

    # HARD CONSTRAINT 4: STRICT mode - only preferred models
    if preference_mode == "strict" and model_preferences:
        if not preferred_vins:
            logger.error("STRICT mode but no preferred vehicles available")
            return PartnerChainResult(
                status='INFEASIBLE',
                chain=[],
                optimization_stats={'error': 'No preferred vehicles available for STRICT mode'},
                solver_time_ms=0
            )

        # Block all non-preferred vehicles
        for vin in candidate_vins:
            if vin not in preferred_vins:
                for slot_idx in range(num_slots):
                    model.Add(x[vin, slot_idx] == 0)

    # SOFT OBJECTIVE 1: Maximize vehicle quality scores
    total_quality_score = sum(
        adjusted_scores[vin] * x[vin, slot_idx]
        for vin in candidate_vins
        for slot_idx in range(num_slots)
    )

    # SOFT OBJECTIVE 2: Penalize consecutive same make (diversity)
    consecutive_same_make = {}
    diversity_penalty_sum = 0

    for make, vins in make_to_vins.items():
        for slot_idx in range(num_slots - 1):
            # Is this make in slot_idx? Is this make in slot_idx+1?
            slot_has_make = sum(x[vin, slot_idx] for vin in vins)
            next_slot_has_make = sum(x[vin, slot_idx + 1] for vin in vins)

            # consecutive = 1 IFF both slots have this make
            consecutive = model.NewBoolVar(f'consec_{make}_{slot_idx}')
            model.Add(consecutive <= slot_has_make)
            model.Add(consecutive <= next_slot_has_make)
            model.Add(consecutive >= slot_has_make + next_slot_has_make - 1)

            consecutive_same_make[(make, slot_idx)] = consecutive
            diversity_penalty_sum += consecutive * int(diversity_weight)

    # Combined objective: Maximize quality - diversity penalty
    model.Maximize(total_quality_score - diversity_penalty_sum)

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max_solve_time_seconds
    solver.parameters.random_seed = 42
    solver.parameters.num_search_workers = 4

    logger.info(f"Solving with {len(candidate_vins)} vehicles, {num_slots} slots...")
    status = solver.Solve(model)

    solve_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

    # Process results
    if status == cp_model.OPTIMAL:
        status_str = 'OPTIMAL'
    elif status == cp_model.FEASIBLE:
        status_str = 'FEASIBLE'
    elif status == cp_model.INFEASIBLE:
        status_str = 'INFEASIBLE'
        logger.error("Solver returned INFEASIBLE - no solution found")
        return PartnerChainResult(
            status='INFEASIBLE',
            chain=[],
            optimization_stats={
                'error': 'No feasible solution (try relaxing constraints or adding more vehicles)',
                'num_candidates': len(candidate_vins),
                'num_slots': num_slots,
                'preference_mode': preference_mode,
                'preferred_count': len(preferred_vins)
            },
            solver_time_ms=solve_time_ms
        )
    else:
        status_str = 'MODEL_INVALID'
        logger.error(f"Solver returned unexpected status: {status}")
        return PartnerChainResult(
            status='MODEL_INVALID',
            chain=[],
            optimization_stats={'error': f'Solver status: {status}'},
            solver_time_ms=solve_time_ms
        )

    # Extract solution
    chain = []
    total_score = 0
    preference_match_count = 0
    make_distribution = {}

    for slot_idx in range(num_slots):
        for vin in candidate_vins:
            if solver.Value(x[vin, slot_idx]) == 1:
                vehicle_row = candidate_vehicles_df[candidate_vehicles_df['vin'] == vin].iloc[0]

                make = str(vehicle_row.get('make', 'Unknown'))
                model_name = str(vehicle_row.get('model', 'Unknown'))
                year = str(vehicle_row.get('year', ''))
                rank = str(vehicle_row.get('rank', 'C'))
                score = adjusted_scores[vin]
                is_preferred = vin in preferred_vins

                # Track statistics
                total_score += score
                if is_preferred:
                    preference_match_count += 1
                make_distribution[make] = make_distribution.get(make, 0) + 1

                chain.append({
                    'slot': slot_idx + 1,
                    'vin': vin,
                    'make': make,
                    'model': model_name,
                    'year': year,
                    'start_date': smart_slots[slot_idx]['start_date'],
                    'end_date': smart_slots[slot_idx]['end_date'],
                    'score': score,
                    'tier': rank,
                    'is_preferred': is_preferred
                })
                break

    # Count consecutive same-make penalties
    consecutive_penalty_count = 0
    for (make, slot_idx), var in consecutive_same_make.items():
        if solver.Value(var) == 1:
            consecutive_penalty_count += 1

    # Build optimization stats
    optimization_stats = {
        'solver_status': status_str,
        'solver_time_ms': solve_time_ms,
        'total_score': total_score,
        'candidates_considered': len(candidate_vins),
        'preferred_match_count': preference_match_count,
        'diversity_penalty': consecutive_penalty_count * int(diversity_weight),
        'consecutive_penalty_count': consecutive_penalty_count,
        'objective_value': solver.ObjectiveValue()
    }

    # Build diagnostics
    diagnostics = {
        'preference_impact': {
            'preferred_count': preference_match_count,
            'total_count': num_slots,
            'boost_applied': f'+{preference_match_count * 800}'
        },
        'diversity_analysis': {
            'consecutive_penalties': consecutive_penalty_count,
            'make_distribution': make_distribution
        }
    }

    logger.info(f"Solver SUCCESS: {status_str} in {solve_time_ms}ms, score={total_score}, diversity_penalty={consecutive_penalty_count}")

    return PartnerChainResult(
        status=status_str,
        chain=chain,
        optimization_stats=optimization_stats,
        solver_time_ms=solve_time_ms,
        diagnostics=diagnostics
    )


def explain_partner_chain_result(
    result: PartnerChainResult,
    all_candidates: pd.DataFrame,
    vehicle_scores: Dict[str, int],
    model_preferences: Optional[List[ModelPreference]] = None
) -> Dict:
    """
    Explain why certain vehicles were/weren't selected.

    Args:
        result: PartnerChainResult from solver
        all_candidates: All candidate vehicles (including non-selected)
        vehicle_scores: Base scores for all vehicles
        model_preferences: User preferences (if any)

    Returns:
        Dictionary with human-readable explanations
    """

    if result.status not in ['OPTIMAL', 'FEASIBLE']:
        return {
            'status': result.status,
            'message': 'No solution found - cannot explain',
            'optimization_stats': result.optimization_stats
        }

    selected_vins = {v['vin'] for v in result.chain}
    selected_models = {(v['make'], v['model']) for v in result.chain}

    # Analyze selected vehicles
    selected_vehicles = []
    for v in result.chain:
        reason = f"Score {v['score']}"
        if v.get('is_preferred'):
            reason += " (preferred model +800)"

        selected_vehicles.append({
            'vin': v['vin'],
            'make': v['make'],
            'model': v['model'],
            'slot': v['slot'],
            'score': v['score'],
            'tier': v['tier'],
            'reason': reason
        })

    # Analyze excluded high-score vehicles
    excluded_vehicles = []
    for _, vehicle in all_candidates.iterrows():
        vin = vehicle['vin']
        if vin not in selected_vins:
            make = vehicle['make']
            model = vehicle['model']
            base_score = vehicle_scores.get(vin, 0)

            # Check why excluded
            reasons = []
            if (make, model) in selected_models:
                reasons.append(f"Model duplicate ({make} {model} already used)")
            if base_score < 400:
                reasons.append("Low quality score")

            if reasons:
                excluded_vehicles.append({
                    'vin': vin,
                    'make': make,
                    'model': model,
                    'score': base_score,
                    'reason': ', '.join(reasons)
                })

    # Sort excluded by score (show missed opportunities)
    excluded_vehicles.sort(key=lambda x: x['score'], reverse=True)

    return {
        'selected_vehicles': selected_vehicles,
        'excluded_vehicles': excluded_vehicles[:10],  # Top 10 excluded
        'preference_impact': result.diagnostics['preference_impact'],
        'diversity_analysis': result.diagnostics['diversity_analysis']
    }
