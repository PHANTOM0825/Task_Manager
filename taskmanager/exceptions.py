"""
Custom exceptions for the TaskManager application.

This module defines a hierarchy of application-specific exceptions
that provide clear, descriptive error messages for different failure modes.
These exceptions enable precise error handling in CI tests and production code.

Exception Hierarchy:
    TaskManagerError (base)
    ├── TaskNotFoundError
    ├── InvalidTaskError
    ├── DuplicateTaskError
    ├── AuthenticationError
    └── AuthorizationError
"""


class TaskManagerError(Exception):
    """
    Base exception for all TaskManager errors.

    All custom exceptions in this application inherit from this base
    class so callers can catch all TaskManager-related errors with a
    single ``except TaskManagerError`` clause if needed.
    """

    def __init__(self, message: str, code: int = 0):
        """
        Initialise the base error.

        Args:
            message (str): Human-readable description of the error.
            code (int): Optional machine-readable error code (default 0).
        """
        super().__init__(message)
        self.message = message
        self.code = code

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r}, code={self.code})"


class TaskNotFoundError(TaskManagerError):
    """
    Raised when a requested task does not exist in the store.

    Example:
        >>> raise TaskNotFoundError(task_id=42)
        TaskNotFoundError: Task with ID 42 was not found.
    """

    def __init__(self, task_id: int):
        super().__init__(
            message=f"Task with ID {task_id} was not found.",
            code=404,
        )
        self.task_id = task_id


class InvalidTaskError(TaskManagerError):
    """
    Raised when task data fails validation.

    This is used by the validators module to signal that the
    provided task fields do not meet the application's constraints
    (e.g., empty title, deadline in the past).

    Example:
        >>> raise InvalidTaskError("Title cannot be empty.")
    """

    def __init__(self, reason: str):
        super().__init__(message=f"Invalid task data: {reason}", code=400)
        self.reason = reason


class DuplicateTaskError(TaskManagerError):
    """
    Raised when attempting to create a task that already exists.

    Example:
        >>> raise DuplicateTaskError(task_id=7)
    """

    def __init__(self, task_id: int):
        super().__init__(
            message=f"A task with ID {task_id} already exists.",
            code=409,
        )
        self.task_id = task_id


class AuthenticationError(TaskManagerError):
    """
    Raised when a user's credentials cannot be verified.

    Example:
        >>> raise AuthenticationError("Invalid username or password.")
    """

    def __init__(self, reason: str = "Invalid credentials."):
        super().__init__(message=f"Authentication failed: {reason}", code=401)


class AuthorizationError(TaskManagerError):
    """
    Raised when an authenticated user lacks permission to perform an action.

    Example:
        >>> raise AuthorizationError(user="alice", action="delete", resource="task#5")
    """

    def __init__(self, user: str, action: str, resource: str):
        super().__init__(
            message=(
                f"User '{user}' is not authorised to perform '{action}' on '{resource}'."
            ),
            code=403,
        )
        self.user = user
        self.action = action
        self.resource = resource
