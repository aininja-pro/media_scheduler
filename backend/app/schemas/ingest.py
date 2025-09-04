"""
Pydantic schemas for CSV data validation and ingestion.
Each schema represents the expected structure for CSV uploads.
"""
from datetime import date
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


class VehicleIngest(BaseModel):
    """Schema for vehicles CSV upload"""
    vin: str
    make: str
    model: str
    trim: str
    office: str
    available_from: date
    available_to: date
    status: str

    @field_validator('vin')
    @classmethod
    def validate_vin(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("VIN cannot be empty")
        return v.strip().upper()

    @field_validator('available_from', 'available_to')
    @classmethod
    def validate_dates(cls, v: date) -> date:
        if not v:
            raise ValueError("Date fields cannot be empty")
        return v


class MediaPartnerIngest(BaseModel):
    """Schema for media_partners CSV upload"""
    partner_id: str
    name: str
    office: str
    contact: Optional[Dict[str, Any]] = None
    eligibility_flags: Optional[List[str]] = []
    default_regions: Optional[List[str]] = []

    @field_validator('partner_id')
    @classmethod
    def validate_partner_id(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("Partner ID cannot be empty")
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
    "partner_make_rank": PartnerMakeRankIngest,
    "loan_history": LoanHistoryIngest,
    "current_activity": CurrentActivityIngest,
    "ops_capacity": OpsCapacityIngest,
    "budgets": BudgetIngest,
}