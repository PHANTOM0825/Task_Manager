"""
Input validation utilities for the TaskManager application.

This module provides standalone validation functions used by both the
:class:`~taskmanager.models.Task` dataclass and the
:class:`~taskmanager.manager.TaskManager` service layer.

Keeping validators in their own module:
    - Avoids circular imports (models → validators, not validators → models).
    - Makes them easy to unit-test in isolation (TDD workflow step: write
      the test for each validator before implementing the function body).
    - Provides a single place to tighten or loosen constraints.

Flow diagram — validate_task_input::

    START
      │
      ▼
    title empty? ──YES──► raise InvalidTaskError("Title required")
      │ NO
      ▼
    title > 200 chars? ──YES──► raise InvalidTaskError("Title too long")
      │ NO
      ▼
    description > 2000? ──YES──► raise InvalidTaskError("Desc too long")
      │ NO
      ▼
    priority valid? ──NO──► raise InvalidTaskError("Bad priority")
      │ YES
      ▼
    RETURN True

Pseudocode — validate_due_date::

    FUNCTION validate_due_date(due_date):
        IF due_date is None: RETURN True   # optional field
        IF due_date is not datetime: RAISE TypeError
        IF due_date <= now(): RAISE InvalidTaskError("Past date")
        RETURN True
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from taskmanager.exceptions import InvalidTaskError
from taskmanager.models import Priority
from taskmanager.security import is_safe_string

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TITLE_MAX_LEN: int = 200
DESCRIPTION_MAX_LEN: int = 2_000
TAG_MAX_LEN: int = 50
MAX_TAGS: int = 10


# ---------------------------------------------------------------------------
# Public validators
# ---------------------------------------------------------------------------


def validate_title(title: Any) -> str:
    """
    Validate and return a sanitised task title.

    Rules:
        - Must be a non-empty string.
        - After stripping whitespace, must be 1–200 characters.
        - Must not contain SQL-injection or script-injection patterns.

    Args:
        title (Any): Raw title value.

    Returns:
        str: The stripped, validated title.

    Raises:
        InvalidTaskError: If any rule is violated.

    TDD notes:
        Tests were written for empty string, whitespace-only, too-long,
        and injection-containing titles *before* this function was coded.

    Sample data tests::

        validate_title("Fix bug #42")          # → "Fix bug #42"
        validate_title("")                      # → InvalidTaskError
        validate_title("  ")                   # → InvalidTaskError
        validate_title("a" * 201)              # → InvalidTaskError
        validate_title("<script>")             # → InvalidTaskError (XSS)
    """
    if not isinstance(title, str):
        raise InvalidTaskError("Title must be a string.")
    stripped = title.strip()
    if not stripped:
        raise InvalidTaskError("Title cannot be empty or whitespace-only.")
    if len(stripped) > TITLE_MAX_LEN:
        raise InvalidTaskError(
            f"Title must not exceed {TITLE_MAX_LEN} characters " f"(got {len(stripped)})."
        )
    if not is_safe_string(stripped):
        raise InvalidTaskError("Title contains potentially unsafe characters or SQL keywords.")
    return stripped


def validate_description(description: Any) -> str:
    """
    Validate and return a sanitised task description.

    Rules:
        - Must be a string (may be empty).
        - Must not exceed 2 000 characters.
        - Must not contain injection patterns.

    Args:
        description (Any): Raw description value.

    Returns:
        str: Validated description (may be empty string).

    Raises:
        InvalidTaskError: If any rule is violated.

    Sample data tests::

        validate_description("")               # → ""  (allowed)
        validate_description("Do the thing.")  # → "Do the thing."
        validate_description("a" * 2001)       # → InvalidTaskError
    """
    if not isinstance(description, str):
        raise InvalidTaskError("Description must be a string.")
    if len(description) > DESCRIPTION_MAX_LEN:
        raise InvalidTaskError(f"Description must not exceed {DESCRIPTION_MAX_LEN} characters.")
    if description and not is_safe_string(description):
        raise InvalidTaskError("Description contains potentially unsafe content.")
    return description


def validate_priority(priority: Any) -> Priority:
    """
    Validate and coerce a priority value to a :class:`~taskmanager.models.Priority` enum.

    Args:
        priority (Any): Raw priority value (string or Priority enum).

    Returns:
        Priority: The validated Priority enum member.

    Raises:
        InvalidTaskError: If the value is not a valid Priority.

    Sample data tests::

        validate_priority("HIGH")            # → Priority.HIGH
        validate_priority(Priority.LOW)      # → Priority.LOW
        validate_priority("UNKNOWN")         # → InvalidTaskError
    """
    if isinstance(priority, Priority):
        return priority
    if isinstance(priority, str):
        try:
            return Priority(priority.upper())
        except ValueError:
            pass
    valid = [p.value for p in Priority]
    raise InvalidTaskError(f"Priority must be one of {valid}; got '{priority}'.")


def validate_due_date(due_date: Optional[datetime]) -> Optional[datetime]:
    """
    Validate an optional task due date.

    Rules:
        - ``None`` is accepted (due date is optional).
        - Must be a timezone-aware :class:`datetime` object.
        - Must be in the future relative to the current UTC time.

    Args:
        due_date (Optional[datetime]): The due date to validate.

    Returns:
        Optional[datetime]: The validated due date, or ``None``.

    Raises:
        InvalidTaskError: If the due date is in the past or not a datetime.

    Sample data tests::

        validate_due_date(None)                             # → None
        validate_due_date(datetime(2099, 1, 1, tzinfo=...)) # → same datetime
        validate_due_date(datetime(2000, 1, 1, tzinfo=...)) # → InvalidTaskError
    """
    if due_date is None:
        return None
    if not isinstance(due_date, datetime):
        raise InvalidTaskError("due_date must be a datetime object.")
    if due_date.tzinfo is None:
        raise InvalidTaskError("due_date must be timezone-aware (use UTC).")
    if due_date <= datetime.now(timezone.utc):
        raise InvalidTaskError("due_date must be a future date/time.")
    return due_date


def validate_tags(tags: Any) -> list:
    """
    Validate a list of string tags.

    Rules:
        - Must be a list (or None → treated as empty list).
        - At most 10 tags per task.
        - Each tag must be a non-empty string ≤ 50 characters.

    Args:
        tags (Any): Raw tags value.

    Returns:
        list[str]: Validated list of tag strings.

    Raises:
        InvalidTaskError: If any rule is violated.

    Sample data tests::

        validate_tags(None)                    # → []
        validate_tags(["ci", "python"])        # → ["ci", "python"]
        validate_tags(["x"] * 11)             # → InvalidTaskError (too many)
        validate_tags([" "])                   # → InvalidTaskError (empty tag)
    """
    if tags is None:
        return []
    if not isinstance(tags, list):
        raise InvalidTaskError("tags must be a list of strings.")
    if len(tags) > MAX_TAGS:
        raise InvalidTaskError(f"A task may have at most {MAX_TAGS} tags.")
    validated = []
    for tag in tags:
        if not isinstance(tag, str) or not tag.strip():
            raise InvalidTaskError("Each tag must be a non-empty string.")
        if len(tag) > TAG_MAX_LEN:
            raise InvalidTaskError(
                f"Tag '{tag}' exceeds maximum length of {TAG_MAX_LEN} characters."
            )
        validated.append(tag.strip())
    return validated


def validate_task_input(
    title: Any,
    description: Any,
    priority: Any,
    tags: Any = None,
    due_date: Optional[datetime] = None,
) -> dict:
    """
    Validate all task input fields and return a clean dict.

    This is a convenience wrapper that calls all individual validators
    in sequence, collecting the first error encountered.

    Args:
        title (Any): Task title.
        description (Any): Task description.
        priority (Any): Task priority.
        tags (Any): Optional list of tags.
        due_date (Optional[datetime]): Optional due date.

    Returns:
        dict: Validated and cleaned input fields.

    Raises:
        InvalidTaskError: On the first validation failure.

    Sample data tests::

        result = validate_task_input(
            title="Deploy app",
            description="Push to production.",
            priority="HIGH",
        )
        # result == {
        #   "title": "Deploy app",
        #   "description": "Push to production.",
        #   "priority": Priority.HIGH,
        #   "tags": [],
        #   "due_date": None,
        # }
    """
    return {
        "title": validate_title(title),
        "description": validate_description(description),
        "priority": validate_priority(priority),
        "tags": validate_tags(tags),
        "due_date": validate_due_date(due_date),
    }
