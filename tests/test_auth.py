import pytest
from bson import ObjectId
from app.auth import get_current_user


@pytest.fixture
def employee_records(db):
    db.employees.insert_many([
        {
            "emp_code": "EMP1001",
            "name": "Employee One",
            "email": "one@example.com",
            "department": "Engineering",
            "joined_on": "2026-01-01",
            "shift_start": "09:30",
            "shift_end": "18:30",
            "created_at": __import__("datetime").datetime(2026, 1, 1),
        },
        {
            "emp_code": "EMP1002",
            "name": "Employee Two",
            "email": "two@example.com",
            "department": "Engineering",
            "joined_on": "2026-01-01",
            "shift_start": "09:30",
            "shift_end": "18:30",
            "created_at": __import__("datetime").datetime(2026, 1, 1),
        },
    ])
    return db


def set_employee(client, db, emp_code="EMP1001",
                 email="one@example.com"):
    user_id = ObjectId()
    db.users.insert_one({
        "_id": user_id,
        "email": email,
        "role": "employee",
        "emp_code": emp_code,
        "is_active": True,
    })
    client.app.dependency_overrides[get_current_user] = lambda: {
        "_id": user_id,
        "email": email,
        "role": "employee",
        "emp_code": emp_code,
        "is_active": True,
    }


def test_employee_cannot_list_another_employees_attendance(
    client, employee_records
):
    set_employee(client, employee_records)
    response = client.get("/attendance", params={"emp_code": "EMP1002"})
    assert response.status_code == 403


def test_employee_cannot_punch_in_for_another_employee(
    client, employee_records
):
    set_employee(client, employee_records)
    response = client.post("/attendance/punch-in", json={
        "emp_code": "EMP1002",
        "status": "PRESENT",
    })
    assert response.status_code == 403


def test_employee_cannot_punch_out_for_another_employee(
    client, employee_records
):
    set_employee(client, employee_records)
    response = client.post("/attendance/punch-out", json={
        "emp_code": "EMP1002",
    })
    assert response.status_code == 403


def test_employee_cannot_view_another_employees_monthly_analytics(
    client, employee_records
):
    set_employee(client, employee_records)
    response = client.get(
        "/analytics/employees/EMP1002/monthly",
        params={"month": "2026-01"},
    )
    assert response.status_code == 403


@pytest.mark.parametrize("path", [
    "/employees",
    "/analytics/departments/summary?month=2026-01",
    "/analytics/leaderboard/late?month=2026-01",
    "/analytics/departments/Engineering/trend?from=2026-01-01&to=2026-01-07",
    "/admin/explain/department_summary?month=2026-01",
])
def test_employee_cannot_access_admin_only_endpoints(
    client, employee_records, path
):
    from app.main import admin_required

    set_employee(client, employee_records)

    # Remove the test fixture's admin bypass so the real role checker runs.
    client.app.dependency_overrides.pop(admin_required, None)

    response = client.get(path)
    assert response.status_code == 403


def test_employee_account_email_must_match_employee_record(
    client, employee_records
):
    set_employee(client, employee_records)
    response = client.post("/auth/employee-account", json={
        "emp_code": "EMP1002",
        "email": "two@example.com",
        "password": "A-long-test-password-123",
    })
    assert response.status_code == 403



def test_employee_cannot_patch_attendance(client, employee_records):
    from app.main import admin_required

    set_employee(client, employee_records)
    client.app.dependency_overrides.pop(admin_required, None)

    response = client.patch(
        "/attendance/EMP1001/2026-01-01",
        json={"status": "ABSENT"},
    )

    assert response.status_code == 403
