from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from pymongo.errors import DuplicateKeyError

from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    require_role,
    verify_password,
)
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class EmployeeAccountCreate(BaseModel):
    emp_code: str = Field(pattern=r"^EMP\d{4,6}$")
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(user["_id"]),
        "email": user["email"],
        "role": user["role"],
        "emp_code": user.get("emp_code"),
    }


@router.post("/login")
def login(payload: LoginRequest, db=Depends(get_db)):
    email = str(payload.email).strip().lower()
    user = db["users"].find_one({"email": email})

    if (
        not user
        or not user.get("password_hash")
        or not verify_password(payload.password, user["password_hash"])
        or user.get("is_active", True) is not True
        or user.get("role") not in {"admin", "employee"}
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Employee accounts must be linked to an existing employee record.
    if user["role"] == "employee":
        emp_code = user.get("emp_code")
        employee = db["employees"].find_one({"emp_code": emp_code})

        if (
            not employee
            or str(employee.get("email", "")).strip().lower() != email
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    token = create_access_token(user)

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 1800,
        "user": public_user(user),
    }


@router.get("/me")
def me(current_user=Depends(get_current_user)):
    return public_user(current_user)


@router.post("/employee-account", status_code=status.HTTP_201_CREATED)
def create_employee_account(
    payload: EmployeeAccountCreate,
    current_user=Depends(require_role("admin")),
    db=Depends(get_db),
):
    email = str(payload.email).strip().lower()
    emp_code = payload.emp_code.strip()

    employee = db["employees"].find_one({"emp_code": emp_code})

    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee record not found.",
        )

    if str(employee.get("email", "")).strip().lower() != email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email must match the existing employee record.",
        )

    users = db["users"]
    users.create_index("email", unique=True, name="uq_users_email")

    if users.find_one({"email": email}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = {
        "email": email,
        "password_hash": hash_password(payload.password),
        "role": "employee",
        "emp_code": emp_code,
        "is_active": True,
    }

    try:
        result = users.insert_one(user)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user["_id"] = result.inserted_id

    return {
        "message": "Employee account created successfully.",
        "user": public_user(user),
    }
