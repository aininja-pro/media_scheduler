"""
Phase 7.5: Distribution/Fairness Soft Penalties

Discourages over-concentration by adding penalties for multiple assignments
to the same partner in the same week.

"We prefer a wider chorus, not just the loudest solo." - Godin
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any
from ortools.sat.python import cp_model


# Default configuration
DEFAULT_FAIR_TARGET = 1  # Preferred assignments per partner before penalties
DEFAULT_LAMBDA_FAIR = 200  # Base penalty weight
DEFAULT_FAIR_STEP_UP = 400  # Additional penalty for 3rd+ assignment (Mode B)


def add_fairness_penalties(
    model: cp_model.CpModel,
    y_vars: Dict,
    triples_df: pd.DataFrame,
    fair_target: int = DEFAULT_FAIR_TARGET,
    lambda_fair: int = DEFAULT_LAMBDA_FAIR,
    fair_step_up: int = 0,  # 0 = Mode A (linear), >0 = Mode B (stepped)
    verbose: bool = True
) -> Tuple[List, Dict[str, Any]]:
    """
    Add fairness penalties to discourage over-concentration of assignments.

    Mode A (linear): penalty = lambda_fair * max(0, n_p - fair_target)
    Mode B (stepped): adds fair_step_up * max(0, n_p - 2) for 3rd+ assignments

    Args:
        model: OR-Tools CP model
        y_vars: Assignment decision variables
        triples_df: Feasible triples
        fair_target: Target assignments per partner (default 1)
        lambda_fair: Base penalty weight
        fair_step_up: Additional penalty for 3rd+ (0 for Mode A)
        verbose: Print debug info

    Returns:
        Tuple of (penalty_terms, fairness_info)
        - penalty_terms: List of penalty variables to subtract from objective
        - fairness_info: Dict with fairness details per partner
    """

    if verbose:
        print(f"\n=== Adding Fairness Penalties (Phase 7.5) ===")
        print(f"  Fair target: {fair_target} per partner")
        print(f"  Lambda fair: {lambda_fair}")
        if fair_step_up > 0:
            print(f"  Mode B active: Step-up penalty {fair_step_up} for 3rd+")
        else:
            print(f"  Mode A: Linear penalties only")

    # Group triples by partner
    partner_vars = {}
    for idx, triple in triples_df.iterrows():
        partner_id = triple['person_id']
        if partner_id not in partner_vars:
            partner_vars[partner_id] = []

        # Find corresponding y variable
        y_key = (triple['vin'], triple['person_id'], triple['start_day'])
        if y_key in y_vars:
            partner_vars[partner_id].append(y_vars[y_key])

    # Track fairness info
    fairness_info = {}
    penalty_terms = []

    # For each partner, count assignments and add penalties
    for partner_id, vars_list in partner_vars.items():
        if not vars_list:
            continue

        # n_p = number of assignments to this partner
        n_p = sum(vars_list)

        # Create integer var for assignment count
        n_p_int = model.NewIntVar(0, len(vars_list), f'n_p_{partner_id[:8]}')
        model.Add(n_p_int == n_p)

        # Mode A: Linear penalty for assignments beyond target
        # penalty_base = lambda_fair * max(0, n_p - fair_target)
        excess = model.NewIntVar(0, len(vars_list), f'excess_{partner_id[:8]}')
        model.Add(excess >= n_p_int - fair_target)
        model.Add(excess >= 0)

        # Add base penalty term
        if lambda_fair > 0:
            penalty_terms.append(lambda_fair * excess)

        # Mode B: Additional penalty for 3rd+ assignments
        if fair_step_up > 0:
            excess_3plus = model.NewIntVar(0, len(vars_list), f'excess3_{partner_id[:8]}')
            model.Add(excess_3plus >= n_p_int - 2)
            model.Add(excess_3plus >= 0)

            # Add step-up penalty term
            penalty_terms.append(fair_step_up * excess_3plus)

        # Store fairness info
        fairness_info[partner_id] = {
            'max_possible': len(vars_list),
            'fair_target': fair_target,
            'has_penalty': True,
            'mode': 'B' if fair_step_up > 0 else 'A'
        }

    if verbose:
        print(f"  Added fairness penalties for {len(partner_vars)} partners")
        print(f"  Total partners with options: {len(partner_vars)}")

        # Show distribution of options
        option_counts = [len(vars) for vars in partner_vars.values()]
        if option_counts:
            print(f"  Options per partner: min={min(option_counts)}, "
                  f"max={max(option_counts)}, avg={np.mean(option_counts):.1f}")

    return penalty_terms, fairness_info


def build_fairness_summary(
    selected_assignments: List[Dict[str, Any]],
    fairness_info: Dict[str, Any],
    fair_target: int = DEFAULT_FAIR_TARGET,
    lambda_fair: int = DEFAULT_LAMBDA_FAIR,
    fair_step_up: int = 0
) -> pd.DataFrame:
    """
    Build summary of fairness penalties after assignment.

    Args:
        selected_assignments: List of selected assignments
        fairness_info: Fairness info from add_fairness_penalties
        fair_target: Target assignments per partner
        lambda_fair: Base penalty weight
        fair_step_up: Step-up penalty for 3rd+

    Returns:
        DataFrame with fairness summary per partner
    """

    # Count assignments per partner
    partner_counts = {}
    for assignment in selected_assignments:
        partner_id = assignment['person_id']
        partner_counts[partner_id] = partner_counts.get(partner_id, 0) + 1

    # Build summary rows
    rows = []
    total_penalty = 0

    for partner_id, count in partner_counts.items():
        # Calculate penalty
        excess = max(0, count - fair_target)
        penalty = lambda_fair * excess

        # Add step-up penalty if Mode B
        if fair_step_up > 0 and count >= 3:
            excess_3plus = count - 2
            penalty += fair_step_up * excess_3plus

        total_penalty += penalty

        rows.append({
            'person_id': partner_id,
            'n_assigned': count,
            'fair_target': fair_target,
            'excess': excess,
            'fairness_penalty': penalty,
            'is_concentrated': count > fair_target
        })

    # Sort by most concentrated first
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(['n_assigned', 'fairness_penalty'], ascending=[False, False])

    # Add metadata
    df.attrs['total_fairness_penalty'] = total_penalty
    df.attrs['lambda_fair'] = lambda_fair
    df.attrs['fair_step_up'] = fair_step_up
    df.attrs['partners_with_multiple'] = len(df[df['n_assigned'] > 1]) if not df.empty else 0
    df.attrs['max_concentration'] = df['n_assigned'].max() if not df.empty else 0

    return df


def calculate_gini_coefficient(assignments_per_partner: List[int]) -> float:
    """
    Calculate Gini coefficient for assignment distribution.

    IMPORTANT: Only includes partners who received assignments (non-zero).
    0 = perfect equality (all selected partners get same number)
    1 = perfect inequality (one partner gets everything)

    Args:
        assignments_per_partner: List of assignment counts (zeros excluded)

    Returns:
        Gini coefficient between 0 and 1
    """
    # Filter out zeros - only measure inequality among those who got assignments
    non_zero_counts = [c for c in assignments_per_partner if c > 0]

    if not non_zero_counts or sum(non_zero_counts) == 0:
        return 0.0

    # Sort in ascending order
    sorted_counts = sorted(non_zero_counts)
    n = len(sorted_counts)

    # Calculate Gini using the formula
    cumsum = 0
    for i, count in enumerate(sorted_counts):
        cumsum += (2 * (i + 1) - n - 1) * count

    total = sum(sorted_counts)
    gini = cumsum / (n * total)

    return min(1.0, max(0.0, gini))  # Ensure in [0, 1]


def calculate_hhi(assignments_per_partner: List[int]) -> float:
    """
    Calculate Herfindahl-Hirschman Index (HHI) for concentration.

    HHI = sum of squared market shares
    Range: 1/n to 1 (where n = number of partners)
    Higher = more concentrated

    Args:
        assignments_per_partner: List of assignment counts

    Returns:
        HHI value between 0 and 1
    """
    non_zero_counts = [c for c in assignments_per_partner if c > 0]

    if not non_zero_counts:
        return 0.0

    total = sum(non_zero_counts)
    if total == 0:
        return 0.0

    # Calculate squared shares
    hhi = sum((count / total) ** 2 for count in non_zero_counts)

    return hhi


def calculate_top_k_share(assignments_per_partner: List[int], k: int = 5) -> float:
    """
    Calculate share of assignments going to top k partners.

    Args:
        assignments_per_partner: List of assignment counts
        k: Number of top partners to consider

    Returns:
        Fraction of total assignments to top k partners
    """
    non_zero_counts = [c for c in assignments_per_partner if c > 0]

    if not non_zero_counts:
        return 0.0

    total = sum(non_zero_counts)
    if total == 0:
        return 0.0

    # Sort descending and take top k
    sorted_counts = sorted(non_zero_counts, reverse=True)
    top_k_sum = sum(sorted_counts[:k])

    return top_k_sum / total


def get_fairness_metrics(fairness_summary: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate comprehensive fairness metrics.

    Includes Gini, HHI, and Top-k share for multi-lens analysis.

    Args:
        fairness_summary: DataFrame from build_fairness_summary

    Returns:
        Dict with various fairness metrics
    """
    if fairness_summary.empty:
        return {
            'total_penalty': 0,
            'partners_assigned': 0,
            'partners_with_multiple': 0,
            'max_concentration': 0,
            'avg_assignments': 0,
            'gini_coefficient': 0,
            'hhi': 0,
            'top_5_share': 0,
            'top_1_share': 0,
            'concentration_ratio': 0
        }

    assignments = fairness_summary['n_assigned'].tolist()
    total_assignments = sum(assignments)

    return {
        'total_penalty': fairness_summary.attrs.get('total_fairness_penalty', 0),
        'partners_assigned': len(fairness_summary),
        'partners_with_multiple': len(fairness_summary[fairness_summary['n_assigned'] > 1]),
        'max_concentration': max(assignments),
        'avg_assignments': total_assignments / len(assignments) if assignments else 0,
        'gini_coefficient': calculate_gini_coefficient(assignments),
        'hhi': calculate_hhi(assignments),
        'top_5_share': calculate_top_k_share(assignments, k=5),
        'top_1_share': calculate_top_k_share(assignments, k=1),
        'concentration_ratio': max(assignments) / total_assignments if total_assignments > 0 else 0
    }