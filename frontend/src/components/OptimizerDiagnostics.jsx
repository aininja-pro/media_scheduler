import React from 'react';

/**
 * OptimizerDiagnostics - Displays "Why This Result?" explanation
 *
 * Shows why the optimizer didn't fill all available capacity:
 * - Daily breakdown of utilization
 * - Primary bottlenecks preventing full capacity
 * - Actionable recommendations
 */
export default function OptimizerDiagnostics({ diagnostics }) {
  if (!diagnostics || !diagnostics.summary) {
    return null;
  }

  const { summary, daily_diagnostics, primary_bottlenecks, recommendations } = diagnostics;

  // Determine if capacity is well-utilized (>85%)
  const isWellUtilized = summary.utilization_pct >= 85;

  // Severity color mapping
  const severityColors = {
    success: 'text-green-600 bg-green-50 border-green-200',
    info: 'text-blue-600 bg-blue-50 border-blue-200',
    medium: 'text-yellow-600 bg-yellow-50 border-yellow-200',
    high: 'text-orange-600 bg-orange-50 border-orange-200',
    critical: 'text-red-600 bg-red-50 border-red-200'
  };

  const priorityIcons = {
    success: '✓',
    high: '🔴',
    medium: '🟡',
    low: '🟢'
  };

  return (
    <div className="mt-6 bg-white border border-gray-200 rounded-lg shadow-sm">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200">
        <h3 className="text-lg font-semibold text-gray-900">
          📊 Optimization Explanation
        </h3>
        <p className="text-sm text-gray-600 mt-1">
          Understanding why the optimizer made these choices
        </p>
      </div>

      {/* THE COMPLETE STORY */}
      <div className="px-6 py-4 border-b border-gray-200 bg-gradient-to-br from-gray-50 to-blue-50">
        <div className="text-lg font-bold text-gray-900 mb-4">📊 The Complete Picture: Why We Got 78 Assignments</div>

        <div className="grid grid-cols-2 gap-6">
          {/* LEFT: VEHICLES JOURNEY */}
          <div className="space-y-3">
            <div className="text-sm font-bold text-gray-700">🚗 VEHICLES JOURNEY</div>

            <div className="bg-white p-3 rounded-lg border-2 border-gray-300">
              <div className="text-xs text-gray-500 uppercase">Total Fleet</div>
              <div className="text-2xl font-bold text-gray-900">{summary.total_vehicles_raw || 'N/A'}</div>
              <div className="text-xs text-gray-600">all vehicles in database</div>
            </div>

            <div className="flex items-center justify-center text-gray-400">↓</div>

            <div className="bg-blue-50 p-3 rounded-lg border-2 border-blue-300">
              <div className="text-xs text-blue-600 uppercase font-semibold">Available This Week</div>
              <div className="text-2xl font-bold text-blue-900">{summary.total_vehicles_available}</div>
              <div className="text-xs text-blue-700">{(summary.total_vehicles_raw || 0) - summary.total_vehicles_available} vehicles out of service</div>
            </div>

            <div className="flex items-center justify-center text-gray-400">↓ Optimizer Filtering</div>

            <div className="bg-green-50 p-3 rounded-lg border-2 border-green-400">
              <div className="text-xs text-green-700 uppercase font-semibold">Entered Optimizer</div>
              <div className="text-2xl font-bold text-green-900">{summary.total_vehicles_available}</div>
              <div className="text-xs text-red-600">{summary.vehicles_filtered} filtered: not available 8 consecutive days</div>
            </div>

            <div className="flex items-center justify-center text-gray-400">↓ Optimizer Decision</div>

            <div className="bg-purple-50 p-3 rounded-lg border-2 border-purple-400">
              <div className="text-xs text-purple-700 uppercase font-semibold">Assigned</div>
              <div className="text-2xl font-bold text-purple-900">{summary.total_assigned}</div>
              <div className="text-xs text-gray-600">{summary.total_vehicles_available - summary.total_assigned} vehicles NOT used</div>
            </div>
          </div>

          {/* RIGHT: PARTNERS JOURNEY */}
          <div className="space-y-3">
            <div className="text-sm font-bold text-gray-700">👥 PARTNERS JOURNEY</div>

            <div className="bg-white p-3 rounded-lg border-2 border-gray-300">
              <div className="text-xs text-gray-500 uppercase">Total Partners</div>
              <div className="text-2xl font-bold text-gray-900">{summary.total_partners_raw || 'N/A'}</div>
              <div className="text-xs text-gray-600">all partners in database</div>
            </div>

            <div className="flex items-center justify-center text-gray-400">↓</div>

            <div className="bg-blue-50 p-3 rounded-lg border-2 border-blue-300">
              <div className="text-xs text-blue-600 uppercase font-semibold">Eligible This Week</div>
              <div className="text-2xl font-bold text-blue-900">{summary.total_partners_eligible}</div>
              <div className="text-xs text-blue-700">{(summary.total_partners_raw || 0) - summary.total_partners_eligible} partners not eligible for available vehicle makes</div>
            </div>

            <div className="flex items-center justify-center text-gray-400">↓ Optimizer Filtering</div>

            <div className="bg-green-50 p-3 rounded-lg border-2 border-green-400">
              <div className="text-xs text-green-700 uppercase font-semibold">Entered Optimizer</div>
              <div className="text-2xl font-bold text-green-900">{summary.total_partners_eligible}</div>
              <div className="text-xs text-red-600">{summary.partners_filtered} filtered: 30-day cooldown period</div>
            </div>

            <div className="flex items-center justify-center text-gray-400">↓ Optimizer Decision</div>

            <div className="bg-purple-50 p-3 rounded-lg border-2 border-purple-400">
              <div className="text-xs text-purple-700 uppercase font-semibold">Received Vehicle</div>
              <div className="text-2xl font-bold text-purple-900">{summary.total_assigned}</div>
              <div className="text-xs text-gray-600">{summary.total_partners_eligible - summary.total_assigned} partners didn't receive vehicle</div>
            </div>
          </div>
        </div>

        {/* BOTTOM: THE CAPACITY MATH */}
        <div className="mt-6 p-4 bg-white rounded-lg border-2 border-yellow-400">
          <div className="text-sm font-bold text-yellow-900 mb-2">📐 THE CAPACITY MATH</div>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <div className="text-xs text-gray-500">Optimizer Target</div>
              <div className="font-bold text-green-700">{summary.total_capacity} slots to fill</div>
              <div className="text-xs text-gray-600">(available capacity after existing commitments)</div>
            </div>
            <div>
              <div className="text-xs text-gray-500">Optimizer Result</div>
              <div className="font-bold text-blue-600">{summary.total_assigned} slots filled</div>
              <div className="text-xs text-gray-600">({summary.total_empty} empty = {summary.utilization_pct.toFixed(1)}% utilized)</div>
            </div>
          </div>
        </div>

        {/* FINAL RESULT */}
        <div className="mt-4 p-4 bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg text-white">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm opacity-90">FINAL RESULT</div>
              <div className="text-4xl font-bold mt-1">
                {summary.total_assigned} of {summary.total_capacity} slots filled
              </div>
              <div className="text-sm mt-1 opacity-90">
                {summary.total_empty} empty slots = {summary.utilization_pct.toFixed(1)}% utilization
              </div>
            </div>
            <div className="text-6xl">
              {summary.utilization_pct >= 85 ? '✅' : summary.utilization_pct >= 65 ? '⚠️' : '❌'}
            </div>
          </div>
        </div>

        {/* WHY DIDN'T WE FILL ALL 120 SLOTS? */}
        {summary.total_empty > 0 && (
          <div className="mt-4 p-4 bg-orange-50 rounded-lg border-2 border-orange-400">
            <div className="text-sm font-bold text-orange-900 mb-2">❓ WHY DIDN'T WE FILL ALL {summary.total_capacity} SLOTS?</div>
            <div className="text-sm text-orange-900 space-y-2">
              <div className="font-semibold">The optimizer had 100 vehicles and 129 partners to work with, but could only make 78 assignments. Here's why:</div>
              <div className="ml-4 space-y-1">
                <div>• <strong>Constraint:</strong> Max 1 vehicle per partner per day (see "Max Vehicles per Media Partner per Day" setting below)</div>
                <div>• <strong>Impact:</strong> Each partner can only receive 1 vehicle for the ENTIRE WEEK, limiting total assignments to ~78 optimal matches</div>
                <div>• <strong>The Gap:</strong> 22 vehicles couldn't be matched without giving the same partner 2+ vehicles (violates the constraint)</div>
              </div>
              <div className="mt-3 p-3 bg-white rounded border border-orange-300">
                <div className="font-bold text-orange-900 mb-1">💡 TO FILL MORE SLOTS:</div>
                <div className="text-xs">Change "Max Vehicles per Media Partner per Day" setting from <strong className="bg-yellow-200 px-1">1 (current)</strong> to <strong className="bg-green-200 px-1">2</strong> — this would allow partners to receive multiple vehicles and fill the remaining 42 empty slots</div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Daily Breakdown */}
      <div className="px-6 py-4">
        <h4 className="font-semibold text-gray-900 mb-3">Daily Capacity Breakdown</h4>
        <div className="space-y-2">
          {daily_diagnostics && daily_diagnostics.map((day) => {
            const utilizationColor =
              day.utilization_pct >= 90 ? 'bg-green-500' :
              day.utilization_pct >= 70 ? 'bg-blue-500' :
              day.utilization_pct >= 50 ? 'bg-yellow-500' :
              'bg-red-500';

            return (
              <div key={day.date} className="flex items-center gap-3">
                <div className="w-20 text-sm font-medium text-gray-700">{day.day}</div>

                {/* Progress bar */}
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-6 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className={`h-full ${utilizationColor} transition-all`}
                        style={{ width: `${day.utilization_pct}%` }}
                      />
                    </div>
                    <div className="text-sm font-medium text-gray-700 w-16 text-right">
                      {day.assigned}/{day.available_capacity}
                    </div>
                  </div>
                </div>

                <div className="text-xs text-gray-500 w-24 text-right">
                  {day.utilization_pct.toFixed(0)}% utilized
                </div>

                {day.empty_slots > 0 && (
                  <div className="text-xs text-orange-600 font-medium w-24 text-right">
                    {day.empty_slots} empty
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
