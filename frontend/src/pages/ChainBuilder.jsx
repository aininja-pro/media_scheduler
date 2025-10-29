import React, { useState, useEffect } from 'react';

function ChainBuilder({ sharedOffice }) {
  // Chain mode: 'partner' (existing) or 'vehicle' (new)
  const [chainMode, setChainMode] = useState('partner');

  // Use shared office from parent, default to 'Los Angeles'
  const [selectedOffice, setSelectedOffice] = useState(sharedOffice || 'Los Angeles');
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
  const [showPartnerDropdown, setShowPartnerDropdown] = useState(false);

  // Vehicle search (for vehicle chain mode)
  const [vehicles, setVehicles] = useState([]);
  const [vehicleSearchQuery, setVehicleSearchQuery] = useState('');
  const [selectedVehicle, setSelectedVehicle] = useState(null);
  const [showVehicleDropdown, setShowVehicleDropdown] = useState(false);

  // Partner intelligence (current/scheduled activities)
  const [partnerIntelligence, setPartnerIntelligence] = useState(null);
  const [loadingIntelligence, setLoadingIntelligence] = useState(false);

  // Make filtering
  const [selectedMakes, setSelectedMakes] = useState([]);

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

  // Budget calculation for chain
  const [chainBudget, setChainBudget] = useState(null);

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

  // Load vehicles when office changes or search query updates (debounced)
  useEffect(() => {
    if (!selectedOffice || chainMode !== 'vehicle') return;

    // Only search if we have a search query (at least 1 character)
    if (!vehicleSearchQuery || vehicleSearchQuery.length === 0) {
      setVehicles([]);
      return;
    }

    const loadVehicles = async () => {
      try {
        const response = await fetch(
          `http://localhost:8081/api/chain-builder/search-vehicles?office=${encodeURIComponent(selectedOffice)}&search_term=${encodeURIComponent(vehicleSearchQuery)}&limit=50`
        );

        if (!response.ok) {
          console.error('Failed to load vehicles');
          setVehicles([]);
          return;
        }

        const data = await response.json();
        setVehicles(data.vehicles || []);
        console.log(`Loaded ${data.vehicles?.length || 0} vehicles for search "${vehicleSearchQuery}" in ${selectedOffice}`);
      } catch (err) {
        console.error('Failed to load vehicles:', err);
        setVehicles([]);
      }
    };

    // Debounce the search - wait 300ms after user stops typing
    const timeoutId = setTimeout(() => {
      loadVehicles();
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [selectedOffice, vehicleSearchQuery, chainMode]);

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
  }, []);

  // Save chain mode to sessionStorage
  useEffect(() => {
    sessionStorage.setItem('chainbuilder_chain_mode', chainMode);
  }, [chainMode]);

  // Save selected partner to sessionStorage
  useEffect(() => {
    if (selectedPartner) {
      sessionStorage.setItem('chainbuilder_partner_id', selectedPartner);
      const partner = partners.find(p => p.person_id === selectedPartner);
      if (partner) {
        sessionStorage.setItem('chainbuilder_partner_name', partner.name);
      }
    }
  }, [selectedPartner, partners]);

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

  // Refresh partner intelligence when tab becomes visible (detect visibility change)
  useEffect(() => {
    const handleVisibilityChange = () => {
      // When tab becomes visible and we have a selected partner, refresh intelligence
      if (!document.hidden && selectedPartner && selectedOffice) {
        const refreshPartnerIntelligence = async () => {
          try {
            const response = await fetch(
              `http://localhost:8081/api/ui/phase7/partner-intelligence?person_id=${selectedPartner}&office=${encodeURIComponent(selectedOffice)}`
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
        `http://localhost:8081/api/ui/phase7/partner-intelligence?person_id=${selectedPartner}&office=${encodeURIComponent(selectedOffice)}`
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

  const deleteEntireChain = async () => {
    if (!partnerIntelligence || !partnerIntelligence.upcoming_assignments) {
      return;
    }

    const chainAssignments = partnerIntelligence.upcoming_assignments.filter(a => a.status === 'manual');

    if (chainAssignments.length === 0) {
      setSaveMessage('❌ No saved chain to delete');
      return;
    }

    if (!window.confirm(`Delete entire chain (${chainAssignments.length} vehicles) for ${partnerIntelligence.partner.name}?`)) {
      return;
    }

    setIsSaving(true);
    setSaveMessage('');

    try {
      // Delete each assignment
      for (const assignment of chainAssignments) {
        await fetch(`http://localhost:8081/api/calendar/delete-assignment/${assignment.assignment_id}`, {
          method: 'DELETE'
        });
      }

      setSaveMessage(`✅ Deleted ${chainAssignments.length} vehicles from chain`);

      // Reload partner intelligence to refresh calendar
      if (selectedPartner && selectedOffice) {
        const response = await fetch(
          `http://localhost:8081/api/ui/phase7/partner-intelligence?person_id=${selectedPartner}&office=${encodeURIComponent(selectedOffice)}`
        );
        if (response.ok) {
          const data = await response.json();
          if (data.success) {
            setPartnerIntelligence(data);
          }
        }
      }
    } catch (err) {
      setSaveMessage(`❌ Error deleting chain: ${err.message}`);
    } finally {
      setIsSaving(false);
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

      const response = await fetch(`http://localhost:8081/api/chain-builder/suggest-chain?${params}`);
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
        await fetch(`http://localhost:8081/api/calendar/delete-assignment/${swapSlot.assignment_id}`, {
          method: 'DELETE'
        });
      }

      // Save new vehicle
      await fetch('http://localhost:8081/api/chain-builder/save-chain', {
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
          `http://localhost:8081/api/ui/phase7/partner-intelligence?person_id=${selectedPartner}&office=${encodeURIComponent(selectedOffice)}`
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
      const response = await fetch(`http://localhost:8081/api/calendar/delete-assignment/${assignmentId}`, {
        method: 'DELETE'
      });

      const result = await response.json();

      if (result.success) {
        setSaveMessage('✅ Vehicle removed from chain');

        // Reload partner intelligence to refresh
        if (selectedPartner && selectedOffice) {
          const resp = await fetch(
            `http://localhost:8081/api/ui/phase7/partner-intelligence?person_id=${selectedPartner}&office=${encodeURIComponent(selectedOffice)}`
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
      const response = await fetch('http://localhost:8081/api/chain-builder/save-chain', {
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
          `http://localhost:8081/api/ui/phase7/partner-intelligence?person_id=${selectedPartner}&office=${encodeURIComponent(selectedOffice)}`
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

    try {
      const params = new URLSearchParams({
        person_id: selectedPartner,
        office: selectedOffice,
        start_date: startDate,
        num_vehicles: numVehicles,
        days_per_loan: daysPerLoan
      });

      // Add selected makes filter if any are selected
      if (selectedMakes.length > 0) {
        params.append('preferred_makes', selectedMakes.join(','));
      }

      const response = await fetch(`http://localhost:8081/api/chain-builder/suggest-chain?${params}`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to generate chain');
      }

      setChain(data);
      console.log('Chain generated:', data);

      // Convert auto-generated chain to manual slots format for editing
      const slots = data.chain.map((vehicle, index) => ({
        slot: vehicle.slot,
        start_date: vehicle.start_date,
        end_date: vehicle.end_date,
        selected_vehicle: {
          vin: vehicle.vin,
          make: vehicle.make,
          model: vehicle.model,
          year: vehicle.year,
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
      setTimeout(() => calculateChainBudget(), 100);
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

      const response = await fetch(`http://localhost:8081/api/chain-builder/suggest-chain?${params}`);
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

      const response = await fetch(`http://localhost:8081/api/chain-builder/get-slot-options?${params}`);
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
    if (shouldCalculateBudget && manualSlots.length > 0 && selectedPartner) {
      const timer = setTimeout(() => {
        calculateChainBudget();
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [manualSlots, selectedPartner, shouldCalculateBudget]);

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

  const calculateChainBudget = async () => {
    // Only calculate if we have slots with selected vehicles
    const filledSlots = manualSlots.filter(s => s.selected_vehicle);
    if (filledSlots.length === 0) {
      setChainBudget(null);
      return;
    }

    try {
      const chainData = filledSlots.map(slot => ({
        person_id: selectedPartner,
        make: slot.selected_vehicle.make,
        start_date: slot.start_date
      }));

      const response = await fetch('http://localhost:8081/api/chain-builder/calculate-chain-budget', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          office: selectedOffice,
          chain: chainData
        })
      });

      const data = await response.json();
      setChainBudget(data);
    } catch (err) {
      console.error('Error calculating budget:', err);
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

      const response = await fetch('http://localhost:8081/api/chain-builder/save-chain', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          person_id: selectedPartner,
          partner_name: partner.name,
          office: selectedOffice,
          status: status,  // 'manual' or 'requested'
          chain: chainData
        })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to save chain');
      }

      setSaveMessage(`✅ ${data.message} View in Calendar tab.`);
      console.log('Manual chain saved:', data);

      // Clear the proposed chain slots (green bars) since they're now saved
      setManualSlots([]);
      setChain(null);

      // Reload partner intelligence to show the saved assignments (magenta/green bars)
      if (selectedPartner && selectedOffice) {
        const resp = await fetch(
          `http://localhost:8081/api/ui/phase7/partner-intelligence?person_id=${selectedPartner}&office=${encodeURIComponent(selectedOffice)}`
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

  return (
    <div className="w-full min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="!text-base font-semibold text-gray-900">Chain Builder</h1>
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
                onChange={(e) => setSelectedOffice(e.target.value)}
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
      <div className="flex h-full">
        {/* Left Panel - Chain Parameters */}
        <div className="w-80 bg-white border-r p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">Chain Parameters</h2>

          <div className="space-y-6">
            {/* Partner Chain Mode - Partner Selector */}
            {chainMode === 'partner' && (
              <div className="relative">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Media Partner
                </label>

              {/* Search Input */}
              <input
                type="text"
                placeholder="Type to search partners..."
                value={partnerSearchQuery}
                onChange={(e) => {
                  setPartnerSearchQuery(e.target.value);
                  setShowPartnerDropdown(true);
                }}
                onFocus={() => setShowPartnerDropdown(true)}
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />

              {/* Dropdown - only show when focused and has results */}
              {showPartnerDropdown && partnerSearchQuery.length > 0 && (
                <div className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-y-auto">
                  {partners
                    .filter(partner =>
                      partner.name.toLowerCase().includes(partnerSearchQuery.toLowerCase())
                    )
                    .slice(0, 20)  // Limit to 20 results
                    .map(partner => (
                      <button
                        key={partner.person_id}
                        onClick={() => {
                          setSelectedPartner(partner.person_id);
                          setPartnerSearchQuery(partner.name);
                          setShowPartnerDropdown(false);
                        }}
                        className="w-full text-left px-3 py-2 text-sm hover:bg-blue-50 transition-colors border-b last:border-b-0"
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
              )}

              {selectedPartner && !showPartnerDropdown && (
                <p className="text-xs text-gray-500 mt-1">
                  Selected: {partners.find(p => p.person_id === selectedPartner)?.name}
                </p>
              )}
              </div>
            )}

            {/* Vehicle Chain Mode - Vehicle Selector */}
            {chainMode === 'vehicle' && (
              <div className="relative">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Vehicle
                </label>

                {/* Vehicle Search Input */}
                <input
                  type="text"
                  placeholder="Type VIN, make, or model..."
                  value={vehicleSearchQuery}
                  onChange={(e) => {
                    setVehicleSearchQuery(e.target.value);
                    setShowVehicleDropdown(true);
                  }}
                  onFocus={() => setShowVehicleDropdown(true)}
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />

                {/* Vehicle Dropdown */}
                {showVehicleDropdown && vehicleSearchQuery.length > 0 && (
                  <div className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-y-auto">
                    {vehicles.length > 0 ? (
                      vehicles.map(vehicle => (
                        <button
                          key={vehicle.vin}
                          onClick={() => {
                            setSelectedVehicle(vehicle);
                            setVehicleSearchQuery(`${vehicle.make} ${vehicle.model} ${vehicle.year} (${vehicle.vin.slice(-6)})`);
                            setShowVehicleDropdown(false);
                          }}
                          className="w-full text-left px-3 py-2 text-sm hover:bg-blue-50 transition-colors border-b last:border-b-0"
                        >
                          <div className="font-medium">{vehicle.make} {vehicle.model} {vehicle.year}</div>
                          <div className="text-xs text-gray-500 mt-0.5">
                            VIN: {vehicle.vin} | Tier: {vehicle.tier}
                          </div>
                        </button>
                      ))
                    ) : (
                      <div className="px-3 py-4 text-sm text-gray-500 text-center">
                        No vehicles found for "{vehicleSearchQuery}"
                      </div>
                    )}
                  </div>
                )}

                {/* Selected Vehicle Display */}
                {selectedVehicle && !showVehicleDropdown && (
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
                  </div>
                )}
              </div>
            )}

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

            {/* Number of Vehicles (Partner Chain Mode) */}
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

            {/* Number of Partners (Vehicle Chain Mode) */}
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

            {/* Make Filter - Show when partner is selected (Partner Chain Mode Only) */}
            {chainMode === 'partner' && partnerIntelligence && partnerIntelligence.approved_makes && partnerIntelligence.approved_makes.length > 0 && (
              <div className="border-t pt-4">
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-sm font-medium text-gray-700">
                    Filter by Make
                  </label>
                  <button
                    onClick={() => {
                      const allMakes = partnerIntelligence.approved_makes.map(m => m.make);
                      setSelectedMakes(selectedMakes.length === allMakes.length ? [] : allMakes);
                    }}
                    className="text-xs text-blue-600 hover:text-blue-800"
                  >
                    {selectedMakes.length === partnerIntelligence.approved_makes.length ? 'Clear All' : 'Select All'}
                  </button>
                </div>

                <div className="max-h-48 overflow-y-auto border border-gray-200 rounded p-2 space-y-1">
                  {partnerIntelligence.approved_makes
                    .sort((a, b) => a.make.localeCompare(b.make))
                    .map((item) => (
                      <label
                        key={item.make}
                        className="flex items-center gap-2 px-2 py-1 hover:bg-gray-50 rounded cursor-pointer"
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
                          className="rounded border-gray-300"
                        />
                        <span className="text-xs flex-1">{item.make}</span>
                        <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${
                          item.rank === 'A+' ? 'bg-purple-100 text-purple-800' :
                          item.rank === 'A' ? 'bg-blue-100 text-blue-800' :
                          item.rank === 'B' ? 'bg-green-100 text-green-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {item.rank}
                        </span>
                      </label>
                    ))}
                </div>

                <p className="text-xs text-gray-500 mt-2">
                  {selectedMakes.length} of {partnerIntelligence.approved_makes.length} makes selected
                </p>
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
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-700">
                Vehicle chain generation coming soon...
                <br />Build mode: {vehicleBuildMode}
              </div>
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

          {selectedPartner && loadingIntelligence ? (
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
          ) : selectedPartner && partnerIntelligence ? (
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

                  <div className="flex items-center gap-3">
                    {/* Delete Chain Button - show if partner has saved manual chains */}
                    {partnerIntelligence?.upcoming_assignments?.some(a => a.status === 'manual') && (
                      <button
                        onClick={deleteEntireChain}
                        disabled={isSaving}
                        className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                          isSaving
                            ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                            : 'bg-red-600 text-white hover:bg-red-700'
                        }`}
                      >
                        Delete Saved Chain
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

                                // Color by type and status: BLUE for active, MAGENTA for requested, GREEN for planned/manual
                                const barColor = activity.type === 'active'
                                  ? 'bg-gradient-to-br from-blue-500 to-blue-600 border-blue-700'
                                  : activity.status === 'requested'
                                    ? 'bg-gradient-to-br from-pink-500 to-pink-600 border-pink-700'
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
                                    ? `Slot ${slot.slot}: ${slot.selected_vehicle.make} ${slot.selected_vehicle.model}\n${slot.start_date} - ${slot.end_date}\nScore: ${slot.selected_vehicle.score}`
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
                        onClick={saveManualChain}
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
                  <div className="grid grid-cols-5 gap-4">
                    {manualSlots.map((slot, index) => (
                      <div
                        key={slot.slot}
                        className="border-2 border-gray-200 rounded-lg p-4 hover:shadow-lg transition-all relative"
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

                        {/* Header: Slot + Available Count */}
                        <div className="flex items-center justify-between mb-3">
                          <span className="text-sm font-bold text-gray-700">Slot {slot.slot}</span>
                          {/* Show actual dropdown count if loaded, otherwise show estimated count */}
                          {loadingSlotOptions[index] ? (
                            <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                              Loading...
                            </span>
                          ) : slot.eligible_vehicles.length > 0 ? (
                            <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
                              {slot.eligible_vehicles.length} avail
                            </span>
                          ) : slot.available_count > 0 ? (
                            <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                              ~{slot.available_count} est
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
                            <select
                              className="w-full border border-gray-300 rounded px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500 max-h-48 overflow-y-auto"
                              size="1"
                              onChange={(e) => {
                                if (e.target.value) {
                                  const vehicle = slot.eligible_vehicles.find(v => v.vin === e.target.value);
                                  if (vehicle) {
                                    selectVehicleForSlot(index, vehicle);
                                  }
                                }
                              }}
                              onFocus={() => {
                                // Load options when dropdown is focused (lazy loading)
                                if (slot.eligible_vehicles.length === 0) {
                                  loadSlotOptions(index);
                                }
                              }}
                              value=""
                            >
                              <option value="">
                                {loadingSlotOptions[index] ? 'Loading options...' :
                                 slot.eligible_vehicles.length === 0 ? 'Click to load options...' :
                                 'Choose vehicle...'}
                              </option>
                              {slot.eligible_vehicles
                                .sort((a, b) => {
                                  // Sort by Make alphabetically, then by Score descending
                                  if (a.make !== b.make) {
                                    return a.make.localeCompare(b.make);
                                  }
                                  return b.score - a.score;
                                })
                                .map(vehicle => (
                                  <option key={vehicle.vin} value={vehicle.vin}>
                                    {vehicle.make} {vehicle.model} ({vehicle.tier}) - Score: {vehicle.score} - {vehicle.last_4_vin}
                                  </option>
                                ))}
                            </select>
                            {slot.available_count === 0 && (
                              <p className="text-xs text-red-600 mt-1">No vehicles available</p>
                            )}
                          </div>
                        ) : (
                          /* Show selected vehicle */
                          <div className="space-y-2">
                            <div className="flex items-center justify-between">
                              <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-bold ${
                                slot.selected_vehicle.tier === 'A+' ? 'bg-purple-100 text-purple-800 border border-purple-300' :
                                slot.selected_vehicle.tier === 'A' ? 'bg-blue-100 text-blue-800 border border-blue-300' :
                                slot.selected_vehicle.tier === 'B' ? 'bg-green-100 text-green-800 border border-green-300' :
                                'bg-gray-100 text-gray-800 border border-gray-300'
                              }`}>
                                {slot.selected_vehicle.tier}
                              </span>
                              <button
                                onClick={() => selectVehicleForSlot(index, null)}
                                className="text-xs text-red-600 hover:text-red-800 underline"
                              >
                                Change
                              </button>
                            </div>

                            <div>
                              <h4 className="font-semibold text-gray-900 text-sm leading-tight">
                                {slot.selected_vehicle.make}
                              </h4>
                              <p className="text-xs text-gray-600 leading-tight">
                                {slot.selected_vehicle.model}
                              </p>
                              <p className="text-xs text-gray-400">{slot.selected_vehicle.year}</p>
                            </div>

                            <div className="pt-2 border-t border-gray-200">
                              <p className="text-xs text-gray-500 font-medium">VIN</p>
                              <a
                                href={`https://fms.driveshop.com/list_activities/${slot.selected_vehicle.vin}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs font-mono text-blue-600 hover:text-blue-800 hover:underline"
                                title="Open in FMS"
                              >
                                ...{slot.selected_vehicle.last_4_vin}
                              </a>
                            </div>

                            <div className="pt-2 border-t border-gray-200">
                              <p className="text-xs text-gray-500 font-medium">Score</p>
                              <p className="text-sm font-bold text-blue-600">{slot.selected_vehicle.score}</p>
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
                        onClick={() => alert(`Click to swap Slot ${vehicle.slot} - Feature coming next!`)}
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
        <div className="w-80 bg-white border-l p-6 overflow-y-auto">
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
    </div>
  );
}

export default ChainBuilder;
