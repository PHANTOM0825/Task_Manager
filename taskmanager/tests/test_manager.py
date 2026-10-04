"""
Test suite for taskmanager.manager (TaskManager service)
==========================================================

TDD workflow:
    This is the highest-level test module.  Each test maps to a user story:

    Story 1:  "As Alice I can register and log in."
              → test_register_and_login, test_login_wrong_password

    Story 2:  "As Alice I can create tasks."
              → test_create_task_*, test_create_task_invalid_*

    Story 3:  "As Alice I can assign my task to Bob."
              → test_assign_task_*

    Story 4:  "As Alice I can complete and cancel tasks."
              → test_complete_task_*, test_cancel_task_*

    Story 5:  "As an admin I can perform any action."
              → test_admin_can_*

    Story 6:  "Statistics give me an overview."
              → test_get_statistics_*

Sample data:
    owner="alice", title="Write tests", priority="HIGH"
    assignee="bob"
    admin="admin_user"

Coverage:
    - register_user / login / logout / get_user_from_token
    - create_task (valid + invalid + unauthorised owner)
    - get_task / list_tasks (filters)
    - update_task
    - assign_task
    - complete_task / cancel_task
    - delete_task
    - get_statistics
    - Authorization rules (owner vs non-owner vs admin)
"""

import pytest

from taskmanager.exceptions import (
    AuthenticationError,
    AuthorizationError,
    InvalidTaskError,
    TaskNotFoundError,
)
from taskmanager.manager import TaskManager
from taskmanager.models import Priority, Status


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def manager():
    """Return a fresh TaskManager for each test (isolation)."""
    return TaskManager()


@pytest.fixture
def manager_with_users(manager):
    """TaskManager pre-populated with alice, bob, and an admin."""
    manager.register_user("alice", "alice_pass!", "alice@example.com")
    manager.register_user("bob", "bob_pass!", "bob@example.com")
    manager.register_user("admin_user", "admin_pass!", "admin@example.com", is_admin=True)
    return manager


@pytest.fixture
def manager_with_tasks(manager_with_users):
    """TaskManager with users + two tasks owned by alice."""
    manager_with_users.create_task(
        owner="alice",
        title="Write CI pipeline",
        description="Set up GitHub Actions.",
        priority="HIGH",
        tags=["ci", "devops"],
    )
    manager_with_users.create_task(
        owner="alice",
        title="Write unit tests",
        description="Achieve 90% coverage.",
        priority="MEDIUM",
    )
    return manager_with_users


# ---------------------------------------------------------------------------
# User registration & authentication
# ---------------------------------------------------------------------------


class TestUserRegistration:
    """Tests for register_user."""

    def test_register_new_user(self, manager):
        """Sample data: alice registers successfully."""
        user = manager.register_user("alice", "pass!", "alice@example.com")
        assert user.username == "alice"
        assert user.email == "alice@example.com"

    def test_register_duplicate_raises(self, manager):
        """Registering the same username twice raises an error."""
        manager.register_user("alice", "pass1", "a@b.com")
        with pytest.raises(Exception):  # DuplicateTaskError or similar
            manager.register_user("alice", "pass2", "a2@b.com")

    def test_register_invalid_username_raises(self, manager):
        """Username with spaces → error."""
        with pytest.raises(InvalidTaskError):
            manager.register_user("bad user", "pass", "a@b.com")

    def test_register_invalid_email_raises(self, manager):
        """Malformed email → error."""
        with pytest.raises(InvalidTaskError):
            manager.register_user("alice", "pass", "not-an-email")


class TestLogin:
    """Tests for login / logout / get_user_from_token."""

    def test_correct_credentials_return_token(self, manager_with_users):
        """Sample data: alice logs in with correct password → token string."""
        token = manager_with_users.login("alice", "alice_pass!")
        assert isinstance(token, str) and len(token) > 0

    def test_wrong_password_raises(self, manager_with_users):
        """Wrong password → AuthenticationError."""
        with pytest.raises(AuthenticationError):
            manager_with_users.login("alice", "wrong_password")

    def test_unknown_user_raises(self, manager_with_users):
        """Unknown username → AuthenticationError."""
        with pytest.raises(AuthenticationError):
            manager_with_users.login("ghost", "anything")

    def test_token_resolves_to_user(self, manager_with_users):
        """get_user_from_token returns the correct User for a valid token."""
        token = manager_with_users.login("alice", "alice_pass!")
        user = manager_with_users.get_user_from_token(token)
        assert user.username == "alice"

    def test_logout_invalidates_token(self, manager_with_users):
        """After logout, the token is rejected."""
        token = manager_with_users.login("alice", "alice_pass!")
        manager_with_users.logout(token)
        with pytest.raises(AuthenticationError):
            manager_with_users.get_user_from_token(token)

    def test_invalid_token_raises(self, manager_with_users):
        """Random token that was never issued → AuthenticationError."""
        with pytest.raises(AuthenticationError):
            manager_with_users.get_user_from_token("made_up_token_xyz")


# ---------------------------------------------------------------------------
# Task creation
# ---------------------------------------------------------------------------


class TestCreateTask:
    """Tests for create_task."""

    def test_create_task_success(self, manager_with_users):
        """Sample data: alice creates a HIGH priority task."""
        task = manager_with_users.create_task(
            owner="alice",
            title="Write tests",
            description="Cover all modules.",
            priority="HIGH",
        )
        assert task.id == 1
        assert task.title == "Write tests"
        assert task.priority == Priority.HIGH
        assert task.status == Status.PENDING
        assert task.owner == "alice"

    def test_auto_increments_id(self, manager_with_users):
        """Each new task gets a unique incremented ID."""
        t1 = manager_with_users.create_task("alice", "Task 1", "", "LOW")
        t2 = manager_with_users.create_task("alice", "Task 2", "", "LOW")
        assert t2.id == t1.id + 1

    def test_unregistered_owner_raises(self, manager):
        """Owner not in user store → AuthenticationError."""
        with pytest.raises(AuthenticationError):
            manager.create_task("ghost", "Title", "Desc", "LOW")

    def test_empty_title_raises(self, manager_with_users):
        """Empty title → InvalidTaskError."""
        with pytest.raises(InvalidTaskError):
            manager_with_users.create_task("alice", "", "Desc", "LOW")

    def test_invalid_priority_raises(self, manager_with_users):
        """Bad priority string → InvalidTaskError."""
        with pytest.raises(InvalidTaskError):
            manager_with_users.create_task("alice", "Title", "Desc", "ULTRA")

    def test_tags_stored(self, manager_with_users):
        """Tags are stored on the task."""
        task = manager_with_users.create_task(
            "alice", "Tagged task", "", "LOW", tags=["ci", "test"]
        )
        assert task.tags == ["ci", "test"]


# ---------------------------------------------------------------------------
# Task retrieval & listing
# ---------------------------------------------------------------------------


class TestGetAndListTasks:
    """Tests for get_task and list_tasks."""

    def test_get_task_by_id(self, manager_with_tasks):
        """Sample data: task id=1 is retrieved correctly."""
        task = manager_with_tasks.get_task(1)
        assert task.id == 1
        assert task.title == "Write CI pipeline"

    def test_get_nonexistent_task_raises(self, manager_with_tasks):
        """Missing task ID → TaskNotFoundError."""
        with pytest.raises(TaskNotFoundError) as exc_info:
            manager_with_tasks.get_task(999)
        assert exc_info.value.task_id == 999

    def test_list_all_tasks(self, manager_with_tasks):
        """list_tasks() with no filters returns all tasks."""
        tasks = manager_with_tasks.list_tasks()
        assert len(tasks) == 2

    def test_list_tasks_by_owner(self, manager_with_tasks):
        """Filter by owner returns only alice's tasks."""
        tasks = manager_with_tasks.list_tasks(owner="alice")
        assert all(t.owner == "alice" for t in tasks)

    def test_list_tasks_by_status(self, manager_with_tasks):
        """Filter by status=PENDING returns only pending tasks."""
        tasks = manager_with_tasks.list_tasks(status=Status.PENDING)
        assert all(t.status == Status.PENDING for t in tasks)

    def test_list_tasks_by_priority(self, manager_with_tasks):
        """Filter by priority=HIGH returns only high-priority tasks."""
        tasks = manager_with_tasks.list_tasks(priority=Priority.HIGH)
        assert all(t.priority == Priority.HIGH for t in tasks)

    def test_list_tasks_ordered_by_id(self, manager_with_tasks):
        """Tasks are returned in ascending ID order."""
        tasks = manager_with_tasks.list_tasks()
        ids = [t.id for t in tasks]
        assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# Task updates
# ---------------------------------------------------------------------------


class TestUpdateTask:
    """Tests for update_task."""

    def test_owner_can_update_title(self, manager_with_tasks):
        """Task owner can update the title."""
        task = manager_with_tasks.update_task(
            task_id=1, requester="alice", title="Renamed Task"
        )
        assert task.title == "Renamed Task"

    def test_owner_can_update_priority(self, manager_with_tasks):
        """Task owner can change priority."""
        task = manager_with_tasks.update_task(
            task_id=1, requester="alice", priority="CRITICAL"
        )
        assert task.priority == Priority.CRITICAL

    def test_non_owner_cannot_update(self, manager_with_tasks):
        """Non-owner → AuthorizationError."""
        with pytest.raises(AuthorizationError):
            manager_with_tasks.update_task(
                task_id=1, requester="bob", title="Stolen update"
            )

    def test_admin_can_update_any_task(self, manager_with_tasks):
        """Admin can update any task regardless of ownership."""
        task = manager_with_tasks.update_task(
            task_id=1, requester="admin_user", title="Admin revision"
        )
        assert task.title == "Admin revision"

    def test_update_nonexistent_raises(self, manager_with_tasks):
        """Updating a nonexistent task → TaskNotFoundError."""
        with pytest.raises(TaskNotFoundError):
            manager_with_tasks.update_task(
                task_id=999, requester="alice", title="Nope"
            )


# ---------------------------------------------------------------------------
# Task assignment
# ---------------------------------------------------------------------------


class TestAssignTask:
    """Tests for assign_task."""

    def test_owner_assigns_to_bob(self, manager_with_tasks):
        """Sample data: alice assigns task#1 to bob → status=IN_PROGRESS."""
        task = manager_with_tasks.assign_task(
            task_id=1, assignee="bob", requester="alice"
        )
        assert task.assigned_to == "bob"
        assert task.status == Status.IN_PROGRESS

    def test_non_owner_cannot_assign(self, manager_with_tasks):
        """Non-owner (bob) cannot assign alice's task → AuthorizationError."""
        with pytest.raises(AuthorizationError):
            manager_with_tasks.assign_task(
                task_id=1, assignee="bob", requester="bob"
            )

    def test_assign_to_unregistered_user_raises(self, manager_with_tasks):
        """Assigning to an unregistered user → AuthenticationError."""
        with pytest.raises(AuthenticationError):
            manager_with_tasks.assign_task(
                task_id=1, assignee="ghost", requester="alice"
            )

    def test_admin_can_assign_any_task(self, manager_with_tasks):
        """Admin can assign any task."""
        task = manager_with_tasks.assign_task(
            task_id=1, assignee="bob", requester="admin_user"
        )
        assert task.assigned_to == "bob"


# ---------------------------------------------------------------------------
# Task completion and cancellation
# ---------------------------------------------------------------------------


class TestCompleteTask:
    """Tests for complete_task."""

    def test_owner_can_complete(self, manager_with_tasks):
        """Owner marks their own task as DONE."""
        task = manager_with_tasks.complete_task(task_id=1, requester="alice")
        assert task.status == Status.DONE

    def test_complete_already_done_raises(self, manager_with_tasks):
        """Completing an already-DONE task → InvalidTaskError."""
        manager_with_tasks.complete_task(task_id=1, requester="alice")
        with pytest.raises(InvalidTaskError, match="DONE"):
            manager_with_tasks.complete_task(task_id=1, requester="alice")

    def test_complete_cancelled_raises(self, manager_with_tasks):
        """Completing a CANCELLED task → InvalidTaskError."""
        manager_with_tasks.cancel_task(task_id=1, requester="alice")
        with pytest.raises(InvalidTaskError, match="CANCELLED"):
            manager_with_tasks.complete_task(task_id=1, requester="alice")

    def test_non_owner_cannot_complete(self, manager_with_tasks):
        """Non-owner → AuthorizationError."""
        with pytest.raises(AuthorizationError):
            manager_with_tasks.complete_task(task_id=1, requester="bob")


class TestCancelTask:
    """Tests for cancel_task."""

    def test_owner_can_cancel(self, manager_with_tasks):
        """Owner cancels their own task."""
        task = manager_with_tasks.cancel_task(task_id=1, requester="alice")
        assert task.status == Status.CANCELLED

    def test_cancel_done_task_raises(self, manager_with_tasks):
        """Cancelling a DONE task → InvalidTaskError."""
        manager_with_tasks.complete_task(task_id=1, requester="alice")
        with pytest.raises(InvalidTaskError, match="DONE"):
            manager_with_tasks.cancel_task(task_id=1, requester="alice")

    def test_non_owner_cannot_cancel(self, manager_with_tasks):
        """Non-owner → AuthorizationError."""
        with pytest.raises(AuthorizationError):
            manager_with_tasks.cancel_task(task_id=1, requester="bob")


# ---------------------------------------------------------------------------
# Task deletion
# ---------------------------------------------------------------------------


class TestDeleteTask:
    """Tests for delete_task."""

    def test_owner_can_delete(self, manager_with_tasks):
        """Owner deletes their task; it is no longer retrievable."""
        manager_with_tasks.delete_task(task_id=1, requester="alice")
        with pytest.raises(TaskNotFoundError):
            manager_with_tasks.get_task(1)

    def test_non_owner_cannot_delete(self, manager_with_tasks):
        """Non-owner → AuthorizationError."""
        with pytest.raises(AuthorizationError):
            manager_with_tasks.delete_task(task_id=1, requester="bob")

    def test_admin_can_delete_any_task(self, manager_with_tasks):
        """Admin deletes any task."""
        manager_with_tasks.delete_task(task_id=1, requester="admin_user")
        with pytest.raises(TaskNotFoundError):
            manager_with_tasks.get_task(1)

    def test_delete_nonexistent_raises(self, manager_with_tasks):
        """Deleting a nonexistent task → TaskNotFoundError."""
        with pytest.raises(TaskNotFoundError):
            manager_with_tasks.delete_task(task_id=999, requester="alice")


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


class TestGetStatistics:
    """Tests for get_statistics."""

    def test_empty_manager_stats(self, manager_with_users):
        """Empty task store → all counts are 0."""
        stats = manager_with_users.get_statistics()
        assert stats["total"] == 0
        assert all(v == 0 for v in stats["by_status"].values())

    def test_stats_after_creating_tasks(self, manager_with_tasks):
        """Two tasks created → total=2, PENDING=2."""
        stats = manager_with_tasks.get_statistics()
        assert stats["total"] == 2
        assert stats["by_status"]["PENDING"] == 2

    def test_stats_after_completing_task(self, manager_with_tasks):
        """After completing one task, DONE count increments."""
        manager_with_tasks.complete_task(task_id=1, requester="alice")
        stats = manager_with_tasks.get_statistics()
        assert stats["by_status"]["DONE"] == 1
        assert stats["by_status"]["PENDING"] == 1

    def test_stats_by_priority(self, manager_with_tasks):
        """Priority breakdown reflects actual task priorities."""
        stats = manager_with_tasks.get_statistics()
        # task1=HIGH, task2=MEDIUM
        assert stats["by_priority"]["HIGH"] == 1
        assert stats["by_priority"]["MEDIUM"] == 1
