import React, { useState, useEffect, useMemo } from 'react';

// Haversine distance calculation (in miles)
const calculateDistance = (lat1, lon1, lat2, lon2) => {
  const R = 3959; // Earth's radius in miles
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon/2) * Math.sin(dLon/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  return R * c;
};

function Calendar({ sharedOffice }) {
  // Use shared office from parent, default to 'Los Angeles' if not provided
  const [selectedOffice, setSelectedOffice] = useState(sharedOffice || 'Los Angeles');

  // Update selectedOffice when sharedOffice prop changes
  useEffect(() => {
    if (sharedOffice) {
      setSelectedOffice(sharedOffice);
    }
  }, [sharedOffice]);
  const [selectedMonth, setSelectedMonth] = useState('');
  const [viewStartDate, setViewStartDate] = useState(null); // Custom start date for sliding view
  const [viewEndDate, setViewEndDate] = useState(null); // Custom end date for sliding view
  const [activities, setActivities] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  // View mode toggle
  const [viewMode, setViewMode] = useState('vehicle'); // 'vehicle' or 'partner'

  // Partner distances cache
  const [partnerDistances, setPartnerDistances] = useState({});

  // Filters
  const [vinFilter, setVinFilter] = useState('');
  const [makeFilter, setMakeFilter] = useState('');
  const [partnerFilter, setPartnerFilter] = useState('');
  const [activityFilter, setActivityFilter] = useState('all'); // 'all', 'with-activity', 'no-activity'

  // Multi-select filters
  const [selectedPartners, setSelectedPartners] = useState([]); // Array of person_ids
  const [selectedVehicles, setSelectedVehicles] = useState([]); // Array of VINs
  const [selectedTiers, setSelectedTiers] = useState([]); // Array of tier ranks (A+, A, B, C)
  const [showPartnerDropdown, setShowPartnerDropdown] = useState(false);
  const [showVehicleDropdown, setShowVehicleDropdown] = useState(false);
  const [showTierDropdown, setShowTierDropdown] = useState(false);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (!e.target.closest('.multi-select-dropdown')) {
        setShowPartnerDropdown(false);
        setShowVehicleDropdown(false);
        setShowTierDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Sorting
  const [sortBy, setSortBy] = useState('make'); // 'make', 'model', 'vin'
  const [sortOrder, setSortOrder] = useState('asc'); // 'asc', 'desc'

  // What-If Mode for drag-drop scenarios
  const [whatIfMode, setWhatIfMode] = useState(false);
  const [scenarioChanges, setScenarioChanges] = useState({});

  // Vehicle context (reuse existing side panel)
  const [selectedVin, setSelectedVin] = useState(null);
  const [vehicleContext, setVehicleContext] = useState(null);
  const [loadingVehicleContext, setLoadingVehicleContext] = useState(false);

  // Chaining opportunities
  const [chainingOpportunities, setChainingOpportunities] = useState(null);
  const [loadingChains, setLoadingChains] = useState(false);

  // Partner context for partner view
  const [selectedPartnerId, setSelectedPartnerId] = useState(null);
  const [partnerContext, setPartnerContext] = useState(null);
  const [loadingPartnerContext, setLoadingPartnerContext] = useState(false);

  // Load offices
  const [offices, setOffices] = useState([]);

  // All vehicles and partners for the office (full inventory)
  const [allVehicles, setAllVehicles] = useState([]);
  const [allPartners, setAllPartners] = useState([]);
  const [partnerTiers, setPartnerTiers] = useState({}); // {person_id: {make: rank, ...}}

  useEffect(() => {
    const loadOffices = async () => {
      try {
        const response = await fetch('http://localhost:8081/api/offices');
        const data = await response.json();
        if (data && data.length > 0) {
          setOffices(data.map(office => office.name));
          if (!data.find(o => o.name === selectedOffice)) {
            setSelectedOffice(data[0].name);
          }
        }
      } catch (err) {
        console.error('Failed to load offices:', err);
        setOffices(['Los Angeles', 'Atlanta', 'Chicago', 'Dallas', 'Denver', 'Detroit', 'Miami', 'Phoenix', 'San Francisco', 'Seattle']);
      }
    };
    loadOffices();
  }, []);

  // Set current month as default
  useEffect(() => {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const monthStr = `${year}-${month}`;
    setSelectedMonth(monthStr);

    // Initialize view dates to show full month
    const startOfMonth = new Date(year, now.getMonth(), 1);
    const endOfMonth = new Date(year, now.getMonth() + 1, 0);
    setViewStartDate(startOfMonth);
    setViewEndDate(endOfMonth);
  }, []);

  // When month selector changes, reset view to show full month
  const handleMonthChange = (monthStr) => {
    setSelectedMonth(monthStr);
    const [year, month] = monthStr.split('-');
    const startOfMonth = new Date(parseInt(year), parseInt(month) - 1, 1);
    const endOfMonth = new Date(parseInt(year), parseInt(month), 0);
    setViewStartDate(startOfMonth);
    setViewEndDate(endOfMonth);
  };

  // Slide view forward by 7 days
  const slideForward = () => {
    if (!viewStartDate || !viewEndDate) return;
    const newStart = new Date(viewStartDate);
    const newEnd = new Date(viewEndDate);
    newStart.setDate(newStart.getDate() + 7);
    newEnd.setDate(newEnd.getDate() + 7);
    setViewStartDate(newStart);
    setViewEndDate(newEnd);
    // Clear month selector since we're now in custom range
    setSelectedMonth('');
  };

  // Slide view backward by 7 days
  const slideBackward = () => {
    if (!viewStartDate || !viewEndDate) return;
    const newStart = new Date(viewStartDate);
    const newEnd = new Date(viewEndDate);
    newStart.setDate(newStart.getDate() - 7);
    newEnd.setDate(newEnd.getDate() - 7);
    setViewStartDate(newStart);
    setViewEndDate(newEnd);
    // Clear month selector since we're now in custom range
    setSelectedMonth('');
  };

  // Clear all filters
  const clearAllFilters = () => {
    setVinFilter('');
    setMakeFilter('');
    setPartnerFilter('');
    setActivityFilter('all');
    setSelectedPartners([]);
    setSelectedVehicles([]);
    setSelectedTiers([]);
    setSortBy('make');
    setSortOrder('asc');
  };

  // Load all vehicles for the office (full inventory)
  useEffect(() => {
    const loadVehicles = async () => {
      if (!selectedOffice) return;
      try {
        const response = await fetch(`http://localhost:8081/api/calendar/vehicles?office=${selectedOffice}`);
        if (response.ok) {
          const data = await response.json();
          setAllVehicles(data.vehicles || []);
        }
      } catch (err) {
        console.error('Failed to load vehicles:', err);
      }
    };
    loadVehicles();
  }, [selectedOffice]);

  // Load all media partners for the office (full inventory with distances)
  useEffect(() => {
    const loadPartners = async () => {
      if (!selectedOffice) return;
      try {
        const response = await fetch(`http://localhost:8081/api/calendar/media-partners?office=${selectedOffice}`);
        if (response.ok) {
          const data = await response.json();
          setAllPartners(data.partners || []);

          // Build distance cache from partner data
          const distances = {};
          (data.partners || []).forEach(partner => {
            if (partner.distance_miles !== null && partner.distance_miles !== undefined) {
              distances[partner.person_id] = {
                success: true,
                distance_miles: partner.distance_miles,
                location_type: partner.location_type
              };
            }
          });
          setPartnerDistances(distances);
        }

        // Fetch tier data for all partners in one call
        const tierResponse = await fetch(`http://localhost:8081/api/calendar/partner-tiers?office=${selectedOffice}`);
        if (tierResponse.ok) {
          const tierData = await tierResponse.json();
          setPartnerTiers(tierData.tiers || {});
        }
      } catch (err) {
        console.error('Failed to load partners:', err);
      }
    };
    loadPartners();
  }, [selectedOffice]);

  // Load activities when office or date range changes
  useEffect(() => {
    if (selectedOffice && viewStartDate && viewEndDate) {
      loadActivities();
    }
  }, [selectedOffice, viewStartDate, viewEndDate]);

  // Fetch distances for partners with activities (optimization - only fetch what we need)
  useEffect(() => {
    if (selectedOffice && activities.length > 0) {
      const fetchDistances = async () => {
        const distances = { ...partnerDistances }; // Keep existing distances

        // Get unique partners from activities
        const uniquePartners = [...new Set(activities.map(a => a.person_id))];

        // Only fetch distances for partners we don't already have
        const partnersToFetch = uniquePartners.filter(id => !distances[id]);

        for (const personId of partnersToFetch) {
          try {
            const params = new URLSearchParams({
              person_id: personId,
              office: selectedOffice
            });
            const response = await fetch(`http://localhost:8081/api/ui/phase7/partner-distance?${params}`);
            if (response.ok) {
              const data = await response.json();
              if (data.success) {
                distances[personId] = data;
              }
            }
          } catch (err) {
            console.error(`Failed to fetch distance for partner ${personId}:`, err);
          }
        }

        setPartnerDistances(distances);
      };

      fetchDistances();
    }
  }, [selectedOffice, activities]);

  const loadActivities = async () => {
    if (!selectedOffice || !viewStartDate || !viewEndDate) return;

    setIsLoading(true);
    setError('');

    try {
      const startDate = viewStartDate.toISOString().split('T')[0];
      const endDate = viewEndDate.toISOString().split('T')[0];

      const params = new URLSearchParams({
        office: selectedOffice,
        start_date: startDate,
        end_date: endDate
      });

      const response = await fetch(`http://localhost:8081/api/calendar/activity?${params}`);
      if (!response.ok) throw new Error('Failed to fetch activities');

      const data = await response.json();
      setActivities(data.activities || []);
    } catch (err) {
      setError(err.message);
      console.error('Error loading activities:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // Helper: Parse date string as local date (YYYY-MM-DD)
  const parseLocalDate = (dateStr) => {
    if (!dateStr || typeof dateStr !== 'string') return null;
    try {
      const parts = dateStr.split('-');
      if (parts.length !== 3) return null;
      const [year, month, day] = parts.map(Number);
      if (isNaN(year) || isNaN(month) || isNaN(day)) return null;
      return new Date(year, month - 1, day);
    } catch (e) {
      return null;
    }
  };

  // Helper: Check if activity overlaps with the current view range
  const activityOverlapsMonth = (activity) => {
    if (!viewStartDate || !viewEndDate) return false;

    const rangeStart = new Date(viewStartDate);
    rangeStart.setHours(0, 0, 0, 0);
    const rangeEnd = new Date(viewEndDate);
    rangeEnd.setHours(23, 59, 59, 999);

    const activityStart = parseLocalDate(activity.start_date);
    const activityEnd = parseLocalDate(activity.end_date);

    return activityEnd >= rangeStart && activityStart <= rangeEnd;
  };

  // Group activities by VIN - START with ALL vehicles for office
  const groupedByVin = useMemo(() => {
    const grouped = {};

    // First, add ALL vehicles for this office (full inventory)
    allVehicles.forEach(vehicle => {
      const vehicleActivities = [];

      // Add lifecycle unavailability periods as synthetic activities
      if (viewStartDate && viewEndDate) {
        const rangeStart = new Date(viewStartDate);
        const rangeEnd = new Date(viewEndDate);
        const today = new Date();
        today.setHours(0, 0, 0, 0);

        // Check if vehicle is not in service yet (before in_service_date)
        if (vehicle.in_service_date) {
          const inServiceDate = new Date(vehicle.in_service_date);
          // Only show if in_service_date is in the future
          if (inServiceDate > today && inServiceDate > rangeStart) {
            vehicleActivities.push({
              vin: vehicle.vin,
              status: 'unavailable',
              activity_type: 'Not in service yet',
              start_date: rangeStart.toISOString().split('T')[0],
              end_date: new Date(Math.min(inServiceDate.getTime() - 86400000, rangeEnd.getTime())).toISOString().split('T')[0],
              partner_name: 'Not in service'
            });
          }
        }

        // Note: expected_turn_in_date is shown in vehicle info, not as unavailability
        // Turn-in is a soft date, vehicles can still have loans before it
      }

      grouped[vehicle.vin] = {
        vin: vehicle.vin,
        make: vehicle.make,
        model: vehicle.model,
        office: vehicle.office,
        in_service_date: vehicle.in_service_date,
        expected_turn_in_date: vehicle.expected_turn_in_date,
        activities: vehicleActivities
      };
    });

    // Then, add actual loan activities to vehicles
    activities.forEach(activity => {
      const vin = activity.vin;
      if (grouped[vin]) {
        grouped[vin].activities.push(activity);
      }
    });

    return grouped;
  }, [allVehicles, activities, viewStartDate, viewEndDate]);

  // Group activities by Partner - START with ALL partners for office
  const groupedByPartner = useMemo(() => {
    const grouped = {};

    // First, add ALL partners for this office (full inventory)
    allPartners.forEach(partner => {
      grouped[partner.person_id] = {
        person_id: partner.person_id,
        partner_name: partner.name,
        office: partner.office,
        activities: []
      };
    });

    // Then, add activities to partners that have them
    activities.forEach(activity => {
      const partnerId = activity.person_id;
      if (grouped[partnerId]) {
        grouped[partnerId].activities.push(activity);
      }
    });

    return grouped;
  }, [allPartners, activities]);

  // Apply filters based on view mode
  const filteredVins = Object.values(groupedByVin).filter(vehicle => {
    // Multi-select vehicle filter
    if (selectedVehicles.length > 0 && !selectedVehicles.includes(vehicle.vin)) return false;

    // Activity filter
    const hasActivityThisMonth = vehicle.activities.some(a => activityOverlapsMonth(a));
    if (activityFilter === 'with-activity' && !hasActivityThisMonth) return false;
    if (activityFilter === 'no-activity' && hasActivityThisMonth) return false;

    // Other filters
    if (vinFilter && !vehicle.vin.toLowerCase().includes(vinFilter.toLowerCase())) return false;
    if (makeFilter && vehicle.make !== makeFilter) return false;
    if (partnerFilter) {
      const hasPartner = vehicle.activities.some(a =>
        a.partner_name?.toLowerCase().includes(partnerFilter.toLowerCase())
      );
      if (!hasPartner) return false;
    }
    return true;
  });

  const filteredPartners = Object.values(groupedByPartner).filter(partner => {
    // Multi-select partner filter
    if (selectedPartners.length > 0 && !selectedPartners.includes(partner.person_id)) return false;

    // Tier filter - show partners who have selected tier(s) for the selected make (or any make if no make selected)
    if (selectedTiers.length > 0) {
      const partnerTierData = partnerTiers[partner.person_id];
      if (!partnerTierData) return false; // Partner has no approved makes

      let hasTier = false;
      if (makeFilter) {
        // Check if partner has selected tier for the filtered make
        const rank = partnerTierData[makeFilter];
        if (rank && selectedTiers.includes(rank)) {
          hasTier = true;
        }
      } else {
        // Check if partner has selected tier for ANY make
        const ranks = Object.values(partnerTierData);
        if (ranks.some(rank => selectedTiers.includes(rank))) {
          hasTier = true;
        }
      }
      if (!hasTier) return false;
    }

    // Activity filter
    const hasActivityThisMonth = partner.activities.some(a => activityOverlapsMonth(a));
    if (activityFilter === 'with-activity' && !hasActivityThisMonth) return false;
    if (activityFilter === 'no-activity' && hasActivityThisMonth) return false;

    // Other filters
    if (partnerFilter && !partner.partner_name.toLowerCase().includes(partnerFilter.toLowerCase())) return false;

    // Make filter - behavior depends on Activity filter
    if (makeFilter) {
      if (activityFilter === 'all') {
        // Show ALL partners approved for this make (check tier data)
        const partnerTierData = partnerTiers[partner.person_id];
        const isApprovedForMake = partnerTierData && partnerTierData[makeFilter];
        if (!isApprovedForMake) return false;
      } else {
        // Show only partners with activities of this make
        const hasMake = partner.activities.some(a => a.make === makeFilter);
        if (!hasMake) return false;
      }
    }
    if (vinFilter) {
      const hasVin = partner.activities.some(a =>
        a.vin?.toLowerCase().includes(vinFilter.toLowerCase())
      );
      if (!hasVin) return false;
    }
    return true;
  });

  // Apply sorting to vehicle view
  const sortedVins = [...filteredVins].sort((a, b) => {
    let compareA, compareB;

    switch (sortBy) {
      case 'make':
        compareA = a.make || '';
        compareB = b.make || '';
        break;
      case 'model':
        compareA = a.model || '';
        compareB = b.model || '';
        break;
      case 'vin':
        compareA = a.vin || '';
        compareB = b.vin || '';
        break;
      default:
        compareA = a.make || '';
        compareB = b.make || '';
    }

    const comparison = compareA.localeCompare(compareB);
    return sortOrder === 'asc' ? comparison : -comparison;
  });

  // Choose which data to display based on view mode
  const displayData = viewMode === 'vehicle' ? sortedVins : filteredPartners;

  // Get unique makes for filter
  const uniqueMakes = [...new Set(activities.map(a => a.make).filter(Boolean))].sort();

  // Fetch vehicle context
  const fetchVehicleContext = async (vin) => {
    if (vehicleContext && vehicleContext.vin === vin) return;

    setLoadingVehicleContext(true);
    try {
      const response = await fetch(`http://localhost:8081/api/ui/phase7/vehicle-context/${vin}`);
      if (!response.ok) throw new Error('Failed to fetch vehicle context');
      const data = await response.json();
      setVehicleContext(data);
    } catch (err) {
      console.error('Error fetching vehicle context:', err);
      setVehicleContext(null);
    } finally {
      setLoadingVehicleContext(false);
    }
  };

  const handleActivityClick = async (vin) => {
    setSelectedVin(vin);
    setLoadingVehicleContext(true);

    try {
      // Build context from calendar activities data
      const vehicleActivities = activities.filter(a => a.vin === vin);

      if (vehicleActivities.length > 0) {
        const firstActivity = vehicleActivities[0];
        const sortedActivities = [...vehicleActivities].sort((a, b) =>
          new Date(a.start_date) - new Date(b.start_date)
        );

        const now = new Date();
        const previous = sortedActivities.filter(a => new Date(a.end_date) < now).pop();
        const next = sortedActivities.find(a => new Date(a.start_date) > now);
        const current = sortedActivities.find(a => {
          const start = new Date(a.start_date);
          const end = new Date(a.end_date);
          return now >= start && now <= end;
        });

        // Try to get mileage from vehicles table
        let mileage = 'N/A';
        try {
          const vehicleResponse = await fetch(`http://localhost:8081/api/ui/phase7/vehicle-context/${vin}`);
          if (vehicleResponse.ok) {
            const vehicleData = await vehicleResponse.json();
            mileage = vehicleData.mileage || 'N/A';
          }
        } catch (err) {
          console.error('Could not fetch mileage:', err);
        }

        // Build context object with timeline
        const context = {
          vin: vin,
          make: firstActivity.make,
          model: firstActivity.model,
          office: firstActivity.office,
          mileage: mileage,
          last_known_location: current
            ? `With ${current.partner_name}`
            : previous
              ? `Last with ${previous.partner_name}`
              : 'Home Office',
          current_activity: current ? {
            activity_type: current.activity_type || 'Media Loan',
            start_date: current.start_date,
            end_date: current.end_date,
            partner_name: current.partner_name,
            status: current.status
          } : null,
          previous_activity: previous ? {
            activity_type: previous.activity_type || 'Media Loan',
            start_date: previous.start_date,
            end_date: previous.end_date,
            partner_name: previous.partner_name,
            status: previous.status
          } : null,
          next_activity: next ? {
            activity_type: next.activity_type || 'Planned Loan',
            start_date: next.start_date,
            end_date: next.end_date,
            partner_name: next.partner_name,
            status: next.status
          } : null,
          timeline: sortedActivities
        };

        setVehicleContext(context);

        // Fetch chaining opportunities if vehicle has current activity
        if (current && selectedOffice) {
          setLoadingChains(true);
          try {
            const params = new URLSearchParams({
              office: selectedOffice,
              max_distance: 50
            });
            const chainResponse = await fetch(`http://localhost:8081/api/ui/phase7/vehicle-chains/${vin}?${params}`);
            if (chainResponse.ok) {
              const chainData = await chainResponse.json();
              setChainingOpportunities(chainData);
            }
          } catch (err) {
            console.error('Failed to fetch chaining opportunities:', err);
            setChainingOpportunities(null);
          } finally {
            setLoadingChains(false);
          }
        } else {
          setChainingOpportunities(null);
        }
      } else {
        await fetchVehicleContext(vin);
      }
    } finally {
      setLoadingVehicleContext(false);
    }
  };

  const handlePartnerClick = async (partnerId, partnerName) => {
    setSelectedPartnerId(partnerId);
    setLoadingPartnerContext(true);

    try {
      // Get ALL activities for this partner - same data source as Gantt chart
      // Use == to handle string/number type mismatch
      const partnerActivities = activities.filter(a => a.person_id == partnerId);

      // Get partner info from allPartners list
      const partnerInfo = allPartners.find(p => p.person_id === partnerId);
      const partnerOffice = partnerInfo?.office || selectedOffice;

      if (partnerActivities.length > 0) {
        const sortedActivities = [...partnerActivities].sort((a, b) =>
          new Date(a.start_date) - new Date(b.start_date)
        );

        // Filter by status - matching Gantt chart colors exactly
        const currentLoans = sortedActivities.filter(a => a.status === 'active');
        const recommendedLoans = sortedActivities.filter(a => a.status === 'planned');

        const partnerAddress = partnerActivities[0].partner_address;
        const office = partnerActivities[0].office;

        // Fetch distance from office using cached lat/lon from media_partners
        let distanceInfo = null;
        try {
          const params = new URLSearchParams({
            person_id: partnerId,
            office: office
          });
          const distanceResponse = await fetch(`http://localhost:8081/api/ui/phase7/partner-distance?${params}`);
          if (distanceResponse.ok) {
            distanceInfo = await distanceResponse.json();
          }
        } catch (err) {
          console.error('Failed to fetch distance:', err);
        }

        // Fetch approved makes from partner-intelligence endpoint
        let approvedMakes = [];
        try {
          const intelligenceParams = new URLSearchParams({
            person_id: partnerId,
            office: office
          });
          const intelligenceResponse = await fetch(`http://localhost:8081/api/ui/phase7/partner-intelligence?${intelligenceParams}`);
          if (intelligenceResponse.ok) {
            const intelligenceData = await intelligenceResponse.json();
            approvedMakes = intelligenceData.approved_makes || [];
          }
        } catch (err) {
          console.error('Failed to fetch partner intelligence:', err);
        }

        // Build context object with timeline
        const context = {
          person_id: partnerId,
          partner_name: partnerName,
          office: office,
          region: partnerActivities[0].region || 'N/A',
          partner_address: partnerAddress || 'N/A',
          distance_info: distanceInfo,
          approved_makes: approvedMakes,
          current_loans: currentLoans.map(loan => ({
            vin: loan.vin,
            make: loan.make,
            model: loan.model,
            start_date: loan.start_date,
            end_date: loan.end_date,
            status: loan.status
          })),
          recommended_loans: recommendedLoans.map(loan => ({
            vin: loan.vin,
            make: loan.make,
            model: loan.model,
            start_date: loan.start_date,
            end_date: loan.end_date,
            status: loan.status
          })),
          timeline: sortedActivities
        };

        setPartnerContext(context);
      } else {
        // Partner has no activities - still show context with basic info
        let distanceInfo = partnerDistances[partnerId] || null;
        let approvedMakes = [];

        // Fetch approved makes
        try {
          const intelligenceParams = new URLSearchParams({
            person_id: partnerId,
            office: partnerOffice
          });
          const intelligenceResponse = await fetch(`http://localhost:8081/api/ui/phase7/partner-intelligence?${intelligenceParams}`);
          if (intelligenceResponse.ok) {
            const intelligenceData = await intelligenceResponse.json();
            approvedMakes = intelligenceData.approved_makes || [];
          }
        } catch (err) {
          console.error('Failed to fetch partner intelligence:', err);
        }

        const context = {
          person_id: partnerId,
          partner_name: partnerName,
          office: partnerOffice,
          region: 'N/A',
          partner_address: partnerInfo?.address || 'N/A',
          distance_info: distanceInfo,
          approved_makes: approvedMakes,
          current_loans: [],
          recommended_loans: [],
          timeline: []
        };

        setPartnerContext(context);
      }
    } catch (error) {
      console.error('Error in handlePartnerClick:', error);
      setPartnerContext(null);
    } finally {
      setLoadingPartnerContext(false);
    }
  };

  const closeSidePanel = () => {
    setSelectedVin(null);
    setVehicleContext(null);
    setSelectedPartnerId(null);
    setPartnerContext(null);
    setChainingOpportunities(null);
  };

  // Helper function for tier badge colors
  const getTierBadgeColor = (rank) => {
    // Handle both numeric (1,2,3,4) and letter-based (A, A+, B, C, D) ranks
    const normalizedRank = typeof rank === 'string' ? rank.toUpperCase().trim() : rank;

    // Check for A+ (premium tier) - GREEN background with DARK GREEN border
    if (normalizedRank === 'A+') {
      return 'bg-green-100 text-green-800 border-green-600'
    }

    // Check for A variants (A, etc) - GREEN (best tier)
    if (normalizedRank === 1 || normalizedRank === 'TA' || normalizedRank === 'A' ||
        (typeof normalizedRank === 'string' && normalizedRank.startsWith('A'))) {
      return 'bg-green-100 text-green-800 border-green-300'
    }

    switch(normalizedRank) {
      case 2:
      case 'TB':
      case 'B':
        return 'bg-blue-100 text-blue-800 border-blue-300'
      case 3:
      case 'TC':
      case 'C':
        return 'bg-yellow-100 text-yellow-800 border-yellow-300'
      case 4:
      case 'TD':
      case 'D':
        return 'bg-gray-100 text-gray-800 border-gray-300'
      default:
        return 'bg-gray-100 text-gray-800 border-gray-300'
    }
  };

  const formatActivityDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    const date = parseLocalDate(dateStr);
    if (!date || isNaN(date.getTime())) return 'Invalid Date';
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const formatFullDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    const date = parseLocalDate(dateStr);
    if (!date || isNaN(date.getTime())) return 'Invalid Date';
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const getActivityColor = (activity, locationColor) => {
    // Use location-based color if provided (for vehicle view)
    if (locationColor && viewMode === 'vehicle') {
      switch (locationColor) {
        case 'green': return 'bg-gradient-to-br from-green-500 to-green-600 border-2 border-green-700';
        case 'yellow': return 'bg-gradient-to-br from-yellow-400 to-yellow-500 border-2 border-yellow-600';
        case 'red': return 'bg-gradient-to-br from-red-500 to-red-600 border-2 border-red-700';
        case 'gray': return 'bg-gradient-to-br from-gray-400 to-gray-500 border-2 border-gray-600';
      }
    }

    // Default status-based colors
    switch (activity.status) {
      case 'completed': return 'bg-gradient-to-br from-gray-400 to-gray-500 border-2 border-gray-600';
      case 'active': return 'bg-gradient-to-br from-blue-500 to-blue-600 border-2 border-blue-700';
      case 'planned':
        // Optimizer AI: solid border
        return 'bg-gradient-to-br from-green-400 to-green-500 border-2 border-green-600';
      case 'manual':
        // Manual pick: dashed border to distinguish from optimizer
        return 'bg-gradient-to-br from-green-400 to-green-500 border-2 border-dashed border-green-600';
      case 'unavailable':
        // Lifecycle unavailability (not in service, turn-in, etc)
        return 'bg-gradient-to-br from-orange-400 to-orange-500 border-2 border-orange-600';
      default: return 'bg-gradient-to-br from-gray-300 to-gray-400 border-2 border-gray-500';
    }
  };

  const getActivityLabel = (status) => {
    switch (status) {
      case 'completed': return 'Past';
      case 'active': return 'Active';
      case 'planned': return 'Proposed (AI)';
      case 'manual': return 'Proposed (Manual)';
      default: return status;
    }
  };

  // Determine vehicle location based on activity
  const getVehicleLocation = (activity) => {
    // Get distance info if available
    const distanceInfo = partnerDistances[activity.person_id];

    // If active, vehicle is with the partner
    if (activity.status === 'active') {
      const locationType = distanceInfo?.location_type || 'unknown';
      const distance = distanceInfo?.distance_miles;

      if (locationType === 'local') {
        return {
          type: 'local',
          label: `🏠 Local (${distance || '?'} mi)`,
          badge: '🏠',
          color: null  // Don't override bar color, just show badge
        };
      } else if (locationType === 'remote') {
        return {
          type: 'remote',
          label: `✈️ Remote (${distance || '?'} mi)`,
          badge: '✈️',
          color: null  // Don't override bar color, just show badge
        };
      }
      return {
        type: 'partner',
        label: `📍 With ${activity.partner_name}`,
        badge: '📍',
        color: null  // Don't override bar color
      };
    }

    // If planned, vehicle will be picked up
    if (activity.status === 'planned') {
      const locationType = distanceInfo?.location_type || 'unknown';
      const distance = distanceInfo?.distance_miles;

      if (locationType === 'local') {
        return {
          type: 'local-planned',
          label: `📅 Local (${distance || '?'} mi)`,
          badge: '🏠',
          color: null  // Don't override bar color, just show badge
        };
      } else if (locationType === 'remote') {
        return {
          type: 'remote-planned',
          label: `📅 Remote (${distance || '?'} mi)`,
          badge: '✈️',
          color: null  // Don't override bar color, just show badge
        };
      }
      // If we don't have distance info, don't return a color - let it use default green for 'planned'
      return null;
    }

    // If completed, vehicle should be back at office
    if (activity.status === 'completed') {
      return {
        type: 'office',
        label: '🏢 At Office',
        badge: '🏢',
        color: null  // Don't override - completed should always be grey
      };
    }

    return null;
  };

  // Detect chaining opportunity (vehicle could go to next partner instead of returning to office)
  const detectChainingOpportunity = (activities, currentIdx) => {
    if (currentIdx >= activities.length - 1) return false;

    const current = activities[currentIdx];
    const next = activities[currentIdx + 1];

    // Check if current activity ends and next starts within 3 days (potential chain)
    const currentEnd = new Date(current.end_date);
    const nextStart = new Date(next.start_date);
    const daysDiff = (nextStart - currentEnd) / (1000 * 60 * 60 * 24);

    return daysDiff >= 0 && daysDiff <= 3 && current.status !== 'completed';
  };

  // Generate days in the current view range
  const getDaysInView = () => {
    if (!viewStartDate || !viewEndDate) return [];
    const days = [];
    const current = new Date(viewStartDate);
    const end = new Date(viewEndDate);

    while (current <= end) {
      days.push(new Date(current));
      current.setDate(current.getDate() + 1);
    }
    return days;
  };

  const daysInView = getDaysInView();

  // Calculate bar position and width for Gantt chart
  const getBarStyle = (activity) => {
    if (!viewStartDate || !viewEndDate) return { left: 0, width: 0 };

    const rangeStart = new Date(viewStartDate);
    const rangeEnd = new Date(viewEndDate);

    const activityStart = parseLocalDate(activity.start_date);
    const activityEnd = parseLocalDate(activity.end_date);

    // Clamp to view range boundaries
    const startDate = activityStart < rangeStart ? rangeStart : activityStart;
    const endDate = activityEnd > rangeEnd ? rangeEnd : activityEnd;

    // Calculate position as percentage based on days from range start
    const totalDays = daysInView.length;
    const startDayOffset = Math.floor((startDate - rangeStart) / (1000 * 60 * 60 * 24));
    const endDayOffset = Math.floor((endDate - rangeStart) / (1000 * 60 * 60 * 24));

    // Center bars on start/end dates (0.5 offset to bisect the day squares)
    const left = ((startDayOffset + 0.5) / totalDays) * 100;
    const width = ((endDayOffset - startDayOffset) / totalDays) * 100;

    return { left: `${left}%`, width: `${width}%` };
  };

  return (
    <div className="w-full min-h-screen bg-gray-50">
      {/* Header - Compact */}
      <div className="bg-white border-b px-6 py-2">
        <div className="flex justify-between items-center">
          <div className="flex items-baseline gap-2">
            <h1 className="!text-base font-semibold text-gray-900">📅 Calendar</h1>
            <p className="text-xs text-gray-500">Vehicle activity timeline</p>
          </div>

          {/* View Mode Toggle and What-If Mode */}
          <div className="flex gap-3 items-center">
            <div className="flex bg-gray-100 rounded-lg p-1">
              <button
                onClick={() => setViewMode('vehicle')}
                className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                  viewMode === 'vehicle'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                🚗 By Vehicle
              </button>
              <button
                onClick={() => setViewMode('partner')}
                className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                  viewMode === 'partner'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                👤 By Media Partner
              </button>
            </div>

            {/* What-If Mode Toggle */}
            <button
              onClick={() => {
                setWhatIfMode(!whatIfMode);
                if (whatIfMode) {
                  setScenarioChanges({});
                }
              }}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                whatIfMode
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {whatIfMode ? '✓ What-If Mode' : '🔄 What-If Mode'}
            </button>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="bg-white border-b px-6 py-2">
        <div className="flex gap-2 items-end">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Office</label>
            <select
              value={selectedOffice}
              onChange={(e) => setSelectedOffice(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-2 py-1.5 text-xs"
            >
              {offices.map(office => (
                <option key={office} value={office}>{office}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Month</label>
            <div className="flex gap-1">
              <button
                onClick={slideBackward}
                className="px-1.5 py-1.5 border border-gray-300 rounded-md hover:bg-gray-50 text-xs flex-shrink-0"
                title="Go back 7 days"
              >
                ←
              </button>
              <input
                type="month"
                value={selectedMonth}
                onChange={(e) => handleMonthChange(e.target.value)}
                className="w-28 border border-gray-300 rounded-md px-1 py-1.5 text-xs"
              />
              <button
                onClick={slideForward}
                className="px-1.5 py-1.5 border border-gray-300 rounded-md hover:bg-gray-50 text-xs flex-shrink-0"
                title="Go forward 7 days"
              >
                →
              </button>
            </div>
          </div>

          <div className="relative multi-select-dropdown">
            <label className="block text-xs font-medium text-gray-700 mb-1">Vehicles</label>
            <button
              onClick={() => setShowVehicleDropdown(!showVehicleDropdown)}
              className="w-full border border-gray-300 rounded-md px-2 py-1.5 text-xs text-left bg-white hover:bg-gray-50 flex justify-between items-center"
            >
              <span>{selectedVehicles.length > 0 ? `${selectedVehicles.length} selected` : 'All'}</span>
              <span>▼</span>
            </button>
            {showVehicleDropdown && (
              <div className="absolute z-50 mt-1 min-w-max bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-y-auto">
                <div className="p-2 border-b sticky top-0 bg-white">
                  <button
                    onClick={() => setSelectedVehicles([])}
                    className="text-xs text-blue-600 hover:text-blue-800"
                  >
                    Clear All
                  </button>
                </div>
                {allVehicles.map(vehicle => (
                  <label
                    key={vehicle.vin}
                    className="flex items-center px-2 py-1.5 hover:bg-gray-50 cursor-pointer text-xs whitespace-nowrap"
                  >
                    <input
                      type="checkbox"
                      checked={selectedVehicles.includes(vehicle.vin)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedVehicles([...selectedVehicles, vehicle.vin]);
                        } else {
                          setSelectedVehicles(selectedVehicles.filter(vin => vin !== vehicle.vin));
                        }
                      }}
                      className="mr-2"
                    />
                    <span>
                      {vehicle.make} {vehicle.model}
                      <span className="text-gray-500 ml-1">(...{vehicle.vin.slice(-5)})</span>
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Make</label>
            <select
              value={makeFilter}
              onChange={(e) => setMakeFilter(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-2 py-1.5 text-xs"
            >
              <option value="">All</option>
              {uniqueMakes.map(make => (
                <option key={make} value={make}>{make}</option>
              ))}
            </select>
          </div>

          <div className="relative multi-select-dropdown">
            <label className="block text-xs font-medium text-gray-700 mb-1">Tier</label>
            <button
              onClick={() => setShowTierDropdown(!showTierDropdown)}
              className="w-full border border-gray-300 rounded-md px-2 py-1.5 text-xs text-left bg-white hover:bg-gray-50 flex justify-between items-center"
            >
              <span>{selectedTiers.length > 0 ? `${selectedTiers.length} selected` : 'All'}</span>
              <span>▼</span>
            </button>
            {showTierDropdown && (
              <div className="absolute z-50 mt-1 w-40 bg-white border border-gray-300 rounded-md shadow-lg">
                <div className="p-2 border-b sticky top-0 bg-white">
                  <button
                    onClick={() => setSelectedTiers([])}
                    className="text-xs text-blue-600 hover:text-blue-800"
                  >
                    Clear All
                  </button>
                </div>
                {['A+', 'A', 'B', 'C'].map(tier => (
                  <label
                    key={tier}
                    className="flex items-center px-2 py-1.5 hover:bg-gray-50 cursor-pointer text-xs"
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
                      className="mr-2"
                    />
                    <span>{tier}</span>
                  </label>
                ))}
              </div>
            )}
          </div>

          <div className="relative multi-select-dropdown">
            <label className="block text-xs font-medium text-gray-700 mb-1">Partners</label>
            <button
              onClick={() => setShowPartnerDropdown(!showPartnerDropdown)}
              className="w-full border border-gray-300 rounded-md px-2 py-1.5 text-xs text-left bg-white hover:bg-gray-50 flex justify-between items-center"
            >
              <span>{selectedPartners.length > 0 ? `${selectedPartners.length} selected` : 'All'}</span>
              <span>▼</span>
            </button>
            {showPartnerDropdown && (
              <div className="absolute z-50 mt-1 w-80 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-y-auto">
                <div className="p-2 border-b sticky top-0 bg-white">
                  <button
                    onClick={() => setSelectedPartners([])}
                    className="text-xs text-blue-600 hover:text-blue-800"
                  >
                    Clear All
                  </button>
                </div>
                {allPartners.map(partner => (
                  <label
                    key={partner.person_id}
                    className="flex items-center px-2 py-1.5 hover:bg-gray-50 cursor-pointer text-xs"
                  >
                    <input
                      type="checkbox"
                      checked={selectedPartners.includes(partner.person_id)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedPartners([...selectedPartners, partner.person_id]);
                        } else {
                          setSelectedPartners(selectedPartners.filter(id => id !== partner.person_id));
                        }
                      }}
                      className="mr-2"
                    />
                    <span className="flex-1 truncate">{partner.name}</span>
                  </label>
                ))}
              </div>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Activity</label>
            <select
              value={activityFilter}
              onChange={(e) => setActivityFilter(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-2 py-1.5 text-xs"
            >
              <option value="all">All</option>
              <option value="with-activity">With</option>
              <option value="no-activity">None</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Sort</label>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-2 py-1.5 text-xs"
            >
              <option value="make">Make</option>
              <option value="model">Model</option>
              <option value="vin">VIN</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Order</label>
            <select
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-2 py-1.5 text-xs"
            >
              <option value="asc">A → Z</option>
              <option value="desc">Z → A</option>
            </select>
          </div>

          <div className="flex items-end">
            <button
              onClick={clearAllFilters}
              className="px-3 py-1.5 bg-red-50 border border-red-300 text-red-700 rounded-md hover:bg-red-100 text-xs font-medium"
            >
              Clear All
            </button>
          </div>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap gap-6 mt-4 text-sm">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-gray-400 rounded"></div>
            <span className="text-gray-600">Past</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-blue-500 rounded"></div>
            <span className="text-gray-600">Active</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-green-400 rounded border-2 border-green-600"></div>
            <span className="text-gray-600">🤖 Proposed (AI)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-green-400 rounded border-2 border-dashed border-green-600"></div>
            <span className="text-gray-600">Proposed (Manual)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-orange-400 rounded"></div>
            <span className="text-gray-600">Unavailable</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-lg">📍</span>
            <span className="text-gray-600">Current Location</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-lg">⛓️</span>
            <span className="text-gray-600">Chaining Opportunity</span>
          </div>
        </div>
      </div>

      {/* Gantt Chart Content */}
      <div className="p-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <svg className="animate-spin h-8 w-8 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          </div>
        ) : error ? (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
            Error: {error}
          </div>
        ) : displayData.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm border p-12 text-center">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <p className="mt-2 text-sm text-gray-500">No activity found</p>
            <p className="text-xs text-gray-400 mt-1">Try adjusting your filters or select a different month</p>
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow-sm border overflow-x-auto">
            {/* Gantt Chart Header */}
            <div className="flex border-b bg-gray-50">
              {/* Row label column */}
              <div className="w-64 flex-shrink-0 px-4 py-3 border-r font-medium text-sm text-gray-700">
                {viewMode === 'vehicle' ? 'Vehicle' : 'Media Partner'}
              </div>
              {/* Days column */}
              <div className="flex-1 flex">
                {daysInView.map((date, idx) => {
                  const dayOfWeek = date.getDay();
                  const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
                  const dayNum = date.getDate();
                  const monthName = date.toLocaleDateString('en-US', { month: 'short' });

                  return (
                    <div
                      key={idx}
                      className={`flex-1 text-center text-xs py-3 border-r ${
                        isWeekend ? 'bg-blue-100 text-blue-800 font-semibold' : 'text-gray-600'
                      }`}
                    >
                      <div>{monthName} {dayNum}</div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Gantt Chart Rows */}
            <div className="divide-y divide-gray-300">
              {displayData.map((item) => {
                // Calculate how many rows we need based on overlapping activities
                const filteredActs = item.activities.filter(activity => activityOverlapsMonth(activity));

                // Detect overlaps and assign row positions
                const activitiesWithRows = filteredActs.map((activity, idx) => {
                  // Check if this activity overlaps with any previous activity
                  let rowIndex = 0;
                  const actStart = parseLocalDate(activity.start_date);
                  const actEnd = parseLocalDate(activity.end_date);

                  for (let i = 0; i < idx; i++) {
                    const prevAct = filteredActs[i];
                    const prevStart = parseLocalDate(prevAct.start_date);
                    const prevEnd = parseLocalDate(prevAct.end_date);

                    // Check if dates overlap
                    if (actStart <= prevEnd && actEnd >= prevStart) {
                      rowIndex = Math.max(rowIndex, (filteredActs[i].rowIndex || 0) + 1);
                    }
                  }

                  activity.rowIndex = rowIndex;
                  return activity;
                });

                const maxRows = Math.max(1, ...activitiesWithRows.map(a => (a.rowIndex || 0) + 1));
                const rowHeight = maxRows * 32; // 32px per row (h-8)
                const totalHeight = rowHeight + 40; // Add padding

                return (
                <div key={viewMode === 'vehicle' ? item.vin : item.person_id} className="flex hover:bg-gray-50" style={{ minHeight: `${totalHeight}px` }}>
                  {/* Row info */}
                  <div className="w-64 flex-shrink-0 px-4 py-3 border-r flex items-start min-h-full">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        if (viewMode === 'vehicle') {
                          handleActivityClick(item.vin);
                        } else {
                          handlePartnerClick(item.person_id, item.partner_name);
                        }
                      }}
                      className="text-left w-full group"
                    >
                      {viewMode === 'vehicle' ? (
                        <div className="w-full">
                          <h3 className="font-semibold text-sm text-gray-900 group-hover:text-blue-600">
                            {item.make} {item.model}
                          </h3>
                          <p className="text-xs text-gray-500 font-mono">{item.vin}</p>
                          {item.expected_turn_in_date && (
                            <p className="text-xs text-orange-600 mt-1">
                              Expected Turn-In: {formatFullDate(item.expected_turn_in_date)}
                            </p>
                          )}
                        </div>
                      ) : (
                        <>
                          <h3 className="font-semibold text-sm text-gray-900 group-hover:text-blue-600">
                            {item.partner_name}
                          </h3>
                          <p className="text-xs text-gray-500">ID: {item.person_id}</p>
                          {partnerDistances[item.person_id] && (
                            <div className="flex items-center gap-1 mt-1">
                              <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${
                                partnerDistances[item.person_id].location_type === 'local'
                                  ? 'bg-green-100 text-green-800'
                                  : 'bg-amber-100 text-amber-800'
                              }`}>
                                {partnerDistances[item.person_id].location_type === 'local' ? '🏠' : '✈️'}
                              </span>
                              <span className="text-xs text-gray-600">
                                {partnerDistances[item.person_id].distance_miles} mi
                              </span>
                            </div>
                          )}
                        </>
                      )}
                    </button>
                  </div>

                  {/* Timeline bars */}
                  <div className="flex-1 relative">
                    {/* Day grid with weekend backgrounds */}
                    <div className="absolute inset-0 flex">
                      {daysInView.map((date, idx) => {
                        const dayOfWeek = date.getDay();
                        const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;

                        return (
                          <div
                            key={idx}
                            className={`flex-1 border-r border-gray-300 ${
                              isWeekend ? 'bg-blue-50' : ''
                            }`}
                          ></div>
                        );
                      })}
                    </div>

                    {/* Activity bars */}
                    {activitiesWithRows.map((activity, idx) => {
                        const barStyle = getBarStyle(activity);
                        const label = viewMode === 'vehicle' ? activity.partner_name : `${activity.make} ${activity.model}`;
                        const vinSuffix = activity.vin ? activity.vin.slice(-6) : '';
                        const location = getVehicleLocation(activity);
                        const hasChaining = viewMode === 'vehicle' && detectChainingOpportunity(item.activities, item.activities.indexOf(activity));
                        const topOffset = 16 + (activity.rowIndex * 32); // Start at 16px from top, then 32px per row

                        const color = getActivityColor(activity, location?.color);

                        return (
                          <button
                            key={idx}
                            onClick={(e) => {
                              e.stopPropagation();
                              if (viewMode === 'vehicle') {
                                handleActivityClick(item.vin);
                              } else {
                                handlePartnerClick(item.person_id, item.partner_name);
                              }
                            }}
                            className={`absolute h-7 ${color} ${hasChaining ? 'ring-2 ring-yellow-400 ring-offset-1' : ''} rounded-lg shadow-lg hover:shadow-xl hover:scale-105 hover:z-10 transition-all cursor-pointer flex items-center gap-1 text-white text-xs font-semibold px-2 overflow-hidden`}
                            style={{ left: barStyle.left, width: barStyle.width, minWidth: '20px', top: `${topOffset}px` }}
                            title={`${label}\nVIN: ...${vinSuffix}\n${formatActivityDate(activity.start_date)} - ${formatActivityDate(activity.end_date)}\n${location ? location.label : ''}${hasChaining ? '\n⛓️ Chaining opportunity!' : ''}`}
                          >
                            {activity.status === 'planned' && <span className="text-xs">🤖</span>}
                            {location?.badge && <span className="text-sm">{location.badge}</span>}
                            {hasChaining && <span>⛓️</span>}
                            <span className="truncate">{label}</span>
                          </button>
                        );
                      })}
                  </div>
                </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Vehicle Context Side Panel (reuse from Optimizer) */}
      {selectedVin && (
        <div className="fixed right-0 top-0 z-40 h-full">
          <div className="bg-white w-96 h-full shadow-2xl overflow-y-auto border-l border-gray-200">
            <div className="sticky top-0 bg-white border-b px-6 py-4 flex justify-between items-center">
              <h2 className="text-lg font-semibold text-gray-900">Vehicle Context</h2>
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
              {loadingVehicleContext ? (
                <div className="flex items-center justify-center py-12">
                  <svg className="animate-spin h-8 w-8 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                </div>
              ) : vehicleContext ? (
                <div className="space-y-6">
                  {/* Vehicle Info */}
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">Vehicle Details</h3>
                    <div className="bg-gray-50 rounded-lg p-4 space-y-2">
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">VIN:</span>
                        <span className="text-sm font-mono font-medium text-gray-900">{vehicleContext.vin}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">Make:</span>
                        <span className="text-sm font-medium text-gray-900">{vehicleContext.make}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">Model:</span>
                        <span className="text-sm font-medium text-gray-900">{vehicleContext.model}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">Office:</span>
                        <span className="text-sm font-medium text-gray-900">{vehicleContext.office}</span>
                      </div>
                      <div className="flex justify-between">
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

                  {/* Current Activity */}
                  {vehicleContext.current_activity && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">Current Activity</h3>
                      <div className="bg-blue-50 border-2 border-blue-400 rounded-lg p-4">
                        <div className="flex items-start">
                          <svg className="w-5 h-5 text-blue-600 mt-0.5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
                          </svg>
                          <div className="flex-1">
                            <p className="text-sm font-medium text-blue-900">📍 {vehicleContext.current_activity.partner_name}</p>
                            <p className="text-xs text-blue-700 mt-1">
                              {formatActivityDate(vehicleContext.current_activity.start_date)} - {formatActivityDate(vehicleContext.current_activity.end_date)}
                            </p>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Previous Activity */}
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">Previous Activity</h3>
                    {vehicleContext.previous_activity ? (
                      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                        <div className="flex items-start">
                          <svg className="w-5 h-5 text-gray-600 mt-0.5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
                          </svg>
                          <div className="flex-1">
                            <p className="text-sm font-medium text-gray-900">{vehicleContext.previous_activity.partner_name}</p>
                            <p className="text-xs text-gray-600 mt-1">
                              {formatActivityDate(vehicleContext.previous_activity.start_date)} - {formatActivityDate(vehicleContext.previous_activity.end_date)}
                            </p>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-500 text-center">
                        No previous activity
                      </div>
                    )}
                  </div>

                  {/* Next Activity */}
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">Next Activity</h3>
                    {vehicleContext.next_activity ? (
                      <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                        <div className="flex items-start">
                          <svg className="w-5 h-5 text-green-600 mt-0.5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
                          </svg>
                          <div className="flex-1">
                            <p className="text-sm font-medium text-green-900">{vehicleContext.next_activity.partner_name}</p>
                            <p className="text-xs text-green-700 mt-1">
                              {formatActivityDate(vehicleContext.next_activity.start_date)} - {formatActivityDate(vehicleContext.next_activity.end_date)}
                            </p>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-500 text-center">
                        No upcoming activity
                      </div>
                    )}
                  </div>

                  {/* Activity Timeline */}
                  {vehicleContext.timeline && vehicleContext.timeline.length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">Activity Timeline</h3>
                      <div className="bg-gray-50 rounded-lg p-4">
                        <div className="space-y-2">
                          {vehicleContext.timeline.map((activity, idx) => {
                            const isCurrent = vehicleContext.current_activity && activity.start_date === vehicleContext.current_activity.start_date;
                            return (
                              <div key={idx} className={`flex items-center text-sm ${isCurrent ? 'font-medium text-blue-900' : 'text-gray-700'}`}>
                                <div className={`w-2 h-2 rounded-full mr-2 flex-shrink-0 ${
                                  activity.status === 'completed' ? 'bg-gray-400' :
                                  activity.status === 'active' ? 'bg-blue-500' :
                                  'bg-green-400'
                                }`}></div>
                                <div className="flex-1 min-w-0">
                                  <p className="truncate">{activity.partner_name}</p>
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

                  {/* Next Best Chains */}
                  {vehicleContext.current_activity && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-2">
                        ⛓️ Next Best Chains
                        <span className="text-xs font-normal text-gray-400">(within 50 mi)</span>
                      </h3>
                      {loadingChains ? (
                        <div className="flex items-center justify-center py-8">
                          <svg className="animate-spin h-6 w-6 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                        </div>
                      ) : chainingOpportunities?.success && chainingOpportunities.nearby_partners?.length > 0 ? (
                        <div className="bg-gradient-to-br from-yellow-50 to-amber-50 border border-yellow-200 rounded-lg p-4">
                          <div className="mb-3">
                            <p className="text-xs text-gray-600 mb-1">
                              Currently with: <span className="font-medium text-gray-900">{chainingOpportunities.current_partner.name}</span>
                            </p>
                            <p className="text-xs text-gray-500">
                              Nearby partners approved for <span className="font-medium">{chainingOpportunities.vehicle_make}</span>:
                            </p>
                          </div>
                          <div className="space-y-2">
                            {chainingOpportunities.nearby_partners.map((partner, idx) => (
                              <div key={idx} className="bg-white rounded-lg p-3 shadow-sm border border-yellow-200 hover:border-yellow-400 transition-colors">
                                <div className="flex items-start justify-between">
                                  <div className="flex-1 min-w-0">
                                    <p className="text-sm font-medium text-gray-900 truncate">{partner.name}</p>
                                    <p className="text-xs text-gray-500 mt-0.5">{partner.region || 'N/A'}</p>
                                    {partner.address && (
                                      <p className="text-xs text-gray-400 mt-1 truncate">{partner.address}</p>
                                    )}
                                  </div>
                                  <div className="ml-3 flex-shrink-0 text-right">
                                    <p className="text-sm font-semibold text-yellow-700">{partner.distance_miles} mi</p>
                                    <p className="text-xs text-gray-500">away</p>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                          <div className="mt-3 pt-3 border-t border-yellow-200">
                            <p className="text-xs text-gray-500 italic">
                              💡 Tip: Chain this vehicle to a nearby partner to reduce deadhead miles
                            </p>
                          </div>
                        </div>
                      ) : chainingOpportunities?.success && chainingOpportunities.nearby_partners?.length === 0 ? (
                        <div className="bg-gray-50 rounded-lg p-4 text-center">
                          <p className="text-sm text-gray-500">No nearby partners within 50 miles</p>
                          <p className="text-xs text-gray-400 mt-1">approved for {chainingOpportunities.vehicle_make}</p>
                        </div>
                      ) : !chainingOpportunities?.success && chainingOpportunities?.message ? (
                        <div className="bg-gray-50 rounded-lg p-4 text-center">
                          <p className="text-sm text-gray-500">{chainingOpportunities.message}</p>
                        </div>
                      ) : (
                        <div className="bg-gray-50 rounded-lg p-4 text-center">
                          <p className="text-sm text-gray-500">Chaining opportunities unavailable</p>
                          <p className="text-xs text-gray-400 mt-1">Vehicle must have active loan to calculate chains</p>
                        </div>
                      )}
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

      {/* Media Partner Context Side Panel */}
      {selectedPartnerId && (
        <div className="fixed right-0 top-0 z-40 h-full">
          <div className="bg-white w-96 h-full shadow-2xl overflow-y-auto border-l border-gray-200">
            <div className="sticky top-0 bg-white border-b px-6 py-4 flex justify-between items-center">
              <h2 className="text-lg font-semibold text-gray-900">Media Partner Context</h2>
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
              ) : partnerContext ? (
                <div className="space-y-6">
                  {/* Media Partner Info */}
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">Media Partner Details</h3>
                    <div className="bg-gray-50 rounded-lg p-4 space-y-2">
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">Name:</span>
                        <span className="text-sm font-medium text-gray-900">{partnerContext.partner_name}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">Media ID:</span>
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
                      {partnerContext.distance_info && partnerContext.distance_info.success && (
                        <div className="flex justify-between items-center border-t pt-2 mt-2">
                          <span className="text-sm text-gray-600">Distance:</span>
                          <div className="flex items-center gap-2">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                              partnerContext.distance_info.location_type === 'local'
                                ? 'bg-green-100 text-green-800'
                                : 'bg-amber-100 text-amber-800'
                            }`}>
                              {partnerContext.distance_info.location_type === 'local' ? '🏠 Local' : '✈️ Remote'}
                            </span>
                            <span className="text-sm font-medium text-gray-900">
                              {partnerContext.distance_info.distance_miles} mi
                            </span>
                          </div>
                        </div>
                      )}
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

                  {/* Approved Makes */}
                  {partnerContext.approved_makes && partnerContext.approved_makes.length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">Approved Makes</h3>
                      <div className="bg-gray-50 rounded-lg p-4">
                        <div className="flex flex-wrap gap-2">
                          {partnerContext.approved_makes.map((item) => (
                            <span
                              key={item.make}
                              className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium border ${getTierBadgeColor(item.rank)}`}
                            >
                              {item.make}
                              <span className="ml-1.5 text-xs">{item.rank}</span>
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

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
              ) : (
                <div className="text-center py-12 text-gray-500">
                  <p>Unable to load media partner context</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Calendar;
