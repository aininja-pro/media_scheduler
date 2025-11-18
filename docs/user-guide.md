# User Guide

This guide provides comprehensive documentation for all Media Scheduler features and workflows.

## Overview

Media Scheduler helps you efficiently assign vehicles to media partners by:

1. Optimizing assignments based on multiple objectives
2. Respecting operational constraints
3. Integrating with the Fleet Management System (FMS)
4. Providing visual tools for manual adjustments

## Key Concepts

### Partners and Tiers

Media partners are categorized into quality tiers based on their publication history and reach:

| Tier | Description |
|------|-------------|
| A+ | Premium partners with highest publication rates |
| A | High-performing partners |
| B | Standard partners |
| C | Developing partners |

### Approved Makes

Each partner has a list of approved vehicle makes they can receive, along with quality rankings for each make.

### Cooldown Periods

After a partner receives a vehicle of a particular make, they enter a 30-day cooldown period before receiving the same make again. This ensures variety in coverage.

### Publication Rate

A rolling 24-month average of successful media clips generated from vehicle loans. Partners with higher publication rates receive priority for premium vehicles.

## Working with Assignments

### Creating Assignments

Assignments can be created through:

1. **Optimizer**: Automated bulk generation
2. **Chain Builder**: Individual partner/vehicle chains
3. **Calendar**: Direct drag-and-drop creation

### Assignment Lifecycle

1. **Planned** (Green): Created in scheduler
2. **Requested** (Magenta): Sent to FMS for approval
3. **Active** (Blue): Approved and confirmed

### Modifying Assignments

- **Reschedule**: Drag assignment to new dates on calendar
- **Reassign**: Change vehicle or partner in assignment details
- **Delete**: Remove assignment (handles FMS cleanup automatically)

### Requesting Assignments

To send an assignment to FMS:

1. Click on a green (planned) assignment
2. Select "Request" from the context menu
3. Assignment turns magenta while pending
4. Once FMS approves, it becomes blue (active)

## Capacity Management

### Daily Capacity

Each office has daily limits for:

- **Pickups**: Vehicles being picked up from partners
- **Dropoffs**: Vehicles being delivered to partners
- **Same-partner swaps**: Replacing one vehicle with another at the same partner

### Viewing Capacity

The Optimizer shows remaining capacity per day. Red indicators warn when approaching limits.

### Overriding Capacity

Adjust daily capacity overrides in Optimizer settings for special circumstances (events, holidays, etc.).

## Budget Awareness

### Fleet Budgets

Each fleet has quarterly budget allocations that affect assignment costs.

### Cost Calculation

Assignment costs factor in:

- Vehicle tier/value
- Loan duration
- Transportation logistics
- Partner tier

### Budget Constraints

The optimizer can enforce soft or hard budget caps to stay within allocation limits.

## Geographic Optimization

### Distance Scoring

The system calculates distances between:

- Office and partner locations
- Partner-to-partner for same-day handoffs

### Local Priority

Adjust the Local Priority slider to weight geographic proximity in assignments. Higher values favor partners closer to the office.

### Same-Day Handoffs

When ending one loan and starting another on the same day, the system optimizes for minimal travel distance between partners.

## Best Practices

### Weekly Planning Workflow

1. Review previous week's results in Calendar
2. Run Optimizer for upcoming week
3. Review and adjust suggested assignments
4. Save approved assignments
5. Build additional chains as needed
6. Request assignments to FMS

### Balancing Objectives

- **High Publication Rate Focus**: Increase Publishing Success slider
- **Geographic Efficiency**: Increase Local Priority slider
- **Fair Distribution**: Adjust Tier Cap Penalty
- **Budget Conscious**: Enable budget constraints

### Handling Conflicts

When the optimizer can't fulfill all constraints:

1. Review diagnostics for rejection reasons
2. Adjust policy weights
3. Override specific constraints if needed
4. Consider manual assignment via Chain Builder

## Tips and Tricks

- Use keyboard shortcuts in Calendar for faster navigation
- Filter partners by tier to focus on specific segments
- Check Publication Rates before major campaigns
- Review Partner Context to understand preferences
- Use Vehicle Chain mode for hard-to-place vehicles
