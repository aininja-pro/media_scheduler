-- Add address column to media_partners table
-- This field stores the physical address of the media partner

-- Add the column with default value NULL (allowing existing records to have missing data)
ALTER TABLE media_partners
ADD COLUMN address TEXT DEFAULT NULL;

-- Add a comment to document the field
COMMENT ON COLUMN media_partners.address IS 'Physical address of the media partner (street, city, state)';

-- Optional: Create an index for faster address-based queries (useful for geo analysis)
CREATE INDEX IF NOT EXISTS idx_media_partners_address
ON media_partners(address)
WHERE address IS NOT NULL;

-- Verify the column was added
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'media_partners'
AND column_name = 'address';