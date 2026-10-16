"""Mapping helpers: MongoDB documents -> API response models."""
from __future__ import annotations

from typing import Any

from bson import ObjectId
from bson.errors import InvalidId

from .errors import AttendanceNotFound
from .schemas import AttendanceOut, AuditChange, AuditLogOut, EmployeeOut


def to_object_id(value: str) -> ObjectId:
    """Parse a path/string id, raising a 404 (not a 500) on malformed input."""
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise AttendanceNotFound(f"No attendance record with id {value!r}")


def employee_out(doc: dict[str, Any]) -> EmployeeOut:
    return EmployeeOut(
        id=str(doc["_id"]),
        employee_id=doc["employee_id"],
        name=doc["name"],
        email=doc["email"],
        department=doc["department"],
        shift_start=doc.get("shift_start", "09:00"),
        shift_end=doc.get("shift_end", "18:00"),
        created_at=doc["created_at"],
    )


def attendance_out(doc: dict[str, Any]) -> AttendanceOut:
    return AttendanceOut(
        id=str(doc["_id"]),
        employee_id=doc["employee_id"],
        employee_name=doc.get("employee_name"),
        department=doc.get("department"),
        punch_in=doc["punch_in"],
        punch_out=doc.get("punch_out"),
        worked_minutes=doc.get("worked_minutes"),
        status=doc["status"],
        is_late=doc.get("is_late", False),
        late_by_minutes=doc.get("late_by_minutes", 0),
        flags=doc.get("flags", []),
        source=doc.get("source", "web"),
        note=doc.get("note"),
        is_corrected=doc.get("is_corrected", False),
        correction_count=doc.get("correction_count", 0),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


def audit_out(doc: dict[str, Any]) -> AuditLogOut:
    return AuditLogOut(
        id=str(doc["_id"]),
        entity_type=doc["entity_type"],
        entity_id=doc["entity_id"],
        employee_id=doc["employee_id"],
        action=doc["action"],
        changes=[AuditChange(**c) for c in doc.get("changes", [])],
        reason=doc.get("reason"),
        performed_by=doc["performed_by"],
        performed_at=doc["performed_at"],
    )
