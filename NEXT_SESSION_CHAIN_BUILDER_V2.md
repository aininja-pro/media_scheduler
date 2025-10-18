# Next Session: Chain Builder v2 - Manual Vehicle Selection

## Quick Start for New Chat

Say to Claude:
```
I want to implement Chain Builder v2 - Manual Vehicle Selection mode.

Read CHAIN_BUILDER_V2_SPEC.md for the full feature spec.

Current state: Chain Builder v1 is complete and working (auto-generation mode).
Goal: Add manual mode where scheduler picks specific vehicles from dropdowns for each slot.

Key files:
- Backend: /backend/app/routers/chain_builder.py
- Frontend: /frontend/src/pages/ChainBuilder.jsx
- Smart scheduling: /backend/app/chain_builder/smart_scheduling.py

Start with Phase 1: Create backend endpoint to get eligible vehicles for a specific slot.
```

---

## What's Already Built (Chain Builder v1)

### **Working Features**:
✅ Smart gap-finding (threads chains through existing commitments)
✅ Auto-generation with optimizer scoring
✅ Model diversity enforcement
✅ VIN exclusion (partner history)
✅ Make filtering with checkboxes
✅ Save/delete chains (entire or individual vehicles)
✅ Timeline visualization with calendar view
✅ Partner selection persistence
✅ 5-column vehicle card grid
✅ Blue ⇄ swap icons (placeholder) / Red × delete buttons

### **Key Endpoints**:
- `GET /api/chain-builder/suggest-chain` - Auto-generates full chain
- `POST /api/chain-builder/save-chain` - Saves to database
- Uses smart_scheduling module for gap-finding
- Reuses optimizer components (scoring, availability, cooldown)

---

## What We're Adding (Chain Builder v2)

### **New Feature: Manual Build Mode**

Instead of system auto-picking vehicles, let scheduler manually select from dropdowns.

**Backend (New Endpoint)**:
```python
GET /api/chain-builder/get-slot-options
  ?person_id=421
  &slot_index=0
  &slot_start=2025-11-04
  &slot_end=2025-11-11
  &preferred_makes=Toyota,Honda
  &exclude_vins=VIN1,VIN2,VIN3  # Already picked in other slots

Returns: List of 20-50 eligible vehicles for THIS slot
```

**Frontend (New UI)**:
- Toggle button: "Auto-Generate" vs "Manual Build"
- Manual mode shows empty slot cards with dropdowns
- Each dropdown populated from `get-slot-options` endpoint
- Save button activates when all slots have selections

---

## Important Context from This Session

### **Key Decisions Made**:
1. ✅ Chains thread through existing commitments (don't just block dates)
2. ✅ Same-day pickup/dropoff allowed (end one vehicle, start next same day)
3. ✅ Weekend-ending slots auto-extend to Monday
4. ✅ Model diversity is HARD RULE (no duplicate make+model in chain)
5. ✅ Availability grid must cover FULL date range (including extensions)
6. ✅ Save with status='manual' to appear in Calendar tab
7. ✅ Partner selection persists via sessionStorage

### **Common Pitfalls We Fixed**:
- ⚠️ Availability grid not covering last slot → Fixed with explicit end_date
- ⚠️ person_id type mismatches (int vs string) → Always convert to int
- ⚠️ Date parsing timezone issues → Parse as local dates (split on '-')
- ⚠️ Generated chain duplicating with saved chain → Don't clear chain after save
- ⚠️ Slot availability always returning 0 for last slot → Grid coverage issue

---

## File Structure

```
backend/
├── app/
│   ├── routers/
│   │   └── chain_builder.py          # Main API endpoints
│   ├── chain_builder/
│   │   ├── exclusions.py              # VIN filtering, cooldown
│   │   ├── availability.py            # Multi-week availability grid
│   │   └── smart_scheduling.py        # Gap-finding algorithm
│   └── solver/
│       └── scoring.py                 # Vehicle scoring (reused)

frontend/
└── src/
    └── pages/
        └── ChainBuilder.jsx           # Main UI component
```

---

## Key Functions to Understand

### **Smart Scheduling** (`smart_scheduling.py`):
- `get_partner_busy_periods()` - Finds existing commitments
- `find_available_slots()` - Finds gaps between commitments
- `adjust_chain_for_existing_commitments()` - Main entry point

### **Availability** (`availability.py`):
- `build_chain_availability_grid()` - Checks vehicle availability over date range
- `check_slot_availability()` - Verifies vehicle available for specific slot
- `get_available_vehicles_for_slot()` - Returns VINs available for slot

### **Chain Builder Router** (`chain_builder.py`):
- `suggest_chain()` - Auto-generation (current)
- `save_chain()` - Persists to database
- **TODO**: `get_slot_options()` - Returns vehicles for manual selection

---

## Implementation Steps for v2

### **Step 1**: Create `get-slot-options` endpoint
- Accept slot dates + partner info
- Call `get_available_vehicles_for_slot()` to get VINs
- Score vehicles using existing `compute_candidate_scores()`
- Return sorted list with full vehicle details

### **Step 2**: Add mode toggle to frontend
- Radio buttons or tabs: Auto vs Manual
- Show different UI based on mode

### **Step 3**: Build Manual Build UI
- Generate slot cards with dates (no vehicles)
- Each card has dropdown
- Fetch options on-demand when dropdown opens
- Track selections in state

### **Step 4**: Validation & Save
- Ensure all slots filled
- Check no duplicate VINs
- Call existing `save-chain` endpoint

---

## Testing Checklist

- [ ] Manual Build generates correct slot dates
- [ ] Each dropdown shows 20+ eligible vehicles
- [ ] Vehicles sorted by score (best first)
- [ ] Selecting a vehicle excludes it from other slots
- [ ] Model diversity still enforced (or relaxed for manual?)
- [ ] Save works with manually-selected chain
- [ ] Chain appears in Calendar tab
- [ ] Can delete individual vehicles after saving

---

## Open Questions for Next Session

1. **Model diversity in manual mode**: Enforce or allow duplicates?
   - Auto mode: Strict (no duplicate make+model)
   - Manual mode: Warn but allow? Or hard block?

2. **Dropdown size**: Show all vehicles or limit to top 50?

3. **Search in dropdown**: Add search box inside each dropdown?

4. **Partial saves**: Allow saving incomplete chains?

5. **Switch modes**: Can user generate Auto chain, then switch to Manual to tweak?

---

## Git Status

**Latest commit**: `5101c10` - Calendar Make multi-select
**Branch**: `main`
**All changes pushed**: ✅

**Chain Builder v1 is complete and stable.**
**Ready to build v2 on top of it.**

---

## Performance Notes

- Chain Builder handles 1-10 vehicle chains
- Typical response time: <2 seconds
- Smart scheduling can handle partners with 20+ existing commitments
- Availability grid covers up to 70 days (10 slots × 7 days)

---

## For the New Chat to Reference

This session covered:
- Initial Chain Builder implementation (Commits 1-9)
- Smart gap-finding algorithm
- Make filtering
- Save/delete functionality
- UI refinements (timeline, cards, dropdowns)
- Bug fixes (availability grid coverage)

**Total commits this session**: ~20
**Lines of code**: ~2000 (backend + frontend)
**Token usage**: 748K / 1M

Ready to continue with v2! 🚀
