from datetime import datetime, timezone

def epoch_ms(value):
    return int(datetime.fromisoformat(value).replace(
        tzinfo=timezone.utc
    ).timestamp() * 1000)


EMP = {
    "emp_code": "EMP12345",
    "name": "Asha Rao",
    "email": "asha@example.com",
    "department": "Engineering",
    "shift_start": "09:30",
    "shift_end": "18:30",
    "joined_on": "2026-10-01",
}


def create_employee(client, emp=None):
    return client.post("/employees", json=emp or EMP)


def test_create_employee_and_duplicate(client):
    with client as c:
        first = create_employee(c)
        assert first.status_code == 201, first.text
        assert first.json()["emp_code"] == "EMP12345"
        assert "_id" not in first.json()

        duplicate = create_employee(c)
        assert duplicate.status_code == 409, duplicate.text


def test_invalid_employee_input(client):
    with client as c:
        invalid = {**EMP, "emp_code": "BAD", "email": "not-an-email"}
        response = create_employee(c, invalid)
        assert response.status_code == 422, response.text


def test_employee_list_pagination(client):
    with client as c:
        assert create_employee(c).status_code == 201
        second = {**EMP, "emp_code": "EMP12346",
                  "email": "second@example.com"}
        assert create_employee(c, second).status_code == 201

        response = c.get("/employees?page=1&page_size=1")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total"] == 2
        assert body["page"] == 1
        assert body["page_size"] == 1
        assert len(body["items"]) == 1


def test_punch_in_and_duplicate_same_day(client):
    with client as c:
        assert create_employee(c).status_code == 201
        payload = {
            "emp_code": "EMP12345",
            "punched_at": epoch_ms("2026-10-05T04:00:00"),
            "status": "PRESENT",
        }
        first = c.post("/attendance/punch-in", json=payload)
        assert first.status_code == 201, first.text
        body = first.json()
        assert body["date"] == "2026-10-05"
        assert body["status"] == "PRESENT"
        assert "_id" not in body

        duplicate = c.post("/attendance/punch-in", json=payload)
        assert duplicate.status_code == 409, duplicate.text


def test_timestamp_must_be_epoch_milliseconds(client):
    with client as c:
        assert create_employee(c).status_code == 201
        for invalid in [
            "2026-10-05T04:00:00Z",
            1_791_168_000,
            1.791168e12,
        ]:
            response = c.post("/attendance/punch-in", json={
                "emp_code": "EMP12345",
                "punched_at": invalid,
            })
            assert response.status_code == 422, (
                f"Expected 422 for {invalid!r}, got "
                f"{response.status_code}: {response.text}"
            )


def test_punch_out_calculates_work_hours(client):
    with client as c:
        assert create_employee(c).status_code == 201
        punch_in = c.post("/attendance/punch-in", json={
            "emp_code": "EMP12345",
            "punched_at": epoch_ms("2026-10-05T04:00:00"),
        })
        assert punch_in.status_code == 201, punch_in.text

        punch_out = c.post("/attendance/punch-out", json={
            "emp_code": "EMP12345",
            "punched_at": epoch_ms("2026-10-05T13:00:00"),
        })
        assert punch_out.status_code == 200, punch_out.text
        assert punch_out.json()["work_hours"] == 9.0

        again = c.post("/attendance/punch-out", json={
            "emp_code": "EMP12345",
            "punched_at": epoch_ms("2026-10-05T13:05:00"),
        })
        assert again.status_code == 409, again.text


def test_attendance_list_rejects_reversed_date_range(client):
    with client as c:
        response = c.get(
            "/attendance?date_from=2026-10-10&date_to=2026-10-01"
        )
        assert response.status_code == 422, response.text


def test_regularization_records_history(client):
    with client as c:
        assert create_employee(c).status_code == 201
        punched = c.post("/attendance/punch-in", json={
            "emp_code": "EMP12345",
            "punched_at": epoch_ms("2026-10-05T04:10:00"),
        })
        assert punched.status_code == 201, punched.text

        patch = c.patch("/attendance/EMP12345/2026-10-05", json={
            "punch_in": epoch_ms("2026-10-05T04:00:00"),
            "reason": "Corrected punch-in",
            "regularized_by": "hr.admin",
        })
        assert patch.status_code == 200, patch.text
        body = patch.json()
        assert len(body["history"]) == 1
        assert body["history"][0]["reason"] == "Corrected punch-in"

        noop = c.patch("/attendance/EMP12345/2026-10-05", json={
            "punch_in": epoch_ms("2026-10-05T04:00:00"),
            "reason": "Same punch time",
            "regularized_by": "hr.admin",
        })
        assert noop.status_code == 422, noop.text
