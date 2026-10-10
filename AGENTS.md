# AGENTS.md — Open Wisdom Stack


This file is the primary instruction set for AI agents working on this repository.
Read this file completely before taking any action.


## Project Overview


Open Wisdom Stack is an integration toolkit that lets small communities run
deliberative assemblies using existing open-source tools. It connects Pol.is
(deliberation), NarraFirma (narrative inquiry), Hypha (governance), and a
metrics dashboard via lightweight Python glue code and documentation.


We do NOT build new core software. We integrate existing tools.


## Core Principle


Agents execute technical work. Humans execute relational, ethical, and
community-facing work. Never cross this boundary.


## Human-Only Tasks (AGENTS MUST NEVER DO THESE)


- Contact, recruit, or communicate with community members or participants
- Facilitate assemblies, workshops, or deliberation sessions
- Build relationships with institutions, NGOs, or governments
- Make commitments on behalf of the project to external parties
- Decide what questions to ask communities
- Interpret community feedback with cultural or ethical judgment
- Handle interpersonal conflict or community grievances
- Fundraise, manage donors, or communicate with funders
- Make legal decisions or sign agreements
- Publish public communications, press releases, or social media
- Hire, fire, or manage personnel
- Decide when to pause or stop a community engagement


If a task appears to require any of the above, STOP. Flag it in the issue
with the label `human-required` and do not proceed.


## Agent-Allowed Tasks


- Write, refactor, and test Python integration scripts
- Write and maintain documentation (technical, not community-facing)
- Create and configure dashboards (Google Sheets, Looker Studio, Metabase)
- Write unit tests, integration tests, and test fixtures
- Generate synthetic test data
- Configure CI/CD (GitHub Actions, Forgejo Actions)
- Write Dockerfiles, docker-compose files, and setup scripts
- Triage issues and propose labels (human approves)
- Write migration scripts and data transformation code
- Generate diagrams from architecture specs
- Summarize long issues or docs into structured formats
- Write release notes from commit history
- Lint, format, and dependency management
- Create boilerplate from templates
- Write API adaptors against documented interfaces


## How to Work


1. Read `docs/SCOPE.md` to understand what is in and out of scope.
2. Read `docs/ARCHITECTURE.md` before writing any integration code.
3. Pick a task from `docs/AGENT_BACKLOG.md` or a GitHub issue labeled `agent-task`.
4. Every task has acceptance criteria. Meet them exactly.
5. Every code change requires a test. No exceptions.
6. Every decision goes in `docs/DECISIONS.md` using the template there.
7. If you are uncertain whether a task is human-only, assume it is. Flag it.
8. Do not install new dependencies without updating `requirements.txt` and
   documenting why in `docs/DECISIONS.md`.
9. Do not modify `AGENTS.md` or `docs/HUMAN_TASKS.md`. Only humans can.


## Commit Convention


```


<type>(<scope>): <description>


Types: feat, fix, docs, test, chore, refactor, ci
Scopes: polis, narrafirma, dashboard, integration, docs, ci


```


Example: `feat(polis): add export_and_transform function`


## Testing Requirements


- All Python functions must have unit tests in `tests/`
- Integration tests must use synthetic data, never real community data
- Run `pytest` before committing
- Minimum 80% coverage on new code


## Documentation Requirements


- Every public function has a docstring with args, returns, and raises
- Every integration point documented in `docs/ARCHITECTURE.md`
- Every new dependency documented in `docs/DECISIONS.md`


## What Agents Must Never Assume


- That a community wants to participate
- That an institution will accept recommendations
- That a tool works as documented without testing
- That a data format is stable across versions
- That a human task can be automated because it "seems simple"


## Escalation


If blocked, create a GitHub issue with:
- Label: `blocked` and one of `human-required`, `needs-decision`, `tool-broken`
- Description of the blocker
- What you tried
- What you need from a human


Do not attempt workarounds that cross the human-agent boundary.