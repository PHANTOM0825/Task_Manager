"""
Test suite for taskmanager.models
====================================

TDD workflow:
    These tests define the expected contract for Task and User dataclasses.
    The ``__post_init__`` validators in both classes were added *after*
    writing failing tests for invalid inputs.

Sample data used:
    Valid task: id=1, title="Write tests", priority=Priority.HIGH, owner="alice"
    Invalid task: id=0 (bad ID), title="" (empty), priority="UNKNOWN"

Coverage:
    - Task construction (valid and invalid)
    - Priority / Status enum coercion
    - Task.to_dict() serialisation
    - Task.__repr__()
    - User construction (valid and invalid)
    - User.to_dict() (credentials excluded)
"""

import pytest

from taskmanager.exceptions import InvalidTaskError
from taskmanager.models import Priority, Status, Task, User
from taskmanager.security import hash_password

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_valid_task(**overrides) -> Task:
    """Return a valid Task, optionally overriding default fields."""
    defaults = dict(
        id=1,
        title="Write CI pipeline",
        description="Set up GitHub Actions.",
        priority=Priority.HIGH,
        status=Status.PENDING,
        owner="alice",
    )
    defaults.update(overrides)
    return Task(**defaults)


def make_valid_user(**overrides) -> User:
    """Return a valid User with hashed password."""
    h, s = hash_password("p@ssword!")
    defaults = dict(
        username="alice",
        password_hash=h,
        salt=s,
        email="alice@example.com",
    )
    defaults.update(overrides)
    return User(**defaults)


# ---------------------------------------------------------------------------
# Task construction
# ---------------------------------------------------------------------------


class TestTaskConstruction:
    """Tests for Task dataclass construction."""

    def test_valid_task_created(self):
        """Sample data: all valid fields → Task constructed without error."""
        task = make_valid_task()
        assert task.id == 1
        assert task.title == "Write CI pipeline"
        assert task.priority == Priority.HIGH
        assert task.status == Status.PENDING
        assert task.owner == "alice"

    def test_string_priority_coerced(self):
        """String priority 'HIGH' should be coerced to Priority.HIGH."""
        task = make_valid_task(priority="HIGH")
        assert task.priority == Priority.HIGH

    def test_string_status_coerced(self):
        """String status 'PENDING' should be coerced to Status.PENDING."""
        task = make_valid_task(status="PENDING")
        assert task.status == Status.PENDING

    def test_invalid_priority_raises(self):
        """Sample data: priority='ULTRA' → InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="priority"):
            make_valid_task(priority="ULTRA")

    def test_invalid_status_raises(self):
        """Sample data: status='UNKNOWN' → InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="status"):
            make_valid_task(status="UNKNOWN")

    def test_empty_title_raises(self):
        """Sample data: title='' → InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="Title"):
            make_valid_task(title="")

    def test_whitespace_title_raises(self):
        """Whitespace-only title → InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="Title"):
            make_valid_task(title="   ")

    def test_title_too_long_raises(self):
        """Title of 201 chars → InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="200"):
            make_valid_task(title="a" * 201)

    def test_description_too_long_raises(self):
        """Description of 2001 chars → InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="2"):
            make_valid_task(description="x" * 2001)

    def test_non_string_description_raises(self):
        """Non-string description → InvalidTaskError."""
        with pytest.raises(InvalidTaskError):
            make_valid_task(description=123)  # type: ignore

    def test_invalid_id_zero_raises(self):
        """Sample data: id=0 → InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="ID"):
            make_valid_task(id=0)

    def test_negative_id_raises(self):
        """Negative ID → InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="ID"):
            make_valid_task(id=-1)

    def test_invalid_owner_raises(self):
        """Owner with spaces → InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="Owner"):
            make_valid_task(owner="bad owner")

    def test_invalid_assignee_raises(self):
        """Invalid assignee username → InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="assigned_to"):
            make_valid_task(assigned_to="bad assignee")

    def test_valid_assignee(self):
        """Valid assignee username → no error."""
        task = make_valid_task(assigned_to="bob")
        assert task.assigned_to == "bob"

    def test_none_assignee_ok(self):
        """assigned_to=None → no error (task not yet assigned)."""
        task = make_valid_task(assigned_to=None)
        assert task.assigned_to is None

    def test_default_tags_empty(self):
        """Default tags should be an empty list."""
        task = make_valid_task()
        assert task.tags == []

    def test_tags_stored(self):
        """Tags provided at construction are stored."""
        task = make_valid_task(tags=["ci", "python"])
        assert task.tags == ["ci", "python"]


# ---------------------------------------------------------------------------
# Task.to_dict()
# ---------------------------------------------------------------------------


class TestTaskToDict:
    """Tests for Task.to_dict() serialisation."""

    def test_returns_dict(self):
        """to_dict() returns a plain dict."""
        task = make_valid_task()
        assert isinstance(task.to_dict(), dict)

    def test_all_keys_present(self):
        """All expected keys are present in the dict."""
        expected_keys = {
            "id",
            "title",
            "description",
            "priority",
            "status",
            "owner",
            "assigned_to",
            "created_at",
            "updated_at",
            "tags",
        }
        task = make_valid_task()
        assert set(task.to_dict().keys()) == expected_keys

    def test_priority_is_string(self):
        """priority in dict is a string (not enum)."""
        task = make_valid_task()
        assert isinstance(task.to_dict()["priority"], str)

    def test_status_is_string(self):
        """status in dict is a string (not enum)."""
        task = make_valid_task()
        assert isinstance(task.to_dict()["status"], str)

    def test_created_at_is_iso_string(self):
        """created_at in dict is an ISO-formatted string."""
        task = make_valid_task()
        d = task.to_dict()
        # Should parse without error
        from datetime import datetime

        datetime.fromisoformat(d["created_at"])

    def test_values_correct(self):
        """Sample data: dict values match Task attributes."""
        task = make_valid_task()
        d = task.to_dict()
        assert d["id"] == 1
        assert d["title"] == "Write CI pipeline"
        assert d["priority"] == "HIGH"
        assert d["status"] == "PENDING"


# ---------------------------------------------------------------------------
# Task.__repr__()
# ---------------------------------------------------------------------------


class TestTaskRepr:
    def test_repr_contains_id_and_title(self):
        task = make_valid_task()
        r = repr(task)
        assert "1" in r
        assert "Write CI pipeline" in r

    def test_repr_contains_priority_and_status(self):
        task = make_valid_task()
        r = repr(task)
        assert "HIGH" in r
        assert "PENDING" in r


# ---------------------------------------------------------------------------
# Priority enum
# ---------------------------------------------------------------------------


class TestPriorityEnum:
    @pytest.mark.parametrize("value", ["LOW", "MEDIUM", "HIGH", "CRITICAL"])
    def test_all_values_exist(self, value):
        """All expected priority levels exist."""
        p = Priority(value)
        assert p.value == value

    def test_is_str(self):
        """Priority inherits from str — JSON-serialisable directly."""
        assert isinstance(Priority.HIGH, str)


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------


class TestStatusEnum:
    @pytest.mark.parametrize("value", ["PENDING", "IN_PROGRESS", "DONE", "CANCELLED"])
    def test_all_values_exist(self, value):
        s = Status(value)
        assert s.value == value


# ---------------------------------------------------------------------------
# User model
# ---------------------------------------------------------------------------


class TestUserModel:
    """Tests for User dataclass."""

    def test_valid_user_created(self):
        """Sample data: valid user is constructed without error."""
        user = make_valid_user()
        assert user.username == "alice"
        assert user.email == "alice@example.com"
        assert user.is_admin is False

    def test_password_hash_stored(self):
        """password_hash attribute should be a non-empty hex string."""
        user = make_valid_user()
        assert len(user.password_hash) > 0

    def test_plaintext_not_stored(self):
        """The plaintext password must not appear in any attribute."""
        user = make_valid_user()
        attrs = vars(user)
        for val in attrs.values():
            assert "p@ssword!" not in str(val)

    def test_invalid_username_raises(self):
        """Sample data: username with space → InvalidTaskError."""
        h, s = hash_password("pw")
        with pytest.raises(InvalidTaskError, match="Username"):
            User(username="bad user", password_hash=h, salt=s, email="a@b.com")

    def test_invalid_email_raises(self):
        """Sample data: malformed email → InvalidTaskError."""
        h, s = hash_password("pw")
        with pytest.raises(InvalidTaskError, match="Email"):
            User(username="alice", password_hash=h, salt=s, email="not-an-email")

    def test_admin_flag(self):
        """is_admin=True is stored correctly."""
        user = make_valid_user(is_admin=True)
        assert user.is_admin is True

    def test_to_dict_excludes_credentials(self):
        """to_dict() must NOT include password_hash or salt."""
        user = make_valid_user()
        d = user.to_dict()
        assert "password_hash" not in d
        assert "salt" not in d

    def test_to_dict_includes_basics(self):
        """to_dict() includes username, email, is_admin, created_at."""
        user = make_valid_user()
        d = user.to_dict()
        assert d["username"] == "alice"
        assert d["email"] == "alice@example.com"
        assert "created_at" in d

    def test_repr(self):
        user = make_valid_user()
        r = repr(user)
        assert "alice" in r
