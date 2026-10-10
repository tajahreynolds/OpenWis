# Pol.is export fixtures

Real export files (`polis-export/1`) produced by Pol.is from **synthetic data
only**, used by `tests/test_export_and_transform.py`.

- `clustered/`: after Pol.is math has run (two opinion groups).
- `messy/`: **hand-made, not Pol.is output**, for `storybridge` tests. Same
  `format.json`; `comments.csv` rows out of ID order with multi-line text,
  quotes, non-ASCII, a leading `;`, a formula-like `=`, a control character,
  a blank statement, a rejected statement, a non-integer `author-id` and a
  bad timestamp; `summary.csv` topic contains `|`, quotes and a comma.
- `no_math/`: votes cast but math not yet run: `comment-groups.csv` has a
  header only and every `group-id` is empty. Three synthetic participants
  (`synthetic-x-<n>`) cast 6 votes on statements 0-2.

`summary.csv` in `clustered/` and `no_math/` is Pol.is output too (no final
newline, `url` shows `undefined://` because no proxy set the protocol).

## `clustered/`

- Server: `compdemocracy/polis@1db2f7919f33b740b34bb84ed9a1fb5bfb1914d2`
  (DECISION-008), run as in `docs/POLIS_SANDBOX.md`, with the Python math
  worker (`delphi/scripts/math_poller.py --once`) to compute clusters.
- Conversation (both fixtures): created by `python -m scripts.polis_setup`
  from `data/synthetic/seeds.json` (8 fictional statements).
- Votes: 30 synthetic participants (XIDs `synthetic-<bloc>-<n>`) in three
  scripted blocs with opposing stances and 10-15% random noise, 207 votes,
  then participant 1 changed one vote (statement 0, agree to disagree) so the
  fixture contains a vote change.
- Downloaded from `/api/v3/reportExport/<report_id>/<file>` on 2026-10-10.

What the files show (checked by the tests):

- `votes.csv` has one row per vote event: 208 rows for 207 current votes.
- 22 of the 30 voters were clustered into 2 groups; the rest have an empty
  `group-id` (too few votes for Pol.is to place them).
- `group-a` / `group-b` in `comment-groups.csv` are group IDs 0 / 1 in
  `participant-votes.csv`.
- Upstream quirk: `participant-votes.csv` shows participant 1's old vote on
  statement 0, and `comments.csv` counts both the old and the new vote. Only
  `votes.csv` is used for vote totals.

To regenerate after moving the Pol.is pin, repeat the steps above and update
the expected values in the tests.
