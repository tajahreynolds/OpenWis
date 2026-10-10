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
- Interface: HTTP API + `polis-cli`
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


· Pol.is CLI: https://github.com/colab-coop/polis-cli
· NarraFirma: https://github.com/participatorynarrative/narrafirma
· Hypha: https://github.com/hypha-dao
· Metagov Deliberation Interoperability: https://metagov.org