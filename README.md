# Employee Attendance & Analytics API

A REST API built with **FastAPI**, **PyMongo**, and **MongoDB** for employee management, attendance tracking, attendance regularization, and analytics.

## Features

- Create and list employees with pagination and department filtering.
- Record employee punch-in and punch-out timestamps.
- Calculate work hours, late minutes, overtime, and half-day status.
- List and filter attendance records.
- Regularize attendance with a reason, administrator identifier, and audit history.
- Generate monthly employee analytics.
- Generate department summaries, late-arrival leaderboards, and department trends.
- Inspect MongoDB query execution plans using the admin explain endpoint.

## Requirements

- Python 3.13 or a compatible Python version.
- MongoDB 6.0 or newer.
- Dependencies listed in `requirements.txt`.

## Setup

### 1. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure MongoDB

Create `.env` from the example file if it does not already exist:

```bash
cp .env.example .env
```

Configure the connection settings:

```dotenv
MONGO_URI=mongodb://localhost:27017
MONGO_DB=attendance
```

Use a separate database name for assessment or test data if appropriate. Do not commit `.env` or credentials to Git.

### 3. Start the API

```bash
uvicorn app.main:app --reload --port 8000
```

Open Swagger UI at:

- API documentation: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

If port 8000 is already occupied, choose another available port, for example `8002`, and use that port in the URLs.

## Configuration

Settings are loaded from environment variables and `.env`. Current application defaults include:

| Variable | Default |
|---|---|
| `MONGO_URI` | `mongodb://localhost:27017` |
| `MONGO_DB` | `attendance` |
| `DEFAULT_SHIFT_START` | `09:30` |
| `DEFAULT_SHIFT_END` | `18:30` |
| `TIMEZONE` | `Asia/Kolkata` |
| `LATE_GRACE_MINUTES` | `10` |
| `MAX_SESSION_MINUTES` | `960` |
| `MIN_SESSION_MINUTES` | `5` |

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Check API health |
| POST | `/employees` | Create an employee |
| GET | `/employees` | List employees; supports department filtering and pagination |
| POST | `/attendance/punch-in` | Record attendance punch-in |
| POST | `/attendance/punch-out` | Record attendance punch-out |
| GET | `/attendance` | List attendance with filters and pagination |
| PATCH | `/attendance/{emp_code}/{attendance_date}` | Regularize an attendance record and record its audit history |
| GET | `/analytics/employees/{emp_code}/monthly` | Monthly employee attendance analytics |
| GET | `/analytics/departments/summary` | Department attendance summary for a month |
| GET | `/analytics/leaderboard/late` | Rank employees by late minutes |
| GET | `/analytics/departments/{department}/trend` | Daily attendance trend for a department |
| GET | `/admin/explain/{endpoint}` | Inspect a supported MongoDB query plan |

### Example requests

Create an employee:

```bash
curl -X POST http://127.0.0.1:8000/employees \
  -H 'Content-Type: application/json' \
  -d '{
    "emp_code": "EMP2001",
    "name": "Example Employee",
    "email": "example.employee@example.com",
    "department": "Engineering",
    "shift_start": "09:30",
    "shift_end": "18:30",
    "joined_on": "2026-10-01"
  }'
```

Check API health:

```bash
curl http://127.0.0.1:8000/health
```

The interactive Swagger documentation at `/docs` shows the request schemas and parameters for each endpoint.

### Admin explain endpoint keys

The `endpoint` path parameter accepts these keys:

- `attendance_list`
- `employee_monthly`
- `department_summary`
- `late_leaderboard`
- `department_trend`

Required query parameters depend on the selected key. For example, `department_trend` requires `department`, `from`, and `to`.

## Testing

Run the currently passing rules and contract tests:

```bash
pytest -q --ignore=tests/test_api.py
```

The current test result was **22 passed, 1 skipped**. A Starlette deprecation warning was also reported.

The legacy `tests/test_api.py` suite is excluded by this command because it currently has compatibility issues. Therefore, this result does not mean the entire unfiltered test suite passes.

## Project Structure

```text
candidate_kit/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── rules.py
│   ├── schemas.py
│   ├── serializers.py
│   └── ...
├── sample_data/
├── tests/
├── scripts/
├── sample_seed.py
├── openapi.yaml
├── DATA_MODEL.md
├── DECISIONS.md
├── REVIEW.md
├── requirements.txt
└── README.md
```

See `DATA_MODEL.md` for the data model and indexes, `DECISIONS.md` for design decisions, and `REVIEW.md` for review notes.
