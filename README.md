# TaskManager — CI/CD Integration Project

> **Week 6 Task:** Integrating Continuous Integration (CI) in Python Projects

[![CI Pipeline](https://github.com/your-org/taskmanager/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/taskmanager/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-98%25-brightgreen)](reports/htmlcov/index.html)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Project Structure](#2-project-structure)
3. [Architecture & Flow Diagrams](#3-architecture--flow-diagrams)
4. [CI Pipeline Configuration](#4-ci-pipeline-configuration)
5. [TDD Workflow](#5-tdd-workflow)
6. [Security Practices](#6-security-practices)
7. [Running Tests Locally](#7-running-tests-locally)
8. [Viewing CI Logs & Reports](#8-viewing-ci-logs--reports)
9. [Environment Replication](#9-environment-replication)
10. [Challenges & Solutions](#10-challenges--solutions)

---

## 1. Project Overview

**TaskManager** is a secure, in-memory task management library built entirely with the Python standard library (no runtime dependencies). It demonstrates:

- Clean, modular Python architecture (models → validators → security → manager)
- Test-Driven Development (TDD) — tests were written **before** production code
- Full CI/CD integration via **GitHub Actions**
- 98% test coverage across 221 automated tests
- OWASP-aligned security practices (PBKDF2-SHA256, XSS prevention, SQL-injection defence)

---

## 2. Project Structure

```
week6-ci-project/
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions CI/CD pipeline
├── taskmanager/                # Main package
│   ├── __init__.py             # Public API exports
│   ├── exceptions.py           # Custom exception hierarchy
│   ├── models.py               # Task & User dataclasses + Enums
│   ├── validators.py           # Input validation utilities
│   ├── security.py             # PBKDF2, token generation, sanitisation
│   ├── manager.py              # Core service layer (TaskManager class)
│   └── tests/
│       ├── __init__.py
│       ├── test_exceptions.py  # 29 tests — exception classes
│       ├── test_security.py    # 51 tests — security utilities
│       ├── test_models.py      # 56 tests — Task & User models
│       ├── test_validators.py  # 44 tests — input validators
│       └── test_manager.py     # 41 tests — service integration
├── docs/
│   └── ci_pipeline.md          # Detailed pipeline documentation
├── reports/
│   └── htmlcov/                # HTML coverage report (generated)
├── .flake8                     # flake8 linting configuration
├── pyproject.toml              # Build system + tool configurations
├── requirements-dev.txt        # Dev/CI dependencies
└── README.md                   # This file
```

---

## 3. Architecture & Flow Diagrams

### 3.1 Module Dependency Flow

```
Client Code
    │
    ▼
TaskManager (manager.py)
    │
    ├──► validators.py   ──► security.py (is_safe_string)
    │        │
    │        └──► exceptions.py (InvalidTaskError)
    │
    ├──► security.py     (hash_password, verify_password, generate_token)
    │
    ├──► models.py       (Task, User, Priority, Status)
    │        └──► exceptions.py
    │        └──► security.py   (validate_username, sanitise_input)
    │
    └──► exceptions.py   (TaskNotFoundError, AuthorizationError, ...)
```

### 3.2 Task Lifecycle State Machine

```
              register_user()
                    │
            ┌───────▼───────┐
            │  User Account │
            └───────┬───────┘
                    │ login() → token
                    │
              create_task()
                    │
            ┌───────▼────────┐
            │   PENDING      │◄─── initial state
            └───────┬────────┘
                    │
          assign_task(assignee)
                    │
            ┌───────▼────────┐
            │  IN_PROGRESS   │
            └───────┬────────┘
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
    complete_task()       cancel_task()
         │                     │
  ┌──────▼──────┐       ┌──────▼──────┐
  │    DONE     │       │  CANCELLED  │
  └─────────────┘       └─────────────┘
    (terminal)              (terminal)
```

### 3.3 create_task Pseudocode

```
FUNCTION create_task(owner, title, description, priority, tags, due_date):

    STEP 1: Verify owner
        IF owner NOT IN _users:
            RAISE AuthenticationError("User not registered")

    STEP 2: Validate all inputs
        cleaned = validate_task_input(
            title, description, priority, tags, due_date
        )
        → validate_title()     : non-empty, ≤200 chars, no SQL/XSS
        → validate_description(): ≤2000 chars, no SQL
        → validate_priority()  : must be LOW/MEDIUM/HIGH/CRITICAL
        → validate_tags()      : ≤10 tags, each ≤50 chars
        → validate_due_date()  : must be future UTC datetime or None

    STEP 3: Assign ID
        task_id = _next_id
        _next_id += 1

    STEP 4: Construct Task
        task = Task(
            id=task_id,
            title=cleaned.title,
            description=cleaned.description,
            priority=cleaned.priority,
            status=PENDING,
            owner=owner,
            tags=cleaned.tags,
            created_at=now(UTC),
            updated_at=now(UTC),
        )

    STEP 5: Store and return
        _tasks[task_id] = task
        RETURN task
```

### 3.4 Security — Password Hashing Pseudocode

```
FUNCTION hash_password(password):
    IF password is empty:
        RAISE ValueError

    salt = os.urandom(16)               # 128-bit random salt
    hash = PBKDF2-HMAC-SHA256(
        password = password.encode('utf-8'),
        salt     = salt,
        iterations = 100_000,           # NIST minimum for SHA-256
        dklen    = 32                   # 256-bit output
    )
    RETURN (hash.hex(), salt.hex())

FUNCTION verify_password(password, stored_hash, salt_hex):
    salt = bytes.fromhex(salt_hex)
    computed = PBKDF2-HMAC-SHA256(password, salt, 100_000, 32)
    RETURN hmac.compare_digest(computed.hex(), stored_hash)
    # ↑ constant-time comparison prevents timing attacks
```

---

## 4. CI Pipeline Configuration

The pipeline is defined in [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

### 4.1 Pipeline Overview

```
Push / PR to main
        │
        ▼
 ┌──────────────┐
 │  1. LINT     │  flake8 + black + isort
 └──────┬───────┘
        │
   ┌────┴─────────────────────┐
   ▼                          ▼
┌──────────────┐    ┌──────────────────┐
│ 2. TYPE CHECK│    │  3. TEST MATRIX  │
│   (mypy)     │    │  Python 3.10,    │
└──────────────┘    │  3.11, 3.12      │
                    │  pytest + cov    │
                    │  cov ≥ 85%       │
                    └──────────────────┘
                              │
                    ┌─────────▼────────┐
                    │ 4. SECURITY SAST │
                    │  (bandit)        │
                    └─────────┬────────┘
                              │
                    ┌─────────▼────────┐
                    │ 5. UPLOAD REPORTS│
                    │  (artifacts)     │
                    └──────────────────┘
```

### 4.2 Job Descriptions

| Job | Tool | Purpose | Fails If |
|-----|------|---------|---------|
| **lint** | flake8, black, isort | PEP 8, formatting, import order | Any style violation |
| **type-check** | mypy (strict) | Static type errors | Untyped or wrongly-typed code |
| **test** | pytest + pytest-cov | Functional correctness + coverage | Any test fails OR coverage < 85% |
| **security** | bandit | SAST — finds known security anti-patterns | Medium/High severity findings |

### 4.3 Key CI Settings

```yaml
# Fail if coverage drops below 85%
--cov-fail-under=85

# Test against multiple Python versions
matrix:
  python-version: ["3.10", "3.11", "3.12"]

# Upload reports even when tests fail (for debugging)
if: always()
```

---

## 5. TDD Workflow

This project followed strict **Test-Driven Development** throughout:

### TDD Cycle per Feature

```
  ┌─────────────────────────────────────────────┐
  │                                             │
  │   1. RED   Write a failing test that        │
  │            describes the desired behavior.  │
  │                    ↓                        │
  │   2. GREEN Implement minimal code to        │
  │            make the test pass.              │
  │                    ↓                        │
  │   3. REFACTOR Clean up code while          │
  │            keeping all tests green.         │
  │                    ↓                        │
  │   4. COMMIT → CI pipeline triggers          │
  │            → linting + full test suite      │
  │                    ↓                        │
  │            (loop back to step 1)            │
  └─────────────────────────────────────────────┘
```

### TDD Example: `hash_password`

```
Step 1 (RED):
  def test_returns_tuple_of_two_strings():
      result = hash_password("secret")   # ImportError — function doesn't exist
      assert isinstance(result, tuple)

Step 2 (GREEN):
  def hash_password(password):
      # minimal implementation
      return ("fake_hash", "fake_salt")

Step 3 (REFACTOR):
  def hash_password(password):
      # full PBKDF2-HMAC-SHA256 implementation
      salt = secrets.token_bytes(16)
      dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000, 32)
      return dk.hex(), salt.hex()
```

### Test Coverage Progression

| Stage | Tests Written | Tests Passing | Coverage |
|-------|-------------|---------------|---------|
| exceptions.py done | 29 | 29 | 100% |
| security.py done | 80 | 80 | 100% |
| models.py done | 136 | 136 | 100% |
| validators.py done | 180 | 180 | 100% |
| manager.py done | 221 | 221 | 98% |

---

## 6. Security Practices

### 6.1 Password Security

| Practice | Implementation |
|---------|---------------|
| No plaintext storage | Passwords hashed immediately via `hash_password()` |
| PBKDF2-HMAC-SHA256 | 100,000 iterations — brute-force resistant |
| Random salt (128-bit) | New salt per hash — defeats rainbow tables |
| Constant-time compare | `hmac.compare_digest()` — prevents timing attacks |

### 6.2 Input Sanitisation

```
User Input
    │
    ▼
sanitise_input()
    ├── 1. strip() — remove whitespace
    ├── 2. SQL pattern removal (\bDROP\b, \bSELECT\b, etc.)
    └── 3. html.escape() — prevent XSS
```

### 6.3 Third-Party Library Security

> **Note on external dependencies:**
> This project uses **zero runtime dependencies** (standard library only).
> For projects that do use third-party libraries, follow these practices:
> - Pin all dependency versions in `requirements.txt` (e.g., `flask==3.0.0`)
> - Use `pip audit` or `safety check` in CI to detect known CVEs
> - Enable Dependabot on GitHub for automatic version-bump PRs
> - Review security advisories for libraries like `cryptography`, `requests`, `django`

### 6.4 SAST with Bandit

Bandit scans the source for common Python security anti-patterns:

```bash
# Run bandit locally
py -3 -m bandit -r taskmanager/ -ll -ii
```

---

## 7. Running Tests Locally

### Prerequisites

```bash
# Clone the repository
git clone https://github.com/your-org/taskmanager.git
cd taskmanager

# Create a virtual environment (recommended)
py -3 -m venv .venv
.venv\Scripts\activate     # Windows
# source .venv/bin/activate  # macOS/Linux

# Install dev dependencies
py -3 -m pip install -r requirements-dev.txt
```

### Run the Full Test Suite

```bash
# Run all tests with verbose output
py -3 -m pytest taskmanager/tests/ -v

# Run with coverage report
py -3 -m pytest taskmanager/tests/ --cov=taskmanager --cov-report=term-missing

# Run a specific test module
py -3 -m pytest taskmanager/tests/test_security.py -v

# Run a specific test class
py -3 -m pytest taskmanager/tests/test_manager.py::TestCreateTask -v

# Run a specific test
py -3 -m pytest taskmanager/tests/test_manager.py::TestCreateTask::test_create_task_success -v

# Run tests matching a keyword
py -3 -m pytest -k "login" -v
```

### Run Linting Locally

```bash
# PEP 8 check
py -3 -m flake8 taskmanager/

# Formatting check
py -3 -m black --check taskmanager/

# Auto-format (applies changes)
py -3 -m black taskmanager/

# Import order check
py -3 -m isort --check-only taskmanager/
```

### Run Security Scan Locally

```bash
py -3 -m bandit -r taskmanager/ -ll -ii
```

### Generate HTML Coverage Report

```bash
py -3 -m pytest taskmanager/tests/ \
    --cov=taskmanager \
    --cov-report=html:reports/htmlcov

# Open the report
start reports\htmlcov\index.html   # Windows
```

---

## 8. Viewing CI Logs & Reports

### GitHub Actions Logs

1. Navigate to your repository on GitHub.
2. Click the **Actions** tab.
3. Select the **CI Pipeline – TaskManager** workflow.
4. Click on a specific workflow run.
5. Expand any job (lint, test, security) to see step-by-step output.

### Downloading Artifacts

After a workflow run completes:

1. Go to **Actions** → select the run.
2. Scroll to the **Artifacts** section at the bottom.
3. Download:
   - `junit-report-py3.11` — XML test results
   - `coverage-html-py3.11` — HTML coverage report (open `index.html`)
   - `bandit-security-report` — JSON security scan results

### Simulating CI Locally with `act`

```bash
# Install act: https://github.com/nektos/act

# Run the lint job locally
act -j lint

# Run the test job locally
act -j test

# Simulate a push event
act push
```

---

## 9. Environment Replication

### Step-by-Step Setup

```bash
# 1. Ensure Python 3.10+ is installed
py -3 --version

# 2. Clone/extract the project
cd week6-ci-project

# 3. (Optional) Create virtual environment
py -3 -m venv .venv
.venv\Scripts\activate

# 4. Install dev dependencies
py -3 -m pip install -r requirements-dev.txt

# 5. Verify installation
py -3 -m pytest --version
py -3 -m flake8 --version

# 6. Run the full CI pipeline simulation
py -3 -m flake8 taskmanager/ && \
py -3 -m black --check taskmanager/ && \
py -3 -m isort --check-only taskmanager/ && \
py -3 -m pytest taskmanager/tests/ \
    --cov=taskmanager \
    --cov-fail-under=85 \
    --cov-report=term-missing \
    --junitxml=reports/junit.xml
```

### CI Trigger

Once pushed to GitHub:
- **Every push to `main` or `develop`** → full pipeline runs automatically
- **Every pull request to `main`** → full pipeline runs as a gate check
- The PR cannot be merged if any pipeline job fails

---

## 10. Challenges & Solutions

### Challenge 1: False Positives in SQL Injection Regex

**Problem:** The initial SQL injection pattern `(DROP|ALTER|...)` used no word boundaries, causing words like `"Update"` to be incorrectly flagged as containing `UPDATE`.

**Solution:** Added `\b` word boundaries to the regex:
```python
# Before (caused false positives)
r"(UPDATE|DELETE|DROP|...)"

# After (word-boundary aware)
r"(\bUNION\b|\bSELECT\b|\bDELETE\b|\bDROP\b|\bALTER\b|\bCREATE\b)"
```
**CI Impact:** CI lint/test jobs turned red; the word-boundary fix restored green status.

### Challenge 2: HTML Escape Order vs SQL Removal

**Problem:** Running `html.escape()` before SQL-pattern removal caused `&amp;` (the escaped `&`) to be partially consumed when the pattern `amp` matched the regex.

**Solution:** Reversed the order — remove SQL patterns first, then HTML-escape:
```python
# Correct order
cleaned = _SQL_INJECTION_PATTERN.sub("", stripped)  # SQL first
escaped = html.escape(cleaned, quote=True)           # HTML second
```

### Challenge 3: Multi-Version Python Matrix

**Problem:** Python 3.10, 3.11, 3.12 have subtle differences in `dataclasses` and `typing` behaviour.

**Solution:** Used `from __future__ import annotations` consistently and `typing.Optional` for compatibility. All matrix jobs now pass.

### Challenge 4: Test Isolation

**Problem:** Early tests shared a global `TaskManager` instance, causing order-dependent failures.

**Solution:** Used pytest `fixtures` that create a **fresh `TaskManager`** for each test:
```python
@pytest.fixture
def manager():
    return TaskManager()   # new instance per test
```

### Challenge 5: Coverage Threshold

**Problem:** Initial coverage was 72% before the manager integration tests were written.

**Solution:** The CI `--cov-fail-under=85` gate forced writing more comprehensive tests. Final coverage reached **98%**.

---

## Test Results Summary

```
Platform: Windows / Python 3.13
Test session started: 2026-10-04

taskmanager/tests/test_exceptions.py  .............................  29 passed
taskmanager/tests/test_manager.py     ...................41 passed   41 passed
taskmanager/tests/test_models.py      .............................  56 passed
taskmanager/tests/test_security.py    .............................  51 passed
taskmanager/tests/test_validators.py  .............................  44 passed

================================ 221 passed in 4.95s =========================

Coverage Summary:
taskmanager/__init__.py         100%
taskmanager/exceptions.py       100%
taskmanager/manager.py           95%
taskmanager/models.py           100%
taskmanager/security.py         100%
taskmanager/validators.py       100%
─────────────────────────────────────
TOTAL                            98%
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.
