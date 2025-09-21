-- SQL migrations for Phase 7 OR-Tools implementation
-- Run these to add the required tables for Phase 7.1

-- 1. Create ops_capacity_calendar table for daily slot management
-- This complements the existing ops_capacity table which provides defaults
CREATE TABLE IF NOT EXISTS public.ops_capacity_calendar (
    id SERIAL PRIMARY KEY,
    office VARCHAR(100) NOT NULL,
    date DATE NOT NULL,
    slots INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Unique constraint to prevent duplicate entries for same office/date
    UNIQUE(office, date)
);

-- Add index for faster lookups
CREATE INDEX IF NOT EXISTS idx_ops_capacity_calendar_office_date
    ON public.ops_capacity_calendar(office, date);

-- Add index for date range queries
CREATE INDEX IF NOT EXISTS idx_ops_capacity_calendar_date
    ON public.ops_capacity_calendar(date);

COMMENT ON TABLE public.ops_capacity_calendar IS
    'Daily delivery slot capacity per office. Overrides default from ops_capacity table.';
COMMENT ON COLUMN public.ops_capacity_calendar.slots IS
    'Number of delivery slots available on this date. 0 means no deliveries (holiday/blackout).';


-- 2. Create model_taxonomy table for vehicle classification
-- Used in Phase 7.3 for model-level cooldown enforcement
CREATE TABLE IF NOT EXISTS public.model_taxonomy (
    id SERIAL PRIMARY KEY,
    make VARCHAR(100) NOT NULL,
    model VARCHAR(100) NOT NULL,
    short_model_class VARCHAR(50),  -- e.g., "Sedan", "SUV", "Truck"
    powertrain VARCHAR(50),         -- e.g., "Gas", "Hybrid", "EV", "PHEV"
    body_style VARCHAR(50),         -- e.g., "4-door", "2-door", "Convertible"
    segment VARCHAR(50),            -- e.g., "Luxury", "Mainstream", "Performance"
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Unique constraint to prevent duplicate make/model entries
    UNIQUE(make, model)
);

-- Add index for faster lookups
CREATE INDEX IF NOT EXISTS idx_model_taxonomy_make_model
    ON public.model_taxonomy(make, model);

COMMENT ON TABLE public.model_taxonomy IS
    'Vehicle classification metadata for enhanced cooldown and assignment logic.';
COMMENT ON COLUMN public.model_taxonomy.short_model_class IS
    'Vehicle class for cooldown grouping (e.g., treat all Sedans similarly).';


-- 3. Optional: Add allowed_start_dows column to media_partners if not exists
-- This allows partners to specify which days they can receive vehicles
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'media_partners'
        AND column_name = 'allowed_start_dows'
    ) THEN
        ALTER TABLE public.media_partners
        ADD COLUMN allowed_start_dows TEXT;

        COMMENT ON COLUMN public.media_partners.allowed_start_dows IS
            'Comma-separated list of allowed start days (e.g., "Mon,Wed,Fri").';
    END IF;
END $$;


-- 4. Sample data for testing

-- Sample ops_capacity_calendar entries (you can delete these after testing)
INSERT INTO public.ops_capacity_calendar (office, date, slots, notes)
VALUES
    -- Normal week in LA
    ('Los Angeles', '2025-09-22', 15, 'Monday - normal capacity'),
    ('Los Angeles', '2025-09-23', 15, 'Tuesday - normal capacity'),
    ('Los Angeles', '2025-09-24', 15, 'Wednesday - normal capacity'),
    ('Los Angeles', '2025-09-25', 15, 'Thursday - normal capacity'),
    ('Los Angeles', '2025-09-26', 15, 'Friday - normal capacity'),

    -- Holiday week example
    ('Los Angeles', '2025-12-24', 8, 'Christmas Eve - half day'),
    ('Los Angeles', '2025-12-25', 0, 'Christmas Day - closed'),
    ('Los Angeles', '2025-12-26', 10, 'Day after Christmas - reduced capacity'),

    -- Denver reduced capacity week
    ('Denver', '2025-10-06', 10, 'Driver vacation - reduced capacity'),
    ('Denver', '2025-10-07', 10, 'Driver vacation - reduced capacity'),
    ('Denver', '2025-10-08', 10, 'Driver vacation - reduced capacity'),
    ('Denver', '2025-10-09', 10, 'Driver vacation - reduced capacity'),
    ('Denver', '2025-10-10', 10, 'Driver vacation - reduced capacity')
ON CONFLICT (office, date) DO UPDATE
    SET slots = EXCLUDED.slots,
        notes = EXCLUDED.notes,
        updated_at = CURRENT_TIMESTAMP;


-- Sample model_taxonomy entries (expand as needed)
INSERT INTO public.model_taxonomy (make, model, short_model_class, powertrain, body_style, segment)
VALUES
    -- Toyota
    ('Toyota', 'Camry', 'Sedan', 'Hybrid', '4-door', 'Mainstream'),
    ('Toyota', 'Corolla', 'Sedan', 'Gas', '4-door', 'Mainstream'),
    ('Toyota', 'Highlander', 'SUV', 'Hybrid', '4-door', 'Mainstream'),
    ('Toyota', 'RAV4', 'SUV', 'Gas', '4-door', 'Mainstream'),
    ('Toyota', 'Tacoma', 'Truck', 'Gas', '4-door', 'Mainstream'),

    -- Honda
    ('Honda', 'Accord', 'Sedan', 'Hybrid', '4-door', 'Mainstream'),
    ('Honda', 'Civic', 'Sedan', 'Gas', '4-door', 'Mainstream'),
    ('Honda', 'CR-V', 'SUV', 'Gas', '4-door', 'Mainstream'),
    ('Honda', 'Pilot', 'SUV', 'Gas', '4-door', 'Mainstream'),

    -- BMW
    ('BMW', '330i', 'Sedan', 'Gas', '4-door', 'Luxury'),
    ('BMW', 'X3', 'SUV', 'Gas', '4-door', 'Luxury'),
    ('BMW', 'X5', 'SUV', 'PHEV', '4-door', 'Luxury'),

    -- Tesla
    ('Tesla', 'Model 3', 'Sedan', 'EV', '4-door', 'Luxury'),
    ('Tesla', 'Model Y', 'SUV', 'EV', '4-door', 'Luxury'),
    ('Tesla', 'Model S', 'Sedan', 'EV', '4-door', 'Luxury')
ON CONFLICT (make, model) DO UPDATE
    SET short_model_class = EXCLUDED.short_model_class,
        powertrain = EXCLUDED.powertrain,
        body_style = EXCLUDED.body_style,
        segment = EXCLUDED.segment,
        updated_at = CURRENT_TIMESTAMP;


-- 5. Grant appropriate permissions (adjust based on your user setup)
-- GRANT ALL ON public.ops_capacity_calendar TO your_app_user;
-- GRANT ALL ON public.model_taxonomy TO your_app_user;


-- 6. How the system will use these tables:

-- The OR-Tools solver will:
-- 1. Check ops_capacity_calendar for specific date slots
-- 2. Fall back to ops_capacity.drivers_per_day as default
-- 3. Use model_taxonomy for cooldown grouping in Phase 7.3

-- Example query to get slots for a date:
-- SELECT
--     COALESCE(occ.slots, oc.drivers_per_day, 15) as available_slots
-- FROM
--     (SELECT 'Los Angeles' as office, '2025-09-22'::date as target_date) params
-- LEFT JOIN ops_capacity_calendar occ
--     ON occ.office = params.office AND occ.date = params.target_date
-- LEFT JOIN ops_capacity oc
--     ON oc.office = params.office;