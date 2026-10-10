# Open Wisdom Stack

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

## Layout

| Path | Contents |
|------|----------|
| `scripts/` | Integration scripts |
| `tests/` | Unit and integration tests |
| `docs/` | Project documentation |
| `data/synthetic/` | Synthetic test data (the only data committed to this repo) |

## Documentation

- [AGENTS.md](AGENTS.md) — instructions for AI agents working on this repo
- [CONTRIBUTING.md](CONTRIBUTING.md) — conventions and review process
- [docs/SCOPE.md](docs/SCOPE.md) — what is and is not in scope
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — components, integration points, data schema
- [docs/AGENT_BACKLOG.md](docs/AGENT_BACKLOG.md) — agent task backlog
- [docs/HUMAN_TASKS.md](docs/HUMAN_TASKS.md) — human-only task registry
- [docs/DECISIONS.md](docs/DECISIONS.md) — decision log
