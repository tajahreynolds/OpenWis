# Agent Backlog


Structured tasks for AI agents. Each has acceptance criteria.
Agents pick tasks labeled `agent-task` in GitHub Issues, or from here.


## Format


```


[TASK-001] Short title


· Status: todo | in-progress | done | blocked
· Depends on: [TASK-XXX] or none
· Acceptance criteria: bullet list
· Test requirement: what test proves it works
· Human input needed: yes/no (if yes, what)


```


## Phase 1 Tasks


### [TASK-001] Repo scaffolding
- Status: done
- Depends on: none
- Acceptance criteria:
  - Directory structure: `scripts/`, `tests/`, `docs/`, `data/synthetic/`
  - `requirements.txt` with pinned versions
  - `pyproject.toml` with pytest config
  - `.gitignore` for Python
  - `README.md` links to all docs
- Test: `pytest` runs with zero tests, exits 0
- Human input: no


### [TASK-002] Pol.is sandbox connection
- Status: todo
- Depends on: TASK-001
- Acceptance criteria:
  - `scripts/polis_setup.py` authenticates to a Pol.is instance
  - Creates a conversation with seed statements from `data/synthetic/seeds.json`
  - Opens the conversation for voting
  - Logs conversation ID to stdout
- Test: mock Pol.is API, assert correct POST calls
- Human input: yes — provide Pol.is instance URL and credentials via env vars


### [TASK-003] Pol.is export and transform
- Status: todo
- Depends on: TASK-002
- Acceptance criteria:
  - `scripts/export_and_transform.py` pulls votes, clusters, comments
  - Outputs canonical JSON schema (see ARCHITECTURE.md)
  - Writes to `data/output/{assembly_id}.json`
- Test: fixture CSV from Pol.is → assert JSON matches schema
- Human input: no


### [TASK-004] NarraFirma import format
- Status: todo
- Depends on: TASK-003
- Acceptance criteria:
  - `scripts/storybridge.py` reads Pol.is comments
  - Outputs NarraFirma-compatible CSV
  - Handles empty/malformed comments gracefully
- Test: fixture comments → assert CSV columns match NarraFirma spec
- Human input: no


### [TASK-005] Dashboard template
- Status: todo
- Depends on: TASK-003
- Acceptance criteria:
  - Google Sheets template with tabs: Participation, Consensus, Experience
  - `scripts/dashboard_push.py` writes canonical JSON to Sheet via API
  - Looker Studio template URL documented in `docs/DASHBOARD.md`
- Test: mock Sheets API, assert correct range writes
- Human input: yes — create Google Cloud service account, share Sheet


### [TASK-006] Synthetic assembly end-to-end test
- Status: todo
- Depends on: TASK-003, TASK-004, TASK-005
- Acceptance criteria:
  - `tests/test_e2e.py` runs Pol.is mock → transform → NarraFirma CSV → dashboard push
  - Asserts data integrity at each step
  - Runs in CI on every push
- Test: itself
- Human input: no


### [TASK-007] CI/CD pipeline
- Status: done
- Depends on: TASK-001
- Acceptance criteria:
  - GitHub Actions workflow: lint, test, coverage report
  - Fails on coverage < 80%
  - Caches dependencies
- Test: push triggers workflow, passes
- Human input: no


### [TASK-008] Integration documentation
- Status: todo
- Depends on: TASK-006
- Acceptance criteria:
  - `docs/SETUP.md` — step-by-step for non-technical user
  - `docs/API.md` — every script, every function, every env var
  - `docs/TROUBLESHOOTING.md` — common failures and fixes
- Test: a non-technical tester completes setup in <2 hours
- Human input: yes — recruit tester, observe session


### [TASK-009] Contributor onboarding kit
- Status: todo
- Depends on: TASK-008
- Acceptance criteria:
  - `CONTRIBUTING.md` with scope, conventions, and good first issues
  - `docs/DECISIONS.md` template
  - 5 issues labeled `good-first-issue`
- Test: none
- Human input: yes — review tone and clarity


### [TASK-010] Open-source release
- Status: todo
- Depends on: TASK-009
- Acceptance criteria:
  - LICENSE (Apache-2.0)
  - CODE_OF_CONDUCT.md
  - Public announcement draft (human reviews before posting)
  - Repo made public
- Test: none
- Human input: yes — publish announcement, handle community response