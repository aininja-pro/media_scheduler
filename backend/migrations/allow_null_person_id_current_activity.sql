-- Allow NULL person_id on current_activity
--
-- Reason: The FMS `current_vehicle_activity.rpt` feed includes activity types
-- that have no associated partner — specifically:
--   - "Hold"
--   - "Hold for Turn In"
--   - "Special"
--   - "Event"
-- These rows arrive with a blank Person_ID. Previously the ingest dropped them
-- silently, so they never reached the calendar. To allow them through, the
-- ingest schema now treats person_id as Optional, which requires the DB column
-- to permit NULL.
--
-- If the column is already nullable, this is a no-op.

ALTER TABLE current_activity
ALTER COLUMN person_id DROP NOT NULL;

COMMENT ON COLUMN current_activity.person_id IS
  'Partner (Person_ID) from FMS. NULL for Hold / Hold for Turn In / Special / Event rows that have no partner assignment.';
