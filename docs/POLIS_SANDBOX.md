# Pol.is Sandbox

A throwaway local Pol.is for developing and testing the integration scripts.
Audience: developers and agents. Use synthetic data only.

The sandbox uses Pol.is's development login (an OIDC simulator with public
test accounts). Never point it at, or reuse its settings for, a production
instance.

## Pinned version

`compdemocracy/polis@1db2f7919f33b740b34bb84ed9a1fb5bfb1914d2` (branch `edge`,
2026-10-10). See DECISION-002 and DECISION-008. To move the pin, repeat the
verification at the end of this page against the new commit and update both
decisions, `requirements.txt` and `docs/ARCHITECTURE.md`.

## Option A: standard Pol.is dev setup (your machine)

Follow the Pol.is README at the pinned commit:

1. Clone `compdemocracy/polis` and check out the pinned commit.
2. Create local certificates with `mkcert` in `~/.simulacrum/certs`
   (`localhost.pem`, `localhost-key.pem`, plus `rootCA.pem` copied from
   `mkcert -CAROOT`).
3. `make generate-jwt-keys`
4. `cp example.env .env`
5. `make start`

The API is then at `http://localhost:5000` and the login simulator at
`https://localhost:3000`.

## Option B: no image builds (restricted networks)

Used and verified in an agent container whose network policy blocks the
Alpine package mirror, so Pol.is's own images cannot build. Only Docker Hub,
npm and crates.io are needed.

1. Clone at the pinned commit; `cp example.env .env`.
2. Certificates: any CA works, not just `mkcert`. Issue `localhost.pem` for
   `localhost`, `127.0.0.1`, `oidc-simulator`, `host.docker.internal`, and put
   it with `localhost-key.pem` and `rootCA.pem` in `~/.simulacrum/certs`
   (the simulator library always reads that path).
3. JWT keys: `node server/scripts/generate-jwt-keys.js`
4. Database: run `postgres:17-alpine` with `POSTGRES_DB`, `POSTGRES_USER`
   and `POSTGRES_PASSWORD` from `.env`, published on port 5432.
5. Migrations: build Pol.is's runner with
   `cargo build --release --locked -p polis-migrate` in `queue-rs/`, then run
   `server/bin/run-migrations.sh` with `DATABASE_URL` pointing at
   `127.0.0.1:5432` and `POLIS_MIGRATE_BIN` at the built binary.
6. Login simulator: in `oidc-simulator/`, `npm install` (not `npm ci`; see
   below), then `npx ts-node src/index.ts`.
7. Server: in `server/`, `npm ci` and `npx tsc`, then start
   `node dist/index.js` with `.env` loaded and these overrides:
   - `DATABASE_URL` → `127.0.0.1:5432`
   - `JWKS_URI=https://localhost:3000/.well-known/jwks.json`
   - `NODE_EXTRA_CA_CERTS` → your `rootCA.pem`
   - `JWT_PRIVATE_KEY_PATH` / `JWT_PUBLIC_KEY_PATH` → `server/keys/`

Check: `GET http://localhost:5000/api/v3/testConnection` returns
`{"status": "ok"}`.

## Getting a token

The simulator issues tokens with the OAuth password grant. The test account
and password are public, listed in Pol.is's `oidc-simulator/README.md`:

- `POST https://localhost:3000/oauth/token` (trust your `rootCA.pem`)
- JSON body: `grant_type=password`, `username=admin@polis.test`,
  `password` from that README, `client_id=dev-client-id`, `audience=users`,
  `scope=openid profile email`
- Use `access_token` from the response as `POLIS_TOKEN`.

For a real instance, get the owner's access token from that instance's OIDC
provider instead. Keep it in `.env` (git-ignored), never in the repo.

## Running the integration

    export POLIS_BASE_URL=http://localhost:5000
    export POLIS_TOKEN=<access token>
    python -m scripts.polis_setup            # prints the conversation ID
    python -m scripts.export_and_transform --conversation-id <id>
    POLIS_LIVE_TESTS=1 POLIS_LIVE_EXPORT_CONVERSATION_ID=<id> \
        pytest tests/test_polis_live.py

The export test needs a conversation with votes whose math has run (next
section).

## Opinion groups (math worker)

Clusters only appear after Pol.is's Python math worker has processed the
votes. Option A's `make start` runs it. For option B it can run natively:

1. Python 3.12 venv (`delphi/pyproject.toml` requires `>=3.12,<3.13`).
2. The poller imports only part of Delphi's dependency list. Installing
   `numpy pandas scipy scikit-learn sqlalchemy psycopg2-binary boto3 pyyaml`
   at the versions in `delphi/requirements.lock` was enough; torch and the
   other heavy packages were not needed.
3. From `delphi/`, with `PYTHONPATH=.`:
   `python scripts/math_poller.py --once`, with environment
   `DATABASE_URL` (Postgres at `127.0.0.1:5432`), `DATABASE_SSL_MODE=disable`,
   `MATH_ENV=dev` (the namespace the dev server reads) and
   `MATH_POLLER_MEMORY_LIMIT_MB` (needed when there is no cgroup memory limit).

`--once` processes conversations with new votes and exits. Pol.is needs
enough voters with enough votes to form groups: in the fixture run, 22 of 30
synthetic voters with 7 or more votes each were placed in 2 groups.

## Verified behaviour at the pinned commit (2026-10-10)

| Request | Result |
|---|---|
| `POST /conversations` (bearer token) | 200 `{url, conversation_id}` |
| `POST /conversations` (no token) | 401 `No authentication token found` |
| `POST /conversations` (invalid token) | 401 `Invalid token format` |
| `POST /comments` with `is_seed` | 200 `{tid, currentPid}`, first `tid` is 0 |
| Same statement twice | 409 `polis_err_post_comment_duplicate` |
| `POST /comments` on a closed conversation | 403 `polis_err_conversation_is_closed` |
| `scripts/polis_setup.py` with `data/synthetic/seeds.json` | conversation active, 8 seed statements |
| `POST /reports` | 200 `{}`; `GET /reports?conversation_id=` lists `report_id` |
| `GET /reportExport/<rid>/<file>` | 200 for every file, before and after math |
| `comment-groups.csv` before math | header only, no group columns |
| `scripts/export_and_transform.py` | output matches the fixture values (`tests/fixtures/polis_export/`) |

## Upstream quirks at the pinned commit

- `oidc-simulator`: `npm ci` fails because `package-lock.json` is out of
  sync (`Missing: picomatch@4.0.7`); `npm install` works.
- The simulator's TLS library reads `~/.simulacrum/certs` even when
  `CERT_DIR` points elsewhere.
- Pol.is's `rust-toolchain.toml` asks for Rust 1.98.1; `polis-migrate` built
  fine with 1.97 (`RUSTUP_TOOLCHAIN=1.97.0`), within its declared minimum
  of 1.88.
