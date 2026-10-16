"""Employee endpoints.

Thin CRUD, mostly so the attendance flow has employees to reference and so the
system is self-contained for seeding and tests.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from ..database import get_db
from ..errors import EmployeeAlreadyExists, EmployeeNotFound
from ..rules import now_utc
from ..schemas import EmployeeIn, EmployeeOut
from ..serializers import employee_out

router = APIRouter(prefix="/employees", tags=["employees"])


@router.post("", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
async def create_employee(body: EmployeeIn, db: AsyncIOMotorDatabase = Depends(get_db)):
    doc = body.model_dump()
    doc["created_at"] = now_utc()
    try:
        res = await db.employees.insert_one(doc)
    except DuplicateKeyError:
        raise EmployeeAlreadyExists(f"Employee {body.employee_id!r} already exists")
    doc["_id"] = res.inserted_id
    return employee_out(doc)


@router.get("", response_model=list[EmployeeOut])
async def list_employees(
    department: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    query: dict = {}
    if department:
        query["department"] = department
    cursor = db.employees.find(query).sort("employee_id", 1).skip(skip).limit(limit)
    return [employee_out(d) async for d in cursor]


@router.get("/{employee_id}", response_model=EmployeeOut)
async def get_employee(employee_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    doc = await db.employees.find_one({"employee_id": employee_id})
    if not doc:
        raise EmployeeNotFound(f"Employee {employee_id!r} not found")
    return employee_out(doc)
