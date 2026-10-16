from fastapi.testclient import TestClient
from app.main import app


def test_health_with_connected_database():
    # Health depends on a real connected MongoDB.
    # Skip if the test environment has not connected MongoDB.
    from app.database import get_db
    try:
        get_db().command("ping")
    except Exception:
        import pytest
        pytest.skip("MongoDB is not connected for this test")
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_timestamp_string_is_rejected():
    with TestClient(app) as client:
        response = client.post("/attendance/punch-in", json={
            "emp_code": "EMP98766",
            "punched_at": "1791647800000",
            "status": "PRESENT"
        })
        assert response.status_code == 422


def test_timestamp_float_is_rejected():
    with TestClient(app) as client:
        response = client.post("/attendance/punch-in", json={
            "emp_code": "EMP98766",
            "punched_at": 1791647800000.0,
            "status": "PRESENT"
        })
        assert response.status_code == 422


def test_timestamp_seconds_are_rejected():
    with TestClient(app) as client:
        response = client.post("/attendance/punch-in", json={
            "emp_code": "EMP98766",
            "punched_at": 1791647800,
            "status": "PRESENT"
        })
        assert response.status_code == 422
