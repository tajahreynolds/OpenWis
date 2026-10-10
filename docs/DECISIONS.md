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