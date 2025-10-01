-- Add preferred_day_of_week columns to media_partners table
-- Run this SQL in Supabase SQL Editor

-- Add preferred_day_of_week column (stores the most common pickup day)
ALTER TABLE media_partners
ADD COLUMN IF NOT EXISTS preferred_day_of_week TEXT CHECK (preferred_day_of_week IN ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'));

-- Add confidence score column (percentage 0-100)
ALTER TABLE media_partners
ADD COLUMN IF NOT EXISTS preferred_day_confidence DECIMAL(5,2);

-- Add index for faster filtering by office and preferred day
CREATE INDEX IF NOT EXISTS idx_media_partners_preferred_day
ON media_partners(office, preferred_day_of_week)
WHERE preferred_day_of_week IS NOT NULL;

-- Add comment to document the columns
COMMENT ON COLUMN media_partners.preferred_day_of_week IS 'Most common day of week for this partner-office combination based on loan_history. Calculated by analyze_preferred_days.py and updated via update_preferred_days.py';

COMMENT ON COLUMN media_partners.preferred_day_confidence IS 'Confidence percentage (0-100) that this is the preferred day. Based on weighted loan history with recent loans weighted 2x.';
