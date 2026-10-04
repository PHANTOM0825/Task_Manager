"""
Test suite for taskmanager.validators
=======================================

TDD workflow used:
    - Each validator function was driven by the tests in this file.
    - Tests were committed before the corresponding implementation,
      causing CI failures that signalled "work still to do."
    - Once all tests passed, the CI pipeline turned green.

Sample data used in tests:
    Valid inputs:  "Fix bug", "Deploy app", Priority.HIGH, ["ci", "python"]
    Invalid inputs: "", "  ", "a"*201, None, "SELECT *", future datetime, past datetime

Coverage:
    - validate_title
    - validate_description
    - validate_priority
    - validate_due_date
    - validate_tags
    - validate_task_input (integration of all validators)
"""

from datetime import datetime, timedelta, timezone

import pytest

from taskmanager.exceptions import InvalidTaskError
from taskmanager.models import Priority
from taskmanager.validators import (
    validate_description,
    validate_due_date,
    validate_priority,
    validate_tags,
    validate_task_input,
    validate_title,
)


# ---------------------------------------------------------------------------
# validate_title
# ---------------------------------------------------------------------------


class TestValidateTitle:
    """Unit tests for validate_title."""

    def test_valid_title_returned(self):
        """Sample data: 'Fix bug #42' → returns the same string."""
        result = validate_title("Fix bug #42")
        assert result == "Fix bug #42"

    def test_strips_whitespace(self):
        """Surrounding whitespace is stripped."""
        assert validate_title("  Deploy app  ") == "Deploy app"

    def test_empty_string_raises(self):
        """Empty string → InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="empty"):
            validate_title("")

    def test_whitespace_only_raises(self):
        """Whitespace-only string → InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="empty"):
            validate_title("   ")

    def test_max_length_ok(self):
        """Title of exactly 200 characters is accepted."""
        validate_title("a" * 200)

    def test_too_long_raises(self):
        """Title of 201 characters → InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="200"):
            validate_title("a" * 201)

    def test_non_string_raises(self):
        """Non-string → InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="string"):
            validate_title(42)  # type: ignore

    def test_sql_injection_raises(self):
        """SQL injection in title → InvalidTaskError."""
        with pytest.raises(InvalidTaskError):
            validate_title("'; DROP TABLE tasks; --")

    def test_xss_attempt_raises(self):
        """The is_safe_string check rejects SQL-pattern titles; XSS escaping
        happens inside sanitise_input (not here), but SQL keywords still caught."""
        # "SELECT" is a flagged SQL keyword
        with pytest.raises(InvalidTaskError):
            validate_title("SELECT * FROM users")

    @pytest.mark.parametrize(
        "title",
        [
            "Write CI pipeline",
            "Refactor auth module",
            "Revise README.md",
            "Fix issue #123",
        ],
    )
    def test_common_valid_titles(self, title):
        """Parametrised sample data: common valid titles are accepted."""
        assert validate_title(title) == title


# ---------------------------------------------------------------------------
# validate_description
# ---------------------------------------------------------------------------


class TestValidateDescription:
    """Unit tests for validate_description."""

    def test_empty_description_allowed(self):
        """Sample data: '' → '' (description is optional)."""
        assert validate_description("") == ""

    def test_valid_description(self):
        """Sample data: normal sentence returns unchanged."""
        desc = "Push the release to production."
        assert validate_description(desc) == desc

    def test_max_length_ok(self):
        """Description of exactly 2000 characters is accepted."""
        validate_description("x" * 2000)

    def test_too_long_raises(self):
        """Description of 2001 characters → InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="2"):
            validate_description("x" * 2001)

    def test_non_string_raises(self):
        with pytest.raises(InvalidTaskError, match="string"):
            validate_description(None)  # type: ignore

    def test_sql_in_description_raises(self):
        """SQL pattern in description → InvalidTaskError."""
        with pytest.raises(InvalidTaskError):
            validate_description("UNION SELECT password FROM users WHERE 1=1")


# ---------------------------------------------------------------------------
# validate_priority
# ---------------------------------------------------------------------------


class TestValidatePriority:
    """Unit tests for validate_priority."""

    @pytest.mark.parametrize(
        "value, expected",
        [
            ("LOW", Priority.LOW),
            ("MEDIUM", Priority.MEDIUM),
            ("HIGH", Priority.HIGH),
            ("CRITICAL", Priority.CRITICAL),
            ("low", Priority.LOW),     # case-insensitive
            ("high", Priority.HIGH),
        ],
    )
    def test_string_coercion(self, value, expected):
        """Sample data: string values (case-insensitive) are coerced to Priority enum."""
        assert validate_priority(value) == expected

    @pytest.mark.parametrize("enum_val", list(Priority))
    def test_enum_passthrough(self, enum_val):
        """Priority enum values are returned as-is."""
        assert validate_priority(enum_val) == enum_val

    def test_invalid_string_raises(self):
        """Unrecognised string → InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="Priority"):
            validate_priority("ULTRA")

    def test_none_raises(self):
        """None → InvalidTaskError."""
        with pytest.raises(InvalidTaskError):
            validate_priority(None)  # type: ignore


# ---------------------------------------------------------------------------
# validate_due_date
# ---------------------------------------------------------------------------


class TestValidateDueDate:
    """Unit tests for validate_due_date."""

    def test_none_accepted(self):
        """Sample data: None → None (due date is optional)."""
        assert validate_due_date(None) is None

    def test_future_date_accepted(self):
        """Sample data: a date far in the future is accepted."""
        future = datetime(2099, 12, 31, tzinfo=timezone.utc)
        assert validate_due_date(future) == future

    def test_past_date_raises(self):
        """Sample data: a past date raises InvalidTaskError."""
        past = datetime(2000, 1, 1, tzinfo=timezone.utc)
        with pytest.raises(InvalidTaskError, match="future"):
            validate_due_date(past)

    def test_now_raises(self):
        """A date that is 'now' (or just passed) should raise."""
        just_past = datetime.now(timezone.utc) - timedelta(seconds=1)
        with pytest.raises(InvalidTaskError, match="future"):
            validate_due_date(just_past)

    def test_naive_datetime_raises(self):
        """Timezone-naive datetime raises InvalidTaskError."""
        naive = datetime(2099, 1, 1)  # no tzinfo
        with pytest.raises(InvalidTaskError, match="timezone"):
            validate_due_date(naive)

    def test_non_datetime_raises(self):
        """Non-datetime value raises InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="datetime"):
            validate_due_date("2099-01-01")  # type: ignore


# ---------------------------------------------------------------------------
# validate_tags
# ---------------------------------------------------------------------------


class TestValidateTags:
    """Unit tests for validate_tags."""

    def test_none_returns_empty_list(self):
        """Sample data: None → []."""
        assert validate_tags(None) == []

    def test_empty_list_ok(self):
        """Empty list → []."""
        assert validate_tags([]) == []

    def test_valid_tags(self):
        """Sample data: ['ci', 'python'] → ['ci', 'python']."""
        assert validate_tags(["ci", "python"]) == ["ci", "python"]

    def test_strips_tag_whitespace(self):
        """Tags with surrounding whitespace are stripped."""
        assert validate_tags(["  ci  "]) == ["ci"]

    def test_max_tags_ok(self):
        """Exactly 10 tags are accepted."""
        validate_tags([f"tag{i}" for i in range(10)])

    def test_too_many_tags_raises(self):
        """11 tags → InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="10"):
            validate_tags([f"tag{i}" for i in range(11)])

    def test_empty_tag_raises(self):
        """Empty string tag → InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="non-empty"):
            validate_tags(["valid", ""])

    def test_whitespace_only_tag_raises(self):
        """Whitespace-only tag → InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="non-empty"):
            validate_tags(["   "])

    def test_tag_too_long_raises(self):
        """Tag > 50 chars → InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="50"):
            validate_tags(["a" * 51])

    def test_non_list_raises(self):
        """Non-list → InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="list"):
            validate_tags("notalist")  # type: ignore


# ---------------------------------------------------------------------------
# validate_task_input (integration)
# ---------------------------------------------------------------------------


class TestValidateTaskInput:
    """Integration tests for validate_task_input (combines all validators)."""

    def test_valid_full_input(self):
        """Sample data: all valid fields return clean dict."""
        result = validate_task_input(
            title="Deploy application",
            description="Push to production environment.",
            priority="HIGH",
            tags=["deploy", "production"],
        )
        assert result["title"] == "Deploy application"
        assert result["description"] == "Push to production environment."
        assert result["priority"] == Priority.HIGH
        assert result["tags"] == ["deploy", "production"]
        assert result["due_date"] is None

    def test_minimal_valid_input(self):
        """Minimal required fields (no tags, no due_date)."""
        result = validate_task_input(
            title="Write tests",
            description="",
            priority="LOW",
        )
        assert result["title"] == "Write tests"
        assert result["tags"] == []

    def test_invalid_title_propagates(self):
        """InvalidTaskError from title validator propagates out."""
        with pytest.raises(InvalidTaskError):
            validate_task_input(title="", description="ok", priority="LOW")

    def test_invalid_priority_propagates(self):
        """InvalidTaskError from priority validator propagates out."""
        with pytest.raises(InvalidTaskError):
            validate_task_input(
                title="Valid title", description="ok", priority="ULTRA"
            )

    def test_future_due_date_accepted(self):
        """Future due_date is returned in the result dict."""
        future = datetime(2099, 6, 1, tzinfo=timezone.utc)
        result = validate_task_input(
            title="CI workshop",
            description="Hands-on session",
            priority="MEDIUM",
            due_date=future,
        )
        assert result["due_date"] == future
