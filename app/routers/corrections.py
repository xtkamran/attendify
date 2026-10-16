"""Manual corrections with an append-only audit trail.

A correction can change ``punch_in`` and/or ``punch_out`` on an existing record.
Every change is:
  * validated (punch_out must stay after punch_in),
  * applied together with recomputed derived fields
    (worked_minutes, lateness, flags, status),
  * recorded in an immutable ``audit_logs`` entry capturing the old and new
    value of each field, who did it, and why.

The audit collection is never updated or deleted from — it is the system of
record for "who changed what, when, and why".
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..config import get_settings
from ..database import get_db
from ..errors import AttendanceNotFound, NothingToCorrect
from ..rules import (
    compute_worked_minutes,
    ensure_utc,
    evaluate_flags,
    evaluate_lateness,
    now_utc,
    validate_punch_out,
)
from ..schemas import AttendanceStatus, AttendanceOut, AuditLogOut, CorrectionRequest
from ..serializers import attendance_out, audit_out, to_object_id

router = APIRouter(prefix="/attendance", tags=["corrections"])


@router.post("/{attendance_id}/corrections", response_model=AttendanceOut)
async def correct_attendance(
    attendance_id: str,
    body: CorrectionRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    settings = get_settings()
    oid = to_object_id(attendance_id)
    doc = await db.attendance.find_one({"_id": oid})
    if not doc:
        raise AttendanceNotFound(f"No attendance record with id {attendance_id!r}")

    # Ensure both old and new values are properly UTC-normalized
    old_pi = ensure_utc(doc["punch_in"])
    old_po = ensure_utc(doc["punch_out"]) if doc.get("punch_out") else None

    new_pi = ensure_utc(body.punch_in) if body.punch_in is not None else old_pi
    new_po = ensure_utc(body.punch_out) if body.punch_out is not None else old_po

    # Collect only genuine changes (compare timestamps to handle precision/tz issues).
    changes: list[dict] = []
    if body.punch_in is not None and int(new_pi.timestamp()) != int(old_pi.timestamp()):
        changes.append({"field": "punch_in", "old": old_pi, "new": new_pi})
    if body.punch_out is not None and old_po is not None and int(new_po.timestamp()) != int(old_po.timestamp()):
        changes.append({"field": "punch_out", "old": old_po, "new": new_po})
    elif body.punch_out is not None and old_po is None and new_po is not None:
        changes.append({"field": "punch_out", "old": old_po, "new": new_po})
    if not changes:
        raise NothingToCorrect("Submitted values are identical to the current record")

    # Validate + recompute derived fields.
    if new_po is not None:
        validate_punch_out(new_pi, new_po)

    employee = await db.employees.find_one({"employee_id": doc["employee_id"]})
    shift_start = (
        employee.get("shift_start", settings.default_shift_start)
        if employee
        else settings.default_shift_start
    )
    is_late, late_by = evaluate_lateness(new_pi, shift_start, settings.late_grace_minutes)

    if new_po is not None:
        worked = compute_worked_minutes(new_pi, new_po)
        flags = evaluate_flags(
            new_pi,
            new_po,
            worked,
            max_session_minutes=settings.max_session_minutes,
            min_session_minutes=settings.min_session_minutes,
        )
        new_status = AttendanceStatus.CLOSED.value
    else:
        worked = None
        flags = []
        new_status = AttendanceStatus.OPEN.value

    now = now_utc()
    update = {
        "punch_in": new_pi,
        "punch_out": new_po,
        "worked_minutes": worked,
        "is_late": is_late,
        "late_by_minutes": late_by,
        "flags": flags,
        "status": new_status,
        "is_corrected": True,
        "correction_count": doc.get("correction_count", 0) + 1,
        "updated_at": now,
    }
    await db.attendance.update_one({"_id": oid}, {"$set": update})

    audit = {
        "entity_type": "attendance",
        "entity_id": attendance_id,
        "employee_id": doc["employee_id"],
        "action": "correction",
        "changes": changes,
        "reason": body.reason,
        "performed_by": body.performed_by,
        "performed_at": now,
    }
    await db.audit_logs.insert_one(audit)

    doc.update(update)
    return attendance_out(doc)


@router.get("/{attendance_id}/audit", response_model=list[AuditLogOut])
async def get_audit_trail(attendance_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    # Validates the id shape (404 on malformed).
    to_object_id(attendance_id)
    cursor = db.audit_logs.find({"entity_id": attendance_id}).sort("performed_at", -1)
    return [audit_out(d) async for d in cursor]
