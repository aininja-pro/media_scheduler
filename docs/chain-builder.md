# Chain Builder

Chain Builder provides manual control for creating sequential assignment chains for individual partners or vehicles.

## Overview

A "chain" is a sequence of 4-6 non-overlapping assignments that maximizes utilization while respecting all constraints.

### Two Modes

| Mode | Description |
|------|-------------|
| **Partner Chain** | Select a partner, get optimal vehicles |
| **Vehicle Chain** | Select a vehicle, get optimal partners |

## Partner Chain Mode

### When to Use

- Building assignments for a specific partner
- Handling partners the optimizer couldn't serve
- Creating custom schedules for VIP partners

### Workflow

1. Select **Partner Chain** mode (default)
2. Choose an **office**
3. Select a **partner** from the dropdown
4. Review the **partner profile**
5. Click **Auto Suggest** to generate chain
6. **Adjust** as needed with drag-and-drop
7. **Save** the chain

### Partner Profile

The profile panel shows:

- Contact information
- Office affiliation
- Quality tier
- Approved makes with rankings
- Preferred days
- Recent assignment history
- Publication rate

### Auto-Suggested Chain

The system suggests optimal vehicles based on:

- Partner's approved makes (highest-ranked first)
- Vehicle availability
- Cooldown status
- Publication history
- Geographic proximity for handoffs

### Manual Adjustments

**Swap a Vehicle**:

1. Click on a slot in the chain
2. Select a different vehicle from the dropdown
3. System validates the change

**Change Dates**:

1. Drag the assignment to new dates
2. Or click to edit start/end dates directly

**Remove from Chain**:

1. Click the X on any slot
2. Slot becomes empty for replacement

**Add to Chain**:

1. Click empty slot
2. Select vehicle from available options

## Vehicle Chain Mode

### When to Use

- Finding partners for a specific vehicle
- Maximizing utilization of premium vehicles
- Scheduling hard-to-place vehicles

### Workflow

1. Toggle to **Vehicle Chain** mode
2. Choose an **office**
3. Select a **vehicle** from the dropdown
4. Review the **vehicle profile**
5. Click **Auto Suggest** to generate chain
6. **Adjust** as needed
7. **Save** the chain

### Vehicle Profile

The profile panel shows:

- VIN and vehicle ID
- Make, model, year
- Office assignment
- Current status/location
- Recent assignment history
- Available date ranges

### Same-Day Handoff Optimization

Vehicle Chain mode optimizes for geographic efficiency:

- Partners selected to minimize travel between consecutive assignments
- Distance calculations show expected travel
- Green indicators for nearby partners

## Drag-and-Drop Interface

### Moving Assignments

- **Within chain**: Drag to reorder slots
- **Between dates**: Drag to timeline to change dates
- **To trash**: Drag to remove from chain

### Visual Indicators

| Indicator | Meaning |
|-----------|---------|
| Green border | Valid assignment |
| Red border | Constraint violation |
| Yellow warning | Approaching limit |
| Gray slot | Empty/available |

### Conflict Detection

The system warns when:

- Vehicle already assigned for dates
- Partner in cooldown for make
- Capacity exceeded
- Partner unavailable

## Saving Chains

### Save Options

**Save as Planned**:

- Assignments saved with green (planned) status
- Appear in Calendar
- Not yet sent to FMS

**Save and Request**:

- Saves and immediately sends to FMS
- Assignments become magenta (requested)
- Use for urgent scheduling

### Validation

Before saving, the system validates:

- All constraints are satisfied
- No overlapping assignments
- Capacity not exceeded

### Partial Save

If some slots have issues:

1. System highlights problematic slots
2. Choose to save valid slots only
3. Or fix issues and try again

## Smart Scheduling

### Automatic Gap Filling

When you add an assignment, the system:

- Checks partner's existing schedule
- Finds available gaps
- Suggests non-conflicting dates

Cancelled and rejected assignments are ignored — only `planned`, `manual`,
`requested`, and `active` rows occupy a partner. Same-day handoffs are allowed in
both directions: a slot may start the day a loan ends, and end the day one begins.

### Allow Double Booking

Gap filling assumes a partner holds one vehicle at a time. That is wrong for
outlets that take several vehicles at once (Car and Driver) and for partners on a
long-term loan who also review other cars. In those cases gap filling pushes the
chain past the existing loan — potentially months past your chosen start date.

The **Allow Double Booking** toggle (off by default) changes this:

| Toggle | Behavior |
| --- | --- |
| Off | Chain is threaded through the gaps, skipping past existing loans |
| On | Chain runs from your chosen start date; overlaps are flagged, not moved |

With the toggle on, the chain is never shortened or shifted — you get exactly the
slots you asked for, and an amber banner names each slot that double-books the
partner along with what it overlaps. Saving is allowed either way; partner
double-booking has never been blocked at save time (only vehicle double-booking
is, in `_reject_if_chain_conflicts`).

To give one partner several vehicles on the *same* dates, turn the toggle on and
run the builder once per vehicle at the same start date. Slots within a single
chain are always sequential.

Both `GET /suggest-chain` and `GET /get-slot-options` accept
`allow_double_booking`. `/suggest-chain` returns a `schedule_adjustment` object
reporting the requested vs. actual start date and every double-booked slot, which
is what drives the banners in the UI.

### Cooldown Awareness

The system tracks cooldowns per partner-make:

- Shows remaining cooldown days
- Prevents violations
- Suggests when cooldown expires

### Preference Matching

Assignments align with:

- Partner's preferred days
- Partner's make preferences
- Historical success patterns

## Advanced Features

### Manual Slot Editing

For precise control:

1. Click **Edit Slot**
2. Select specific vehicle/partner
3. Set exact start/end dates
4. Add notes if needed

### Chain Templates

Save successful chains as templates:

1. Create and verify a chain
2. Click **Save as Template**
3. Reuse for similar future scheduling

### Bulk Operations

For multiple chains:

1. Create first chain
2. Click **Add Another**
3. Build additional chains
4. Save all at once

## Best Practices

### Partner Chain Tips

- Start with highest-tier partners
- Check publication rates before assigning premium vehicles
- Use preferred days for better partner satisfaction

### Vehicle Chain Tips

- Prioritize vehicles nearing availability end
- Optimize same-day handoffs for logistics efficiency
- Balance make distribution across partners

### General Tips

- Review partner context before building chains
- Check calendar for existing commitments
- Validate before saving to catch issues early
- Use diagnostics to understand rejected suggestions
