# Getting Started

This guide will help you get started with Media Scheduler and understand its basic navigation and workflows.

## Accessing the Application

Media Scheduler is available at:

- **Production**: [https://media-scheduler.onrender.com](https://media-scheduler.onrender.com)
- **Local Development**: [http://localhost:5173](http://localhost:5173)

## Application Layout

### Navigation Tabs

The application is organized into main sections accessible via the top navigation:

| Tab | Purpose |
|-----|---------|
| **Optimizer** | Run automated assignment optimization for a week |
| **Chain Builder** | Build individual assignment chains for partners or vehicles |
| **Calendar** | View and manage assignments on a timeline |
| **Partners** | Browse and manage media partner information |
| **Publication Rates** | View partner publication success metrics |
| **Availability** | Check data availability and sync status |

### Office Selection

Most views include an office selector dropdown. Select your office to filter vehicles and partners:

- Los Angeles
- New York
- Chicago
- Atlanta
- Detroit
- Dallas
- San Francisco

## Core Workflows

### 1. Running the Optimizer

The Optimizer automatically generates optimal assignments for a week:

1. Go to the **Optimizer** tab
2. Select your office and target week
3. Adjust policy sliders (optional):
   - Local Priority (0-200)
   - Publishing Success (0-300)
   - Tier Cap Penalty
   - Budget awareness
4. Click **Run Optimizer**
5. Review suggested assignments
6. Save approved assignments to the calendar

### 2. Building Chains

Use Chain Builder for manual control over individual assignments:

**Partner Chain Mode**:

1. Select a partner from the dropdown
2. View their profile and preferences
3. Click **Auto Suggest** to generate optimal vehicle chain
4. Drag and drop to adjust assignments
5. Save the chain

**Vehicle Chain Mode**:

1. Toggle to Vehicle mode
2. Select a vehicle from the dropdown
3. View vehicle details and availability
4. Click **Auto Suggest** to generate optimal partner chain
5. Adjust and save

### 3. Managing Assignments

In the Calendar view:

1. View assignments on the timeline
2. Click assignments to see details
3. Drag to reschedule
4. Right-click for context menu options
5. Mark assignments as "requested" to send to FMS

## Assignment Status Colors

| Color | Status | Description |
|-------|--------|-------------|
| Green | Planned | In scheduler, not yet sent to FMS |
| Magenta | Requested | Sent to FMS, awaiting approval |
| Blue | Active | Approved by FMS, confirmed |

## Understanding Context Windows

Click on any vehicle or partner to open a context window with:

- **Vehicle Context**: Recent assignment history, publication data, geographic info
- **Partner Context**: Tier rankings, preferred days, affiliation, budget performance

## Next Steps

- Read the [User Guide](user-guide.md) for detailed feature explanations
- Learn about the [Optimizer](optimizer.md) settings
- Explore the [Chain Builder](chain-builder.md) workflows
- Review [Troubleshooting](troubleshooting.md) for common issues
