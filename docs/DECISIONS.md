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
- Status: proposed
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
