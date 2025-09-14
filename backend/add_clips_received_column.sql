-- Add clips_received boolean column to loan_history table
-- This field tracks whether the media partner published content for each loan

-- Add the column with default value NULL (allowing existing records to have missing data)
ALTER TABLE loan_history
ADD COLUMN clips_received BOOLEAN DEFAULT NULL;

-- Add a comment to document the field
COMMENT ON COLUMN loan_history.clips_received IS 'Whether the media partner published content/clips for this loan. NULL = unknown, TRUE = published, FALSE = no publication';

-- Optional: Create an index for faster queries on this field (useful for publication rate calculations)
CREATE INDEX IF NOT EXISTS idx_loan_history_clips_received
ON loan_history(clips_received)
WHERE clips_received IS NOT NULL;

-- Verify the column was added
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'loan_history'
AND column_name = 'clips_received';