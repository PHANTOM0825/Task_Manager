"""
Data models for the TaskManager application.

This module defines the core domain objects:

    - :class:`Priority` — Enum representing task urgency levels.
    - :class:`Status`   — Enum representing task lifecycle state.
    - :class:`Task`     — Immutable-ish task entity with validation.
    - :class:`User`     — User entity with hashed credential storage.

Design decisions
----------------
* Dataclasses are used for concise, readable model definitions.
* ``__post_init__`` performs lightweight field validation so every
  constructed object is always in a valid state (a TDD-friendly pattern:
  write the test first, then add the validation).
* Passwords are **never** stored in plaintext; the :mod:`security` module
  handles hashing at creation time.

Flow diagram (Task lifecycle)::

    [Created / PENDING]
          │
          ▼
    [Assigned → IN_PROGRESS]
          │
     ┌────┴───────┐
     ▼            ▼
  [DONE]      [CANCELLED]

Pseudocode — create_task workflow::

    FUNCTION create_task(title, description, priority, assigned_to):
        1. sanitise(title), sanitise(description)
        2. validate fields (non-empty title, valid priority)
        3. assign auto-incremented ID
        4. set status = PENDING, created_at = now()
        5. RETURN Task object
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from taskmanager.exceptions import InvalidTaskError
from taskmanager.security import sanitise_input, validate_username


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class Priority(str, Enum):
    """
    Task urgency levels.

    Inheriting from ``str`` makes serialisation to JSON trivial
    (``json.dumps(Priority.HIGH)`` → ``"HIGH"``).
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Status(str, Enum):
    """
    Task lifecycle states.

    State-transition rules are enforced by :class:`TaskManager`.
    """

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


# ---------------------------------------------------------------------------
# Task model
# ---------------------------------------------------------------------------


@dataclass
class Task:
    """
    Represents a single task entity.

    Attributes:
        id (int): Unique task identifier (auto-assigned by TaskManager).
        title (str): Short, descriptive title (1–200 characters).
        description (str): Detailed description of the task (max 2000 chars).
        priority (Priority): Urgency level of the task.
        status (Status): Current lifecycle state.
        owner (str): Username of the user who created the task.
        assigned_to (Optional[str]): Username of the assignee, or ``None``.
        created_at (datetime): UTC timestamp of task creation.
        updated_at (datetime): UTC timestamp of the last update.
        tags (list[str]): Optional list of keyword tags.

    Example::

        task = Task(
            id=1,
            title="Write CI pipeline",
            description="Set up GitHub Actions workflow.",
            priority=Priority.HIGH,
            status=Status.PENDING,
            owner="alice",
        )
    """

    id: int
    title: str
    description: str
    priority: Priority
    status: Status
    owner: str
    assigned_to: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: list = field(default_factory=list)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        """
        Validate fields immediately after construction.

        This follows the TDD principle of "fail fast" — if a test creates
        a Task with bad data the exception is raised at construction time,
        not buried in a later method call.

        Raises:
            InvalidTaskError: If any field fails its constraint.
        """
        # --- title ---
        if not isinstance(self.title, str) or not self.title.strip():
            raise InvalidTaskError("Title must be a non-empty string.")
        if len(self.title) > 200:
            raise InvalidTaskError("Title must not exceed 200 characters.")

        # --- description ---
        if not isinstance(self.description, str):
            raise InvalidTaskError("Description must be a string.")
        if len(self.description) > 2000:
            raise InvalidTaskError("Description must not exceed 2 000 characters.")

        # --- priority / status (enum coercion) ---
        if not isinstance(self.priority, Priority):
            try:
                self.priority = Priority(self.priority)
            except ValueError:
                raise InvalidTaskError(
                    f"Invalid priority '{self.priority}'. "
                    f"Valid values: {[p.value for p in Priority]}."
                )
        if not isinstance(self.status, Status):
            try:
                self.status = Status(self.status)
            except ValueError:
                raise InvalidTaskError(
                    f"Invalid status '{self.status}'. "
                    f"Valid values: {[s.value for s in Status]}."
                )

        # --- owner / assignee ---
        if not validate_username(self.owner):
            raise InvalidTaskError(
                "Owner username must be 3–50 alphanumeric/underscore/hyphen/dot chars."
            )
        if self.assigned_to is not None and not validate_username(self.assigned_to):
            raise InvalidTaskError("assigned_to contains an invalid username.")

        # --- id ---
        if not isinstance(self.id, int) or self.id < 1:
            raise InvalidTaskError("Task ID must be a positive integer.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """
        Serialise the task to a plain dictionary.

        Returns:
            dict: JSON-serialisable representation of the task.
        """
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value,
            "status": self.status.value,
            "owner": self.owner,
            "assigned_to": self.assigned_to,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "tags": self.tags,
        }

    def __repr__(self) -> str:
        return (
            f"Task(id={self.id}, title={self.title!r}, "
            f"priority={self.priority.value}, status={self.status.value})"
        )


# ---------------------------------------------------------------------------
# User model
# ---------------------------------------------------------------------------


@dataclass
class User:
    """
    Represents an application user.

    Passwords are stored as ``(hash_hex, salt_hex)`` pairs produced by
    :func:`~taskmanager.security.hash_password`.  Plaintext passwords are
    **never** stored in this object.

    Attributes:
        username (str): Unique username (validated by :func:`validate_username`).
        password_hash (str): Hex-encoded PBKDF2-HMAC-SHA256 password hash.
        salt (str): Hex-encoded random salt used to produce ``password_hash``.
        email (str): User's email address.
        is_admin (bool): Whether the user has administrative privileges.
        created_at (datetime): UTC timestamp of account creation.

    Example::

        from taskmanager.security import hash_password
        h, s = hash_password("p@ssw0rd!")
        user = User(username="alice", password_hash=h, salt=s,
                    email="alice@example.com")
    """

    username: str
    password_hash: str
    salt: str
    email: str
    is_admin: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    _EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    def __post_init__(self) -> None:
        """
        Validate username and email format.

        Raises:
            InvalidTaskError: If username or email format is invalid.
        """
        if not validate_username(self.username):
            raise InvalidTaskError(
                "Username must be 3–50 alphanumeric/underscore/hyphen/dot characters."
            )
        if not self._EMAIL_RE.match(self.email):
            raise InvalidTaskError(f"Email '{self.email}' is not a valid address.")

    def to_dict(self) -> dict:
        """
        Serialise the user to a plain dictionary (excluding credentials).

        Returns:
            dict: Safe representation without password_hash or salt.
        """
        return {
            "username": self.username,
            "email": self.email,
            "is_admin": self.is_admin,
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"User(username={self.username!r}, is_admin={self.is_admin})"
