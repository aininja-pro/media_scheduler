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

  // Load offices and partners
  const [offices, setOffices] = useState([]);
  const [partners, setPartners] = useState([]);

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
        const response = await fetch(`http://localhost:8081/api/ui/phase7/overview?office=${encodeURIComponent(selectedOffice)}&week_start=2025-10-20&min_days=7`);
        if (!response.ok) return;

        const data = await response.json();
        // For now, we'll load a simple partner list
        // In Commit 7, we'll integrate with proper partner endpoint
        setPartners([
          { person_id: 1601, name: 'Karl Brauer' },
          { person_id: 1602, name: 'Partner 1602' }
        ]);
      } catch (err) {
        console.error('Failed to load partners:', err);
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
            {/* Partner Selector */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Media Partner
              </label>
              <select
                value={selectedPartner}
                onChange={(e) => setSelectedPartner(e.target.value)}
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select a partner...</option>
                {partners.map(partner => (
                  <option key={partner.person_id} value={partner.person_id}>
                    {partner.name}
                  </option>
                ))}
              </select>
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
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-gray-500 mt-1">Must be a weekday (Mon-Fri)</p>
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

          {chain ? (
            <div className="bg-white rounded-lg shadow-sm border p-6">
              <div className="mb-4">
                <h3 className="text-lg font-medium text-gray-900">{chain.partner_info.name}</h3>
                <p className="text-sm text-gray-500">
                  {chain.chain_params.start_date} - {chain.chain[chain.chain.length - 1]?.end_date} ({chain.chain_params.total_span_days} days)
                </p>
              </div>

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

              {/* Summary Stats */}
              <div className="mt-6 pt-6 border-t">
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <div className="text-2xl font-semibold text-gray-900">{chain.chain.length}</div>
                    <div className="text-xs text-gray-500">Vehicles</div>
                  </div>
                  <div>
                    <div className="text-2xl font-semibold text-gray-900">{chain.constraints_applied.excluded_vins}</div>
                    <div className="text-xs text-gray-500">Excluded</div>
                  </div>
                  <div>
                    <div className="text-2xl font-semibold text-gray-900">{chain.chain_params.total_span_days}</div>
                    <div className="text-xs text-gray-500">Days</div>
                  </div>
                </div>
              </div>
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
