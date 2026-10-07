"""
Test suite for taskmanager.exceptions
======================================

TDD workflow:
    These tests were written BEFORE the exception classes existed.
    Running the test suite at that stage produced ImportError / AttributeError
    failures, which drove the implementation of each exception class.

Coverage targets:
    - Exception instantiation
    - Message and code attributes
    - Repr strings
    - Exception hierarchy (all inherit from TaskManagerError)
"""

import pytest

from taskmanager.exceptions import (
    AuthenticationError,
    AuthorizationError,
    DuplicateTaskError,
    InvalidTaskError,
    TaskManagerError,
    TaskNotFoundError,
)

# ---------------------------------------------------------------------------
# TaskManagerError (base)
# ---------------------------------------------------------------------------


class TestTaskManagerError:
    """Tests for the base TaskManagerError exception."""

    def test_is_exception(self):
        """TaskManagerError must be a subclass of Exception."""
        assert issubclass(TaskManagerError, Exception)

    def test_message_attribute(self):
        """message attribute stores the description."""
        err = TaskManagerError("Something went wrong", code=1)
        assert err.message == "Something went wrong"

    def test_code_attribute(self):
        """code attribute stores the machine-readable error code."""
        err = TaskManagerError("Error", code=500)
        assert err.code == 500

    def test_default_code_zero(self):
        """code defaults to 0 when not provided."""
        err = TaskManagerError("Error")
        assert err.code == 0

    def test_str_representation(self):
        """str() returns the human-readable message."""
        err = TaskManagerError("Oops")
        assert str(err) == "Oops"

    def test_repr_representation(self):
        """repr() includes class name, message, and code."""
        err = TaskManagerError("Oops", code=99)
        r = repr(err)
        assert "TaskManagerError" in r
        assert "Oops" in r


# ---------------------------------------------------------------------------
# TaskNotFoundError
# ---------------------------------------------------------------------------


class TestTaskNotFoundError:
    """Tests for TaskNotFoundError."""

    def test_inherits_base(self):
        assert issubclass(TaskNotFoundError, TaskManagerError)

    def test_task_id_attribute(self):
        """task_id attribute stores the missing task ID."""
        err = TaskNotFoundError(task_id=42)
        assert err.task_id == 42

    def test_code_is_404(self):
        """HTTP-inspired code should be 404."""
        err = TaskNotFoundError(task_id=1)
        assert err.code == 404

    def test_message_contains_id(self):
        """Error message should mention the missing task ID."""
        err = TaskNotFoundError(task_id=99)
        assert "99" in err.message

    def test_is_raiseable(self):
        """Should be raiseable and catchable."""
        with pytest.raises(TaskNotFoundError) as exc_info:
            raise TaskNotFoundError(task_id=5)
        assert exc_info.value.task_id == 5


# ---------------------------------------------------------------------------
# InvalidTaskError
# ---------------------------------------------------------------------------


class TestInvalidTaskError:
    """Tests for InvalidTaskError."""

    def test_inherits_base(self):
        assert issubclass(InvalidTaskError, TaskManagerError)

    def test_reason_attribute(self):
        err = InvalidTaskError("Title is empty")
        assert err.reason == "Title is empty"

    def test_code_is_400(self):
        err = InvalidTaskError("Bad data")
        assert err.code == 400

    def test_message_contains_reason(self):
        err = InvalidTaskError("Too long")
        assert "Too long" in err.message

    @pytest.mark.parametrize(
        "reason",
        [
            "Title cannot be empty.",
            "Description too long.",
            "Invalid priority 'ULTRA'.",
        ],
    )
    def test_various_reasons(self, reason):
        """Parametrised: all reason strings are stored correctly."""
        err = InvalidTaskError(reason)
        assert err.reason == reason


# ---------------------------------------------------------------------------
# DuplicateTaskError
# ---------------------------------------------------------------------------


class TestDuplicateTaskError:
    """Tests for DuplicateTaskError."""

    def test_inherits_base(self):
        assert issubclass(DuplicateTaskError, TaskManagerError)

    def test_code_is_409(self):
        err = DuplicateTaskError(task_id=3)
        assert err.code == 409

    def test_task_id_stored(self):
        err = DuplicateTaskError(task_id=7)
        assert err.task_id == 7


# ---------------------------------------------------------------------------
# AuthenticationError
# ---------------------------------------------------------------------------


class TestAuthenticationError:
    """Tests for AuthenticationError."""

    def test_inherits_base(self):
        assert issubclass(AuthenticationError, TaskManagerError)

    def test_code_is_401(self):
        err = AuthenticationError()
        assert err.code == 401

    def test_default_reason(self):
        err = AuthenticationError()
        assert "Invalid credentials" in err.message

    def test_custom_reason(self):
        err = AuthenticationError("Token expired.")
        assert "Token expired" in err.message


# ---------------------------------------------------------------------------
# AuthorizationError
# ---------------------------------------------------------------------------


class TestAuthorizationError:
    """Tests for AuthorizationError."""

    def test_inherits_base(self):
        assert issubclass(AuthorizationError, TaskManagerError)

    def test_code_is_403(self):
        err = AuthorizationError(user="bob", action="delete", resource="task#1")
        assert err.code == 403

    def test_attributes(self):
        err = AuthorizationError(user="carol", action="update", resource="task#2")
        assert err.user == "carol"
        assert err.action == "update"
        assert err.resource == "task#2"

    def test_message_contains_details(self):
        err = AuthorizationError(user="dave", action="assign", resource="task#3")
        assert "dave" in err.message
        assert "assign" in err.message
        assert "task#3" in err.message
