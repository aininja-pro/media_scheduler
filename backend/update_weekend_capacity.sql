-- Update ops_capacity_calendar to set weekend capacity to 0
-- This reflects that we don't do deliveries/starts on weekends

-- Set all Saturday and Sunday slots to 0
UPDATE public.ops_capacity_calendar
SET
    slots = 0,
    notes = 'No weekend deliveries'
WHERE EXTRACT(DOW FROM date) IN (0, 6);  -- 0 = Sunday, 6 = Saturday

-- Verify the update
SELECT
    office,
    date,
    TO_CHAR(date, 'Day') as day_name,
    slots,
    notes
FROM public.ops_capacity_calendar
WHERE date >= '2025-09-22'
  AND date < '2025-09-29'
ORDER BY office, date;