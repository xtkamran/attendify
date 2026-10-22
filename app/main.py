"""HROne Employee Attendance & Analytics API."""
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import os
import re
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StrictInt, field_validator, model_validator
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

from . import __version__
from .database import connect_to_mongo, close_mongo_connection, get_db
from app.config import get_settings
from app.auth_routes import router as auth_router
from app.auth import get_current_user, require_role

admin_required = require_role("admin")


def authorize_employee_access(emp_code: str, current_user: dict, db):
    """Admins can access all records; employees only their own."""
    if current_user.get("role") == "admin":
        return

    if current_user.get("role") != "employee":
        raise HTTPException(status_code=403, detail="Permission denied")

    user_emp_code = current_user.get("emp_code")
    if not user_emp_code or user_emp_code != emp_code:
        raise HTTPException(
            status_code=403,
            detail="You can access only your own attendance records.",
        )

    employee = db.employees.find_one({"emp_code": user_emp_code})
    if (
        not employee
        or str(employee.get("email", "")).strip().lower()
        != str(current_user.get("email", "")).strip().lower()
    ):
        raise HTTPException(status_code=403, detail="Permission denied")

UTC = timezone.utc
IST = ZoneInfo("Asia/Kolkata")
EMP_RE = re.compile(r"^EMP\d{4,6}$")
MIN_MS, MAX_MS = 100_000_000_000, 4_102_444_800_000
PRESENCE = {"PRESENT", "WFH", "ON_DUTY"}
STATUSES = PRESENCE | {"ABSENT", "LEAVE"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    connect_to_mongo()
    yield
    close_mongo_connection()


app = FastAPI(
    title="Employee Attendance & Analytics API",
    version=__version__,
    lifespan=lifespan,
)

app.include_router(auth_router)

cors_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



def error(code: int, message: str):
    raise HTTPException(status_code=code, detail=message)


def date_value(value: str, field="date") -> date:
    try:
        result = date.fromisoformat(value)
        if result.isoformat() != value:
            raise ValueError()
        return result
    except (ValueError, TypeError):
        error(422, f"{field} must use YYYY-MM-DD")


def month_bounds(month: str):
    if not re.fullmatch(r"\d{4}-\d{2}", month or ""):
        error(422, "month must use YYYY-MM")
    try:
        start = date.fromisoformat(month + "-01")
    except ValueError:
        error(422, "month must use YYYY-MM")
    end = date(start.year + (start.month == 12),
               1 if start.month == 12 else start.month + 1, 1) - timedelta(days=1)
    return start, end


def hhmm(value: str):
    if not isinstance(value, str) or not re.fullmatch(r"\d{2}:\d{2}", value):
        error(422, "Shift time must use HH:MM")
    try:
        return time.fromisoformat(value)
    except ValueError:
        error(422, "Invalid shift time")


def utc_second(dt: datetime):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).replace(microsecond=0)


def timestamp(value):
    if value is None:
        return utc_second(datetime.now(UTC))
    if isinstance(value, bool) or not isinstance(value, int) or not MIN_MS <= value <= MAX_MS:
        error(422, "Timestamp must be an epoch-millisecond integer")
    try:
        return utc_second(datetime.fromtimestamp(value / 1000, UTC))
    except (ValueError, OverflowError, OSError):
        error(422, "Invalid timestamp")


def ms(dt):
    return int(utc_second(dt).timestamp() * 1000) if dt else None


def r2(number):
    return float(Decimal(str(number)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def r4(number):
    return float(Decimal(str(number)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def weekday(day):
    return day.weekday() < 5


def employee_or_404(code):
    employee = get_db().employees.find_one({"emp_code": code})
    if not employee:
        error(404, "Employee not found")
    return employee


def shift_bounds(day, employee):
    d = date_value(day)
    start = hhmm(employee.get("shift_start", "09:30"))
    end = hhmm(employee.get("shift_end", "18:30"))
    start_dt = datetime.combine(d, start, IST)
    end_day = d + timedelta(days=1) if end <= start else d
    end_dt = datetime.combine(end_day, end, IST)
    return start_dt.astimezone(UTC), end_dt.astimezone(UTC)


def attendance_day(punch, employee):
    local = punch.astimezone(IST)
    start = hhmm(employee.get("shift_start", "09:30"))
    end = hhmm(employee.get("shift_end", "18:30"))
    d = local.date()
    if end <= start and local.time().replace(tzinfo=None) < end:
        d -= timedelta(days=1)
    return d.isoformat()


def calculate(record, employee):
    result = dict(record)
    status = result.get("status", "PRESENT")
    result["work_hours"] = None
    result["late_minutes"] = 0
    result["overtime_minutes"] = 0
    result["early_departure_minutes"] = 0
    result["half_day"] = False

    if status in {"ABSENT", "LEAVE"}:
        result["punch_in"] = None
        result["punch_out"] = None
        return result
    if status not in PRESENCE or result.get("punch_in") is None:
        error(422, "Presence status requires punch_in")

    pi = utc_second(result["punch_in"])
    po = utc_second(result["punch_out"]) if result.get("punch_out") else None
    result["punch_in"] = pi
    shift_start, shift_end = shift_bounds(result["date"], employee)

    grace_minutes = get_settings().late_grace_minutes
    if pi > shift_start + timedelta(minutes=grace_minutes):
        result["late_minutes"] = int((pi - shift_start).total_seconds() // 60)
        result["half_day"] = True

    if po:
        duration = (po - pi).total_seconds()
        if duration <= 0 or duration > 86400:
            error(422, "punch_out must be after punch_in and within 24 hours")
        result["punch_out"] = po
        result["work_hours"] = r2(duration / 3600)
        result["half_day"] = result["half_day"] or result["work_hours"] < 4.50
        result["early_departure_minutes"] = max(
            0, int((shift_end - po).total_seconds() // 60)
        )
        overtime = int((po - shift_end).total_seconds() // 60)
        result["overtime_minutes"] = overtime if overtime >= 30 else 0
    return result


def employee_out(doc):
    return {
        "emp_code": doc["emp_code"], "name": doc["name"], "email": doc["email"],
        "department": doc["department"], "shift_start": doc["shift_start"],
        "shift_end": doc["shift_end"], "joined_on": doc["joined_on"],
        "created_at": ms(doc["created_at"]),
    }


def attendance_out(doc):
    history = []
    for entry in doc.get("history", []):
        history.append({
            "changed_at": ms(entry["changed_at"]),
            "reason": entry["reason"],
            "regularized_by": entry["regularized_by"],
            "changes": entry["changes"],
        })
    return {
        "emp_code": doc["emp_code"], "date": doc["date"],
        "status": doc["status"], "punch_in": ms(doc.get("punch_in")),
        "punch_out": ms(doc.get("punch_out")),
        "work_hours": doc.get("work_hours"), "late_minutes": doc.get("late_minutes", 0),
        "overtime_minutes": doc.get("overtime_minutes", 0),
        "early_departure_minutes": doc.get("early_departure_minutes", 0),
        "half_day": doc.get("half_day", False), "history": history,
    }


class EmployeeCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    emp_code: str
    name: str = Field(min_length=1)
    email: EmailStr
    department: str = Field(min_length=1)
    shift_start: str = "09:30"
    shift_end: str = "18:30"
    joined_on: str

    @field_validator("emp_code")
    @classmethod
    def code_valid(cls, value):
        if not EMP_RE.fullmatch(value):
            raise ValueError("emp_code must match EMP followed by 4 to 6 digits")
        return value

    @field_validator("joined_on")
    @classmethod
    def date_valid(cls, value):
        date_value(value, "joined_on")
        return value

    @field_validator("shift_start", "shift_end")
    @classmethod
    def shift_valid(cls, value):
        hhmm(value)
        return value

    @model_validator(mode="after")
    def shifts_differ(self):
        if self.shift_start == self.shift_end:
            raise ValueError("shift_start and shift_end must differ")
        return self


class PunchIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    emp_code: str
    punched_at: StrictInt | None = None
    status: str = "PRESENT"

    @field_validator("status")
    @classmethod
    def status_valid(cls, value):
        if value not in PRESENCE:
            raise ValueError("status must be PRESENT, WFH, or ON_DUTY")
        return value


class PunchOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    emp_code: str
    punched_at: StrictInt | None = None


class AttendancePatch(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: str | None = None
    punch_in: StrictInt | None = None
    punch_out: StrictInt | None = None
    reason: str = Field(min_length=5, max_length=200)
    regularized_by: str = Field(min_length=1, max_length=50)

    @field_validator("status")
    @classmethod
    def status_valid(cls, value):
        if value is not None and value not in STATUSES:
            raise ValueError("Invalid attendance status")
        return value


@app.get("/health")
def health():
    from fastapi import HTTPException
    try:
        get_db().command("ping")
        return {"status": "ok"}
    except Exception:
        raise HTTPException(status_code=503, detail="MongoDB unavailable")


@app.post("/employees", status_code=201)
def create_employee(
    body: EmployeeCreate,
    current_user=Depends(admin_required),
):
    db = get_db()
    doc = body.model_dump()
    doc["created_at"] = utc_second(datetime.now(UTC))
    try:
        db.employees.insert_one(doc)
    except DuplicateKeyError as exc:
        print(f"Duplicate employee insert details: {exc.details}", flush=True)
        error(409, "Duplicate employee code or another unique constraint")
    return employee_out(doc)


@app.get("/employees")
def list_employees(
    department: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(5, ge=1, le=100),
    current_user=Depends(admin_required),
):
    query = {}
    if department is not None:
        query["department"] = department
    if search and search.strip():
        pattern = re.escape(search.strip())
        query["$or"] = [
            {"name": {"$regex": pattern, "$options": "i"}},
            {"emp_code": {"$regex": pattern, "$options": "i"}},
            {"department": {"$regex": pattern, "$options": "i"}},
            {"email": {"$regex": pattern, "$options": "i"}},
        ]

    db = get_db()
    total = db.employees.count_documents(query)
    docs = list(
        db.employees.find(query, {"_id": 0})
        .sort("emp_code", ASCENDING)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    return {
        "items": [employee_out(d) for d in docs],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@app.get("/employees/me")
def get_my_employee_profile(current_user=Depends(get_current_user)):
    if current_user.get("role") != "employee":
        raise HTTPException(
            status_code=403,
            detail="This endpoint is for employee accounts only.",
        )

    emp_code = current_user.get("emp_code")
    if not emp_code:
        raise HTTPException(status_code=403, detail="Employee code is missing.")

    db = get_db()
    authorize_employee_access(emp_code, current_user, db)
    employee = db.employees.find_one({"emp_code": emp_code})

    if not employee:
        raise HTTPException(status_code=404, detail="Employee profile not found.")

    return employee_out(employee)


@app.post("/attendance/punch-in", status_code=201)
def punch_in(body: PunchIn, current_user=Depends(get_current_user)):
    db = get_db()
    authorize_employee_access(body.emp_code, current_user, db)
    pi = timestamp(body.punched_at)
    employee = employee_or_404(body.emp_code)
    day = attendance_day(pi, employee)
    doc = calculate({
        "emp_code": body.emp_code, "department": employee["department"],
        "date": day, "status": body.status, "punch_in": pi, "punch_out": None,
        "history": [], "created_at": pi, "updated_at": pi,
    }, employee)
    try:
        db.attendance_logs.insert_one(doc)
    except DuplicateKeyError:
        error(409, "Attendance already exists for this employee and date")
    return attendance_out(doc)


@app.get("/attendance")
def list_attendance(
    emp_code: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(5, ge=1, le=100),
    current_user=Depends(get_current_user),
):
    query = {}
    if current_user.get("role") == "employee":
        own_code = current_user.get("emp_code")
        if not own_code:
            raise HTTPException(status_code=403, detail="Permission denied")
        if emp_code and emp_code != own_code:
            raise HTTPException(
                status_code=403,
                detail="You can access only your own attendance records.",
            )
        authorize_employee_access(own_code, current_user, get_db())
        query["emp_code"] = own_code
    if emp_code:
        query["emp_code"] = emp_code
    if date_from:
        date_value(date_from, "date_from")
        query.setdefault("date", {})["$gte"] = date_from
    if date_to:
        date_value(date_to, "date_to")
        query.setdefault("date", {})["$lte"] = date_to
    if date_from and date_to and date_from > date_to:
        error(422, "date_from must be on or before date_to")
    if status:
        if status not in STATUSES:
            error(422, "Invalid status")
        query["status"] = status

    if search and search.strip():
        pattern = re.escape(search.strip())
        matching_codes = get_db().employees.distinct(
            "emp_code",
            {
                "$or": [
                    {"name": {"$regex": pattern, "$options": "i"}},
                    {"emp_code": {"$regex": pattern, "$options": "i"}},
                    {"department": {"$regex": pattern, "$options": "i"}},
                    {"email": {"$regex": pattern, "$options": "i"}},
                ]
            },
        )
        search_conditions = [
            {"emp_code": {"$in": matching_codes}},
            {"date": {"$regex": pattern, "$options": "i"}},
            {"status": {"$regex": pattern, "$options": "i"}},
        ]
        query["$and"] = [{"$or": search_conditions}]

    db = get_db()
    total = db.attendance_logs.count_documents(query)
    docs = list(
        db.attendance_logs.find(query, {"_id": 0})
        .sort([("date", DESCENDING), ("emp_code", ASCENDING)])
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    employee_codes = list({d["emp_code"] for d in docs})
    employees_by_code = {
        employee["emp_code"]: employee
        for employee in db.employees.find(
            {"emp_code": {"$in": employee_codes}},
            {
                "_id": 0,
                "emp_code": 1,
                "name": 1,
                "department": 1,
                "shift_start": 1,
                "shift_end": 1,
            },
        )
    } if employee_codes else {}

    items = []
    for doc in docs:
        employee = employees_by_code.get(doc["emp_code"], {})
        item = attendance_out(doc)

        # Recalculate early departure for the response only.
        # Do not modify existing database records.
        punch_out = doc.get("punch_out")
        if punch_out is not None:
            _, shift_end = shift_bounds(doc["date"], employee)
            punch_out = utc_second(punch_out)
            item["early_departure_minutes"] = max(
                0, int((shift_end - punch_out).total_seconds() // 60)
            )
        else:
            item["early_departure_minutes"] = 0

        item["name"] = employee.get("name")
        item["department"] = employee.get("department")
        items.append(item)

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@app.post("/attendance/punch-out")
def punch_out(body: PunchOut, current_user=Depends(get_current_user)):
    db = get_db()
    authorize_employee_access(body.emp_code, current_user, db)
    employee_or_404(body.emp_code)
    po = timestamp(body.punched_at)
    record = db.attendance_logs.find_one(
        {"emp_code": body.emp_code, "punch_in": {"$lte": po},
         "punch_out": None, "status": {"$in": list(PRESENCE)}},
        sort=[("punch_in", DESCENDING)],
    )
    if not record:
        closed = db.attendance_logs.find_one(
            {"emp_code": body.emp_code, "punch_in": {"$lte": po},
             "punch_out": {"$ne": None}, "status": {"$in": list(PRESENCE)}},
            sort=[("punch_in", DESCENDING)],
        )
        if closed:
            error(409, "Attendance record is already closed")
        error(404, "No open attendance record found")
    updated = calculate({**record, "punch_out": po, "updated_at": po},
                        employee_or_404(body.emp_code))
    result = db.attendance_logs.update_one(
        {"emp_code": body.emp_code, "date": record["date"], "punch_out": None},
        {"$set": {k: updated[k] for k in
                  ("punch_out", "work_hours", "late_minutes", "overtime_minutes", "early_departure_minutes", "half_day", "updated_at")}},
    )
    if result.modified_count != 1:
        error(409, "Attendance was updated concurrently")
    return attendance_out(updated)


@app.patch("/attendance/{emp_code}/{attendance_date}")
def patch_attendance(emp_code: str, attendance_date: str, body: AttendancePatch, current_user=Depends(admin_required)):
    date_value(attendance_date)
    db = get_db()
    employee = employee_or_404(emp_code)
    record = db.attendance_logs.find_one({"emp_code": emp_code, "date": attendance_date})
    if not record:
        error(404, "Attendance record not found")

    updated = dict(record)
    if body.status is not None:
        updated["status"] = body.status
    for field in ("punch_in", "punch_out"):
        value = getattr(body, field)
        if value is not None:
            updated[field] = timestamp(value)
    if updated["status"] in {"ABSENT", "LEAVE"}:
        if body.punch_in is not None or body.punch_out is not None:
            error(422, "ABSENT/LEAVE cannot be set with timestamps")
        updated["punch_in"] = updated["punch_out"] = None
    elif updated.get("punch_in") is None:
        error(422, "Presence status requires punch_in")
    elif attendance_day(updated["punch_in"], employee) != attendance_date:
        error(422, "punch_in does not belong to this attendance date")

    updated = calculate(updated, employee)
    def same_value(old, new):
        if isinstance(old, datetime) and isinstance(new, datetime):
            return ms(old) == ms(new)
        return old == new

    changes = {}
    for field in ("status", "punch_in", "punch_out"):
        old, new = record.get(field), updated.get(field)
        if not same_value(old, new):
            changes[field] = {
                "from": ms(old) if isinstance(old, datetime) else old,
                "to": ms(new) if isinstance(new, datetime) else new,
            }

    if not changes:
        error(422, "Patch does not change attendance")

    now = utc_second(datetime.now(UTC))
    history = list(record.get("history", []))
    history.append({
        "changed_at": now, "reason": body.reason,
        "regularized_by": body.regularized_by, "changes": changes,
    })
    updated.update(history=history, reason=body.reason,
                   regularized_by=body.regularized_by, updated_at=now)
    result = db.attendance_logs.replace_one(
        {"emp_code": emp_code, "date": attendance_date,
         "updated_at": record.get("updated_at")}, updated)
    if result.modified_count != 1:
        error(409, "Attendance was updated concurrently")
    return attendance_out(updated)


@app.get("/analytics/employees/{emp_code}/monthly")
def employee_monthly(
    emp_code: str, month: str,
    current_user=Depends(get_current_user),
):
    authorize_employee_access(emp_code, current_user, get_db())
    employee = employee_or_404(emp_code)
    start, end = month_bounds(month)
    joined = date_value(employee["joined_on"], "joined_on")
    first = max(start, joined)
    working_days = sum(weekday(first + timedelta(days=i))
                       for i in range(max(0, (end - first).days + 1)))
    logs = list(get_db().attendance_logs.find({
        "emp_code": emp_code, "date": {"$gte": start.isoformat(), "$lte": end.isoformat()}
    }))
    present = 0.0
    leave = late_count = late_minutes = overtime = 0
    for row in logs:
        is_weekday = weekday(date_value(row["date"]))

        # Late and overtime totals include weekend attendance logs.
        if row.get("late_minutes", 0) > 0:
            late_count += 1
            late_minutes += row["late_minutes"]
        overtime += row.get("overtime_minutes", 0)

        # Attendance and leave days count weekdays only.
        if not is_weekday:
            continue
        if row.get("status") in PRESENCE:
            present += 0.5 if row.get("half_day") else 1.0
        if row.get("status") == "LEAVE":
            leave += 1
    return {
        "emp_code": emp_code, "month": month, "working_days": working_days,
        "present_days": r2(present), "leave_days": leave,
        "late_count": late_count, "total_late_minutes": late_minutes,
        "total_overtime_minutes": overtime,
        "attendance_pct": r4(present / working_days) if working_days else None,
    }


@app.get("/analytics/departments/summary")
def department_summary(month: str, department: str | None = None, current_user=Depends(admin_required)):
    start, end = month_bounds(month)
    db = get_db()

    employee_match = {"joined_on": {"$lte": end.isoformat()}}
    if department:
        employee_match["department"] = department

    pipeline = [
        {"$match": employee_match},
        {"$lookup": {
            "from": "attendance_logs",
            "let": {"code": "$emp_code", "joined": "$joined_on"},
            "pipeline": [
                {"$match": {"$expr": {"$and": [
                    {"$eq": ["$emp_code", "$$code"]},
                    {"$gte": ["$date", start.isoformat()]},
                    {"$lte": ["$date", end.isoformat()]},
                    {"$gte": ["$date", "$$joined"]},
                ]}}},
                {"$set": {"_day": {"$dayOfWeek": {
                    "$dateFromString": {"dateString": "$date"}
                }}}},
            ],
            "as": "logs",
        }},
        {"$set": {
            "_present_days": {"$sum": {"$map": {
                "input": "$logs", "as": "log", "in": {"$cond": [
                    {"$and": [
                        {"$in": ["$$log.status", list(PRESENCE)]},
                        {"$in": ["$$log._day", [2, 3, 4, 5, 6]]},
                    ]},
                    {"$cond": [
                        {"$eq": ["$$log.half_day", True]}, 0.5, 1
                    ]},
                    0,
                ]},
            }}},
            "_hours": {"$map": {
                "input": {"$filter": {
                    "input": "$logs", "as": "log",
                    "cond": {"$and": [
                        {"$in": ["$$log.status", list(PRESENCE)]},
                        {"$ne": [
                            {"$ifNull": ["$$log.work_hours", None]}, None
                        ]},
                    ]},
                }},
                "as": "log", "in": "$$log.work_hours",
            }},
            "_late_count": {"$size": {"$filter": {
                "input": "$logs", "as": "log",
                "cond": {"$gt": [
                    {"$ifNull": ["$$log.late_minutes", 0]}, 0
                ]},
            }}},
            "_late_minutes": {"$sum": {"$map": {
                "input": "$logs", "as": "log",
                "in": {"$ifNull": ["$$log.late_minutes", 0]},
            }}},
            "_leave_count": {"$size": {"$filter": {
                "input": "$logs", "as": "log",
                "cond": {"$eq": ["$$log.status", "LEAVE"]},
            }}},
            "_on_duty_count": {"$size": {"$filter": {
                "input": "$logs", "as": "log",
                "cond": {"$eq": ["$$log.status", "ON_DUTY"]},
            }}},
        }},
        {"$group": {
            "_id": "$department",
            "headcount": {"$sum": 1},
            "present_days": {"$sum": "$_present_days"},
            "hours_sum": {"$sum": {"$sum": "$_hours"}},
            "hours_count": {"$sum": {"$size": "$_hours"}},
            "late_count": {"$sum": "$_late_count"},
            "total_late_minutes": {"$sum": "$_late_minutes"},
            "leave_count": {"$sum": "$_leave_count"},
            "on_duty_count": {"$sum": "$_on_duty_count"},
        }},
        {"$project": {
            "_id": 0,
            "department": "$_id",
            "headcount": 1,
            "present_days": {"$round": ["$present_days", 2]},
            "avg_work_hours": {"$cond": [
                {"$gt": ["$hours_count", 0]},
                {"$round": [
                    {"$divide": ["$hours_sum", "$hours_count"]}, 2
                ]},
                None,
            ]},
            "late_count": 1,
            "total_late_minutes": 1,
            "leave_count": 1,
            "on_duty_count": 1,
        }},
        {"$sort": {"department": 1}},
    ]

    items = list(db.employees.aggregate(pipeline))
    return {"month": month, "items": items}


@app.get("/analytics/leaderboard/late")
def late_leaderboard(month: str, limit: int = Query(10, ge=1, le=50),
                     department: str | None = None, current_user=Depends(admin_required)):
    start, end = month_bounds(month)
    pipeline = [
        {"$match": {
            "date": {"$gte": start.isoformat(), "$lte": end.isoformat()},
            "late_minutes": {"$gt": 0},
        }},
        {"$lookup": {
            "from": "employees",
            "localField": "emp_code",
            "foreignField": "emp_code",
            "as": "employee",
        }},
        {"$unwind": "$employee"},
        {"$match": {"$expr": {"$gte": ["$date", "$employee.joined_on"]}}},
    ]
    if department:
        pipeline.append({"$match": {"employee.department": department}})
    pipeline.extend([
        {"$group": {
            "_id": "$emp_code",
            "total_late_minutes": {"$sum": "$late_minutes"},
            "name": {"$first": "$employee.name"},
            "department": {"$first": "$employee.department"},
        }},
        {"$setWindowFields": {
            "sortBy": {"total_late_minutes": -1},
            "output": {"rank": {"$rank": {}}},
        }},
        {"$match": {"rank": {"$lte": limit}}},
        {"$sort": {"total_late_minutes": -1, "_id": 1}},
        {"$project": {
            "_id": 0,
            "emp_code": "$_id",
            "name": 1,
            "department": 1,
            "total_late_minutes": 1,
            "rank": 1,
        }},
    ])
    return {
        "month": month,
        "items": list(get_db().attendance_logs.aggregate(pipeline)),
    }


@app.get("/analytics/departments/{department}/trend")
def department_trend(department: str, from_date: str = Query(..., alias="from"),
                     to_date: str = Query(..., alias="to"),
                      current_user=Depends(admin_required)):
    start, end = date_value(from_date, "from"), date_value(to_date, "to")
    if end < start or (end - start).days + 1 > 92:
        error(422, "Invalid date range; maximum range is 92 days")
    db = get_db()
    if not db.employees.count_documents({"department": department}):
        error(404, "Department not found")

    # Densify the daily aggregate in MongoDB so dates without attendance remain present.
    lower = datetime.combine(start, time.min, UTC)
    upper = datetime.combine(end + timedelta(days=1), time.min, UTC)
    pipeline = [
        {"$match": {"department": department,
                    "date": {"$gte": start.isoformat(), "$lte": end.isoformat()}}},
        {"$lookup": {
            "from": "employees",
            "localField": "emp_code",
            "foreignField": "emp_code",
            "as": "_employee",
        }},
        {"$unwind": "$_employee"},
        {"$match": {"$expr": {"$gte": ["$date", "$_employee.joined_on"]}}},
        {"$group": {"_id": "$date",
                    "present_count": {"$sum": {"$cond": [
                        {"$in": ["$status", list(PRESENCE)]},
                        {"$cond": ["$half_day", 0.5, 1]}, 0]}},
                    "late_count": {"$sum": {"$cond": [{"$gt": ["$late_minutes", 0]}, 1, 0]}}}},
        {"$project": {"_id": 0, "day": {"$dateFromString": {"dateString": "$_id"}},
                      "present_count": 1, "late_count": 1}},
        {"$densify": {"field": "day", "range": {"step": 1, "unit": "day", "bounds": [lower, upper]}}},
        {"$set": {"present_count": {"$ifNull": ["$present_count", 0]},
                  "late_count": {"$ifNull": ["$late_count", 0]}}},
        {"$lookup": {"from": "employees", "let": {"d": "$day"},
                     "pipeline": [{"$match": {"$expr": {"$and": [
                         {"$eq": ["$department", department]},
                         {"$lte": ["$joined_on", {"$dateToString": {"date": "$$d", "format": "%Y-%m-%d"}}]},
                     ]}}}, {"$count": "n"}], "as": "hc"}},
        {"$set": {"headcount": {"$ifNull": [{"$arrayElemAt": ["$hc.n", 0]}, 0]},
                  "is_working_day": {"$in": [{"$dayOfWeek": "$day"}, [2, 3, 4, 5, 6]]}}},
        {"$set": {"attendance_rate": {"$cond": [
            {"$and": ["$is_working_day", {"$gt": ["$headcount", 0]}]},
            {"$round": [{"$divide": ["$present_count", "$headcount"]}, 4]}, None]}}},
        {"$setWindowFields": {"sortBy": {"day": 1},
                              "output": {"moving_avg_7d": {"$avg": "$attendance_rate",
                              "window": {"range": [-6, 0], "unit": "day"}}}}},
        {"$sort": {"day": 1}},
        {"$project": {"_id": 0, "date": {"$dateToString": {"date": "$day", "format": "%Y-%m-%d"}},
                      "is_working_day": 1, "headcount": 1, "present_count": 1,
                      "late_count": 1, "attendance_rate": 1,
                      "moving_avg_7d": {"$round": ["$moving_avg_7d", 4]}}},
    ]
    return {"department": department, "from": from_date, "to": to_date,
            "items": list(db.attendance_logs.aggregate(pipeline))}


@app.get("/admin/explain/{endpoint}")
def explain_endpoint(
    endpoint: str,
    month: str | None = None,
    emp_code: str | None = None,
    department: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = Query(10, ge=1, le=50),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    current_user=Depends(admin_required),
):
    db = get_db()
    allowed = {
        "attendance_list",
        "employee_monthly",
        "department_summary",
        "late_leaderboard",
        "department_trend",
    }
    if endpoint not in allowed:
        error(422, "Unknown explain endpoint")

    def explain_aggregate(collection, pipeline):
        result = db.command(
            "explain",
            {"aggregate": collection, "pipeline": pipeline, "cursor": {}},
            verbosity="executionStats",
        )
        return {
            "endpoint": endpoint,
            "collection": collection,
            "explain": result,
        }

    if endpoint == "attendance_list":
        query = {}
        if emp_code:
            query["emp_code"] = emp_code
        if date_from:
            date_value(date_from, "date_from")
            query.setdefault("date", {})["$gte"] = date_from
        if date_to:
            date_value(date_to, "date_to")
            query.setdefault("date", {})["$lte"] = date_to
        if date_from and date_to and date_from > date_to:
            error(422, "date_from must be <= date_to")

        result = db.command(
            "explain",
            {
                "find": "attendance_logs",
                "filter": query,
                "sort": {"date": -1, "emp_code": 1},
                "limit": 20,
            },
            verbosity="executionStats",
        )
        return {
            "endpoint": endpoint,
            "collection": "attendance_logs",
            "explain": result,
        }

    if endpoint == "department_trend":
        if not department or not from_date or not to_date:
            error(422, "department, from and to are required")
        start, end = date_value(from_date, "from"), date_value(to_date, "to")
        if end < start or (end - start).days + 1 > 92:
            error(422, "Invalid date range; maximum range is 92 days")

        # Match the actual trend endpoint's initial filtering and daily grouping.
        pipeline = [
            {"$match": {
                "department": department,
                "date": {
                    "$gte": start.isoformat(),
                    "$lte": end.isoformat(),
                },
            }},
            {"$group": {
                "_id": "$date",
                "present_count": {"$sum": {"$cond": [
                    {"$in": ["$status", list(PRESENCE)]},
                    {"$cond": ["$half_day", 0.5, 1]},
                    0,
                ]}},
                "late_count": {"$sum": {"$cond": [
                    {"$gt": ["$late_minutes", 0]}, 1, 0
                ]}},
            }},
            {"$project": {
                "_id": 0,
                "day": {"$dateFromString": {"dateString": "$_id"}},
                "present_count": 1,
                "late_count": 1,
            }},
            {"$densify": {
                "field": "day",
                "range": {
                    "step": 1,
                    "unit": "day",
                    "bounds": [
                        datetime.combine(start, time.min, UTC),
                        datetime.combine(end + timedelta(days=1), time.min, UTC),
                    ],
                },
            }},
        ]
        return explain_aggregate("attendance_logs", pipeline)

    if not month:
        error(422, "month=YYYY-MM is required")
    start, end = month_bounds(month)
    date_filter = {
        "$gte": start.isoformat(),
        "$lte": end.isoformat(),
    }

    if endpoint == "employee_monthly":
        if not emp_code:
            error(422, "emp_code is required")
        pipeline = [
            {"$match": {"emp_code": emp_code, "date": date_filter}},
            {"$sort": {"date": 1}},
        ]
        return explain_aggregate("attendance_logs", pipeline)

    if endpoint == "department_summary":
        employee_match = {"joined_on": {"$lte": end.isoformat()}}
        if department:
            employee_match["department"] = department
        pipeline = [
            {"$match": employee_match},
            {"$lookup": {
                "from": "attendance_logs",
                "let": {"code": "$emp_code"},
                "pipeline": [
                    {"$match": {"$expr": {"$and": [
                        {"$eq": ["$emp_code", "$$code"]},
                        {"$gte": ["$date", start.isoformat()]},
                        {"$lte": ["$date", end.isoformat()]},
                    ]}}},
                ],
                "as": "logs",
            }},
            {"$group": {
                "_id": "$department",
                "headcount": {"$sum": 1},
                "logs": {"$push": "$logs"},
            }},
        ]
        return explain_aggregate("employees", pipeline)

    if endpoint == "late_leaderboard":
        match = {"date": date_filter, "late_minutes": {"$gt": 0}}
        pipeline = [{"$match": match}]
        pipeline.extend([
            {"$group": {
                "_id": "$emp_code",
                "total_late_minutes": {"$sum": "$late_minutes"},
            }},
            {"$lookup": {
                "from": "employees",
                "localField": "_id",
                "foreignField": "emp_code",
                "as": "employee",
            }},
            {"$unwind": "$employee"},
        ])
        if department:
            pipeline.append({"$match": {"employee.department": department}})
        pipeline.extend([
            {"$setWindowFields": {
                "sortBy": {"total_late_minutes": -1},
                "output": {"rank": {"$rank": {}}},
            }},
            {"$match": {"rank": {"$lte": limit}}},
            {"$sort": {"total_late_minutes": -1, "_id": 1}},
            {"$project": {
                "_id": 0,
                "emp_code": "$_id",
                "name": "$employee.name",
                "department": "$employee.department",
                "total_late_minutes": 1,
                "rank": 1,
            }},
        ])
        return explain_aggregate("attendance_logs", pipeline)

    error(422, "Unsupported explain endpoint")
