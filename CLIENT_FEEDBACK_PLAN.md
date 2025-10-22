# Client Feedback - Implementation Plan

**Date:** October 19, 2025
**Status:** Ready for Implementation
**Target:** LA Presentation

---

## Executive Summary

Three key stakeholders provided feedback:
- **Derek Drake (CEO)**: Three-status workflow system
- **Rob Lucier (PE Investor)**: Budget visibility in Chain Builder
- **Dave (Operations)**: Critical fixes and polish items

---

## Three-Status Workflow System

### Current State (2 statuses):
- 🟢 **Green** = Recommended (optimizer/chain builder suggestions)
- 🔵 **Blue** = Committed (confirmed in FMS via current_activity)

### Proposed State (3 statuses):
- 🟢 **Green** (`status='planned'`) = Recommended (not yet sent to FMS)
- 🟵 **Magenta/Pink** (`status='requested'`) = Requested (sent to FMS, awaiting approval)
- 🔵 **Blue** (`status='committed'`) = Committed (FMS confirmed, in current_activity)

### Workflow:
```
[Build Recommendations] → Green bars appear
         ↓
[Click "Request/Commit"] → Magenta bars (sent to FMS)
         ↓
[FMS Approves] → Blue bars appear (via data sync)
         ↓
[Auto-cleanup] → Magenta bars deleted (prevent duplicates)
```

### Technical Implementation:
- Add `status='requested'` to scheduled_assignments
- Update Calendar colors: green, magenta, blue
- Add "Request" button to change green → magenta
- Auto-delete magenta when matching blue appears (VIN + person_id + date match)
- Delete button for green and magenta bars

---

## 🔴 CRITICAL - Before LA Presentation

### 1. Three-Status System ⭐
**Priority:** HIGHEST
**Source:** Derek Drake (CEO)
**Complexity:** Medium
**Time:** 2-3 hours

**What:**
- Add third status "requested" with magenta/pink color
- "Request" button to move green → magenta
- Auto-cleanup when FMS creates matching blue bar
- Delete buttons for green/magenta bars

**Files to modify:**
- `backend/app/routers/calendar.py` - Add status change endpoint
- `backend/app/routers/ui_phase7.py` - Auto-cleanup logic
- `frontend/src/pages/Calendar.jsx` - Magenta color, buttons
- `frontend/src/pages/Optimizer.jsx` - Request button
- `frontend/src/pages/ChainBuilder.jsx` - Request button

---

### 2. Fix Chain Builder 8-Day Loans ⭐
**Priority:** HIGHEST
**Source:** Dave (highlighted)
**Complexity:** Low
**Time:** 30 minutes

**What:**
Currently showing 7-day loans (Tue-Mon) instead of 8 days (Mon-Mon).

**Issue:**
- User sets "8 days per loan"
- System calculates: start_date + (8 - 1) = 7 days
- Should be: start_date + 8 days, ending on the 9th day

**Example:**
- Current: Oct 20 (Mon) + 7 days = Oct 27 (Mon) = 8 days total ✅
- But code might be doing: Oct 20 + 6 days = Oct 26 (Sun) = 7 days ❌

**Fix:**
Check date calculation in:
- `backend/app/chain_builder/smart_scheduling.py`
- Ensure: `end_date = start_date + timedelta(days=days_per_loan - 1)` calculates correctly
- Verify weekend extensions don't break the count

**Files to modify:**
- `backend/app/chain_builder/smart_scheduling.py`
- Verify calculation logic

---

### 3. Media Partner Quality Slider - Fixed Notches ⭐
**Priority:** HIGHEST
**Source:** Dave (highlighted)
**Complexity:** Low
**Time:** 20 minutes

**What:**
Currently: Slider with infinite range (0.0 - 2.0 with 0.1 steps)
Want: 4 discrete options only

**Four Options:**
1. **All Tiers** (A+, A, B, C, D)
2. **B+ and Better** (A+, A, B)
3. **A Tier and Better** (A+, A)
4. **A+ Only**

**Implementation:**
- Change slider to 4-position discrete slider OR dropdown
- Map to weight values:
  - All Tiers → 0.3
  - B+ → 0.8
  - A → 1.2
  - A+ → 1.6

**Files to modify:**
- `frontend/src/pages/Optimizer.jsx` - Change slider to discrete steps

---

### 4. Show Vehicle Availability Conflicts in Dropdowns ⭐
**Priority:** HIGHEST
**Source:** Dave (highlighted)
**Complexity:** Medium
**Time:** 1-2 hours

**What:**
When showing eligible vehicles in Chain Builder dropdowns, indicate if vehicle has activity on the proposed slot dates.

**Display:**
```
Select Vehicle:
┌──────────────────────────────────────────┐
│ Toyota Camry - 1234 (A) - Score: 870    │ ← Available
│ Honda Accord - 5678 (A) - Score: 865    │ ← Available
│ ⚠️ Mazda CX-5 - 9012 (A) - Score: 860   │ ← Has activity on these dates
│ Lexus RX - 3456 (B) - Score: 720        │ ← Available
└──────────────────────────────────────────┘
```

**Logic:**
- Check if vehicle has overlapping activity in slot date range
- Show warning icon if conflict exists
- Still allow selection (maybe scheduler knows it's fine)

**Files to modify:**
- `backend/app/routers/chain_builder.py` - Add conflict check to get-slot-options
- `frontend/src/pages/ChainBuilder.jsx` - Display warning icon in dropdown

---

### 5. VIN Hyperlinks to FMS ⭐
**Priority:** HIGHEST
**Source:** Dave (highlighted)
**Complexity:** Low
**Time:** 30 minutes

**What:**
Make all VINs clickable links to FMS.

**URL Pattern:**
```
https://fms.driveshop.com/list_activities/VEHICLEID
```

**Where to add:**
- Calendar table (VIN column)
- Optimizer assignments table (VIN column)
- Chain Builder vehicle cards (VIN display)
- Any hover tooltips showing VINs

**Implementation:**
```jsx
<a
  href={`https://fms.driveshop.com/list_activities/${vin}`}
  target="_blank"
  rel="noopener noreferrer"
  className="text-blue-600 hover:underline"
>
  {vin}
</a>
```

**Files to modify:**
- `frontend/src/pages/Calendar.jsx`
- `frontend/src/pages/Optimizer.jsx`
- `frontend/src/pages/ChainBuilder.jsx`

---

## 🟡 IMPORTANT - Before LA (Not highlighted but valuable)

### 6. Budget Display in Chain Builder
**Priority:** HIGH
**Source:** Rob Lucier
**Complexity:** Medium
**Time:** 1-2 hours

**What:**
Show Budget Status section in Chain Builder (same as Optimizer).

**Challenges:**
- Chains can span multiple quarters
- Need to calculate costs per quarter

**Solution:**
- Calculate total chain cost using media cost lookup
- Determine which quarter each vehicle falls into
- Show breakdown by quarter if multi-quarter
- Display in right panel of Chain Builder

**Files to modify:**
- `frontend/src/pages/ChainBuilder.jsx` - Add Budget Status section
- Use same component structure as Optimizer

---

### 7. Prevent 3+ Same Make in a Row
**Priority:** MEDIUM
**Source:** Dave's concern
**Complexity:** Low
**Time:** 30 minutes

**What:**
Chain Builder already prevents duplicate models. Add rule: no more than 2 consecutive vehicles from same make.

**Current Rules:**
- ✅ VIN exclusion (partner hasn't been in this VIN)
- ✅ Model diversity (no duplicate make+model in chain)
- ❌ Make repetition limit (NEW)

**New Rule:**
- Allow: Toyota, Honda, Toyota (ok - not consecutive)
- Block: Toyota, Toyota, Toyota (3 in a row)

**Files to modify:**
- `backend/app/routers/chain_builder.py` - Add consecutive make check
- `frontend/src/pages/ChainBuilder.jsx` - Show warning if rule violated

---

### 8. Capacity = 2 Moves per Driver
**Priority:** LOW
**Source:** Dave's note
**Complexity:** Low
**Time:** 15 minutes

**What:**
Display capacity as "drivers" but multiply by 2 for actual slot capacity.

**Current:**
- Input: 5 drivers
- Capacity: 5 slots

**Proposed:**
- Input: 5 drivers
- Capacity: 10 slots (5 × 2)
- Label: "Drivers (2 moves each)"

**Files to modify:**
- `frontend/src/pages/Optimizer.jsx` - Update capacity input label and calculation

---

## 🟢 POST-LA - Polish & Admin Features

### 9. Individual Optimizer Assignment Actions
**Priority:** LOW
**Complexity:** Medium
**Time:** 2-3 hours

**What:**
- Delete individual recommendation
- Swap/find alternatives
- Edit assignment details

**Files to modify:**
- `frontend/src/pages/Optimizer.jsx` - Add action buttons to table rows
- `backend/app/routers/calendar.py` - Individual delete endpoint

---

### 10. Admin: Disable Scheduling for Specific Makes
**Priority:** LOW
**Source:** Dave - client pauses
**Complexity:** Medium
**Time:** 1-2 hours

**What:**
Admin override to block all scheduling for a make (e.g., "No Mercedes this month").

**Implementation:**
- Add `scheduling_disabled` table with make + start_date + end_date
- Filter out disabled makes in optimizer/chain builder
- Admin UI to manage disabled makes

**Files to create:**
- `backend/app/routers/admin.py` - Admin endpoints
- `frontend/src/pages/Admin.jsx` - Admin UI

---

### 11. Hide Scores in Production
**Priority:** LOW
**Source:** Dave's preference
**Complexity:** Very Low
**Time:** 10 minutes

**What:**
Add toggle or env variable to hide scores from schedulers.

**Files to modify:**
- All components showing scores - add conditional display

---

### 12. Hide IDs Everywhere
**Priority:** LOW
**Source:** Dave's preference
**Complexity:** Low
**Time:** 30 minutes

**What:**
Remove person_id, assignment_id displays (keep in code, just hide from UI).

**Files to modify:**
- `frontend/src/pages/Calendar.jsx`
- `frontend/src/pages/Optimizer.jsx`
- `frontend/src/pages/ChainBuilder.jsx`

---

### 13. Verify All Future Activities Display
**Priority:** VERIFY
**Source:** Dave's confirmation
**Complexity:** Testing only
**Time:** 15 minutes

**What:**
Confirm Calendar shows all activity types:
- ✅ Loans
- ✅ Services
- ✅ Holds
- ✅ Other activity types

**Action:** Test and verify, no code changes needed (likely already working)

---

## Implementation Phases

### **Phase 1 - This Chat (Before LA - Critical Items)**
**Estimated Time:** 4-6 hours
**Items:** 1, 2, 3, 4, 5

1. Three-status system (2-3 hours)
2. Fix 8-day loans (30 min)
3. Fixed slider notches (20 min)
4. Vehicle conflict indicators (1-2 hours)
5. VIN hyperlinks (30 min)

### **Phase 2 - Next Session (Before LA - Important Items)**
**Estimated Time:** 2-3 hours
**Items:** 6, 7, 8

6. Chain Builder budget display (1-2 hours)
7. 3+ same make rule (30 min)
8. Capacity × 2 factor (15 min)

### **Phase 3 - Post-LA (Polish)**
**Estimated Time:** 4-6 hours
**Items:** 9, 10, 11, 12, 13

---

## Token Budget Check

**Current usage:** ~273K / 1M tokens (27%)
**Remaining:** 727K tokens

**Can we do Phase 1 in this chat?** YES - plenty of capacity!

---

## Questions Before Starting

1. **Three-status colors:** Green, Magenta, Blue confirmed?
2. **Request button location:** On each assignment row, or bulk action?
3. **Auto-cleanup timing:** During data sync only, or also on manual refresh?
4. **8-day loan fix:** Need to verify current behavior first - is it actually broken?

---

## Next Steps

**Ready to start Phase 1 implementation?**

Let me know if you want to:
- A) Start implementing Phase 1 now
- B) Adjust priorities
- C) Add/remove items from the plan

---

**Last Updated:** 2025-10-19
**Document Owner:** Ray + Claude
**Review with:** Derek, Dave, Rob before LA presentation
