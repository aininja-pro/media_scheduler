# Troubleshooting

This guide helps you resolve common issues with Media Scheduler.

## Connection Issues

### Cannot Access Application

**Symptoms**: Browser shows error or blank page

**Solutions**:

1. Check your internet connection
2. Verify the URL is correct
3. Clear browser cache and cookies
4. Try a different browser
5. Check if the service is under maintenance

### API Connection Failed

**Symptoms**: "Failed to fetch" or "Network error" messages

**Solutions**:

1. Refresh the page
2. Check if backend service is running
3. Verify API URL in environment configuration
4. Check browser console for specific errors

### Slow Performance

**Symptoms**: Pages load slowly, actions take long time

**Solutions**:

1. Reduce date range in Calendar view
2. Apply filters to limit data
3. Close unused browser tabs
4. Check your network speed

## Optimizer Issues

### Optimizer Won't Start

**Symptoms**: Run button doesn't respond or shows error

**Solutions**:

1. Ensure office is selected
2. Verify date is selected
3. Check that data has been synced recently
4. Reduce the scope (fewer partners/vehicles)

### No Assignments Generated

**Symptoms**: Optimizer completes but returns zero assignments

**Causes & Solutions**:

| Cause | Solution |
|-------|----------|
| All vehicles assigned | Check calendar for existing assignments |
| All partners in cooldown | Wait for cooldowns to expire |
| Capacity exceeded | Increase daily capacity limits |
| Budget exhausted | Adjust budget constraints |
| No eligible matches | Review approved makes lists |

### Poor Quality Results

**Symptoms**: Assignments don't match expectations

**Solutions**:

1. Review policy slider settings
2. Check partner tier caps
3. Verify publication rates are current
4. Increase solver time limit
5. Run multiple iterations with different settings

### Optimizer Timeout

**Symptoms**: "Optimization timed out" message

**Solutions**:

1. Increase time limit in settings
2. Reduce the number of partners/vehicles
3. Simplify constraints
4. Accept partial results

## Chain Builder Issues

### Auto-Suggest Returns Empty

**Symptoms**: No vehicles/partners suggested

**Causes & Solutions**:

- **Partner has no approved makes**: Add approved makes to partner profile
- **All vehicles assigned**: Check calendar for availability
- **Partner in cooldown for all makes**: Wait for cooldowns
- **No available dates**: Expand date range

### Cannot Save Chain

**Symptoms**: Save button shows error

**Solutions**:

1. Check for constraint violations (red indicators)
2. Verify all slots are valid
3. Ensure no date overlaps
4. Check capacity limits

### Drag-and-Drop Not Working

**Symptoms**: Assignments won't move

**Solutions**:

1. Ensure assignment is selected (highlighted)
2. Check that target slot is valid
3. Verify destination doesn't violate constraints
4. Try refreshing the page

## Calendar Issues

### Assignments Not Showing

**Symptoms**: Calendar appears empty

**Solutions**:

1. Check date range selection
2. Verify filters aren't hiding assignments
3. Select correct office
4. Refresh the page

### Status Colors Wrong

**Symptoms**: Colors don't match expected status

**Understanding Colors**:

- **Green**: Planned (local only)
- **Magenta**: Requested (sent to FMS)
- **Blue**: Active (FMS approved)

If colors seem wrong:

1. Refresh to sync with latest data
2. Check FMS for actual status
3. May be a sync delay

### Cannot Drag Assignments

**Symptoms**: Assignments are stuck

**Solutions**:

1. Blue (active) assignments can't be moved - they're FMS-confirmed
2. Check that target dates are valid
3. Verify capacity isn't exceeded
4. Ensure no conflicting assignments

## FMS Integration Issues

### Request Fails

**Symptoms**: "Failed to create FMS request" error

**Solutions**:

1. Check FMS environment configuration
2. Verify FMS token is valid
3. Ensure FMS service is available
4. Check browser console for details

### Request Stuck on Magenta

**Symptoms**: Assignment stays magenta indefinitely

**Causes**:

- FMS hasn't processed the request yet
- FMS request was rejected
- Sync hasn't run

**Solutions**:

1. Check request directly in FMS
2. Wait for next sync cycle
3. Manually verify status
4. Contact FMS admin if needed

### Cannot Unrequest

**Symptoms**: Unrequest option fails

**Solutions**:

1. Verify assignment is actually in FMS
2. Check if request was already processed
3. May need to delete directly in FMS

## Data Issues

### Missing Partners/Vehicles

**Symptoms**: Expected items not in dropdowns

**Solutions**:

1. Check that data sync has run
2. Verify items exist in FMS
3. Check filter settings
4. May need manual data refresh

### Incorrect Publication Rates

**Symptoms**: Rates don't match expectations

**Understanding Calculation**:

- 24-month rolling window
- Requires 3+ observed loans
- Excludes NULL outcomes

**Solutions**:

1. Check loan history data
2. Verify clips were recorded
3. May need to wait for data update

### Stale Data

**Symptoms**: Information seems outdated

**Solutions**:

1. Check last sync timestamp
2. Trigger manual sync
3. Verify nightly sync is enabled
4. Check sync logs for errors

## Authentication Issues

### Session Expired

**Symptoms**: Suddenly logged out or actions fail

**Solutions**:

1. Refresh the page
2. Log in again
3. Clear cookies if persistent

### Permission Denied

**Symptoms**: "Not authorized" errors

**Solutions**:

1. Verify your role permissions
2. Contact administrator
3. May need elevated access for certain features

## Getting Help

### Collecting Information

Before reporting an issue, gather:

1. Exact error message
2. Steps to reproduce
3. Browser and version
4. Screenshot if visual issue
5. Browser console errors (F12 > Console)

### Error Reporting

Include:

- Description of expected vs actual behavior
- Time when issue occurred
- Any recent changes

### Contact

For urgent issues, contact the development team directly. For non-urgent matters, submit through the project repository.

## Common Error Messages

| Error | Meaning | Action |
|-------|---------|--------|
| "Constraint violation" | Assignment breaks a rule | Check cooldowns, capacity, eligibility |
| "Network error" | Cannot reach server | Check connection, retry |
| "Invalid date range" | Dates are wrong | Verify start < end, valid dates |
| "Capacity exceeded" | Office at limit | Reduce assignments or increase capacity |
| "FMS sync failed" | Cannot reach FMS | Check FMS status, try later |
