"""
Core TaskManager service layer.

This module provides the :class:`TaskManager` class, which acts as the
single entry point for all task and user operations.

Architecture overview::

    ┌─────────────────────────────────────────┐
    │              Client Code                │
    └──────────────┬──────────────────────────┘
                   │ calls
    ┌──────────────▼──────────────────────────┐
    │            TaskManager                  │
    │  ┌──────────┐  ┌──────────┐            │
    │  │  _tasks  │  │  _users  │  (in-mem)  │
    │  └──────────┘  └──────────┘            │
    └──────────────┬──────────────────────────┘
                   │ uses
    ┌──────────────▼──────────────────────────┐
    │  validators  │  security  │  exceptions │
    └─────────────────────────────────────────┘

TDD workflow used during development:
    1. Write failing test (e.g., test_create_task_missing_title).
    2. Implement minimal code to make the test pass.
    3. Refactor while keeping tests green.
    4. Commit → CI pipeline triggers → linting + test suite run.

Pseudocode — create_task::

    FUNCTION create_task(owner, title, description, priority, tags):
        1. CHECK owner is registered
        2. VALIDATE all input fields via validators.validate_task_input()
        3. INCREMENT _next_id counter
        4. CONSTRUCT Task object
        5. STORE in _tasks dict
        6. RETURN task

Pseudocode — assign_task::

    FUNCTION assign_task(task_id, assignee, requester):
        1. FETCH task or RAISE TaskNotFoundError
        2. CHECK requester is owner or admin
        3. CHECK assignee is registered
        4. UPDATE task.assigned_to = assignee
        5. UPDATE task.status = IN_PROGRESS
        6. UPDATE task.updated_at = now()
        7. RETURN task
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from taskmanager.exceptions import (
    AuthenticationError,
    AuthorizationError,
    DuplicateTaskError,
    InvalidTaskError,
    TaskNotFoundError,
)
from taskmanager.models import Priority, Status, Task, User
from taskmanager.security import (
    generate_token,
    hash_password,
    verify_password,
)
from taskmanager.validators import validate_task_input


class TaskManager:
    """
    In-memory task management service.

    Manages users and tasks with authentication, authorisation,
    validation, and status-transition enforcement.

    Attributes:
        _tasks (dict[int, Task]): Internal task store keyed by task ID.
        _users (dict[str, User]): Internal user store keyed by username.
        _sessions (dict[str, str]): Active session tokens → username.
        _next_id (int): Auto-incrementing task ID counter.

    Example::

        manager = TaskManager()
        manager.register_user("alice", "p@ss!", "alice@example.com")
        token = manager.login("alice", "p@ss!")
        task = manager.create_task(
            owner="alice",
            title="Write tests",
            description="Cover all edge cases.",
            priority="HIGH",
        )
    """

    def __init__(self) -> None:
        # In-memory stores
        self._tasks: Dict[int, Task] = {}
        self._users: Dict[str, User] = {}
        self._sessions: Dict[str, str] = {}  # token → username
        self._next_id: int = 1

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------

    def register_user(
        self,
        username: str,
        password: str,
        email: str,
        is_admin: bool = False,
    ) -> User:
        """
        Register a new user.

        Args:
            username (str): Desired username.
            password (str): Plaintext password (will be hashed immediately).
            email (str): User's email address.
            is_admin (bool): Grant administrator privileges (default False).

        Returns:
            User: The newly created :class:`~taskmanager.models.User`.

        Raises:
            InvalidTaskError: If the username or email is invalid.
            DuplicateTaskError: If the username is already registered.

        TDD note:
            Test ``test_register_duplicate_user`` was written before this
            DuplicateTaskError branch was added.
        """
        if username in self._users:
            raise DuplicateTaskError(task_id=0)  # reuse for users (code=409)
        pw_hash, salt = hash_password(password)
        user = User(
            username=username,
            password_hash=pw_hash,
            salt=salt,
            email=email,
            is_admin=is_admin,
        )
        self._users[username] = user
        return user

    def login(self, username: str, password: str) -> str:
        """
        Authenticate a user and return a session token.

        Args:
            username (str): The user's username.
            password (str): The user's plaintext password.

        Returns:
            str: A fresh session token valid until :meth:`logout` is called.

        Raises:
            AuthenticationError: If credentials are incorrect.
        """
        user = self._users.get(username)
        if user is None or not verify_password(password, user.password_hash, user.salt):
            raise AuthenticationError("Invalid username or password.")
        token = generate_token()
        self._sessions[token] = username
        return token

    def logout(self, token: str) -> None:
        """
        Invalidate a session token.

        Args:
            token (str): The session token to revoke.
        """
        self._sessions.pop(token, None)

    def get_user_from_token(self, token: str) -> User:
        """
        Resolve a session token to a :class:`~taskmanager.models.User`.

        Args:
            token (str): Active session token.

        Returns:
            User: The authenticated user.

        Raises:
            AuthenticationError: If the token is invalid or expired.
        """
        username = self._sessions.get(token)
        if username is None:
            raise AuthenticationError("Invalid or expired session token.")
        return self._users[username]

    # ------------------------------------------------------------------
    # Task CRUD
    # ------------------------------------------------------------------

    def create_task(
        self,
        owner: str,
        title: str,
        description: str,
        priority: str | Priority,
        tags: Optional[List[str]] = None,
        due_date: Optional[datetime] = None,
    ) -> Task:
        """
        Create and store a new task.

        Args:
            owner (str): Username of the task creator (must be registered).
            title (str): Task title.
            description (str): Task description.
            priority (str | Priority): Task priority level.
            tags (list[str] | None): Optional keyword tags.
            due_date (datetime | None): Optional due date (must be future UTC).

        Returns:
            Task: The newly created :class:`~taskmanager.models.Task`.

        Raises:
            AuthenticationError: If ``owner`` is not a registered user.
            InvalidTaskError: If any field fails validation.

        Pseudocode::

            1. Verify owner exists
            2. Validate input via validate_task_input()
            3. Assign next available ID
            4. Construct Task
            5. Store and return

        Sample data tests::

            task = manager.create_task("alice","Fix login","Auth bug","HIGH")
            assert task.id == 1
            assert task.status == Status.PENDING
        """
        if owner not in self._users:
            raise AuthenticationError(f"User '{owner}' is not registered.")

        cleaned = validate_task_input(
            title=title,
            description=description,
            priority=priority,
            tags=tags,
            due_date=due_date,
        )

        task = Task(
            id=self._next_id,
            title=cleaned["title"],
            description=cleaned["description"],
            priority=cleaned["priority"],
            status=Status.PENDING,
            owner=owner,
            tags=cleaned["tags"],
        )
        self._tasks[self._next_id] = task
        self._next_id += 1
        return task

    def get_task(self, task_id: int) -> Task:
        """
        Retrieve a task by its ID.

        Args:
            task_id (int): The task identifier.

        Returns:
            Task: The requested task.

        Raises:
            TaskNotFoundError: If no task with ``task_id`` exists.
        """
        if task_id not in self._tasks:
            raise TaskNotFoundError(task_id)
        return self._tasks[task_id]

    def list_tasks(
        self,
        owner: Optional[str] = None,
        status: Optional[Status] = None,
        priority: Optional[Priority] = None,
    ) -> List[Task]:
        """
        List tasks with optional filters.

        Args:
            owner (str | None): Filter by owner username.
            status (Status | None): Filter by task status.
            priority (Priority | None): Filter by priority level.

        Returns:
            list[Task]: Matching tasks in creation-ID order.

        Sample data tests::

            tasks = manager.list_tasks(status=Status.PENDING)
            # Returns only tasks whose status is PENDING
        """
        results = list(self._tasks.values())
        if owner:
            results = [t for t in results if t.owner == owner]
        if status:
            results = [t for t in results if t.status == status]
        if priority:
            results = [t for t in results if t.priority == priority]
        return sorted(results, key=lambda t: t.id)

    def update_task(
        self,
        task_id: int,
        requester: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[str | Priority] = None,
        tags: Optional[List[str]] = None,
    ) -> Task:
        """
        Update a task's mutable fields.

        Only the task owner or an admin may update a task.

        Args:
            task_id (int): ID of the task to update.
            requester (str): Username of the user making the request.
            title (str | None): New title (if provided).
            description (str | None): New description (if provided).
            priority (str | Priority | None): New priority (if provided).
            tags (list[str] | None): New tags (if provided).

        Returns:
            Task: The updated task.

        Raises:
            TaskNotFoundError: If the task does not exist.
            AuthorizationError: If ``requester`` is not the owner or admin.
            InvalidTaskError: If updated fields fail validation.
        """
        task = self.get_task(task_id)
        self._check_authorised(requester, task, action="update")

        if title is not None:
            from taskmanager.validators import validate_title

            task.title = validate_title(title)
        if description is not None:
            from taskmanager.validators import validate_description

            task.description = validate_description(description)
        if priority is not None:
            from taskmanager.validators import validate_priority

            task.priority = validate_priority(priority)
        if tags is not None:
            from taskmanager.validators import validate_tags

            task.tags = validate_tags(tags)

        task.updated_at = datetime.now(timezone.utc)
        return task

    def assign_task(self, task_id: int, assignee: str, requester: str) -> Task:
        """
        Assign a task to a user and move it to IN_PROGRESS.

        Args:
            task_id (int): ID of the task to assign.
            assignee (str): Username of the user to assign the task to.
            requester (str): Username of the user making the request.

        Returns:
            Task: The updated task with IN_PROGRESS status.

        Raises:
            TaskNotFoundError: If the task does not exist.
            AuthorizationError: If requester is not the owner or admin.
            AuthenticationError: If assignee is not a registered user.

        Pseudocode::

            1. Fetch task (or raise TaskNotFoundError)
            2. Verify requester is owner or admin
            3. Verify assignee is registered
            4. task.assigned_to = assignee
            5. task.status = IN_PROGRESS
            6. task.updated_at = now()
            7. Return task
        """
        task = self.get_task(task_id)
        self._check_authorised(requester, task, action="assign")
        if assignee not in self._users:
            raise AuthenticationError(f"Assignee '{assignee}' is not registered.")
        task.assigned_to = assignee
        task.status = Status.IN_PROGRESS
        task.updated_at = datetime.now(timezone.utc)
        return task

    def complete_task(self, task_id: int, requester: str) -> Task:
        """
        Mark a task as DONE.

        Args:
            task_id (int): ID of the task to complete.
            requester (str): Username of the user marking it done.

        Returns:
            Task: The updated task with DONE status.

        Raises:
            TaskNotFoundError: If the task does not exist.
            AuthorizationError: If requester is not authorised.
            InvalidTaskError: If the task is already DONE or CANCELLED.
        """
        task = self.get_task(task_id)
        self._check_authorised(requester, task, action="complete")
        if task.status in (Status.DONE, Status.CANCELLED):
            raise InvalidTaskError(f"Cannot complete a task with status '{task.status.value}'.")
        task.status = Status.DONE
        task.updated_at = datetime.now(timezone.utc)
        return task

    def cancel_task(self, task_id: int, requester: str) -> Task:
        """
        Cancel a task.

        Args:
            task_id (int): ID of the task to cancel.
            requester (str): Username of the requesting user.

        Returns:
            Task: The updated task with CANCELLED status.

        Raises:
            TaskNotFoundError: If the task does not exist.
            AuthorizationError: If requester is not authorised.
            InvalidTaskError: If the task is already DONE or CANCELLED.
        """
        task = self.get_task(task_id)
        self._check_authorised(requester, task, action="cancel")
        if task.status in (Status.DONE, Status.CANCELLED):
            raise InvalidTaskError(f"Cannot cancel a task with status '{task.status.value}'.")
        task.status = Status.CANCELLED
        task.updated_at = datetime.now(timezone.utc)
        return task

    def delete_task(self, task_id: int, requester: str) -> None:
        """
        Delete a task permanently.

        Only the task owner or an admin may delete a task.

        Args:
            task_id (int): ID of the task to delete.
            requester (str): Username of the requesting user.

        Raises:
            TaskNotFoundError: If the task does not exist.
            AuthorizationError: If requester is not authorised.
        """
        task = self.get_task(task_id)
        self._check_authorised(requester, task, action="delete")
        del self._tasks[task_id]

    # ------------------------------------------------------------------
    # Statistics / reporting
    # ------------------------------------------------------------------

    def get_statistics(self) -> dict[str, Any]:
        """
        Return aggregate statistics about the task store.

        Returns:
            dict: Counts by status and priority, plus total task count.

        Example::

            stats = manager.get_statistics()
            # {
            #   "total": 10,
            #   "by_status": {"PENDING": 3, "IN_PROGRESS": 4, ...},
            #   "by_priority": {"HIGH": 5, ...},
            # }
        """
        by_status = {s.value: 0 for s in Status}
        by_priority = {p.value: 0 for p in Priority}
        for task in self._tasks.values():
            by_status[task.status.value] += 1
            by_priority[task.priority.value] += 1
        return {
            "total": len(self._tasks),
            "by_status": by_status,
            "by_priority": by_priority,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_authorised(self, requester: str, task: Task, action: str) -> None:
        """
        Raise AuthorizationError if requester may not perform action on task.

        Admins may perform any action.  Non-admins may only act on their
        own tasks.

        Args:
            requester (str): Username of the requesting user.
            task (Task): The task being acted upon.
            action (str): Description of the action (for error messages).

        Raises:
            AuthenticationError: If requester is not registered.
            AuthorizationError: If requester lacks permission.
        """
        user = self._users.get(requester)
        if user is None:
            raise AuthenticationError(f"User '{requester}' is not registered.")
        if not user.is_admin and task.owner != requester:
            raise AuthorizationError(
                user=requester,
                action=action,
                resource=f"task#{task.id}",
            )
