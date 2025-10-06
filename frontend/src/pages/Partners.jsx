import { useState, useEffect, Fragment } from 'react'
import { Listbox, Transition } from '@headlessui/react'

export default function Partners({ office }) {
  const [allPartners, setAllPartners] = useState([])
  const [selectedPartner, setSelectedPartner] = useState(null)
  const [partnerIntelligence, setPartnerIntelligence] = useState(null)
  const [selectedDate, setSelectedDate] = useState('')
  const [candidates, setCandidates] = useState([])
  const [loading, setLoading] = useState(false)
  const [loadingPartners, setLoadingPartners] = useState(false)
  const [loadingIntelligence, setLoadingIntelligence] = useState(false)
  const [scheduling, setScheduling] = useState(false)
  const [message, setMessage] = useState('')

  // Load all partners on mount
  useEffect(() => {
    if (office) {
      loadAllPartners()
    }
  }, [office])

  // Get Monday of current week as default
  useEffect(() => {
    const today = new Date()
    const monday = new Date(today)
    monday.setDate(today.getDate() - today.getDay() + (today.getDay() === 0 ? -6 : 1))
    setSelectedDate(monday.toISOString().split('T')[0])
  }, [])

  // Load partner intelligence when partner is selected
  useEffect(() => {
    if (selectedPartner && office) {
      loadPartnerIntelligence()
    } else {
      setPartnerIntelligence(null)
    }
  }, [selectedPartner, office])

  const loadAllPartners = async () => {
    setLoadingPartners(true)
    try {
      const response = await fetch(`http://localhost:8081/ingest/partners/search?office=${encodeURIComponent(office)}&query=`)
      if (response.ok) {
        const data = await response.json()
        const sorted = (data.partners || []).sort((a, b) => a.name.localeCompare(b.name))
        setAllPartners(sorted)
      }
    } catch (error) {
      console.error('Error loading partners:', error)
    } finally {
      setLoadingPartners(false)
    }
  }

  const loadPartnerIntelligence = async () => {
    if (!selectedPartner) return

    setLoadingIntelligence(true)
    try {
      const response = await fetch(
        `http://localhost:8081/api/ui/phase7/partner-intelligence?person_id=${selectedPartner.person_id}&office=${office}`
      )
      if (response.ok) {
        const data = await response.json()
        if (data.success) {
          setPartnerIntelligence(data)
        }
      }
    } catch (error) {
      console.error('Error loading partner intelligence:', error)
    } finally {
      setLoadingIntelligence(false)
    }
  }

  const handlePartnerChange = (partner) => {
    setSelectedPartner(partner)
    setCandidates([])
    setMessage('')
  }

  const handleFindVehicles = async () => {
    if (!selectedPartner || !selectedDate) {
      setMessage('Please select a partner and date')
      return
    }

    setLoading(true)
    setMessage('')

    try {
      const response = await fetch(
        `http://localhost:8081/api/ui/phase7/partner-day-candidates?person_id=${selectedPartner.person_id}&date=${selectedDate}&office=${office}`
      )

      if (response.ok) {
        const data = await response.json()
        if (data.success) {
          setCandidates(data.candidates || [])
          if (data.candidates.length === 0) {
            setMessage(data.message || 'No vehicles available for this date')
          }
        } else {
          setMessage(data.message || 'Error fetching candidates')
        }
      } else {
        setMessage('Error fetching vehicle candidates')
      }
    } catch (error) {
      console.error('Error:', error)
      setMessage('Network error fetching candidates')
    } finally {
      setLoading(false)
    }
  }

  const handleScheduleVehicle = async (candidate) => {
    if (!window.confirm(`Schedule ${candidate.make} ${candidate.model} to ${selectedPartner.name} on ${selectedDate}?`)) {
      return
    }

    setScheduling(true)

    try {
      const date = new Date(selectedDate)
      const monday = new Date(date)
      monday.setDate(date.getDate() - date.getDay() + (date.getDay() === 0 ? -6 : 1))
      const weekStart = monday.toISOString().split('T')[0]

      const response = await fetch('http://localhost:8081/api/calendar/schedule-assignment', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          vin: candidate.vin,
          person_id: selectedPartner.person_id,
          start_day: selectedDate,
          office: office,
          week_start: weekStart,
          partner_name: selectedPartner.name,
          make: candidate.make,
          model: candidate.model
        })
      })

      const result = await response.json()

      if (result.success) {
        setMessage(`✅ Successfully scheduled ${candidate.make} ${candidate.model} to ${selectedPartner.name}!`)
        handleFindVehicles() // Refresh candidates
        loadPartnerIntelligence() // Refresh intelligence data
      } else {
        setMessage(`❌ ${result.message}`)
      }
    } catch (error) {
      console.error('Error scheduling:', error)
      setMessage('❌ Network error scheduling assignment')
    } finally {
      setScheduling(false)
    }
  }

  const getTierBadgeColor = (rank) => {
    switch(rank) {
      case 1: return 'bg-yellow-100 text-yellow-800 border-yellow-300'
      case 2: return 'bg-blue-100 text-blue-800 border-blue-300'
      case 3: return 'bg-green-100 text-green-800 border-green-300'
      case 4: return 'bg-gray-100 text-gray-800 border-gray-300'
      default: return 'bg-gray-100 text-gray-800 border-gray-300'
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b border-gray-200 mb-6">
        <div className="max-w-[1800px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="md:flex md:items-center md:justify-between">
            <div className="flex-1 min-w-0">
              <h2 className="text-3xl font-bold leading-7 text-gray-900 sm:text-3xl sm:truncate">
                👥 Partner Scheduling
              </h2>
              <p className="mt-2 text-sm text-gray-600">
                Select a partner to view intelligence and schedule vehicles
              </p>
            </div>
            {office && (
              <div className="mt-4 flex md:mt-0 md:ml-4">
                <span className="inline-flex items-center px-4 py-2 rounded-md text-sm font-medium bg-blue-100 text-blue-800">
                  📍 Office: {office}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="max-w-[1800px] mx-auto px-4 sm:px-6 lg:px-8">
        {/* Office warning */}
        {!office && (
          <div className="rounded-md bg-yellow-50 border border-yellow-200 p-4 mb-6">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-yellow-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <h3 className="text-sm font-medium text-yellow-800">
                  Office Required
                </h3>
                <div className="mt-2 text-sm text-yellow-700">
                  <p>Please select an office from the Optimizer tab first to use Partner Scheduling.</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Partner Selection */}
        <div className="bg-white shadow rounded-lg p-6 mb-6">
          <Listbox value={selectedPartner} onChange={handlePartnerChange} disabled={!office || loadingPartners}>
            <Listbox.Label className="block text-sm font-medium text-gray-700 mb-2">
              Select Partner
            </Listbox.Label>
            <div className="relative">
              <Listbox.Button className="relative w-full cursor-pointer rounded-lg bg-white py-3 pl-4 pr-10 text-left border-2 border-gray-300 shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all duration-200 hover:border-gray-400">
                <span className="block truncate font-medium text-gray-900">
                  {loadingPartners ? (
                    'Loading partners...'
                  ) : selectedPartner ? (
                    `${selectedPartner.name} - ${selectedPartner.address}`
                  ) : (
                    <span className="text-gray-500 font-normal">Select a partner...</span>
                  )}
                </span>
                <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3">
                  <svg className="h-5 w-5 text-indigo-600" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
                  </svg>
                </span>
              </Listbox.Button>

              <Transition
                as={Fragment}
                leave="transition ease-in duration-100"
                leaveFrom="opacity-100"
                leaveTo="opacity-0"
              >
                <Listbox.Options className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-lg bg-white py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
                  {allPartners.map((partner) => (
                    <Listbox.Option
                      key={partner.person_id}
                      value={partner}
                      className={({ active }) =>
                        `relative cursor-pointer select-none py-3 pl-10 pr-4 ${
                          active ? 'bg-indigo-50 text-indigo-900' : 'text-gray-900'
                        }`
                      }
                    >
                      {({ selected, active }) => (
                        <>
                          <span className={`block truncate ${selected ? 'font-semibold' : 'font-normal'}`}>
                            {partner.name} - {partner.address}
                          </span>
                          {selected ? (
                            <span className={`absolute inset-y-0 left-0 flex items-center pl-3 ${active ? 'text-indigo-600' : 'text-indigo-600'}`}>
                              <svg className="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                                <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clipRule="evenodd" />
                              </svg>
                            </span>
                          ) : null}
                        </>
                      )}
                    </Listbox.Option>
                  ))}
                </Listbox.Options>
              </Transition>
            </div>
          </Listbox>
          {allPartners.length > 0 && (
            <p className="mt-2 text-sm text-gray-500">
              {allPartners.length} partners available in {office}
            </p>
          )}
        </div>

        {/* Two Column Layout - 1/3 Sidebar, 2/3 Calendar */}
        {selectedPartner && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* LEFT SIDEBAR - Partner Intelligence */}
            <div className="lg:col-span-1 space-y-6">
              {loadingIntelligence ? (
                <div className="bg-white rounded-lg shadow p-6">
                  <div className="animate-pulse flex space-x-4">
                    <div className="flex-1 space-y-4 py-1">
                      <div className="h-4 bg-gray-200 rounded w-3/4"></div>
                      <div className="space-y-2">
                        <div className="h-4 bg-gray-200 rounded"></div>
                        <div className="h-4 bg-gray-200 rounded w-5/6"></div>
                      </div>
                    </div>
                  </div>
                </div>
              ) : partnerIntelligence ? (
                <>
                  {/* Partner Stats Card */}
                  <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg shadow border border-blue-200 p-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">📊 Partner Stats</h3>
                    <div className="space-y-3">
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">Total Loans:</span>
                        <span className="text-sm font-semibold text-gray-900">{partnerIntelligence.stats.total_loans}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">Publication Rate:</span>
                        <span className="text-sm font-semibold text-gray-900">
                          {(partnerIntelligence.stats.publication_rate * 100).toFixed(1)}%
                        </span>
                      </div>
                      {partnerIntelligence.stats.last_loan_date && (
                        <div className="flex justify-between">
                          <span className="text-sm text-gray-600">Last Loan:</span>
                          <span className="text-sm font-semibold text-gray-900">
                            {new Date(partnerIntelligence.stats.last_loan_date).toLocaleDateString()}
                          </span>
                        </div>
                      )}
                      {partnerIntelligence.stats.cooldown_active && (
                        <div className="mt-3 pt-3 border-t border-blue-200">
                          <div className="flex items-center text-orange-700">
                            <svg className="h-4 w-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
                            </svg>
                            <span className="text-sm font-medium">
                              Cooldown until {new Date(partnerIntelligence.stats.cooldown_until).toLocaleDateString()}
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Approved Makes */}
                  <div className="bg-white rounded-lg shadow p-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">🚗 Approved Makes</h3>
                    <div className="flex flex-wrap gap-2">
                      {partnerIntelligence.approved_makes.map((item) => (
                        <span
                          key={item.make}
                          className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium border ${getTierBadgeColor(item.rank)}`}
                        >
                          {item.make}
                          <span className="ml-1.5 text-xs">T{item.rank}</span>
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Vehicle Search - Moved to Left */}
                  <div className="bg-white rounded-lg shadow p-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">🔍 Find & Schedule</h3>
                    <div className="space-y-3">
                      <div>
                        <label htmlFor="target-date-left" className="block text-sm font-medium text-gray-700 mb-2">
                          Target Date
                        </label>
                        <input
                          id="target-date-left"
                          type="date"
                          value={selectedDate}
                          onChange={(e) => setSelectedDate(e.target.value)}
                          className="block w-full px-3 py-2 text-sm border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 rounded-md"
                        />
                      </div>
                      <button
                        onClick={handleFindVehicles}
                        disabled={loading || !selectedDate}
                        className="w-full inline-flex justify-center items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:bg-gray-400 disabled:cursor-not-allowed"
                      >
                        {loading ? 'Loading...' : 'Find Vehicles'}
                      </button>
                    </div>
                  </div>

                  {/* Compact Timeline View */}
                  <div className="bg-white rounded-lg shadow p-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">📋 Quick View</h3>
                    <div className="space-y-2">
                      {/* Combine recent loans and upcoming assignments for timeline */}
                      {(() => {
                        const timeline = [];
                        const today = new Date();

                        // Add recent loans (past 4 weeks)
                        partnerIntelligence.recent_loans.slice(0, 5).forEach(loan => {
                          if (loan.start_date) {
                            const startDate = new Date(loan.start_date);
                            const endDate = loan.end_date ? new Date(loan.end_date) : new Date(startDate.getTime() + 7 * 24 * 60 * 60 * 1000);
                            const isPast = endDate < today;

                            timeline.push({
                              type: 'past',
                              make: loan.make,
                              start: startDate,
                              end: endDate,
                              published: loan.published,
                              sortDate: startDate
                            });
                          }
                        });

                        // Add current active loans
                        partnerIntelligence.current_loans.forEach(loan => {
                          timeline.push({
                            type: 'active',
                            vin: loan.vehicle_vin,
                            start: new Date(loan.start_date),
                            end: new Date(loan.end_date),
                            sortDate: new Date(loan.start_date)
                          });
                        });

                        // Add upcoming scheduled assignments
                        partnerIntelligence.upcoming_assignments.slice(0, 8).forEach(assignment => {
                          timeline.push({
                            type: 'scheduled',
                            make: assignment.make,
                            model: assignment.model,
                            start: new Date(assignment.start_day),
                            end: new Date(assignment.end_day),
                            status: assignment.status,
                            sortDate: new Date(assignment.start_day)
                          });
                        });

                        // Sort by date
                        timeline.sort((a, b) => b.sortDate - a.sortDate);

                        return timeline.slice(0, 12).map((item, idx) => (
                          <div
                            key={idx}
                            className={`rounded-lg p-3 border ${
                              item.type === 'past'
                                ? 'bg-gray-50 border-gray-200'
                                : item.type === 'active'
                                ? 'bg-green-50 border-green-300'
                                : item.status === 'manual'
                                ? 'bg-blue-50 border-blue-200'
                                : 'bg-indigo-50 border-indigo-200'
                            }`}
                          >
                            <div className="flex items-start justify-between">
                              <div className="flex-1">
                                <div className="flex items-center gap-2">
                                  <span className={`text-sm font-medium ${
                                    item.type === 'past' ? 'text-gray-600' : 'text-gray-900'
                                  }`}>
                                    {item.make || `VIN ...${item.vin?.slice(-6)}`} {item.model || ''}
                                  </span>
                                  {item.type === 'scheduled' && (
                                    <span className={`text-xs px-1.5 py-0.5 rounded ${
                                      item.status === 'manual'
                                        ? 'bg-blue-200 text-blue-800'
                                        : 'bg-indigo-200 text-indigo-800'
                                    }`}>
                                      {item.status === 'manual' ? 'M' : 'O'}
                                    </span>
                                  )}
                                  {item.type === 'past' && item.published && (
                                    <svg className="h-3 w-3 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                                    </svg>
                                  )}
                                </div>
                                <div className="text-xs text-gray-500 mt-1">
                                  {item.start.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} - {item.end.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                                </div>
                              </div>
                              {item.type === 'active' && (
                                <span className="text-xs font-medium text-green-700">Active</span>
                              )}
                            </div>
                          </div>
                        ));
                      })()}
                    </div>
                  </div>
                </>
              ) : null}
            </div>

            {/* RIGHT PANE - Calendar Grid View (2/3 width) */}
            <div className="lg:col-span-2 space-y-6">
              {loadingIntelligence ? (
                <div className="bg-white rounded-lg shadow p-6">
                  <div className="animate-pulse">
                    <div className="h-8 bg-gray-200 rounded w-1/3 mb-4"></div>
                    <div className="space-y-3">
                      <div className="h-16 bg-gray-200 rounded"></div>
                      <div className="h-16 bg-gray-200 rounded"></div>
                      <div className="h-16 bg-gray-200 rounded"></div>
                    </div>
                  </div>
                </div>
              ) : partnerIntelligence ? (
                <div className="bg-white shadow rounded-lg p-6 overflow-x-auto">
                  <h3 className="text-lg font-medium text-gray-900 mb-4">📅 {partnerIntelligence.partner.name}'s Calendar</h3>

                  {/* Calendar Grid */}
                  {(() => {
                    const today = new Date();
                    const currentMonth = today.getMonth();
                    const currentYear = today.getFullYear();
                    const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();

                    // Collect all assignments for this month
                    const assignments = [];

                    // Recent loans
                    partnerIntelligence.recent_loans.forEach(loan => {
                      if (loan.start_date) {
                        const start = new Date(loan.start_date);
                        const end = loan.end_date ? new Date(loan.end_date) : new Date(start.getTime() + 7 * 24 * 60 * 60 * 1000);

                        if (start.getMonth() === currentMonth && start.getFullYear() === currentYear) {
                          assignments.push({
                            type: 'past',
                            make: loan.make,
                            start,
                            end,
                            published: loan.published
                          });
                        }
                      }
                    });

                    // Active loans
                    partnerIntelligence.current_loans.forEach(loan => {
                      const start = new Date(loan.start_date);
                      const end = new Date(loan.end_date);

                      if ((start.getMonth() === currentMonth && start.getFullYear() === currentYear) ||
                          (end.getMonth() === currentMonth && end.getFullYear() === currentYear) ||
                          (start < new Date(currentYear, currentMonth, 1) && end > new Date(currentYear, currentMonth + 1, 0))) {
                        assignments.push({
                          type: 'active',
                          vin: loan.vehicle_vin,
                          make: loan.make,
                          model: loan.model,
                          start,
                          end,
                          status: 'active'
                        });
                      }
                    });

                    // Scheduled assignments
                    partnerIntelligence.upcoming_assignments.forEach(assignment => {
                      const start = new Date(assignment.start_day);
                      const end = new Date(assignment.end_day);

                      if ((start.getMonth() === currentMonth && start.getFullYear() === currentYear) ||
                          (end.getMonth() === currentMonth && end.getFullYear() === currentYear) ||
                          (start < new Date(currentYear, currentMonth, 1) && end > new Date(currentYear, currentMonth + 1, 0))) {
                        assignments.push({
                          type: 'scheduled',
                          make: assignment.make,
                          model: assignment.model,
                          status: assignment.status,
                          start,
                          end
                        });
                      }
                    });

                    return (
                      <div className="min-w-[800px]">
                        {/* Header Row - Day Numbers */}
                        <div className="flex border-b-2 border-gray-300">
                          <div className="w-32 flex-shrink-0 p-2 font-semibold text-sm text-gray-700">
                            {today.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
                          </div>
                          {Array.from({ length: daysInMonth }, (_, i) => {
                            const day = i + 1;
                            const date = new Date(currentYear, currentMonth, day);
                            const isToday = date.toDateString() === today.toDateString();

                            return (
                              <div
                                key={day}
                                className={`flex-1 min-w-[30px] text-center p-1 text-xs font-medium ${
                                  isToday ? 'bg-blue-100 text-blue-900' : 'text-gray-600'
                                }`}
                              >
                                {day}
                              </div>
                            );
                          })}
                        </div>

                        {/* Assignment Rows */}
                        <div className="relative h-48">
                          {assignments.map((assign, idx) => {
                            const startDay = assign.start.getDate();
                            const endDay = assign.end.getDate();
                            const startMonth = assign.start.getMonth();
                            const endMonth = assign.end.getMonth();

                            // Calculate position
                            const actualStartDay = startMonth < currentMonth ? 1 : startDay;
                            const actualEndDay = endMonth > currentMonth ? daysInMonth : endDay;
                            const dayWidth = 100 / daysInMonth;
                            const left = (actualStartDay - 0.5) * dayWidth;
                            const width = (actualEndDay - actualStartDay) * dayWidth;
                            const top = (idx % 5) * 32 + 16;

                            // Match Calendar.jsx color scheme exactly
                            let barColor;
                            if (assign.type === 'past') {
                              barColor = 'bg-gradient-to-br from-gray-400 to-gray-500 border-2 border-gray-600';
                            } else if (assign.type === 'active') {
                              barColor = 'bg-gradient-to-br from-blue-500 to-blue-600 border-2 border-blue-700';
                            } else {
                              // scheduled (planned)
                              barColor = 'bg-gradient-to-br from-green-400 to-green-500 border-2 border-green-600';
                            }

                            // Label: Always show Make/Model if available, otherwise VIN as fallback
                            let label = '';
                            if (assign.make) {
                              label = assign.model ? `${assign.make} ${assign.model}` : assign.make;
                            } else if (assign.vin) {
                              label = `VIN ...${assign.vin.slice(-6)}`;
                            } else {
                              label = 'Vehicle';
                            }

                            return (
                              <div
                                key={idx}
                                className={`absolute h-7 ${barColor} rounded-lg shadow-lg hover:shadow-xl hover:scale-105 transition-all cursor-pointer px-2 flex items-center text-white text-xs font-semibold overflow-hidden whitespace-nowrap`}
                                style={{
                                  left: `calc(8rem + ${left}%)`,
                                  width: `${width}%`,
                                  minWidth: '20px',
                                  top: `${top}px`
                                }}
                                title={`${assign.make || 'Vehicle'} ${assign.model || ''} ${assign.vin ? `(VIN: ${assign.vin})` : ''}\n${assign.start.toLocaleDateString()} - ${assign.end.toLocaleDateString()}\n${assign.status === 'manual' ? 'Manual Assignment' : 'Optimizer Assignment'}`}
                              >
                                <span className="truncate">{label}</span>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })()}
                </div>
              ) : null}

              {/* Message */}
              {message && (
                <div className={`rounded-md p-4 ${
                  message.includes('✅')
                    ? 'bg-green-50 border border-green-200'
                    : 'bg-yellow-50 border border-yellow-200'
                }`}>
                  <p className={`text-sm ${message.includes('✅') ? 'text-green-800' : 'text-yellow-800'}`}>
                    {message}
                  </p>
                </div>
              )}

              {/* Vehicle Candidates List */}
              {candidates.length > 0 && (
                <div className="bg-white shadow rounded-lg p-6">
                  <div className="mb-4">
                    <h3 className="text-lg font-medium text-gray-900">
                      🚗 Available Vehicles for {selectedDate}
                    </h3>
                    <p className="mt-1 text-sm text-gray-600">
                      Found {candidates.length} available vehicle{candidates.length !== 1 ? 's' : ''} ranked by score
                    </p>
                  </div>

                  <div className="space-y-4">
                    {candidates.map((candidate, idx) => (
                      <div
                        key={idx}
                        className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow duration-200"
                      >
                        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
                          <div className="flex-1">
                            <div className="flex items-center mb-2">
                              <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-blue-100 text-blue-800 text-sm font-semibold mr-3">
                                {idx + 1}
                              </span>
                              <h4 className="text-lg font-semibold text-gray-900">
                                {candidate.make} {candidate.model} {candidate.year}
                              </h4>
                            </div>
                            <div className="ml-11 space-y-1">
                              <div className="flex flex-wrap gap-3 text-sm text-gray-600">
                                <span className="inline-flex items-center">
                                  🔖 VIN: ...{candidate.vin.slice(-6)}
                                </span>
                                <span className="inline-flex items-center">
                                  ⭐ Score: <strong className="ml-1 text-gray-900">{candidate.score}</strong>
                                </span>
                                <span className="inline-flex items-center">
                                  🏆 Rank {candidate.rank}
                                </span>
                              </div>
                              <div className="text-xs text-gray-500">
                                Base Score: {candidate.base_score} + Publication Bonus: {candidate.pub_bonus}
                              </div>
                            </div>
                          </div>
                          <div className="mt-4 sm:mt-0 sm:ml-4">
                            <button
                              onClick={() => handleScheduleVehicle(candidate)}
                              disabled={scheduling}
                              className="w-full sm:w-auto inline-flex justify-center items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:bg-gray-400 disabled:cursor-not-allowed"
                            >
                              ✅ Schedule This
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
