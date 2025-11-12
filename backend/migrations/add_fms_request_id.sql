-- Migration: Add FMS request ID column to scheduled_assignments
-- Purpose: Store FMS vehicle_request ID for tracking and deletion
-- Date: 2025-11-12

-- Add column to store FMS request ID
ALTER TABLE scheduled_assignments
ADD COLUMN IF NOT EXISTS fms_request_id INTEGER;

-- Add index for faster lookups
CREATE INDEX IF NOT EXISTS idx_scheduled_assignments_fms_request_id
ON scheduled_assignments(fms_request_id);

-- Add comment for documentation
COMMENT ON COLUMN scheduled_assignments.fms_request_id
IS 'FMS vehicle_request ID returned from POST /api/v1/vehicle_requests - used for deletion';
