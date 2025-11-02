import React, { useState } from 'react';

/**
 * Interactive Timeline Bar Component
 *
 * Features:
 * - Hover to show action buttons (Delete, Request, Unrequest)
 * - Click to open details panel
 * - Rich tooltips with tier, score, dates
 * - Color coding by status (blue=active, green=manual, magenta=requested)
 */
export function TimelineBar({
  activity,
  style,
  onDelete,
  onRequest,
  onUnrequest,
  onClick,
  interactive = true,
  showActions = true
}) {
  const [showTooltip, setShowTooltip] = useState(false);

  // Determine bar color based on type and status
  const getBarColor = () => {
    if (activity.type === 'active') {
      return 'bg-blue-600 border-blue-700';
    }
    if (activity.status === 'manual') {
      return 'bg-green-600 border-green-700';
    }
    if (activity.status === 'requested') {
      return 'bg-pink-600 border-pink-700';
    }
    return 'bg-gray-600 border-gray-700';
  };

  // Build label for bar
  const getLabel = () => {
    const icon = activity.type === 'active' ? '🔵' : activity.status === 'requested' ? '🤖' : '✓';

    // For Partner view, show vehicle info
    if (activity.make && activity.model) {
      return `${icon} ${activity.make} ${activity.model}`;
    }

    // For Vehicle view, show partner info
    if (activity.partner_name) {
      return `${icon} ${activity.partner_name}`;
    }

    return `${icon} Assignment`;
  };

  // Build rich tooltip content
  const getTooltipContent = () => {
    const lines = [];

    // Status
    const statusLabel = activity.type === 'active' ? 'ACTIVE' :
                       activity.status === 'requested' ? 'REQUESTED' : 'MANUAL';
    lines.push(`Status: ${statusLabel}`);

    // Dates
    const startDate = activity.start?.toLocaleDateString() || activity.start_day;
    const endDate = activity.end?.toLocaleDateString() || activity.end_day;
    lines.push(`Dates: ${startDate} - ${endDate}`);

    // Vehicle info (for Partner view)
    if (activity.make && activity.model) {
      lines.push(`Vehicle: ${activity.make} ${activity.model}`);
      if (activity.vin) lines.push(`VIN: ${activity.vin}`);
    }

    // Partner info (for Vehicle view)
    if (activity.partner_name) {
      lines.push(`Partner: ${activity.partner_name}`);
      if (activity.tier) lines.push(`Tier: ${activity.tier}`);
    }

    // Score
    if (activity.score) {
      lines.push(`Score: ${activity.score}`);
    }

    // Office
    if (activity.office) {
      lines.push(`Office: ${activity.office}`);
    }

    return lines.join('\n');
  };

  // Determine which actions are available
  const canDelete = activity.assignment_id && (activity.status === 'manual' || activity.status === 'requested');
  const canRequest = activity.assignment_id && activity.status === 'manual';
  const canUnrequest = activity.assignment_id && activity.status === 'requested';

  const barColor = getBarColor();
  const label = getLabel();

  return (
    <div
      className={`
        absolute ${barColor} border-2 rounded-lg shadow-md text-white text-xs font-semibold
        overflow-hidden px-2 flex items-center transition-all
        ${interactive ? 'hover:shadow-xl cursor-pointer group' : ''}
      `}
      style={style}
      onClick={() => interactive && onClick && onClick(activity)}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
      title={getTooltipContent()}
    >
      {/* Label */}
      <span className="truncate text-[10px]">
        {label}
      </span>

      {/* Hover Action Buttons */}
      {interactive && showActions && (
        <div className="hidden group-hover:flex items-center gap-0.5 ml-auto pl-1">
          {/* Delete Button */}
          {canDelete && onDelete && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete(activity);
              }}
              className="bg-white text-red-600 hover:bg-red-100 rounded px-1 py-0.5 text-[10px] font-bold shadow-sm transition-colors"
              title="Delete assignment"
            >
              ✕
            </button>
          )}

          {/* Request Button (green → magenta) */}
          {canRequest && onRequest && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onRequest(activity);
              }}
              className="bg-white text-pink-600 hover:bg-pink-100 rounded px-1 py-0.5 text-[10px] font-bold shadow-sm transition-colors"
              title="Send to FMS (request)"
            >
              📤
            </button>
          )}

          {/* Unrequest Button (magenta → green) */}
          {canUnrequest && onUnrequest && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onUnrequest(activity);
              }}
              className="bg-white text-green-600 hover:bg-green-100 rounded px-1 py-0.5 text-[10px] font-bold shadow-sm transition-colors"
              title="Move back to manual"
            >
              ↩️
            </button>
          )}
        </div>
      )}

      {/* Rich Tooltip (optional enhancement) */}
      {showTooltip && interactive && (
        <div className="absolute bottom-full left-0 mb-1 bg-gray-900 text-white text-[10px] px-2 py-1 rounded shadow-lg whitespace-nowrap z-50 pointer-events-none">
          {activity.partner_name && <div className="font-bold">{activity.partner_name}</div>}
          {activity.make && activity.model && <div className="font-bold">{activity.make} {activity.model}</div>}
          {activity.tier && <div>Tier: {activity.tier}</div>}
          {activity.score && <div>Score: {activity.score}</div>}
        </div>
      )}
    </div>
  );
}

export default TimelineBar;
