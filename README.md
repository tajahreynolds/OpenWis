# Open Wisdom Stack

[![CI](https://github.com/tajahreynolds/OpenWis/actions/workflows/ci.yml/badge.svg)](https://github.com/tajahreynolds/OpenWis/actions/workflows/ci.yml)

An integration toolkit that lets small communities run deliberative assemblies
using existing open-source tools: Pol.is (deliberation), NarraFirma (narrative
inquiry), Hypha (governance), and a metrics dashboard, connected by lightweight
Python glue code.

This project integrates existing tools; it does not build new core software.

## Quick start (development)

Requires Python 3.11+.

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

Checks run by CI (`.github/workflows/ci.yml`):

```
ruff check .            # lint
ruff format --check .   # formatting
pytest --cov            # tests, fails under 80% coverage of scripts/
```

## Layout

| Path | Contents |
|------|----------|
| `scripts/` | Integration scripts, run as `python -m scripts.<name>` |
| `schemas/` | JSON Schema for the canonical assembly output |
| `tests/` | Unit and integration tests; `tests/fixtures/` holds Pol.is exports of synthetic conversations |
| `docs/` | Project documentation |
| `data/synthetic/` | Synthetic input data |
| `data/output/` | Generated output (git-ignored) |

Only synthetic data is committed. Real participant data never goes in this
repo.

## Documentation

- [AGENTS.md](AGENTS.md) — instructions for AI agents working on this repo
- [CONTRIBUTING.md](CONTRIBUTING.md) — conventions and review process
- [docs/SCOPE.md](docs/SCOPE.md) — what is and is not in scope
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — components, integration points, data schema
- [docs/AGENT_BACKLOG.md](docs/AGENT_BACKLOG.md) — agent task backlog
- [docs/HUMAN_TASKS.md](docs/HUMAN_TASKS.md) — human-only task registry
- [docs/DECISIONS.md](docs/DECISIONS.md) — decision log
- [docs/POLIS_SANDBOX.md](docs/POLIS_SANDBOX.md) — local Pol.is for testing the integration
- [docs/NARRAFIRMA_IMPORT.md](docs/NARRAFIRMA_IMPORT.md) — importing Pol.is statements into NarraFirma
