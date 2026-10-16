# Design Decisions

This document describes the current Employee Attendance & Analytics API
implementation. Decisions below are based on the current application code.

## 1. Framework and database driver

**Decision:** FastAPI with synchronous PyMongo.

**Implementation:** MongoDB connections and index initialization are handled
in `app/database.py`. Application settings are defined in `app/config.py`.

**Trade-off:** Synchronous database operations are straightforward to maintain,
but they can block a worker while waiting for MongoDB. An async database driver
or synchronous route execution in a worker thread could be considered if
concurrency requirements justify the additional complexity.

## 2. Configuration

**Decision:** Use Pydantic Settings for application configuration.

Current defaults include:

- MongoDB URI: `mongodb://localhost:27017`
- Database: `attendance`
- Timezone setting: `Asia/Kolkata`
- Default shift: `09:30`–`18:30`
- Late grace period: 10 minutes
- Maximum session: 960 minutes
- Minimum session: 5 minutes

Environment variables can override applicable settings. Local configuration
belongs in `.env`, which must not be committed. `.env.example` documents
the example configuration.

## 3. Data model

**Decision:** Store employee information and attendance records in separate
MongoDB collections.

- `employees`: employee details, including `emp_code`, department, shift
  information and joining date.
- `attendance_logs`: attendance records associated with `emp_code` and date.

The unique employee-code index prevents duplicate employee codes.
The unique `(emp_code, date)` index prevents multiple attendance records for
the same employee and date.

## 4. Database indexes

`app/database.py` defines the following indexes:

- Unique `employees.emp_code`
- Unique `attendance_logs(emp_code, date)`
- `attendance_logs(department, date)`
- `attendance_logs(date, late_minutes)`
- `attendance_logs(emp_code, punch_in DESC)`
- `employees(department, joined_on)`

These indexes support uniqueness and common attendance, department,
employee-history and reporting queries.

Index creation should remain consistent between normal application startup
and any seed or setup workflow.

## 5. Time handling and input validation

**Decision:** Attendance punch timestamps are supplied as epoch milliseconds.

The API validates timestamp inputs; ISO timestamp strings, floating-point
timestamps and epoch seconds are not accepted where an integer epoch-millisecond
value is required.

`app/rules.py` contains time-related helper functions. Its `ensure_utc`
function normalizes aware datetimes to UTC and treats naive datetimes as UTC.

The shift-time interpretation and reporting timezone should be reviewed
against the official assignment requirements if those requirements specify
a different timezone convention.

## 6. Attendance business rules

Business-rule helpers are kept in `app/rules.py` where applicable.

The current configuration defines a late grace period, maximum session length
and minimum session length. Punch-out must occur strictly after punch-in.
The application calculates attendance-related values and validates requests
before completing attendance operations.

The official assignment specification remains the source of truth for any
boundary conditions not explicitly documented here.

## 7. Attendance regularization

**Decision:** Attendance records can be corrected through the current
regularization endpoint:

`PATCH /attendance/{emp_code}/{attendance_date}`

The request includes a reason and the identity of the person performing
the regularization. The current response includes a history of changes.

Regularization should recalculate affected attendance values and preserve
the change history. Any additional audit guarantees should be verified against
the implementation and the assignment requirements.

## 8. Analytics and reporting

The current analytics endpoints are:

- `GET /analytics/employees/{emp_code}/monthly`
- `GET /analytics/departments/summary`
- `GET /analytics/leaderboard/late`
- `GET /analytics/departments/{department}/trend`

These endpoints provide employee-level monthly attendance metrics,
department summaries, late-arrival rankings and department trends.

`GET /admin/explain/{endpoint}` exposes query-plan information for supported
analytics/list operations. It is useful for inspecting index usage and query
execution statistics.

## 9. API contract and documentation

The main application routes are defined in `app/main.py`.

The saved `openapi.yaml` was compared with the running application's
`/openapi.json`; paths, HTTP methods, component schemas and the full
specification matched at the time of verification.

Regenerate or re-verify the saved OpenAPI document whenever API routes,
schemas or response models change.

## 10. Testing strategy and limitations

The current test setup uses synchronous FastAPI `TestClient` and
`mongomock` fixtures for isolated tests.

The verified command is:

`pytest -q --ignore=tests/test_api.py`

The last recorded result was 22 passed and 1 skipped.

The legacy `tests/test_api.py` currently uses an older API contract and
async calls against a synchronous test client. Running it separately produced
failures and a missing `supports_round` fixture. Therefore, the complete
test suite is not yet confirmed as passing.

These limitations should be resolved or explicitly documented before claiming
that all tests pass.

## 11. Scope and future improvements

Potential improvements should be prioritized according to the assignment:

- Resolve or replace tests written for the obsolete API contract.
- Verify index creation consistently across startup and seed workflows.
- Add tests for attendance boundaries, regularization and analytics.
- Review database concurrency guarantees for attendance writes.
- Review authentication and authorization if required by the deployment
  environment.

No claim is made that these future improvements are already implemented.
