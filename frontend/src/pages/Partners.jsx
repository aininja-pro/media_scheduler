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
  const [selectedMonth, setSelectedMonth] = useState('')
  const [selectedPartnerId, setSelectedPartnerId] = useState(null)
  const [partnerContext, setPartnerContext] = useState(null)
  const [loadingPartnerContext, setLoadingPartnerContext] = useState(false)
  const [partnerSearchQuery, setPartnerSearchQuery] = useState('')

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

  // Set current month as default for calendar
  useEffect(() => {
    const now = new Date()
    const year = now.getFullYear()
    const month = String(now.getMonth() + 1).padStart(2, '0')
    setSelectedMonth(`${year}-${month}`)
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

  const handleBarClick = async () => {
    if (!selectedPartner || !partnerIntelligence) return;

    setSelectedPartnerId(selectedPartner.person_id)
    setLoadingPartnerContext(true)

    try {
      // Build context from partnerIntelligence data
      const context = {
        person_id: selectedPartner.person_id,
        partner_name: partnerIntelligence.partner.name,
        office: partnerIntelligence.partner.office,
        region: 'N/A',
        partner_address: partnerIntelligence.partner.address || 'N/A',
        distance_info: null,
        current_loans: partnerIntelligence.current_loans.map(loan => ({
          vin: loan.vehicle_vin,
          make: loan.make,
          model: loan.model,
          start_date: loan.start_date,
          end_date: loan.end_date,
          status: 'active'
        })),
        recommended_loans: partnerIntelligence.upcoming_assignments.map(assignment => ({
          vin: assignment.vin,
          make: assignment.make,
          model: assignment.model,
          start_date: assignment.start_day,
          end_date: assignment.end_day,
          status: assignment.status
        })),
        timeline: [
          ...partnerIntelligence.recent_loans.map(loan => ({
            make: loan.make,
            model: '',
            start_date: loan.start_date,
            end_date: loan.end_date,
            status: 'completed'
          })),
          ...partnerIntelligence.current_loans.map(loan => ({
            make: loan.make,
            model: loan.model,
            start_date: loan.start_date,
            end_date: loan.end_date,
            status: 'active'
          })),
          ...partnerIntelligence.upcoming_assignments.map(assignment => ({
            make: assignment.make,
            model: assignment.model,
            start_date: assignment.start_day,
            end_date: assignment.end_day,
            status: 'planned'
          }))
        ]
      }

      setPartnerContext(context)
    } catch (error) {
      console.error('Error building partner context:', error)
      setPartnerContext(null)
    } finally {
      setLoadingPartnerContext(false)
    }
  }

  const closeSidePanel = () => {
    setSelectedPartnerId(null)
    setPartnerContext(null)
  }

  const formatActivityDate = (dateStr) => {
    if (!dateStr) return 'N/A'
    try {
      const date = new Date(dateStr)
      if (isNaN(date.getTime())) return 'Invalid Date'
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    } catch {
      return 'Invalid Date'
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
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Select Partner
          </label>

          <Listbox value={selectedPartner} onChange={handlePartnerChange} disabled={!office || loadingPartners}>
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
                <Listbox.Options className="absolute z-10 mt-1 w-full rounded-lg bg-white text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
                  {/* Search input inside dropdown */}
                  <div className="sticky top-0 bg-white p-2 border-b border-gray-200">
                    <input
                      type="text"
                      placeholder="Type to search..."
                      value={partnerSearchQuery}
                      onChange={(e) => setPartnerSearchQuery(e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                      className="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>

                  {/* Scrollable partner list */}
                  <div className="max-h-60 overflow-auto py-1">
                    {allPartners
                      .filter(partner =>
                        partner.name.toLowerCase().includes(partnerSearchQuery.toLowerCase()) ||
                        partner.address?.toLowerCase().includes(partnerSearchQuery.toLowerCase())
                      )
                      .map((partner) => (
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
                    {allPartners.filter(partner =>
                      partner.name.toLowerCase().includes(partnerSearchQuery.toLowerCase()) ||
                      partner.address?.toLowerCase().includes(partnerSearchQuery.toLowerCase())
                    ).length === 0 && (
                      <div className="px-4 py-6 text-center text-sm text-gray-500">
                        No partners found matching "{partnerSearchQuery}"
                      </div>
                    )}
                  </div>
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
                  {/* Calendar Header with Month Selector */}
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-medium text-gray-900">📅 {partnerIntelligence.partner.name}'s Calendar</h3>
                    <div className="flex items-center gap-2">
                      <label className="text-sm font-medium text-gray-700">Month:</label>
                      <input
                        type="month"
                        value={selectedMonth}
                        onChange={(e) => setSelectedMonth(e.target.value)}
                        className="border border-gray-300 rounded-md px-3 py-1 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      />
                    </div>
                  </div>

                  {/* Calendar Grid */}
                  {(() => {
                    if (!selectedMonth) return null;

                    const [year, month] = selectedMonth.split('-');
                    const currentYear = parseInt(year);
                    const currentMonth = parseInt(month) - 1; // JavaScript months are 0-indexed
                    const today = new Date();
                    const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();

                    // Collect all assignments for this month
                    const assignments = [];

                    // Don't show recent_loans in calendar - they're historical data from loan_history table
                    // Calendar tab only shows current_activity and scheduled_assignments, so we match that

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
                      <div className="min-w-[800px] border-2 rounded-lg overflow-hidden">
                        {/* Header Row - Day Numbers */}
                        <div className="flex border-b-2 border-b-gray-400 bg-gray-50">
                          <div className="w-32 flex-shrink-0 p-2 border-r font-semibold text-sm text-gray-700">
                            {new Date(currentYear, currentMonth, 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
                          </div>
                          {Array.from({ length: daysInMonth }, (_, i) => {
                            const day = i + 1;
                            const date = new Date(currentYear, currentMonth, day);
                            const dayOfWeek = date.getDay();
                            const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;

                            return (
                              <div
                                key={day}
                                className={`flex-1 text-center text-xs py-3 border-r ${
                                  isWeekend ? 'bg-blue-100 text-blue-800 font-semibold' : 'text-gray-600'
                                }`}
                              >
                                {day}
                              </div>
                            );
                          })}
                        </div>

                        {/* Assignment Rows */}
                        <div className="relative h-48 flex">
                          {/* Month label spacer - matches header width */}
                          <div className="w-32 flex-shrink-0 border-r"></div>

                          {/* Day grid area */}
                          <div className="flex-1 relative">
                            {/* Day grid with weekend backgrounds and vertical lines */}
                            <div className="absolute inset-0 flex">
                              {Array.from({ length: daysInMonth }, (_, i) => {
                                const day = i + 1;
                                const date = new Date(currentYear, currentMonth, day);
                                const dayOfWeek = date.getDay();
                                const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;

                                return (
                                  <div
                                    key={day}
                                    className={`flex-1 border-r border-gray-300 ${
                                      isWeekend ? 'bg-blue-50' : ''
                                    }`}
                                  ></div>
                                );
                              })}
                            </div>

                            {/* Assignment bars */}
                          {assignments.map((assign, idx) => {
                            const startDay = assign.start.getDate();
                            const endDay = assign.end.getDate();
                            const startMonth = assign.start.getMonth();
                            const endMonth = assign.end.getMonth();

                            // Calculate position - use same logic as Calendar.jsx
                            const actualStartDay = startMonth < currentMonth ? 1 : startDay;
                            const actualEndDay = endMonth > currentMonth ? daysInMonth : endDay;
                            const totalDays = daysInMonth;

                            // Center bars on start/end dates (0.5 offset to bisect the day squares)
                            const left = ((actualStartDay - 0.5) / totalDays) * 100;
                            const width = ((actualEndDay - actualStartDay) / totalDays) * 100;
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
                              <button
                                key={idx}
                                onClick={handleBarClick}
                                className={`absolute h-7 ${barColor} rounded-lg shadow-lg hover:shadow-xl hover:scale-105 transition-all cursor-pointer px-2 flex items-center text-white text-xs font-semibold overflow-hidden whitespace-nowrap`}
                                style={{
                                  left: `${left}%`,
                                  width: `${width}%`,
                                  minWidth: '20px',
                                  top: `${top}px`
                                }}
                                title={`${assign.make || 'Vehicle'} ${assign.model || ''} ${assign.vin ? `(VIN: ${assign.vin})` : ''}\n${assign.start.toLocaleDateString()} - ${assign.end.toLocaleDateString()}\n${assign.status === 'manual' ? 'Manual Assignment' : 'Optimizer Assignment'}`}
                              >
                                <span className="truncate">{label}</span>
                              </button>
                            );
                          })}
                          </div>
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

        {/* Partner Context Side Panel */}
        {selectedPartnerId && partnerContext && (
          <div className="fixed right-0 top-0 z-40 h-full">
            <div className="bg-white w-96 h-full shadow-2xl overflow-y-auto border-l border-gray-200">
              <div className="sticky top-0 bg-white border-b px-6 py-4 flex justify-between items-center">
                <h2 className="text-lg font-semibold text-gray-900">Partner Context</h2>
                <button
                  onClick={closeSidePanel}
                  className="text-gray-400 hover:text-gray-600 focus:outline-none"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <div className="p-6">
                {loadingPartnerContext ? (
                  <div className="flex items-center justify-center py-12">
                    <svg className="animate-spin h-8 w-8 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                  </div>
                ) : (
                  <div className="space-y-6">
                    {/* Partner Info */}
                    <div>
                      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">Partner Details</h3>
                      <div className="bg-gray-50 rounded-lg p-4 space-y-2">
                        <div className="flex justify-between">
                          <span className="text-sm text-gray-600">Name:</span>
                          <span className="text-sm font-medium text-gray-900">{partnerContext.partner_name}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-sm text-gray-600">Partner ID:</span>
                          <span className="text-sm font-mono font-medium text-gray-900">{partnerContext.person_id}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-sm text-gray-600">Office:</span>
                          <span className="text-sm font-medium text-gray-900">{partnerContext.office}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-sm text-gray-600">Region:</span>
                          <span className="text-sm font-medium text-gray-900">{partnerContext.region}</span>
                        </div>
                        {partnerContext.partner_address && partnerContext.partner_address !== 'N/A' && (
                          <div className="border-t pt-2 mt-2">
                            <div className="flex items-start">
                              <svg className="w-4 h-4 text-blue-600 mt-0.5 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clipRule="evenodd" />
                              </svg>
                              <div className="flex-1">
                                <p className="text-xs text-gray-500 font-medium">Address</p>
                                <p className="text-sm text-gray-900 mt-0.5">{partnerContext.partner_address}</p>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Current Loans (Active) */}
                    <div>
                      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">
                        Current Loan{partnerContext.current_loans?.length > 1 ? 's' : ''}
                        {partnerContext.current_loans?.length > 0 && (
                          <span className="ml-2 text-xs font-normal text-gray-400">({partnerContext.current_loans.length})</span>
                        )}
                      </h3>
                      {partnerContext.current_loans && partnerContext.current_loans.length > 0 ? (
                        <div className="space-y-2">
                          {partnerContext.current_loans.map((loan, idx) => (
                            <div key={idx} className="bg-blue-50 border-2 border-blue-400 rounded-lg p-4">
                              <div className="flex items-start">
                                <svg className="w-5 h-5 text-blue-600 mt-0.5 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
                                </svg>
                                <div className="flex-1 min-w-0">
                                  <p className="text-sm font-medium text-blue-900">🚗 {loan.make} {loan.model}</p>
                                  <p className="text-xs text-blue-700 mt-1">
                                    {formatActivityDate(loan.start_date)} - {formatActivityDate(loan.end_date)}
                                  </p>
                                  <p className="text-xs text-blue-600 mt-1 font-mono truncate">VIN: {loan.vin}</p>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="text-center py-8 text-gray-400 bg-gray-50 rounded-lg border border-gray-200">
                          <p className="text-sm">No active loans</p>
                        </div>
                      )}
                    </div>

                    {/* Recommended Loans (Planned) */}
                    <div>
                      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">
                        Recommended Loan{partnerContext.recommended_loans?.length > 1 ? 's' : ''}
                        {partnerContext.recommended_loans?.length > 0 && (
                          <span className="ml-2 text-xs font-normal text-gray-400">({partnerContext.recommended_loans.length})</span>
                        )}
                      </h3>
                      {partnerContext.recommended_loans && partnerContext.recommended_loans.length > 0 ? (
                        <div className="space-y-2">
                          {partnerContext.recommended_loans.map((loan, idx) => (
                            <div key={idx} className="bg-green-50 border-2 border-green-400 rounded-lg p-4">
                              <div className="flex items-start">
                                <svg className="w-5 h-5 text-green-600 mt-0.5 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
                                </svg>
                                <div className="flex-1 min-w-0">
                                  <p className="text-sm font-medium text-green-900">🚗 {loan.make} {loan.model}</p>
                                  <p className="text-xs text-green-700 mt-1">
                                    {formatActivityDate(loan.start_date)} - {formatActivityDate(loan.end_date)}
                                  </p>
                                  <p className="text-xs text-green-600 mt-1 font-mono truncate">VIN: {loan.vin}</p>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="text-center py-8 text-gray-400 bg-gray-50 rounded-lg border border-gray-200">
                          <p className="text-sm">No planned loans yet</p>
                          <p className="text-xs mt-1">Run the optimizer to get recommendations</p>
                        </div>
                      )}
                    </div>

                    {/* Timeline */}
                    <div>
                      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">Activity Timeline</h3>
                      <div className="space-y-2">
                        {partnerContext.timeline.map((act, idx) => (
                          <div key={idx} className="flex items-center text-xs bg-gray-50 rounded p-2">
                            <span className={`inline-block w-2 h-2 rounded-full mr-2 ${
                              act.status === 'active' ? 'bg-blue-500' :
                              act.status === 'planned' ? 'bg-green-500' :
                              'bg-gray-400'
                            }`}></span>
                            <span className="flex-1 font-medium text-gray-900">{act.make} {act.model}</span>
                            <span className="text-gray-500">{formatActivityDate(act.start_date)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
