"""Test fixtures for the synchronous FastAPI application."""

import pytest
import mongomock
from fastapi.testclient import TestClient

import app.main as main_module
import app.auth as auth_module
from app.auth import get_current_user
import app.auth_routes as auth_routes_module
from app.main import app
from app.database import get_db as database_get_db


@pytest.fixture(autouse=True)
def disable_real_database_startup(monkeypatch, mock_db):
    # Keep tests isolated from the real MongoDB database.
    monkeypatch.setattr(main_module, "connect_to_mongo", lambda: None)
    monkeypatch.setattr(main_module, "get_db", lambda: mock_db)
    monkeypatch.setattr(auth_module, "get_db", lambda: mock_db)
    monkeypatch.setattr(
        auth_module,
        "get_settings",
        lambda: type("TestSettings", (), {
            "jwt_secret_key": "test-only-secret-for-jwt-tests-2026"
        })(),
    )
    monkeypatch.setattr(auth_routes_module, "get_db", lambda: mock_db)
    app.dependency_overrides[database_get_db] = lambda: mock_db
    app.dependency_overrides[main_module.admin_required] = lambda: {
        "_id": "test-admin",
        "role": "admin",
        "email": "test-admin@example.com",
        "is_active": True,
    }
    app.dependency_overrides[get_current_user] = lambda: {
        "_id": "test-admin",
        "role": "admin",
        "email": "test-admin@example.com",
        "is_active": True,
    }



@pytest.fixture
def db():
    client = mongomock.MongoClient()
    database = client["attendance_test"]
    database.employees.create_index("emp_code", unique=True)
    database.attendance_logs.create_index(
        [("emp_code", 1), ("date", 1)], unique=True
    )
    yield database
    client.close()


@pytest.fixture
def mock_db(db, monkeypatch):
    monkeypatch.setattr(main_module, "get_db", lambda: db)
    return db


@pytest.fixture
def client(mock_db):
    with TestClient(app) as test_client:
        yield test_client
