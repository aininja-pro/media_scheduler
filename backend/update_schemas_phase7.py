"""
Updates needed to support Phase 7 tables in the application.

This shows what changes are needed in the existing code to support
the new ops_capacity_calendar and model_taxonomy tables.
"""

# 1. Add to app/schemas/ingest.py:

NEW_SCHEMAS = """
class OpsCapacityCalendarIngest(BaseModel):
    \"\"\"Schema for ops_capacity_calendar CSV upload\"\"\"
    office: str
    date: date
    slots: int
    notes: Optional[str] = None

    @field_validator('office')
    def validate_office(cls, v):
        if not v or not v.strip():
            raise ValueError('Office is required')
        return v.strip()

    @field_validator('slots')
    def validate_slots(cls, v):
        if v < 0:
            raise ValueError('Slots cannot be negative')
        return v


class ModelTaxonomyIngest(BaseModel):
    \"\"\"Schema for model_taxonomy CSV upload\"\"\"
    make: str
    model: str
    short_model_class: Optional[str] = None
    powertrain: Optional[str] = None
    body_style: Optional[str] = None
    segment: Optional[str] = None
    notes: Optional[str] = None

    @field_validator('make', 'model')
    def validate_required(cls, v):
        if not v or not v.strip():
            raise ValueError('Make and model are required')
        return v.strip()
"""

# 2. Add to INGEST_SCHEMAS dict in app/schemas/ingest.py:

INGEST_SCHEMAS_UPDATE = """
    "ops_capacity_calendar": OpsCapacityCalendarIngest,
    "model_taxonomy": ModelTaxonomyIngest,
"""

# 3. Add to UPSERT_COLUMNS in app/services/database.py:

UPSERT_COLUMNS_UPDATE = """
    "ops_capacity_calendar": "office,date",  # Composite key
    "model_taxonomy": "make,model",  # Composite key
"""

# 4. Sample CSV format for ops_capacity_calendar:

SAMPLE_OPS_CAPACITY_CALENDAR_CSV = """office,date,slots,notes
Los Angeles,2025-09-22,15,Normal Monday
Los Angeles,2025-09-23,15,Normal Tuesday
Los Angeles,2025-09-24,15,Normal Wednesday
Los Angeles,2025-09-25,15,Normal Thursday
Los Angeles,2025-09-26,15,Normal Friday
Los Angeles,2025-09-27,0,Saturday - closed
Los Angeles,2025-09-28,0,Sunday - closed
Los Angeles,2025-12-25,0,Christmas Day
Los Angeles,2025-12-26,10,Day after Christmas - reduced
Denver,2025-09-22,12,Normal capacity
Denver,2025-09-23,12,Normal capacity
Denver,2025-10-06,8,Driver vacation week
Denver,2025-10-07,8,Driver vacation week
"""

# 5. Sample CSV format for model_taxonomy:

SAMPLE_MODEL_TAXONOMY_CSV = """make,model,short_model_class,powertrain,body_style,segment
Toyota,Camry,Sedan,Hybrid,4-door,Mainstream
Toyota,Corolla,Sedan,Gas,4-door,Mainstream
Toyota,Highlander,SUV,Hybrid,4-door,Mainstream
Toyota,RAV4,SUV,Gas,4-door,Mainstream
Toyota,Tacoma,Truck,Gas,4-door,Mainstream
Honda,Accord,Sedan,Hybrid,4-door,Mainstream
Honda,Civic,Sedan,Gas,4-door,Mainstream
Honda,CR-V,SUV,Gas,4-door,Mainstream
Honda,Pilot,SUV,Gas,4-door,Mainstream
BMW,330i,Sedan,Gas,4-door,Luxury
BMW,X3,SUV,Gas,4-door,Luxury
BMW,X5,SUV,PHEV,4-door,Luxury
Tesla,Model 3,Sedan,EV,4-door,Luxury
Tesla,Model Y,SUV,EV,4-door,Luxury
Tesla,Model S,Sedan,EV,4-door,Luxury
Ford,F-150,Truck,Gas,4-door,Mainstream
Ford,Mustang,Coupe,Gas,2-door,Performance
Ford,Explorer,SUV,Hybrid,4-door,Mainstream
"""

# 6. How to use in the solver (app/routers/solver.py):

SOLVER_USAGE = """
# Load ops_capacity_calendar
ops_calendar_response = db.client.table('ops_capacity_calendar').select('*').execute()
ops_calendar_df = pd.DataFrame(ops_calendar_response.data) if ops_calendar_response.data else pd.DataFrame()

# Load model_taxonomy
taxonomy_response = db.client.table('model_taxonomy').select('*').execute()
taxonomy_df = pd.DataFrame(taxonomy_response.data) if taxonomy_response.data else pd.DataFrame()

# Pass to feasible triples builder
triples = build_feasible_start_day_triples(
    vehicles_df=vehicles,
    partners_df=partners,
    availability_df=availability,
    approved_makes_df=approved_makes,
    ops_capacity_df=ops_calendar_df,  # Daily slots
    model_taxonomy_df=taxonomy_df,    # Model metadata
    week_start=week_start,
    office=office
)
"""

print("Phase 7 Schema Updates")
print("=" * 70)
print("\n1. Run the SQL migration:")
print("   psql -d your_database -f create_phase7_tables.sql")
print("\n2. Update app/schemas/ingest.py with the new schemas above")
print("\n3. Update app/services/database.py with new upsert columns")
print("\n4. Create CSV files for initial data using the samples above")
print("\n5. Upload via the /ingest/{table_name} endpoints")
print("\nThe system will then:")
print("- Use ops_capacity_calendar for daily slot management")
print("- Fall back to ops_capacity.drivers_per_day when no calendar entry exists")
print("- Use model_taxonomy for cooldown grouping (Phase 7.3)")