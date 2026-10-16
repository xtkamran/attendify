"""Punch-in / punch-out and attendance reads."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from ..config import get_settings
from ..database import get_db
from ..errors import EmployeeNotFound, NoOpenSession, OpenSessionExists
from ..rules import (
    compute_worked_minutes,
    ensure_utc,
    evaluate_flags,
    evaluate_lateness,
    now_utc,
    validate_punch_out,
)
from ..schemas import AttendanceStatus, AttendanceOut, PunchInRequest, PunchOutRequest
from ..serializers import attendance_out, to_object_id

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.post("/punch-in", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
async def punch_in(body: PunchInRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    settings = get_settings()

    employee = await db.employees.find_one({"employee_id": body.employee_id})
    if not employee:
        raise EmployeeNotFound(f"Employee {body.employee_id!r} not found")

    ts = ensure_utc(body.timestamp) if body.timestamp else now_utc()

    # App-level guard (clear 409, testable). The DB partial-unique index below is
    # the real race-condition guarantee for concurrent requests.
    existing = await db.attendance.find_one(
        {"employee_id": body.employee_id, "status": AttendanceStatus.OPEN.value}
    )
    if existing:
        raise OpenSessionExists(
            f"Employee {body.employee_id!r} already has an open session"
        )

    shift_start = employee.get("shift_start", settings.default_shift_start)
    is_late, late_by = evaluate_lateness(ts, shift_start, settings.late_grace_minutes)

    now = now_utc()
    doc = {
        "employee_id": body.employee_id,
        "employee_name": employee.get("name"),
        "department": employee.get("department"),
        "punch_in": ts,
        "punch_out": None,
        "worked_minutes": None,
        "status": AttendanceStatus.OPEN.value,
        "is_late": is_late,
        "late_by_minutes": late_by,
        "flags": [],
        "source": body.source.value,
        "note": body.note,
        "is_corrected": False,
        "correction_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    try:
        res = await db.attendance.insert_one(doc)
    except DuplicateKeyError:
        # Lost the race against a concurrent punch-in; honour the invariant.
        raise OpenSessionExists(
            f"Employee {body.employee_id!r} already has an open session"
        )
    doc["_id"] = res.inserted_id
    return attendance_out(doc)


@router.post("/punch-out", response_model=AttendanceOut)
async def punch_out(body: PunchOutRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    settings = get_settings()

    session = await db.attendance.find_one(
        {"employee_id": body.employee_id, "status": AttendanceStatus.OPEN.value}
    )
    if not session:
        raise NoOpenSession(f"Employee {body.employee_id!r} has no open session to close")

    ts = ensure_utc(body.timestamp) if body.timestamp else now_utc()
    validate_punch_out(session["punch_in"], ts)  # raises InvalidPunchSequence (422)

    worked = compute_worked_minutes(session["punch_in"], ts)
    flags = evaluate_flags(
        session["punch_in"],
        ts,
        worked,
        max_session_minutes=settings.max_session_minutes,
        min_session_minutes=settings.min_session_minutes,
    )

    update = {
        "punch_out": ts,
        "worked_minutes": worked,
        "status": AttendanceStatus.CLOSED.value,
        "flags": flags,
        "updated_at": now_utc(),
    }
    if body.note:
        update["note"] = body.note
    await db.attendance.update_one({"_id": session["_id"]}, {"$set": update})
    session.update(update)
    return attendance_out(session)


@router.get("", response_model=list[AttendanceOut])
async def list_attendance(
    employee_id: str | None = None,
    status_: AttendanceStatus | None = Query(None, alias="status"),
    date_from: datetime | None = Query(None, alias="from"),
    date_to: datetime | None = Query(None, alias="to"),
    limit: int = Query(50, ge=1, le=500),
    skip: int = Query(0, ge=0),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    query: dict = {}
    if employee_id:
        query["employee_id"] = employee_id
    if status_:
        query["status"] = status_.value
    if date_from or date_to:
        window: dict = {}
        if date_from:
            window["$gte"] = ensure_utc(date_from)
        if date_to:
            window["$lte"] = ensure_utc(date_to)
        query["punch_in"] = window
    cursor = db.attendance.find(query).sort("punch_in", -1).skip(skip).limit(limit)
    return [attendance_out(d) async for d in cursor]


@router.get("/{attendance_id}", response_model=AttendanceOut)
async def get_attendance(attendance_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    from ..errors import AttendanceNotFound

    doc = await db.attendance.find_one({"_id": to_object_id(attendance_id)})
    if not doc:
        raise AttendanceNotFound(f"No attendance record with id {attendance_id!r}")
    return attendance_out(doc)
