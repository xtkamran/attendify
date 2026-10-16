"""Seed the database with employees and a realistic week of attendance.

Usage:
    python sample_seed.py            # insert (keeps existing data)
    python sample_seed.py --drop     # wipe collections first

Honours the same env vars as the app (MONGO_URI, MONGO_DB).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient

from app.config import get_settings
from app.database import ensure_indexes
from app.rules import (
    compute_worked_minutes,
    evaluate_flags,
    evaluate_lateness,
    parse_hhmm,
)

HERE = Path(__file__).parent
EMPLOYEES_FILE = HERE / "sample_data" / "employees.json"

random.seed(42)  # deterministic seed data


def _at(day: datetime, hhmm: str, jitter_min: int = 0) -> datetime:
    hour, minute = parse_hhmm(hhmm)
    base = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return base + timedelta(minutes=jitter_min)


def build_attendance(employees: list[dict], settings) -> list[dict]:
    docs: list[dict] = []
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    # Last 7 calendar days, weekdays only.
    days = [today - timedelta(days=d) for d in range(7, 0, -1)]
    days = [d for d in days if d.weekday() < 5]

    for emp in employees:
        for day in days:
            # ~15% chance someone is absent that day.
            if random.random() < 0.15:
                continue

            late_jitter = random.choice([-10, -5, 0, 5, 20, 35])  # some late
            punch_in = _at(day, emp["shift_start"], late_jitter)

            # Mostly a normal day; sometimes overtime, sometimes a short day.
            roll = random.random()
            if roll < 0.2:
                out_jitter = random.randint(90, 180)  # overtime
            elif roll < 0.35:
                out_jitter = -random.randint(60, 150)  # short day
            else:
                out_jitter = random.randint(-10, 20)
            punch_out = _at(day, emp["shift_end"], out_jitter)

            docs.append(_make_doc(emp, punch_in, punch_out, settings))

    # A guaranteed overnight session for the Support late-shift worker.
    e006 = next((e for e in employees if e["employee_id"] == "E006"), None)
    if e006:
        start = _at(days[-1], "22:00")
        end = _at(days[-1] + timedelta(days=1), "06:00")
        docs.append(_make_doc(e006, start, end, settings))

    # One currently-open session (punched in today, not yet out).
    e001 = next((e for e in employees if e["employee_id"] == "E001"), None)
    if e001:
        docs.append(_make_doc(e001, _at(today, e001["shift_start"], 5), None, settings))

    return docs


def _make_doc(emp: dict, punch_in: datetime, punch_out: datetime | None, settings) -> dict:
    is_late, late_by = evaluate_lateness(
        punch_in, emp["shift_start"], settings.late_grace_minutes
    )
    if punch_out is not None:
        worked = compute_worked_minutes(punch_in, punch_out)
        flags = evaluate_flags(
            punch_in,
            punch_out,
            worked,
            max_session_minutes=settings.max_session_minutes,
            min_session_minutes=settings.min_session_minutes,
        )
        status = "closed"
    else:
        worked, flags, status = None, [], "open"

    now = datetime.now(timezone.utc)
    return {
        "employee_id": emp["employee_id"],
        "employee_name": emp["name"],
        "department": emp["department"],
        "punch_in": punch_in,
        "punch_out": punch_out,
        "worked_minutes": worked,
        "status": status,
        "is_late": is_late,
        "late_by_minutes": late_by,
        "flags": flags,
        "source": "biometric",
        "note": None,
        "is_corrected": False,
        "correction_count": 0,
        "created_at": now,
        "updated_at": now,
    }


async def main(drop: bool) -> None:
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongo_uri, tz_aware=True)
    db = client[settings.mongo_db]

    if drop:
        await db.employees.delete_many({})
        await db.attendance.delete_many({})
        await db.audit_logs.delete_many({})
        print("Dropped employees / attendance / audit_logs")

    await ensure_indexes(db)

    employees = json.loads(EMPLOYEES_FILE.read_text())
    for emp in employees:
        emp_doc = {**emp, "created_at": datetime.now(timezone.utc)}
        await db.employees.update_one(
            {"employee_id": emp["employee_id"]}, {"$setOnInsert": emp_doc}, upsert=True
        )
    print(f"Upserted {len(employees)} employees")

    attendance = build_attendance(employees, settings)
    if attendance:
        await db.attendance.insert_many(attendance)
    print(f"Inserted {len(attendance)} attendance records")

    client.close()
    print("Done. Try: uvicorn app.main:app --reload  ->  http://localhost:8000/docs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--drop", action="store_true", help="wipe collections first")
    args = parser.parse_args()
    asyncio.run(main(args.drop))
