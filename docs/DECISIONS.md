# Decision Log


Every non-trivial technical decision goes here. Agents append; humans review.


## Template


### [DECISION-XXX] Title
- Date: YYYY-MM-DD
- Status: proposed | accepted | superseded
- Decided by: agent | human | both
- Context: why this came up
- Options considered: list
- Decision: what was chosen
- Consequences: what follows
- Review date: YYYY-MM-DD


## Decisions


### [DECISION-001] Use Google Sheets + Looker Studio for dashboard
- Date: 2026-10-10
- Status: accepted
- Decided by: human
- Context: Need low-cost, low-maintenance dashboard for Phase 1
- Options: Metabase (self-hosted), Grafana, Google Sheets + Looker Studio
- Decision: Google Sheets + Looker Studio
- Consequences: Free, clonable, no infrastructure; limited to ~10k rows;
  requires Google account
- Review date: 2027-01-10


### [DECISION-002] Pin Pol.is to specific version
- Date: 2026-10-10
- Status: accepted
- Decided by: human
- Context: Pol.is API has changed across versions
- Options: latest, pin to v1.2, pin to commit hash
- Decision: Pin to commit hash in `requirements.txt`
- Consequences: Stable builds; manual updates required
- Review date: 2027-01-10

### [DECISION-003] pytest + pytest-cov as test tooling
- Date: 2026-10-10
- Status: proposed
- Decided by: agent
- Context: TASK-001 requires a pytest config; TASK-007 requires a coverage
  gate at 80%. AGENTS.md requires every dependency to be logged.
- Options considered: pytest + pytest-cov; unittest + coverage.py
- Decision: pytest 9.1.1 and pytest-cov 7.1.0, pinned in `requirements.txt`
- Consequences: Coverage can be enforced with `--cov-fail-under=80` in CI
  without extra tooling; version bumps are manual.
- Review date: 2027-01-10


### [DECISION-004] Treat an empty test suite as passing during scaffolding
- Date: 2026-10-10
- Status: superseded (TASK-007 added tests; hook removed)
- Decided by: agent
- Context: TASK-001's test is "`pytest` runs with zero tests, exits 0", but
  pytest exits 5 when no tests are collected.
- Options considered: add a placeholder test (violates "zero tests");
  `pytest_sessionfinish` hook in `tests/conftest.py` mapping exit 5 to 0;
  CI wrapper that tolerates exit 5 (moves the logic outside pytest)
- Decision: conftest hook. Real failures still exit non-zero.
- Consequences: An accidentally empty suite would also pass, so the hook
  must be removed once TASK-002 adds the first tests.
- Review date: when TASK-002 merges


### [DECISION-005] Ruff for linting and formatting
- Date: 2026-10-10
- Status: proposed
- Decided by: agent
- Context: TASK-007 requires a lint step in CI.
- Options considered: Ruff; flake8 + black + isort + pydocstyle
- Decision: Ruff 0.17.0 (one pinned tool, config in `pyproject.toml`).
  Rules: pycodestyle, pyflakes, isort, bugbear, pyupgrade, and pydocstyle
  with Google convention so the AGENTS.md docstring rule is enforced
  (args/returns/raises). Docstring rules are off for `tests/`.
- Consequences: Lint and format run in seconds; CI uses `ruff check` and
  `ruff format --check`. Version bumps are manual.
- Review date: 2027-01-10


### [DECISION-006] CI design (GitHub Actions)
- Date: 2026-10-10
- Status: proposed
- Decided by: agent
- Context: TASK-007 — lint, test, coverage report, fail under 80%, cache deps.
- Options considered: GitHub Actions; Forgejo Actions (not needed while the
  repo is on GitHub)
- Decision:
  - Workflow `.github/workflows/ci.yml` on every push and pull request,
    read-only token, superseded runs cancelled except on `main`.
  - Tests on Python 3.11 (minimum supported) and 3.13 (latest).
  - Coverage threshold lives in `pyproject.toml` (`fail_under = 80`,
    source `scripts/`) so local and CI runs enforce the same gate; a test
    asserts the threshold is not lowered.
  - While `scripts/` has no Python files the gate is skipped with a visible
    notice, because coverage of nothing reports 0%. It applies
    automatically once TASK-002 adds code.
  - Dependency caching via `actions/setup-python` pip cache keyed on
    `requirements.txt`.
  - Coverage table written to the job summary; `coverage.xml` uploaded as
    an artifact.
  - Third-party actions pinned to major tags (`@v5`, `@v6`, `@v4`).
- Consequences: Branches pushed to this repo with an open PR run CI twice
  (push + pull_request). Major-tag pins can move under us; follow-up:
  pin actions to commit SHAs and enable Dependabot for `github-actions`.
- Review date: 2027-01-10
