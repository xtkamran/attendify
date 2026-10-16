"""Analytics endpoints — all powered by MongoDB aggregation pipelines.

Design note: the heavy lifting (grouping, counting, date bucketing, overtime
math) is pushed into the database with ``$match / $group / $project / $facet``
so we move as little data over the wire as possible and let the server use its
indexes. ``/analytics/hours`` intentionally does the final rounding in Python so
there is at least one endpoint that runs on any MongoDB-compatible engine; the
others use richer in-pipeline operators (``$round``, ``$dateToString`` …).
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..config import get_settings
from ..database import get_db
from ..rules import ensure_utc
from ..schemas import (
    DailySummary,
    DepartmentSummary,
    EmployeeHours,
    LateArrival,
    OvertimeRow,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _punch_in_range(
    date_from: datetime | None, date_to: datetime | None
) -> dict:
    """Build a ``punch_in`` range filter fragment."""
    window: dict = {}
    if date_from:
        window["$gte"] = ensure_utc(date_from)
    if date_to:
        window["$lte"] = ensure_utc(date_to)
    return {"punch_in": window} if window else {}


@router.get("/hours", response_model=list[EmployeeHours])
async def hours_per_employee(
    employee_id: str | None = None,
    date_from: datetime | None = Query(None, alias="from"),
    date_to: datetime | None = Query(None, alias="to"),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Total / average worked time per employee over a window (closed sessions)."""
    match: dict = {"status": "closed", **_punch_in_range(date_from, date_to)}
    if employee_id:
        match["employee_id"] = employee_id

    pipeline = [
        {"$match": match},
        {
            "$group": {
                "_id": "$employee_id",
                "employee_name": {"$first": "$employee_name"},
                "department": {"$first": "$department"},
                "sessions": {"$sum": 1},
                "total_minutes": {"$sum": "$worked_minutes"},
            }
        },
        {"$sort": {"total_minutes": -1}},
    ]
    rows = await db.attendance.aggregate(pipeline).to_list(length=None)
    out: list[EmployeeHours] = []
    for r in rows:
        total = int(r.get("total_minutes") or 0)
        sessions = int(r.get("sessions") or 0)
        out.append(
            EmployeeHours(
                employee_id=r["_id"],
                employee_name=r.get("employee_name"),
                department=r.get("department"),
                sessions=sessions,
                total_minutes=total,
                total_hours=round(total / 60, 2),
                avg_session_minutes=round(total / sessions, 1) if sessions else 0.0,
            )
        )
    return out


@router.get("/daily-summary", response_model=list[DailySummary])
async def daily_summary(
    date_from: datetime | None = Query(None, alias="from"),
    date_to: datetime | None = Query(None, alias="to"),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Per-day head-count, late-count and total hours (closed sessions)."""
    match = {"status": "closed", **_punch_in_range(date_from, date_to)}
    pipeline = [
        {"$match": match},
        {
            "$group": {
                "_id": {
                    "$dateToString": {
                        "format": "%Y-%m-%d",
                        "date": "$punch_in",
                        "timezone": "UTC",
                    }
                },
                "sessions": {"$sum": 1},
                "employees": {"$addToSet": "$employee_id"},
                "late": {"$sum": {"$cond": ["$is_late", 1, 0]}},
                "total_minutes": {"$sum": "$worked_minutes"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "date": "$_id",
                "sessions": 1,
                "head_count": {"$size": "$employees"},
                "late_count": "$late",
                "total_minutes": 1,
                "total_hours": {"$round": [{"$divide": ["$total_minutes", 60]}, 2]},
            }
        },
        {"$sort": {"date": 1}},
    ]
    rows = await db.attendance.aggregate(pipeline).to_list(length=None)
    return [DailySummary(**r) for r in rows]


@router.get("/late-arrivals", response_model=list[LateArrival])
async def late_arrivals(
    date_from: datetime | None = Query(None, alias="from"),
    date_to: datetime | None = Query(None, alias="to"),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Late-arrival counts per employee. Lateness is known at punch-in, so this
    counts both open and closed sessions."""
    match = {"is_late": True, **_punch_in_range(date_from, date_to)}
    pipeline = [
        {"$match": match},
        {
            "$group": {
                "_id": "$employee_id",
                "employee_name": {"$first": "$employee_name"},
                "department": {"$first": "$department"},
                "late_count": {"$sum": 1},
                "total_late_minutes": {"$sum": "$late_by_minutes"},
                "avg_late": {"$avg": "$late_by_minutes"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "employee_id": "$_id",
                "employee_name": 1,
                "department": 1,
                "late_count": 1,
                "total_late_minutes": 1,
                "avg_late_minutes": {"$round": ["$avg_late", 1]},
            }
        },
        {"$sort": {"late_count": -1}},
    ]
    rows = await db.attendance.aggregate(pipeline).to_list(length=None)
    return [LateArrival(**r) for r in rows]


@router.get("/department-summary", response_model=list[DepartmentSummary])
async def department_summary(
    date_from: datetime | None = Query(None, alias="from"),
    date_to: datetime | None = Query(None, alias="to"),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Aggregate hours and lateness grouped by department (closed sessions)."""
    match = {"status": "closed", **_punch_in_range(date_from, date_to)}
    pipeline = [
        {"$match": match},
        {
            "$group": {
                "_id": "$department",
                "employees": {"$addToSet": "$employee_id"},
                "sessions": {"$sum": 1},
                "total_minutes": {"$sum": "$worked_minutes"},
                "late": {"$sum": {"$cond": ["$is_late", 1, 0]}},
            }
        },
        {
            "$project": {
                "_id": 0,
                "department": "$_id",
                "head_count": {"$size": "$employees"},
                "sessions": 1,
                "total_hours": {"$round": [{"$divide": ["$total_minutes", 60]}, 2]},
                "avg_hours_per_session": {
                    "$round": [
                        {"$divide": [{"$divide": ["$total_minutes", 60]}, "$sessions"]},
                        2,
                    ]
                },
                "late_count": "$late",
            }
        },
        {"$sort": {"total_hours": -1}},
    ]
    rows = await db.attendance.aggregate(pipeline).to_list(length=None)
    return [DepartmentSummary(**r) for r in rows]


@router.get("/overtime", response_model=list[OvertimeRow])
async def overtime(
    standard_minutes: int | None = Query(
        None, description="Daily threshold; defaults to settings.standard_day_minutes"
    ),
    date_from: datetime | None = Query(None, alias="from"),
    date_to: datetime | None = Query(None, alias="to"),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Per-employee-per-day worked minutes exceeding the standard working day.

    Demonstrates grouping on a composite key (employee + calendar day) and a
    post-group ``$match`` on the computed total.
    """
    threshold = standard_minutes or get_settings().standard_day_minutes
    match = {"status": "closed", **_punch_in_range(date_from, date_to)}
    pipeline = [
        {"$match": match},
        {
            "$group": {
                "_id": {
                    "employee_id": "$employee_id",
                    "day": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$punch_in",
                            "timezone": "UTC",
                        }
                    },
                },
                "employee_name": {"$first": "$employee_name"},
                "department": {"$first": "$department"},
                "day_minutes": {"$sum": "$worked_minutes"},
            }
        },
        {"$match": {"day_minutes": {"$gt": threshold}}},
        {
            "$project": {
                "_id": 0,
                "employee_id": "$_id.employee_id",
                "date": "$_id.day",
                "employee_name": 1,
                "department": 1,
                "day_minutes": 1,
                "overtime_minutes": {"$subtract": ["$day_minutes", threshold]},
            }
        },
        {"$sort": {"overtime_minutes": -1}},
    ]
    rows = await db.attendance.aggregate(pipeline).to_list(length=None)
    return [OvertimeRow(**r) for r in rows]


@router.get("/overview")
async def overview(
    date_from: datetime | None = Query(None, alias="from"),
    date_to: datetime | None = Query(None, alias="to"),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Single-pass dashboard snapshot using ``$facet`` (several sub-aggregations
    over one scan of the matched documents)."""
    match = _punch_in_range(date_from, date_to)
    pipeline = [
        {"$match": match} if match else {"$match": {}},
        {
            "$facet": {
                "totals": [
                    {
                        "$group": {
                            "_id": None,
                            "sessions": {"$sum": 1},
                            "closed": {
                                "$sum": {"$cond": [{"$eq": ["$status", "closed"]}, 1, 0]}
                            },
                            "open": {
                                "$sum": {"$cond": [{"$eq": ["$status", "open"]}, 1, 0]}
                            },
                            "late": {"$sum": {"$cond": ["$is_late", 1, 0]}},
                            "total_minutes": {"$sum": {"$ifNull": ["$worked_minutes", 0]}},
                        }
                    },
                    {
                        "$project": {
                            "_id": 0,
                            "sessions": 1,
                            "closed": 1,
                            "open": 1,
                            "late": 1,
                            "total_hours": {
                                "$round": [{"$divide": ["$total_minutes", 60]}, 2]
                            },
                        }
                    },
                ],
                "by_department": [
                    {"$match": {"status": "closed"}},
                    {
                        "$group": {
                            "_id": "$department",
                            "sessions": {"$sum": 1},
                            "total_minutes": {"$sum": "$worked_minutes"},
                        }
                    },
                    {
                        "$project": {
                            "_id": 0,
                            "department": "$_id",
                            "sessions": 1,
                            "total_hours": {
                                "$round": [{"$divide": ["$total_minutes", 60]}, 2]
                            },
                        }
                    },
                    {"$sort": {"total_hours": -1}},
                ],
            }
        },
        {
            "$project": {
                "totals": {"$ifNull": [{"$arrayElemAt": ["$totals", 0]}, {}]},
                "by_department": 1,
            }
        },
    ]
    rows = await db.attendance.aggregate(pipeline).to_list(length=1)
    return rows[0] if rows else {"totals": {}, "by_department": []}
