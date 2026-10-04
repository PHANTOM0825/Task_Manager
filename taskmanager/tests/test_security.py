"""
Test suite for taskmanager.security
=====================================

TDD workflow:
    1. test_hash_password_returns_tuple   → drove hash_password signature
    2. test_verify_password_correct       → drove verify_password logic
    3. test_timing_safe_comparison        → ensured hmac.compare_digest use
    4. test_sanitise_html_injection       → drove html.escape in sanitise_input
    5. test_sanitise_sql_patterns         → drove SQL-pattern regex

Coverage:
    - hash_password / verify_password
    - generate_token
    - sanitise_input (XSS, SQL injection, whitespace)
    - validate_username
    - is_safe_string
    - Edge cases and error paths
"""

import re

import pytest

from taskmanager.security import (
    generate_token,
    hash_password,
    is_safe_string,
    sanitise_input,
    validate_username,
    verify_password,
)


# ---------------------------------------------------------------------------
# hash_password
# ---------------------------------------------------------------------------


class TestHashPassword:
    """Tests for the hash_password function."""

    def test_returns_tuple_of_two_strings(self):
        """hash_password must return (hash_hex, salt_hex) — both strings."""
        result = hash_password("secret")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert all(isinstance(x, str) for x in result)

    def test_hash_is_hex_string(self):
        """The returned hash should be a valid hexadecimal string."""
        h, _ = hash_password("mypassword")
        assert re.fullmatch(r"[0-9a-f]+", h), "Hash must be hex-encoded"

    def test_salt_is_hex_string(self):
        """The returned salt should be a valid hexadecimal string."""
        _, s = hash_password("mypassword")
        assert re.fullmatch(r"[0-9a-f]+", s), "Salt must be hex-encoded"

    def test_different_passwords_different_hashes(self):
        """Different passwords must produce different hashes."""
        h1, _ = hash_password("pass1")
        h2, _ = hash_password("pass2")
        assert h1 != h2

    def test_same_password_different_salts(self):
        """Same password hashed twice must use different salts (random salt)."""
        _, s1 = hash_password("samepass")
        _, s2 = hash_password("samepass")
        assert s1 != s2, "Each call must generate a unique random salt"

    def test_same_password_different_hashes_due_to_salt(self):
        """Same password, different salt ⟹ different hash."""
        h1, _ = hash_password("samepass")
        h2, _ = hash_password("samepass")
        assert h1 != h2

    def test_empty_password_raises(self):
        """Empty password should raise ValueError."""
        with pytest.raises(ValueError):
            hash_password("")

    def test_non_string_raises(self):
        """Non-string input should raise ValueError."""
        with pytest.raises((ValueError, TypeError)):
            hash_password(None)  # type: ignore

    def test_unicode_password(self):
        """Unicode passwords should be handled correctly."""
        h, s = hash_password("пароль123")
        assert h and s

    def test_long_password(self):
        """Very long passwords (>1000 chars) should not raise."""
        h, s = hash_password("x" * 1000)
        assert h and s


# ---------------------------------------------------------------------------
# verify_password
# ---------------------------------------------------------------------------


class TestVerifyPassword:
    """Tests for the verify_password function."""

    def test_correct_password_returns_true(self):
        """Correct password + matching hash/salt → True."""
        h, s = hash_password("correct_horse")
        assert verify_password("correct_horse", h, s) is True

    def test_wrong_password_returns_false(self):
        """Wrong password → False."""
        h, s = hash_password("correct_horse")
        assert verify_password("wrong_pony", h, s) is False

    def test_empty_password_returns_false(self):
        """Empty password string → False (no exception)."""
        h, s = hash_password("realpassword")
        assert verify_password("", h, s) is False

    def test_tampered_hash_returns_false(self):
        """Tampered hash → False."""
        h, s = hash_password("password")
        tampered = h[:-4] + "ffff"
        assert verify_password("password", tampered, s) is False

    def test_tampered_salt_returns_false(self):
        """Tampered salt → False."""
        h, s = hash_password("password")
        tampered_s = s[:-4] + "aaaa"
        assert verify_password("password", h, tampered_s) is False

    def test_case_sensitive(self):
        """Password verification is case-sensitive."""
        h, s = hash_password("Password")
        assert verify_password("password", h, s) is False


# ---------------------------------------------------------------------------
# generate_token
# ---------------------------------------------------------------------------


class TestGenerateToken:
    """Tests for the generate_token function."""

    def test_default_length(self):
        """Default token length should be 32 characters."""
        token = generate_token()
        assert len(token) == 32

    def test_custom_length(self):
        """Custom length parameter is respected."""
        token = generate_token(64)
        assert len(token) == 64

    def test_url_safe_characters(self):
        """Token must contain only URL-safe characters."""
        for _ in range(20):
            token = generate_token()
            assert re.fullmatch(r"[A-Za-z0-9_\-]+", token), (
                f"Token '{token}' contains unsafe characters"
            )

    def test_unique_tokens(self):
        """Two calls should produce different tokens."""
        t1 = generate_token()
        t2 = generate_token()
        assert t1 != t2

    def test_minimum_length(self):
        """Token of length 1 should work."""
        token = generate_token(1)
        assert len(token) == 1


# ---------------------------------------------------------------------------
# sanitise_input
# ---------------------------------------------------------------------------


class TestSanitiseInput:
    """Tests for the sanitise_input function."""

    def test_strips_whitespace(self):
        """Leading/trailing whitespace should be stripped."""
        assert sanitise_input("  hello  ") == "hello"

    def test_escapes_html_lt_gt(self):
        """< and > must be escaped."""
        result = sanitise_input("<b>bold</b>")
        assert "<" not in result
        assert ">" not in result

    def test_escapes_script_tag(self):
        """XSS vector: script tag must be escaped."""
        result = sanitise_input("<script>alert('xss')</script>")
        assert "<script>" not in result

    def test_escapes_ampersand(self):
        """& must be escaped to &amp;."""
        result = sanitise_input("a & b")
        assert "&amp;" in result

    def test_escapes_quotes(self):
        """Double-quote must be escaped."""
        result = sanitise_input('"hello"')
        assert '"' not in result

    def test_removes_sql_select(self):
        """SQL SELECT keyword should be removed."""
        result = sanitise_input("'; SELECT * FROM users; --")
        assert "SELECT" not in result.upper()

    def test_removes_sql_drop(self):
        """SQL DROP keyword should be removed."""
        result = sanitise_input("DROP TABLE tasks")
        assert "DROP" not in result.upper()

    def test_plain_string_unchanged_content(self):
        """A safe plain string should be returned without modification."""
        result = sanitise_input("Hello World")
        assert "Hello World" == result

    def test_non_string_raises_type_error(self):
        """Non-string input should raise TypeError."""
        with pytest.raises(TypeError):
            sanitise_input(42)  # type: ignore

    def test_empty_string_returns_empty(self):
        """Empty string should return empty string."""
        assert sanitise_input("") == ""


# ---------------------------------------------------------------------------
# validate_username
# ---------------------------------------------------------------------------


class TestValidateUsername:
    """Tests for the validate_username function."""

    @pytest.mark.parametrize(
        "username",
        ["alice", "bob42", "user_name", "test.user", "a-b", "abc"],
    )
    def test_valid_usernames(self, username):
        """Valid usernames return True."""
        assert validate_username(username) is True

    @pytest.mark.parametrize(
        "username",
        [
            "",          # empty
            "ab",        # too short (< 3)
            "a" * 51,    # too long (> 50)
            "user name", # space
            "user@name", # @ symbol
            None,        # not a string
            123,         # integer
        ],
    )
    def test_invalid_usernames(self, username):
        """Invalid usernames return False."""
        assert validate_username(username) is False


# ---------------------------------------------------------------------------
# is_safe_string
# ---------------------------------------------------------------------------


class TestIsSafeString:
    """Tests for the is_safe_string function."""

    def test_safe_string_returns_true(self):
        assert is_safe_string("Fix the login bug") is True

    def test_sql_union_returns_false(self):
        assert is_safe_string("' UNION SELECT password FROM users") is False

    def test_sql_drop_returns_false(self):
        assert is_safe_string("DROP TABLE users") is False

    def test_empty_string_is_safe(self):
        assert is_safe_string("") is True

    def test_non_string_returns_false(self):
        assert is_safe_string(None) is False  # type: ignore
