"""
TaskManager Package
===================
A secure, well-tested task management library demonstrating CI/CD best practices.

Modules:
    - models: Data models for tasks and users
    - manager: Core task management logic
    - auth: Authentication and authorization
    - validators: Input validation utilities
    - exceptions: Custom exception classes
    - security: Security utilities (input sanitization, password hashing)
"""

__version__ = "1.0.0"
__author__ = "Week6 CI Task"
__email__ = "student@example.com"

from taskmanager.models import Task, User, Priority, Status
from taskmanager.manager import TaskManager
from taskmanager.exceptions import (
    TaskNotFoundError,
    InvalidTaskError,
    AuthenticationError,
    AuthorizationError,
)

__all__ = [
    "Task",
    "User",
    "Priority",
    "Status",
    "TaskManager",
    "TaskNotFoundError",
    "InvalidTaskError",
    "AuthenticationError",
    "AuthorizationError",
]
