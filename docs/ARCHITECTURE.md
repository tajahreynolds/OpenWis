# Architecture


## Overview


```


[Community] → [Pol.is] → [Integration Scripts] → [NarraFirma]
↓                                    ↓
[Hypha] ← ────────────────────────→ [Dashboard]


```


## Components


### Pol.is
- Role: Deliberation and consensus-finding
- Interface: HTTP API (`/api/v3`), owner authenticated with an OIDC bearer
  token (DECISION-008). No official API docs; endpoints are verified against
  the server source at the pinned commit.
- Version: pinned to `compdemocracy/polis@1db2f7919f33b740b34bb84ed9a1fb5bfb1914d2`
  (DECISION-002, DECISION-008)
- Data out: Votes, clusters, comments, participant counts
- License: AGPL-3.0


### NarraFirma
- Role: Participatory narrative inquiry
- Interface: WordPress plugin or Node.js app
- Data in: Stories, survey responses, annotations
- License: Open source


### Hypha
- Role: Governance and decision logging
- Interface: REST API
- Data out: Proposals, votes, decision records
- License: Open source


### Dashboard
- Role: Metrics visualization
- Stack: Google Sheets + Looker Studio (Phase 1)
- Data in: Participation counts, consensus scores, survey results


## Integration Points


### Pol.is setup
- Script: `scripts/polis_setup.py` (TASK-002)
- Input: `data/synthetic/seeds.json` (`topic`, `description`, `statements`)
- Config: `POLIS_BASE_URL`, `POLIS_TOKEN` (owner's OIDC access token)
- Calls, in order:
  1. `POST /api/v3/conversations` with `topic`, `description`,
     `is_active: true`, `is_draft: false` → `{conversation_id, url}`.
     The conversation is created open because Pol.is rejects statements on
     a closed one (`403 polis_err_conversation_is_closed`).
  2. `POST /api/v3/comments` with `conversation_id`, `txt`, `is_seed: true`,
     once per statement → `{tid, currentPid}` (`tid` starts at 0).
- Output: conversation ID on stdout; progress on stderr
- Server limits checked before any request: topic 1000 chars, description
  50000, statement 997; duplicate statements are rejected by Pol.is (409).
- No retries: a retried POST could duplicate a conversation or statement.
- Local sandbox: `docs/POLIS_SANDBOX.md`


### Pol.is → Dashboard
- Endpoint: Pol.is export CSV
- Transform: `scripts/export_and_transform.py`
- Output: JSON with cluster summaries and participation counts


### Pol.is → NarraFirma
- Endpoint: Pol.is comments export
- Transform: `scripts/storybridge.py`
- Output: NarraFirma-compatible import format


### Hypha → Dashboard
- Endpoint: Hypha API
- Transform: `scripts/hypha_to_dashboard.py`
- Output: Decision records in dashboard schema


## Data Schema (Canonical)


```json
{
  "assembly_id": "string",
  "participants": 0,
  "statements": 0,
  "votes": 0,
  "clusters": [
    {"id": 0, "size": 0, "consensus": 0.0}
  ],
  "stories_collected": 0,
  "decisions": [
    {"id": "string", "text": "string", "votes_for": 0, "votes_against": 0}
  ]
}
```


Hosting Requirements


· Python 3.11+
· Docker + docker-compose
· Access to a Pol.is instance (public or self-hosted)
· NarraFirma instance (WordPress or Node.js)
· Google Sheets API credentials (for dashboard)


External References


· Pol.is: https://github.com/compdemocracy/polis
· NarraFirma: https://github.com/participatorynarrative/narrafirma
· Hypha: https://github.com/hypha-dao
· Metagov Deliberation Interoperability: https://metagov.org