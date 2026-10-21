from datetime import datetime, timezone

import app.main as main_module


EMPLOYEE = {
    "emp_code": "EMP12345",
    "shift_start": "09:30",
    "shift_end": "18:30",
}


def utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def attendance(punch_in, punch_out=None):
    return main_module.calculate(
        {
            "date": "2026-10-05",
            "status": "PRESENT",
            "punch_in": utc(punch_in),
            "punch_out": utc(punch_out) if punch_out else None,
        },
        EMPLOYEE,
    )


def test_punch_in_at_1000_am_is_within_grace(monkeypatch):
    monkeypatch.setattr(
        main_module, "get_settings",
        lambda: type("Settings", (), {"late_grace_minutes": 30})(),
    )

    result = attendance("2026-10-05T04:30:00Z")

    assert result["late_minutes"] == 0
    assert result["half_day"] is False


def test_punch_in_at_1001_am_is_late_and_half_day_even_after_full_shift(
    monkeypatch,
):
    monkeypatch.setattr(
        main_module, "get_settings",
        lambda: type("Settings", (), {"late_grace_minutes": 30})(),
    )

    result = attendance(
        "2026-10-05T04:31:00Z",
        "2026-10-05T13:00:00Z",
    )

    assert result["late_minutes"] == 31
    assert result["work_hours"] == 8.48
    assert result["half_day"] is True
