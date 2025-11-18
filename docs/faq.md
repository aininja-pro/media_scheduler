# Frequently Asked Questions

## General Questions

### What is Media Scheduler?

Media Scheduler is an optimization system that automatically assigns vehicles to media partners for coverage. It considers multiple factors like publication history, geographic location, partner preferences, and operational constraints to generate optimal assignments.

### Who uses Media Scheduler?

Fleet coordinators, operations managers, and media relations teams at DriveShop use Media Scheduler to plan and manage vehicle loans to media partners.

### How does it integrate with FMS?

Media Scheduler has bi-directional integration with FMS (Fleet Management System). You can create assignments in Media Scheduler and send them to FMS as vehicle requests. FMS approval status syncs back to Media Scheduler automatically.

## Assignments

### What's the difference between Planned, Requested, and Active?

- **Planned (Green)**: Assignment exists only in Media Scheduler
- **Requested (Magenta)**: Sent to FMS, waiting for approval
- **Active (Blue)**: Approved by FMS, confirmed loan

### How long should an assignment be?

Typical loan durations are 5-7 days. The optimizer generates chains with standard durations, but you can adjust them manually in Calendar or Chain Builder.

### Can I assign the same vehicle to the same partner twice?

Yes, but a 30-day cooldown applies per make. If a partner receives a BMW, they can't receive another BMW for 30 days. They can receive other makes during that time.

### What happens if I delete an assignment that's in FMS?

Media Scheduler automatically deletes the corresponding FMS request. The assignment is removed from both systems.

## Optimizer

### How long does optimization take?

Typically 30-60 seconds depending on the number of vehicles and partners. You can adjust the time limit in settings.

### Why didn't a partner get assigned?

Check the diagnostics panel after running. Common reasons:

- Partner in cooldown for available makes
- Partner's approved makes not available
- Partner marked as inactive
- Capacity exceeded

### How do the policy sliders work?

Sliders adjust weights in the optimization algorithm:

- **Higher Local Priority**: Favor partners closer to the office
- **Higher Publishing Success**: Favor partners with better publication rates
- **Higher Tier Cap Penalty**: Stricter enforcement of tier distribution

### Can I run the optimizer for multiple weeks?

Currently, optimization runs for one week at a time. Run it multiple times for consecutive weeks.

## Chain Builder

### When should I use Chain Builder vs Optimizer?

Use **Optimizer** for bulk assignments across all partners. Use **Chain Builder** for:

- Specific partners the optimizer couldn't serve
- VIP partners needing custom schedules
- Hard-to-place vehicles needing partners

### What's a "chain"?

A chain is a sequence of 4-6 consecutive assignments for a partner or vehicle. Each assignment follows the previous one without gaps.

### Can I build partial chains?

Yes, you can save chains with fewer than 4-6 slots. The system shows optimal suggestions but doesn't require them all.

## Calendar

### Why can't I move a blue assignment?

Blue assignments are confirmed in FMS. To change them, you need to modify the request in FMS directly.

### How do I request multiple assignments at once?

Select multiple green assignments using Shift+Click, then use the bulk request option.

### What do the capacity indicators mean?

They show remaining daily capacity for pickups (vehicles returning) and dropoffs (vehicles going out). Red indicates approaching the limit.

## Data & Sync

### When does data sync from FMS?

Automatic sync runs nightly at 2 AM Pacific. You can also trigger manual syncs through the Availability page.

### Why don't I see new partners/vehicles?

They may not have synced yet. Check the last sync time in Availability. Trigger a manual sync if needed.

### How is publication rate calculated?

It's a 24-month rolling average of loans that resulted in media clips. Partners need at least 3 observed loans for a supported rate.

### Can I import data manually?

Yes, administrators can upload CSV files through the data ingestion endpoints. Contact your admin for bulk imports.

## Partners

### How are partner tiers determined?

Tiers (A+, A, B, C) are based on publication success, reach, and historical performance. Tier changes are managed through FMS.

### What are "approved makes"?

The list of vehicle makes a partner is eligible to receive. Partners can only be assigned vehicles from their approved makes list.

### What are "preferred days"?

Days the partner prefers for pickups and dropoffs. The optimizer and Chain Builder try to respect these preferences.

## Technical Questions

### Which browsers are supported?

Media Scheduler works best with:

- Chrome (recommended)
- Firefox
- Safari
- Edge

### Can I use it on mobile?

The interface is optimized for desktop. Basic viewing works on tablets, but editing is best done on larger screens.

### Is there an API?

Yes, Media Scheduler has a REST API. See the [API Reference](api-reference.md) for documentation.

### How do I report a bug?

Submit issues through the project repository with:

- Steps to reproduce
- Expected vs actual behavior
- Screenshots if applicable
- Browser console errors

## Best Practices

### What's the best workflow for weekly planning?

1. Review previous week in Calendar
2. Run Optimizer for next week
3. Review diagnostics
4. Fill gaps with Chain Builder
5. Request ready assignments to FMS

### How can I improve optimization results?

- Ensure data is current (run sync)
- Adjust policy sliders for your priorities
- Review partner approved makes lists
- Check for stale cooldowns

### How do I handle partners with low publication rates?

Options include:

- Assign lower-tier vehicles
- Reduce assignment frequency
- Place under review pending improvement
- Work with them on improvement plan
