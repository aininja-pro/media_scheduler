-- Add address field to loan_history table
ALTER TABLE loan_history
ADD COLUMN IF NOT EXISTS partner_address TEXT;

-- Add address field to current_activity table  
ALTER TABLE current_activity
ADD COLUMN IF NOT EXISTS partner_address TEXT;

-- Add comment for documentation
COMMENT ON COLUMN loan_history.partner_address IS 'Partner mailing address for the loan';
COMMENT ON COLUMN current_activity.partner_address IS 'Partner mailing address for the current activity';
