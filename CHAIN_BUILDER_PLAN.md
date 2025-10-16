# Chain Builder Feature - Implementation Plan

## Overview
Build a "Loan Chain Builder" feature that allows Rafael to quickly create 4-6 back-to-back vehicle assignments for a single media partner, filtering out vehicles they've already reviewed.

## Current State (What We Have)
- ✅ Robust Optimizer with constraint solving
- ✅ Distance calculations (local/remote partners)
- ✅ Tier/ranking system (A+, A, B, C)
- ✅ Loan history tracking
- ✅ Availability grid (lifecycle, current activity)
- ✅ Calendar view with timeline visualization
- ✅ Partner intelligence endpoint (approved makes, past reviews)

## Key Repositories & Files
- **Backend:** `/backend/app/routers/` - API endpoints
- **Frontend:** `/frontend/src/pages/` - UI components
- **Solver:** `/backend/app/solver/` - Optimization logic
- **Database:** Supabase tables via DatabaseService

### Critical Tables
- `media_partners` - Partner info, office, address, lat/lon
- `vehicles` - VIN, make, model, office, lifecycle dates
- `loan_history` - Past assignments (who reviewed what)
- `current_activity` - Active loans
- `approved_makes` - Partner approvals with tier ranks
- `rules` - Tier caps, cooldown periods

### Existing Endpoints to Leverage
- `/api/ui/phase7/partner-intelligence` - Get partner's approved makes and history
- `/api/calendar/activity` - Get activities for date range
- `/api/calendar/vehicles` - Get all vehicles for office
- `/solver/generate_schedule` - Optimization logic (can adapt)

## Feature Requirements

### User Workflow
1. Rafael selects a media partner from dropdown
2. Specifies chain parameters (num vehicles, start date, days per loan)
3. System suggests vehicles they HAVEN'T driven, sequentially available
4. Rafael previews the chain timeline
5. Can manually swap vehicles
6. Confirms → Saves to scheduled_assignments

### Business Rules
- **Exclusion:** Don't suggest vehicles partner reviewed in past 12 months
- **Sequential availability:** Each vehicle must be available when previous loan ends
- **Cooldown:** Respect model/trim cooldown rules
- **Budget:** Stay within tier caps for chain period
- **Distance:** Prefer local partners for multi-vehicle chains
- **Variety:** Prioritize different makes/models in chain

## Implementation Plan (Commit-by-Commit)

### Phase 1: Backend Foundation (Days 1-2)

#### Commit 1: Create chain suggestions endpoint skeleton
**File:** `backend/app/routers/chain_builder.py`
**Changes:**
- New router with prefix `/api/chain-builder`
- Endpoint: `GET /suggest-chain`
- Parameters: person_id, office, start_date, num_vehicles, days_per_loan
- Returns: Mock response structure
- **Test:** Endpoint responds with 200

#### Commit 2: Add "vehicles not reviewed" logic
**File:** `backend/app/chain_builder/exclusions.py`
**Changes:**
- Function: `get_vehicles_not_reviewed(person_id, office, months_back=12)`
- Query loan_history for this partner
- Return set of VINs they HAVE reviewed
- Filter vehicles to those NOT in that set
- **Test:** Returns correct exclusion list for known partner

#### Commit 3: Add sequential availability checker
**File:** `backend/app/chain_builder/availability.py`
**Changes:**
- Function: `check_chain_availability(vins, start_date, days_per_loan)`
- For each vehicle, check it's available for its slot
- Slot 1: start_date to start_date+days
- Slot 2: start_date+days to start_date+(2*days)
- etc.
- **Test:** Validates a known good chain, rejects overlapping chain

#### Commit 4: Integrate chain suggestion logic
**File:** `backend/app/routers/chain_builder.py`
**Changes:**
- Call exclusions logic
- Call availability checker
- Score remaining vehicles (reuse scoring.py logic)
- Return top N vehicles in chain order
- **Test:** Full chain suggestion for test partner

### Phase 2: Frontend UI (Days 3-4)

#### Commit 5: Create Chain Builder tab skeleton
**File:** `frontend/src/pages/ChainBuilder.jsx`
**Changes:**
- New component with basic layout
- Partner selector dropdown
- Start date picker
- Number of vehicles slider (1-10)
- Days per loan input (default 7)
- "Generate Chain" button
- **Test:** Tab renders, inputs work

#### Commit 6: Add chain preview component
**File:** `frontend/src/components/ChainPreview.jsx`
**Changes:**
- Reuse Calendar timeline rendering
- Show chain as sequential bars
- Display vehicle info (make/model, VIN)
- Show gaps/conflicts if any
- **Test:** Renders mock chain data correctly

#### Commit 7: Connect to backend API
**File:** `frontend/src/pages/ChainBuilder.jsx`
**Changes:**
- Call `/api/chain-builder/suggest-chain`
- Display loading state
- Show results in ChainPreview
- Handle errors gracefully
- **Test:** End-to-end chain generation

#### Commit 8: Add manual vehicle swap
**File:** `frontend/src/pages/ChainBuilder.jsx`
**Changes:**
- Click vehicle in chain to open swap modal
- Show alternative vehicles for that slot
- Swap maintains sequential availability
- Update preview in real-time
- **Test:** Swap vehicles without breaking chain

### Phase 3: Save & Refinements (Days 5-6)

#### Commit 9: Save chain to database
**File:** `backend/app/routers/chain_builder.py`
**Changes:**
- Endpoint: `POST /save-chain`
- Accept array of assignments
- Insert into scheduled_assignments with status='manual'
- Return confirmation
- **Test:** Chain appears in Calendar view

#### Commit 10: Add make/tier preferences
**File:** Frontend + Backend
**Changes:**
- Optional "Prefer makes" multi-select
- Optional "Prefer tiers" filter
- Adjust scoring to weight preferences
- **Test:** Chain suggestions respect preferences

#### Commit 11: Add chain templates
**File:** Frontend
**Changes:**
- Save common chain configs (4 vehicles, 7 days, prefer luxury)
- Load from localStorage
- Quick-apply templates
- **Test:** Save/load templates

#### Commit 12: Polish & edge cases
**Changes:**
- Better error messages
- Loading indicators
- Validation (can't chain if no vehicles available)
- Conflict warnings
- **Test:** Handle all edge cases gracefully

## Fallback Points
- After Commit 4: Backend works standalone (can test via API)
- After Commit 7: Basic chain builder functional
- After Commit 9: Feature is usable (manual swaps are nice-to-have)

## Testing Strategy
Each commit should:
1. Have a specific test case
2. Be independently testable
3. Not break existing functionality
4. Be revertible if needed

## Estimated Timeline
- Days 1-2: Backend (Commits 1-4)
- Days 3-4: Frontend (Commits 5-8)
- Days 5-6: Save + Polish (Commits 9-12)
- Day 7: Buffer for issues

## Success Criteria
✅ Rafael can select a partner and get 4-6 vehicle suggestions
✅ Vehicles are ones partner hasn't reviewed recently
✅ Chain is sequentially available (no gaps/conflicts)
✅ Visual preview shows timeline clearly
✅ Can save chain to scheduled_assignments
✅ Chain appears in Calendar view
