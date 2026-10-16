"""Unit tests for the pure business-rules module (no DB, no HTTP)."""
from datetime import datetime, timedelta, timezone

import pytest

from app.errors import InvalidPunchSequence
from app.rules import (
    compute_worked_minutes,
    ensure_utc,
    evaluate_flags,
    evaluate_lateness,
    parse_hhmm,
    validate_punch_out,
)


def dt(y, m, d, h, mi, tz=timezone.utc):
    return datetime(y, m, d, h, mi, tzinfo=tz)


def test_worked_minutes_basic():
    assert compute_worked_minutes(dt(2026, 10, 5, 9, 0), dt(2026, 10, 5, 17, 30)) == 510


def test_worked_minutes_overnight():
    assert compute_worked_minutes(dt(2026, 10, 5, 22, 0), dt(2026, 10, 6, 6, 0)) == 480


def test_worked_minutes_over_24h():
    # The classic timedelta.seconds bug would report 60 here, not 1500.
    assert compute_worked_minutes(dt(2026, 10, 5, 9, 0), dt(2026, 10, 6, 10, 0)) == 25 * 60


def test_ensure_utc_treats_naive_as_utc():
    out = ensure_utc(datetime(2026, 10, 5, 9, 0))
    assert out.tzinfo is not None
    assert out.hour == 9


def test_ensure_utc_converts_aware():
    ist = timezone(timedelta(hours=5, minutes=30))
    out = ensure_utc(datetime(2026, 10, 5, 14, 30, tzinfo=ist))  # == 09:00 UTC
    assert (out.hour, out.minute) == (9, 0)


def test_lateness_within_grace():
    late, by = evaluate_lateness(dt(2026, 10, 5, 9, 10), "09:00", 15)
    assert late is False and by == 0


def test_lateness_beyond_grace_measured_from_shift_start():
    late, by = evaluate_lateness(dt(2026, 10, 5, 9, 40), "09:00", 15)
    assert late is True and by == 40


def test_validate_punch_out_rejects_equal_or_before():
    with pytest.raises(InvalidPunchSequence):
        validate_punch_out(dt(2026, 10, 5, 9, 0), dt(2026, 10, 5, 9, 0))
    with pytest.raises(InvalidPunchSequence):
        validate_punch_out(dt(2026, 10, 5, 9, 0), dt(2026, 10, 5, 8, 0))


def test_flags_overnight():
    flags = evaluate_flags(
        dt(2026, 10, 5, 22, 0), dt(2026, 10, 6, 6, 0), 480,
        max_session_minutes=960, min_session_minutes=5,
    )
    assert "overnight" in flags and "long_session" not in flags


def test_flags_long_and_short():
    long_flags = evaluate_flags(
        dt(2026, 10, 5, 0, 0), dt(2026, 10, 5, 20, 0), 1200,
        max_session_minutes=960, min_session_minutes=5,
    )
    assert "long_session" in long_flags
    short_flags = evaluate_flags(
        dt(2026, 10, 5, 9, 0), dt(2026, 10, 5, 9, 2), 2,
        max_session_minutes=960, min_session_minutes=5,
    )
    assert "short_session" in short_flags


def test_parse_hhmm_invalid():
    with pytest.raises(ValueError):
        parse_hhmm("25:00")
