# Contributing


## For Humans


Read `AGENTS.md` to understand what agents do and do not do. Your role is
everything in `docs/HUMAN_TASKS.md` plus reviewing agent output.


## For Agents


Read `AGENTS.md` first. Then `docs/SCOPE.md`. Then `docs/ARCHITECTURE.md`.
Pick a task from `docs/AGENT_BACKLOG.md` or an issue labeled `agent-task`.


## Conventions


- Commits: `<type>(<scope>): <description>`
- Branches: `agent/<task-id>-<short-description>`
- PRs: reference task ID, include test output, list decisions made
- Tests: required for all code changes
- Docs: required for all public functions and integration points


## Review Process


1. Agent opens PR with test results.
2. Human reviews for scope, boundary violations, and quality.
3. Human approves or requests changes.
4. Human merges. Agents do not merge.


## What Gets Rejected


- Code without tests
- Docs without clear audience
- Scope creep beyond `docs/SCOPE.md`
- Any attempt to perform a human-only task
- New dependencies without a decision log entry