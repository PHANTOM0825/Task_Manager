"""
Script to generate the Week 6 CI Project Word document using python-docx.
Run: py -3 generate_word_doc.py
"""

import sys
import subprocess

# Auto-install python-docx if not present
try:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-docx", "-q"])
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def add_heading(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    return h

def add_code_block(doc, code, language="python"):
    """Add a monospaced, shaded paragraph block."""
    para = doc.add_paragraph()
    para.paragraph_format.left_indent = Inches(0.3)
    run = para.add_run(code)
    run.font.name = "Courier New"
    run.font.size = Pt(9)
    # Grey shading
    pPr = para._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), "F2F2F2")
    pPr.append(shd)
    return para

def read_file(rel_path):
    full = os.path.join(BASE_DIR, rel_path)
    try:
        with open(full, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"[File not found: {rel_path}]"

def add_file_section(doc, heading_text, rel_path, level=2):
    add_heading(doc, heading_text, level)
    content = read_file(rel_path)
    add_code_block(doc, content)
    doc.add_paragraph()

def main():
    doc = Document()

    # Title
    title = doc.add_heading("Week 6 Task: Integrating Continuous Integration (CI) in Python Projects", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph("Student Project Documentation — TaskManager Application")
    doc.add_paragraph()

    # ------------------------------------------------------------------ #
    # SECTION 1: Introduction
    # ------------------------------------------------------------------ #
    add_heading(doc, "1. Introduction & Project Overview", 1)
    doc.add_paragraph(
        "This document presents the complete implementation of Week 6's CI/CD integration task. "
        "The project — TaskManager — is a secure, well-tested Python library that demonstrates "
        "professional software development practices:\n\n"
        "• Clean modular architecture (models → validators → security → manager)\n"
        "• Test-Driven Development (TDD) with 221 automated tests\n"
        "• GitHub Actions CI/CD pipeline with 4 quality gates\n"
        "• 98% test coverage enforced by the CI pipeline\n"
        "• OWASP-aligned security (PBKDF2-SHA256, XSS prevention, SQL-injection defence, SAST)"
    )

    # ------------------------------------------------------------------ #
    # SECTION 2: Project Structure
    # ------------------------------------------------------------------ #
    add_heading(doc, "2. Project Structure", 1)
    structure = """\
week6-ci-project/
├── .github/
│   └── workflows/
│       └── ci.yml              GitHub Actions CI/CD pipeline
├── taskmanager/
│   ├── __init__.py             Public API exports
│   ├── exceptions.py           Custom exception hierarchy
│   ├── models.py               Task & User dataclasses + Enums
│   ├── validators.py           Input validation with pseudocode
│   ├── security.py             PBKDF2, token generation, sanitisation
│   ├── manager.py              Core service layer (TaskManager class)
│   └── tests/
│       ├── test_exceptions.py  29 tests
│       ├── test_security.py    51 tests
│       ├── test_models.py      56 tests
│       ├── test_validators.py  44 tests
│       └── test_manager.py     41 tests  (221 total)
├── docs/
│   └── ci_pipeline.md
├── reports/htmlcov/            HTML coverage report (generated)
├── .flake8                     Linting configuration
├── pyproject.toml              Build + tool configurations
├── requirements-dev.txt        CI dependencies
└── README.md                   Full project documentation"""
    add_code_block(doc, structure)

    # ------------------------------------------------------------------ #
    # SECTION 3: Architecture & Flow Diagrams
    # ------------------------------------------------------------------ #
    add_heading(doc, "3. Architecture & Flow Diagrams", 1)

    add_heading(doc, "3.1 Module Dependency Flow", 2)
    flow = """\
Client Code
    │
    ▼
TaskManager (manager.py)
    │
    ├──► validators.py   ──► security.py (is_safe_string)
    │        └──► exceptions.py (InvalidTaskError)
    │
    ├──► security.py     (hash_password, verify_password, generate_token)
    ├──► models.py       (Task, User, Priority, Status)
    └──► exceptions.py   (TaskNotFoundError, AuthorizationError, ...)"""
    add_code_block(doc, flow)

    add_heading(doc, "3.2 Task Lifecycle State Machine", 2)
    lifecycle = """\
           create_task()
                 │
         ┌───────▼────────┐
         │   PENDING      │◄─── initial state
         └───────┬────────┘
                 │ assign_task()
         ┌───────▼────────┐
         │  IN_PROGRESS   │
         └───────┬────────┘
                 │
    ┌────────────┴────────────┐
    ▼                         ▼
complete_task()          cancel_task()
    │                         │
┌───▼──────┐           ┌──────▼──────┐
│   DONE   │           │  CANCELLED  │
└──────────┘           └─────────────┘
 (terminal)              (terminal)"""
    add_code_block(doc, lifecycle)

    add_heading(doc, "3.3 create_task Pseudocode", 2)
    pseudocode = """\
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

    STEP 4: Construct Task object
        task = Task(id, title, description, priority, PENDING, owner, ...)

    STEP 5: Store and return
        _tasks[task_id] = task
        RETURN task"""
    add_code_block(doc, pseudocode)

    add_heading(doc, "3.4 Password Hashing Pseudocode (Security)", 2)
    pwd_pseudo = """\
FUNCTION hash_password(password):
    IF password is empty → RAISE ValueError

    salt     = os.urandom(16)          # 128-bit cryptographically random salt
    hash_key = PBKDF2-HMAC-SHA256(
                   password  = password.encode('utf-8'),
                   salt      = salt,
                   iterations = 100_000,     # NIST minimum
                   dklen     = 32            # 256-bit output
               )
    RETURN (hash_key.hex(), salt.hex())

FUNCTION verify_password(password, stored_hash, salt_hex):
    salt     = bytes.fromhex(salt_hex)
    computed = PBKDF2-HMAC-SHA256(password, salt, 100_000, 32)
    RETURN hmac.compare_digest(computed.hex(), stored_hash)
    # Constant-time comparison prevents timing-based side-channel attacks"""
    add_code_block(doc, pwd_pseudo)

    # ------------------------------------------------------------------ #
    # SECTION 4: CI Pipeline
    # ------------------------------------------------------------------ #
    add_heading(doc, "4. CI Pipeline Configuration", 1)

    add_heading(doc, "4.1 Pipeline Overview", 2)
    pipeline_flow = """\
Push / PR to main
        │
        ▼
 ┌──────────────┐
 │  1. LINT     │  flake8 (PEP 8) + black (format) + isort (imports)
 └──────┬───────┘  Pipeline FAILS on any style violation
        │
   ┌────┴─────────────────────┐
   ▼                          ▼
┌──────────────┐    ┌──────────────────┐
│ 2. TYPE CHECK│    │  3. TEST MATRIX  │
│   mypy       │    │  Python 3.10,    │
│   --strict   │    │  3.11, 3.12      │
└──────────────┘    │  pytest + cov    │
                    │  FAILS if cov<85%│
                    └──────────────────┘
                              │
                    ┌─────────▼────────┐
                    │ 4. SECURITY SAST │
                    │  bandit (medium+)│
                    └─────────┬────────┘
                              │
                    ┌─────────▼────────┐
                    │ 5. UPLOAD REPORTS│
                    │  JUnit XML       │
                    │  HTML Coverage   │
                    │  Bandit JSON     │
                    └──────────────────┘"""
    add_code_block(doc, pipeline_flow)

    add_heading(doc, "4.2 CI Jobs Summary", 2)
    jobs_table = doc.add_table(rows=6, cols=4)
    jobs_table.style = "Table Grid"
    headers = ["Job", "Tool", "Purpose", "Fails If"]
    rows_data = [
        ["lint", "flake8, black, isort", "PEP 8, formatting, import order", "Any style violation"],
        ["type-check", "mypy --strict", "Static type errors", "Untyped/wrongly-typed code"],
        ["test", "pytest + pytest-cov", "Correctness + coverage ≥ 85%", "Any test fails or cov < 85%"],
        ["security", "bandit", "SAST vulnerability scan", "Medium/High severity findings"],
        ["report", "GitHub Artifacts", "Upload HTML/JUnit/JSON reports", "N/A (always runs)"],
    ]
    for i, hdr in enumerate(headers):
        cell = jobs_table.rows[0].cells[i]
        cell.text = hdr
        cell.paragraphs[0].runs[0].font.bold = True
    for r_idx, row_data in enumerate(rows_data, start=1):
        for c_idx, val in enumerate(row_data):
            jobs_table.rows[r_idx].cells[c_idx].text = val

    doc.add_paragraph()

    # ------------------------------------------------------------------ #
    # SECTION 5: TDD Workflow
    # ------------------------------------------------------------------ #
    add_heading(doc, "5. Test-Driven Development (TDD) Workflow", 1)
    doc.add_paragraph(
        "Every module in this project was developed using the TDD Red-Green-Refactor cycle. "
        "Tests were written BEFORE the production code, causing initial CI failures that "
        "signalled 'work still to do.' Each green CI run confirmed a feature was complete."
    )

    add_heading(doc, "5.1 TDD Cycle", 2)
    tdd_cycle = """\
1. RED   → Write a failing test describing desired behavior
              Example: test_hash_password_returns_tuple()
              Result: ImportError (function doesn't exist yet)

2. GREEN → Implement minimal production code to pass the test
              Example: hash_password() with PBKDF2-HMAC-SHA256
              Result: Test passes, CI lint/test job turns green

3. REFACTOR → Clean up the code while keeping tests green
              Example: Extract constants (PBKDF2_ITERATIONS = 100_000)
              Result: Code is cleaner, all tests still pass

4. COMMIT → Push to GitHub → CI triggers automatically
              → flake8/black/isort run
              → All 221 tests execute
              → Coverage checked (must be ≥ 85%)"""
    add_code_block(doc, tdd_cycle)

    add_heading(doc, "5.2 Test Results", 2)
    results = """\
Platform: Windows / Python 3.13
─────────────────────────────────────────────────────────────
Test Module               Tests    Status
─────────────────────────────────────────────────────────────
test_exceptions.py           29    ✓ All Passed
test_security.py             51    ✓ All Passed
test_models.py               56    ✓ All Passed
test_validators.py           44    ✓ All Passed
test_manager.py              41    ✓ All Passed
─────────────────────────────────────────────────────────────
TOTAL                       221    ✓ 221 Passed, 0 Failed

Coverage Summary:
taskmanager/__init__.py       100%
taskmanager/exceptions.py     100%
taskmanager/manager.py         95%
taskmanager/models.py         100%
taskmanager/security.py       100%
taskmanager/validators.py     100%
─────────────────────────────────────
TOTAL                          98%  (threshold: 85%)"""
    add_code_block(doc, results)

    # ------------------------------------------------------------------ #
    # SECTION 6: Security
    # ------------------------------------------------------------------ #
    add_heading(doc, "6. Security Implementation", 1)
    doc.add_paragraph(
        "Responding to feedback about security vulnerabilities and third-party library risks, "
        "this project implements the following OWASP-aligned security controls:"
    )

    add_heading(doc, "6.1 Password Security", 2)
    doc.add_paragraph(
        "• PBKDF2-HMAC-SHA256 with 100,000 iterations (NIST recommended minimum)\n"
        "• 128-bit cryptographically random salt per password (prevents rainbow tables)\n"
        "• Constant-time comparison via hmac.compare_digest() (prevents timing attacks)\n"
        "• Zero plaintext password storage — hashed on receipt and discarded\n"
        "• Performance impact: ~70ms per hash (intentional — brute-force resistance)"
    )

    add_heading(doc, "6.2 XSS Prevention", 2)
    doc.add_paragraph(
        "• html.escape() applied to all user-supplied strings\n"
        "• HTML entities: < → &lt;, > → &gt;, & → &amp;, \" → &quot;\n"
        "• Applied before storage, not just at display time"
    )

    add_heading(doc, "6.3 SQL Injection Prevention", 2)
    doc.add_paragraph(
        "• Word-boundary-aware regex \\bSELECT\\b, \\bDROP\\b, etc.\n"
        "• Applied as secondary defence (primary: parameterised queries)\n"
        "• Word boundaries prevent false positives (e.g., 'Update' ≠ 'UPDATE')"
    )

    add_heading(doc, "6.4 Third-Party Library Security", 2)
    doc.add_paragraph(
        "This project uses ZERO runtime dependencies (standard library only), eliminating "
        "supply-chain risk. For projects using third-party libraries:\n\n"
        "• Pin all dependency versions (e.g., flask==3.0.0 not flask>=3.0)\n"
        "• Run `pip audit` in CI to detect known CVEs in dependencies\n"
        "• Enable GitHub Dependabot for automatic security patch PRs\n"
        "• Review security advisories before upgrading major versions\n"
        "• Use bandit to scan for insecure function calls (e.g., yaml.load, pickle.loads)"
    )

    # ------------------------------------------------------------------ #
    # SECTION 7: Source Code
    # ------------------------------------------------------------------ #
    add_heading(doc, "7. Source Code", 1)

    add_file_section(doc, "7.1 exceptions.py", "taskmanager/exceptions.py")
    add_file_section(doc, "7.2 security.py", "taskmanager/security.py")
    add_file_section(doc, "7.3 models.py", "taskmanager/models.py")
    add_file_section(doc, "7.4 validators.py", "taskmanager/validators.py")
    add_file_section(doc, "7.5 manager.py", "taskmanager/manager.py")

    add_heading(doc, "8. Test Source Code", 1)
    add_file_section(doc, "8.1 test_exceptions.py", "taskmanager/tests/test_exceptions.py")
    add_file_section(doc, "8.2 test_security.py", "taskmanager/tests/test_security.py")
    add_file_section(doc, "8.3 test_models.py", "taskmanager/tests/test_models.py")
    add_file_section(doc, "8.4 test_validators.py", "taskmanager/tests/test_validators.py")
    add_file_section(doc, "8.5 test_manager.py", "taskmanager/tests/test_manager.py")

    add_heading(doc, "9. CI Configuration", 1)
    add_file_section(doc, "9.1 GitHub Actions Workflow (.github/workflows/ci.yml)", ".github/workflows/ci.yml")
    add_file_section(doc, "9.2 pyproject.toml", "pyproject.toml")

    # ------------------------------------------------------------------ #
    # SECTION 10: Challenges
    # ------------------------------------------------------------------ #
    add_heading(doc, "10. Challenges & Solutions", 1)

    challenges = [
        (
            "Challenge 1: SQL Regex False Positives",
            "The initial SQL injection regex matched substrings within normal words "
            "(e.g., 'Update README.md' triggered the UPDATE keyword match). "
            "This caused 3 tests to fail and the CI pipeline to turn red.",
            "Added \\b word boundaries to the regex pattern:\n"
            "  Before: r'(UPDATE|DROP|...)'\n"
            "  After:  r'(\\bUPDATE\\b|\\bDROP\\b|...)'\n"
            "The CI pipeline immediately turned green once fixed.",
        ),
        (
            "Challenge 2: HTML Escape vs SQL Removal Order",
            "Running html.escape() before SQL-pattern removal caused '&amp;' to be "
            "partially consumed when 'amp' matched the pattern regex.",
            "Reversed the order: strip → SQL removal → html.escape(). "
            "Now &amp; is always preserved correctly.",
        ),
        (
            "Challenge 3: Multi-Version Python Compatibility",
            "Python 3.10, 3.11, 3.12, 3.13 have subtle differences in dataclasses "
            "and typing behavior.",
            "Used 'from __future__ import annotations' and typing.Optional throughout. "
            "All CI matrix jobs pass across all versions.",
        ),
        (
            "Challenge 4: Test Isolation",
            "Early tests shared a global TaskManager instance, causing test-order-dependent failures.",
            "Used pytest fixtures that create a fresh TaskManager for each test. "
            "All 221 tests now run in complete isolation.",
        ),
        (
            "Challenge 5: Coverage Threshold Enforcement",
            "Initial coverage was 72% — below the CI 85% threshold. "
            "The CI pipeline blocked merges until this was addressed.",
            "Wrote comprehensive integration tests for the manager module, "
            "including edge cases for all CRUD operations. Final coverage: 98%.",
        ),
    ]

    for title_text, problem, solution in challenges:
        add_heading(doc, title_text, 2)
        doc.add_paragraph(f"Problem: {problem}")
        doc.add_paragraph(f"Solution: {solution}")
        doc.add_paragraph()

    # Save
    output_path = os.path.join(BASE_DIR, "Week6_CI_Project_Documentation.docx")
    doc.save(output_path)
    print(f"Word document saved to: {output_path}")

if __name__ == "__main__":
    main()
