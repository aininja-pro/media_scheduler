-- Create scheduled_assignments table to persist optimizer output
-- This allows the Calendar view to show planned assignments even after page refresh

CREATE TABLE IF NOT EXISTS scheduled_assignments (
    assignment_id SERIAL PRIMARY KEY,

    -- Assignment details
    vin VARCHAR(17) NOT NULL,
    person_id INTEGER NOT NULL,
    start_day DATE NOT NULL,
    end_day DATE NOT NULL,  -- Calculated as start_day + 7 days

    -- Vehicle info (denormalized for easy querying)
    make VARCHAR(100),
    model VARCHAR(255),
    office VARCHAR(100),

    -- Partner info (denormalized)
    partner_name VARCHAR(255),

    -- Optimizer metadata
    score INTEGER,
    optimizer_run_id UUID,  -- Groups assignments from same optimizer run
    week_start DATE NOT NULL,

    -- Status tracking
    status VARCHAR(50) DEFAULT 'planned',  -- 'planned', 'confirmed', 'cancelled', 'completed'

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_scheduled_assignments_vin
    ON scheduled_assignments(vin);

CREATE INDEX IF NOT EXISTS idx_scheduled_assignments_person_id
    ON scheduled_assignments(person_id);

CREATE INDEX IF NOT EXISTS idx_scheduled_assignments_office
    ON scheduled_assignments(office);

CREATE INDEX IF NOT EXISTS idx_scheduled_assignments_date_range
    ON scheduled_assignments(start_day, end_day);

CREATE INDEX IF NOT EXISTS idx_scheduled_assignments_optimizer_run
    ON scheduled_assignments(optimizer_run_id);

CREATE INDEX IF NOT EXISTS idx_scheduled_assignments_status
    ON scheduled_assignments(status);

-- Composite index for calendar queries
CREATE INDEX IF NOT EXISTS idx_scheduled_assignments_office_dates
    ON scheduled_assignments(office, start_day, end_day);

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_scheduled_assignments_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_scheduled_assignments_updated_at
    BEFORE UPDATE ON scheduled_assignments
    FOR EACH ROW
    EXECUTE FUNCTION update_scheduled_assignments_updated_at();

-- Add comments for documentation
COMMENT ON TABLE scheduled_assignments IS 'Stores optimizer output for calendar view and tracking planned assignments';
COMMENT ON COLUMN scheduled_assignments.optimizer_run_id IS 'UUID grouping all assignments from a single optimizer run';
COMMENT ON COLUMN scheduled_assignments.status IS 'planned: initial state, confirmed: approved by ops, cancelled: removed, completed: loan finished';
COMMENT ON COLUMN scheduled_assignments.end_day IS 'Calculated as start_day + 7 days (standard loan period)';
