import React, { useState, useEffect, Fragment } from 'react';
import { API_BASE_URL } from '../config';
import ModelSelector from '../components/ModelSelector';
import { EventManager, EventTypes } from '../utils/eventManager';
import TimelineBar from '../components/TimelineBar';
import AssignmentDetailsPanel from '../components/AssignmentDetailsPanel';
import { Combobox, Transition } from '@headlessui/react';

/**
 * Format partner name for display
 * @param {string} name - Full name (e.g., "John Smith" or "Mary Jo Smith")
 * @param {string} format - 'lastFirst' or 'firstLast'
 * @returns {string} Formatted name
 */
const formatPartnerName = (name, format = 'lastFirst') => {
  if (!name) return '';

  const parts = name.trim().split(/\s+/);

  // Single word name (e.g., "Madonna")
  if (parts.length === 1) {
    return name;
  }

  // Multi-part name
  const lastName = parts[parts.length - 1];
  const firstName = parts.slice(0, -1).join(' ');

  if (format === 'lastFirst') {
    return `${lastName}, ${firstName}`;
  } else {
    return name; // firstLast - return original
  }
};

/**
 * Format activity date for display
 * @param {string} dateString - ISO date string
 * @returns {string} Formatted date (e.g., "Jan 15")
 */
const formatActivityDate = (dateString) => {
  if (!dateString) return 'N/A';
  const date = new Date(dateString + 'T00:00:00');
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

function ChainBuilder({ sharedOffice, onOfficeChange, preloadedVehicle, onVehicleLoaded, preloadedPartner, onPartnerLoaded }) {
  // Chain mode: 'partner' (existing) or 'vehicle' (new)
  const [chainMode, setChainMode] = useState('partner');

  // Use shared office from parent, default to 'Los Angeles'
  const [selectedOffice, setSelectedOffice] = useState(sharedOffice || 'Los Angeles');

  // Update parent when local office changes
  const handleOfficeChange = (newOffice) => {
    setSelectedOffice(newOffice);
    // Clear selections when office changes (old selections may not exist in new office)
    setSelectedPartner('');
    setSelectedVehicle(null);
    setPartnerSearchQuery('');
    setVehicleSearchQuery('');
    setChain(null);
    setManualSlots([]);
    setManualPartnerSlots([]);
    if (onOfficeChange) {
      onOfficeChange(newOffice);
    }
  };
  const [selectedPartner, setSelectedPartner] = useState('');
  const [startDate, setStartDate] = useState('');
  const [numVehicles, setNumVehicles] = useState(4);
  const [daysPerLoan, setDaysPerLoan] = useState(8);
  const [isLoading, setIsLoading] = useState(false);
  const [chain, setChain] = useState(null);
  const [error, setError] = useState('');
  const [saveMessage, setSaveMessage] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  // Timeline navigation
  const [viewStartDate, setViewStartDate] = useState(null); // Show 1 month at a time
  const [viewEndDate, setViewEndDate] = useState(null);

  // Load offices and partners
  const [offices, setOffices] = useState([]);
  const [partners, setPartners] = useState([]);
  const [partnerSearchQuery, setPartnerSearchQuery] = useState('');

  // Vehicle search (for vehicle chain mode)
  const [vehicles, setVehicles] = useState([]);
  const [vehicleSearchQuery, setVehicleSearchQuery] = useState('');
  const [selectedVehicle, setSelectedVehicle] = useState(null);

  // Partner intelligence (current/scheduled activities)
  const [partnerIntelligence, setPartnerIntelligence] = useState(null);
  const [loadingIntelligence, setLoadingIntelligence] = useState(false);

  // Vehicle intelligence (for vehicle chain mode)
  const [vehicleIntelligence, setVehicleIntelligence] = useState(null);
  const [loadingVehicleIntelligence, setLoadingVehicleIntelligence] = useState(false);

  // Make filtering
  const [selectedMakes, setSelectedMakes] = useState([]);

  // Model preferences for Partner Chain (NEW)
  const [modelPreferences, setModelPreferences] = useState([]); // Array of {make, model}
  const [preferenceMode, setPreferenceMode] = useState('prioritize'); // 'prioritize' | 'strict' | 'ignore'

  // Tier filter for Vehicle Chain (NEW)
  const [selectedTiers, setSelectedTiers] = useState(['A+', 'A', 'B', 'C']); // Default: all tiers

  // Helper: Get selected partner object for Combobox display
  const selectedPartnerObj = partners.find(p => p.person_id === selectedPartner) || null;

  // Slot vehicle search queries (for filtering dropdown options)
  const [slotVehicleSearchQueries, setSlotVehicleSearchQueries] = useState({});

  // Swap modal
  const [swapModalOpen, setSwapModalOpen] = useState(false);
  const [swapSlot, setSwapSlot] = useState(null);
  const [swapAlternatives, setSwapAlternatives] = useState([]);
  const [loadingSwap, setLoadingSwap] = useState(false);

  // Manual Build mode (for partner chains)
  const [buildMode, setBuildMode] = useState('auto'); // 'auto' or 'manual'
  const [manualSlots, setManualSlots] = useState([]); // Array of {slot, start_date, end_date, selected_vehicle, eligible_vehicles}
  const [loadingSlotOptions, setLoadingSlotOptions] = useState({});

  // Manual Build mode (for vehicle chains)
  const [vehicleBuildMode, setVehicleBuildMode] = useState('auto'); // 'auto' or 'manual'
  const [manualPartnerSlots, setManualPartnerSlots] = useState([]); // Array of {slot, start_date, end_date, selected_partner, eligible_partners}
  const [loadingPartnerSlotOptions, setLoadingPartnerSlotOptions] = useState({});
  const [vehicleChain, setVehicleChain] = useState(null); // Auto-generated vehicle chain

  // Edit mode for auto-generated chains
  const [editingSlot, setEditingSlot] = useState(null); // Which slot is being edited (index)
  const [slotOptions, setSlotOptions] = useState([]); // Partner options for editing slot
  const [chainModified, setChainModified] = useState(false); // Track if chain has been edited

  // Budget calculation for chain
  const [chainBudget, setChainBudget] = useState(null);

  // Assignment details panel
  const [selectedAssignment, setSelectedAssignment] = useState(null); // For details panel

  // Model Selector Modal state
  const [showModelSelectorModal, setShowModelSelectorModal] = useState(false);

  // Review history filters
  const [vehicleHistoryFilter, setVehicleHistoryFilter] = useState(null); // { vin, reviewHistory }
  const [partnerHistoryFilter, setPartnerHistoryFilter] = useState(null); // { person_id, reviewHistory }

  // Vehicle Context side panel
  const [selectedVehicleVin, setSelectedVehicleVin] = useState(null);
  const [vehicleContext, setVehicleContext] = useState(null);
  const [loadingVehicleContext, setLoadingVehicleContext] = useState(false);

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
        const response = await fetch(`${API_BASE_URL}/api/offices`);
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
        const response = await fetch(`${API_BASE_URL}/api/calendar/media-partners?office=${encodeURIComponent(selectedOffice)}`);
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

  // Load all vehicles when office or chainMode changes (no debounce for dropdown)
  useEffect(() => {
    if (!selectedOffice || chainMode !== 'vehicle') {
      setVehicles([]);
      return;
    }

    const loadVehicles = async () => {
      try {
        // Load all vehicles for office (empty search_term returns all)
        const response = await fetch(
          `${API_BASE_URL}/api/chain-builder/search-vehicles?office=${encodeURIComponent(selectedOffice)}&search_term=&limit=1000`
        );

        if (!response.ok) {
          console.error('Failed to load vehicles');
          setVehicles([]);
          return;
        }

        const data = await response.json();
        let vehiclesList = data.vehicles || [];

        // Apply partner history filter if active
        if (partnerHistoryFilter && partnerHistoryFilter.reviewHistory) {
          const reviewedVINs = new Set(
            partnerHistoryFilter.reviewHistory.reviews.map(r => r.vin)
          );
          vehiclesList = vehiclesList.filter(v => reviewedVINs.has(v.vin));
          console.log(`Filtered to ${vehiclesList.length} vehicles reviewed by partner ${partnerHistoryFilter.person_id}`);
        }

        setVehicles(vehiclesList);
        console.log(`Loaded ${vehiclesList.length} vehicles for ${selectedOffice}`);
      } catch (err) {
        console.error('Failed to load vehicles:', err);
        setVehicles([]);
      }
    };

    loadVehicles();
  }, [selectedOffice, chainMode, partnerHistoryFilter]);

  // Get current Monday as default
  const getCurrentMonday = () => {
    const today = new Date();
    const dayOfWeek = today.getDay();
    const daysToMonday = dayOfWeek === 0 ? 1 : 1 - dayOfWeek;
    const monday = new Date(today);
    monday.setDate(today.getDate() + daysToMonday);
    return monday.toISOString().split('T')[0];
  };

  // Initialize start date to next Monday and restore from session
  useEffect(() => {
    setStartDate(getCurrentMonday());

    // Restore chain mode from sessionStorage
    const savedChainMode = sessionStorage.getItem('chainbuilder_chain_mode');
    if (savedChainMode && (savedChainMode === 'partner' || savedChainMode === 'vehicle')) {
      setChainMode(savedChainMode);
    }

    // Restore selected partner from sessionStorage
    const savedPartnerId = sessionStorage.getItem('chainbuilder_partner_id');
    const savedPartnerName = sessionStorage.getItem('chainbuilder_partner_name');
    if (savedPartnerId) {
      setSelectedPartner(parseInt(savedPartnerId));
      setPartnerSearchQuery(savedPartnerName || '');
    }

    // Restore chain/slots from sessionStorage
    const savedManualSlots = sessionStorage.getItem('chainbuilder_manual_slots');
    const savedBuildMode = sessionStorage.getItem('chainbuilder_build_mode');
    const savedStartDate = sessionStorage.getItem('chainbuilder_start_date');
    const savedNumVehicles = sessionStorage.getItem('chainbuilder_num_vehicles');
    const savedDaysPerLoan = sessionStorage.getItem('chainbuilder_days_per_loan');

    if (savedManualSlots) {
      try {
        console.time('Restoring chain');
        const restored = JSON.parse(savedManualSlots);
        console.log('Restoring', restored.length, 'slots');
        // Ensure eligible_vehicles array exists (wasn't saved to sessionStorage)
        const restoredWithDefaults = restored.map(slot => ({
          ...slot,
          eligible_vehicles: slot.eligible_vehicles || []
        }));
        setManualSlots(restoredWithDefaults);
        console.timeEnd('Restoring chain');
      } catch (e) {
        console.error('Error restoring manual slots:', e);
      }
    }
    if (savedBuildMode) setBuildMode(savedBuildMode);
    if (savedStartDate) setStartDate(savedStartDate);
    if (savedNumVehicles) setNumVehicles(parseInt(savedNumVehicles));
    if (savedDaysPerLoan) setDaysPerLoan(parseInt(savedDaysPerLoan));

    // Restore vehicle chain state from sessionStorage
    const savedVehicleVin = sessionStorage.getItem('chainbuilder_vehicle_vin');
    const savedVehicleMake = sessionStorage.getItem('chainbuilder_vehicle_make');
    const savedVehicleModel = sessionStorage.getItem('chainbuilder_vehicle_model');
    const savedVehicleYear = sessionStorage.getItem('chainbuilder_vehicle_year');
    if (savedVehicleVin) {
      setSelectedVehicle({
        vin: savedVehicleVin,
        make: savedVehicleMake || '',
        model: savedVehicleModel || '',
        year: savedVehicleYear || ''
      });
      setVehicleSearchQuery(`${savedVehicleMake || ''} ${savedVehicleModel || ''} ${savedVehicleYear || ''}`.trim());
    }

    const savedVehicleBuildMode = sessionStorage.getItem('chainbuilder_vehicle_build_mode');
    if (savedVehicleBuildMode) setVehicleBuildMode(savedVehicleBuildMode);

    const savedManualPartnerSlots = sessionStorage.getItem('chainbuilder_manual_partner_slots');
    if (savedManualPartnerSlots) {
      try {
        const restored = JSON.parse(savedManualPartnerSlots);
        console.log('Restoring', restored.length, 'partner slots');
        const restoredWithDefaults = restored.map(slot => ({
          ...slot,
          eligible_partners: slot.eligible_partners || []
        }));
        setManualPartnerSlots(restoredWithDefaults);
      } catch (e) {
        console.error('Error restoring manual partner slots:', e);
      }
    }
  }, []);

  // Save chain mode to sessionStorage
  useEffect(() => {
    sessionStorage.setItem('chainbuilder_chain_mode', chainMode);
  }, [chainMode]);

  // Clear chain when partner changes and save to sessionStorage
  useEffect(() => {
    if (selectedPartner) {
      // Clear existing chain when partner changes
      setManualSlots([]);
      setChain(null);
      setError('');
      setSaveMessage('');

      // Save to sessionStorage
      sessionStorage.setItem('chainbuilder_partner_id', selectedPartner);
      const partner = partners.find(p => p.person_id === selectedPartner);
      if (partner) {
        sessionStorage.setItem('chainbuilder_partner_name', partner.name);
      }
    }
  }, [selectedPartner, partners]);

  // Clear chain when vehicle changes and save to sessionStorage
  useEffect(() => {
    if (selectedVehicle) {
      // Clear existing chain when vehicle changes
      setManualPartnerSlots([]);
      setVehicleChain(null);
      setChainModified(false);
      setError('');
      setSaveMessage('');

      // Save to sessionStorage
      sessionStorage.setItem('chainbuilder_vehicle_vin', selectedVehicle.vin);
      sessionStorage.setItem('chainbuilder_vehicle_make', selectedVehicle.make || '');
      sessionStorage.setItem('chainbuilder_vehicle_model', selectedVehicle.model || '');
      sessionStorage.setItem('chainbuilder_vehicle_year', selectedVehicle.year || '');
    }
  }, [selectedVehicle]);

  // Save vehicle build mode to sessionStorage
  useEffect(() => {
    sessionStorage.setItem('chainbuilder_vehicle_build_mode', vehicleBuildMode);
  }, [vehicleBuildMode]);

  // Save manual partner slots to sessionStorage
  useEffect(() => {
    if (manualPartnerSlots.length > 0) {
      try {
        // Don't save eligible_partners array (too large, reload on demand)
        const sanitizedSlots = manualPartnerSlots.map(slot => ({
          ...slot,
          eligible_partners: [] // Clear to reduce storage size
        }));
        sessionStorage.setItem('chainbuilder_manual_partner_slots', JSON.stringify(sanitizedSlots));
      } catch (err) {
        console.error('Error saving manual partner slots to sessionStorage:', err);
      }
    }
  }, [manualPartnerSlots]);

  // Listen for Calendar updates
  useEffect(() => {
    const handleCalendarDataUpdate = (detail) => {
      console.log('[ChainBuilder] Received calendar data update event:', detail);

      // Reload partner intelligence if in partner mode and office matches
      if (chainMode === 'partner' && detail.office === selectedOffice && selectedPartner) {
        console.log('[ChainBuilder] Reloading partner intelligence...');
        fetch(
          `${API_BASE_URL}/api/ui/phase7/partner-intelligence?person_id=${selectedPartner}&office=${encodeURIComponent(selectedOffice)}`
        )
          .then(response => response.json())
          .then(data => {
            if (data.success) {
              setPartnerIntelligence(data);
            }
          })
          .catch(err => console.error('Failed to reload partner intelligence:', err));
      }

      // Reload vehicle intelligence if in vehicle mode and office matches
      if (chainMode === 'vehicle' && detail.office === selectedOffice && selectedVehicle) {
        console.log('[ChainBuilder] Reloading vehicle intelligence...');
        const now = new Date();
        const sixMonthsAgo = new Date(now.getFullYear(), now.getMonth() - 6, 1);
        const sixMonthsAhead = new Date(now.getFullYear(), now.getMonth() + 6, 0);
        const startDate = sixMonthsAgo.toISOString().split('T')[0];
        const endDate = sixMonthsAhead.toISOString().split('T')[0];

        fetch(
          `${API_BASE_URL}/api/chain-builder/vehicle-busy-periods?vin=${encodeURIComponent(selectedVehicle.vin)}&start_date=${startDate}&end_date=${endDate}`
        )
          .then(response => response.json())
          .then(data => setVehicleIntelligence(data))
          .catch(err => console.error('Failed to reload vehicle intelligence:', err));
      }
    };

    const handler = EventManager.on(EventTypes.CALENDAR_DATA_UPDATED, handleCalendarDataUpdate);

    // Cleanup on unmount
    return () => {
      EventManager.off(EventTypes.CALENDAR_DATA_UPDATED, handler);
    };
  }, [chainMode, selectedOffice, selectedPartner, selectedVehicle]);

  // Listen for review history filter events from AssignmentDetailsPanel
  useEffect(() => {
    const handleVehicleFilter = (event) => {
      const { vin, reviewHistory } = event.detail;
      console.log('[ChainBuilder] Applying vehicle history filter:', vin, reviewHistory);
      setVehicleHistoryFilter({ vin, reviewHistory });
    };

    const handlePartnerFilter = (event) => {
      const { person_id, reviewHistory } = event.detail;
      console.log('[ChainBuilder] Applying partner history filter:', person_id, reviewHistory);
      setPartnerHistoryFilter({ person_id, reviewHistory });
    };

    const handleClearFilters = () => {
      console.log('[ChainBuilder] Clearing all history filters');
      setVehicleHistoryFilter(null);
      setPartnerHistoryFilter(null);
    };

    // Add event listeners using native addEventListener
    window.addEventListener(EventTypes.APPLY_VEHICLE_HISTORY_FILTER, handleVehicleFilter);
    window.addEventListener(EventTypes.APPLY_PARTNER_HISTORY_FILTER, handlePartnerFilter);
    window.addEventListener(EventTypes.CLEAR_HISTORY_FILTERS, handleClearFilters);

    // Cleanup on unmount
    return () => {
      window.removeEventListener(EventTypes.APPLY_VEHICLE_HISTORY_FILTER, handleVehicleFilter);
      window.removeEventListener(EventTypes.APPLY_PARTNER_HISTORY_FILTER, handlePartnerFilter);
      window.removeEventListener(EventTypes.CLEAR_HISTORY_FILTERS, handleClearFilters);
    };
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
          `${API_BASE_URL}/api/ui/phase7/partner-intelligence?person_id=${selectedPartner}&office=${encodeURIComponent(selectedOffice)}`
        );
        if (response.ok) {
          const data = await response.json();
          if (data.success) {
            setPartnerIntelligence(data);

            // Auto-select all approved makes by default
            const approvedMakes = data.approved_makes?.map(m => m.make) || [];
            setSelectedMakes(approvedMakes);

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

  // Load vehicle busy periods when vehicle is selected (vehicle chain mode)
  useEffect(() => {
    if (!selectedVehicle || !selectedOffice || chainMode !== 'vehicle') {
      setVehicleIntelligence(null);
      return;
    }

    const loadVehicleBusyPeriods = async () => {
      setLoadingVehicleIntelligence(true);
      try {
        // Calculate date range (6 months back, 6 months forward)
        const now = new Date();
        const sixMonthsAgo = new Date(now.getFullYear(), now.getMonth() - 6, 1);
        const sixMonthsAhead = new Date(now.getFullYear(), now.getMonth() + 6, 0);

        const startDate = sixMonthsAgo.toISOString().split('T')[0];
        const endDate = sixMonthsAhead.toISOString().split('T')[0];

        const response = await fetch(
          `${API_BASE_URL}/api/chain-builder/vehicle-busy-periods?vin=${encodeURIComponent(selectedVehicle.vin)}&start_date=${startDate}&end_date=${endDate}`
        );

        if (response.ok) {
          const data = await response.json();
          setVehicleIntelligence(data);

          // Initialize timeline view to current month when vehicle loads
          if (!viewStartDate) {
            const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
            const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0);
            setViewStartDate(monthStart);
            setViewEndDate(monthEnd);
          }
        }
      } catch (err) {
        console.error('Error loading vehicle busy periods:', err);
      } finally {
        setLoadingVehicleIntelligence(false);
      }
    };

    loadVehicleBusyPeriods();
  }, [selectedVehicle, selectedOffice, chainMode]);

  // Fetch vehicle context when selectedVehicleVin changes
  useEffect(() => {
    const fetchVehicleContext = async () => {
      if (!selectedVehicleVin) {
        setVehicleContext(null);
        return;
      }

      setLoadingVehicleContext(true);
      try {
        const response = await fetch(
          `${API_BASE_URL}/api/ui/phase7/vehicle-context/${encodeURIComponent(selectedVehicleVin)}`
        );

        if (response.ok) {
          const data = await response.json();
          setVehicleContext(data);
        } else {
          console.error('Failed to load vehicle context');
          setVehicleContext(null);
        }
      } catch (err) {
        console.error('Error loading vehicle context:', err);
        setVehicleContext(null);
      } finally {
        setLoadingVehicleContext(false);
      }
    };

    fetchVehicleContext();
  }, [selectedVehicleVin]);

  // Function to open vehicle context panel
  const openVehicleContext = (vin) => {
    setSelectedVehicleVin(vin);
  };

  // Function to close vehicle context panel
  const closeVehicleContext = () => {
    setSelectedVehicleVin(null);
    setVehicleContext(null);
  };

  // Handle preloaded vehicle from Calendar navigation
  useEffect(() => {
    if (preloadedVehicle) {
      setChainMode('vehicle');
      setSelectedVehicle(preloadedVehicle);
      setVehicleSearchQuery(`${preloadedVehicle.make} ${preloadedVehicle.model} ${preloadedVehicle.year}`.trim());
      if (onVehicleLoaded) {
        onVehicleLoaded(); // Clear the preloaded vehicle from parent
      }
    }
  }, [preloadedVehicle]);

  // Handle preloaded partner from Calendar navigation
  useEffect(() => {
    if (preloadedPartner) {
      setChainMode('partner');
      setSelectedPartner(preloadedPartner.person_id);
      setPartnerSearchQuery(preloadedPartner.name);
      if (onPartnerLoaded) {
        onPartnerLoaded(); // Clear the preloaded partner from parent
      }
    }
  }, [preloadedPartner]);

  // Refresh partner intelligence when tab becomes visible (detect visibility change)
  useEffect(() => {
    const handleVisibilityChange = () => {
      // When tab becomes visible and we have a selected partner, refresh intelligence
      if (!document.hidden && selectedPartner && selectedOffice) {
        const refreshPartnerIntelligence = async () => {
          try {
            const response = await fetch(
              `${API_BASE_URL}/api/ui/phase7/partner-intelligence?person_id=${selectedPartner}&office=${encodeURIComponent(selectedOffice)}`
            );
            if (response.ok) {
              const data = await response.json();
              if (data.success) {
                setPartnerIntelligence(data);
                console.log('Partner intelligence refreshed on tab visibility');
              }
            }
          } catch (err) {
            console.error('Error refreshing partner intelligence:', err);
          }
        };
        refreshPartnerIntelligence();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
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

  // Refresh partner intelligence manually
  const refreshPartnerIntelligence = async () => {
    if (!selectedPartner || !selectedOffice) return;

    setLoadingIntelligence(true);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/ui/phase7/partner-intelligence?person_id=${selectedPartner}&office=${encodeURIComponent(selectedOffice)}`
      );
      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          setPartnerIntelligence(data);
          console.log('Partner intelligence refreshed manually');
        }
      }
    } catch (err) {
      console.error('Error refreshing partner intelligence:', err);
    } finally {
      setLoadingIntelligence(false);
    }
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

  const deleteManualChain = async () => {
    if (!partnerIntelligence || !partnerIntelligence.upcoming_assignments) {
      return;
    }

    const chainAssignments = partnerIntelligence.upcoming_assignments.filter(a => a.status === 'manual');

    if (chainAssignments.length === 0) {
      setSaveMessage('❌ No manual chain to delete');
      return;
    }

    if (!window.confirm(`Delete manual chain (${chainAssignments.length} vehicles) for ${partnerIntelligence.partner.name}?`)) {
      return;
    }

    setIsSaving(true);
    setSaveMessage('');

    try {
      // Delete each assignment
      for (const assignment of chainAssignments) {
        await fetch(`${API_BASE_URL}/api/calendar/delete-assignment/${assignment.assignment_id}`, {
          method: 'DELETE'
        });
      }

      setSaveMessage(`✅ Deleted ${chainAssignments.length} manual assignment(s)`);

      // Reload partner intelligence to refresh calendar
      if (selectedPartner && selectedOffice) {
        const response = await fetch(
          `${API_BASE_URL}/api/ui/phase7/partner-intelligence?person_id=${selectedPartner}&office=${encodeURIComponent(selectedOffice)}`
        );
        if (response.ok) {
          const data = await response.json();
          if (data.success) {
            setPartnerIntelligence(data);
          }
        }
      }

      // Emit event so Calendar can reload
      EventManager.emit(EventTypes.CALENDAR_DATA_UPDATED, {
        office: selectedOffice,
        partnerId: selectedPartner,
        action: 'deleteChain',
        status: 'manual',
        count: chainAssignments.length
      });
    } catch (err) {
      setSaveMessage(`❌ Error deleting chain: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const deleteRequestedChain = async () => {
    if (!partnerIntelligence || !partnerIntelligence.upcoming_assignments) {
      return;
    }

    const chainAssignments = partnerIntelligence.upcoming_assignments.filter(a => a.status === 'requested');

    if (chainAssignments.length === 0) {
      setSaveMessage('❌ No requested chain to delete');
      return;
    }

    if (!window.confirm(`Delete requested chain (${chainAssignments.length} vehicles) for ${partnerIntelligence.partner.name}?\n\nNote: This will remove assignments that were sent to FMS.`)) {
      return;
    }

    setIsSaving(true);
    setSaveMessage('');

    try {
      // Use bulk delete endpoint for requested chains (handles FMS deletion)
      const assignmentIds = chainAssignments.map(a => a.assignment_id);

      const response = await fetch(`${API_BASE_URL}/api/fms/bulk-delete-vehicle-requests`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ assignment_ids: assignmentIds })
      });

      const result = await response.json();

      if (result.succeeded > 0) {
        setSaveMessage(`✅ Deleted ${result.succeeded}/${result.total} assignment(s) from FMS and scheduler`);
      } else {
        setSaveMessage(`❌ Failed to delete chain: ${result.failed} errors`);
        console.error('Bulk delete failed:', result);
      }

      // Reload partner intelligence to refresh calendar
      if (selectedPartner && selectedOffice) {
        const response = await fetch(
          `${API_BASE_URL}/api/ui/phase7/partner-intelligence?person_id=${selectedPartner}&office=${encodeURIComponent(selectedOffice)}`
        );
        if (response.ok) {
          const data = await response.json();
          if (data.success) {
            setPartnerIntelligence(data);
          }
        }
      }

      // Emit event so Calendar can reload
      EventManager.emit(EventTypes.CALENDAR_DATA_UPDATED, {
        office: selectedOffice,
        partnerId: selectedPartner,
        action: 'deleteChain',
        status: 'requested',
        count: chainAssignments.length
      });
    } catch (err) {
      setSaveMessage(`❌ Error deleting chain: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const deleteManualVehicleChain = async () => {
    if (!vehicleIntelligence || !vehicleIntelligence.busy_periods) {
      return;
    }

    const chainAssignments = vehicleIntelligence.busy_periods.filter(a => a.status === 'manual');

    if (chainAssignments.length === 0) {
      setSaveMessage('❌ No manual chain to delete');
      return;
    }

    if (!window.confirm(`Delete manual chain (${chainAssignments.length} partners) for ${selectedVehicle.make} ${selectedVehicle.model}?`)) {
      return;
    }

    setIsSaving(true);
    setSaveMessage('');

    try {
      // Delete each assignment
      for (const assignment of chainAssignments) {
        await fetch(`${API_BASE_URL}/api/calendar/delete-assignment/${assignment.assignment_id}`, {
          method: 'DELETE'
        });
      }

      setSaveMessage(`✅ Deleted ${chainAssignments.length} manual assignment(s)`);

      // Reload vehicle intelligence to refresh calendar
      if (selectedVehicle) {
        const now = new Date();
        const sixMonthsAgo = new Date(now.getFullYear(), now.getMonth() - 6, 1);
        const sixMonthsAhead = new Date(now.getFullYear(), now.getMonth() + 6, 0);
        const startDate = sixMonthsAgo.toISOString().split('T')[0];
        const endDate = sixMonthsAhead.toISOString().split('T')[0];

        const response = await fetch(
          `${API_BASE_URL}/api/chain-builder/vehicle-busy-periods?vin=${encodeURIComponent(selectedVehicle.vin)}&start_date=${startDate}&end_date=${endDate}`
        );
        if (response.ok) {
          const data = await response.json();
          setVehicleIntelligence(data);
        }
      }

      // Emit event so Calendar can reload
      EventManager.emit(EventTypes.CALENDAR_DATA_UPDATED, {
        office: selectedOffice,
        vin: selectedVehicle.vin,
        action: 'deleteChain',
        status: 'manual',
        count: chainAssignments.length
      });
    } catch (err) {
      setSaveMessage(`❌ Error deleting chain: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const deleteRequestedVehicleChain = async () => {
    if (!vehicleIntelligence || !vehicleIntelligence.busy_periods) {
      return;
    }

    const chainAssignments = vehicleIntelligence.busy_periods.filter(a => a.status === 'requested');

    if (chainAssignments.length === 0) {
      setSaveMessage('❌ No requested chain to delete');
      return;
    }

    if (!window.confirm(`Delete requested chain (${chainAssignments.length} partners) for ${selectedVehicle.make} ${selectedVehicle.model}?\n\nNote: This will remove assignments from FMS.`)) {
      return;
    }

    setIsSaving(true);
    setSaveMessage('');

    try {
      // Use bulk delete endpoint for requested chains (handles FMS deletion)
      const assignmentIds = chainAssignments.map(a => a.assignment_id);

      const response = await fetch(`${API_BASE_URL}/api/fms/bulk-delete-vehicle-requests`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ assignment_ids: assignmentIds })
      });

      const result = await response.json();

      if (result.succeeded > 0) {
        setSaveMessage(`✅ Deleted ${result.succeeded}/${result.total} assignment(s) from FMS and scheduler`);
      } else {
        setSaveMessage(`❌ Failed to delete chain: ${result.failed} errors`);
        console.error('Bulk delete failed:', result);
      }

      // Reload vehicle intelligence to refresh calendar
      if (selectedVehicle) {
        const now = new Date();
        const sixMonthsAgo = new Date(now.getFullYear(), now.getMonth() - 6, 1);
        const sixMonthsAhead = new Date(now.getFullYear(), now.getMonth() + 6, 0);
        const startDate = sixMonthsAgo.toISOString().split('T')[0];
        const endDate = sixMonthsAhead.toISOString().split('T')[0];

        const response = await fetch(
          `${API_BASE_URL}/api/chain-builder/vehicle-busy-periods?vin=${encodeURIComponent(selectedVehicle.vin)}&start_date=${startDate}&end_date=${endDate}`
        );
        if (response.ok) {
          const data = await response.json();
          setVehicleIntelligence(data);
        }
      }

      // Emit event so Calendar can reload
      EventManager.emit(EventTypes.CALENDAR_DATA_UPDATED, {
        office: selectedOffice,
        vin: selectedVehicle.vin,
        action: 'deleteChain',
        status: 'requested',
        count: chainAssignments.length
      });
    } catch (err) {
      setSaveMessage(`❌ Error deleting chain: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  // Timeline bar action handlers
  const handleTimelineBarClick = (assignment) => {
    setSelectedAssignment(assignment);
  };

  const handleTimelineBarDelete = async (assignment) => {
    if (!assignment.assignment_id) return;

    if (!window.confirm(`Delete this ${assignment.status} assignment?`)) {
      return;
    }

    try {
      let response;

      // If status is 'requested' (magenta), use FMS delete endpoint
      if (assignment.status === 'requested') {
        response = await fetch(
          `${API_BASE_URL}/api/fms/delete-vehicle-request/${assignment.assignment_id}`,
          { method: 'DELETE' }
        );
      } else {
        // For non-requested assignments (green), use regular delete
        response = await fetch(
          `${API_BASE_URL}/api/calendar/delete-assignment/${assignment.assignment_id}`,
          { method: 'DELETE' }
        );
      }

      if (!response.ok) {
        const errorData = await response.json();
        if (response.status === 500 && assignment.status === 'requested') {
          setSaveMessage(`❌ Failed to delete from FMS - assignment may still exist`);
        } else {
          setSaveMessage(`❌ Failed to delete: ${errorData.detail || errorData.message || 'Unknown error'}`);
        }
        return;
      }

      const data = await response.json();

      if (data.success) {
        // Show appropriate success message
        if (assignment.status === 'requested' && data.deleted_from_fms) {
          setSaveMessage(`✅ Assignment deleted! Request removed from FMS and scheduler.`);
        } else {
          setSaveMessage(`✅ Assignment deleted successfully`);
        }

        // Reload intelligence based on mode
        if (chainMode === 'partner' && selectedPartner && selectedOffice) {
          const resp = await fetch(
            `${API_BASE_URL}/api/ui/phase7/partner-intelligence?person_id=${selectedPartner}&office=${encodeURIComponent(selectedOffice)}`
          );
          if (resp.ok) {
            const reloadData = await resp.json();
            if (reloadData.success) {
              setPartnerIntelligence(reloadData);
            }
          }
        } else if (chainMode === 'vehicle' && selectedVehicle) {
          const now = new Date();
          const sixMonthsAgo = new Date(now.getFullYear(), now.getMonth() - 6, 1);
          const sixMonthsAhead = new Date(now.getFullYear(), now.getMonth() + 6, 0);
          const startDate = sixMonthsAgo.toISOString().split('T')[0];
          const endDate = sixMonthsAhead.toISOString().split('T')[0];

          const resp = await fetch(
            `${API_BASE_URL}/api/chain-builder/vehicle-busy-periods?vin=${encodeURIComponent(selectedVehicle.vin)}&start_date=${startDate}&end_date=${endDate}`
          );
          if (resp.ok) {
            const reloadData = await resp.json();
            setVehicleIntelligence(reloadData);
          }
        }

        // Emit event for Calendar
        EventManager.emit(EventTypes.CALENDAR_DATA_UPDATED, {
          office: selectedOffice,
          action: 'delete',
          assignmentId: assignment.assignment_id
        });
      } else {
        setSaveMessage(`❌ Failed to delete: ${data.message}`);
      }
    } catch (err) {
      setSaveMessage(`❌ Error: ${err.message}`);
    }
  };

  const handleTimelineBarRequest = async (assignment) => {
    if (!assignment.assignment_id) return;

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/calendar/change-assignment-status/${assignment.assignment_id}?new_status=requested`,
        { method: 'PATCH' }
      );

      if (!response.ok) {
        const errorData = await response.json();
        if (response.status === 500) {
          setSaveMessage(`❌ Failed to send request to FMS - assignment not marked as requested`);
        } else {
          setSaveMessage(`❌ Failed to request: ${errorData.detail || errorData.message || 'Unknown error'}`);
        }
        return;
      }

      const data = await response.json();

      if (data.success) {
        // Check if FMS action was performed
        if (data.fms_action === 'create') {
          setSaveMessage(`✅ Assignment requested! Request sent to FMS for approval.`);
        } else {
          setSaveMessage(`✅ Changed to requested`);
        }

        // Reload intelligence
        if (chainMode === 'partner' && selectedPartner && selectedOffice) {
          const resp = await fetch(
            `${API_BASE_URL}/api/ui/phase7/partner-intelligence?person_id=${selectedPartner}&office=${encodeURIComponent(selectedOffice)}`
          );
          if (resp.ok) {
            const reloadData = await resp.json();
            if (reloadData.success) {
              setPartnerIntelligence(reloadData);
            }
          }
        } else if (chainMode === 'vehicle' && selectedVehicle) {
          const now = new Date();
          const sixMonthsAgo = new Date(now.getFullYear(), now.getMonth() - 6, 1);
          const sixMonthsAhead = new Date(now.getFullYear(), now.getMonth() + 6, 0);
          const startDate = sixMonthsAgo.toISOString().split('T')[0];
          const endDate = sixMonthsAhead.toISOString().split('T')[0];

          const resp = await fetch(
            `${API_BASE_URL}/api/chain-builder/vehicle-busy-periods?vin=${encodeURIComponent(selectedVehicle.vin)}&start_date=${startDate}&end_date=${endDate}`
          );
          if (resp.ok) {
            const reloadData = await resp.json();
            setVehicleIntelligence(reloadData);
          }
        }

        // Emit event for Calendar
        EventManager.emit(EventTypes.CALENDAR_DATA_UPDATED, {
          office: selectedOffice,
          action: 'request',
          assignmentId: assignment.assignment_id
        });
      } else {
        setSaveMessage(`❌ Failed to request: ${data.message}`);
      }
    } catch (err) {
      setSaveMessage(`❌ Error: ${err.message}`);
    }
  };

  const handleTimelineBarUnrequest = async (assignment) => {
    if (!assignment.assignment_id) return;

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/calendar/change-assignment-status/${assignment.assignment_id}?new_status=manual`,
        { method: 'PATCH' }
      );

      if (!response.ok) {
        const errorData = await response.json();
        if (response.status === 500) {
          setSaveMessage(`❌ Failed to unrequest from FMS - request may still be active`);
        } else {
          setSaveMessage(`❌ Failed to unrequest: ${errorData.detail || errorData.message || 'Unknown error'}`);
        }
        return;
      }

      const data = await response.json();

      if (data.success) {
        // Check if FMS action was performed
        if (data.fms_action === 'delete') {
          setSaveMessage(`✅ Unrequested! Request deleted from FMS and changed back to manual.`);
        } else {
          setSaveMessage(`✅ Changed back to manual`);
        }

        // Reload intelligence
        if (chainMode === 'partner' && selectedPartner && selectedOffice) {
          const resp = await fetch(
            `${API_BASE_URL}/api/ui/phase7/partner-intelligence?person_id=${selectedPartner}&office=${encodeURIComponent(selectedOffice)}`
          );
          if (resp.ok) {
            const reloadData = await resp.json();
            if (reloadData.success) {
              setPartnerIntelligence(reloadData);
            }
          }
        } else if (chainMode === 'vehicle' && selectedVehicle) {
          const now = new Date();
          const sixMonthsAgo = new Date(now.getFullYear(), now.getMonth() - 6, 1);
          const sixMonthsAhead = new Date(now.getFullYear(), now.getMonth() + 6, 0);
          const startDate = sixMonthsAgo.toISOString().split('T')[0];
          const endDate = sixMonthsAhead.toISOString().split('T')[0];

          const resp = await fetch(
            `${API_BASE_URL}/api/chain-builder/vehicle-busy-periods?vin=${encodeURIComponent(selectedVehicle.vin)}&start_date=${startDate}&end_date=${endDate}`
          );
          if (resp.ok) {
            const reloadData = await resp.json();
            setVehicleIntelligence(reloadData);
          }
        }

        // Emit event for Calendar
        EventManager.emit(EventTypes.CALENDAR_DATA_UPDATED, {
          office: selectedOffice,
          action: 'unrequest',
          assignmentId: assignment.assignment_id
        });
      } else {
        setSaveMessage(`❌ Failed to unrequest: ${data.message}`);
      }
    } catch (err) {
      setSaveMessage(`❌ Error: ${err.message}`);
    }
  };

  const openSwapModal = async (vehicle, savedAssignment = null) => {
    setSwapSlot({
      ...vehicle,
      assignment_id: savedAssignment?.assignment_id
    });
    setSwapModalOpen(true);
    setLoadingSwap(true);

    try {
      // Call chain builder to get alternatives for this slot
      // Request a 1-vehicle chain for these specific dates
      const params = new URLSearchParams({
        person_id: selectedPartner,
        office: selectedOffice,
        start_date: vehicle.start_date,
        num_vehicles: 1,
        days_per_loan: daysPerLoan
      });

      if (selectedMakes.length > 0) {
        params.append('preferred_makes', selectedMakes.join(','));
      }

      const response = await fetch(`${API_BASE_URL}/api/chain-builder/suggest-chain?${params}`);
      const data = await response.json();

      if (response.ok && data.chain && data.chain.length > 0) {
        // Get top 5 alternatives
        const alternatives = data.slot_availability[0]?.available_count || 0;
        // For now, we'll need a new endpoint to get alternatives
        // Simplified: show message that swap will regenerate
        setSwapAlternatives([]);
      }
    } catch (err) {
      console.error('Error loading swap alternatives:', err);
    } finally {
      setLoadingSwap(false);
    }
  };

  const swapVehicle = async (newVehicle) => {
    // Delete old assignment, save new one
    try {
      if (swapSlot.assignment_id) {
        await fetch(`${API_BASE_URL}/api/calendar/delete-assignment/${swapSlot.assignment_id}`, {
          method: 'DELETE'
        });
      }

      // Save new vehicle
      await fetch(`${API_BASE_URL}/api/chain-builder/save-chain`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          person_id: selectedPartner,
          partner_name: partnerIntelligence.partner.name,
          office: selectedOffice,
          chain: [{
            vin: newVehicle.vin,
            make: newVehicle.make,
            model: newVehicle.model,
            start_date: swapSlot.start_date,
            end_date: swapSlot.end_date,
            score: newVehicle.score
          }]
        })
      });

      setSaveMessage(`✅ Swapped vehicle for Slot ${swapSlot.slot}`);
      setSwapModalOpen(false);

      // Reload partner intelligence
      if (selectedPartner && selectedOffice) {
        const response = await fetch(
          `${API_BASE_URL}/api/ui/phase7/partner-intelligence?person_id=${selectedPartner}&office=${encodeURIComponent(selectedOffice)}`
        );
        if (response.ok) {
          const data = await response.json();
          if (data.success) {
            setPartnerIntelligence(data);
          }
        }
      }
    } catch (err) {
      setSaveMessage(`❌ Error swapping: ${err.message}`);
    }
  };

  const deleteVehicleFromChain = async (assignmentId) => {
    if (!window.confirm('Remove this vehicle from the chain?')) {
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/calendar/delete-assignment/${assignmentId}`, {
        method: 'DELETE'
      });

      const result = await response.json();

      if (result.success) {
        setSaveMessage('✅ Vehicle removed from chain');

        // Reload partner intelligence to refresh
        if (selectedPartner && selectedOffice) {
          const resp = await fetch(
            `${API_BASE_URL}/api/ui/phase7/partner-intelligence?person_id=${selectedPartner}&office=${encodeURIComponent(selectedOffice)}`
          );
          if (resp.ok) {
            const data = await resp.json();
            if (data.success) {
              setPartnerIntelligence(data);
            }
          }
        }
      } else {
        setSaveMessage(`❌ ${result.message || 'Failed to delete'}`);
      }
    } catch (err) {
      setSaveMessage(`❌ Error: ${err.message}`);
    }
  };

  const clearChainBuilder = () => {
    if (!window.confirm('Clear Chain Builder and start fresh?')) {
      return;
    }

    // Clear all state
    setSelectedPartner('');
    setPartnerSearchQuery('');
    setChain(null);
    setError('');
    setSaveMessage('');
    setPartnerIntelligence(null);
    setSelectedMakes([]);
    setModelPreferences([]);  // Clear model preferences too
    setStartDate(getCurrentMonday());
    setManualSlots([]);
    setBuildMode('auto');

    // Clear sessionStorage
    sessionStorage.removeItem('chainbuilder_partner_id');
    sessionStorage.removeItem('chainbuilder_partner_name');
    sessionStorage.removeItem('chainbuilder_manual_slots');
    sessionStorage.removeItem('chainbuilder_build_mode');
    sessionStorage.removeItem('chainbuilder_start_date');
    sessionStorage.removeItem('chainbuilder_num_vehicles');
    sessionStorage.removeItem('chainbuilder_days_per_loan');
  };

  const saveChain = async () => {
    if (!chain || !chain.chain || chain.chain.length === 0) {
      setError('No chain to save');
      return;
    }

    if (!window.confirm(`Save this ${chain.chain.length}-vehicle chain for ${chain.partner_info.name}?`)) {
      return;
    }

    setIsSaving(true);
    setSaveMessage('');

    try {
      const response = await fetch(`${API_BASE_URL}/api/chain-builder/save-chain`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          person_id: chain.partner_info.person_id,
          partner_name: chain.partner_info.name,
          office: chain.partner_info.office,
          chain: chain.chain.map(v => ({
            vin: v.vin,
            make: v.make,
            model: v.model,
            start_date: v.start_date,
            end_date: v.end_date,
            score: v.score
          }))
        })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to save chain');
      }

      setSaveMessage(`✅ ${data.message} View in Calendar tab.`);
      console.log('Chain saved:', data);

      // Don't clear chain - keep showing it so × buttons appear
      // Just reload partner intelligence to get assignment IDs
      if (selectedPartner && selectedOffice) {
        const resp = await fetch(
          `${API_BASE_URL}/api/ui/phase7/partner-intelligence?person_id=${selectedPartner}&office=${encodeURIComponent(selectedOffice)}`
        );
        if (resp.ok) {
          const reloadData = await resp.json();
          if (reloadData.success) {
            setPartnerIntelligence(reloadData);
          }
        }
      }
    } catch (err) {
      setSaveMessage(`❌ Error: ${err.message}`);
    } finally {
      setIsSaving(false);
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
    setSaveMessage('');
    setChain(null);
    setManualSlots([]); // Clear existing chain immediately
    setChainBudget(null); // Clear budget display

    try {
      const params = new URLSearchParams({
        person_id: selectedPartner,
        office: selectedOffice,
        start_date: startDate,
        num_vehicles: numVehicles,
        days_per_loan: daysPerLoan,
        preference_mode: preferenceMode
      });

      // Add selected makes filter if any are selected (DEPRECATED - keeping for backward compat)
      if (selectedMakes.length > 0) {
        params.append('preferred_makes', selectedMakes.join(','));
      }

      // Add model preferences (NEW - OR-Tools support)
      if (modelPreferences.length > 0 && preferenceMode !== 'ignore') {
        params.append('model_preferences', JSON.stringify(modelPreferences));
      }

      const response = await fetch(`${API_BASE_URL}/api/chain-builder/suggest-chain?${params}`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to generate chain');
      }

      // Normalize response format for backward compatibility
      // New API returns 'suggested_chain', old code expects 'chain'
      const normalizedData = {
        ...data,
        chain: data.suggested_chain || data.chain || []
      };

      setChain(normalizedData);
      console.log('Chain generated:', normalizedData);

      // Convert auto-generated chain to manual slots format for editing
      const chainData = normalizedData.chain;
      const slots = chainData.map((vehicle, index) => ({
        slot: vehicle.slot,
        start_date: vehicle.start_date,
        end_date: vehicle.end_date,
        selected_vehicle: {
          vin: vehicle.vin,
          make: vehicle.make,
          model: vehicle.model,
          year: vehicle.year,
          color: vehicle.color || '',
          score: vehicle.score,
          tier: vehicle.tier,
          last_4_vin: vehicle.vin.slice(-4)
        },
        eligible_vehicles: [],  // Will load on dropdown open
        available_count: data.slot_availability?.[index]?.available_count || 0
      }));

      setManualSlots(slots);
      console.log('Converted to editable slots:', slots);

      // Calculate budget for auto-generated chain
      // Set flag to trigger budget calculation after state updates
      setShouldCalculateBudget(true);
    } catch (err) {
      setError(err.message);
      setChain(null);
    } finally {
      setIsLoading(false);
    }
  };

  const generateManualSlots = async () => {
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
    setSaveMessage('');
    setChain(null);
    setManualSlots([]);

    try {
      // First, get the slot dates by calling suggest-chain (we just need the slot dates, not the vehicles)
      const params = new URLSearchParams({
        person_id: selectedPartner,
        office: selectedOffice,
        start_date: startDate,
        num_vehicles: numVehicles,
        days_per_loan: daysPerLoan
      });

      // IMPORTANT: Pass make filter so counts are accurate
      if (selectedMakes.length > 0) {
        params.append('preferred_makes', selectedMakes.join(','));
      }

      const response = await fetch(`${API_BASE_URL}/api/chain-builder/suggest-chain?${params}`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to generate slots');
      }

      // Create empty slots with dates from the response
      const slots = data.slot_availability.map((slot, index) => ({
        slot: index + 1,
        start_date: slot.start_date,
        end_date: slot.end_date,
        selected_vehicle: null,
        eligible_vehicles: [],
        available_count: slot.available_count  // This now reflects filtered count
      }));

      setManualSlots(slots);
      console.log('Manual slots generated:', slots);

      // Budget will be calculated as vehicles are selected

      // Initialize timeline view to show the chain period
      if (slots.length > 0) {
        const dateStr = slots[0].start_date;
        const [year, month, day] = dateStr.split('-').map(Number);
        const monthStart = new Date(year, month - 1, 1);
        const monthEnd = new Date(year, month, 0);
        setViewStartDate(monthStart);
        setViewEndDate(monthEnd);
      }
    } catch (err) {
      setError(err.message);
      setManualSlots([]);
    } finally {
      setIsLoading(false);
    }
  };

  const loadSlotOptions = async (slotIndex) => {
    if (!selectedPartner || !manualSlots[slotIndex]) {
      return;
    }

    setLoadingSlotOptions(prev => ({ ...prev, [slotIndex]: true }));

    try {
      // Build exclude_vins from already-selected vehicles
      const excludeVins = manualSlots
        .filter((s, i) => i !== slotIndex && s.selected_vehicle)
        .map(s => s.selected_vehicle.vin)
        .join(',');

      const params = new URLSearchParams({
        person_id: selectedPartner,
        office: selectedOffice,
        start_date: startDate,
        num_vehicles: numVehicles,
        days_per_loan: daysPerLoan,
        slot_index: slotIndex
      });

      if (selectedMakes.length > 0) {
        params.append('preferred_makes', selectedMakes.join(','));
      }

      if (excludeVins) {
        params.append('exclude_vins', excludeVins);
      }

      const response = await fetch(`${API_BASE_URL}/api/chain-builder/get-slot-options?${params}`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to load slot options');
      }

      // Update the slot with eligible vehicles
      setManualSlots(prev => {
        const updated = [...prev];
        updated[slotIndex] = {
          ...updated[slotIndex],
          eligible_vehicles: data.eligible_vehicles
        };
        return updated;
      });

      console.log(`Loaded ${data.eligible_vehicles.length} options for slot ${slotIndex}`);
    } catch (err) {
      console.error('Error loading slot options:', err);
      setError(`Failed to load options for slot ${slotIndex + 1}: ${err.message}`);
    } finally {
      setLoadingSlotOptions(prev => ({ ...prev, [slotIndex]: false }));
    }
  };

  const selectVehicleForSlot = (slotIndex, vehicle) => {
    setManualSlots(prev => {
      const updated = [...prev];
      updated[slotIndex] = {
        ...updated[slotIndex],
        selected_vehicle: vehicle
      };
      return updated;
    });
    setShouldCalculateBudget(true);  // Trigger budget calc on user action
  };

  // Recalculate budget only when user actively changes slots (not on restore)
  const [shouldCalculateBudget, setShouldCalculateBudget] = useState(false);

  useEffect(() => {
    if (!shouldCalculateBudget) return;

    // Handle both Partner Chain and Vehicle Chain modes
    const shouldCalculate = chainMode === 'partner'
      ? (manualSlots.length > 0 && selectedPartner)
      : (manualPartnerSlots.length > 0 && selectedVehicle);

    if (shouldCalculate) {
      const timer = setTimeout(() => {
        calculateChainBudget();
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [manualSlots, manualPartnerSlots, selectedPartner, selectedVehicle, shouldCalculateBudget, chainMode]);

  // Save chain state to sessionStorage when it changes
  useEffect(() => {
    if (manualSlots.length > 0) {
      try {
        // Sanitize manualSlots to remove any circular references or DOM elements
        const sanitizedSlots = manualSlots.map(slot => ({
          slot: slot.slot,
          start_date: slot.start_date,
          end_date: slot.end_date,
          selected_vehicle: slot.selected_vehicle ? {
            vin: slot.selected_vehicle.vin,
            make: slot.selected_vehicle.make,
            model: slot.selected_vehicle.model,
            year: slot.selected_vehicle.year,
            score: slot.selected_vehicle.score,
            tier: slot.selected_vehicle.tier,
            last_4_vin: slot.selected_vehicle.last_4_vin
          } : null,
          available_count: slot.available_count
          // Do NOT save eligible_vehicles array - it can be huge and cause issues
        }));

        sessionStorage.setItem('chainbuilder_manual_slots', JSON.stringify(sanitizedSlots));
        sessionStorage.setItem('chainbuilder_build_mode', buildMode);
        sessionStorage.setItem('chainbuilder_start_date', startDate);
        sessionStorage.setItem('chainbuilder_num_vehicles', numVehicles.toString());
        sessionStorage.setItem('chainbuilder_days_per_loan', daysPerLoan.toString());
      } catch (err) {
        console.error('Error saving to sessionStorage:', err);
      }
    }
  }, [manualSlots, buildMode, startDate, numVehicles, daysPerLoan]);

  // ============================================================
  // VEHICLE CHAIN FUNCTIONS
  // ============================================================

  const generateVehicleChain = async () => {
    if (!selectedVehicle) {
      setError('Please select a vehicle');
      return;
    }

    if (!startDate) {
      setError('Please select a start date');
      return;
    }

    setIsLoading(true);
    setError('');
    setSaveMessage('');
    setVehicleChain(null);
    setManualPartnerSlots([]); // Clear existing slots immediately
    setChainBudget(null); // Clear budget display
    setChainModified(false);

    try {
      const params = new URLSearchParams({
        vin: selectedVehicle.vin,
        office: selectedOffice,
        start_date: startDate,
        num_partners: numVehicles,  // Reusing numVehicles slider for num_partners
        days_per_loan: daysPerLoan,
        distance_weight: 0.7,
        max_distance_per_hop: 50.0
      });

      // Add tier filter if any tiers are deselected
      if (selectedTiers.length > 0 && selectedTiers.length < 4) {
        params.append('partner_tier_filter', selectedTiers.join(','));
      }

      const response = await fetch(`${API_BASE_URL}/api/chain-builder/suggest-vehicle-chain?${params}`, {
        method: 'POST'
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || data.message || 'Failed to generate vehicle chain');
      }

      setVehicleChain(data);
      console.log('Vehicle chain generated:', data);

      // Helper to calculate distance
      const calculateDistance = (lat1, lon1, lat2, lon2) => {
        const R = 3956;
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLon = (lon2 - lon1) * Math.PI / 180;
        const a =
          Math.sin(dLat/2) * Math.sin(dLat/2) +
          Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
          Math.sin(dLon/2) * Math.sin(dLon/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        return R * c;
      };

      // Convert to manual slots format for editing
      const slots = data.optimal_chain.map((partner, index) => {
        let distanceFromPrev = null;

        if (index === 0) {
          // Slot 0: use office distance
          distanceFromPrev = partner.office_distance || null;
        } else {
          // Slot 1+: Get distance from PREVIOUS partner's handoff (handoff goes TO this slot)
          const prevPartner = data.optimal_chain[index - 1];
          if (prevPartner && prevPartner.handoff) {
            distanceFromPrev = prevPartner.handoff.distance_miles;
          } else if (prevPartner && prevPartner.latitude && prevPartner.longitude && partner.latitude && partner.longitude) {
            // Fallback if handoff missing
            distanceFromPrev = calculateDistance(
              prevPartner.latitude,
              prevPartner.longitude,
              partner.latitude,
              partner.longitude
            );
          }
        }

        return {
          slot: partner.slot,
          start_date: partner.start_date,
          end_date: partner.end_date,
          selected_partner: {
            person_id: partner.person_id,
            name: partner.name,
            address: partner.address || 'Address not available',
            base_score: partner.score,
            final_score: partner.score,
            tier: partner.tier,
            engagement_level: partner.engagement_level,
            latitude: partner.latitude,
            longitude: partner.longitude,
            distance_from_previous: distanceFromPrev
          },
          eligible_partners: []
        };
      });

      setManualPartnerSlots(slots);
      console.log('Converted to editable partner slots:', slots);

      // Calculate budget for auto-generated vehicle chain
      setShouldCalculateBudget(true);

      // Set timeline view to show the chain's start month
      if (slots.length > 0 && slots[0].start_date) {
        const chainStart = new Date(slots[0].start_date + 'T00:00:00');
        const monthStart = new Date(chainStart.getFullYear(), chainStart.getMonth(), 1);
        const monthEnd = new Date(chainStart.getFullYear(), chainStart.getMonth() + 1, 0);
        setViewStartDate(monthStart);
        setViewEndDate(monthEnd);
      }

    } catch (err) {
      setError(err.message);
      setVehicleChain(null);
    } finally {
      setIsLoading(false);
    }
  };

  const generateManualPartnerSlots = async () => {
    if (!selectedVehicle) {
      setError('Please select a vehicle');
      return;
    }

    if (!startDate) {
      setError('Please select a start date');
      return;
    }

    setIsLoading(true);
    setError('');
    setSaveMessage('');
    setVehicleChain(null);
    setManualPartnerSlots([]);

    try {
      // Calculate slot dates with weekend extension (client-side)
      const calculateSlotDates = (startDateStr, numSlots, daysPerLoan) => {
        const slots = [];
        let currentStart = new Date(startDateStr + 'T00:00:00');

        for (let i = 0; i < numSlots; i++) {
          // Calculate end date (start + days - 1)
          let endDate = new Date(currentStart);
          endDate.setDate(endDate.getDate() + daysPerLoan - 1);

          // Weekend extension: If end date is Sat/Sun, extend to Monday
          const dayOfWeek = endDate.getDay();
          if (dayOfWeek === 6) { // Saturday
            endDate.setDate(endDate.getDate() + 2); // → Monday
          } else if (dayOfWeek === 0) { // Sunday
            endDate.setDate(endDate.getDate() + 1); // → Monday
          }

          // Format dates as YYYY-MM-DD
          const formatDate = (date) => {
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            return `${year}-${month}-${day}`;
          };

          slots.push({
            slot: i,
            start_date: formatDate(currentStart),
            end_date: formatDate(endDate),
            selected_partner: null,
            eligible_partners: []
          });

          // Next slot starts the day after this one ends (same-day handoff)
          currentStart = new Date(endDate);
          currentStart.setDate(currentStart.getDate() + 1);
        }

        return slots;
      };

      const slots = calculateSlotDates(startDate, numVehicles, daysPerLoan);
      setManualPartnerSlots(slots);
      console.log(`Created ${numVehicles} empty partner slots with dates:`, slots);

      // Set timeline view to show the chain's start month
      if (slots.length > 0 && slots[0].start_date) {
        const chainStart = new Date(slots[0].start_date + 'T00:00:00');
        const monthStart = new Date(chainStart.getFullYear(), chainStart.getMonth(), 1);
        const monthEnd = new Date(chainStart.getFullYear(), chainStart.getMonth() + 1, 0);
        setViewStartDate(monthStart);
        setViewEndDate(monthEnd);
      }

    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const loadPartnerSlotOptions = async (slotIndex) => {
    if (!selectedVehicle || !manualPartnerSlots[slotIndex]) {
      return;
    }

    setLoadingPartnerSlotOptions(prev => ({ ...prev, [slotIndex]: true }));

    try {
      // Build exclude_partner_ids from already-selected partners
      const excludePartnerIds = manualPartnerSlots
        .filter((s, i) => i !== slotIndex && s.selected_partner)
        .map(s => s.selected_partner.person_id)
        .join(',');

      // Get previous partner info for distance calculation
      let previousPartnerId = null;
      let previousPartnerLat = null;
      let previousPartnerLng = null;

      if (slotIndex > 0) {
        const prevSlot = manualPartnerSlots[slotIndex - 1];
        if (prevSlot && prevSlot.selected_partner) {
          previousPartnerId = prevSlot.selected_partner.person_id;
          previousPartnerLat = prevSlot.selected_partner.latitude;
          previousPartnerLng = prevSlot.selected_partner.longitude;
        }
      }

      const params = new URLSearchParams({
        vin: selectedVehicle.vin,
        office: selectedOffice,
        start_date: startDate,
        num_partners: numVehicles,
        days_per_loan: daysPerLoan,
        slot_index: slotIndex
      });

      if (excludePartnerIds) {
        params.append('exclude_partner_ids', excludePartnerIds);
      }

      if (previousPartnerId) {
        params.append('previous_partner_id', previousPartnerId);
        params.append('previous_partner_lat', previousPartnerLat);
        params.append('previous_partner_lng', previousPartnerLng);
      }

      const response = await fetch(`${API_BASE_URL}/api/chain-builder/get-partner-slot-options?${params}`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to load partner options');
      }

      // Update this slot with eligible partners
      setManualPartnerSlots(prev => {
        const updated = [...prev];
        updated[slotIndex] = {
          ...updated[slotIndex],
          start_date: data.slot.start_date,
          end_date: data.slot.end_date,
          eligible_partners: data.eligible_partners || []
        };
        return updated;
      });

      console.log(`Loaded ${data.eligible_partners?.length || 0} partner options for slot ${slotIndex}`);

    } catch (err) {
      console.error(`Failed to load partner options for slot ${slotIndex}:`, err);
      setError(err.message);
    } finally {
      setLoadingPartnerSlotOptions(prev => ({ ...prev, [slotIndex]: false }));
    }
  };

  const selectPartnerForSlot = (slotIndex, partner) => {
    // Haversine distance formula
    const calculateDistance = (lat1, lon1, lat2, lon2) => {
      const R = 3956;
      const dLat = (lat2 - lat1) * Math.PI / 180;
      const dLon = (lon2 - lon1) * Math.PI / 180;
      const a =
        Math.sin(dLat/2) * Math.sin(dLat/2) +
        Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
        Math.sin(dLon/2) * Math.sin(dLon/2);
      const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
      return R * c;
    };

    setManualPartnerSlots(prev => {
      const updated = [...prev];

      // Update the selected partner for this slot
      updated[slotIndex] = {
        ...updated[slotIndex],
        selected_partner: partner
      };

      // CRITICAL: Recalculate distances for ALL downstream slots
      for (let i = slotIndex + 1; i < updated.length; i++) {
        const prevSlot = updated[i - 1];
        const currSlot = updated[i];

        // Clear eligible_partners so dropdown reloads with NEW distances from NEW previous partner
        updated[i].eligible_partners = [];

        if (currSlot.selected_partner && prevSlot.selected_partner) {
          if (prevSlot.selected_partner.latitude && prevSlot.selected_partner.longitude &&
              currSlot.selected_partner.latitude && currSlot.selected_partner.longitude) {
            const distance = calculateDistance(
              prevSlot.selected_partner.latitude,
              prevSlot.selected_partner.longitude,
              currSlot.selected_partner.latitude,
              currSlot.selected_partner.longitude
            );

            updated[i].selected_partner = {
              ...updated[i].selected_partner,
              distance_from_previous: distance
            };
          }
        }
      }

      return updated;
    });

    // Recalculate logistics summary immediately using the updated slots
    setManualPartnerSlots(prevSlots => {
      // Use the already-updated slots from above
      if (vehicleChain) {
        let totalDistance = 0;

        for (let i = 0; i < prevSlots.length; i++) {
          const slot = prevSlots[i];
          if (slot.selected_partner && slot.selected_partner.distance_from_previous) {
            totalDistance += slot.selected_partner.distance_from_previous;
          }
        }

        const estimateDriveTime = (miles) => Math.round(miles / 20 * 60);
        const totalDriveTime = estimateDriveTime(totalDistance);
        const totalCost = totalDistance * 2.0;

        setVehicleChain(prev => ({
          ...prev,
          logistics_summary: {
            ...prev.logistics_summary,
            total_distance_miles: totalDistance,
            total_drive_time_min: totalDriveTime,
            total_logistics_cost: totalCost,
            average_hop_distance: totalDistance / (prevSlots.length - 1)
          }
        }));

        setChainModified(true);
      }

      return prevSlots; // Return unchanged since we already updated above
    });

    console.log(`Selected ${partner.name} for slot ${slotIndex}, recalculated downstream distances`);

    // Trigger budget calculation for Vehicle Chain mode
    setShouldCalculateBudget(true);
  };

  const deletePartnerSlot = (slotIndex) => {
    setManualPartnerSlots(prev => {
      const updated = [...prev];
      updated[slotIndex] = {
        ...updated[slotIndex],
        selected_partner: null
      };
      return updated;
    });
  };

  // Edit/Change partner in slot (works for both auto-generated and manual chains)
  const handleEditSlot = async (slotIndex) => {
    if (!selectedVehicle || !manualPartnerSlots[slotIndex]) {
      return;
    }

    // Just call loadPartnerSlotOptions which does the same thing
    await loadPartnerSlotOptions(slotIndex);
  };

  const handleSwapPartner = (slotIndex, newPartner) => {
    // Haversine distance formula
    const calculateDistance = (lat1, lon1, lat2, lon2) => {
      const R = 3956; // Earth radius in miles
      const dLat = (lat2 - lat1) * Math.PI / 180;
      const dLon = (lon2 - lon1) * Math.PI / 180;
      const a =
        Math.sin(dLat/2) * Math.sin(dLat/2) +
        Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
        Math.sin(dLon/2) * Math.sin(dLon/2);
      const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
      return R * c;
    };

    const estimateDriveTime = (miles) => {
      return Math.round(miles / 20 * 60); // 20 mph average, convert to minutes
    };

    // Update manualPartnerSlots with new partner
    const updatedSlots = [...manualPartnerSlots];

    // Swap the partner in this slot
    updatedSlots[slotIndex] = {
      ...updatedSlots[slotIndex],
      selected_partner: {
        person_id: newPartner.person_id,
        name: newPartner.name,
        address: newPartner.address,
        latitude: newPartner.latitude,
        longitude: newPartner.longitude,
        base_score: newPartner.base_score,
        final_score: newPartner.final_score,
        tier: newPartner.tier,
        engagement_level: newPartner.engagement_level,
        distance_from_previous: newPartner.distance_from_previous
      }
    };

    // Recalculate distances for all subsequent slots
    for (let i = slotIndex + 1; i < updatedSlots.length; i++) {
      const prevSlot = updatedSlots[i - 1];
      const currSlot = updatedSlots[i];

      if (prevSlot.selected_partner && currSlot.selected_partner) {
        if (prevSlot.selected_partner.latitude && prevSlot.selected_partner.longitude &&
            currSlot.selected_partner.latitude && currSlot.selected_partner.longitude) {
          const distance = calculateDistance(
            prevSlot.selected_partner.latitude,
            prevSlot.selected_partner.longitude,
            currSlot.selected_partner.latitude,
            currSlot.selected_partner.longitude
          );

          // Update distance in selected_partner
          updatedSlots[i].selected_partner = {
            ...updatedSlots[i].selected_partner,
            distance_from_previous: distance
          };
        }
      }
    }

    // Update manual slots
    setManualPartnerSlots(updatedSlots);

    // Recalculate logistics summary if vehicleChain exists
    if (vehicleChain) {
      let totalDistance = 0;
      let totalDriveTime = 0;
      let totalCost = 0;

      for (let i = 1; i < updatedSlots.length; i++) {
        const slot = updatedSlots[i];
        if (slot.selected_partner && slot.selected_partner.distance_from_previous) {
          const dist = slot.selected_partner.distance_from_previous;
          totalDistance += dist;
          totalDriveTime += estimateDriveTime(dist);
          totalCost += dist * 2.0;
        }
      }

      const updatedLogisticsSummary = {
        ...vehicleChain.logistics_summary,
        total_distance_miles: totalDistance,
        total_drive_time_min: totalDriveTime,
        total_logistics_cost: totalCost,
        average_hop_distance: totalDistance / (updatedSlots.length - 1)
      };

      setVehicleChain({
        ...vehicleChain,
        logistics_summary: updatedLogisticsSummary
      });

      setChainModified(true);
    }

    console.log(`Swapped slot ${slotIndex} to ${newPartner.name}, recalculated ${updatedSlots.length - slotIndex - 1} downstream distances`);
  };

  // Save vehicle chain function
  const saveVehicleChain = async (saveStatus = 'manual') => {
    if (!selectedVehicle || !manualPartnerSlots.length) {
      setError('No chain to save');
      return;
    }

    // Check all slots have partners
    const allFilled = manualPartnerSlots.every(s => s.selected_partner);
    if (!allFilled) {
      setError('Please select partners for all slots before saving');
      return;
    }

    setIsSaving(true);
    setSaveMessage('');
    setError('');

    try {
      const chainData = manualPartnerSlots.map(slot => ({
        person_id: slot.selected_partner.person_id,
        partner_name: slot.selected_partner.name,
        start_date: slot.start_date,
        end_date: slot.end_date,
        score: slot.selected_partner.final_score || slot.selected_partner.base_score || 0
      }));

      const payload = {
        vin: selectedVehicle.vin,
        vehicle_make: selectedVehicle.make,
        vehicle_model: selectedVehicle.model,
        office: selectedOffice,
        status: saveStatus,
        chain: chainData
      };

      const response = await fetch(`${API_BASE_URL}/api/chain-builder/save-vehicle-chain`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to save vehicle chain');
      }

      setSaveMessage(`✅ ${data.message} Slots cleared for next build.`);
      console.log('Vehicle chain saved:', data);

      // If saved as 'requested', send to FMS
      if (saveStatus === 'requested' && data.assignment_ids && data.assignment_ids.length > 0) {
        try {
          const fmsResponse = await fetch(`${API_BASE_URL}/api/fms/bulk-create-vehicle-requests`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ assignment_ids: data.assignment_ids })
          });

          const fmsResult = await fmsResponse.json();

          if (fmsResult.succeeded > 0) {
            setSaveMessage(`✅ Chain saved and ${fmsResult.succeeded}/${fmsResult.total} requests sent to FMS!`);
          } else {
            setSaveMessage(`⚠️ Chain saved but FMS requests failed. See console for details.`);
            console.error('FMS bulk request failed:', fmsResult);
          }
        } catch (fmsError) {
          console.error('Failed to send bulk requests to FMS:', fmsError);
          setSaveMessage(`⚠️ Chain saved but failed to send to FMS: ${fmsError.message}`);
        }
      }

      // Clear modified flag
      setChainModified(false);

      // Clear the chain slots for next build
      setManualPartnerSlots([]);
      setVehicleChain(null);

      // Reload vehicle intelligence to show the saved assignments
      if (selectedVehicle) {
        try {
          const now = new Date();
          const sixMonthsAgo = new Date(now.getFullYear(), now.getMonth() - 6, 1);
          const sixMonthsAhead = new Date(now.getFullYear(), now.getMonth() + 6, 0);
          const startDate = sixMonthsAgo.toISOString().split('T')[0];
          const endDate = sixMonthsAhead.toISOString().split('T')[0];

          const resp = await fetch(
            `${API_BASE_URL}/api/chain-builder/vehicle-busy-periods?vin=${encodeURIComponent(selectedVehicle.vin)}&start_date=${startDate}&end_date=${endDate}`
          );

          if (resp.ok) {
            const reloadData = await resp.json();
            setVehicleIntelligence(reloadData);
          }
        } catch (reloadErr) {
          console.error('Failed to reload vehicle intelligence:', reloadErr);
        }
      }

      // Emit event so Calendar component can reload
      EventManager.emit(EventTypes.CHAIN_DATA_UPDATED, {
        office: selectedOffice,
        vin: selectedVehicle.vin,
        status: saveStatus,
        assignmentIds: data.assignment_ids
      });

    } catch (err) {
      setError(err.message);
      setSaveMessage(`❌ Error: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  // ============================================================
  // END VEHICLE CHAIN FUNCTIONS
  // ============================================================

  const calculateChainBudget = async () => {
    // Handle both Partner Chain and Vehicle Chain modes
    let chainData;

    if (chainMode === 'partner') {
      // Partner Chain mode: one partner, multiple vehicles
      const filledSlots = manualSlots.filter(s => s.selected_vehicle);
      console.log('[Budget] Partner Chain mode. Filled slots:', filledSlots.length, 'Partner:', selectedPartner);

      if (filledSlots.length === 0 || !selectedPartner) {
        console.log('[Budget] No filled slots or no partner selected, clearing budget');
        setChainBudget(null);
        return;
      }

      chainData = filledSlots.map(slot => ({
        person_id: selectedPartner,
        make: slot.selected_vehicle.make,
        start_date: slot.start_date
      }));
    } else {
      // Vehicle Chain mode: one vehicle, multiple partners
      const filledSlots = manualPartnerSlots.filter(s => s.selected_partner);
      console.log('[Budget] Vehicle Chain mode. Filled slots:', filledSlots.length, 'Vehicle:', selectedVehicle?.vin);

      if (filledSlots.length === 0 || !selectedVehicle) {
        console.log('[Budget] No filled slots or no vehicle selected, clearing budget');
        setChainBudget(null);
        return;
      }

      chainData = filledSlots.map(slot => ({
        person_id: slot.selected_partner.person_id,
        make: selectedVehicle.make,
        start_date: slot.start_date
      }));
    }

    try {
      console.log('[Budget] Requesting budget with chain data:', chainData);

      const response = await fetch(`${API_BASE_URL}/api/chain-builder/calculate-chain-budget`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          office: selectedOffice,
          chain: chainData
        })
      });

      const data = await response.json();
      console.log('[Budget] Budget response:', data);
      setChainBudget(data);
    } catch (err) {
      console.error('[Budget] Error calculating budget:', err);
      setChainBudget(null);
    }
  };

  const saveManualChain = async (status = 'manual') => {
    // Check if all slots have vehicles selected
    const unfilledSlots = manualSlots.filter(s => !s.selected_vehicle);
    if (unfilledSlots.length > 0) {
      setError(`Please select vehicles for all ${manualSlots.length} slots (${unfilledSlots.length} remaining)`);
      return;
    }

    const partner = partners.find(p => p.person_id === selectedPartner);
    if (!partner) {
      setError('Partner not found');
      return;
    }

    const statusLabel = status === 'requested' ? 'and send to FMS' : 'as recommendations';
    if (!window.confirm(`Save this ${manualSlots.length}-vehicle chain ${statusLabel} for ${partner.name}?`)) {
      return;
    }

    setIsSaving(true);
    setSaveMessage('');

    try {
      const chainData = manualSlots.map(slot => ({
        vin: slot.selected_vehicle.vin,
        make: slot.selected_vehicle.make,
        model: slot.selected_vehicle.model,
        start_date: slot.start_date,
        end_date: slot.end_date,
        score: slot.selected_vehicle.score
      }));

      const payload = {
        person_id: selectedPartner,
        partner_name: partner.name,
        office: selectedOffice,
        status: status,  // 'manual' or 'requested'
        chain: chainData
      };

      console.log('Saving chain with payload:', payload);

      let payloadString;
      try {
        payloadString = JSON.stringify(payload);
      } catch (jsonError) {
        console.error('JSON stringify error:', jsonError);
        console.error('Problematic payload:', payload);
        throw new Error(`Failed to serialize payload: ${jsonError.message}`);
      }

      const response = await fetch(`${API_BASE_URL}/api/chain-builder/save-chain`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: payloadString
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to save chain');
      }

      setSaveMessage(`✅ ${data.message} Slots cleared for next build.`);
      console.log('Manual chain saved:', data);

      // If saved as 'requested', send to FMS
      if (status === 'requested' && data.assignment_ids && data.assignment_ids.length > 0) {
        try {
          const fmsResponse = await fetch(`${API_BASE_URL}/api/fms/bulk-create-vehicle-requests`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ assignment_ids: data.assignment_ids })
          });

          const fmsResult = await fmsResponse.json();

          if (fmsResult.succeeded > 0) {
            setSaveMessage(`✅ Chain saved and ${fmsResult.succeeded}/${fmsResult.total} requests sent to FMS!`);
          } else {
            setSaveMessage(`⚠️ Chain saved but FMS requests failed. See console for details.`);
            console.error('FMS bulk request failed:', fmsResult);
          }
        } catch (fmsError) {
          console.error('Failed to send bulk requests to FMS:', fmsError);
          setSaveMessage(`⚠️ Chain saved but failed to send to FMS: ${fmsError.message}`);
        }
      }

      // Clear the proposed chain slots (green bars) since they're now saved
      setManualSlots([]);
      setChain(null);

      // Reload partner intelligence to show the saved assignments (magenta/green bars)
      if (selectedPartner && selectedOffice) {
        const resp = await fetch(
          `${API_BASE_URL}/api/ui/phase7/partner-intelligence?person_id=${selectedPartner}&office=${encodeURIComponent(selectedOffice)}`
        );
        if (resp.ok) {
          const reloadData = await resp.json();
          if (reloadData.success) {
            setPartnerIntelligence(reloadData);
          }
        }
      }

      // Emit event so Calendar component can reload
      EventManager.emit(EventTypes.CHAIN_DATA_UPDATED, {
        office: selectedOffice,
        partnerId: selectedPartner,
        status: status,
        assignmentIds: data.assignment_ids
      });
    } catch (err) {
      setSaveMessage(`❌ Error: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="w-full min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="!text-base font-semibold text-gray-900">Chain Builder</h1>
              <span className="inline-flex items-center rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700 border border-blue-200">
                📍 {selectedOffice}
              </span>
            </div>
            <p className="text-sm text-gray-500 mt-1">
              {chainMode === 'partner'
                ? 'Create sequential vehicle assignments for a media partner'
                : 'Create sequential partner assignments for a vehicle'}
            </p>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3">
              <label className="text-sm text-gray-600">Office</label>
              <select
                value={selectedOffice}
                onChange={(e) => handleOfficeChange(e.target.value)}
                className="border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {offices.map(office => (
                  <option key={office} value={office}>{office}</option>
                ))}
              </select>
            </div>

            {/* Refresh Button */}
            {selectedPartner && (
              <button
                onClick={refreshPartnerIntelligence}
                disabled={loadingIntelligence}
                className="px-3 py-1.5 border border-gray-300 rounded text-sm text-blue-600 hover:bg-blue-50 disabled:opacity-50"
                title="Refresh partner calendar data"
              >
                {loadingIntelligence ? 'Refreshing...' : '🔄 Refresh'}
              </button>
            )}

            {/* Clear/Reset Button */}
            {selectedPartner && (
              <button
                onClick={clearChainBuilder}
                className="px-3 py-1.5 border border-gray-300 rounded text-sm text-gray-600 hover:bg-gray-50"
                title="Clear and start fresh"
              >
                Clear
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="bg-white border-b">
        <div className="px-6">
          <div className="flex gap-1">
            <button
              onClick={() => setChainMode('partner')}
              className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                chainMode === 'partner'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Partner Chain
            </button>
            <button
              onClick={() => setChainMode('vehicle')}
              className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                chainMode === 'vehicle'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Vehicle Chain
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex flex-col lg:flex-row h-full">
        {/* Left Panel - Chain Parameters - WIDER for 2-column layout, stack on mobile */}
        <div className="w-full lg:w-[520px] bg-white border-b lg:border-b-0 lg:border-r p-6 overflow-y-auto">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">Chain Parameters</h2>

          <div className="space-y-4">
            {/* Partner Chain Mode - Partner Selector */}
            {chainMode === 'partner' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Media Partner
                </label>

                <Combobox
                  value={selectedPartnerObj}
                  onChange={(partner) => {
                    setSelectedPartner(partner?.person_id || '');
                    setPartnerSearchQuery('');
                    setModelPreferences([]);
                  }}
                >
                  <div className="relative">
                    <div className="relative w-full">
                      <Combobox.Input
                        className="w-full border border-gray-300 rounded px-3 py-2 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        displayValue={(partner) => partner?.name ? formatPartnerName(partner.name, 'lastFirst') : ''}
                        onChange={(event) => setPartnerSearchQuery(event.target.value)}
                        placeholder="Select or search partner..."
                      />
                      <Combobox.Button
                        className="absolute inset-y-0 right-0 flex items-center pr-2"
                        onClick={() => setPartnerSearchQuery('')}
                      >
                        <svg className="h-5 w-5 text-gray-400" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
                        </svg>
                      </Combobox.Button>
                    </div>

                    <Transition
                      as={Fragment}
                      leave="transition ease-in duration-100"
                      leaveFrom="opacity-100"
                      leaveTo="opacity-0"
                      afterLeave={() => setPartnerSearchQuery('')}
                    >
                      <Combobox.Options className="absolute z-10 mt-1 w-full bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-y-auto">
                        {partners
                          .filter(partner => {
                            // Search query filter
                            const searchLower = partnerSearchQuery.toLowerCase();
                            const matchesSearch = partnerSearchQuery === '' || partner.name.toLowerCase().includes(searchLower);

                            // Review history filter (if active)
                            if (vehicleHistoryFilter && vehicleHistoryFilter.reviewHistory) {
                              const reviewedPartnerIds = new Set(
                                vehicleHistoryFilter.reviewHistory.reviews.map(r => r.person_id)
                              );
                              return matchesSearch && reviewedPartnerIds.has(partner.person_id);
                            }

                            return matchesSearch;
                          })
                          .sort((a, b) => {
                            // Sort by last name, removing leading special characters (quotes, parentheses, etc.)
                            const aFormatted = formatPartnerName(a.name, 'lastFirst').replace(/^[^\w]+/, '');
                            const bFormatted = formatPartnerName(b.name, 'lastFirst').replace(/^[^\w]+/, '');
                            return aFormatted.localeCompare(bFormatted);
                          })
                          .map((partner) => (
                            <Combobox.Option
                              key={partner.person_id}
                              value={partner}
                              className={({ active }) =>
                                `relative cursor-pointer select-none py-2 px-3 text-sm ${
                                  active ? 'bg-blue-50 text-blue-900' : 'text-gray-900'
                                }`
                              }
                            >
                              {({ selected }) => (
                                <div className="flex items-center justify-between">
                                  <span className={selected ? 'font-semibold' : 'font-normal'}>
                                    {formatPartnerName(partner.name, 'lastFirst')}
                                  </span>
                                  {selected && (
                                    <svg className="h-5 w-5 text-blue-600" viewBox="0 0 20 20" fill="currentColor">
                                      <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clipRule="evenodd" />
                                    </svg>
                                  )}
                                </div>
                              )}
                            </Combobox.Option>
                          ))}
                        {partners.filter(p => {
                          const searchLower = partnerSearchQuery.toLowerCase();
                          return partnerSearchQuery === '' || p.name.toLowerCase().includes(searchLower);
                        }).length === 0 && (
                          <div className="px-3 py-4 text-sm text-gray-500 text-center">
                            No partners found
                          </div>
                        )}
                      </Combobox.Options>
                    </Transition>
                  </div>
                </Combobox>

              {/* Vehicle History Filter Indicator */}
              {vehicleHistoryFilter && (
                <div className="mt-2 p-2 bg-indigo-50 border border-indigo-200 rounded flex items-center justify-between">
                  <span className="text-xs text-indigo-700 font-semibold flex items-center gap-1">
                    <span>🔍</span>
                    <span>Filtered: Partners who reviewed {vehicleHistoryFilter.vin}</span>
                  </span>
                  <button
                    onClick={() => {
                      setVehicleHistoryFilter(null);
                      window.dispatchEvent(new CustomEvent(EventTypes.CLEAR_HISTORY_FILTERS));
                    }}
                    className="text-indigo-700 hover:text-indigo-900 font-bold text-sm"
                  >
                    ✕
                  </button>
                </div>
              )}
              </div>
            )}

            {/* Vehicle Chain Mode - Vehicle Selector */}
            {chainMode === 'vehicle' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Vehicle
                </label>

                <Combobox
                  value={selectedVehicle}
                  onChange={(vehicle) => {
                    setSelectedVehicle(vehicle);
                    setVehicleSearchQuery('');
                  }}
                >
                  <div className="relative">
                    <div className="relative w-full">
                      <Combobox.Input
                        className="w-full border border-gray-300 rounded px-3 py-2 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        displayValue={(vehicle) => vehicle ? `${vehicle.make} ${vehicle.model} ${vehicle.year}` : ''}
                        onChange={(event) => setVehicleSearchQuery(event.target.value)}
                        placeholder="Select or search vehicle..."
                      />
                      <Combobox.Button
                        className="absolute inset-y-0 right-0 flex items-center pr-2"
                        onClick={() => setVehicleSearchQuery('')}
                      >
                        <svg className="h-5 w-5 text-gray-400" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
                        </svg>
                      </Combobox.Button>
                    </div>

                    <Transition
                      as={Fragment}
                      leave="transition ease-in duration-100"
                      leaveFrom="opacity-100"
                      leaveTo="opacity-0"
                      afterLeave={() => setVehicleSearchQuery('')}
                    >
                      <Combobox.Options className="absolute z-10 mt-1 w-full bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-y-auto">
                        {vehicles
                          .filter(vehicle => {
                            // Search query filter
                            const searchLower = vehicleSearchQuery.toLowerCase();
                            if (vehicleSearchQuery === '') return true;

                            return (
                              vehicle.make.toLowerCase().includes(searchLower) ||
                              vehicle.model.toLowerCase().includes(searchLower) ||
                              vehicle.vin.toLowerCase().includes(searchLower) ||
                              vehicle.year?.toString().includes(searchLower)
                            );
                          })
                          .sort((a, b) => {
                            // Sort by make, then model
                            const makeCompare = a.make.localeCompare(b.make);
                            if (makeCompare !== 0) return makeCompare;
                            return a.model.localeCompare(b.model);
                          })
                          .map((vehicle) => (
                            <Combobox.Option
                              key={vehicle.vin}
                              value={vehicle}
                              className={({ active }) =>
                                `relative cursor-pointer select-none py-2 px-3 text-sm ${
                                  active ? 'bg-blue-50 text-blue-900' : 'text-gray-900'
                                }`
                              }
                            >
                              {({ selected }) => (
                                <div>
                                  <div className="flex items-center justify-between">
                                    <span className={selected ? 'font-semibold' : 'font-medium'}>
                                      {vehicle.make} {vehicle.model} {vehicle.year}
                                    </span>
                                    {selected && (
                                      <svg className="h-5 w-5 text-blue-600" viewBox="0 0 20 20" fill="currentColor">
                                        <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clipRule="evenodd" />
                                      </svg>
                                    )}
                                  </div>
                                  <div className="text-xs text-gray-500 mt-0.5">
                                    VIN: ...{vehicle.vin.slice(-8)}{vehicle.color ? ` | ${vehicle.color}` : ''}
                                  </div>
                                </div>
                              )}
                            </Combobox.Option>
                          ))}
                        {vehicles.filter(v => {
                          const searchLower = vehicleSearchQuery.toLowerCase();
                          return vehicleSearchQuery === '' ||
                                 v.make.toLowerCase().includes(searchLower) ||
                                 v.model.toLowerCase().includes(searchLower) ||
                                 v.vin.toLowerCase().includes(searchLower);
                        }).length === 0 && (
                          <div className="px-3 py-4 text-sm text-gray-500 text-center">
                            No vehicles found
                          </div>
                        )}
                      </Combobox.Options>
                    </Transition>
                  </div>
                </Combobox>

                {/* Selected Vehicle Display */}
                {selectedVehicle && (
                  <div className="mt-2 p-3 bg-gray-50 border border-gray-200 rounded text-xs">
                    <div className="font-medium text-gray-900">
                      {selectedVehicle.make} {selectedVehicle.model} {selectedVehicle.year}
                    </div>
                    <div className="text-gray-600 mt-1">
                      VIN: {selectedVehicle.vin}
                    </div>
                    <div className="text-gray-600">
                      Trim: {selectedVehicle.trim} | Tier: {selectedVehicle.tier}
                    </div>
                    {selectedVehicle.color && (
                      <div className="text-gray-600">
                        Color: {selectedVehicle.color}
                      </div>
                    )}
                  </div>
                )}

                {/* Partner History Filter Indicator */}
                {partnerHistoryFilter && (
                  <div className="mt-2 p-2 bg-indigo-50 border border-indigo-200 rounded flex items-center justify-between">
                    <span className="text-xs text-indigo-700 font-semibold flex items-center gap-1">
                      <span>🔍</span>
                      <span>Filtered: Vehicles reviewed by {partnerHistoryFilter.reviewHistory?.partner_name || `Partner ${partnerHistoryFilter.person_id}`}</span>
                    </span>
                    <button
                      onClick={() => {
                        setPartnerHistoryFilter(null);
                        window.dispatchEvent(new CustomEvent(EventTypes.CLEAR_HISTORY_FILTERS));
                      }}
                      className="text-indigo-700 hover:text-indigo-900 font-bold text-sm"
                    >
                      ✕
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Two-Column Grid for Core Parameters - responsive */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
                <p className="text-xs text-gray-500 mt-1">Weekday (Mon-Fri)</p>
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
                <p className="text-xs text-gray-500 mt-1">Typical: 7 days</p>
              </div>
            </div>

            {/* Number of Vehicles (Partner Chain Mode) - Full Width */}
            {chainMode === 'partner' && (
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
            )}

            {/* Number of Partners (Vehicle Chain Mode) - Full Width */}
            {chainMode === 'vehicle' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Number of Partners
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
            )}

            {/* Tier Filter - Vehicle Chain Mode Only */}
            {chainMode === 'vehicle' && selectedVehicle && (
              <div className="border-t pt-4">
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-sm font-medium text-gray-700">
                    Partner Tier Filter
                  </label>
                  <button
                    onClick={() => {
                      const allTiers = ['A+', 'A', 'B', 'C'];
                      setSelectedTiers(selectedTiers.length === allTiers.length ? [] : allTiers);
                    }}
                    className="text-xs text-blue-600 hover:text-blue-800"
                  >
                    {selectedTiers.length === 4 ? 'Clear All' : 'Select All'}
                  </button>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {['A+', 'A', 'B', 'C'].map((tier) => (
                    <label
                      key={tier}
                      className={`flex items-center justify-center gap-2 px-3 py-2 rounded-md border cursor-pointer text-xs transition-colors ${
                        selectedTiers.includes(tier)
                          ? tier === 'A+'
                            ? 'bg-green-100 border-green-600 text-green-800'
                            : tier === 'A'
                            ? 'bg-green-100 border-green-300 text-green-800'
                            : tier === 'B'
                            ? 'bg-blue-100 border-blue-300 text-blue-800'
                            : 'bg-yellow-100 border-yellow-300 text-yellow-800'
                          : 'bg-white border-gray-300 text-gray-500 hover:bg-gray-50'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedTiers.includes(tier)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedTiers([...selectedTiers, tier]);
                          } else {
                            setSelectedTiers(selectedTiers.filter(t => t !== tier));
                          }
                        }}
                        className="rounded border-gray-300"
                      />
                      <span className="font-semibold">{tier}</span>
                    </label>
                  ))}
                </div>

                <p className="text-xs text-gray-500 mt-2">
                  {selectedTiers.length} of 4 tiers selected
                  {selectedTiers.length === 0 && <span className="text-red-600"> (at least 1 required)</span>}
                </p>
              </div>
            )}

            {/* Make Filter - Compact horizontal layout */}
            {chainMode === 'partner' && partnerIntelligence && partnerIntelligence.approved_makes && partnerIntelligence.approved_makes.length > 0 && (
              <div className="border-t pt-4">
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-sm font-medium text-gray-700">
                    Filter by Make ({selectedMakes.length}/{partnerIntelligence.approved_makes.length})
                  </label>
                  <button
                    onClick={() => {
                      const allMakes = partnerIntelligence.approved_makes.map(m => m.make);
                      setSelectedMakes(selectedMakes.length === allMakes.length ? [] : allMakes);
                    }}
                    className="text-xs text-blue-600 hover:text-blue-800"
                  >
                    {selectedMakes.length === partnerIntelligence.approved_makes.length ? 'Clear' : 'All'}
                  </button>
                </div>

                <div className="flex flex-wrap gap-2">
                  {partnerIntelligence.approved_makes
                    .sort((a, b) => a.make.localeCompare(b.make))
                    .map((item) => (
                      <label
                        key={item.make}
                        className={`inline-flex items-center gap-1 px-2 py-1 rounded-md border cursor-pointer text-xs transition-colors ${
                          selectedMakes.includes(item.make)
                            ? item.rank === 'A+' ? 'bg-green-100 border-green-600 text-green-800' :
                              item.rank === 'A' ? 'bg-green-100 border-green-300 text-green-800' :
                              item.rank === 'B' ? 'bg-blue-100 border-blue-300 text-blue-800' :
                              'bg-yellow-100 border-yellow-300 text-yellow-800'
                            : 'bg-white border-gray-300 text-gray-600 hover:bg-gray-50'
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={selectedMakes.includes(item.make)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedMakes([...selectedMakes, item.make]);
                            } else {
                              setSelectedMakes(selectedMakes.filter(m => m !== item.make));
                            }
                          }}
                          className="sr-only"
                        />
                        <span>{item.make}</span>
                        <span className={`font-medium ${
                          item.rank === 'A+' ? 'text-purple-600' :
                          item.rank === 'A' ? 'text-blue-600' :
                          item.rank === 'B' ? 'text-green-600' :
                          'text-gray-600'
                        }`}>
                          {item.rank}
                        </span>
                      </label>
                    ))}
                </div>
              </div>
            )}

            {/* Model Preferences - Partner Chain (NEW) */}
            {chainMode === 'partner' && selectedPartner && (
              <div className="border-t pt-4">
                <div className="mb-3">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    🎯 Vehicle Preferences (Optional)
                  </label>
                  <button
                    onClick={() => setShowModelSelectorModal(true)}
                    className="w-full py-2 px-4 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {modelPreferences.length > 0
                      ? `✓ ${modelPreferences.length} models selected - Click to edit`
                      : '+ Select specific models to prioritize or restrict'}
                  </button>

                  {/* Show selected models as tags */}
                  {modelPreferences.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {modelPreferences.slice(0, 5).map((pref, idx) => (
                        <span
                          key={idx}
                          className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-blue-100 text-blue-800"
                        >
                          {pref.make} {pref.model}
                        </span>
                      ))}
                      {modelPreferences.length > 5 && (
                        <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-gray-100 text-gray-600">
                          +{modelPreferences.length - 5} more
                        </span>
                      )}
                    </div>
                  )}
                </div>

                <div className="mt-3">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Preference Mode
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    <label className={`flex items-center gap-2 px-3 py-2 rounded-md border cursor-pointer text-xs ${
                      preferenceMode === 'prioritize'
                        ? 'bg-blue-50 border-blue-500 text-blue-700'
                        : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'
                    }`}>
                      <input
                        type="radio"
                        name="preferenceMode"
                        value="prioritize"
                        checked={preferenceMode === 'prioritize'}
                        onChange={(e) => setPreferenceMode(e.target.value)}
                        className="text-blue-600"
                      />
                      <div>
                        <div className="font-medium">Prioritize</div>
                        <div className="text-gray-500">Boost +800</div>
                      </div>
                    </label>

                    <label className={`flex items-center gap-2 px-3 py-2 rounded-md border cursor-pointer text-xs ${
                      preferenceMode === 'strict'
                        ? 'bg-blue-50 border-blue-500 text-blue-700'
                        : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'
                    }`}>
                      <input
                        type="radio"
                        name="preferenceMode"
                        value="strict"
                        checked={preferenceMode === 'strict'}
                        onChange={(e) => setPreferenceMode(e.target.value)}
                        className="text-blue-600"
                      />
                      <div>
                        <div className="font-medium">Strict</div>
                        <div className="text-gray-500">Only these</div>
                      </div>
                    </label>
                  </div>

                  <div className="mt-2 text-xs text-gray-500">
                    {preferenceMode === 'prioritize' && modelPreferences.length > 0 && (
                      <span>✓ Selected models will receive +800 score boost</span>
                    )}
                    {preferenceMode === 'strict' && modelPreferences.length > 0 && (
                      <span>⚠️ Chain will ONLY include selected models</span>
                    )}
                    {modelPreferences.length === 0 && (
                      <span>No models selected - preferences will not apply</span>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Mode Toggle - Partner Chain */}
            {chainMode === 'partner' && (
              <div className="border-t pt-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Build Mode
                </label>
                <div className="grid grid-cols-2 gap-2 mb-3">
                  <button
                    onClick={() => setBuildMode('auto')}
                    className={`py-2 px-3 rounded-md text-xs font-medium transition-colors border ${
                      buildMode === 'auto'
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    Auto-Generate
                  </button>
                  <button
                    onClick={() => setBuildMode('manual')}
                    className={`py-2 px-3 rounded-md text-xs font-medium transition-colors border ${
                      buildMode === 'manual'
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    Manual Build
                  </button>
                </div>
              </div>
            )}

            {/* Mode Toggle - Vehicle Chain */}
            {chainMode === 'vehicle' && (
              <div className="border-t pt-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Build Mode
                </label>
                <div className="grid grid-cols-2 gap-2 mb-3">
                  <button
                    onClick={() => setVehicleBuildMode('auto')}
                    className={`py-2 px-3 rounded-md text-xs font-medium transition-colors border ${
                      vehicleBuildMode === 'auto'
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    Auto-Generate
                  </button>
                  <button
                    onClick={() => setVehicleBuildMode('manual')}
                    className={`py-2 px-3 rounded-md text-xs font-medium transition-colors border ${
                      vehicleBuildMode === 'manual'
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    Manual Build
                  </button>
                </div>
              </div>
            )}

            {/* Generate Button - Partner Chain */}
            {chainMode === 'partner' && (
              <button
                onClick={buildMode === 'auto' ? generateChain : generateManualSlots}
                disabled={isLoading || !selectedPartner || !startDate}
                className={`w-full py-3 rounded-md text-sm font-medium transition-colors ${
                  isLoading || !selectedPartner || !startDate
                    ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                    : 'bg-blue-600 text-white hover:bg-blue-700'
                }`}
              >
                {isLoading
                  ? (buildMode === 'auto' ? 'Generating Chain...' : 'Creating Slots...')
                  : (buildMode === 'auto' ? 'Generate Chain' : 'Create Empty Slots')
                }
              </button>
            )}

            {/* Generate Button - Vehicle Chain */}
            {chainMode === 'vehicle' && (
              <button
                onClick={vehicleBuildMode === 'auto' ? generateVehicleChain : generateManualPartnerSlots}
                disabled={isLoading || !selectedVehicle || !startDate}
                className={`w-full py-3 rounded-md text-sm font-medium transition-colors ${
                  isLoading || !selectedVehicle || !startDate
                    ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                    : 'bg-blue-600 text-white hover:bg-blue-700'
                }`}
              >
                {isLoading
                  ? (vehicleBuildMode === 'auto' ? 'Generating Chain...' : 'Creating Slots...')
                  : (vehicleBuildMode === 'auto' ? 'Generate Chain' : 'Create Empty Slots')
                }
              </button>
            )}

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

          {/* Partner Chain Mode Preview */}
          {chainMode === 'partner' && selectedPartner && loadingIntelligence ? (
            <div className="bg-white rounded-lg shadow-sm border p-12">
              <div className="text-center">
                <svg className="animate-spin h-12 w-12 text-blue-600 mx-auto mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <p className="text-sm text-gray-600">Loading partner data...</p>
                <p className="text-xs text-gray-400 mt-1">Restoring your chain</p>
              </div>
            </div>
          ) : chainMode === 'partner' && selectedPartner && partnerIntelligence ? (
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
                  <div className="flex items-center gap-3">
                    <h3 className="text-md font-semibold text-gray-900">Chain Timeline</h3>
                    <a
                      href="#"
                      onClick={(e) => {
                        e.preventDefault();
                        window.dispatchEvent(new CustomEvent('navigateToCalendar', {
                          detail: { person_id: selectedPartner }
                        }));
                      }}
                      className="text-xs text-blue-600 hover:text-blue-800 hover:underline"
                      title="Open in Calendar view"
                    >
                      📅 View Full Calendar
                    </a>
                  </div>

                  <div className="flex items-center gap-3">
                    {/* Delete Manual Chain Button - show if partner has saved manual chains */}
                    {partnerIntelligence?.upcoming_assignments?.some(a => a.status === 'manual') && (
                      <button
                        onClick={deleteManualChain}
                        disabled={isSaving}
                        className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                          isSaving
                            ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                            : 'bg-green-700 text-white hover:bg-green-800'
                        }`}
                        title="Delete manual (green) chain assignments"
                      >
                        Delete Manual Chain
                      </button>
                    )}

                    {/* Delete Requested Chain Button - show if partner has saved requested chains */}
                    {partnerIntelligence?.upcoming_assignments?.some(a => a.status === 'requested') && (
                      <button
                        onClick={deleteRequestedChain}
                        disabled={isSaving}
                        className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                          isSaving
                            ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                            : 'bg-pink-700 text-white hover:bg-pink-800'
                        }`}
                        title="Delete requested (magenta) chain assignments sent to FMS"
                      >
                        Delete Requested Chain
                      </button>
                    )}

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
                        {/* Header Row - Day headers like Calendar (Month Day format) */}
                        <div className="flex border-b bg-gray-50">
                          <div className="w-48 flex-shrink-0 px-4 py-3 border-r font-medium text-sm text-gray-700">
                            {chain ? chain.partner_info.name : partnerIntelligence.partner.name}
                          </div>
                          <div className="flex-1 flex">
                            {days.map((date, idx) => {
                              const dayOfWeek = date.getDay();
                              const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
                              const monthDay = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

                              return (
                                <div
                                  key={idx}
                                  className={`flex-1 text-center text-xs py-2 border-r ${
                                    isWeekend ? 'bg-blue-100 text-blue-800 font-semibold' : 'text-gray-600'
                                  }`}
                                >
                                  <div className="leading-tight font-semibold">
                                    {monthDay}
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
                                  assignment_id: assignment.assignment_id,  // CRITICAL for interactive actions
                                  vin: assignment.vin,
                                  make: assignment.make,
                                  model: assignment.model,
                                  status: assignment.status,
                                  tier: assignment.tier,
                                  score: assignment.score,
                                  start: new Date(sYear, sMonth - 1, sDay),
                                  end: new Date(eYear, eMonth - 1, eDay),
                                  start_day: assignment.start_day,
                                  end_day: assignment.end_day,
                                  office: assignment.office
                                });
                              });

                              // Detect overlaps and assign row positions (match Calendar behavior)
                              const activitiesWithRows = existingActivities.map((activity, idx) => {
                                // Check if this activity overlaps with any previous activity
                                let rowIndex = 0;
                                const actStart = activity.start;
                                const actEnd = activity.end;

                                for (let i = 0; i < idx; i++) {
                                  const prevAct = existingActivities[i];
                                  const prevStart = prevAct.start;
                                  const prevEnd = prevAct.end;

                                  // Check if dates overlap
                                  if (actStart <= prevEnd && actEnd >= prevStart) {
                                    rowIndex = Math.max(rowIndex, (existingActivities[i].rowIndex || 0) + 1);
                                  }
                                }

                                activity.rowIndex = rowIndex;
                                return activity;
                              });

                              return activitiesWithRows.map((activity, idx) => {
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

                                // Use rowIndex for vertical positioning to prevent overlaps
                                const topOffset = 8 + (activity.rowIndex * 28);

                                return (
                                  <TimelineBar
                                    key={`existing-${idx}`}
                                    activity={activity}
                                    style={{
                                      left: `${left}%`,
                                      width: `${width}%`,
                                      minWidth: '60px',
                                      top: `${topOffset}px`,
                                      height: '20px',
                                      zIndex: 5
                                    }}
                                    onDelete={handleTimelineBarDelete}
                                    onRequest={handleTimelineBarRequest}
                                    onUnrequest={handleTimelineBarUnrequest}
                                    onClick={handleTimelineBarClick}
                                    interactive={true}
                                    showActions={true}
                                  />
                                );
                              });
                            })()}

                            {/* Unified Slots - works for both Auto and Manual modes */}
                            {manualSlots.map((slot, idx) => {
                              // Parse dates as local (avoid timezone shift)
                              const [sYear, sMonth, sDay] = slot.start_date.split('-').map(Number);
                              const [eYear, eMonth, eDay] = slot.end_date.split('-').map(Number);
                              const vStart = new Date(sYear, sMonth - 1, sDay);
                              const vEnd = new Date(eYear, eMonth - 1, eDay);

                              // Only show if slot overlaps with current view
                              const viewStart = new Date(viewStartDate);
                              const viewEnd = new Date(viewEndDate);

                              if (vEnd < viewStart || vStart > viewEnd) {
                                return null;
                              }

                              // Calculate bar position
                              const rangeStart = new Date(viewStartDate);
                              const rangeEnd = new Date(viewEndDate);

                              const startDate = vStart < rangeStart ? rangeStart : vStart;
                              const endDate = vEnd > rangeEnd ? rangeEnd : vEnd;

                              const totalDays = days.length;
                              const startDayOffset = Math.floor((startDate - rangeStart) / (1000 * 60 * 60 * 24));
                              const endDayOffset = Math.floor((endDate - rangeStart) / (1000 * 60 * 60 * 24));

                              const left = ((startDayOffset + 0.5) / totalDays) * 100;
                              const width = ((endDayOffset - startDayOffset) / totalDays) * 100;

                              // Stair-step pattern
                              const positionInGroup = idx % 3;
                              const top = 40 + (positionInGroup * 28);

                              // Color: Gray for empty, Green for filled
                              const barColor = slot.selected_vehicle
                                ? 'bg-gradient-to-br from-green-400 to-green-500 border-green-600'
                                : 'bg-gradient-to-br from-gray-300 to-gray-400 border-gray-500';

                              const label = slot.selected_vehicle
                                ? `${slot.selected_vehicle.make} ${slot.selected_vehicle.model}`
                                : `Slot ${slot.slot} - Select Vehicle`;

                              return (
                                <div
                                  key={slot.slot}
                                  className={`absolute ${barColor} border-2 rounded-lg shadow-lg hover:shadow-xl transition-all px-2 flex items-center text-white text-xs font-semibold overflow-hidden`}
                                  style={{
                                    left: `${left}%`,
                                    width: `${width}%`,
                                    minWidth: '80px',
                                    top: `${top}px`,
                                    height: '24px'
                                  }}
                                  title={slot.selected_vehicle
                                    ? `Slot ${slot.slot}: ${slot.selected_vehicle.make} ${slot.selected_vehicle.model}${slot.selected_vehicle.color ? ` (${slot.selected_vehicle.color})` : ''}\n${slot.start_date} - ${slot.end_date}\nScore: ${slot.selected_vehicle.score}`
                                    : `Slot ${slot.slot}: Empty\n${slot.start_date} - ${slot.end_date}\nClick dropdown below to select vehicle`
                                  }
                                >
                                  <span className="truncate text-[11px]">
                                    {label}
                                  </span>
                                </div>
                              );
                            })}

                            {/* OLD Auto chain timeline - now using unified slots above */}
                            {false && buildMode === 'auto' && chain && chain.chain.map((vehicle, idx) => {
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
                  {buildMode === 'manual' ? (
                    <>
                      <span className="inline-block w-3 h-3 bg-gray-400 border-2 border-gray-500 rounded"></span>
                      <span>Gray = Empty slots (select vehicle)</span>
                      <span className="inline-block w-3 h-3 bg-green-400 border-2 border-green-600 rounded ml-3"></span>
                      <span>Green = Vehicle selected</span>
                    </>
                  ) : (
                    <>
                      <span className="inline-block w-3 h-3 bg-green-400 border-2 border-green-600 rounded"></span>
                      <span>Green bars = Proposed chain recommendations</span>
                    </>
                  )}
                  <span className="ml-4">Use arrows to navigate months</span>
                </div>
              </div>

              {/* Vehicle Cards with Dropdowns - Works for BOTH Auto and Manual modes */}
              {manualSlots.length > 0 && (
                <div className="bg-white rounded-lg shadow-sm border p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-md font-semibold text-gray-900">
                      {buildMode === 'manual' ? 'Select Vehicles for Each Slot' : 'Chain Vehicles (Editable)'}
                    </h3>

                    {/* Save Chain Buttons */}
                    <div className="flex gap-2">
                      <button
                        onClick={() => saveManualChain('manual')}
                        disabled={isSaving || manualSlots.some(s => !s.selected_vehicle)}
                        className={`px-6 py-2 rounded-md text-sm font-medium transition-colors ${
                          isSaving || manualSlots.some(s => !s.selected_vehicle)
                            ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                            : 'bg-green-600 text-white hover:bg-green-700'
                        }`}
                        title={manualSlots.some(s => !s.selected_vehicle) ? 'Select vehicles for all slots first' : 'Save as recommendations (green)'}
                      >
                        {isSaving ? 'Saving...' : 'Save Chain'}
                      </button>
                      <button
                        onClick={() => saveManualChain('requested')}
                        disabled={isSaving || manualSlots.some(s => !s.selected_vehicle)}
                        className={`px-6 py-2 rounded-md text-sm font-medium transition-colors ${
                          isSaving || manualSlots.some(s => !s.selected_vehicle)
                            ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                            : 'bg-pink-600 text-white hover:bg-pink-700'
                        }`}
                        title={manualSlots.some(s => !s.selected_vehicle) ? 'Select vehicles for all slots first' : 'Save and send to FMS (magenta)'}
                      >
                        {isSaving ? 'Saving...' : 'Save as Requested'}
                      </button>
                    </div>
                  </div>

                  {/* Save Message */}
                  {saveMessage && (
                    <div className={`mb-4 p-3 rounded-md text-sm ${
                      saveMessage.includes('✅')
                        ? 'bg-green-50 border border-green-200 text-green-800'
                        : 'bg-red-50 border border-red-200 text-red-700'
                    }`}>
                      {saveMessage}
                    </div>
                  )}

                  {/* Manual Slot Cards */}
                  <div className="grid grid-cols-4 gap-4">
                    {manualSlots.map((slot, index) => (
                      <div
                        key={slot.slot}
                        className={`border-2 rounded-lg p-3 hover:shadow-lg transition-all relative ${
                          slot.selected_vehicle
                            ? 'border-green-500 bg-green-50 shadow-md'
                            : 'border-gray-300 bg-white'
                        }`}
                      >
                        {/* Delete button - top right corner */}
                        <button
                          onClick={() => {
                            if (window.confirm(`Remove Slot ${slot.slot} from chain?`)) {
                              setManualSlots(prev => prev.filter((_, i) => i !== index));
                            }
                          }}
                          className="absolute -top-2 -right-2 w-6 h-6 bg-red-600 text-white rounded-full hover:bg-red-700 flex items-center justify-center text-sm font-bold shadow-lg z-10"
                          title="Delete this slot"
                        >
                          ×
                        </button>

                        {/* Header: Slot + Dates + Available Count */}
                        <div className="flex items-center justify-between mb-2 pb-2 border-b border-gray-200">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-bold text-gray-700">Slot {slot.slot}</span>
                            <span className="text-xs text-gray-600">
                              {new Date(slot.start_date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} - {new Date(slot.end_date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                            </span>
                          </div>
                          {/* Show actual dropdown count if loaded, otherwise show estimated count */}
                          {loadingSlotOptions[index] ? (
                            <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                              ...
                            </span>
                          ) : slot.eligible_vehicles.length > 0 ? (
                            <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
                              {slot.eligible_vehicles.length}
                            </span>
                          ) : slot.available_count > 0 ? (
                            <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                              ~{slot.available_count}
                            </span>
                          ) : null}
                        </div>

                        {/* Vehicle Selection Dropdown */}
                        {!slot.selected_vehicle ? (
                          <div>
                            <div className="flex items-center justify-between mb-1">
                              <label className="block text-xs font-medium text-gray-700">
                                Select Vehicle:
                              </label>
                              {slot.eligible_vehicles.length > 0 && (
                                <button
                                  onClick={() => loadSlotOptions(index)}
                                  disabled={loadingSlotOptions[index]}
                                  className="text-xs text-blue-600 hover:text-blue-800 underline"
                                >
                                  {loadingSlotOptions[index] ? 'Loading...' : 'Reload'}
                                </button>
                              )}
                            </div>

                            {loadingSlotOptions[index] ? (
                              <div className="w-full border border-gray-300 rounded px-3 py-2 text-xs text-gray-500 bg-gray-50">
                                Loading options...
                              </div>
                            ) : slot.eligible_vehicles.length === 0 ? (
                              <button
                                onClick={() => loadSlotOptions(index)}
                                className="w-full border border-gray-300 rounded px-3 py-2 text-xs text-blue-600 hover:bg-blue-50 bg-white"
                              >
                                Click to load options...
                              </button>
                            ) : (
                              <div className="relative">
                                <div className="border border-gray-300 rounded-md bg-white shadow-sm">
                                  <div className="p-2 border-b sticky top-0 bg-white">
                                    <input
                                      type="text"
                                      placeholder="Search by make, model, or VIN..."
                                      value={slotVehicleSearchQueries[index] || ''}
                                      onChange={(e) => setSlotVehicleSearchQueries({
                                        ...slotVehicleSearchQueries,
                                        [index]: e.target.value
                                      })}
                                      className="w-full px-2 py-1.5 text-xs border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                  </div>
                                  <div className="max-h-48 overflow-y-auto">
                                    {slot.eligible_vehicles
                                      .filter(vehicle => {
                                        const searchQuery = slotVehicleSearchQueries[index] || '';
                                        if (searchQuery === '') return true;
                                        const searchLower = searchQuery.toLowerCase();
                                        return (
                                          vehicle.make.toLowerCase().includes(searchLower) ||
                                          vehicle.model.toLowerCase().includes(searchLower) ||
                                          vehicle.vin.toLowerCase().includes(searchLower)
                                        );
                                      })
                                      .sort((a, b) => {
                                        // Sort by Make alphabetically, then by Score descending
                                        if (a.make !== b.make) {
                                          return a.make.localeCompare(b.make);
                                        }
                                        return b.score - a.score;
                                      })
                                      .map(vehicle => (
                                      <button
                                        key={vehicle.vin}
                                        onClick={() => selectVehicleForSlot(index, vehicle)}
                                        className="w-full text-left px-3 py-2 text-xs hover:bg-blue-50 hover:text-blue-900 transition-colors border-b last:border-b-0 flex items-center justify-between"
                                      >
                                        <div>
                                          <div className="font-medium">
                                            {vehicle.make} {vehicle.model}
                                            <span className={`ml-1.5 px-1.5 py-0.5 rounded text-xs font-semibold ${
                                              vehicle.tier === 'A+' ? 'bg-green-100 text-green-800' :
                                              vehicle.tier === 'A' ? 'bg-green-100 text-green-700' :
                                              vehicle.tier === 'B' ? 'bg-blue-100 text-blue-800' :
                                              'bg-yellow-100 text-yellow-800'
                                            }`}>
                                              {vehicle.tier}
                                            </span>
                                          </div>
                                          <div className="text-gray-500 mt-0.5">
                                            Score: {vehicle.score} • VIN: ...{vehicle.last_4_vin}{vehicle.color ? ` • ${vehicle.color}` : ''}
                                          </div>
                                        </div>
                                      </button>
                                    ))}
                                    {slot.eligible_vehicles.filter(vehicle => {
                                      const searchQuery = slotVehicleSearchQueries[index] || '';
                                      if (searchQuery === '') return true;
                                      const searchLower = searchQuery.toLowerCase();
                                      return (
                                        vehicle.make.toLowerCase().includes(searchLower) ||
                                        vehicle.model.toLowerCase().includes(searchLower) ||
                                        vehicle.vin.toLowerCase().includes(searchLower)
                                      );
                                    }).length === 0 && (
                                      <div className="px-3 py-4 text-xs text-gray-500 text-center">
                                        No vehicles match your search
                                      </div>
                                    )}
                                  </div>
                                </div>
                              </div>
                            )}

                            {slot.available_count === 0 && (
                              <p className="text-xs text-red-600 mt-1">No vehicles available</p>
                            )}
                          </div>
                        ) : (
                          /* Show selected vehicle - Condensed layout */
                          <div className="space-y-1">
                            {/* Line 1: Tier badge + Make Model Year */}
                            <div className="flex items-start gap-2">
                              <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-bold flex-shrink-0 ${
                                slot.selected_vehicle.tier === 'A+' ? 'bg-purple-100 text-purple-800 border border-purple-300' :
                                slot.selected_vehicle.tier === 'A' ? 'bg-blue-100 text-blue-800 border border-blue-300' :
                                slot.selected_vehicle.tier === 'B' ? 'bg-green-100 text-green-800 border border-green-300' :
                                'bg-gray-100 text-gray-800 border border-gray-300'
                              }`}>
                                {slot.selected_vehicle.tier}
                              </span>
                              <span className="font-semibold text-gray-900 text-sm leading-tight">
                                {slot.selected_vehicle.make} {slot.selected_vehicle.model} {slot.selected_vehicle.year}
                              </span>
                            </div>

                            {/* Line 2: Color | VIN */}
                            <div className="text-xs text-gray-600 pl-7">
                              {slot.selected_vehicle.color && <span>{slot.selected_vehicle.color} | </span>}
                              VIN: <a
                                href={`https://fms.driveshop.com/vehicles/list_activities/${slot.selected_vehicle.vehicle_id || slot.selected_vehicle.vin}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="font-mono text-blue-600 hover:text-blue-800 hover:underline"
                                title="Open in FMS"
                              >
                                ...{slot.selected_vehicle.vin ? slot.selected_vehicle.vin.slice(-8) : slot.selected_vehicle.last_4_vin}
                              </a>
                            </div>

                            {/* Change button */}
                            <div className="text-right">
                              <button
                                onClick={() => {
                                  selectVehicleForSlot(index, null);
                                  loadSlotOptions(index);
                                }}
                                className="text-xs text-red-600 hover:text-red-800 underline"
                              >
                                Change
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* OLD Auto-Generate Cards - Now using unified Manual mode cards above */}
              {false && buildMode === 'auto' && chain && (
                <div className="bg-white rounded-lg shadow-sm border p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-md font-semibold text-gray-900">Chain Vehicles</h3>

                    {/* Action Buttons */}
                    <div className="flex gap-2">
                      {/* Delete Entire Chain Button - only show if partner has saved manual assignments */}
                      {partnerIntelligence?.upcoming_assignments?.some(a => a.status === 'manual') && (
                        <button
                          onClick={deleteEntireChain}
                          disabled={isSaving}
                          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                            isSaving
                              ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                              : 'bg-red-600 text-white hover:bg-red-700'
                          }`}
                        >
                          Delete Chain
                        </button>
                      )}

                      {/* Save Chain Button */}
                      <button
                        onClick={saveChain}
                        disabled={isSaving}
                        className={`px-6 py-2 rounded-md text-sm font-medium transition-colors ${
                          isSaving
                            ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                            : 'bg-green-600 text-white hover:bg-green-700'
                        }`}
                      >
                        {isSaving ? 'Saving...' : 'Save Chain'}
                      </button>
                    </div>
                  </div>

                  {/* Save Message */}
                  {saveMessage && (
                    <div className={`mb-4 p-3 rounded-md text-sm ${
                      saveMessage.includes('✅')
                        ? 'bg-green-50 border border-green-200 text-green-800'
                        : 'bg-red-50 border border-red-200 text-red-700'
                    }`}>
                      {saveMessage}
                    </div>
                  )}

                  {/* Card grid - max 5 per row, then wrap */}
                  <div className="grid grid-cols-5 gap-4">
                    {chain.chain.map((vehicle) => {
                      // Find if this vehicle is saved (has assignment_id)
                      const savedAssignment = partnerIntelligence?.upcoming_assignments?.find(a =>
                        a.vin === vehicle.vin &&
                        a.start_day === vehicle.start_date &&
                        a.status === 'manual'
                      );

                      return (<div
                        key={vehicle.slot}
                        onClick={() => openVehicleContext(vehicle.vin)}
                        className="border-2 border-gray-200 rounded-lg p-4 hover:shadow-lg transition-all hover:border-blue-400 cursor-pointer relative"
                      >
                        {/* Delete button - only show if saved */}
                        {savedAssignment && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              deleteVehicleFromChain(savedAssignment.assignment_id);
                            }}
                            className="absolute -top-2 -right-2 w-6 h-6 bg-red-600 text-white rounded-full hover:bg-red-700 flex items-center justify-center text-sm font-bold shadow-lg z-10"
                            title="Delete this saved vehicle"
                          >
                            ×
                          </button>
                        )}

                        {/* Swap icon - show for generated (not saved) vehicles */}
                        {!savedAssignment && (
                          <div className="absolute -top-2 -right-2 w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center text-xs font-bold shadow-lg pointer-events-none">
                            ⇄
                          </div>
                        )}

                        {/* Header: Slot + Tier */}
                        <div className="flex items-center justify-between mb-3">
                          <span className="text-sm font-bold text-gray-700">Slot {vehicle.slot}</span>
                          <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-bold ${
                            vehicle.tier === 'A+' ? 'bg-purple-100 text-purple-800 border border-purple-300' :
                            vehicle.tier === 'A' ? 'bg-blue-100 text-blue-800 border border-blue-300' :
                            vehicle.tier === 'B' ? 'bg-green-100 text-green-800 border border-green-300' :
                            'bg-gray-100 text-gray-800 border border-gray-300'
                          }`}>
                            {vehicle.tier}
                          </span>
                        </div>

                        {/* Vehicle Info */}
                        <div className="space-y-2">
                          <div>
                            <h4 className="font-semibold text-gray-900 text-sm leading-tight">
                              {vehicle.make}
                            </h4>
                            <p className="text-xs text-gray-600 leading-tight">
                              {vehicle.model}
                            </p>
                            <p className="text-xs text-gray-400">{vehicle.year}</p>
                          </div>

                          {/* Dates */}
                          <div className="pt-2 border-t border-gray-200">
                            <p className="text-xs text-gray-500 font-medium">Dates</p>
                            <p className="text-xs text-gray-900">
                              {new Date(vehicle.start_date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} - {new Date(vehicle.end_date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                            </p>
                          </div>

                          {/* VIN */}
                          <div className="pt-2 border-t border-gray-200">
                            <p className="text-xs text-gray-500 font-medium">VIN</p>
                            <p className="text-xs font-mono text-gray-700 truncate">
                              ...{vehicle.vin.slice(-8)}
                            </p>
                          </div>

                          {/* Score */}
                          <div className="pt-2 border-t border-gray-200">
                            <p className="text-xs text-gray-500 font-medium">Score</p>
                            <p className="text-sm font-bold text-blue-600">{vehicle.score}</p>
                          </div>
                        </div>
                      </div>);
                    })}
                  </div>
                </div>
              )}
            </div>
          ) : chainMode === 'partner' ? (
            <div className="bg-white rounded-lg shadow-sm border p-12">
              <div className="text-center">
                <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                <p className="mt-2 text-sm text-gray-500">No chain generated yet</p>
                <p className="text-xs text-gray-400 mt-1">Select a partner and click "Generate Chain" to see suggestions</p>
              </div>
            </div>
          ) : null}

          {/* Vehicle Chain Mode - Timeline Calendar (EXACT copy of partner timeline but with partner names on bars) */}
          {chainMode === 'vehicle' && selectedVehicle && (
            <div className="bg-white rounded-lg shadow-sm border p-6">
              <div className="mb-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <h3 className="text-md font-semibold text-gray-900">Vehicle Calendar Timeline</h3>
                    <a
                      href="#"
                      onClick={(e) => {
                        e.preventDefault();
                        window.dispatchEvent(new CustomEvent('navigateToCalendar', {
                          detail: { vin: selectedVehicle.vin }
                        }));
                      }}
                      className="text-xs text-blue-600 hover:text-blue-800 hover:underline"
                      title="Open in Calendar view"
                    >
                      📅 View Full Calendar
                    </a>
                  </div>

                  <div className="flex items-center gap-3">
                    {/* Delete Manual Chain Button - show if vehicle has saved manual chains */}
                    {vehicleIntelligence?.busy_periods?.some(a => a.status === 'manual') && (
                      <button
                        onClick={deleteManualVehicleChain}
                        disabled={isSaving}
                        className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                          isSaving
                            ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                            : 'bg-green-700 text-white hover:bg-green-800'
                        }`}
                        title="Delete manual (green) chain assignments"
                      >
                        Delete Manual Chain
                      </button>
                    )}

                    {/* Delete Requested Chain Button - show if vehicle has saved requested chains */}
                    {vehicleIntelligence?.busy_periods?.some(a => a.status === 'requested') && (
                      <button
                        onClick={deleteRequestedVehicleChain}
                        disabled={isSaving}
                        className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                          isSaving
                            ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                            : 'bg-pink-700 text-white hover:bg-pink-800'
                        }`}
                        title="Delete requested (magenta) chain assignments sent to FMS"
                      >
                        Delete Requested Chain
                      </button>
                    )}

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
                      {/* Header Row - Day headers */}
                      <div className="flex border-b bg-gray-50">
                        <div className="w-48 flex-shrink-0 px-4 py-3 border-r font-medium text-sm text-gray-700">
                          <div>{selectedVehicle.make} {selectedVehicle.model}</div>
                          {selectedVehicle.color && (
                            <div className="text-xs text-gray-500 font-normal">{selectedVehicle.color}</div>
                          )}
                        </div>
                        <div className="flex-1 flex">
                          {days.map((date, idx) => {
                            const dayOfWeek = date.getDay();
                            const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
                            const monthDay = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

                            return (
                              <div
                                key={idx}
                                className={`flex-1 text-center text-xs py-2 border-r ${
                                  isWeekend ? 'bg-blue-100 text-blue-800 font-semibold' : 'text-gray-600'
                                }`}
                              >
                                <div className="leading-tight font-semibold">
                                  {monthDay}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>

                      {/* Timeline Row with bars */}
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

                          {/* Existing activities (busy periods) - BLUE for active, GREEN/MAGENTA for scheduled */}
                          {vehicleIntelligence && vehicleIntelligence.busy_periods && (() => {
                            return vehicleIntelligence.busy_periods.map((period, idx) => {
                              const [sYear, sMonth, sDay] = period.start_date.split('-').map(Number);
                              const [eYear, eMonth, eDay] = period.end_date.split('-').map(Number);
                              const pStart = new Date(sYear, sMonth - 1, sDay);
                              const pEnd = new Date(eYear, eMonth - 1, eDay);

                              // Only show if overlaps with current view
                              const viewStart = new Date(viewStartDate);
                              const viewEnd = new Date(viewEndDate);

                              if (pEnd < viewStart || pStart > viewEnd) {
                                return null;
                              }

                              // Calculate bar position
                              const rangeStart = new Date(viewStartDate);
                              const startDate = pStart < rangeStart ? rangeStart : pStart;
                              const endDate = pEnd > viewEnd ? viewEnd : pEnd;

                              const totalDays = days.length;
                              const startDayOffset = Math.floor((startDate - rangeStart) / (1000 * 60 * 60 * 24));
                              const endDayOffset = Math.floor((endDate - rangeStart) / (1000 * 60 * 60 * 24));

                              const left = ((startDayOffset + 0.5) / totalDays) * 100;
                              const width = ((endDayOffset - startDayOffset) / totalDays) * 100;

                              // Create activity object for TimelineBar
                              const activity = {
                                ...period,
                                type: period.status === 'active' ? 'active' : 'scheduled',
                                start: pStart,
                                end: pEnd,
                                start_day: period.start_date,
                                end_day: period.end_date
                              };

                              return (
                                <TimelineBar
                                  key={`busy-${idx}`}
                                  activity={activity}
                                  style={{
                                    left: `${left}%`,
                                    width: `${width}%`,
                                    minWidth: '60px',
                                    top: '8px',
                                    height: '20px',
                                    zIndex: 5
                                  }}
                                  onDelete={handleTimelineBarDelete}
                                  onRequest={handleTimelineBarRequest}
                                  onUnrequest={handleTimelineBarUnrequest}
                                  onClick={handleTimelineBarClick}
                                  interactive={true}
                                  showActions={true}
                                />
                              );
                            });
                          })()}

                          {/* Proposed chain slots (gray bars) */}
                          {manualPartnerSlots.map((slot, idx) => {
                            if (!slot.start_date || !slot.end_date) return null;

                            const [sYear, sMonth, sDay] = slot.start_date.split('-').map(Number);
                            const [eYear, eMonth, eDay] = slot.end_date.split('-').map(Number);
                            const pStart = new Date(sYear, sMonth - 1, sDay);
                            const pEnd = new Date(eYear, eMonth - 1, eDay);

                            // Only show if slot overlaps with current view
                            const viewStart = new Date(viewStartDate);
                            const viewEnd = new Date(viewEndDate);

                            if (pEnd < viewStart || pStart > viewEnd) {
                              return null;
                            }

                            // Calculate bar position
                            const rangeStart = new Date(viewStartDate);
                            const startDate = pStart < rangeStart ? rangeStart : pStart;
                            const endDate = pEnd > viewEnd ? viewEnd : pEnd;

                            const totalDays = days.length;
                            const startDayOffset = Math.floor((startDate - rangeStart) / (1000 * 60 * 60 * 24));
                            const endDayOffset = Math.floor((endDate - rangeStart) / (1000 * 60 * 60 * 24));

                            const left = ((startDayOffset + 0.5) / totalDays) * 100;
                            const width = ((endDayOffset - startDayOffset) / totalDays) * 100;

                            // Stair-step pattern
                            const positionInGroup = idx % 3;
                            const top = 40 + (positionInGroup * 28);

                            // Color: Gray for empty, Green for filled
                            const barColor = slot.selected_partner
                              ? 'bg-gradient-to-br from-green-400 to-green-500 border-green-600'
                              : 'bg-gradient-to-br from-gray-300 to-gray-400 border-gray-500';

                            const label = slot.selected_partner
                              ? slot.selected_partner.name
                              : `Slot ${slot.slot} - Select Partner`;

                            return (
                              <div
                                key={slot.slot}
                                className={`absolute ${barColor} border-2 rounded-lg shadow-lg hover:shadow-xl transition-all px-2 flex items-center text-white text-xs font-semibold overflow-hidden`}
                                style={{
                                  left: `${left}%`,
                                  width: `${width}%`,
                                  minWidth: '80px',
                                  top: `${top}px`,
                                  height: '24px'
                                }}
                                title={slot.selected_partner
                                  ? `Slot ${slot.slot}: ${slot.selected_partner.name}\n${slot.start_date} - ${slot.end_date}\nScore: ${slot.selected_partner.final_score}`
                                  : `Slot ${slot.slot}: Empty\n${slot.start_date} - ${slot.end_date}\nClick dropdown below to select partner`
                                }
                              >
                                <span className="truncate text-[11px]">
                                  {label}
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
                {vehicleBuildMode === 'manual' ? (
                  <>
                    <span className="inline-block w-3 h-3 bg-gray-400 border-2 border-gray-500 rounded"></span>
                    <span>Gray = Empty slots (select partner)</span>
                    <span className="inline-block w-3 h-3 bg-green-400 border-2 border-green-600 rounded ml-3"></span>
                    <span>Green = Partner selected</span>
                  </>
                ) : (
                  <>
                    <span className="inline-block w-3 h-3 bg-green-400 border-2 border-green-600 rounded"></span>
                    <span>Green bars = Proposed chain recommendations</span>
                  </>
                )}
                <span className="ml-4">Use arrows to navigate months</span>
              </div>
            </div>
          )}

          {/* Loading Indicator - Vehicle Chain Mode */}
          {chainMode === 'vehicle' && isLoading && (
            <div className="bg-white rounded-lg shadow-sm border p-12">
              <div className="text-center">
                <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
                <p className="text-sm text-gray-700 font-medium">
                  {vehicleBuildMode === 'auto' ? 'Generating optimal partner chain...' : 'Creating partner slots...'}
                </p>
                <p className="text-xs text-gray-500 mt-2">
                  {vehicleBuildMode === 'auto' ? 'Using OR-Tools to optimize distances and partner quality' : 'Calculating slot dates with weekend extensions'}
                </p>
              </div>
            </div>
          )}

          {/* Vehicle Chain Mode - Manual Partner Slot Cards */}
          {chainMode === 'vehicle' && manualPartnerSlots.length > 0 && (
            <div className="bg-white rounded-lg shadow-sm border p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-md font-semibold text-gray-900">
                    {vehicleBuildMode === 'manual' ? 'Select Partners for Each Slot' : 'Chain Partners (Editable)'}
                  </h3>
                  {selectedVehicle && (
                    <p className="text-xs text-gray-600 mt-1">
                      Vehicle: {selectedVehicle.make} {selectedVehicle.model} {selectedVehicle.year}{selectedVehicle.color ? ` - ${selectedVehicle.color}` : ''} (VIN: ...{selectedVehicle.vin.slice(-4)})
                    </p>
                  )}
                </div>

                {/* Save Chain Buttons */}
                <div className="flex gap-2">
                  <button
                    onClick={() => saveVehicleChain('manual')}
                    disabled={isSaving || !manualPartnerSlots.every(s => s.selected_partner)}
                    className={`px-6 py-2 rounded-md text-sm font-medium transition-colors ${
                      isSaving || !manualPartnerSlots.every(s => s.selected_partner)
                        ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                        : 'bg-green-600 text-white hover:bg-green-700'
                    }`}
                    title={!manualPartnerSlots.every(s => s.selected_partner) ? 'Select partners for all slots first' : 'Save as recommendations (green bars in calendar)'}
                  >
                    {isSaving ? 'Saving...' : 'Save Chain'}
                  </button>
                  <button
                    onClick={() => saveVehicleChain('requested')}
                    disabled={isSaving || !manualPartnerSlots.every(s => s.selected_partner)}
                    className={`px-6 py-2 rounded-md text-sm font-medium transition-colors ${
                      isSaving || !manualPartnerSlots.every(s => s.selected_partner)
                        ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                        : 'bg-pink-600 text-white hover:bg-pink-700'
                    }`}
                    title={!manualPartnerSlots.every(s => s.selected_partner) ? 'Select partners for all slots first' : 'Save and send to FMS (magenta bars in calendar)'}
                  >
                    {isSaving ? 'Saving...' : 'Save as Requested'}
                  </button>
                </div>
              </div>

              {/* Save Message */}
              {saveMessage && (
                <div className={`mb-4 p-3 rounded-md text-sm ${
                  saveMessage.includes('✅')
                    ? 'bg-green-50 border border-green-200 text-green-800'
                    : 'bg-red-50 border border-red-200 text-red-700'
                }`}>
                  {saveMessage}
                </div>
              )}

              {/* Manual Partner Slot Cards */}
              <div className="grid grid-cols-5 gap-4">
                {manualPartnerSlots.map((slot, index) => (
                  <div
                    key={slot.slot}
                    className={`border-2 rounded-lg p-4 hover:shadow-lg transition-all relative ${
                      slot.selected_partner
                        ? 'border-green-500 bg-green-50 shadow-md'
                        : 'border-gray-300 bg-white'
                    }`}
                  >
                    {/* Delete button - top right corner */}
                    <button
                      onClick={() => {
                        if (window.confirm(`Remove Slot ${slot.slot} from chain?`)) {
                          setManualPartnerSlots(prev => prev.filter((_, i) => i !== index));
                        }
                      }}
                      className="absolute -top-2 -right-2 w-6 h-6 bg-red-600 text-white rounded-full hover:bg-red-700 flex items-center justify-center text-sm font-bold shadow-lg z-10"
                      title="Delete this slot"
                    >
                      ×
                    </button>

                    {/* Header: Slot + Available Count */}
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-sm font-bold text-gray-700">Slot {slot.slot}</span>
                      {/* Show actual dropdown count if loaded, otherwise show estimated count */}
                      {loadingPartnerSlotOptions[index] ? (
                        <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                          Loading...
                        </span>
                      ) : slot.eligible_partners && slot.eligible_partners.length > 0 ? (
                        <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
                          {slot.eligible_partners.length} avail
                        </span>
                      ) : null}
                    </div>

                    {/* Dates */}
                    <div className="mb-3 pb-3 border-b border-gray-200">
                      <p className="text-xs text-gray-500 font-medium">Dates</p>
                      <p className="text-xs text-gray-900">
                        {new Date(slot.start_date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} - {new Date(slot.end_date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                      </p>
                    </div>

                    {/* Partner Selection Dropdown */}
                    {!slot.selected_partner ? (
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <label className="block text-xs font-medium text-gray-700">
                            Select Partner:
                          </label>
                          {slot.eligible_partners && slot.eligible_partners.length > 0 && (
                            <button
                              onClick={() => loadPartnerSlotOptions(index)}
                              disabled={loadingPartnerSlotOptions[index]}
                              className="text-xs text-blue-600 hover:text-blue-800 underline"
                            >
                              {loadingPartnerSlotOptions[index] ? 'Loading...' : 'Reload'}
                            </button>
                          )}
                        </div>
                        <select
                          className="w-full border border-gray-300 rounded px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500 max-h-48 overflow-y-auto"
                          size="1"
                          onChange={(e) => {
                            if (e.target.value) {
                              const partner = slot.eligible_partners.find(p => p.person_id.toString() === e.target.value);
                              if (partner) {
                                selectPartnerForSlot(index, partner);
                              }
                            }
                          }}
                          onFocus={() => {
                            // Load options when dropdown is focused (lazy loading)
                            if (!slot.eligible_partners || slot.eligible_partners.length === 0) {
                              loadPartnerSlotOptions(index);
                            }
                          }}
                          value=""
                          disabled={index > 0 && !manualPartnerSlots[index - 1]?.selected_partner}
                        >
                          <option value="">
                            {index > 0 && !manualPartnerSlots[index - 1]?.selected_partner
                              ? 'Select previous slot first...'
                              : loadingPartnerSlotOptions[index]
                                ? 'Loading options...'
                                : !slot.eligible_partners || slot.eligible_partners.length === 0
                                  ? 'Click to load options...'
                                  : 'Choose partner...'}
                          </option>
                          {slot.eligible_partners && slot.eligible_partners.map(partner => {
                            // Format: "Partner Name ⭐ 159 (3.2 mi from office) [A]" for slot 0
                            //         "Partner Name ⭐ 159 (3.2 mi) [A]" for slot 1+
                            //         "Partner Name ⚠️ Location Unknown [B]" if no coords
                            let distanceText = '';
                            if (partner.distance_from_previous !== null && partner.distance_from_previous !== undefined) {
                              const distLabel = index === 0 ? ' from office' : '';
                              distanceText = ` (${partner.distance_from_previous.toFixed(1)} mi${distLabel})`;
                            } else {
                              distanceText = ' ⚠️ Location Unknown';
                            }

                            const label = `${partner.name} ⭐ ${partner.final_score}${distanceText} [${partner.tier || 'N/A'}]`;

                            return (
                              <option key={partner.person_id} value={partner.person_id}>
                                {label}
                              </option>
                            );
                          })}
                        </select>
                        {(!slot.eligible_partners || slot.eligible_partners.length === 0) && !loadingPartnerSlotOptions[index] && (
                          <p className="text-xs text-red-600 mt-1">No partners available</p>
                        )}
                      </div>
                    ) : (
                      /* Show selected partner */
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-bold ${
                            slot.selected_partner.tier === 'A+' ? 'bg-purple-100 text-purple-800 border border-purple-300' :
                            slot.selected_partner.tier === 'A' ? 'bg-blue-100 text-blue-800 border border-blue-300' :
                            slot.selected_partner.tier === 'B' ? 'bg-green-100 text-green-800 border border-green-300' :
                            'bg-gray-100 text-gray-800 border border-gray-300'
                          }`}>
                            {slot.selected_partner.tier || 'N/A'}
                          </span>
                          <button
                            onClick={() => selectPartnerForSlot(index, null)}
                            className="text-xs text-red-600 hover:text-red-800 underline"
                          >
                            Change
                          </button>
                        </div>

                        <div>
                          <h4 className="font-semibold text-gray-900 text-sm leading-tight">
                            {slot.selected_partner.name}
                          </h4>
                          <p className="text-xs text-gray-600 leading-tight">
                            {slot.selected_partner.address || 'Address not available'}
                          </p>
                        </div>

                        {/* Distance from home office (slot 0) or previous partner (slot 1+) */}
                        {slot.selected_partner.distance_from_previous !== null && slot.selected_partner.distance_from_previous !== undefined && (
                          <div className="pt-2 border-t border-gray-200">
                            <p className="text-xs text-gray-500 font-medium">
                              {index === 0 ? 'Distance from Home Office' : 'Distance from Previous'}
                            </p>
                            <p className="text-sm font-bold text-blue-600">
                              {slot.selected_partner.distance_from_previous.toFixed(1)} mi
                            </p>
                          </div>
                        )}

                        {/* Score */}
                        <div className="pt-2 border-t border-gray-200">
                          <p className="text-xs text-gray-500 font-medium">Score</p>
                          <p className="text-sm font-bold text-blue-600">{slot.selected_partner.final_score}</p>
                        </div>

                        {/* Engagement Level - Only show if NOT neutral */}
                        {slot.selected_partner.engagement_level && slot.selected_partner.engagement_level !== 'neutral' && (
                          <div className="pt-2 border-t border-gray-200">
                            <p className="text-xs text-gray-500 font-medium">Engagement</p>
                            <p className="text-xs text-gray-700 capitalize">{slot.selected_partner.engagement_level}</p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Logistics Summary - Show when auto-generated chain exists */}
              {vehicleChain && vehicleChain.logistics_summary && (
                <div className="mt-6 bg-blue-50 rounded-lg p-4 border border-blue-200">
                  <h4 className="text-sm font-semibold text-blue-900 mb-3">Chain Logistics</h4>
                  <div className="grid grid-cols-4 gap-4 text-xs">
                    <div>
                      <p className="text-blue-600 font-medium">Total Distance</p>
                      <p className="text-blue-900 font-bold text-lg">
                        {(vehicleChain.logistics_summary.total_distance_miles || 0).toFixed(1)} mi
                      </p>
                    </div>
                    <div>
                      <p className="text-blue-600 font-medium">Drive Time</p>
                      <p className="text-blue-900 font-bold text-lg">
                        {vehicleChain.logistics_summary.total_drive_time_min || 0} min
                      </p>
                    </div>
                    <div>
                      <p className="text-blue-600 font-medium">Logistics Cost</p>
                      <p className="text-blue-900 font-bold text-lg">
                        ${(vehicleChain.logistics_summary.total_logistics_cost || 0).toFixed(2)}
                      </p>
                    </div>
                    <div>
                      <p className="text-blue-600 font-medium">Avg per Hop</p>
                      <p className="text-blue-900 font-bold text-lg">
                        {(vehicleChain.logistics_summary.average_hop_distance || 0).toFixed(1)} mi
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Panel - Info - Hidden on mobile, visible on desktop */}
        <div className="hidden lg:block w-80 bg-white border-l p-6 overflow-y-auto">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">Chain Info</h2>

          <div className="space-y-4 text-sm">
            {/* Budget Status - EXACT COPY from Optimizer */}
            {chainBudget && chainBudget.fleets && (
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-3">Budget Status</h3>
                <div className="bg-gray-50 rounded p-3">
                  <div className="space-y-3 text-sm">
                    {Object.entries(chainBudget.fleets).map(([fleet, data]) => (
                      <div key={fleet}>
                        <div className="flex justify-between items-center">
                          <span className="font-medium text-gray-900">{fleet}:</span>
                          <div className="flex items-center gap-1">
                            <span className={data.current > data.budget ? 'text-red-600 font-medium' : 'text-green-600 font-medium'}>
                              ${data.current?.toLocaleString()}
                            </span>
                            <span className="text-gray-400">/</span>
                            <span className={data.current > data.budget ? 'text-red-600 font-medium' : 'text-green-700 font-semibold'}>
                              ${data.budget?.toLocaleString()}
                            </span>
                          </div>
                        </div>
                        {data.planned > 0 && (
                          <div className="flex justify-end items-center text-xs text-gray-500 mt-0.5">
                            <span>+${Math.round(data.planned).toLocaleString()} this chain → </span>
                            <span className={data.projected > data.budget ? 'text-red-600 font-medium ml-1' : 'text-blue-600 font-medium ml-1'}>
                              ${Math.round(data.projected).toLocaleString()} projected
                            </span>
                          </div>
                        )}
                      </div>
                    ))}
                    {chainBudget.total && (
                      <div className="border-t pt-2 mt-2">
                        <div className="flex justify-between items-center font-semibold">
                          <span className="text-gray-900">Total:</span>
                          <div className="flex items-center gap-1">
                            <span className={chainBudget.total.current > chainBudget.total.budget ? 'text-red-600' : 'text-green-600'}>
                              ${chainBudget.total.current?.toLocaleString()}
                            </span>
                            <span className="text-gray-400">/</span>
                            <span className={chainBudget.total.current > chainBudget.total.budget ? 'text-red-600' : 'text-green-700'}>
                              ${chainBudget.total.budget?.toLocaleString()}
                            </span>
                          </div>
                        </div>
                        {chainBudget.total.planned > 0 && (
                          <div className="flex justify-end items-center text-xs text-gray-500 mt-0.5">
                            <span>+${Math.round(chainBudget.total.planned).toLocaleString()} this chain → </span>
                            <span className={chainBudget.total.projected > chainBudget.total.budget ? 'text-red-600 font-semibold ml-1' : 'text-blue-600 font-semibold ml-1'}>
                              ${Math.round(chainBudget.total.projected).toLocaleString()} projected
                            </span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="space-y-4 text-sm mt-4">
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

      {/* Model Selector Modal */}
      {showModelSelectorModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          {/* Background overlay with rgba for transparency */}
          <div
            className="fixed inset-0 transition-opacity"
            style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)' }}
            onClick={() => setShowModelSelectorModal(false)}
          ></div>

          {/* Modal container */}
          <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20">
            {/* Modal panel - positioned above overlay with z-index */}
            <div className="relative z-50 bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all max-w-4xl w-full mx-auto">
              <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-medium text-gray-900">
                    Select Vehicle Preferences
                  </h3>
                  <button
                    onClick={() => setShowModelSelectorModal(false)}
                    className="text-gray-400 hover:text-gray-500"
                  >
                    <span className="text-2xl">&times;</span>
                  </button>
                </div>

                <p className="text-sm text-gray-500 mb-4">
                  Choose specific models to prioritize or restrict in your chain generation.
                </p>

                {/* ModelSelector Component */}
                <div className="max-h-[60vh] overflow-y-auto">
                  <ModelSelector
                    office={selectedOffice}
                    personId={selectedPartner}
                    startDate={startDate}
                    numVehicles={numVehicles}
                    daysPerLoan={daysPerLoan}
                    onSelectionChange={setModelPreferences}
                    value={modelPreferences}
                  />
                </div>
              </div>

              <div className="bg-gray-50 px-4 py-3 flex flex-row-reverse gap-3">
                <button
                  type="button"
                  onClick={() => setShowModelSelectorModal(false)}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm font-medium"
                >
                  Done ({modelPreferences.length} selected)
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setModelPreferences([]);
                    setShowModelSelectorModal(false);
                  }}
                  className="px-4 py-2 bg-white text-gray-700 rounded-md border border-gray-300 hover:bg-gray-50 text-sm font-medium"
                >
                  Clear & Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Vehicle Context Side Panel */}
      {selectedVehicleVin && (
        <div className="fixed right-0 top-0 z-50 h-full">
          <div className="bg-white w-[700px] h-full shadow-2xl overflow-y-auto border-l border-gray-200">
            <div className="sticky top-0 bg-white border-b px-6 py-4 flex justify-between items-center z-10">
              <h2 className="text-lg font-semibold text-gray-900">Vehicle Context</h2>
              <button
                onClick={closeVehicleContext}
                className="text-gray-400 hover:text-gray-600 focus:outline-none"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="p-6">
              {loadingVehicleContext ? (
                <div className="flex items-center justify-center py-12">
                  <svg className="animate-spin h-8 w-8 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                </div>
              ) : vehicleContext ? (
                <div className="space-y-6">
                  {/* Vehicle Details with Intelligence */}
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">Vehicle Details</h3>
                    <div className="bg-gray-50 rounded-lg p-4 space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-gray-600">VIN:</span>
                        <a
                          href={`https://fms.driveshop.com/vehicles/list_activities/${vehicleContext.vehicle_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm font-mono font-medium text-blue-600 hover:text-blue-800 hover:underline"
                          title="Open in FMS"
                        >
                          {vehicleContext.vin}
                        </a>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-gray-600">Make:</span>
                        <span className="text-sm font-medium text-gray-900">{vehicleContext.make}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-gray-600">Model:</span>
                        <span className="text-sm font-medium text-gray-900">{vehicleContext.model}</span>
                      </div>
                      {vehicleContext.vehicle_intelligence && (
                        <>
                          {vehicleContext.vehicle_intelligence.year && vehicleContext.vehicle_intelligence.year !== 'N/A' && (
                            <div className="flex justify-between items-center">
                              <span className="text-sm text-gray-600">Year:</span>
                              <span className="text-sm font-medium text-gray-900">{vehicleContext.vehicle_intelligence.year}</span>
                            </div>
                          )}
                          {vehicleContext.vehicle_intelligence.tier && vehicleContext.vehicle_intelligence.tier !== 'N/A' && (
                            <div className="flex justify-between items-center">
                              <span className="text-sm text-gray-600">Tier:</span>
                              <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
                                vehicleContext.vehicle_intelligence.tier === 'A' ? 'bg-green-100 text-green-800' :
                                vehicleContext.vehicle_intelligence.tier === 'B' ? 'bg-blue-100 text-blue-800' :
                                vehicleContext.vehicle_intelligence.tier === 'C' ? 'bg-yellow-100 text-yellow-800' :
                                'bg-gray-100 text-gray-800'
                              }`}>
                                {vehicleContext.vehicle_intelligence.tier}
                              </span>
                            </div>
                          )}
                          {vehicleContext.vehicle_intelligence.trim && vehicleContext.vehicle_intelligence.trim !== 'N/A' && (
                            <div className="flex justify-between items-center">
                              <span className="text-sm text-gray-600">Trim:</span>
                              <span className="text-sm font-medium text-gray-900">{vehicleContext.vehicle_intelligence.trim}</span>
                            </div>
                          )}
                        </>
                      )}
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-gray-600">Office:</span>
                        <span className="text-sm font-medium text-gray-900">{vehicleContext.office}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-gray-600">Mileage:</span>
                        <span className="text-sm font-medium text-gray-900">{vehicleContext.mileage}</span>
                      </div>
                      {vehicleContext.last_known_location && (
                        <div className="border-t pt-2 mt-2">
                          <div className="flex items-start">
                            <svg className="w-4 h-4 text-blue-600 mt-0.5 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clipRule="evenodd" />
                            </svg>
                            <div className="flex-1">
                              <p className="text-xs text-gray-500 font-medium">Last Known Location</p>
                              <p className="text-sm text-gray-900 mt-0.5">{vehicleContext.last_known_location}</p>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Budget Impact */}
                  {vehicleContext.budget_impact && Object.keys(vehicleContext.budget_impact).length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2 flex items-center justify-between">
                        <span>Budget Impact</span>
                        <span className="text-xs font-normal text-gray-400">{vehicleContext.budget_impact.quarter}</span>
                      </h3>
                      <div className="bg-gray-50 rounded-lg p-4 space-y-3">
                        <div className="grid grid-cols-3 gap-4">
                          <div className="text-center">
                            <p className="text-xs text-gray-500 mb-1">Used</p>
                            <p className="text-lg font-bold text-gray-900">
                              ${(vehicleContext.budget_impact.office_budget_current || 0).toLocaleString()}
                            </p>
                          </div>
                          <div className="text-center">
                            <p className="text-xs text-gray-500 mb-1">Total Budget</p>
                            <p className="text-lg font-bold text-gray-900">
                              ${(vehicleContext.budget_impact.office_budget_total || 0).toLocaleString()}
                            </p>
                          </div>
                          <div className="text-center">
                            <p className="text-xs text-gray-500 mb-1">% Used</p>
                            <p className={`text-lg font-bold ${
                              vehicleContext.budget_impact.percent_used >= 75 ? 'text-red-600' :
                              vehicleContext.budget_impact.percent_used >= 40 ? 'text-amber-600' :
                              'text-green-600'
                            }`}>
                              {vehicleContext.budget_impact.percent_used}%
                            </p>
                          </div>
                        </div>
                        <div className="border-t pt-3">
                          <div className="flex justify-between items-center mb-2">
                            <span className="text-sm text-gray-600">Cost per Loan:</span>
                            <span className="text-sm font-semibold text-gray-900">
                              ${(vehicleContext.budget_impact.cost_per_loan || 0).toLocaleString()}
                            </span>
                          </div>
                          <div className="flex justify-between items-center">
                            <span className="text-sm text-gray-600">Remaining Budget:</span>
                            <span className="text-sm font-semibold text-gray-900">
                              ${(vehicleContext.budget_impact.remaining_budget || 0).toLocaleString()}
                            </span>
                          </div>
                          {vehicleContext.budget_impact.impact_if_loaned > 0 && (
                            <div className="mt-2 pt-2 border-t">
                              <p className="text-xs text-gray-500">
                                Loaning this vehicle will use <span className="font-semibold text-gray-900">{vehicleContext.budget_impact.impact_if_loaned}%</span> of remaining budget
                              </p>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Publication Performance by Partner */}
                  {vehicleContext.publication_by_partner && Object.keys(vehicleContext.publication_by_partner).length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">Publication Performance by Partner</h3>
                      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                        <div className="overflow-x-auto">
                          <table className="min-w-full divide-y divide-gray-200">
                            <thead className="bg-gray-50">
                              <tr>
                                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Partner</th>
                                <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Total</th>
                                <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Published</th>
                                <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Rate</th>
                              </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-gray-200">
                              {Object.entries(vehicleContext.publication_by_partner)
                                .sort(([,a], [,b]) => b.total - a.total)
                                .slice(0, 10)
                                .map(([partnerName, stats]) => (
                                  <tr key={partnerName} className="hover:bg-gray-50">
                                    <td className="px-4 py-2 text-sm text-gray-900">{partnerName}</td>
                                    <td className="px-4 py-2 text-sm text-center text-gray-700">{stats.total}</td>
                                    <td className="px-4 py-2 text-sm text-center text-blue-600 font-medium">{stats.published}</td>
                                    <td className="px-4 py-2 text-center">
                                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                                        stats.rate >= 80 ? 'bg-green-100 text-green-800' :
                                        stats.rate >= 50 ? 'bg-amber-100 text-amber-800' :
                                        'bg-red-100 text-red-800'
                                      }`}>
                                        {stats.rate}%
                                      </span>
                                    </td>
                                  </tr>
                                ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Activity Chain Context */}
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-3">Activity Chain Context</h3>
                    <div className="space-y-3">
                      {/* Coming Off Of */}
                      <div>
                        <h4 className="text-xs font-medium text-gray-400 uppercase mb-2">Coming Off Of</h4>
                        {vehicleContext.previous_activity_expanded ? (
                          <div className="bg-gradient-to-br from-gray-50 to-gray-100 border-2 border-gray-300 rounded-lg p-4">
                            <div className="flex items-start justify-between mb-2">
                              <div className="flex-1">
                                <p className="text-sm font-semibold text-gray-900">
                                  {vehicleContext.previous_activity_expanded.partner_name || 'Unknown Partner'}
                                </p>
                                <p className="text-xs text-gray-600 mt-0.5">
                                  {vehicleContext.previous_activity_expanded.partner_office}
                                </p>
                              </div>
                              {vehicleContext.previous_activity_expanded.gap_days !== undefined && (
                                <div className="ml-3 text-right">
                                  <p className={`text-xs font-semibold ${
                                    vehicleContext.previous_activity_expanded.gap_days > 7 ? 'text-red-600' :
                                    vehicleContext.previous_activity_expanded.gap_days > 3 ? 'text-amber-600' :
                                    'text-green-600'
                                  }`}>
                                    {vehicleContext.previous_activity_expanded.gap_days} days idle
                                  </p>
                                </div>
                              )}
                            </div>
                            <div className="space-y-1">
                              <p className="text-xs text-gray-600">
                                📅 {formatActivityDate(vehicleContext.previous_activity_expanded.start_date)} - {formatActivityDate(vehicleContext.previous_activity_expanded.end_date)}
                              </p>
                              {vehicleContext.previous_activity_expanded.partner_address && (
                                <p className="text-xs text-gray-500">
                                  📍 {vehicleContext.previous_activity_expanded.partner_address}
                                </p>
                              )}
                              {vehicleContext.previous_activity_expanded.published !== undefined && (
                                <p className="text-xs">
                                  {vehicleContext.previous_activity_expanded.published ? (
                                    <span className="text-green-600 font-medium">✓ Published</span>
                                  ) : (
                                    <span className="text-gray-500">Not Published</span>
                                  )}
                                </p>
                              )}
                            </div>
                          </div>
                        ) : (
                          <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-500 text-center border-2 border-dashed border-gray-300">
                            No previous activity
                          </div>
                        )}
                      </div>

                      {/* Going To */}
                      <div>
                        <h4 className="text-xs font-medium text-gray-400 uppercase mb-2">Going To</h4>
                        {vehicleContext.next_activity_expanded ? (
                          <div className="bg-gradient-to-br from-blue-50 to-blue-100 border-2 border-blue-400 rounded-lg p-4">
                            <div className="flex items-start justify-between mb-2">
                              <div className="flex-1">
                                <p className="text-sm font-semibold text-blue-900">
                                  {vehicleContext.next_activity_expanded.partner_name || 'Unknown Partner'}
                                </p>
                                <p className="text-xs text-blue-700 mt-0.5">
                                  {vehicleContext.next_activity_expanded.partner_office}
                                </p>
                              </div>
                              {vehicleContext.next_activity_expanded.days_until !== undefined && (
                                <div className="ml-3 text-right">
                                  <p className="text-xs font-semibold text-blue-700">
                                    in {vehicleContext.next_activity_expanded.days_until} days
                                  </p>
                                </div>
                              )}
                            </div>
                            <div className="space-y-1">
                              <p className="text-xs text-blue-700">
                                📅 {formatActivityDate(vehicleContext.next_activity_expanded.start_date)} - {formatActivityDate(vehicleContext.next_activity_expanded.end_date || 'TBD')}
                              </p>
                              {vehicleContext.next_activity_expanded.partner_address && (
                                <p className="text-xs text-blue-600">
                                  📍 {vehicleContext.next_activity_expanded.partner_address}
                                </p>
                              )}
                            </div>
                          </div>
                        ) : (
                          <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-500 text-center border-2 border-dashed border-gray-300">
                            No upcoming activity
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Activity Timeline */}
                  {vehicleContext.timeline && vehicleContext.timeline.length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">Activity Timeline</h3>
                      <div className="bg-gray-50 rounded-lg p-4">
                        <div className="space-y-2">
                          {vehicleContext.timeline.slice(0, 10).map((activity, idx) => {
                            // Determine if this activity is past, current, or future
                            const now = new Date();
                            const startDate = new Date(activity.start_date);
                            const endDate = activity.end_date ? new Date(activity.end_date) : null;

                            const isPast = endDate && endDate < now;
                            const isCurrent = startDate <= now && (!endDate || endDate >= now);

                            return (
                              <div key={idx} className={`flex items-center text-sm ${isCurrent ? 'font-medium text-blue-900' : 'text-gray-700'}`}>
                                <div className={`w-2 h-2 rounded-full mr-2 flex-shrink-0 ${
                                  isPast ? 'bg-gray-400' :
                                  isCurrent ? 'bg-blue-500' :
                                  'bg-blue-400'
                                }`}></div>
                                <div className="flex-1 min-w-0">
                                  <p className="truncate text-xs">{activity.partner_name || 'Unknown Partner'}</p>
                                  <p className="text-xs text-gray-500">
                                    {formatActivityDate(activity.start_date)} - {formatActivityDate(activity.end_date)}
                                  </p>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-12 text-gray-500">
                  <p>Unable to load vehicle context</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Assignment Details Panel */}
      {selectedAssignment && (
        <AssignmentDetailsPanel
          assignment={selectedAssignment}
          office={selectedOffice}
          onClose={() => setSelectedAssignment(null)}
          onDelete={handleTimelineBarDelete}
          onRequest={handleTimelineBarRequest}
          onUnrequest={handleTimelineBarUnrequest}
        />
      )}
    </div>
  );
}

export default ChainBuilder;
