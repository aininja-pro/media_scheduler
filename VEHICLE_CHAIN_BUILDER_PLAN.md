
How to Use This Document

  When starting new conversations:
  1. Reference this file: /Users/richardrierson/Desktop/Projects/media_scheduler/VEHICLE_CHAIN_BUILDER_PLAN.md
  2. Say: "Continue implementing Vehicle Chain Builder per VEHICLE_CHAIN_BUILDER_PLAN.md, starting at Chunk X.Y"
  3. The plan has all context needed to pick up where we left off

  During implementation:
  - Follow chunks sequentially (1.1 → 1.2 → 2.1 → ...)
  - Each chunk is independent and committable
  - Test partner chain mode after each commit (regression check)
  - Update "Changelog" section at end of document as you complete phases


# Vehicle Chain Builder - Implementation Plan

**Date Created:** 2025-10-29
**Status:** Planning Complete - Ready for Implementation
**Feature:** Add Vehicle-Centric Chain Building to existing Partner-Centric Chain Builder

---

## Table of Contents

1. [Overview](#overview)
2. [Core Concept](#core-concept)
3. [Key Differences from Partner Chains](#key-differences-from-partner-chains)
4. [Business Rules](#business-rules)
5. [Technical Architecture](#technical-architecture)
6. [Implementation Plan - 8 Phases](#implementation-plan---8-phases)
7. [OR-Tools Optimization Strategy](#or-tools-optimization-strategy)
8. [API Specifications](#api-specifications)
9. [UI/UX Design](#uiux-design)
10. [Testing Strategy](#testing-strategy)
11. [Rollback Strategy](#rollback-strategy)

---

## Overview

### Current State
- **Chain Builder** exists for creating sequential vehicle chains for a single Media Partner
- Users can auto-generate or manually build 4-6 vehicle assignments
- Partner-centric: Pick 1 partner → get N vehicles

### New Feature
- Add **Vehicle Chain** mode to the same UI
- Vehicle-centric: Pick 1 vehicle → get N partners
- Same dual build modes (auto-generate + manual)
- Same edit capabilities
- **Critical addition:** Geographic optimization for same-day handoffs

---

## Core Concept

### Partner Chain (Current)
**Input:** 1 Media Partner
**Output:** Sequential chain of 4-6 vehicles
**Optimization:** Vehicle quality, tier preferences, availability
**Logistics:** Vehicles delivered to partner's location (distance irrelevant)

### Vehicle Chain (New)
**Input:** 1 Vehicle (VIN)
**Output:** Sequential chain of 4-6 media partners
**Optimization:** Partner quality + geographic proximity
**Logistics:** **SAME-DAY HANDOFFS** - Vehicle driven from Partner A → Partner B on transition date

### Critical Distinction: Same-Day Handoffs

```
Timeline Example (8-day loans, 3 partners):

Partner A (LA Times):    [Nov 3 ========== Nov 11]
                                           ↓ (Same-day handoff)
Partner B (KTLA):                     [Nov 11 ========== Nov 19]
                                                         ↓ (Same-day handoff)
Partner C (Daily News):                             [Nov 19 ========== Nov 27]

Nov 11: Partner A returns vehicle at LA Times (morning)
        Vehicle driven 3.2 miles to KTLA (midday)
        Partner B picks up at KTLA (afternoon)

Nov 19: Partner B returns at KTLA (morning)
        Vehicle driven 2.8 miles to Daily News (midday)
        Partner C picks up at Daily News (afternoon)
```

**Why Geographic Optimization is Critical:**
- Vehicle physically travels between partner locations
- Staff must coordinate same-day pickup/dropoff
- Distance = operational cost + time + logistics complexity
- Long distances (>50 miles) may be infeasible for same-day handoff

---

## Key Differences from Partner Chains

| Aspect | Partner Chain | Vehicle Chain |
|--------|---------------|---------------|
| **Primary Input** | Media Partner | Vehicle (VIN) |
| **Output Items** | Vehicles (4-6) | Partners (4-6) |
| **Calendar Source** | Partner's busy periods | Vehicle's rental periods |
| **Exclusions** | Partners who reviewed vehicle | Vehicles partner has reviewed |
| **Geographic Factor** | N/A (delivery irrelevant) | **CRITICAL** - minimize travel distance |
| **Availability Check** | Vehicle in-service dates | Partner availability windows |
| **Scoring Priority** | Vehicle tier/quality | Partner quality + proximity |
| **Optimization Goal** | Maximize partner satisfaction | Minimize logistics cost + maximize quality |
| **Default Distance Weight** | N/A | 70% (distance matters more) |

---

## Business Rules

### Hard Constraints

1. **8-Day Default Loan Duration** (not 7)
   - Client requirement to avoid weekend handoffs
   - Most loans are exactly 8 days
   - Some extended to 9-10 days due to weekend rule

2. **Weekend Extension Rule**
   - If loan end date falls on Saturday → extend to Monday (+2 days)
   - If loan end date falls on Sunday → extend to Monday (+1 day)
   - **All handoffs must occur on weekdays (Mon-Fri)**

3. **Same-Day Handoff**
   - Next partner pickup date = Previous partner dropoff date (exact same day)
   - No gap between sequential loans
   - Vehicle never sits idle between partners

4. **Weekday Start Dates Only**
   - Chain start date must be Mon-Fri
   - Reject Saturday/Sunday starts with validation error

5. **Maximum Distance Per Hop**
   - Default: 50 miles between consecutive partners
   - Hard constraint (infeasible if exceeded)
   - Ensures same-day handoff is operationally feasible

6. **Partner Exclusions**
   - Never suggest partner who has previously reviewed this vehicle
   - Permanent exclusion (not time-based)
   - Based on `loan_history` table

7. **Sequential Uniqueness**
   - Each partner used at most once in chain
   - No duplicate partners

8. **Availability**
   - Partner must be free (no active loans, no scheduled assignments) during entire slot period
   - Vehicle must not be rented during slot period

### Soft Objectives (OR-Tools Weighted)

1. **Minimize Total Travel Distance**
   - Sum of miles between consecutive partners
   - Operational cost = distance × $2/mile (configurable)
   - Default weight: 70%

2. **Maximize Partner Quality**
   - Base score: engagement level + publication rate + tier preference
   - Default weight: 30%

3. **Prefer Geographically Clustered Partners**
   - Traveling Salesman Problem (TSP) optimization
   - Balance quality vs proximity

---

## Technical Architecture

### UI Structure - Two-Tab Design

```
┌─────────────────────────────────────────────────────┐
│  [ Partner Chain ]  [ Vehicle Chain ]  ← Tabs       │
├─────────────────────────────────────────────────────┤
│  Left Panel   │   Center Timeline   │  Right Panel  │
│  (Parameters) │   (Visualization)   │  (Info)       │
└─────────────────────────────────────────────────────┘
```

**Shared Components:**
- Timeline calendar visualization
- Save/delete functionality
- Budget calculations
- Session storage persistence
- Build mode toggle (auto vs manual)
- Status selection (manual vs requested)

**New Components:**
- Vehicle selector dropdown (VIN search)
- Partner slot cards (with distance display)
- Logistics summary panel (total distance, drive time, costs)
- Distance weight slider (0-100%)
- Max distance per hop input

### State Management

**New State Variables (Vehicle Chain Mode):**
```javascript
const [chainMode, setChainMode] = useState('partner'); // 'partner' | 'vehicle'
const [selectedVehicle, setSelectedVehicle] = useState(null);
const [vehicleChainBuildMode, setVehicleChainBuildMode] = useState('auto'); // 'auto' | 'manual'
const [vehicleChain, setVehicleChain] = useState(null); // Auto-generated chain
const [manualPartnerSlots, setManualPartnerSlots] = useState([]); // Manual mode slots
const [distanceWeight, setDistanceWeight] = useState(0.7); // 0.0-1.0
const [maxDistancePerHop, setMaxDistancePerHop] = useState(50); // miles
const [daysPerLoanVehicle, setDaysPerLoanVehicle] = useState(8); // Default 8 days
```

**Session Storage Keys (Vehicle Mode):**
- `chainbuilder_chain_mode` ('partner' | 'vehicle')
- `chainbuilder_vehicle_vin`
- `chainbuilder_vehicle_make_model`
- `chainbuilder_vehicle_chain_mode` ('auto' | 'manual')
- `chainbuilder_manual_partner_slots` (JSON)
- `chainbuilder_distance_weight`
- `chainbuilder_max_distance_per_hop`

### Backend Architecture

**New Modules:**
```
backend/app/chain_builder/
  ├── vehicle_exclusions.py      (NEW - partners who reviewed vehicle)
  ├── geography.py                (NEW - distance calculations, scoring)
  └── exclusions.py               (EXISTING - vehicles reviewed by partner)

backend/app/solver/
  ├── vehicle_chain_solver.py    (NEW - OR-Tools CP-SAT for partner sequencing)
  ├── ortools_solver_v6.py        (EXISTING - main optimizer)
  └── scoring.py                  (EXISTING - shared scoring logic)
```

**New API Endpoints:**
```
GET  /api/chain-builder/search-vehicles              (Search VINs by office/make/model)
GET  /api/chain-builder/vehicle-busy-periods         (Get vehicle's rental history)
POST /api/chain-builder/suggest-vehicle-chain        (Auto-generate optimal partner chain)
GET  /api/chain-builder/get-partner-slot-options     (Manual mode: get partners for slot)
POST /api/chain-builder/save-vehicle-chain           (Save chain to scheduled_assignments)
GET  /api/chain-builder/vehicle-intelligence         (Vehicle current status, history)
POST /api/chain-builder/calculate-chain-budget       (EXISTING - reuse for vehicle chains)
```

---

## Implementation Plan - 8 Phases

### Phase 1: UI Foundation (No Backend Changes)

#### Chunk 1.1: Add Tab Switching ✅
**Files Modified:**
- `frontend/src/pages/ChainBuilder.jsx`

**Changes:**
- Add state: `chainMode` ('partner' | 'vehicle')
- Add tab buttons at top of page
- Conditionally render existing UI based on `chainMode`
- Session storage: save/restore selected tab
- No visual changes to partner chain mode (regression test)

**Testing:**
- ✅ Can toggle between tabs
- ✅ Partner chain mode works exactly as before
- ✅ Tab selection persists on page refresh

**Commit Message:**
`"Add Partner/Vehicle chain mode tabs to Chain Builder UI"`

---

#### Chunk 1.2: Vehicle Selector UI ✅
**Files Modified:**
- `frontend/src/pages/ChainBuilder.jsx`

**Changes:**
- Add vehicle search/autocomplete dropdown (similar to partner selector)
- VIN search with typeahead
- Display: VIN + Make + Model + Year
- Filter by office (same as current office selector)
- Only shows when `chainMode === 'vehicle'`
- No API integration yet (mock data for UI testing)

**Testing:**
- ✅ Vehicle selector appears in vehicle mode
- ✅ Selector hidden in partner mode
- ✅ Autocomplete interaction works

**Commit Message:**
`"Add vehicle selector UI for vehicle-centric chain mode"`

---

### Phase 2: Backend Data Endpoints

#### Chunk 2.1: Vehicle Search Endpoint ✅
**Files Created:**
- None (add route to existing `backend/app/routers/chain_builder.py`)

**New Route:**
```python
@router.get("/search-vehicles")
async def search_vehicles(
    office: str,
    search_term: str = "",  # VIN, make, or model
    limit: int = 50
):
    """
    Search vehicles by VIN, make, or model within an office.
    Returns list of vehicles for autocomplete dropdown.
    """
```

**Logic:**
1. Query `vehicles` table filtered by office
2. Search `vin`, `make`, `model` fields (ILIKE for partial match)
3. Return up to 50 results sorted by make, model

**Response:**
```json
{
  "vehicles": [
    {
      "vin": "1HGBH41JXMN109186",
      "make": "Honda",
      "model": "Accord",
      "year": "2023",
      "trim": "EX-L",
      "office": "Los Angeles",
      "in_service_date": "2024-01-15",
      "tier": "A+"
    }
  ]
}
```

**Testing:**
- ✅ Search by VIN returns correct vehicle
- ✅ Search by make returns all matching vehicles
- ✅ Office filter works correctly
- ✅ Limit enforced

**Commit Message:**
`"Add vehicle search endpoint for Chain Builder"`

---

#### Chunk 2.2: Vehicle Calendar Data ✅
**Files Modified:**
- `backend/app/routers/chain_builder.py`

**New Route:**
```python
@router.get("/vehicle-busy-periods")
async def get_vehicle_busy_periods(
    vin: str,
    start_date: str,  # YYYY-MM-DD
    end_date: str     # YYYY-MM-DD
):
    """
    Get vehicle's current and scheduled rental periods.
    Used to find gaps in vehicle's calendar for chain scheduling.
    """
```

**Logic:**
1. Query `current_activity` for active loans with this VIN
2. Query `scheduled_assignments` for upcoming assignments with this VIN
3. Return list of (start_date, end_date) tuples

**Response:**
```json
{
  "vin": "1HGBH41JXMN109186",
  "busy_periods": [
    {
      "start_date": "2025-10-15",
      "end_date": "2025-10-22",
      "partner_name": "LA Times",
      "status": "active"
    },
    {
      "start_date": "2025-11-01",
      "end_date": "2025-11-08",
      "partner_name": "KTLA",
      "status": "scheduled"
    }
  ]
}
```

**Testing:**
- ✅ Returns current active loans
- ✅ Returns scheduled assignments
- ✅ Date range filtering works

**Commit Message:**
`"Add vehicle busy periods endpoint for calendar data"`

---

### Phase 3: Partner Eligibility & Geography

#### Chunk 3.1: Partner Exclusion Logic ✅
**Files Created:**
- `backend/app/chain_builder/vehicle_exclusions.py`

**New Functions:**
```python
def get_partners_not_reviewed(
    vin: str,
    office: str,
    loan_history_df: pd.DataFrame,
    partners_df: pd.DataFrame
) -> Dict:
    """
    Returns partners who have NOT previously reviewed this vehicle.
    Permanent exclusion (not time-based).
    """
```

**Logic:**
1. Filter `loan_history` for this VIN
2. Get all `person_id` values (partners who reviewed)
3. Get all partners in office from `media_partners`
4. Return eligible partners (not in reviewed list)

**Returns:**
```python
{
    "eligible_partners": [partner_id, ...],
    "excluded_partners": [partner_id, ...],
    "exclusion_details": {
        partner_id: {
            "name": "LA Times",
            "last_loan_date": "2024-03-15",
            "reason": "Previously reviewed this vehicle"
        }
    }
}
```

**Testing:**
- ✅ Partner who reviewed vehicle is excluded
- ✅ New partners (never reviewed) are eligible
- ✅ Office filtering works

**Commit Message:**
`"Add partner exclusion logic for vehicle chains"`

---

#### Chunk 3.2: Geographic Distance Calculator ✅
**Files Created:**
- `backend/app/chain_builder/geography.py`

**New Functions:**
```python
def calculate_distance_matrix(
    partners_df: pd.DataFrame
) -> Dict[Tuple[int, int], float]:
    """
    Calculate pairwise distances between all partners using Haversine formula.
    Returns distance matrix: {(partner_id_1, partner_id_2): miles}
    """

def calculate_partner_distances(
    partner_id: int,
    all_partners_df: pd.DataFrame
) -> Dict[int, float]:
    """
    Calculate distances from one partner to all others.
    Returns {partner_id: miles}
    """

def haversine_distance(
    lat1: float, lng1: float,
    lat2: float, lng2: float
) -> float:
    """
    Calculate great-circle distance between two points in miles.
    """
```

**Logic:**
- Use Haversine formula for lat/lng → miles conversion
- Cache distance matrix for performance
- Handle missing lat/lng gracefully (return infinity or exclude)

**Testing:**
- ✅ Haversine formula accurate (test known distances)
- ✅ Symmetric: distance(A→B) == distance(B→A)
- ✅ Handles missing coordinates

**Commit Message:**
`"Add geographic distance calculation utilities"`

---

### Phase 4: Core Vehicle Chain Algorithm

#### Chunk 4.1: Partner Availability Grid ✅
**Files Modified:**
- `backend/app/chain_builder/availability.py`

**New Function:**
```python
def build_partner_availability_grid(
    partners_df: pd.DataFrame,
    current_activity_df: pd.DataFrame,
    scheduled_assignments_df: pd.DataFrame,
    start_date: datetime.date,
    end_date: datetime.date,
    office: str
) -> pd.DataFrame:
    """
    Create day-by-day availability matrix for partners.
    Similar to vehicle availability grid but for partners.

    Returns DataFrame: [person_id, date, available, reason]
    """
```

**Logic:**
1. For each partner in office
2. For each date in range (start_date → end_date)
3. Check if partner has active loan on that date
4. Check if partner has scheduled assignment on that date
5. Mark available=False if busy, True if free

**Testing:**
- ✅ Partner with active loan marked unavailable
- ✅ Partner with scheduled assignment marked unavailable
- ✅ Free partners marked available

**Commit Message:**
`"Add partner availability grid builder for vehicle chains"`

---

#### Chunk 4.2: Partner Base Scoring ✅
**Files Modified:**
- `backend/app/chain_builder/geography.py`

**New Function:**
```python
def score_partners_base(
    partners_df: pd.DataFrame,
    vehicle_make: str,
    approved_makes_df: pd.DataFrame
) -> Dict[int, float]:
    """
    Calculate base partner scores WITHOUT distance penalty.
    Distance handled separately by OR-Tools solver.

    Base score components:
    - Engagement level (dormant=0, neutral=50, active=100)
    - Publication rate (publications_last_90_days * 10)
    - Tier preference (A+=100, A=75, B=50, C=25)
    """
```

**Logic:**
1. Get partner engagement level
2. Get publication count (last 90 days)
3. Get tier preference for this vehicle's make from `approved_makes`
4. Combine: `score = engagement + (publications * 10) + tier_bonus`

**Testing:**
- ✅ A+ tier partners score highest
- ✅ Active partners score higher than dormant
- ✅ High publication rate increases score

**Commit Message:**
`"Add partner base scoring for vehicle chains (pre-distance)"`

---

#### Chunk 4.2b: OR-Tools Vehicle Chain Solver ✅ 🆕
**Files Created:**
- `backend/app/solver/vehicle_chain_solver.py`

**Main Functions:**
```python
def solve_vehicle_chain(
    vin: str,
    vehicle_make: str,
    office: str,
    start_date: datetime.date,
    num_partners: int,
    days_per_loan: int,
    candidates: List[Partner],
    distance_matrix: Dict[Tuple[int, int], float],
    distance_weight: float = 0.7,
    max_distance_per_hop: float = 50.0,
    distance_cost_per_mile: float = 2.0
) -> VehicleChainResult
```

**OR-Tools CP-SAT Model:**

**Decision Variables:**
```python
# Binary: Is partner p assigned to slot s?
x[partner_id, slot_index] = model.NewBoolVar(...)

# Binary: Does chain flow from p1 (slot s) to p2 (slot s+1)?
flow[partner_id_1, partner_id_2, slot_index] = model.NewBoolVar(...)
```

**Hard Constraints:**
```python
# 1. Each slot assigned exactly one partner
for s in range(num_partners):
    model.Add(sum(x[p, s] for p in candidates) == 1)

# 2. Each partner used at most once
for p in candidates:
    model.Add(sum(x[p, s] for s in range(num_partners)) <= 1)

# 3. Partner available during slot dates
for p in candidates:
    for s in range(num_partners):
        if not is_available(p, slot_dates[s]):
            model.Add(x[p, s] == 0)

# 4. Partner hasn't reviewed this vehicle
for p in reviewed_partners:
    for s in range(num_partners):
        model.Add(x[p, s] == 0)

# 5. CRITICAL: Max distance per handoff
for s in range(num_partners - 1):
    for p1, p2 in candidate_pairs:
        if distance_matrix[p1, p2] > max_distance_per_hop:
            model.Add(flow[p1, p2, s] == 0)  # Infeasible

# 6. Flow linking: flow[p1,p2,s] = 1 IFF x[p1,s]=1 AND x[p2,s+1]=1
for s in range(num_partners - 1):
    for p1, p2 in candidate_pairs:
        model.Add(flow[p1, p2, s] <= x[p1, s])
        model.Add(flow[p1, p2, s] <= x[p2, s+1])
        model.Add(flow[p1, p2, s] >= x[p1, s] + x[p2, s+1] - 1)
```

**Soft Objectives (Weighted):**
```python
# Minimize logistics cost (distance-based)
total_logistics_cost = sum(
    distance_matrix[p1, p2] * distance_cost_per_mile * flow[p1, p2, s]
    for s in range(num_partners - 1)
    for p1, p2 in candidate_pairs
)

# Maximize partner quality
total_quality_score = sum(
    partner_scores[p] * x[p, s]
    for p in candidates
    for s in range(num_partners)
)

# Combined objective
model.Maximize(
    (1 - distance_weight) * total_quality_score -
    distance_weight * total_logistics_cost
)
```

**Helper Functions:**
```python
def calculate_chain_slot_dates(
    start_date: datetime.date,
    num_slots: int,
    days_per_loan: int = 8
) -> List[Dict]:
    """
    Calculate slot dates with weekend extension logic.
    Returns list of slot dicts with start, end, actual_duration, handoff_date.
    """

def extend_to_weekday_if_weekend(date: datetime.date) -> datetime.date:
    """
    If date is Sat/Sun, extend to following Monday.
    """

def estimate_drive_time(distance_miles: float) -> int:
    """
    Estimate drive time in minutes (assume 20 mph avg in city).
    """
```

**Testing:**
- ✅ Solver finds optimal sequence for 4 partners
- ✅ All handoffs within max_distance_per_hop
- ✅ Distance weight = 0.0 → picks highest quality regardless of distance
- ✅ Distance weight = 1.0 → picks shortest total distance
- ✅ Partners who reviewed vehicle excluded
- ✅ Unavailable partners excluded
- ✅ Weekend extension applied correctly

**Commit Message:**
`"Add OR-Tools solver for vehicle chain geographic optimization with same-day handoffs"`

---

#### Chunk 4.3: Suggest Vehicle Chain Endpoint ✅
**Files Modified:**
- `backend/app/routers/chain_builder.py`

**New Route:**
```python
@router.post("/suggest-vehicle-chain")
async def suggest_vehicle_chain(
    request: VehicleChainRequest
):
    """
    Auto-generate optimal partner chain for a vehicle using OR-Tools.
    """
```

**Request Body:**
```json
{
  "vin": "1HGBH41JXMN109186",
  "office": "Los Angeles",
  "start_date": "2025-11-03",
  "num_partners": 4,
  "days_per_loan": 8,
  "distance_weight": 0.7,
  "max_distance_per_hop": 50.0,
  "distance_cost_per_mile": 2.0
}
```

**Logic:**
1. Validate start_date is weekday (reject Sat/Sun)
2. Get vehicle details from `vehicles` table
3. Get vehicle busy periods
4. Calculate chain slot dates (with weekend extension)
5. Load partners, current_activity, scheduled_assignments, loan_history
6. Get eligible partners (exclude reviewed)
7. Build distance matrix
8. Build partner availability grid
9. Score partners (base score)
10. **Call `vehicle_chain_solver.solve_vehicle_chain()`**
11. Return optimal chain with handoff details

**Response:**
```json
{
  "status": "success",
  "vehicle_info": {
    "vin": "1HGBH41JXMN109186",
    "make": "Honda",
    "model": "Accord",
    "year": "2023",
    "office": "Los Angeles"
  },
  "chain_params": {
    "start_date": "2025-11-03",
    "num_partners": 4,
    "days_per_loan": 8,
    "total_span_days": 32
  },
  "optimal_chain": [
    {
      "slot": 0,
      "person_id": 1523,
      "name": "LA Times",
      "start_date": "2025-11-03",
      "end_date": "2025-11-11",
      "nominal_duration": 8,
      "actual_duration": 8,
      "extended_for_weekend": false,
      "handoff": {
        "date": "2025-11-11",
        "to_partner": "KTLA News",
        "from_location": {"lat": 34.0522, "lng": -118.2437},
        "to_location": {"lat": 34.0580, "lng": -118.2516},
        "distance_miles": 3.2,
        "estimated_drive_time_min": 15,
        "logistics_cost": 6.40
      },
      "score": 850,
      "tier": "A+",
      "latitude": 34.0522,
      "longitude": -118.2437
    }
  ],
  "optimization_stats": {
    "total_distance_miles": 7.9,
    "average_distance_miles": 2.63,
    "total_quality_score": 3040,
    "average_quality_score": 760,
    "objective_value": 2250,
    "solver_time_ms": 124,
    "candidates_considered": 23
  },
  "logistics_summary": {
    "total_distance_miles": 7.9,
    "total_drive_time_min": 37,
    "total_logistics_cost": 15.80,
    "average_hop_distance": 2.63,
    "longest_hop": {
      "from": "LA Times",
      "to": "KTLA News",
      "distance": 3.2
    },
    "all_hops_within_limit": true,
    "max_limit": 50
  }
}
```

**Testing:**
- ✅ Returns optimal chain for valid input
- ✅ Rejects weekend start dates
- ✅ All handoffs on weekdays
- ✅ Distance limit enforced
- ✅ Logistics summary accurate

**Commit Message:**
`"Add suggest-vehicle-chain endpoint with OR-Tools optimization and handoff logistics"`

---

#### Chunk 4.4: Solver Diagnostics Integration ✅ 🆕
**Files Modified:**
- `backend/app/solver/vehicle_chain_solver.py`

**New Function:**
```python
def explain_vehicle_chain_result(
    result: VehicleChainResult,
    all_candidates: List[Partner],
    distance_matrix: Dict
) -> Dict:
    """
    Explain why certain partners were/weren't selected.
    Similar to OptimizerDiagnostics but for vehicle chains.
    """
```

**Returns:**
```json
{
  "selected_partners": [
    {
      "partner": "LA Times",
      "reason": "Highest base score (850) with no previous handoff"
    }
  ],
  "excluded_partners": [
    {
      "partner": "NBC LA",
      "reason": "Distance from Slot 0 (15.3 mi) exceeded optimal with 50pt score advantage"
    }
  ],
  "tradeoffs": [
    {
      "alternative_partner": "CBS LA",
      "score_difference": -30,
      "distance_difference": +8.2,
      "reason": "Quality vs distance tradeoff favored proximity"
    }
  ]
}
```

**Testing:**
- ✅ Diagnostics explain high-quality partners excluded due to distance
- ✅ Diagnostics explain distance-optimal partners excluded due to low quality

**Commit Message:**
`"Add diagnostics for vehicle chain solver decisions"`

---

### Phase 5: Manual Build Mode for Vehicle Chains

#### Chunk 5.1: Get Partner Slot Options Endpoint ✅
**Files Modified:**
- `backend/app/routers/chain_builder.py`

**New Route:**
```python
@router.get("/get-partner-slot-options")
async def get_partner_slot_options(
    vin: str,
    office: str,
    start_date: str,
    num_partners: int,
    days_per_loan: int,
    slot_index: int,
    exclude_partner_ids: str = "",           # Comma-separated
    previous_partner_id: Optional[int] = None,
    previous_partner_lat: Optional[float] = None,
    previous_partner_lng: Optional[float] = None,
    distance_weight: float = 0.7
):
    """
    Returns eligible partners for a specific slot in manual build mode.
    Sorted by distance-adjusted score.
    """
```

**Logic:**
1. Calculate slot dates (with weekend extension)
2. Get target slot (slot_index)
3. Load all data (partners, activity, history)
4. Get eligible partners:
   - In same office
   - Haven't reviewed this vehicle
   - Available during slot dates
   - NOT in exclude_partner_ids list
5. **If slot_index > 0:** Calculate distance from previous partner
6. Score each partner:
   ```python
   base_score = engagement + publication + tier
   if slot_index > 0:
       distance_penalty = distance_miles * distance_weight * 10
       final_score = base_score - distance_penalty
   else:
       final_score = base_score  # No distance penalty for first slot
   ```
7. Sort by final_score DESC
8. Return top 50

**Response:**
```json
{
  "status": "success",
  "slot": {
    "index": 1,
    "start_date": "2025-11-11",
    "end_date": "2025-11-19",
    "actual_duration": 8,
    "extended_for_weekend": false
  },
  "previous_partner": {
    "person_id": 1523,
    "name": "LA Times",
    "latitude": 34.0522,
    "longitude": -118.2437
  },
  "eligible_partners": [
    {
      "person_id": 2156,
      "name": "Fox 11",
      "address": "321 Pine Rd, LA",
      "latitude": 34.0545,
      "longitude": -118.2401,
      "distance_from_previous": 2.9,
      "base_score": 710,
      "distance_penalty": 203,
      "final_score": 507,
      "tier": "A",
      "engagement_level": "active",
      "publications_last_90_days": 12
    }
  ],
  "total_eligible": 50,
  "excluded_count": 2,
  "unavailable_count": 8,
  "reviewed_vehicle_count": 5
}
```

**Testing:**
- ✅ Slot 0 returns partners sorted by base score (no distance)
- ✅ Slot 1+ returns partners sorted by distance-adjusted score
- ✅ Excluded partners not in results
- ✅ Unavailable partners not in results

**Commit Message:**
`"Add partner slot options endpoint with distance-aware scoring for manual mode"`

---

#### Chunk 5.2: Frontend Manual Mode Integration ✅
**Files Modified:**
- `frontend/src/pages/ChainBuilder.jsx`

**Changes:**
- Add `manualPartnerSlots` state
- Display empty slot cards (5 per row grid) when manual mode active
- Each slot has dropdown (lazy-loaded on focus)
- Call `/get-partner-slot-options` when dropdown focused
- Display partners with distance from previous
- Enable slots sequentially (Slot N disabled until Slot N-1 selected)
- Real-time logistics summary updates as slots filled
- Session storage persistence

**UI Elements:**
```jsx
// Empty slot card
<SlotCard>
  <div>Slot 0: Nov 3 - Nov 11</div>
  <Select
    placeholder="Select Partner"
    onFocus={() => loadPartnerOptions(0)}
  >
    {options.map(partner => (
      <Option>
        {partner.name} ⭐ {partner.final_score}
        {slot > 0 && ` (${partner.distance_from_previous.toFixed(1)} mi)`}
      </Option>
    ))}
  </Select>
</SlotCard>

// Filled slot card
<SlotCard className="selected">
  <div>Slot 0: Nov 3 - Nov 11</div>
  <div>{partner.name}</div>
  <div>Score: {partner.final_score}</div>
  <div>Distance: {handoff.distance_miles} mi</div>
  <Button onClick={() => editSlot(0)}>Edit</Button>
  <Button onClick={() => deleteSlot(0)}>Delete</Button>
</SlotCard>
```

**Testing:**
- ✅ Empty slots display correctly
- ✅ Dropdown lazy-loads options
- ✅ Distance shown for slots 1+
- ✅ Sequential enabling works
- ✅ Session storage persists manual selections

**Commit Message:**
`"Add manual build mode UI for vehicle chains with distance display"`

---

#### Chunk 5.3: Edit Mode After Auto-Generate ✅ 🆕
**Files Modified:**
- `frontend/src/pages/ChainBuilder.jsx`

**Changes:**
- Add "Edit" button to auto-generated chain slot cards
- Clicking "Edit" opens dropdown with slot options (same API as manual mode)
- User can swap partner for any slot
- **Recalculate distances** for all subsequent slots after swap
- Update logistics summary after swap
- Mark chain as "modified" (show indicator)

**Logic:**
```javascript
const handleEditSlot = async (slotIndex) => {
  // Load options for this slot
  const options = await fetchPartnerSlotOptions(slotIndex, {
    exclude_partner_ids: getOtherSelectedPartnerIds(slotIndex),
    previous_partner_id: slotIndex > 0 ? chain[slotIndex - 1].person_id : null,
    // ... other params
  });

  // Show dropdown
  setEditingSlot(slotIndex);
  setSlotOptions(options);
};

const handleSwapPartner = (slotIndex, newPartner) => {
  // Update chain at this slot
  const updatedChain = [...vehicleChain];
  updatedChain[slotIndex] = newPartner;

  // Recalculate distances for slots after this one
  for (let i = slotIndex + 1; i < updatedChain.length; i++) {
    const prevPartner = updatedChain[i - 1];
    const currPartner = updatedChain[i];
    const distance = calculateDistance(
      prevPartner.latitude,
      prevPartner.longitude,
      currPartner.latitude,
      currPartner.longitude
    );
    updatedChain[i].handoff.distance_miles = distance;
    updatedChain[i].handoff.estimated_drive_time_min = estimateDriveTime(distance);
    updatedChain[i].handoff.logistics_cost = distance * 2.0;
  }

  setVehicleChain(updatedChain);
  setChainModified(true);

  // Refresh logistics summary
  refreshLogisticsSummary(updatedChain);
};
```

**Testing:**
- ✅ Edit button appears on auto-generated chains
- ✅ Dropdown shows alternatives sorted by distance
- ✅ Swapping recalculates all downstream distances
- ✅ Logistics summary updates correctly
- ✅ "Modified" indicator shows after edit

**Commit Message:**
`"Add edit mode for auto-generated vehicle chains with distance recalculation"`

---

### Phase 6: Save & Visualization

#### Chunk 6.1: Save Vehicle Chain Endpoint ✅
**Files Modified:**
- `backend/app/routers/chain_builder.py`

**New Route:**
```python
@router.post("/save-vehicle-chain")
async def save_vehicle_chain(request: SaveVehicleChainRequest):
    """
    Save vehicle chain to scheduled_assignments table.
    Same table as partner chains, different perspective.
    """
```

**Request Body:**
```json
{
  "vin": "1HGBH41JXMN109186",
  "vehicle_make": "Honda",
  "office": "Los Angeles",
  "status": "manual",  // or 'requested'
  "chain": [
    {
      "person_id": 1523,
      "partner_name": "LA Times",
      "start_date": "2025-11-03",
      "end_date": "2025-11-11",
      "score": 850
    }
  ]
}
```

**Logic:**
1. Validate required fields
2. For each partner in chain:
   - Calculate `week_start` (Monday of start week)
   - Create `scheduled_assignments` record:
     ```sql
     INSERT INTO scheduled_assignments (
       person_id, vin, make, model, start_day, end_day,
       office, partner_name, week_start, status, score
     ) VALUES (...)
     ```
3. Return assignment IDs

**Status Values:**
- `'manual'` → GREEN in calendar (recommendations)
- `'requested'` → MAGENTA in calendar (sent to FMS)

**Testing:**
- ✅ Chain saved to database
- ✅ All records have correct dates
- ✅ Status field set correctly
- ✅ Assignment IDs returned

**Commit Message:**
`"Add save vehicle chain endpoint to scheduled_assignments table"`

---

#### Chunk 6.2: Timeline Visualization ✅
**Files Modified:**
- `frontend/src/pages/ChainBuilder.jsx`

**Changes:**
- When `chainMode === 'vehicle'`, load vehicle's calendar instead of partner's
- Query vehicle's `current_activity` and `scheduled_assignments`
- Timeline shows:
  - **BLUE bars:** Current active loans (vehicle with partners)
  - **GREEN bars:** Scheduled manual assignments
  - **MAGENTA bars:** Scheduled requested assignments
  - **GRAY bars:** Proposed chain slots (before save)
- Display partner names on bars (instead of vehicle info)
- Handoff indicators (orange dots) on transition dates

**Timeline Bar Content (Vehicle Mode):**
```jsx
<TimelineBar color={getBarColor(assignment.status)}>
  <div>{assignment.partner_name}</div>
  <div>{formatDate(assignment.start_date)} - {formatDate(assignment.end_date)}</div>
  {assignment.handoff && (
    <HandoffIndicator date={assignment.handoff.date}>
      🔄 {assignment.handoff.distance_miles} mi
    </HandoffIndicator>
  )}
</TimelineBar>
```

**Testing:**
- ✅ Timeline loads vehicle's calendar
- ✅ Bars show partner names
- ✅ Handoff indicators display on transition dates
- ✅ Colors match status (blue/green/magenta/gray)

**Commit Message:**
`"Update timeline visualization for vehicle chain mode with handoff indicators"`

---

### Phase 7: Budget & Intelligence

#### Chunk 7.1: Vehicle Intelligence Endpoint ✅
**Files Modified:**
- `backend/app/routers/chain_builder.py`

**New Route:**
```python
@router.get("/vehicle-intelligence")
async def get_vehicle_intelligence(vin: str, office: str):
    """
    Get vehicle's current status and historical metrics.
    Similar to partner intelligence but for vehicles.
    """
```

**Response:**
```json
{
  "vin": "1HGBH41JXMN109186",
  "make": "Honda",
  "model": "Accord",
  "year": "2023",
  "office": "Los Angeles",
  "tier": "A+",
  "current_status": {
    "is_active": true,
    "partner_name": "LA Times",
    "start_date": "2025-10-15",
    "end_date": "2025-10-22"
  },
  "upcoming_assignments": [
    {
      "partner_name": "KTLA",
      "start_date": "2025-11-01",
      "end_date": "2025-11-08",
      "status": "manual"
    }
  ],
  "historical_metrics": {
    "total_loans": 12,
    "unique_partners": 8,
    "average_loan_days": 7.5,
    "last_loan_date": "2025-10-22"
  }
}
```

**Testing:**
- ✅ Returns current active loan if exists
- ✅ Returns upcoming scheduled assignments
- ✅ Historical metrics accurate

**Commit Message:**
`"Add vehicle intelligence endpoint for chain builder"`

---

#### Chunk 7.2: Budget Calculation Integration ✅
**Files Modified:**
- `backend/app/routers/chain_builder.py` (MODIFY existing endpoint)

**Changes:**
- Update existing `/calculate-chain-budget` endpoint to accept vehicle-centric format
- Same cost lookup by partner/make
- Return same format (breakdown by fleet)

**Request Body (Vehicle Chain Format):**
```json
{
  "office": "Los Angeles",
  "vehicle_make": "Honda",
  "chain": [
    {
      "person_id": 1523,
      "partner_name": "LA Times",
      "start_date": "2025-11-03"
    }
  ]
}
```

**Logic:**
- For each assignment, lookup cost from `media_costs` table
- Group by fleet (make)
- Return current + planned + projected spend

**Testing:**
- ✅ Works for partner chains (existing)
- ✅ Works for vehicle chains (new)
- ✅ Costs calculated correctly

**Commit Message:**
`"Integrate budget calculations for vehicle chains (reuse existing endpoint)"`

---

### Phase 8: Polish & Enhancements

#### Chunk 8.1: Distance Display & Metrics ✅
**Files Modified:**
- `frontend/src/pages/ChainBuilder.jsx`

**New UI Elements:**
- Right panel: "Logistics Summary" section (vehicle mode only)
- Show:
  - Total travel distance
  - Average distance per hop
  - Total drive time estimate
  - Total logistics cost
  - Longest hop with warning if >40 miles
  - List of all handoffs with distances

**Example:**
```jsx
<LogisticsSummary>
  <h3>Chain Logistics</h3>
  <Metric>
    <label>Total Distance</label>
    <value>7.9 miles</value>
  </Metric>
  <Metric>
    <label>Average per Hop</label>
    <value>2.6 miles</value>
  </Metric>
  <Metric>
    <label>Total Drive Time</label>
    <value>~37 minutes</value>
  </Metric>
  <Metric>
    <label>Logistics Cost</label>
    <value>$15.80 (@ $2/mile)</value>
  </Metric>

  <h4>Handoff Schedule</h4>
  <HandoffList>
    <Handoff>
      <date>Nov 11</date>
      <transition>LA Times → KTLA News</transition>
      <distance>3.2 mi (~15 min)</distance>
    </Handoff>
    {/* ... more handoffs */}
  </HandoffList>

  {longestHop > 40 && (
    <Warning>
      ⚠️ Longest hop: {longestHop} mi (consider closer alternatives)
    </Warning>
  )}
</LogisticsSummary>
```

**Testing:**
- ✅ Metrics calculate correctly
- ✅ Updates in real-time as chain modified
- ✅ Warning appears for long hops

**Commit Message:**
`"Add comprehensive logistics metrics and distance display for vehicle chains"`

---

#### Chunk 8.2: Optional Map View ✅ (Future Enhancement)
**Files Created:**
- `frontend/src/components/ChainMap.jsx`

**Dependencies:**
- React Leaflet or Google Maps React
- Map tile provider (OpenStreetMap, Mapbox, Google)

**Features:**
- Plot partner locations as numbered markers
- Draw route lines between sequential partners
- Color-code by distance (green <10mi, yellow 10-30mi, red >30mi)
- Click marker to see partner details
- Hover route line to see distance

**Testing:**
- ✅ Map renders with correct markers
- ✅ Route lines connect in sequence
- ✅ Markers clickable with partner info

**Commit Message:**
`"Add geographic map visualization for vehicle chains (optional enhancement)"`

---

## OR-Tools Optimization Strategy

### Why OR-Tools for Vehicle Chains

1. **Consistency** - Same solver framework as main Optimizer
2. **Global optimality** - Not greedy, finds best sequence
3. **Multi-objective** - Balance distance vs quality
4. **Constraint handling** - Hard limits (max distance, availability, exclusions)
5. **Speed** - CP-SAT solves small problems (<50 partners, 6 slots) in <1 second
6. **Auditability** - Can explain every decision

### Model Structure

**Problem Type:** Vehicle Routing Problem (VRP) variant

**Input:**
- Set of candidate partners (20-50 typical)
- Distance matrix (pairwise distances)
- Partner quality scores
- Availability constraints
- Exclusion rules

**Output:**
- Optimal sequence of N partners
- Total distance minimized
- Total quality maximized
- All constraints satisfied

### Solver Parameters

```python
solver.parameters.random_seed = 42          # Deterministic results
solver.parameters.max_time_in_seconds = 30  # Timeout
solver.parameters.num_search_workers = 4    # Parallel search
```

### Objective Function Tuning

**Distance Weight (0.0 - 1.0):**
- 0.0 = Ignore distance, maximize quality only
- 0.5 = Equal weight to distance and quality
- 0.7 = **Default** - Prioritize logistics (recommended)
- 1.0 = Minimize distance only, ignore quality

**Example Scenarios:**

| Weight | Use Case | Result |
|--------|----------|--------|
| 0.3 | High-value partners, distance less critical | May have 1-2 longer hops (15+ mi) but top-tier partners |
| 0.7 | **Standard** - Balance quality and logistics | Reasonable distances (5-10 mi avg), good partners |
| 0.9 | Logistics-critical, tight time windows | Minimal distances (<5 mi avg), may sacrifice some quality |

---

## API Specifications

### Summary Table

| Method | Endpoint | Purpose | Phase |
|--------|----------|---------|-------|
| GET | `/api/chain-builder/search-vehicles` | Search VINs for autocomplete | 2.1 |
| GET | `/api/chain-builder/vehicle-busy-periods` | Get vehicle's rental calendar | 2.2 |
| POST | `/api/chain-builder/suggest-vehicle-chain` | Auto-generate optimal partner chain | 4.3 |
| GET | `/api/chain-builder/get-partner-slot-options` | Get partners for manual slot selection | 5.1 |
| POST | `/api/chain-builder/save-vehicle-chain` | Save chain to database | 6.1 |
| GET | `/api/chain-builder/vehicle-intelligence` | Get vehicle status and history | 7.1 |
| POST | `/api/chain-builder/calculate-chain-budget` | Calculate cost (EXISTING - reuse) | 7.2 |

### Detailed Specifications

See [API Specifications](#api-specifications) section above for full request/response formats.

---

## UI/UX Design

### Tab Structure

```
┌─────────────────────────────────────────────────────┐
│  [ Partner Chain ]  [ Vehicle Chain ]  ← Tabs       │
├───────────────┬─────────────────────┬───────────────┤
│  Left Panel   │  Center Timeline    │  Right Panel  │
│  (Parameters) │  (Visualization)    │  (Info)       │
│               │                     │               │
│  Office: LA   │  [Timeline showing  │  Chain Stats  │
│               │   vehicle's         │               │
│  When vehicle │   calendar with     │  Logistics:   │
│  mode active: │   partner names]    │  • Total: 7.9 │
│               │                     │    miles      │
│  [Vehicle     │                     │  • Time: 37m  │
│   Selector]   │  [Proposed chain    │  • Cost: $15  │
│               │   slots shown as    │               │
│  Start: Nov 3 │   gray bars]        │  Handoffs:    │
│               │                     │  • Nov 11:    │
│  Partners: 4  │  [Handoff           │    LA→KTLA    │
│               │   indicators on     │    3.2 mi     │
│  Days: 8      │   transition dates] │               │
│               │                     │  Budget:      │
│  Distance:    │                     │  Honda: $500  │
│  ━━━●━━━━ 70% │                     │               │
│               │                     │               │
│  Build Mode:  │                     │               │
│  ● Auto       │                     │               │
│  ○ Manual     │                     │               │
│               │                     │               │
│  [Generate]   │                     │  [Save Chain] │
└───────────────┴─────────────────────┴───────────────┘
```

### Component Reuse

**Shared (Both Modes):**
- Timeline calendar component
- Save/delete buttons
- Budget display
- Session storage logic
- Build mode toggle

**Partner Mode Only:**
- Partner selector dropdown
- Vehicle slot cards
- Make filter

**Vehicle Mode Only:**
- Vehicle selector dropdown
- Partner slot cards (with distance)
- Logistics summary panel
- Distance weight slider
- Map view (optional)

---

## Testing Strategy

### Unit Tests

**Backend:**
```python
# test_vehicle_chain_solver.py
def test_solver_basic_chain()
def test_solver_weekend_extension()
def test_solver_max_distance_constraint()
def test_solver_partner_exclusion()
def test_solver_availability_constraint()
def test_distance_weight_extremes()

# test_geography.py
def test_haversine_accuracy()
def test_distance_matrix_symmetry()
def test_missing_coordinates()

# test_vehicle_exclusions.py
def test_partner_reviewed_excluded()
def test_new_partner_eligible()
```

**Frontend:**
```javascript
// ChainBuilder.test.jsx
test('tab switching works', ...)
test('vehicle selector appears in vehicle mode', ...)
test('partner selector hidden in vehicle mode', ...)
test('manual slots enable sequentially', ...)
test('distance shown in partner dropdowns', ...)
test('logistics summary updates on edit', ...)
```

### Integration Tests

```python
# test_vehicle_chain_integration.py

def test_end_to_end_auto_generate():
    """Full flow: search vehicle → generate chain → save → verify DB"""

def test_end_to_end_manual_build():
    """Full flow: create slots → select partners → save → verify DB"""

def test_edit_after_auto_generate():
    """Generate chain → edit slot 1 → verify distances recalculated"""

def test_weekend_extension_chain():
    """Friday start → verify first slot extended to Monday"""
```

### Regression Tests

**Critical:** Ensure partner chain mode still works after every commit

```python
def test_partner_chain_unchanged():
    """Verify existing partner chain functionality not broken"""
    # Test auto-generate
    # Test manual build
    # Test save
    # Test timeline
```

### Manual QA Checklist

Per chunk commit:
- [ ] Partner chain mode works (no regression)
- [ ] Vehicle chain new feature works
- [ ] Timeline displays correctly
- [ ] Save to database successful
- [ ] Session storage persists
- [ ] No console errors
- [ ] Mobile responsive (if applicable)

---

## Rollback Strategy

### Per-Chunk Rollback

Each chunk is a single commit. If issues found:

```bash
# Rollback last commit
git revert HEAD

# Or rollback to specific chunk
git revert <chunk-commit-hash>
```

### Feature Flag (Optional)

Add feature flag to hide vehicle chain tab if critical issues found in production:

```javascript
// config.js
export const FEATURE_FLAGS = {
  VEHICLE_CHAIN_ENABLED: process.env.REACT_APP_VEHICLE_CHAIN_ENABLED === 'true'
};

// ChainBuilder.jsx
{FEATURE_FLAGS.VEHICLE_CHAIN_ENABLED && (
  <Tab>Vehicle Chain</Tab>
)}
```

### Database Rollback

Vehicle chains use existing `scheduled_assignments` table. No schema changes = no database rollback needed.

If bad data saved:
```sql
-- Delete vehicle chain assignments (manual cleanup)
DELETE FROM scheduled_assignments
WHERE assignment_id IN (...);
```

---

## Implementation Timeline

### Estimated Duration: 5 Weeks

**Week 1: Foundation (Chunks 1.1, 1.2, 2.1, 2.2)**
- Days 1-2: Tab switching + vehicle selector UI
- Days 3-4: Backend search and calendar endpoints
- Day 5: Testing and refinement

**Week 2: Core Logic (Chunks 3.1, 3.2, 4.1, 4.2)**
- Days 1-2: Exclusions + geography modules
- Days 3-4: Availability grid + partner scoring
- Day 5: Testing

**Week 3: OR-Tools Solver (Chunks 4.2b, 4.3, 4.4)**
- Days 1-3: Implement CP-SAT solver
- Day 4: Suggest-vehicle-chain endpoint
- Day 5: Diagnostics integration

**Week 4: Manual Mode (Chunks 5.1, 5.2, 5.3)**
- Days 1-2: Partner slot options endpoint
- Days 3-4: Manual mode UI + edit mode
- Day 5: Testing

**Week 5: Polish (Chunks 6.1, 6.2, 7.1, 7.2, 8.1)**
- Days 1-2: Save endpoint + timeline visualization
- Days 3-4: Intelligence + budget integration
- Day 5: Logistics metrics + final testing

**Optional (Week 6): Map View (Chunk 8.2)**
- If time permits, add geographic map visualization

---

## Success Criteria

### Feature Complete Checklist

- [ ] User can toggle between Partner Chain and Vehicle Chain tabs
- [ ] User can search and select vehicles by VIN/make/model
- [ ] Auto-generate mode produces optimal partner chains using OR-Tools
- [ ] Manual mode allows slot-by-slot partner selection
- [ ] Distance from previous partner shown in dropdowns
- [ ] All handoffs occur on weekdays (weekend extension working)
- [ ] Same-day handoff logic enforced
- [ ] Max distance per hop constraint enforced
- [ ] Chains can be saved with status 'manual' or 'requested'
- [ ] Timeline shows vehicle's calendar with partner names
- [ ] Handoff indicators display on transition dates
- [ ] Logistics summary shows distance, time, cost
- [ ] Budget integration works
- [ ] Edit mode allows swapping partners with distance recalculation
- [ ] Session storage persists work across page refreshes
- [ ] Partner chain mode unchanged (no regression)
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Documentation complete

### Performance Targets

- [ ] OR-Tools solver completes in <5 seconds for 4-6 partner chains
- [ ] Timeline loads in <2 seconds
- [ ] Dropdown options load in <1 second (lazy-loaded)
- [ ] Save operation completes in <1 second
- [ ] No memory leaks (test with 10+ chain builds)

---

## Future Enhancements (Post-Launch)

1. **Multi-Office Chains** - Vehicle travels between LA, SF, NY offices
2. **Route Optimization API** - Use Google Maps Directions API for actual drive time
3. **Automated Handoff Scheduling** - Email notifications to partners about handoff times
4. **Historical Handoff Analytics** - Track actual vs estimated drive times
5. **Partner Clustering Visualization** - Heat map of partner density
6. **Batch Chain Creation** - Generate chains for 10+ vehicles simultaneously
7. **Chain Templates** - Save successful chain patterns for reuse
8. **Dynamic Distance Weighting** - Adjust weight based on time of day (rush hour)

---

## Questions & Answers

### Q: Why 8-day loans instead of 7?
**A:** Client requirement to avoid weekend handoffs. With 8-day loans starting Monday, end date is Tuesday (weekday). 7-day loans would end on Sunday, requiring Monday extension anyway.

### Q: Why is distance weight defaulted to 70%?
**A:** Same-day handoffs mean distance is actual operational cost (staff time, gas, logistics). Partner quality difference of 50 points is less important than a 20-mile drive.

### Q: Can we use this for multi-vehicle chains?
**A:** Not in initial version. Current design is 1 vehicle → N partners. Multi-vehicle chains would require different UI and optimization approach.

### Q: What if no partners are within 50 miles?
**A:** Solver returns "infeasible" result with diagnostic message. User can increase max_distance_per_hop or select different start date.

### Q: How do we handle last-minute cancellations?
**A:** User can delete individual slots or entire chains. Timeline updates immediately. Deleted assignments removed from `scheduled_assignments`.

### Q: Can we optimize for factors other than distance?
**A:** Yes! OR-Tools model is flexible. Can add objectives for:
- Partner engagement (prefer active partners)
- Publication rate (prefer high-performing partners)
- Time since last loan (prefer dormant partners)
- Partner tier preference (A+ partners only)

---

## References

### Documentation
- [PHASE_7_COMPLETE_DOCUMENTATION_local.md](/Users/richardrierson/Desktop/Projects/media_scheduler/backend/PHASE_7_COMPLETE_DOCUMENTATION_local.md) - Main Optimizer documentation
- [OPTIMIZER_DIAGNOSTICS_INTEGRATION.md](/Users/richardrierson/Desktop/Projects/media_scheduler/OPTIMIZER_DIAGNOSTICS_INTEGRATION.md) - Diagnostics integration guide

### Existing Code Files
- `frontend/src/pages/ChainBuilder.jsx` - Current partner chain implementation
- `backend/app/routers/chain_builder.py` - Partner chain API routes
- `backend/app/solver/ortools_solver_v6.py` - Main optimizer (reference for OR-Tools patterns)
- `backend/app/chain_builder/exclusions.py` - Vehicle exclusion logic (template for partner exclusions)
- `backend/app/chain_builder/availability.py` - Vehicle availability grid (template for partner availability)
- `backend/app/chain_builder/smart_scheduling.py` - Smart slot finding (reusable)

### External Dependencies
- Google OR-Tools (ortools.sat.python.cp_model)
- Pandas (data manipulation)
- FastAPI (backend framework)
- React (frontend framework)
- Supabase (database)

---

## Appendix: Code Snippets

### Weekend Extension Logic
```python
def extend_to_weekday_if_weekend(date: datetime.date) -> datetime.date:
    """If date is Sat/Sun, extend to following Monday."""
    if date.weekday() == 5:  # Saturday
        return date + timedelta(days=2)  # → Monday
    elif date.weekday() == 6:  # Sunday
        return date + timedelta(days=1)  # → Monday
    else:
        return date  # Already weekday
```

### Haversine Distance Formula
```python
from math import radians, cos, sin, asin, sqrt

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in miles."""
    # Convert to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))

    # Radius of earth in miles
    r = 3956

    return c * r
```

### OR-Tools Model Template
```python
from ortools.sat.python import cp_model

model = cp_model.CpModel()

# Decision variables
x = {}
for p in partners:
    for s in range(num_slots):
        x[p, s] = model.NewBoolVar(f'x_{p}_{s}')

# Constraints
for s in range(num_slots):
    model.Add(sum(x[p, s] for p in partners) == 1)

# Objective
model.Maximize(sum(score[p] * x[p, s] for p in partners for s in range(num_slots)))

# Solve
solver = cp_model.CpSolver()
solver.parameters.random_seed = 42
status = solver.Solve(model)
```

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2025-10-29 | 1.0 | Initial plan created - comprehensive design doc |

---

## Contact & Support

For questions about this implementation plan:
- Review existing Chain Builder code in `frontend/src/pages/ChainBuilder.jsx`
- Reference main Optimizer documentation in `PHASE_7_COMPLETE_DOCUMENTATION_local.md`
- Check git history for patterns: `git log --oneline backend/app/routers/chain_builder.py`

---

**END OF VEHICLE CHAIN BUILDER IMPLEMENTATION PLAN**
