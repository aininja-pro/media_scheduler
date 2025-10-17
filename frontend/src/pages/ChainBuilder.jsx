import React, { useState, useEffect } from 'react';

function ChainBuilder({ sharedOffice }) {
  // Use shared office from parent, default to 'Los Angeles'
  const [selectedOffice, setSelectedOffice] = useState(sharedOffice || 'Los Angeles');
  const [selectedPartner, setSelectedPartner] = useState('');
  const [startDate, setStartDate] = useState('');
  const [numVehicles, setNumVehicles] = useState(4);
  const [daysPerLoan, setDaysPerLoan] = useState(7);
  const [isLoading, setIsLoading] = useState(false);
  const [chain, setChain] = useState(null);
  const [error, setError] = useState('');

  // Timeline navigation
  const [viewStartDate, setViewStartDate] = useState(null); // Show 1 month at a time
  const [viewEndDate, setViewEndDate] = useState(null);

  // Load offices and partners
  const [offices, setOffices] = useState([]);
  const [partners, setPartners] = useState([]);
  const [partnerSearchQuery, setPartnerSearchQuery] = useState('');

  // Partner intelligence (current/scheduled activities)
  const [partnerIntelligence, setPartnerIntelligence] = useState(null);
  const [loadingIntelligence, setLoadingIntelligence] = useState(false);

  // Update selectedOffice when sharedOffice prop changes
  useEffect(() => {
    if (sharedOffice) {
      setSelectedOffice(sharedOffice);
    }
  }, [sharedOffice]);

  // Load offices from API
  useEffect(() => {
    const loadOffices = async () => {
      try {
        const response = await fetch('http://localhost:8081/api/offices');
        const data = await response.json();
        if (data && data.length > 0) {
          setOffices(data.map(office => office.name));
        }
      } catch (err) {
        console.error('Failed to load offices:', err);
        setOffices(['Los Angeles', 'Atlanta', 'Chicago', 'Dallas', 'Denver', 'Detroit', 'Miami', 'Phoenix', 'San Francisco', 'Seattle']);
      }
    };
    loadOffices();
  }, []);

  // Load partners when office changes
  useEffect(() => {
    if (!selectedOffice) return;

    const loadPartners = async () => {
      try {
        // Use the calendar API to get all partners for this office
        const response = await fetch(`http://localhost:8081/api/calendar/media-partners?office=${encodeURIComponent(selectedOffice)}`);
        if (!response.ok) {
          console.error('Failed to load partners');
          return;
        }

        const data = await response.json();

        // Sort partners alphabetically by name
        const partnersList = data.partners || [];
        const sortedPartners = partnersList
          .map(p => ({
            person_id: p.person_id,
            name: p.name || `Partner ${p.person_id}`
          }))
          .sort((a, b) => a.name.localeCompare(b.name));

        setPartners(sortedPartners);
        console.log(`Loaded ${sortedPartners.length} partners for ${selectedOffice}`);
      } catch (err) {
        console.error('Failed to load partners:', err);
        setPartners([]);
      }
    };

    loadPartners();
  }, [selectedOffice]);

  // Get current Monday as default
  const getCurrentMonday = () => {
    const today = new Date();
    const dayOfWeek = today.getDay();
    const daysToMonday = dayOfWeek === 0 ? 1 : 1 - dayOfWeek;
    const monday = new Date(today);
    monday.setDate(today.getDate() + daysToMonday);
    return monday.toISOString().split('T')[0];
  };

  // Initialize start date to next Monday
  useEffect(() => {
    setStartDate(getCurrentMonday());
  }, []);

  // Load partner intelligence when partner is selected
  useEffect(() => {
    if (!selectedPartner || !selectedOffice) {
      setPartnerIntelligence(null);
      return;
    }

    const loadPartnerIntelligence = async () => {
      setLoadingIntelligence(true);
      try {
        const response = await fetch(
          `http://localhost:8081/api/ui/phase7/partner-intelligence?person_id=${selectedPartner}&office=${encodeURIComponent(selectedOffice)}`
        );
        if (response.ok) {
          const data = await response.json();
          if (data.success) {
            setPartnerIntelligence(data);

            // Initialize timeline view to current month when partner loads
            if (!viewStartDate) {
              const now = new Date();
              const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
              const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0);
              setViewStartDate(monthStart);
              setViewEndDate(monthEnd);
            }
          }
        }
      } catch (err) {
        console.error('Error loading partner intelligence:', err);
      } finally {
        setLoadingIntelligence(false);
      }
    };

    loadPartnerIntelligence();
  }, [selectedPartner, selectedOffice]);

  // Initialize timeline view when chain is generated
  useEffect(() => {
    if (chain && chain.chain.length > 0) {
      // Set view to show first month of chain (use string parsing to avoid timezone)
      const dateStr = chain.chain[0].start_date; // "2025-10-20"
      const [year, month, day] = dateStr.split('-').map(Number);
      const chainStart = new Date(year, month - 1, day); // Local date
      const monthStart = new Date(year, month - 1, 1);
      const monthEnd = new Date(year, month, 0);
      setViewStartDate(monthStart);
      setViewEndDate(monthEnd);
    }
  }, [chain]);

  // Slide timeline forward by 7 days (like Calendar tab)
  const slideForward = () => {
    if (!viewStartDate || !viewEndDate) return;
    const newStart = new Date(viewStartDate);
    const newEnd = new Date(viewEndDate);
    newStart.setDate(newStart.getDate() + 7);
    newEnd.setDate(newEnd.getDate() + 7);
    setViewStartDate(newStart);
    setViewEndDate(newEnd);
  };

  // Slide timeline backward by 7 days (like Calendar tab)
  const slideBackward = () => {
    if (!viewStartDate || !viewEndDate) return;
    const newStart = new Date(viewStartDate);
    const newEnd = new Date(viewEndDate);
    newStart.setDate(newStart.getDate() - 7);
    newEnd.setDate(newEnd.getDate() - 7);
    setViewStartDate(newStart);
    setViewEndDate(newEnd);
  };

  // Parse date string as local date (avoid timezone issues)
  const parseLocalDate = (dateStr) => {
    if (!dateStr || typeof dateStr !== 'string') return null;
    try {
      const parts = dateStr.split('-');
      if (parts.length !== 3) return null;
      return new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
    } catch (e) {
      return null;
    }
  };

  const generateChain = async () => {
    if (!selectedPartner) {
      setError('Please select a media partner');
      return;
    }

    if (!startDate) {
      setError('Please select a start date');
      return;
    }

    setIsLoading(true);
    setError('');
    setChain(null);

    try {
      const params = new URLSearchParams({
        person_id: selectedPartner,
        office: selectedOffice,
        start_date: startDate,
        num_vehicles: numVehicles,
        days_per_loan: daysPerLoan
      });

      const response = await fetch(`http://localhost:8081/api/chain-builder/suggest-chain?${params}`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to generate chain');
      }

      setChain(data);
      console.log('Chain generated:', data);
    } catch (err) {
      setError(err.message);
      setChain(null);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">Chain Builder</h1>
            <p className="text-sm text-gray-500 mt-1">Create sequential vehicle assignments for a media partner</p>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3">
              <label className="text-sm text-gray-600">Office</label>
              <select
                value={selectedOffice}
                onChange={(e) => setSelectedOffice(e.target.value)}
                className="border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {offices.map(office => (
                  <option key={office} value={office}>{office}</option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex h-full">
        {/* Left Panel - Chain Parameters */}
        <div className="w-80 bg-white border-r p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">Chain Parameters</h2>

          <div className="space-y-6">
            {/* Partner Selector with Search */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Media Partner
              </label>

              {/* Search Input */}
              <input
                type="text"
                placeholder="Type to search partners..."
                value={partnerSearchQuery}
                onChange={(e) => setPartnerSearchQuery(e.target.value)}
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 mb-2"
              />

              {/* Filtered Partner List */}
              <div className="border border-gray-300 rounded max-h-48 overflow-y-auto">
                {partners
                  .filter(partner =>
                    partner.name.toLowerCase().includes(partnerSearchQuery.toLowerCase())
                  )
                  .map(partner => (
                    <button
                      key={partner.person_id}
                      onClick={() => {
                        setSelectedPartner(partner.person_id);
                        setPartnerSearchQuery(partner.name); // Show selected name
                      }}
                      className={`w-full text-left px-3 py-2 text-sm hover:bg-blue-50 transition-colors ${
                        selectedPartner === partner.person_id ? 'bg-blue-100 font-medium' : ''
                      }`}
                    >
                      {partner.name}
                    </button>
                  ))}
                {partners.filter(p => p.name.toLowerCase().includes(partnerSearchQuery.toLowerCase())).length === 0 && (
                  <div className="px-3 py-4 text-sm text-gray-500 text-center">
                    No partners found
                  </div>
                )}
              </div>

              {selectedPartner && (
                <p className="text-xs text-gray-500 mt-1">
                  Selected: {partners.find(p => p.person_id === selectedPartner)?.name}
                </p>
              )}
            </div>

            {/* Start Date */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Start Date
              </label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                min={new Date().toISOString().split('T')[0]}
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-gray-500 mt-1">Must be a weekday (Mon-Fri), today or future</p>
            </div>

            {/* Number of Vehicles */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Number of Vehicles
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min="1"
                  max="10"
                  value={numVehicles}
                  onChange={(e) => setNumVehicles(parseInt(e.target.value))}
                  className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                />
                <span className="text-lg font-semibold text-gray-900 w-8 text-center">{numVehicles}</span>
              </div>
              <div className="flex justify-between text-xs text-gray-400 mt-1">
                <span>1</span>
                <span>10</span>
              </div>
            </div>

            {/* Days Per Loan */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Days Per Loan
              </label>
              <input
                type="number"
                min="1"
                max="14"
                value={daysPerLoan}
                onChange={(e) => setDaysPerLoan(parseInt(e.target.value) || 7)}
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-gray-500 mt-1">Typical: 7 days (1 week)</p>
            </div>

            {/* Generate Button */}
            <button
              onClick={generateChain}
              disabled={isLoading || !selectedPartner || !startDate}
              className={`w-full py-3 rounded-md text-sm font-medium transition-colors ${
                isLoading || !selectedPartner || !startDate
                  ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                  : 'bg-blue-600 text-white hover:bg-blue-700'
              }`}
            >
              {isLoading ? 'Generating Chain...' : 'Generate Chain'}
            </button>

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-md p-3 text-sm text-red-700">
                {error}
              </div>
            )}
          </div>
        </div>

        {/* Center Panel - Chain Preview */}
        <div className="flex-1 p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Chain Preview</h2>

          {selectedPartner && partnerIntelligence ? (
            <div className="space-y-6">
              {/* Chain Header */}
              {chain && (
                <div className="bg-white rounded-lg shadow-sm border p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-lg font-medium text-gray-900">{chain.partner_info.name}</h3>
                      <p className="text-sm text-gray-500">
                        {chain.chain_params.start_date} - {chain.chain[chain.chain.length - 1]?.end_date} ({chain.chain_params.total_span_days} days)
                      </p>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-semibold text-gray-900">{chain.chain.length}</div>
                      <div className="text-xs text-gray-500">Vehicles</div>
                    </div>
                  </div>
                </div>
              )}

              {/* Timeline Visualization - Calendar Style with Month View */}
              <div className="bg-white rounded-lg shadow-sm border p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-md font-semibold text-gray-900">Chain Timeline</h3>

                  {/* Month Navigation Arrows */}
                  <div className="flex gap-2">
                    <button
                      onClick={slideBackward}
                      className="px-2 py-1 border border-gray-300 rounded-md hover:bg-gray-50 text-xs"
                      title="Previous month"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                      </svg>
                    </button>
                    <span className="text-sm font-medium text-gray-700 px-3 py-1">
                      {viewStartDate?.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
                    </span>
                    <button
                      onClick={slideForward}
                      className="px-2 py-1 border border-gray-300 rounded-md hover:bg-gray-50 text-xs"
                      title="Next month"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </button>
                  </div>
                </div>

                <div className="border-2 rounded-lg overflow-x-auto">
                  {(() => {
                    if (!viewStartDate || !viewEndDate) return null;

                    // Generate days in current month view
                    const days = [];
                    const current = new Date(viewStartDate);
                    const end = new Date(viewEndDate);

                    while (current <= end) {
                      days.push(new Date(current));
                      current.setDate(current.getDate() + 1);
                    }

                    return (
                      <>
                        {/* Header Row - Day headers like Calendar (Mon 1, Tue 2, etc.) */}
                        <div className="flex border-b bg-gray-50">
                          <div className="w-48 flex-shrink-0 px-4 py-3 border-r font-medium text-sm text-gray-700">
                            {chain ? chain.partner_info.name : partnerIntelligence.partner.name}
                          </div>
                          <div className="flex-1 flex">
                            {days.map((date, idx) => {
                              const dayOfWeek = date.getDay();
                              const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
                              const dayNum = date.getDate();
                              const weekday = date.toLocaleDateString('en-US', { weekday: 'short' });

                              return (
                                <div
                                  key={idx}
                                  className={`flex-1 text-center text-xs py-2 border-r ${
                                    isWeekend ? 'bg-blue-100 text-blue-800 font-semibold' : 'text-gray-600'
                                  }`}
                                >
                                  <div className="leading-tight">
                                    <div>{weekday}</div>
                                    <div className="font-semibold">{dayNum}</div>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>

                        {/* Timeline Row with stair-stepped bars (3 per row) */}
                        <div className="relative flex" style={{ minHeight: '200px' }}>
                          <div className="w-48 flex-shrink-0 border-r bg-gray-50"></div>

                          <div className="flex-1 relative">
                            {/* Day grid background with weekend highlighting */}
                            <div className="absolute inset-0 flex">
                              {days.map((date, i) => {
                                const isWeekend = date.getDay() === 0 || date.getDay() === 6;
                                return (
                                  <div
                                    key={i}
                                    className={`flex-1 border-r border-gray-300 ${
                                      isWeekend ? 'bg-blue-50' : ''
                                    }`}
                                  ></div>
                                );
                              })}
                            </div>

                            {/* Existing activities (current + scheduled) - show FIRST */}
                            {partnerIntelligence && (() => {
                              const existingActivities = [];

                              // Add current active loans (BLUE)
                              partnerIntelligence.current_loans?.forEach(loan => {
                                const [sYear, sMonth, sDay] = loan.start_date.split('-').map(Number);
                                const [eYear, eMonth, eDay] = loan.end_date.split('-').map(Number);
                                existingActivities.push({
                                  type: 'active',
                                  vin: loan.vehicle_vin,
                                  make: loan.make,
                                  model: loan.model,
                                  start: new Date(sYear, sMonth - 1, sDay),
                                  end: new Date(eYear, eMonth - 1, eDay)
                                });
                              });

                              // Add scheduled assignments (GREEN - optimizer/manual)
                              partnerIntelligence.upcoming_assignments?.forEach(assignment => {
                                const [sYear, sMonth, sDay] = assignment.start_day.split('-').map(Number);
                                const [eYear, eMonth, eDay] = assignment.end_day.split('-').map(Number);
                                existingActivities.push({
                                  type: 'scheduled',
                                  vin: assignment.vin,
                                  make: assignment.make,
                                  model: assignment.model,
                                  status: assignment.status,
                                  start: new Date(sYear, sMonth - 1, sDay),
                                  end: new Date(eYear, eMonth - 1, eDay)
                                });
                              });

                              return existingActivities.map((activity, idx) => {
                                const aStart = activity.start;
                                const aEnd = activity.end;

                                // Only show if overlaps with current view
                                const viewStart = new Date(viewStartDate);
                                const viewEnd = new Date(viewEndDate);

                                if (aEnd < viewStart || aStart > viewEnd) {
                                  return null;
                                }

                                // Calculate bar position
                                const rangeStart = new Date(viewStartDate);
                                const startDate = aStart < rangeStart ? rangeStart : aStart;
                                const endDate = aEnd > viewEnd ? viewEnd : aEnd;

                                const totalDays = days.length;
                                const startDayOffset = Math.floor((startDate - rangeStart) / (1000 * 60 * 60 * 24));
                                const endDayOffset = Math.floor((endDate - rangeStart) / (1000 * 60 * 60 * 24));

                                const left = ((startDayOffset + 0.5) / totalDays) * 100;
                                const width = ((endDayOffset - startDayOffset) / totalDays) * 100;

                                // Color by type: BLUE for active, GREEN for scheduled
                                const barColor = activity.type === 'active'
                                  ? 'bg-gradient-to-br from-blue-500 to-blue-600 border-blue-700'
                                  : 'bg-gradient-to-br from-green-400 to-green-500 border-green-600';

                                return (
                                  <div
                                    key={`existing-${idx}`}
                                    className={`absolute ${barColor} border-2 rounded-lg shadow-md text-white text-xs font-semibold overflow-hidden px-2 flex items-center`}
                                    style={{
                                      left: `${left}%`,
                                      width: `${width}%`,
                                      minWidth: '60px',
                                      top: '8px',
                                      height: '20px',
                                      zIndex: 5
                                    }}
                                    title={`${activity.type === 'active' ? 'ACTIVE' : 'SCHEDULED'}: ${activity.make} ${activity.model}\n${activity.start.toLocaleDateString()} - ${activity.end.toLocaleDateString()}`}
                                  >
                                    <span className="truncate text-[10px]">
                                      {activity.type === 'active' ? '🔵 ' : '🤖 '}
                                      {activity.make} {activity.model}
                                    </span>
                                  </div>
                                );
                              });
                            })()}

                            {/* NEW Chain vehicles - stair-stepped in groups of 3 */}
                            {chain && chain.chain.map((vehicle, idx) => {
                              // Parse dates as local (avoid timezone shift)
                              const [sYear, sMonth, sDay] = vehicle.start_date.split('-').map(Number);
                              const [eYear, eMonth, eDay] = vehicle.end_date.split('-').map(Number);
                              const vStart = new Date(sYear, sMonth - 1, sDay);
                              const vEnd = new Date(eYear, eMonth - 1, eDay);

                              // Only show if vehicle overlaps with current view
                              const viewStart = new Date(viewStartDate);
                              const viewEnd = new Date(viewEndDate);

                              if (vEnd < viewStart || vStart > viewEnd) {
                                return null; // Outside current month view
                              }

                              // Calculate bar position - COPY EXACT logic from Calendar.jsx
                              const rangeStart = new Date(viewStartDate);
                              const rangeEnd = new Date(viewEndDate);

                              // Clamp to view range boundaries
                              const startDate = vStart < rangeStart ? rangeStart : vStart;
                              const endDate = vEnd > rangeEnd ? rangeEnd : vEnd;

                              // Calculate position as percentage based on days from range start
                              const totalDays = days.length;
                              const startDayOffset = Math.floor((startDate - rangeStart) / (1000 * 60 * 60 * 24));
                              const endDayOffset = Math.floor((endDate - rangeStart) / (1000 * 60 * 60 * 24));

                              // Center bars on start/end dates (0.5 offset to bisect the day squares)
                              const left = ((startDayOffset + 0.5) / totalDays) * 100;
                              const width = ((endDayOffset - startDayOffset) / totalDays) * 100;

                              // Repeating stair-step pattern (groups of 3)
                              // Start below existing activities (existing at top=8, so start chain at top=40)
                              // Position 0: top=40, Position 1: top=68, Position 2: top=96
                              // Position 3: top=40 (REPEAT), Position 4: top=68, etc.
                              const positionInGroup = idx % 3; // 0, 1, 2, then repeats
                              const top = 40 + (positionInGroup * 28); // Start at 40 to leave room for existing activities

                              // Use GREEN for chain recommendations (consistent with calendar)
                              const barColor = 'bg-gradient-to-br from-green-400 to-green-500 border-green-600';

                              return (
                                <div
                                  key={vehicle.slot}
                                  className={`absolute ${barColor} border-2 rounded-lg shadow-lg hover:shadow-xl transition-all cursor-pointer px-2 flex items-center text-white text-xs font-semibold overflow-hidden`}
                                  style={{
                                    left: `${left}%`,
                                    width: `${width}%`,
                                    minWidth: '80px',
                                    top: `${top}px`,
                                    height: '24px' // Thicker bars - more readable
                                  }}
                                  title={`Slot ${vehicle.slot}: ${vehicle.make} ${vehicle.model}\n${vehicle.start_date} - ${vehicle.end_date}\nScore: ${vehicle.score}, Tier: ${vehicle.tier}`}
                                >
                                  <span className="truncate text-[11px]">
                                    {vehicle.make} {vehicle.model}
                                  </span>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      </>
                    );
                  })()}
                </div>

                <div className="mt-3 text-xs text-gray-500 flex items-center gap-2">
                  <span className="inline-block w-3 h-3 bg-green-400 border-2 border-green-600 rounded"></span>
                  <span>Green bars = Proposed chain recommendations</span>
                  <span className="ml-4">Use arrows to navigate months</span>
                </div>
              </div>

              {/* Vehicle Details List - only show if chain exists */}
              {chain && (
                <div className="bg-white rounded-lg shadow-sm border p-6">
                  <h3 className="text-md font-semibold text-gray-900 mb-4">Vehicle Details</h3>
                  <div className="space-y-3">
                    {chain.chain.map((vehicle) => (
                    <div
                      key={vehicle.slot}
                      className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-3">
                            <span className="text-lg font-semibold text-gray-900">Slot {vehicle.slot}</span>
                            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                              vehicle.tier === 'A+' ? 'bg-purple-100 text-purple-800' :
                              vehicle.tier === 'A' ? 'bg-blue-100 text-blue-800' :
                              vehicle.tier === 'B' ? 'bg-green-100 text-green-800' :
                              'bg-gray-100 text-gray-800'
                            }`}>
                              {vehicle.tier}
                            </span>
                          </div>
                          <h4 className="text-base font-medium text-gray-900 mt-2">
                            {vehicle.year} {vehicle.make} {vehicle.model}
                          </h4>
                          <p className="text-sm text-gray-500 font-mono">{vehicle.vin}</p>
                          <div className="flex items-center gap-4 mt-2 text-sm text-gray-600">
                            <span>{vehicle.start_date} to {vehicle.end_date}</span>
                            <span>Score: {vehicle.score}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow-sm border p-12">
              <div className="text-center">
                <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                <p className="mt-2 text-sm text-gray-500">No chain generated yet</p>
                <p className="text-xs text-gray-400 mt-1">Select a partner and click "Generate Chain" to see suggestions</p>
              </div>
            </div>
          )}
        </div>

        {/* Right Panel - Info */}
        <div className="w-80 bg-white border-l p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">Chain Info</h2>

          <div className="space-y-4 text-sm">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h3 className="font-medium text-blue-900 mb-2">What is Chain Builder?</h3>
              <p className="text-blue-700 text-xs">
                Quickly create 4-6 back-to-back vehicle assignments for a single media partner.
                The system suggests vehicles they haven't reviewed, sequentially available.
              </p>
            </div>

            <div className="space-y-2">
              <h3 className="font-medium text-gray-700">Business Rules</h3>
              <div className="text-xs text-gray-600 space-y-1">
                <div className="flex items-start gap-2">
                  <span className="text-green-600">✓</span>
                  <span>Excludes vehicles partner has already reviewed</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-green-600">✓</span>
                  <span>Enforces 30-day model cooldown (no duplicate models)</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-green-600">✓</span>
                  <span>Checks sequential availability across weeks</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-green-600">✓</span>
                  <span>Prioritizes by partner tier ranking (A+, A, B, C)</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-green-600">✓</span>
                  <span>Weekday pickups/dropoffs only (Mon-Fri)</span>
                </div>
              </div>
            </div>

            {chain && (
              <div className="pt-4 border-t">
                <h3 className="font-medium text-gray-700 mb-2">Chain Summary</h3>
                <div className="text-xs text-gray-600 space-y-1">
                  <div className="flex justify-between">
                    <span>Total Vehicles:</span>
                    <span className="font-medium">{chain.chain.length}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Total Duration:</span>
                    <span className="font-medium">{chain.chain_params.total_span_days} days</span>
                  </div>
                  <div className="flex justify-between">
                    <span>VINs Excluded:</span>
                    <span className="font-medium">{chain.constraints_applied.excluded_vins}</span>
                  </div>
                  {chain.slot_availability && (
                    <div className="mt-3 pt-3 border-t">
                      <div className="font-medium mb-1">Availability per Slot:</div>
                      {chain.slot_availability.map(slot => (
                        <div key={slot.slot} className="flex justify-between text-xs">
                          <span>Slot {slot.slot}:</span>
                          <span>{slot.available_count} vehicles</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default ChainBuilder;
