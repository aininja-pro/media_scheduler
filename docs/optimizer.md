# Optimizer

The Optimizer is Media Scheduler's core feature that automatically generates optimal vehicle-to-partner assignments using constraint satisfaction algorithms.

## Overview

The Phase 7 Optimizer uses Google OR-Tools CP-SAT solver to:

- Assign vehicles to partners for a target week
- Balance multiple competing objectives
- Respect hard and soft constraints
- Provide diagnostic information for rejected assignments

## Running the Optimizer

### Basic Steps

1. Navigate to the **Optimizer** tab
2. Select your **office** from the dropdown
3. Choose the **target week** using the date picker
4. Review and adjust **policy settings** (optional)
5. Click **Run Optimizer**
6. Review the **results** and **diagnostics**
7. **Save** approved assignments

### Selecting the Target Week

The optimizer generates assignments for a full week (Monday-Sunday). Select any date within your target week.

!!! note
    The optimizer considers existing assignments to avoid conflicts.

## Policy Settings

### Sliders

Adjust these sliders to weight different objectives:

| Slider | Range | Description |
|--------|-------|-------------|
| **Local Priority** | 0-200 | Weight geographic proximity to office |
| **Publishing Success** | 0-300 | Weight partner publication history |
| **Tier Cap Penalty** | 0-1000 | Penalty for exceeding tier soft caps |
| **Fairness Weight** | 0-100 | Incentivize balanced distribution |
| **Budget Weight** | 0-100 | Weight budget awareness |

### Recommended Settings

**Maximize Coverage**:
```
Local Priority: 50
Publishing Success: 250
Tier Cap Penalty: 500
```

**Geographic Efficiency**:
```
Local Priority: 180
Publishing Success: 150
Tier Cap Penalty: 800
```

**Fair Distribution**:
```
Local Priority: 100
Publishing Success: 150
Tier Cap Penalty: 900
Fairness Weight: 80
```

## Constraints

### Hard Constraints

These must be satisfied:

- **Vehicle Availability**: Vehicle must be available for the loan period
- **Partner Eligibility**: Partner must have approved make
- **Cooldown Period**: 30-day gap per partner-make combination
- **Daily Capacity**: Office pickup/dropoff limits
- **Holiday Blackouts**: No assignments on blocked dates

### Soft Constraints

These are optimized but can be relaxed:

- **Tier Caps**: Maximum assignments per quality tier
- **Budget Ceiling**: Fleet budget limits
- **Partner Daily Limits**: Max assignments per partner per day

## Daily Capacity

### Viewing Capacity

The optimizer displays remaining capacity for each day:

| Metric | Description |
|--------|-------------|
| Pickups | Vehicles returning from partners |
| Dropoffs | Vehicles going to partners |
| Swaps | Same-partner vehicle replacements |

### Capacity Overrides

Adjust capacity for specific days:

1. Click **Capacity Settings**
2. Select the day to override
3. Enter new values
4. Save changes

!!! warning
    Overrides apply only to the current optimization run.

## Understanding Results

### Assignment Grid

Results display in a grid showing:

- Partner name and tier
- Assigned vehicle (make/model)
- Loan dates
- Score breakdown

### Score Components

Each assignment shows contributing scores:

- **Publication Score**: Based on partner's publication rate
- **Geographic Score**: Based on distance to office
- **Quality Score**: Based on vehicle-partner tier match
- **Fairness Score**: Based on distribution balance

### Diagnostics Panel

Click **Show Diagnostics** to see:

- Rejected partner-vehicle pairs
- Rejection reasons
- Constraint violations
- Optimization statistics

## Common Rejection Reasons

| Reason | Description | Solution |
|--------|-------------|----------|
| Cooldown Active | Partner recently had this make | Wait for cooldown to expire |
| Not Approved | Partner doesn't accept this make | Check approved makes list |
| No Availability | Partner unavailable for dates | Adjust date range |
| Capacity Exceeded | Office at daily limit | Increase capacity or shift dates |
| Budget Exceeded | Fleet over budget | Reduce assignments or adjust budget |

## Saving Results

### Selective Save

1. Review all suggested assignments
2. Uncheck any you want to exclude
3. Click **Save Selected**
4. Assignments appear in Calendar as green (planned)

### Bulk Save

Click **Save All** to save all suggested assignments at once.

!!! tip
    Review diagnostics before saving to understand any rejected high-priority partners.

## Advanced Usage

### Iterative Optimization

Run multiple iterations with different settings:

1. Run with default settings
2. Note underserved partners in diagnostics
3. Adjust weights to favor those partners
4. Run again and compare results

### Combining with Chain Builder

After optimization:

1. Check for partners without assignments
2. Use Chain Builder to manually create chains
3. This handles edge cases the optimizer couldn't satisfy

### Time Limits

The solver has a configurable time limit (default: 60 seconds). For complex scenarios:

- Increase time limit for better solutions
- Or accept good-enough results faster

## Metrics and Analytics

### Optimization Summary

After each run, view:

- Total assignments created
- Coverage rate by tier
- Budget utilization
- Geographic distribution

### Historical Comparison

Compare current optimization to previous weeks:

- Assignment count trends
- Partner coverage rates
- Publication success correlation
