"""
Pydantic schemas for CSV data validation and ingestion.
Each schema represents the expected structure for CSV uploads.
"""
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, field_validator
from enum import Enum


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
    vin: str
    partner_id: str
    make: str
    model: str
    trim: str
    start_date: date
    end_date: date
    published_bool: bool

    @field_validator('vin', 'partner_id')
    @classmethod
    def validate_required_fields(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("Field cannot be empty")
        return v.strip()


class CurrentActivityIngest(BaseModel):
    """Schema for current_activity CSV upload"""
    vin: str
    activity_type: ActivityTypeEnum
    start_date: date
    end_date: date

    @field_validator('vin')
    @classmethod
    def validate_vin(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("VIN cannot be empty")
        return v.strip().upper()


class OpsCapacityIngest(BaseModel):
    """Schema for ops_capacity CSV upload"""
    office: str
    drivers_per_day: int

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


class BudgetIngest(BaseModel):
    """Schema for budgets CSV upload (optional table)"""
    office: str
    make: str
    year: int
    quarter: int
    budget_used: float
    budget_remaining: float

    @field_validator('quarter')
    @classmethod
    def validate_quarter(cls, v: int) -> int:
        if v not in [1, 2, 3, 4]:
            raise ValueError("Quarter must be 1, 2, 3, or 4")
        return v

    @field_validator('budget_used', 'budget_remaining')
    @classmethod
    def validate_budget_amounts(cls, v: float) -> float:
        if v < 0:
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
    "budgets": BudgetIngest,
}