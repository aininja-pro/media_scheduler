-- Migration script to populate Phase 7 tables with REAL data from existing tables
-- This preserves your production data while setting up the new structure

-- ============================================================================
-- 1. CLEAR THE SAMPLE DATA (if you ran the previous script)
-- ============================================================================

TRUNCATE TABLE public.ops_capacity_calendar;
TRUNCATE TABLE public.model_taxonomy;


-- ============================================================================
-- 2. POPULATE ops_capacity_calendar FROM EXISTING ops_capacity
-- ============================================================================

-- Generate default calendar entries for the next 90 days based on current ops_capacity
-- This gives you a starting point that matches your current capacity settings

WITH date_series AS (
    -- Generate dates for next 90 days
    SELECT generate_series(
        CURRENT_DATE,
        CURRENT_DATE + INTERVAL '90 days',
        '1 day'::interval
    )::date AS date
),
office_dates AS (
    -- Create office/date combinations for weekdays only
    SELECT
        oc.office,
        ds.date,
        oc.drivers_per_day as slots,
        CASE
            WHEN EXTRACT(DOW FROM ds.date) IN (0, 6) THEN 'Weekend - typically no deliveries'
            ELSE 'Default capacity from ops_capacity table'
        END as notes
    FROM public.ops_capacity oc
    CROSS JOIN date_series ds
    WHERE EXTRACT(DOW FROM ds.date) BETWEEN 1 AND 5  -- Monday = 1, Friday = 5
)
INSERT INTO public.ops_capacity_calendar (office, date, slots, notes)
SELECT
    office,
    date,
    slots,
    notes
FROM office_dates
ON CONFLICT (office, date) DO NOTHING;

-- Show what was created
SELECT
    office,
    COUNT(*) as days_created,
    MIN(date) as first_date,
    MAX(date) as last_date,
    AVG(slots) as avg_slots
FROM public.ops_capacity_calendar
GROUP BY office
ORDER BY office;


-- ============================================================================
-- 3. POPULATE model_taxonomy FROM EXISTING VEHICLE DATA
-- ============================================================================

-- Extract unique make/model combinations from vehicles table
-- This ensures we have taxonomy for all vehicles actually in your fleet

INSERT INTO public.model_taxonomy (make, model, short_model_class, powertrain)
SELECT DISTINCT
    v.make,
    v.model,
    -- Intelligent classification based on model names
    CASE
        -- SUVs and Crossovers
        WHEN LOWER(v.model) LIKE '%suv%' OR LOWER(v.model) LIKE '%crossover%' THEN 'SUV'
        WHEN LOWER(v.model) IN ('highlander', 'pilot', 'explorer', 'tahoe', 'expedition', 'suburban') THEN 'SUV'
        WHEN LOWER(v.model) IN ('rav4', 'cr-v', 'cx-5', 'cx-9', 'rdx', 'mdx', 'q5', 'q7', 'x3', 'x5') THEN 'SUV'
        WHEN LOWER(v.model) IN ('atlas', 'tiguan', 'touareg', 'cayenne', 'macan') THEN 'SUV'
        WHEN LOWER(v.model) IN ('4runner', 'land cruiser', 'sequoia', 'armada', 'pathfinder') THEN 'SUV'

        -- Trucks
        WHEN LOWER(v.model) LIKE '%truck%' OR LOWER(v.model) LIKE '%pickup%' THEN 'Truck'
        WHEN LOWER(v.model) IN ('f-150', 'f150', 'f-250', 'f250', 'silverado', 'sierra', 'ram', 'tundra', 'titan', 'tacoma', 'ranger', 'colorado', 'canyon', 'ridgeline', 'gladiator') THEN 'Truck'

        -- Vans
        WHEN LOWER(v.model) LIKE '%van%' OR LOWER(v.model) LIKE '%minivan%' THEN 'Van'
        WHEN LOWER(v.model) IN ('odyssey', 'sienna', 'pacifica', 'carnival') THEN 'Van'

        -- Coupes and Sports Cars
        WHEN LOWER(v.model) LIKE '%coupe%' OR LOWER(v.model) LIKE '%convertible%' THEN 'Coupe'
        WHEN LOWER(v.model) IN ('mustang', 'camaro', 'challenger', 'corvette', '911', 'cayman', 'boxster') THEN 'Coupe'
        WHEN LOWER(v.model) IN ('miata', 'mx-5', 'brz', 'gr86', 'supra', 'z4') THEN 'Coupe'

        -- Hatchbacks
        WHEN LOWER(v.model) LIKE '%hatchback%' OR LOWER(v.model) LIKE '%hatch%' THEN 'Hatchback'
        WHEN LOWER(v.model) IN ('golf', 'gti', 'civic hatchback', 'mazda3 hatchback', 'impreza') THEN 'Hatchback'

        -- Wagons
        WHEN LOWER(v.model) LIKE '%wagon%' OR LOWER(v.model) LIKE '%estate%' THEN 'Wagon'
        WHEN LOWER(v.model) IN ('outback', 'v60', 'v90', 'e-class wagon', 'alltrack') THEN 'Wagon'

        -- Default to Sedan for everything else (most common)
        ELSE 'Sedan'
    END AS short_model_class,

    -- Intelligent powertrain detection based on model name patterns
    CASE
        WHEN LOWER(v.model) LIKE '%hybrid%' OR LOWER(v.model) LIKE '% hv%' THEN 'Hybrid'
        WHEN LOWER(v.model) LIKE '%phev%' OR LOWER(v.model) LIKE '%plug-in%' THEN 'PHEV'
        WHEN LOWER(v.model) LIKE '%electric%' OR LOWER(v.model) LIKE '% ev%' THEN 'EV'
        WHEN LOWER(v.model) LIKE '%e-tron%' OR v.make = 'Tesla' THEN 'EV'
        WHEN LOWER(v.model) LIKE '%diesel%' OR LOWER(v.model) LIKE '% tdi%' THEN 'Diesel'
        ELSE 'Gas'  -- Default assumption
    END AS powertrain
FROM public.vehicles v
WHERE v.make IS NOT NULL
    AND v.model IS NOT NULL
    AND v.make != ''
    AND v.model != ''
ON CONFLICT (make, model) DO NOTHING;

-- Show what was created
SELECT
    short_model_class,
    COUNT(*) as model_count,
    STRING_AGG(DISTINCT make, ', ' ORDER BY make) as makes_with_class
FROM public.model_taxonomy
GROUP BY short_model_class
ORDER BY model_count DESC;

-- Show powertrain distribution
SELECT
    powertrain,
    COUNT(*) as model_count,
    STRING_AGG(DISTINCT make, ', ' ORDER BY make) as makes_with_powertrain
FROM public.model_taxonomy
GROUP BY powertrain
ORDER BY model_count DESC;


-- ============================================================================
-- 4. ADD CRITICAL DATES TO ops_capacity_calendar
-- ============================================================================

-- Add known holidays with 0 capacity
-- Adjust these dates for your business calendar

INSERT INTO public.ops_capacity_calendar (office, date, slots, notes)
SELECT
    office,
    holiday_date,
    0 as slots,
    holiday_name as notes
FROM public.ops_capacity
CROSS JOIN (
    VALUES
        ('2025-01-01'::date, 'New Year''s Day'),
        ('2025-01-20'::date, 'MLK Day'),
        ('2025-02-17'::date, 'Presidents Day'),
        ('2025-05-26'::date, 'Memorial Day'),
        ('2025-07-04'::date, 'Independence Day'),
        ('2025-09-01'::date, 'Labor Day'),
        ('2025-11-27'::date, 'Thanksgiving'),
        ('2025-11-28'::date, 'Black Friday'),
        ('2025-12-24'::date, 'Christmas Eve'),
        ('2025-12-25'::date, 'Christmas Day'),
        ('2025-12-26'::date, 'Day after Christmas'),
        ('2025-12-31'::date, 'New Year''s Eve')
) AS holidays(holiday_date, holiday_name)
ON CONFLICT (office, date) DO UPDATE
    SET slots = 0,
        notes = EXCLUDED.notes;


-- ============================================================================
-- 5. VERIFICATION QUERIES
-- ============================================================================

-- Check ops_capacity_calendar population
SELECT
    'ops_capacity_calendar' as table_name,
    COUNT(*) as total_records,
    COUNT(DISTINCT office) as unique_offices,
    MIN(date) as earliest_date,
    MAX(date) as latest_date
FROM public.ops_capacity_calendar

UNION ALL

-- Check model_taxonomy population
SELECT
    'model_taxonomy' as table_name,
    COUNT(*) as total_records,
    COUNT(DISTINCT make) as unique_makes,
    NULL as earliest_date,
    NULL as latest_date
FROM public.model_taxonomy;


-- ============================================================================
-- 6. SAMPLE QUERIES TO VERIFY DATA QUALITY
-- ============================================================================

-- Show a week of LA capacity as example
SELECT
    office,
    date,
    TO_CHAR(date, 'Day') as day_of_week,
    slots,
    notes
FROM public.ops_capacity_calendar
WHERE office = 'Los Angeles'
    AND date BETWEEN '2025-09-22' AND '2025-09-28'
ORDER BY date;

-- Show some vehicle classifications
SELECT
    make,
    model,
    short_model_class,
    powertrain
FROM public.model_taxonomy
WHERE make IN ('Toyota', 'Honda', 'Ford')
ORDER BY make, model
LIMIT 20;


-- ============================================================================
-- 7. NOTES FOR MANUAL REVIEW
-- ============================================================================

/*
AFTER RUNNING THIS MIGRATION:

1. Review the model_taxonomy classifications:
   - The script makes intelligent guesses based on model names
   - You should review and correct any misclassifications
   - Add body_style and segment data as needed

2. Review the ops_capacity_calendar:
   - Default weekday capacity matches your current ops_capacity table
   - Weekends are excluded (adjust if you do weekend deliveries)
   - Major holidays are set to 0 capacity

3. Work with your client to:
   - Identify any special reduced-capacity days
   - Get accurate model classifications if available
   - Confirm holiday schedule

4. Consider creating CSV exports for client review:

   COPY (
       SELECT * FROM public.model_taxonomy
       ORDER BY make, model
   ) TO '/tmp/model_taxonomy_review.csv' CSV HEADER;

   COPY (
       SELECT * FROM public.ops_capacity_calendar
       WHERE date BETWEEN '2025-09-01' AND '2025-10-31'
       ORDER BY office, date
   ) TO '/tmp/ops_capacity_review.csv' CSV HEADER;
*/