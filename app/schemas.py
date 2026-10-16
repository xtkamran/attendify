"""Request/response models (Pydantic v2) and shared enums."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .rules import parse_hhmm


class AttendanceStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class PunchSource(str, Enum):
    WEB = "web"
    MOBILE = "mobile"
    BIOMETRIC = "biometric"
    SYSTEM = "system"
    CORRECTION = "correction"


# Employees
class EmployeeIn(BaseModel):
    employee_id: str = Field(..., min_length=1, examples=["E001"])
    name: str = Field(..., min_length=1, examples=["Asha Rao"])
    email: str = Field(..., examples=["asha.rao@example.com"])
    department: str = Field(..., min_length=1, examples=["Engineering"])
    shift_start: str = Field("09:00", examples=["09:00"])
    shift_end: str = Field("18:00", examples=["18:00"])

    @field_validator("shift_start", "shift_end")
    @classmethod
    def _valid_hhmm(cls, v: str) -> str:
        parse_hhmm(v)  # raises ValueError if malformed
        return v


class EmployeeOut(EmployeeIn):
    id: str
    created_at: datetime


# Punch in / out
class PunchInRequest(BaseModel):
    employee_id: str = Field(..., min_length=1)
    timestamp: Optional[datetime] = Field(
        default=None,
        description="Punch time (ISO-8601). Defaults to server time (UTC) if omitted.",
    )
    source: PunchSource = PunchSource.WEB
    note: Optional[str] = None


class PunchOutRequest(PunchInRequest):
    """Same shape as punch-in; kept distinct for a clearer API contract."""


# Corrections
class CorrectionRequest(BaseModel):
    punch_in: Optional[datetime] = None
    punch_out: Optional[datetime] = None
    reason: str = Field(..., min_length=1, description="Why the correction is being made.")
    performed_by: str = Field(..., min_length=1, description="Actor applying the correction.")

    @model_validator(mode="after")
    def _at_least_one_change(self) -> "CorrectionRequest":
        if self.punch_in is None and self.punch_out is None:
            raise ValueError("Provide at least one of punch_in / punch_out to correct.")
        return self


# Responses
class AttendanceOut(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    employee_id: str
    employee_name: Optional[str] = None
    department: Optional[str] = None
    punch_in: datetime
    punch_out: Optional[datetime] = None
    worked_minutes: Optional[int] = None
    status: AttendanceStatus
    is_late: bool = False
    late_by_minutes: int = 0
    flags: list[str] = Field(default_factory=list)
    source: str = "web"
    note: Optional[str] = None
    is_corrected: bool = False
    correction_count: int = 0
    created_at: datetime
    updated_at: datetime


class AuditChange(BaseModel):
    field: str
    old: Optional[Any] = None
    new: Optional[Any] = None


class AuditLogOut(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    employee_id: str
    action: str
    changes: list[AuditChange]
    reason: Optional[str] = None
    performed_by: str
    performed_at: datetime


# Analytics responses
class EmployeeHours(BaseModel):
    employee_id: str
    employee_name: Optional[str] = None
    department: Optional[str] = None
    sessions: int
    total_minutes: int
    total_hours: float
    avg_session_minutes: float


class DailySummary(BaseModel):
    date: str
    sessions: int
    head_count: int
    late_count: int
    total_minutes: int
    total_hours: float


class LateArrival(BaseModel):
    employee_id: str
    employee_name: Optional[str] = None
    department: Optional[str] = None
    late_count: int
    total_late_minutes: int
    avg_late_minutes: float


class DepartmentSummary(BaseModel):
    department: Optional[str] = None
    head_count: int
    sessions: int
    total_hours: float
    avg_hours_per_session: float
    late_count: int


class OvertimeRow(BaseModel):
    employee_id: str
    employee_name: Optional[str] = None
    department: Optional[str] = None
    date: str
    day_minutes: int
    overtime_minutes: int


class ErrorResponse(BaseModel):
    detail: str
    code: str
