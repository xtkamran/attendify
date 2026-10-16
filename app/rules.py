"""Pure business-rules + time helpers.

Everything here is deliberately free of I/O and of MongoDB/FastAPI imports so it
can be unit-tested in isolation (see tests/test_rules.py). All datetimes are
normalised to timezone-aware UTC.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .errors import InvalidPunchSequence


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    """Return a timezone-aware UTC datetime.

    Naive datetimes are *assumed* to already be UTC (documented behaviour so
    clients know what to send). Aware datetimes are converted to UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_hhmm(value: str) -> tuple[int, int]:
    """Parse an "HH:MM" shift string into (hour, minute)."""
    hh, mm = value.strip().split(":")
    hour, minute = int(hh), int(mm)
    if not (0 <= hour < 24 and 0 <= minute < 60):
        raise ValueError(f"Invalid HH:MM time: {value!r}")
    return hour, minute


def compute_worked_minutes(punch_in: datetime, punch_out: datetime) -> int:
    """Whole minutes between punch_in and punch_out (rounded to nearest)."""
    delta = ensure_utc(punch_out) - ensure_utc(punch_in)
    return int(round(delta.total_seconds() / 60.0))


def validate_punch_out(punch_in: datetime, punch_out: datetime) -> None:
    """punch_out must be strictly after punch_in."""
    if ensure_utc(punch_out) <= ensure_utc(punch_in):
        raise InvalidPunchSequence("punch_out must be strictly after punch_in")


def evaluate_lateness(
    punch_in: datetime, shift_start_hhmm: str, grace_minutes: int
) -> tuple[bool, int]:
    """Decide whether a punch-in is late.

    The shift start time is interpreted on the *same calendar day* as the
    punch-in, in the punch-in's own timezone (after UTC normalisation). A
    punch-in is "late" when it lands after ``shift_start + grace``. The reported
    ``late_by_minutes`` is measured from the shift start itself (not from the end
    of the grace window), which is what payroll/HR usually wants.
    """
    pi = ensure_utc(punch_in)
    hour, minute = parse_hhmm(shift_start_hhmm)
    shift_start = pi.replace(hour=hour, minute=minute, second=0, microsecond=0)
    allowed_until = shift_start + timedelta(minutes=grace_minutes)
    if pi > allowed_until:
        late_by = int((pi - shift_start).total_seconds() // 60)
        return True, late_by
    return False, 0


def evaluate_flags(
    punch_in: datetime,
    punch_out: datetime,
    worked_minutes: int,
    *,
    max_session_minutes: int,
    min_session_minutes: int,
) -> list[str]:
    """Return review flags for a completed session."""
    flags: list[str] = []
    pi = ensure_utc(punch_in)
    po = ensure_utc(punch_out)
    if worked_minutes > max_session_minutes:
        flags.append("long_session")
    if worked_minutes < min_session_minutes:
        flags.append("short_session")
    if pi.date() != po.date():
        flags.append("overnight")
    return flags
