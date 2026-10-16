from datetime import datetime, timedelta, timezone

import jwt
from bson import ObjectId

from app.auth import (
    ALGORITHM,
    create_access_token,
    get_current_user,
    hash_password,
)


TEST_SECRET = "test-only-secret-for-jwt-tests-2026"


def create_admin_user(db, email="admin@example.com", password="Strong-test-password-123"):
    user = {
        "_id": ObjectId(),
        "email": email,
        "password_hash": hash_password(password),
        "role": "admin",
        "is_active": True,
    }
    db.users.insert_one(user)
    return user


def enable_real_authentication(client):
    # Remove the fixture's authentication bypass for these tests.
    client.app.dependency_overrides.pop(get_current_user, None)


def test_login_with_valid_credentials_returns_token(client, db):
    user = create_admin_user(db)

    response = client.post(
        "/auth/login",
        json={
            "email": user["email"],
            "password": "Strong-test-password-123",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 1800
    assert body["user"]["email"] == user["email"]
    assert "password_hash" not in body["user"]


def test_login_rejects_wrong_password(client, db):
    user = create_admin_user(db)

    response = client.post(
        "/auth/login",
        json={"email": user["email"], "password": "Wrong-password"},
    )

    assert response.status_code == 401


def test_login_rejects_unknown_email(client, db):
    response = client.post(
        "/auth/login",
        json={"email": "unknown@example.com", "password": "Any-password"},
    )

    assert response.status_code == 401


def test_login_rejects_inactive_user(client, db):
    user = create_admin_user(db)
    db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"is_active": False}},
    )

    response = client.post(
        "/auth/login",
        json={
            "email": user["email"],
            "password": "Strong-test-password-123",
        },
    )

    assert response.status_code == 401


def test_me_rejects_missing_token(client, db):
    enable_real_authentication(client)

    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_me_rejects_invalid_token(client, db):
    enable_real_authentication(client)

    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid.token.value"},
    )

    assert response.status_code == 401


def test_me_rejects_expired_token(client, db):
    user = create_admin_user(db)
    enable_real_authentication(client)

    now = datetime.now(timezone.utc)
    expired_token = jwt.encode(
        {
            "sub": str(user["_id"]),
            "role": "admin",
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
        },
        TEST_SECRET,
        algorithm=ALGORITHM,
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401


def test_me_accepts_valid_token(client, db):
    user = create_admin_user(db)
    enable_real_authentication(client)

    token = create_access_token(user)

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == user["email"]
    assert response.json()["role"] == "admin"
    assert "password_hash" not in response.json()

def test_me_rejects_token_with_invalid_signature(client, db):
    user = create_admin_user(db)
    enable_real_authentication(client)

    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": str(user["_id"]),
            "role": "admin",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        "different-test-secret-not-the-real-key",
        algorithm=ALGORITHM,
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_me_rejects_token_for_inactive_user(client, db):
    user = create_admin_user(db)
    token = create_access_token(user)
    enable_real_authentication(client)

    db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"is_active": False}},
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_employee_cannot_access_admin_only_endpoint(client, db):
    from app.main import admin_required

    employee_id = ObjectId()
    client.app.dependency_overrides.pop(admin_required, None)
    client.app.dependency_overrides[get_current_user] = lambda: {
        "_id": employee_id,
        "email": "employee@example.com",
        "role": "employee",
        "emp_code": "EMP1001",
        "is_active": True,
    }

    response = client.get("/employees")

    assert response.status_code == 403


def test_employee_account_rejects_email_mismatch(client, db):
    db.employees.insert_one({
        "emp_code": "EMP1001",
        "name": "Test Employee",
        "email": "employee@example.com",
    })

    response = client.post(
        "/auth/employee-account",
        json={
            "emp_code": "EMP1001",
            "email": "different@example.com",
            "password": "Strong-test-password-123",
        },
    )

    assert response.status_code == 400

def test_admin_can_create_employee_account(client, db):
    db.employees.insert_one({
        "emp_code": "EMP2001",
        "name": "New Employee",
        "email": "new.employee@example.com",
    })

    response = client.post(
        "/auth/employee-account",
        json={
            "emp_code": "EMP2001",
            "email": "new.employee@example.com",
            "password": "Strong-test-password-123",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "new.employee@example.com"
    assert body["user"]["role"] == "employee"
    assert "password_hash" not in body["user"]

    saved_user = db.users.find_one({
        "email": "new.employee@example.com"
    })
    assert saved_user is not None
    assert saved_user["password_hash"] != "Strong-test-password-123"
    assert saved_user["password_hash"].startswith("$")


def test_admin_cannot_create_duplicate_employee_account(client, db):
    db.employees.insert_one({
        "emp_code": "EMP2002",
        "name": "Duplicate Employee",
        "email": "duplicate@example.com",
    })
    db.users.insert_one({
        "email": "duplicate@example.com",
        "password_hash": hash_password("Existing-test-password-123"),
        "role": "employee",
        "emp_code": "EMP2002",
        "is_active": True,
    })

    response = client.post(
        "/auth/employee-account",
        json={
            "emp_code": "EMP2002",
            "email": "duplicate@example.com",
            "password": "Another-test-password-123",
        },
    )

    assert response.status_code == 409
    assert db.users.count_documents({
        "email": "duplicate@example.com"
    }) == 1


def test_admin_cannot_create_account_for_missing_employee(client, db):
    response = client.post(
        "/auth/employee-account",
        json={
            "emp_code": "EMP2999",
            "email": "missing@example.com",
            "password": "Strong-test-password-123",
        },
    )

    assert response.status_code == 404

