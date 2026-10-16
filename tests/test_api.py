"""Regression tests for the current Employee Attendance API."""

import app.main as main_module


EMPLOYEE = {
    "emp_code": "EMP12345",
    "name": "Asha Rao",
    "email": "asha@example.com",
    "department": "Engineering",
    "shift_start": "09:30",
    "shift_end": "18:30",
    "joined_on": "2026-10-01",
}


def epoch_ms(value):
    from datetime import datetime, timezone

    return int(
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        .astimezone(timezone.utc)
        .timestamp()
        * 1000
    )


def test_health(client, monkeypatch):
    class HealthyDB:
        @staticmethod
        def command(name):
            assert name == "ping"
            return {"ok": 1}

    monkeypatch.setattr(main_module, "get_db", lambda: HealthyDB())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_punch_in_requires_existing_employee(client):
    response = client.post(
        "/attendance/punch-in",
        json={"emp_code": "EMP99999"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Employee not found"


def test_monthly_analytics_after_completed_attendance(client):
    created = client.post("/employees", json=EMPLOYEE)
    assert created.status_code == 201, created.text

    punched_in = client.post(
        "/attendance/punch-in",
        json={
            "emp_code": "EMP12345",
            "punched_at": epoch_ms("2026-10-05T04:00:00Z"),
        },
    )
    assert punched_in.status_code == 201, punched_in.text
    assert punched_in.json()["date"] == "2026-10-05"

    punched_out = client.post(
        "/attendance/punch-out",
        json={
            "emp_code": "EMP12345",
            "punched_at": epoch_ms("2026-10-05T13:00:00Z"),
        },
    )
    assert punched_out.status_code == 200, punched_out.text
    assert punched_out.json()["work_hours"] == 9.0

    response = client.get(
        "/analytics/employees/EMP12345/monthly",
        params={"month": "2026-10"},
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["emp_code"] == "EMP12345"
    assert result["month"] == "2026-10"
    assert result["present_days"] == 1.0
    assert result["late_count"] == 0


def test_monthly_analytics_rejects_invalid_month(client):
    response = client.get(
        "/analytics/employees/EMP12345/monthly",
        params={"month": "October-2026"},
    )

    assert response.status_code == 404 or response.status_code == 422
