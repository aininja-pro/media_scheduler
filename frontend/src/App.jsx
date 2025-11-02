import { useState, useEffect } from 'react'
import driveShopLogo from './assets/DriveShop_WebLogo.png'
import PublicationRates from './pages/PublicationRates.jsx'
import Optimizer from './pages/Optimizer.jsx'
import Calendar from './pages/Calendar.jsx'
import Partners from './pages/Partners.jsx'
import ChainBuilder from './pages/ChainBuilder.jsx'
import './App.css'

function App() {
  const [selectedOffice, setSelectedOffice] = useState('')
  const [selectedWeek, setSelectedWeek] = useState('')
  const [activeTab, setActiveTab] = useState('upload')
  const [optimizerOffice, setOptimizerOffice] = useState('Los Angeles') // Shared office state
  const [chainBuilderVehicle, setChainBuilderVehicle] = useState(null) // For Calendar→ChainBuilder navigation
  const [vehiclesUrl, setVehiclesUrl] = useState('https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/active_vehicles.rpt&init=csv')
  const [mediaPartnersUrl, setMediaPartnersUrl] = useState('https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/media_partners.rpt&init=csv')
  const [approvedRanksUrl, setApprovedRanksUrl] = useState('https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/approved_makes.rpt&init=csv')
  const [loanHistoryUrl, setLoanHistoryUrl] = useState('https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/loan_history.rpt&init=csv')
  const [currentActivityUrl, setCurrentActivityUrl] = useState('https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/current_vehicle_activity.rpt&init=csv')
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingMediaPartners, setIsLoadingMediaPartners] = useState(false)
  const [mediaPartnersProgress, setMediaPartnersProgress] = useState({ step: '', progress: 0 })
  const [isLoadingApprovedRanks, setIsLoadingApprovedRanks] = useState(false)
  const [isLoadingLoanHistory, setIsLoadingLoanHistory] = useState(false)
  const [isLoadingCurrentActivity, setIsLoadingCurrentActivity] = useState(false)
  const [isLoadingOperationsData, setIsLoadingOperationsData] = useState(false)
  const [isLoadingBudgets, setIsLoadingBudgets] = useState(false)

  const offices = ['SEA', 'PDX', 'LAX', 'SFO', 'PHX', 'DEN', 'LAS']

  // Listen for navigation from ChainBuilder to Calendar
  useEffect(() => {
    const handleNavigateToCalendar = (event) => {
      setActiveTab('calendar');
      // Could pass VIN to Calendar to highlight that vehicle
    };

    window.addEventListener('navigateToCalendar', handleNavigateToCalendar);
    return () => window.removeEventListener('navigateToCalendar', handleNavigateToCalendar);
  }, []);

  const handleVehiclesUpdate = async () => {
    setIsLoading(true)
    try {
      const response = await fetch(`http://localhost:8081/ingest/vehicles/url?url=${encodeURIComponent(vehiclesUrl)}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      })
      
      const result = await response.json()
      
      if (response.ok) {
        alert(`Success! Processed ${result.rows_processed} vehicles`)
      } else {
        alert(`Error: ${result.detail}`)
      }
    } catch (error) {
      alert(`Network error: ${error.message}`)
    } finally {
      setIsLoading(false)
    }
  }

  const handleMediaPartnersUpdate = async () => {
    setIsLoadingMediaPartners(true)
    setMediaPartnersProgress({ step: 'Starting...', progress: 0 })

    try {
      const eventSource = new EventSource(
        `http://localhost:8081/ingest/media_partners/url/stream?url=${encodeURIComponent(mediaPartnersUrl)}`
      )

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)

          if (data.status === 'progress') {
            setMediaPartnersProgress({ step: data.step, progress: data.progress })
          } else if (data.status === 'complete') {
            setMediaPartnersProgress({ step: data.message, progress: 100 })
            alert(`Success! ${data.message}`)
            eventSource.close()
            setIsLoadingMediaPartners(false)
          } else if (data.status === 'error') {
            setMediaPartnersProgress({ step: `Error: ${data.message}`, progress: 0 })
            alert(`Error: ${data.message}`)
            eventSource.close()
            setIsLoadingMediaPartners(false)
          }
        } catch (e) {
          console.error('Failed to parse SSE data:', e)
        }
      }

      eventSource.onerror = (error) => {
        console.error('EventSource error:', error)
        setMediaPartnersProgress({ step: 'Connection error', progress: 0 })
        alert('Network error: Connection to server failed')
        eventSource.close()
        setIsLoadingMediaPartners(false)
      }
    } catch (error) {
      alert(`Network error: ${error.message}`)
      setIsLoadingMediaPartners(false)
      setMediaPartnersProgress({ step: '', progress: 0 })
    }
  }

  const handleApprovedRanksUpdate = async () => {
    setIsLoadingApprovedRanks(true)
    try {
      const response = await fetch(`http://localhost:8081/ingest/approved_makes/url?url=${encodeURIComponent(approvedRanksUrl)}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      })
      
      const result = await response.json()
      
      if (response.ok) {
        alert(`Success! Processed ${result.rows_processed} approved ranks`)
      } else {
        alert(`Error: ${result.detail}`)
      }
    } catch (error) {
      alert(`Network error: ${error.message}`)
    } finally {
      setIsLoadingApprovedRanks(false)
    }
  }

  const handleLoanHistoryUpdate = async () => {
    setIsLoadingLoanHistory(true)
    try {
      const response = await fetch(`http://localhost:8081/ingest/loan_history/url?url=${encodeURIComponent(loanHistoryUrl)}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      })
      
      const result = await response.json()
      
      if (response.ok) {
        alert(`Success! Processed ${result.rows_processed} loan history records`)
      } else {
        alert(`Error: ${result.detail}`)
      }
    } catch (error) {
      alert(`Network error: ${error.message}`)
    } finally {
      setIsLoadingLoanHistory(false)
    }
  }

  const handleCurrentActivityUpdate = async () => {
    setIsLoadingCurrentActivity(true)
    try {
      const response = await fetch(`http://localhost:8081/ingest/current_activity/url?url=${encodeURIComponent(currentActivityUrl)}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      })
      
      const result = await response.json()
      
      if (response.ok) {
        alert(`Success! Processed ${result.rows_processed} current activity records`)
      } else {
        alert(`Error: ${result.detail}`)
      }
    } catch (error) {
      alert(`Network error: ${error.message}`)
    } finally {
      setIsLoadingCurrentActivity(false)
    }
  }

  const handleOperationsDataUpload = async (event) => {
    const file = event.target.files[0]
    if (!file) return

    setIsLoadingOperationsData(true)
    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch(`http://localhost:8081/ingest/operations_data`, {
        method: 'POST',
        body: formData,
      })
      
      const result = await response.json()
      
      if (response.ok) {
        alert(`Success! Processed ${result.tables_processed} tables: ${result.summary}`)
      } else {
        alert(`Error: ${result.detail}`)
      }
    } catch (error) {
      alert(`Network error: ${error.message}`)
    } finally {
      setIsLoadingOperationsData(false)
      // Reset file input
      event.target.value = ''
    }
  }

  const handleBudgetsUpload = async (event) => {
    const file = event.target.files[0]
    if (!file) return

    setIsLoadingBudgets(true)
    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch(`http://localhost:8081/ingest/budgets`, {
        method: 'POST',
        body: formData,
      })
      
      const result = await response.json()
      
      if (response.ok) {
        alert(`Success! Processed ${result.total_rows_processed} budget records`)
      } else {
        alert(`Error: ${result.detail}`)
      }
    } catch (error) {
      alert(`Network error: ${error.message}`)
    } finally {
      setIsLoadingBudgets(false)
      // Reset file input
      event.target.value = ''
    }
  }

  const csvTypes = [
    { id: 'vehicles', name: 'Vehicles', description: 'Year, make, model, VIN, fleet, dates', icon: '🚗' },
    { id: 'media_partners', name: 'Media Partners', description: 'Partner details, contact info, eligibility', icon: '📺' },
    { id: 'approved_makes', name: 'Approved Ranks', description: 'A+/A/B/C rankings per partner/make', icon: '⭐' },
    { id: 'loan_history', name: 'Loan History', description: 'Historical assignment data', icon: '📊' },
    { id: 'current_activity', name: 'Current Activity', description: 'Active bookings and holds', icon: '📅' },
    { id: 'operations_data', name: 'Operations Data', description: 'Rules, capacity limits, holiday dates', icon: '📊' },
    { id: 'budgets', name: 'Budgets', description: 'Office/fleet budget tracking by quarter', icon: '💰' }
  ]
  
  return (
    <div className="w-full min-h-screen bg-gray-50">
      {/* Header with DriveShop logo */}
      <header className="bg-black h-16 md:h-20">
        <div className="w-full px-4 sm:px-6 lg:px-8 h-full flex items-center justify-between">
          <div className="flex items-center space-x-4">
              <img
                src={driveShopLogo}
                alt="DriveShop Logo"
                className="h-10 w-auto"
                onError={() => console.log('Logo failed to load')}
              />
              <span className="ml-3 text-white/90 text-lg md:text-xl lg:text-2xl font-semibold tracking-wide leading-none whitespace-nowrap">
                Media Scheduler
              </span>
          </div>

          <nav className="flex space-x-2">
              <button
                onClick={() => setActiveTab('upload')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'upload'
                    ? 'bg-white text-black'
                    : 'bg-gray-600 text-white hover:bg-gray-500'
                }`}
              >
                Upload Data
              </button>
              <button
                onClick={() => setActiveTab('optimizer')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'optimizer'
                    ? 'bg-white text-black'
                    : 'bg-gray-600 text-white hover:bg-gray-500'
                }`}
              >
                Optimizer
              </button>
              <button
                onClick={() => setActiveTab('calendar')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'calendar'
                    ? 'bg-white text-black'
                    : 'bg-gray-600 text-white hover:bg-gray-500'
                }`}
              >
                Calendar
              </button>
              <button
                onClick={() => setActiveTab('chain-builder')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'chain-builder'
                    ? 'bg-white text-black'
                    : 'bg-gray-600 text-white hover:bg-gray-500'
                }`}
              >
                Chain Builder
              </button>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="w-full py-8 px-4 sm:px-6 lg:px-8">
        <div className="min-h-[800px]">

        {/* Upload Data Tab */}
        {activeTab === 'upload' && (
          <>
            <div className="mb-8">
              <h2 className="text-3xl font-bold text-gray-900 mb-3">
                Upload CSV Data
              </h2>
              <p className="text-lg text-gray-600">
                Import data files for vehicles, partners, and operational constraints
              </p>
            </div>

            {/* CSV Upload Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
              {csvTypes.map((csvType) => (
                <div key={csvType.id} className="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow">
                  <div className="p-6">
                    <div className="flex items-center mb-4">
                      <div className="text-3xl mr-3">{csvType.icon}</div>
                      <div>
                        <h3 className="text-lg font-semibold text-gray-900">{csvType.name}</h3>
                        <p className="text-sm text-gray-500">{csvType.description}</p>
                      </div>
                    </div>
                    
                    {/* CSV drop area for non-operations tables */}
                    {csvType.id !== 'operations_data' && csvType.id !== 'budgets' && (
                      <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:border-blue-400 transition-colors cursor-pointer mb-4">
                        <div className="text-gray-400 mb-2">
                          <svg className="mx-auto h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                          </svg>
                        </div>
                        <p className="text-sm text-gray-600 mb-2">
                          Drop CSV file or <span className="text-blue-600 font-medium">browse</span>
                        </p>
                        <p className="text-xs text-gray-400">Max file size: 10MB</p>
                      </div>
                    )}
                    
                    {/* Special handling for Vehicles - URL input */}
                    {csvType.id === 'vehicles' ? (
                      <div className="space-y-3">
                        <div>
                          <label className="block text-xs font-medium text-gray-700 mb-1">
                            Data Source URL:
                          </label>
                          <input
                            type="text"
                            value={vehiclesUrl}
                            onChange={(e) => setVehiclesUrl(e.target.value)}
                            className="w-full border border-gray-300 rounded-md px-3 py-2 text-xs focus:ring-2 focus:ring-green-500 focus:border-transparent"
                            placeholder="Enter DriveShop reports URL..."
                          />
                        </div>
                        <button 
                          onClick={handleVehiclesUpdate}
                          disabled={isLoading}
                          className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded-md transition-colors"
                        >
                          {isLoading ? 'Fetching...' : 'Update Vehicles Data'}
                        </button>
                      </div>
                    ) : csvType.id === 'media_partners' ? (
                      /* Special handling for Media Partners - URL input */
                      <div className="space-y-3">
                        <div>
                          <label className="block text-xs font-medium text-gray-700 mb-1">
                            Data Source URL:
                          </label>
                          <input
                            type="text"
                            value={mediaPartnersUrl}
                            onChange={(e) => setMediaPartnersUrl(e.target.value)}
                            className="w-full border border-gray-300 rounded-md px-3 py-2 text-xs focus:ring-2 focus:ring-green-500 focus:border-transparent"
                            placeholder="Enter DriveShop media partners URL..."
                          />
                        </div>
                        <button
                          onClick={handleMediaPartnersUpdate}
                          disabled={isLoadingMediaPartners}
                          className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded-md transition-colors"
                        >
                          {isLoadingMediaPartners ? 'Processing...' : 'Update Media Partners Data'}
                        </button>
                        {isLoadingMediaPartners && mediaPartnersProgress.step && (
                          <div className="mt-3 space-y-2">
                            <div className="flex justify-between text-xs text-gray-600">
                              <span>{mediaPartnersProgress.step}</span>
                              <span>{mediaPartnersProgress.progress}%</span>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-2">
                              <div
                                className="bg-green-600 h-2 rounded-full transition-all duration-300"
                                style={{ width: `${mediaPartnersProgress.progress}%` }}
                              ></div>
                            </div>
                          </div>
                        )}
                      </div>
                    ) : csvType.id === 'approved_makes' ? (
                      /* Special handling for Approved Ranks - URL input */
                      <div className="space-y-3">
                        <div>
                          <label className="block text-xs font-medium text-gray-700 mb-1">
                            Data Source URL:
                          </label>
                          <input
                            type="text"
                            value={approvedRanksUrl}
                            onChange={(e) => setApprovedRanksUrl(e.target.value)}
                            className="w-full border border-gray-300 rounded-md px-3 py-2 text-xs focus:ring-2 focus:ring-green-500 focus:border-transparent"
                            placeholder="Enter DriveShop approved ranks URL..."
                          />
                        </div>
                        <button 
                          onClick={handleApprovedRanksUpdate}
                          disabled={isLoadingApprovedRanks}
                          className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded-md transition-colors"
                        >
                          {isLoadingApprovedRanks ? 'Fetching...' : 'Update Approved Ranks Data'}
                        </button>
                      </div>
                    ) : csvType.id === 'loan_history' ? (
                      /* Special handling for Loan History - URL input */
                      <div className="space-y-3">
                        <div>
                          <label className="block text-xs font-medium text-gray-700 mb-1">
                            Data Source URL:
                          </label>
                          <input
                            type="text"
                            value={loanHistoryUrl}
                            onChange={(e) => setLoanHistoryUrl(e.target.value)}
                            className="w-full border border-gray-300 rounded-md px-3 py-2 text-xs focus:ring-2 focus:ring-green-500 focus:border-transparent"
                            placeholder="Enter DriveShop loan history URL..."
                          />
                        </div>
                        <button 
                          onClick={handleLoanHistoryUpdate}
                          disabled={isLoadingLoanHistory}
                          className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded-md transition-colors"
                        >
                          {isLoadingLoanHistory ? 'Fetching...' : 'Update Loan History Data'}
                        </button>
                      </div>
                    ) : csvType.id === 'current_activity' ? (
                      /* Special handling for Current Activity - URL input */
                      <div className="space-y-3">
                        <div>
                          <label className="block text-xs font-medium text-gray-700 mb-1">
                            Data Source URL:
                          </label>
                          <input
                            type="text"
                            value={currentActivityUrl}
                            onChange={(e) => setCurrentActivityUrl(e.target.value)}
                            className="w-full border border-gray-300 rounded-md px-3 py-2 text-xs focus:ring-2 focus:ring-green-500 focus:border-transparent"
                            placeholder="Enter DriveShop current activity URL..."
                          />
                        </div>
                        <button 
                          onClick={handleCurrentActivityUpdate}
                          disabled={isLoadingCurrentActivity}
                          className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded-md transition-colors"
                        >
                          {isLoadingCurrentActivity ? 'Fetching...' : 'Update Current Activity Data'}
                        </button>
                      </div>
                    ) : csvType.id === 'operations_data' ? (
                      /* Special handling for Operations Data - Excel file upload */
                      <div className="space-y-3">
                        <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:border-green-400 transition-colors">
                          <input
                            type="file"
                            accept=".xlsx,.xls"
                            onChange={handleOperationsDataUpload}
                            className="hidden"
                            id={`file-input-${csvType.id}`}
                          />
                          <label
                            htmlFor={`file-input-${csvType.id}`}
                            className="cursor-pointer"
                          >
                            <div className="text-gray-400 mb-2">
                              <svg className="mx-auto h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                              </svg>
                            </div>
                            <p className="text-sm text-gray-600 mb-2">
                              Drop Excel file or <span className="text-green-600 font-medium">browse</span>
                            </p>
                            <p className="text-xs text-gray-400">Max file size: 10MB | .xlsx, .xls</p>
                          </label>
                        </div>
                        <div className="text-xs text-gray-500 space-y-1 mb-4">
                          <div>✅ Sheet 1: Rules</div>
                          <div>✅ Sheet 2: Ops Capacity</div>
                          <div>✅ Sheet 3: Holiday/Blackout Dates</div>
                        </div>
                        <div className="mt-auto">
                          <button 
                            disabled={isLoadingOperationsData}
                            className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded-md transition-colors"
                          >
                            {isLoadingOperationsData ? 'Processing...' : 'Ready for Excel Upload'}
                          </button>
                        </div>
                      </div>
                    ) : csvType.id === 'budgets' ? (
                      /* Special handling for Budgets - Excel file upload */
                      <div className="space-y-3">
                        <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:border-green-400 transition-colors">
                          <input
                            type="file"
                            accept=".xlsx,.xls"
                            onChange={handleBudgetsUpload}
                            className="hidden"
                            id={`file-input-${csvType.id}`}
                          />
                          <label
                            htmlFor={`file-input-${csvType.id}`}
                            className="cursor-pointer"
                          >
                            <div className="text-gray-400 mb-2">
                              <svg className="mx-auto h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                              </svg>
                            </div>
                            <p className="text-sm text-gray-600 mb-2">
                              Drop Excel file or <span className="text-green-600 font-medium">browse</span>
                            </p>
                            <p className="text-xs text-gray-400">Max file size: 10MB | .xlsx, .xls</p>
                          </label>
                        </div>
                        <div className="text-xs text-gray-500 space-y-1 mb-4">
                          <div>✅ Office budget data by quarter</div>
                          <div>✅ Fleet/make budget allocations</div>
                          <div>✅ Usage tracking and reporting</div>
                        </div>
                        <div className="mt-auto">
                          <button 
                            disabled={isLoadingBudgets}
                            className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded-md transition-colors"
                          >
                            {isLoadingBudgets ? 'Processing...' : 'Ready for Budget Upload'}
                          </button>
                        </div>
                      </div>
                    ) : (
                      /* Regular file upload for other tables */
                      <button 
                        className="w-full mt-4 font-medium py-2 px-4 rounded-md transition-colors text-white border border-transparent bg-gray-600 hover:bg-white hover:text-black hover:border-black disabled:cursor-not-allowed shadow-sm"
                        disabled={true}
                      >
                        Upload {csvType.name}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        {/* Publication Rates Tab */}
        {activeTab === 'publication' && (
          <PublicationRates />
        )}

        {/* Optimizer Tab */}
        {activeTab === 'optimizer' && (
          <Optimizer
            sharedOffice={optimizerOffice}
            onOfficeChange={setOptimizerOffice}
          />
        )}

        {/* Calendar Tab */}
        <div style={{ display: activeTab === 'calendar' ? 'block' : 'none' }}>
          <Calendar
            sharedOffice={optimizerOffice}
            onOfficeChange={setOptimizerOffice}
            isActive={activeTab === 'calendar'}
            onBuildChainForVehicle={(vehicleData) => {
              setChainBuilderVehicle(vehicleData);
              setActiveTab('chain-builder');
            }}
          />
        </div>

        {/* Partners Tab */}
        {activeTab === 'partners' && (
          <Partners
            office={optimizerOffice}
            onOfficeChange={setOptimizerOffice}
          />
        )}

        {/* Chain Builder Tab */}
        {activeTab === 'chain-builder' && (
          <ChainBuilder
            sharedOffice={optimizerOffice}
            onOfficeChange={setOptimizerOffice}
            preloadedVehicle={chainBuilderVehicle}
            onVehicleLoaded={() => setChainBuilderVehicle(null)}
          />
        )}
        </div>
      </main>
    </div>
  )
}

export default App