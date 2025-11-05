"""
Pydantic schemas for CSV data validation and ingestion.
Each schema represents the expected structure for CSV uploads.
"""
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, field_validator
from enum import Enum
import pandas as pd


class ActivityTypeEnum(str, Enum):
    loan = "loan"
    service = "service"
    hold = "hold"


class RankEnum(str, Enum):
    A_plus = "A+"
    A = "A"
    B = "B"
    C = "C"
    Pending = "Pending"


class VehicleIngest(BaseModel):
    """Schema for vehicles CSV upload"""
    vehicle_id: Optional[int] = None  # FMS internal vehicle ID (first column in CSV)
    year: Optional[int] = None
    make: str
    model: str
    model_short_name: Optional[str] = None
    office: str
    vin: str
    fleet: Optional[str] = None
    registration_exp: Optional[date] = None
    insurance_exp: Optional[date] = None
    current_mileage: Optional[int] = None
    in_service_date: Optional[date] = None
    expected_turn_in_date: Optional[date] = None
    notes: Optional[str] = None

    @field_validator('vin')
    @classmethod
    def validate_vin(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("VIN cannot be empty")
        return v.strip().upper()

    @field_validator('current_mileage', mode='before')
    @classmethod
    def parse_mileage(cls, v):
        if v and isinstance(v, str):
            # Remove commas from mileage numbers like "2,151"
            return int(v.replace(',', ''))
        return v

    @field_validator('registration_exp', 'insurance_exp', mode='before')
    @classmethod
    def parse_exp_dates(cls, v):
        if v and isinstance(v, str) and v.strip():
            try:
                # Handle MM/DD/YY format
                return datetime.strptime(v, '%m/%d/%y').date()
            except ValueError:
                try:
                    # Fallback to MM/DD/YYYY format
                    return datetime.strptime(v, '%m/%d/%Y').date()
                except ValueError:
                    raise ValueError(f"Invalid date format: {v}")
        return v

    @field_validator('in_service_date', mode='before')
    @classmethod
    def parse_service_date(cls, v):
        if v and isinstance(v, str) and v.strip():
            try:
                # Handle M/YYYY format (like "2/2025")
                month, year = v.split('/')
                return datetime(int(year), int(month), 1).date()
            except (ValueError, IndexError):
                raise ValueError(f"Invalid service date format (expected M/YYYY): {v}")
        return v

    @field_validator('expected_turn_in_date', mode='before')
    @classmethod
    def parse_turn_in_date(cls, v):
        if v and isinstance(v, str) and v.strip():
            try:
                # Handle MM-DD-YY format (like "11-01-25")
                return datetime.strptime(v, '%m-%d-%y').date()
            except ValueError:
                try:
                    # Fallback to MM/DD/YY format
                    return datetime.strptime(v, '%m/%d/%y').date()
                except ValueError:
                    raise ValueError(f"Invalid turn-in date format: {v}")
        return v


class MediaPartnerIngest(BaseModel):
    """Schema for media_partners CSV upload"""
    person_id: str
    name: str
    address: Optional[str] = None
    office: str
    default_loan_region: Optional[str] = None
    notes_instructions: Optional[str] = None

    @field_validator('person_id', mode='before')
    @classmethod
    def validate_person_id(cls, v) -> str:
        if v is None:
            raise ValueError("Person ID cannot be empty")
        # Convert int to string if needed
        v_str = str(v).strip()
        if not v_str:
            raise ValueError("Person ID cannot be empty")
        return v_str


class ApprovedMakesIngest(BaseModel):
    """Schema for approved_makes CSV upload"""
    person_id: str
    name: str
    make: str
    rank: RankEnum

    @field_validator('person_id', mode='before')
    @classmethod
    def validate_person_id(cls, v) -> str:
        if v is None:
            raise ValueError("Person ID cannot be empty")
        # Convert int to string if needed
        v_str = str(v).strip()
        if not v_str:
            raise ValueError("Person ID cannot be empty")
        return v_str

    @field_validator('name', 'make')
    @classmethod
    def validate_required_fields(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("Field cannot be empty")
        return v.strip()

class PartnerMakeRankIngest(BaseModel):
    """Schema for partner_make_rank CSV upload"""
    partner_id: str
    make: str
    rank: RankEnum

    @field_validator('partner_id', 'make')
    @classmethod
    def validate_required_fields(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("Field cannot be empty")
        return v.strip()


class LoanHistoryIngest(BaseModel):
    """Schema for loan_history CSV upload"""
    activity_id: str
    vin: str
    person_id: str
    make: str
    model: str
    year: Optional[int] = None
    model_short_name: Optional[str] = None
    start_date: date
    end_date: date
    office: str
    name: str
    clips_received: Optional[str] = None
    partner_address: Optional[str] = None
    region: Optional[str] = None  # NEW: Region field

    @field_validator('activity_id', 'vin', 'person_id', mode='before')
    @classmethod
    def validate_required_fields(cls, v) -> str:
        if v is None:
            raise ValueError("Field cannot be empty")
        # Convert to string and strip
        v_str = str(v).strip()
        if not v_str:
            raise ValueError("Field cannot be empty")
        return v_str

    @field_validator('start_date', 'end_date', mode='before')
    @classmethod
    def parse_dates(cls, v):
        if v and isinstance(v, str) and v.strip():
            try:
                # Handle MM-DD-YY format (like "08-11-25")
                return datetime.strptime(v, '%m-%d-%y').date()
            except ValueError:
                try:
                    # Fallback to MM/DD/YY format
                    return datetime.strptime(v, '%m/%d/%y').date()
                except ValueError:
                    raise ValueError(f"Invalid date format: {v}")
        return v

    @field_validator('clips_received', mode='before')
    @classmethod
    def parse_clips_received(cls, v):
        """Parse clips_received field to text (preserve original value)."""
        if v is None or pd.isna(v):
            return None
        # Convert to string and strip whitespace
        return str(v).strip() if str(v).strip() else None


class CurrentActivityIngest(BaseModel):
    """Schema for current_activity CSV upload"""
    activity_id: str
    person_id: str  # NEW: Partner ID from second field
    vehicle_vin: str
    activity_type: str
    start_date: date
    end_date: date
    to_field: Optional[str] = None
    partner_address: Optional[str] = None
    region: Optional[str] = None  # NEW: Region field

    @field_validator('activity_id', 'person_id', 'vehicle_vin', mode='before')
    @classmethod
    def validate_required_fields(cls, v) -> str:
        if v is None:
            raise ValueError("Field cannot be empty")
        # Convert to string and strip
        v_str = str(v).strip()
        if not v_str:
            raise ValueError("Field cannot be empty")
        return v_str

    @field_validator('start_date', 'end_date', mode='before')
    @classmethod
    def parse_dates(cls, v):
        if v and isinstance(v, str) and v.strip():
            try:
                # Handle MM-DD-YY format (like "09-26-25")
                return datetime.strptime(v, '%m-%d-%y').date()
            except ValueError:
                try:
                    # Fallback to MM/DD/YY format
                    return datetime.strptime(v, '%m/%d/%y').date()
                except ValueError:
                    raise ValueError(f"Invalid date format: {v}")
        return v


class OpsCapacityIngest(BaseModel):
    """Schema for ops_capacity CSV upload"""
    office: str
    drivers_per_day: int
    notes: Optional[str] = None

    @field_validator('office')
    @classmethod
    def validate_office(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("Office cannot be empty")
        return v.strip()

    @field_validator('drivers_per_day')
    @classmethod
    def validate_capacity(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Drivers per day must be non-negative")
        return v


class HolidayBlackoutDatesIngest(BaseModel):
    """Schema for holiday_blackout_dates CSV upload"""
    office: str
    date: date
    holiday_name: str
    type: str
    all_day: Optional[str] = None  # Changed to text to match table
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    notes: Optional[str] = None  # Changed from 'notea' to 'notes'

    @field_validator('office', 'holiday_name', 'type')
    @classmethod
    def validate_required_fields(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("Field cannot be empty")
        return v.strip()

    @field_validator('date', mode='before')
    @classmethod
    def parse_date(cls, v):
        if v and isinstance(v, str) and v.strip():
            try:
                # Handle YYYY-MM-DD format
                return datetime.strptime(v, '%Y-%m-%d').date()
            except ValueError:
                try:
                    # Handle MM/DD/YYYY format
                    return datetime.strptime(v, '%m/%d/%Y').date()
                except ValueError:
                    try:
                        # Handle MM-DD-YY format
                        return datetime.strptime(v, '%m-%d-%y').date()
                    except ValueError:
                        raise ValueError(f"Invalid date format: {v}")
        return v

    @field_validator('all_day', mode='before')
    @classmethod
    def parse_all_day(cls, v):
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            v_lower = v.lower().strip()
            if v_lower in ['true', '1', 'yes', 'y']:
                return True
            elif v_lower in ['false', '0', 'no', 'n']:
                return False
        return None


class RulesIngest(BaseModel):
    """Schema for rules CSV upload"""
    make: str
    rank: str
    loan_cap_per_year: Optional[int] = None
    publication_rate_requirement: Optional[str] = None  # Fixed column name
    cooldown_period: Optional[int] = None  # Changed to int to match table
    soft_vs_hard_constraint: Optional[str] = None
    rule_description: Optional[str] = None
    notes: Optional[str] = None

    @field_validator('make', 'rank')
    @classmethod
    def validate_required_fields(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("Field cannot be empty")
        return v.strip()

    @field_validator('loan_cap_per_year', mode='before')
    @classmethod
    def parse_loan_cap(cls, v):
        if v is None:
            return None
        if isinstance(v, str) and v.strip():
            try:
                return int(v.strip())
            except ValueError:
                # If it's not a number, store as None
                return None
        return v


class BudgetIngest(BaseModel):
    """Schema for budgets Excel upload"""
    office: str
    fleet: str  # Changed from 'make' to 'fleet'
    year: int
    quarter: str  # Changed to string for "Q1", "Q2", etc.
    budget_amount: Optional[float] = None  # Changed from budget_used/remaining
    amount_used: Optional[float] = None

    @field_validator('office', 'fleet', 'quarter')
    @classmethod
    def validate_required_fields(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("Field cannot be empty")
        return v.strip()

    @field_validator('budget_amount', 'amount_used', mode='before')
    @classmethod
    def parse_currency(cls, v):
        if v is None or pd.isna(v):
            return None
        if isinstance(v, str):
            v_stripped = v.strip()
            if not v_stripped:  # Empty string
                return None
            # Remove $ and commas from currency strings
            cleaned = v_stripped.replace('$', '').replace(',', '')
            try:
                return float(cleaned)
            except ValueError:
                return None
        if isinstance(v, (int, float)):
            return float(v)
        return v

    @field_validator('budget_amount', 'amount_used')
    @classmethod
    def validate_budget_amounts(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("Budget amounts must be non-negative")
        return v


# Mapping of table names to their corresponding schemas
INGEST_SCHEMAS = {
    "vehicles": VehicleIngest,
    "media_partners": MediaPartnerIngest,
    "approved_makes": ApprovedMakesIngest,
    "partner_make_rank": PartnerMakeRankIngest,
    "loan_history": LoanHistoryIngest,
    "current_activity": CurrentActivityIngest,
    "ops_capacity": OpsCapacityIngest,
    "holiday_blackout_dates": HolidayBlackoutDatesIngest,
    "rules": RulesIngest,
    "budgets": BudgetIngest,
}