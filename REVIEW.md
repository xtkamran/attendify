# Code Review

## Scope and limitation

The original code snippet for the code-review exercise was not available
when this document was prepared. The review below evaluates a representative
punch-in/punch-out implementation, not a confirmed copy of the original
assessment snippet.

The findings are general engineering observations. They must not be treated
as proof that the current application has every issue described below.

## Representative implementation

A typical naive implementation might:

- Use one endpoint to toggle between punch-in and punch-out.
- Store naive local timestamps.
- Calculate work duration using `timedelta.seconds`.
- Check for an open session before inserting a record.
- Use untyped request data and return ad hoc responses.

These patterns can cause correctness, concurrency and maintainability issues.

## Findings

### 1. Duration calculations

Using `timedelta.seconds` discards the day component of a duration. Sessions
lasting overnight or longer than 24 hours can therefore produce incorrect
durations.

**Recommendation:** Use `total_seconds()` and calculate integer worked minutes
with an explicitly documented rounding policy.

### 2. Timezone handling

Naive local timestamps can be interpreted differently across machines and
timezones.

**Recommendation:** Normalize timestamps consistently, document how naive
inputs are interpreted, and use the reporting timezone required by the
business contract.

### 3. Punch sequence validation

A punch-out at or before punch-in must not produce a valid completed session.

**Recommendation:** Reject invalid sequences and test boundary conditions.

### 4. Concurrent attendance writes

An application-level check followed by an insert can race when multiple
requests arrive simultaneously.

**Recommendation:** Define the attendance invariant first and enforce it
using an appropriate database constraint or atomic operation. The constraint
must match the actual data model.

The current application defines a unique index on `(emp_code, date)`.
That is not the same as a partial unique index on open sessions, so the two
designs must not be described as equivalent.

### 5. Explicit API operations

A single endpoint that silently switches between punch-in and punch-out
makes retries and client intent harder to reason about.

**Recommendation:** Use explicit operations and return clear validation and
conflict responses.

The current application exposes separate punch-in and punch-out endpoints.

### 6. Database access and lifecycle

Synchronous database operations can block a worker while waiting for MongoDB.
Creating connections at module import time can also make testing and lifecycle
management more difficult.

**Recommendation:** Manage database connections through application startup
and shutdown, and evaluate an asynchronous driver or worker-thread approach
when justified by concurrency requirements.

The current application uses synchronous PyMongo and defines connection,
index-initialization and close functions in `app/database.py`.

### 7. Indexes and query performance

Queries without suitable indexes may require collection scans.

**Recommendation:** Review actual query filters and sort orders, add indexes
for demonstrated access patterns, and inspect query plans rather than assuming
an index is being used.

The current application defines employee, attendance-date, department,
late-minute and employee-history indexes.

### 8. Validation and API contracts

Untyped request data and inconsistent error responses make clients harder
to maintain.

**Recommendation:** Use request/response schemas, validate inputs, and keep
HTTP status codes and error responses consistent with the documented API.

The current application uses FastAPI and Pydantic schemas.

## Verification before sign-off

Recommended checks include:

- Unit tests for overnight and long-session duration calculations.
- Boundary tests for punch-in, punch-out and late-grace calculations.
- Duplicate employee and duplicate attendance-record tests.
- Regularization tests that verify recalculation and change history.
- Analytics tests using representative data.
- Concurrency tests for the attendance invariant required by the assignment.
- Verification that the saved OpenAPI specification matches the running app.

## Test status

The last verified supported test command was:

`pytest -q --ignore=tests/test_api.py`

Result: 22 passed, 1 skipped.

The legacy `tests/test_api.py` currently fails because it uses async calls
against a synchronous `TestClient`, expects older endpoint contracts, and
references a missing `supports_round` fixture. The full test suite therefore
must not be reported as passing yet.

## Conclusion

The review identifies common risks in attendance systems and records the
current implementation facts separately. Before using this review as the
final assessment submission, compare it with the actual code snippet supplied
by the assessment, if that snippet becomes available.
