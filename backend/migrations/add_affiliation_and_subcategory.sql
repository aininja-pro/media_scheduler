-- Migration: Add affiliation and activity_type_subcategory_id to media_partners
-- Date: 2025-01-16
-- Purpose: Support FMS request payload with activity_type and reason fields

-- Add affiliation column (for FMS 'reason' field)
-- This comes from column 7 in the media partners CSV
ALTER TABLE media_partners
ADD COLUMN IF NOT EXISTS affiliation TEXT;

-- Add activity_type_subcategory_id column (for FMS payload)
-- This comes from column 8 in the media partners CSV
ALTER TABLE media_partners
ADD COLUMN IF NOT EXISTS activity_type_subcategory_id INTEGER;

-- Add comments for documentation
COMMENT ON COLUMN media_partners.affiliation IS 'Partner affiliation/reason text from CSV column 7. Used as FMS request reason field.';
COMMENT ON COLUMN media_partners.activity_type_subcategory_id IS 'FMS activity type subcategory ID from CSV column 8. Optional field for FMS requests.';
