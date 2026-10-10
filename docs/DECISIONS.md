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


### [DECISION-007] Normalize text files to LF, UTF-8 without BOM
- Date: 2026-10-10
- Status: proposed
- Decided by: both (human requested; agent implemented)
- Context: The seed docs were CRLF with a UTF-8 BOM; everything else is LF.
  Agent edits flipped line endings and produced whole-file diffs (PR #1, #2).
- Options considered: keep per-file endings; `* text=auto` (native endings
  on checkout); `* text=auto eol=lf` (LF everywhere)
- Decision: `.gitattributes` with `* text=auto eol=lf`, `.editorconfig` with
  `end_of_line = lf` and `charset = utf-8`, existing files converted once,
  BOMs removed. `tests/test_repo_hygiene.py` fails on CRLF or a BOM in any
  tracked text file.
- Consequences: Shell scripts and YAML behave the same on every OS; future
  diffs show only content changes. Windows editors must honor
  `.editorconfig` or Git converts on commit. The one-time conversion
  touches every line of the seed docs.
- Review date: 2027-01-10


### [DECISION-008] Pol.is integration: direct HTTP API, OIDC token, pinned server
- Date: 2026-10-10
- Status: proposed
- Decided by: both (human chose direct API and an in-container sandbox;
  agent chose the details)
- Context: TASK-002. ARCHITECTURE.md named `colab-coop/polis-cli`, which
  could not be found. The closest package, deliberAIde `polis-cli` 0.1.1
  (Sep 2026), lists its Phase 1 commands as unfinished. Pol.is has no
  official API docs, and its seed-statement behaviour changed several times
  in 2025-2026.
- Options considered: deliberAIde `polis-cli`; direct calls to `/api/v3`
- Decision:
  - Call `/api/v3` directly from `scripts/polis_setup.py`.
  - Pin the server to `compdemocracy/polis@1db2f7919f33b740b34bb84ed9a1fb5bfb1914d2`
    and verify endpoints against its source and a live sandbox
    (`docs/POLIS_SANDBOX.md`). Pol.is is not a Python package, so the pin is
    recorded as a comment in `requirements.txt` rather than a requirement
    (refines DECISION-002).
  - Authenticate with the owner's OIDC access token (`POLIS_TOKEN`). The
    pinned server has no email/password login route, so none is supported.
  - Create the conversation with `is_active: true`; Pol.is rejects seed
    statements on a closed conversation, so "create closed, seed, then open"
    is impossible.
  - Validate seeds against server limits before the first request; never
    retry POSTs.
- Consequences: No third-party client to track. Moving the pin means
  re-running the sandbox verification. A token from the dev simulator is
  long-lived; a production token must come from the instance's provider.
- Review date: 2027-01-10


### [DECISION-009] requests + responses for HTTP and its tests
- Date: 2026-10-10
- Status: proposed
- Decided by: agent
- Context: `scripts/polis_setup.py` needs an HTTP client; the TASK-002 test
  must assert the exact POST calls against a mocked Pol.is.
- Options considered: requests + responses; httpx + respx; stdlib urllib +
  unittest.mock
- Decision: `requests` 2.34.2 and `responses` 0.26.3. Both are long
  established; `responses` matches on JSON body and headers, so tests assert
  payloads and the bearer header directly.
- Consequences: Synchronous client only, which is enough for setup scripts.
  Later scripts (TASK-003, TASK-005) should reuse the same pair.
- Review date: 2027-01-10


### [DECISION-010] Canonical metric definitions from the Pol.is export
- Date: 2026-10-10
- Status: proposed (needs human review: `consensus` will be shown on the
  dashboard)
- Decided by: agent
- Context: TASK-003. ARCHITECTURE.md listed the canonical fields but not how
  to compute them, and Pol.is has no per-group "consensus" value. The pinned
  export also has quirks: `votes.csv` lists vote events (a changed vote
  appears twice), `participant-votes.csv` can show a changed vote's old
  value, and `comments.csv` counts both.
- Options considered for `consensus`: mean within-group agree rate;
  share of votes with the group majority (range 0.5-1); vote-weighted
  |agrees - disagrees| / (agrees + disagrees) (range 0-1); Pol.is's
  group-aware consensus (a per-statement, cross-group value that does not
  fit a per-group field)
- Decision:
  - `statements`: comments not rejected by moderation (`moderated` != -1).
  - `votes`: distinct (voter, statement) pairs in `votes.csv` on those
    statements, passes included.
  - `participants`: distinct voters among those votes.
  - `clusters`: Pol.is groups from `participant-votes.csv` (`group-id`),
    matched to `comment-groups.csv` columns by letter (`group-a` is 0).
  - `consensus`: per group, sum over counted statements of
    |agrees - disagrees| divided by sum of (agrees + disagrees); 1 means
    the group voted unanimously on every statement, 0 means evenly split.
    Passes are excluded. Rounded to 4 places; `null` when the group cast no
    agree or disagree votes.
  - `stories_collected` 0 and `decisions` `[]` until those integrations
    exist.
  - The output holds counts only: no participant IDs or statement text.
- Consequences: Values are reproducible from the export alone. `consensus`
  measures how united a group is, not agreement between groups; a
  cross-group measure would need a new schema field. Group sizes can sum to
  fewer than `participants` because Pol.is leaves low-activity voters
  unclustered.
- Review date: 2027-01-10


### [DECISION-011] JSON Schema for the canonical output; jsonschema library
- Date: 2026-10-10
- Status: proposed
- Decided by: agent
- Context: TASK-003's test must show the output "matches schema", and
  TASK-005/006 will consume the same document.
- Options considered: hand-written checks in tests; JSON Schema file +
  `jsonschema`; pydantic models
- Decision: `schemas/assembly.schema.json` (JSON Schema 2020-12) is the
  source of truth, with `additionalProperties: false`. The script validates
  every document before writing it, and the tests validate fixtures against
  it. Library: `jsonschema` 4.26.0.
- Consequences: Any consumer, in any language, can validate the document.
  Schema changes are explicit diffs to one file.
- Review date: 2027-01-10


### [DECISION-012] Scripts are a package, run with `python -m`
- Date: 2026-10-10
- Status: proposed
- Decided by: agent
- Context: `export_and_transform` reuses the Pol.is client written for
  `polis_setup`. Sharing code between files run as `python scripts/x.py`
  requires path hacks.
- Options considered: duplicate the client; `sys.path` manipulation;
  `scripts/` as a package with absolute imports, run as modules
- Decision: `scripts/__init__.py`; shared client in `scripts/polis_client.py`;
  scripts run from the repository root as `python -m scripts.<name>`.
- Consequences: `python scripts/polis_setup.py` (documented in TASK-002) no
  longer works; docs now show `python -m scripts.polis_setup`.
- Review date: 2027-01-10


### [DECISION-013] Pol.is statements to NarraFirma: two CSV files, default columns
- Date: 2026-10-10
- Status: proposed (needs human review: whether Pol.is statements should be
  treated as stories is a methodological choice, not a technical one)
- Decided by: agent
- Context: TASK-004. NarraFirma (1.6.14) imports stories from a CSV whose
  columns are described by a story form, entered by hand or imported as a
  "story form CSV". ARCHITECTURE.md linked a NarraFirma repository that does
  not exist; the source is `pdfernhout/narrafirma`.
- Options considered: stories CSV only (user describes columns by hand);
  stories CSV plus story form CSV; NarraFirma project export (JSON, tied to
  internal IDs)
- Decision:
  - Write both a story form CSV and a stories CSV.
  - One story per Pol.is statement not rejected by moderation. Columns use
    NarraFirma's default names (`Participant ID`, `Eliciting question`,
    `Story title`, `Story text`, `Collection date`), so the stories file
    still imports if the form file is not used.
  - Participant ID is the Pol.is author ID; the eliciting question is the
    conversation topic; titles are `Statement <id>` (no summarising of
    participant text); dates are UTC ISO dates.
  - No vote data: Pol.is `comments.csv` agree/disagree counts double-count
    changed votes (DECISION-010).
  - Blank, rejected and malformed rows are skipped and counted rather than
    failing the run; a missing file or column, or another export format,
    still fails.
  - Text is kept as written apart from line endings and control
    characters. Formula-like text (`=...`) is not escaped, because
    NarraFirma would store the escape character as part of the story.
- Consequences: Verified by importing into a running NarraFirma 1.6.14
  (docs/NARRAFIRMA_IMPORT.md). The stories file holds participant text and
  must stay out of the repo. Opening it in a spreadsheet program could
  evaluate formula-like cells; it is meant for NarraFirma.
- Review date: 2027-01-10
