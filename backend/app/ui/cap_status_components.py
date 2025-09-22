"""
UI Components for Soft Tier Cap Status Display
Provides formatted components for displaying cap violation status in the UI.
"""

import pandas as pd
from typing import Dict, Any, Optional, List


class CapStatusDisplay:
    """Generate UI components for soft tier cap status."""

    def __init__(self, lambda_cap: int = 800):
        self.lambda_cap = lambda_cap

    def get_status_chip(self, result: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate main status chip for header/navbar display.

        Returns dict with:
        - text: Display text
        - color: Badge color (green/orange/red)
        - icon: Icon class/emoji
        """
        cap_summary = result.get('cap_summary', pd.DataFrame())
        total_penalty = result.get('total_cap_penalty', 0)

        violations = self._count_violations(cap_summary)

        if violations == 0:
            return {
                'text': f'✓ Caps OK (λ={self.lambda_cap})',
                'color': 'success',
                'icon': 'check-circle',
                'tooltip': 'All assignments within tier caps'
            }
        elif total_penalty < 2000:
            return {
                'text': f'⚠ Over-cap: {violations} (${total_penalty:,})',
                'color': 'warning',
                'icon': 'alert-triangle',
                'tooltip': f'{violations} partners exceeded caps, ${total_penalty:,} penalty'
            }
        else:
            return {
                'text': f'⛔ Over-cap: {violations} (${total_penalty:,})',
                'color': 'danger',
                'icon': 'x-octagon',
                'tooltip': f'High penalties! {violations} violations, ${total_penalty:,} total'
            }

    def get_detail_card(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate detailed card for expanded view.

        Shows breakdown of violations and penalties.
        """
        cap_summary = result.get('cap_summary', pd.DataFrame())
        total_penalty = result.get('total_cap_penalty', 0)

        violations = self._count_violations(cap_summary)
        total_delta = self._sum_delta(cap_summary)

        # Get top violations
        top_violations = []
        if not cap_summary.empty and violations > 0:
            over_cap = cap_summary[cap_summary['delta_overage'] > 0].head(3)
            for _, row in over_cap.iterrows():
                top_violations.append({
                    'partner': row['person_id'][:10] + '...' if len(row['person_id']) > 10 else row['person_id'],
                    'make': row['make'],
                    'rank': row.get('rank', '?'),
                    'delta': int(row['delta_overage']),
                    'penalty': int(row['penalty'])
                })

        return {
            'title': 'Tier Cap Status',
            'lambda': self.lambda_cap,
            'stats': {
                'violations': violations,
                'total_delta': total_delta,
                'total_penalty': total_penalty,
                'penalty_per_violation': total_penalty // violations if violations > 0 else 0
            },
            'top_violations': top_violations,
            'color': self._get_severity_color(total_penalty)
        }

    def get_stage_summary(self, result: Dict[str, Any]) -> List[str]:
        """
        Generate summary lines for pipeline stage display.

        Returns list of formatted strings.
        """
        cap_summary = result.get('cap_summary', pd.DataFrame())
        total_penalty = result.get('total_cap_penalty', 0)
        removed_by_zero = result.get('removed_by_zero_caps', 0)

        violations = self._count_violations(cap_summary)

        lines = [
            '✓ Soft Tier Caps Active',
            f'• Lambda: {self.lambda_cap}',
            f'• Removed by zero-caps: {removed_by_zero:,}' if removed_by_zero > 0 else None,
            f'• Cap penalties: ${total_penalty:,}',
            f'• Violations: {violations}'
        ]

        return [line for line in lines if line]  # Filter None values

    def get_assignment_annotation(
        self,
        assignment: Dict[str, Any],
        cap_summary: pd.DataFrame
    ) -> Optional[Dict[str, str]]:
        """
        Get annotation for individual assignment display.

        Shows cap usage for this partner-make pair.
        """
        if cap_summary.empty:
            return None

        # Find matching cap info
        match = cap_summary[
            (cap_summary['person_id'] == assignment['person_id']) &
            (cap_summary['make'] == assignment['make'])
        ]

        if match.empty:
            return None

        row = match.iloc[0]
        cap = row.get('cap', 'Unlimited')

        if cap == 'Unlimited':
            return {
                'text': 'Unlimited',
                'color': 'muted',
                'icon': 'infinity'
            }

        cap_val = int(cap) if cap != 'Unlimited' else None
        used = int(row.get('used_after', 0))
        remaining = int(row.get('remaining_after', 0))

        if remaining == 0:
            return {
                'text': f'At cap ({used}/{cap_val})',
                'color': 'warning',
                'icon': 'alert-circle'
            }
        elif used > cap_val:
            overage = used - cap_val
            return {
                'text': f'Over cap +{overage} ({used}/{cap_val})',
                'color': 'danger',
                'icon': 'x-circle'
            }
        else:
            return {
                'text': f'Used: {used}/{cap_val} ({remaining} left)',
                'color': 'success',
                'icon': 'check'
            }

    def get_warning_banner(self, result: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """
        Generate warning banner if penalties are high.

        Returns None if no warning needed.
        """
        total_penalty = result.get('total_cap_penalty', 0)
        cap_summary = result.get('cap_summary', pd.DataFrame())

        if total_penalty > 5000:
            violations = self._count_violations(cap_summary)
            return {
                'type': 'danger',
                'title': 'High Cap Penalties',
                'message': f'{violations} partners exceeded caps, incurring ${total_penalty:,} in penalties.',
                'action': 'Review violations',
                'link': '/audit/caps'
            }
        elif total_penalty > 2000:
            violations = self._count_violations(cap_summary)
            return {
                'type': 'warning',
                'title': 'Cap Violations Detected',
                'message': f'{violations} partners over cap (${total_penalty:,} penalty)',
                'action': 'View details',
                'link': '/audit/caps'
            }

        return None

    def format_audit_table(self, cap_summary: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Format cap summary for audit table display.

        Returns list of dicts ready for table rendering.
        """
        if cap_summary.empty:
            return []

        # Filter to violations only
        violations = cap_summary[cap_summary['delta_overage'] > 0].copy()

        if violations.empty:
            return []

        # Sort by penalty descending
        violations = violations.sort_values('penalty', ascending=False)

        rows = []
        for _, row in violations.iterrows():
            cap_display = str(row['cap']) if row['cap'] != 'Unlimited' else '∞'
            rows.append({
                'partner_id': row['person_id'],
                'make': row['make'],
                'rank': row.get('rank', '?'),
                'usage': f"{row['used_12m_before']} → {row['used_after']}",
                'cap': cap_display,
                'delta': f"+{row['delta_overage']}",
                'penalty': f"${row['penalty']:,}",
                'severity': self._get_severity_color(row['penalty'])
            })

        return rows

    # Helper methods
    def _count_violations(self, cap_summary: pd.DataFrame) -> int:
        """Count partners with violations."""
        if cap_summary.empty:
            return 0
        return len(cap_summary[cap_summary['delta_overage'] > 0])

    def _sum_delta(self, cap_summary: pd.DataFrame) -> int:
        """Sum total delta overage."""
        if cap_summary.empty:
            return 0
        return int(cap_summary['delta_overage'].sum())

    def _get_severity_color(self, penalty: int) -> str:
        """Map penalty amount to severity color."""
        if penalty == 0:
            return 'success'
        elif penalty < 2000:
            return 'warning'
        else:
            return 'danger'


# React component template (for reference)
REACT_COMPONENT_TEMPLATE = """
// CapStatusChip.tsx
import React from 'react';
import { Badge, Tooltip } from 'antd';

interface CapStatusProps {
  violations: number;
  penalty: number;
  lambda: number;
}

export const CapStatusChip: React.FC<CapStatusProps> = ({ violations, penalty, lambda }) => {
  const getStatus = () => {
    if (violations === 0) {
      return { text: `✓ Caps OK (λ=${lambda})`, color: 'green' };
    } else if (penalty < 2000) {
      return { text: `⚠ Over-cap: ${violations} ($${penalty.toLocaleString()})`, color: 'orange' };
    } else {
      return { text: `⛔ Over-cap: ${violations} ($${penalty.toLocaleString()})`, color: 'red' };
    }
  };

  const { text, color } = getStatus();

  return (
    <Tooltip title={`${violations} partners exceeded tier caps, $${penalty.toLocaleString()} total penalty`}>
      <Badge color={color} text={text} />
    </Tooltip>
  );
};
"""