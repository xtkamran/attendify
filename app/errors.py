"""Domain-level exceptions.

Routers raise these instead of HTTPException so that business logic stays
transport-agnostic. ``main.py`` installs a single handler that maps any
``DomainError`` to a consistent JSON error body: ``{"detail", "code"}``.
"""


class DomainError(Exception):
    status_code: int = 400
    code: str = "domain_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class EmployeeNotFound(DomainError):
    status_code = 404
    code = "employee_not_found"


class EmployeeAlreadyExists(DomainError):
    status_code = 409
    code = "employee_already_exists"


class AttendanceNotFound(DomainError):
    status_code = 404
    code = "attendance_not_found"


class OpenSessionExists(DomainError):
    """Employee tried to punch in while an earlier session is still open."""

    status_code = 409
    code = "open_session_exists"


class NoOpenSession(DomainError):
    """Employee tried to punch out with no open session."""

    status_code = 409
    code = "no_open_session"


class InvalidPunchSequence(DomainError):
    """punch_out is not strictly after punch_in."""

    status_code = 422
    code = "invalid_punch_sequence"


class NothingToCorrect(DomainError):
    status_code = 422
    code = "nothing_to_correct"
