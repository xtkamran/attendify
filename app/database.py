"""MongoDB connection and index initialization using PyMongo."""
from __future__ import annotations

from functools import lru_cache

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database

from .config import get_settings

_client: MongoClient | None = None
_db: Database | None = None


def connect_to_mongo() -> None:
    """Connect to MongoDB and create indexes idempotently."""
    global _client, _db

    settings = get_settings()
    _client = MongoClient(
        settings.mongo_uri,
        tz_aware=True,
        serverSelectionTimeoutMS=3000,
    )
    _client.admin.command("ping")
    _db = _client[settings.mongo_db]

    _db.employees.create_index(
        [("emp_code", ASCENDING)],
        unique=True,
        name="uq_employees_emp_code",
    )

    _db.attendance_logs.create_index(
        [("emp_code", ASCENDING), ("date", ASCENDING)],
        unique=True,
        name="uq_attendance_emp_date",
    )

    _db.attendance_logs.create_index(
        [("department", ASCENDING), ("date", ASCENDING)],
        name="ix_attendance_department_date",
    )

    _db.attendance_logs.create_index(
        [("date", ASCENDING), ("late_minutes", ASCENDING)],
        name="ix_attendance_date_late",
    )

    _db.attendance_logs.create_index(
        [("emp_code", ASCENDING), ("punch_in", DESCENDING)],
        name="ix_attendance_emp_punch_in",
    )

    _db.employees.create_index(
        [("department", ASCENDING), ("joined_on", ASCENDING)],
        name="ix_employees_department_joined",
    )


def close_mongo_connection() -> None:
    """Close the MongoDB client."""
    global _client, _db

    if _client is not None:
        _client.close()

    _client = None
    _db = None


def get_db() -> Database:
    """Return the connected database."""
    if _db is None:
        raise RuntimeError(
            "MongoDB is not connected. Start the application lifespan first."
        )
    return _db

async def ensure_indexes(db) -> None:
    """Create indexes for the seed database."""
    await db.employees.create_index(
        [("emp_code", 1)],
        unique=True,
        name="uq_employees_emp_code",
    )
    await db.attendance_logs.create_index(
        [("emp_code", 1), ("date", 1)],
        unique=True,
        name="uq_attendance_emp_date",
    )
