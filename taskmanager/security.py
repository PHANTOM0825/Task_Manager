"""
Security utilities for the TaskManager application.

This module addresses common web-application vulnerabilities and follows
OWASP secure-coding guidelines:

    - Password hashing with PBKDF2-HMAC-SHA256 (no plaintext storage)
    - HTML/script injection prevention via input sanitisation
    - SQL-injection prevention via parameterised-style value escaping
    - Timing-safe string comparison to prevent timing attacks
    - Token generation using a cryptographically secure PRNG

Performance note:
    ``hash_password`` is intentionally slow (100 000 PBKDF2 iterations)
    to resist brute-force attacks.  Cache the result where appropriate
    rather than recomputing it per request.

Third-party library security:
    This module relies only on the Python standard library (``hashlib``,
    ``hmac``, ``secrets``, ``html``).  When integrating third-party
    libraries for cryptography (e.g., ``bcrypt``, ``cryptography``),
    always pin dependency versions and regularly update them to pick up
    security patches.
"""

import hashlib
import hmac
import html
import re
import secrets
import string
from typing import Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Number of PBKDF2 iterations — NIST recommends ≥ 100 000 for SHA-256.
PBKDF2_ITERATIONS: int = 100_000

#: Length of the random salt in bytes (128-bit entropy).
SALT_BYTES: int = 16

#: Length of the derived password hash in bytes.
HASH_BYTES: int = 32

#: Length of generated bearer/session tokens (URL-safe base-64 characters).
TOKEN_LENGTH: int = 32

# Regex for detecting potential SQL-injection patterns in string inputs.
# Uses word boundaries (\b) to avoid matching substrings inside normal words
# (e.g., "Update" contains "pdate" but not the isolated word "UPDATE",
#  and "README" should not match "ALTER" as a standalone token).
_SQL_INJECTION_PATTERN = re.compile(
    r"(\-\-|;|/\*|\*/|xp_|\bUNION\b|\bSELECT\b|\bINSERT\b|\bDELETE\b|"
    r"\bDROP\b|\bALTER\b|\bCREATE\b)",
    re.IGNORECASE,
)

# Characters allowed in usernames.
_USERNAME_ALLOWED = re.compile(r"^[A-Za-z0-9_\-\.]{3,50}$")


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def hash_password(password: str) -> Tuple[str, str]:
    """
    Hash a plaintext password using PBKDF2-HMAC-SHA256.

    A random 128-bit salt is generated for each call so that identical
    passwords produce different hashes (preventing rainbow-table attacks).

    Args:
        password (str): The plaintext password to hash.

    Returns:
        Tuple[str, str]: A ``(hash_hex, salt_hex)`` tuple.  Both values
        must be stored and supplied to :func:`verify_password` later.

    Raises:
        ValueError: If ``password`` is empty or not a string.

    Example::

        hash_hex, salt_hex = hash_password("s3cr3t!")
        assert verify_password("s3cr3t!", hash_hex, salt_hex)

    Performance:
        ~70 ms on a modern laptop per call (intentional — brute-force resistant).
    """
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string.")

    salt: bytes = secrets.token_bytes(SALT_BYTES)
    dk: bytes = hashlib.pbkdf2_hmac(
        hash_name="sha256",
        password=password.encode("utf-8"),
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
        dklen=HASH_BYTES,
    )
    return dk.hex(), salt.hex()


def verify_password(password: str, stored_hash: str, salt_hex: str) -> bool:
    """
    Verify a plaintext password against a stored PBKDF2-HMAC-SHA256 hash.

    Uses :func:`hmac.compare_digest` for constant-time comparison to
    prevent timing-based side-channel attacks.

    Args:
        password (str): The plaintext password to check.
        stored_hash (str): The hex-encoded hash produced by :func:`hash_password`.
        salt_hex (str): The hex-encoded salt produced by :func:`hash_password`.

    Returns:
        bool: ``True`` if the password matches, ``False`` otherwise.

    Example::

        ok = verify_password("s3cr3t!", stored_hash, salt_hex)
    """
    if not isinstance(password, str) or not password:
        return False

    salt: bytes = bytes.fromhex(salt_hex)
    dk: bytes = hashlib.pbkdf2_hmac(
        hash_name="sha256",
        password=password.encode("utf-8"),
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
        dklen=HASH_BYTES,
    )
    return hmac.compare_digest(dk.hex(), stored_hash)


# ---------------------------------------------------------------------------
# Token generation
# ---------------------------------------------------------------------------


def generate_token(length: int = TOKEN_LENGTH) -> str:
    """
    Generate a cryptographically secure URL-safe token.

    Uses :mod:`secrets` (backed by ``os.urandom``) which is suitable for
    session tokens, password-reset links, and API keys.

    Args:
        length (int): Number of URL-safe characters in the token (default 32).

    Returns:
        str: A URL-safe random token string.

    Example::

        token = generate_token()          # 32-char token
        api_key = generate_token(64)      # 64-char token
    """
    alphabet = string.ascii_letters + string.digits + "-_"
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ---------------------------------------------------------------------------
# Input sanitisation
# ---------------------------------------------------------------------------


def sanitise_input(value: str) -> str:
    """
    Sanitise a string value for safe storage and display.

    Steps performed:
    1. Strip leading/trailing whitespace.
    2. Escape HTML special characters (``< > & " '``) to prevent XSS.
    3. Remove common SQL-injection patterns (defence-in-depth; the
       primary defence should always be parameterised queries).

    Args:
        value (str): Raw user-supplied string.

    Returns:
        str: The sanitised string safe for storage.

    Raises:
        TypeError: If ``value`` is not a string.

    Example::

        safe = sanitise_input("<script>alert(1)</script>")
        # Returns: "&lt;script&gt;alert(1)&lt;/script&gt;"
    """
    if not isinstance(value, str):
        raise TypeError(f"Expected str, got {type(value).__name__}.")

    stripped = value.strip()
    # Remove SQL-injection keywords BEFORE HTML-escaping so the regex
    # operates on the raw text and &amp; is never partially consumed.
    cleaned = _SQL_INJECTION_PATTERN.sub("", stripped)
    # Escape HTML special characters to prevent XSS.
    escaped = html.escape(cleaned, quote=True)
    return escaped


def validate_username(username: str) -> bool:
    """
    Validate that a username contains only safe characters.

    Allowed pattern: 3–50 alphanumeric characters, underscores, hyphens,
    or dots.  This prevents username-based injection attacks.

    Args:
        username (str): The username to validate.

    Returns:
        bool: ``True`` if the username is valid, ``False`` otherwise.

    Example::

        validate_username("alice_42")   # True
        validate_username("a b")        # False (contains a space)
    """
    if not isinstance(username, str):
        return False
    return bool(_USERNAME_ALLOWED.match(username))


def is_safe_string(value: str) -> bool:
    """
    Check whether a string is free from known injection patterns.

    This is a lightweight guard used by the validators module before
    accepting user-supplied task titles and descriptions.

    Args:
        value (str): The string to inspect.

    Returns:
        bool: ``True`` if no suspicious patterns are found.
    """
    if not isinstance(value, str):
        return False
    return not bool(_SQL_INJECTION_PATTERN.search(value))
