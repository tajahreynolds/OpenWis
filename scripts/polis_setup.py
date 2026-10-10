"""Create a Pol.is conversation, add seed statements, and open it for voting.

Reads the Pol.is instance and owner token from the environment:

    POLIS_BASE_URL  Base URL of the instance, e.g. http://localhost:5000
    POLIS_TOKEN     OIDC access token of the conversation owner

Usage:

    python scripts/polis_setup.py [--seeds data/synthetic/seeds.json]

The conversation ID is the only thing written to stdout, so it can be
captured by later steps. Progress and errors go to stderr.

Exit codes: 0 success, 1 Pol.is request failed, 2 bad configuration or seeds.

Endpoints and limits were verified against the Pol.is server pinned in
DECISION-008. See docs/ARCHITECTURE.md ("Pol.is setup").
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import requests

log = logging.getLogger("polis_setup")

DEFAULT_SEEDS_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "synthetic" / "seeds.json"
)
TIMEOUT_SECONDS = 30

# Field limits enforced by the pinned Pol.is server (server/app.ts). Checked
# before any request so bad seeds never leave a half-built conversation.
MAX_TOPIC_CHARS = 1000
MAX_DESCRIPTION_CHARS = 50000
MAX_STATEMENT_CHARS = 997


class PolisError(RuntimeError):
    """A Pol.is API request failed or returned an unexpected response."""


@dataclass(frozen=True)
class Seeds:
    """Conversation content to create in Pol.is.

    Attributes:
        topic: Conversation title.
        description: Conversation description shown to participants.
        statements: Seed statements, in the order they are added.
    """

    topic: str
    description: str
    statements: tuple[str, ...]


def load_seeds(path: Path) -> Seeds:
    """Load and validate a seeds file.

    The file is JSON with ``topic`` (string), ``description`` (string) and
    ``statements`` (non-empty list of unique, non-blank strings). Any other
    keys are ignored.

    Args:
        path: Path to the seeds JSON file.

    Returns:
        The validated seeds, with surrounding whitespace stripped.

    Raises:
        OSError: If the file cannot be read.
        ValueError: If the file is not valid JSON or breaks a rule above.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: not valid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top level must be a JSON object")

    topic = _required_text(data, "topic", MAX_TOPIC_CHARS, path)
    description = _required_text(data, "description", MAX_DESCRIPTION_CHARS, path)

    raw = data.get("statements")
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{path}: 'statements' must be a non-empty list")
    statements = []
    for i, item in enumerate(raw, 1):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{path}: statement {i} must be a non-blank string")
        text = item.strip()
        if len(text) > MAX_STATEMENT_CHARS:
            raise ValueError(
                f"{path}: statement {i} is {len(text)} characters; "
                f"Pol.is allows {MAX_STATEMENT_CHARS}"
            )
        if text in statements:
            raise ValueError(f"{path}: statement {i} duplicates an earlier one")
        statements.append(text)

    return Seeds(topic=topic, description=description, statements=tuple(statements))


def _required_text(data: dict, key: str, limit: int, path: Path) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}: '{key}' must be a non-blank string")
    value = value.strip()
    if len(value) > limit:
        raise ValueError(f"{path}: '{key}' is longer than {limit} characters")
    return value


def config_from_env(environ: Mapping[str, str]) -> tuple[str, str]:
    """Read the Pol.is connection settings.

    Args:
        environ: Environment mapping, usually ``os.environ``.

    Returns:
        A ``(base_url, token)`` tuple.

    Raises:
        ValueError: If ``POLIS_BASE_URL`` or ``POLIS_TOKEN`` is missing or blank.
    """
    missing = [
        name
        for name in ("POLIS_BASE_URL", "POLIS_TOKEN")
        if not environ.get(name, "").strip()
    ]
    if missing:
        raise ValueError(f"missing environment variable(s): {', '.join(missing)}")
    return environ["POLIS_BASE_URL"].strip(), environ["POLIS_TOKEN"].strip()


class PolisClient:
    """Minimal client for the Pol.is ``/api/v3`` endpoints this toolkit uses.

    Requests are not retried: a retried POST could create a duplicate
    conversation or statement.
    """

    def __init__(
        self, base_url: str, token: str, session: requests.Session | None = None
    ) -> None:
        """Create a client.

        Args:
            base_url: Base URL of the Pol.is instance.
            token: OIDC access token of the conversation owner.
            session: Optional ``requests.Session`` to use (for tests).
        """
        self._api = base_url.rstrip("/") + "/api/v3"
        self._session = session or requests.Session()
        self._session.headers["Authorization"] = f"Bearer {token}"

    def create_conversation(self, topic: str, description: str) -> tuple[str, str]:
        """Create a conversation that is open for voting.

        Pol.is rejects statements on a closed conversation, so the
        conversation is created active rather than opened after seeding.

        Args:
            topic: Conversation title.
            description: Conversation description.

        Returns:
            A ``(conversation_id, url)`` tuple. ``url`` is the participant
            link, or an empty string if the server did not return one.

        Raises:
            PolisError: If the request fails or returns no conversation ID.
            requests.RequestException: On network errors.
        """
        data = self._post(
            "/conversations",
            {
                "topic": topic,
                "description": description,
                "is_active": True,
                "is_draft": False,
            },
        )
        conversation_id = data.get("conversation_id")
        if not conversation_id:
            raise PolisError("POST /conversations returned no conversation_id")
        return str(conversation_id), str(data.get("url") or "")

    def add_seed_statement(self, conversation_id: str, text: str) -> int:
        """Add one seed statement to a conversation.

        Args:
            conversation_id: Conversation to add the statement to.
            text: Statement text.

        Returns:
            The statement ID (``tid``) assigned by Pol.is.

        Raises:
            PolisError: If the request fails or returns no statement ID.
            requests.RequestException: On network errors.
        """
        data = self._post(
            "/comments",
            {"conversation_id": conversation_id, "txt": text, "is_seed": True},
        )
        if "tid" not in data:
            raise PolisError("POST /comments returned no tid")
        return int(data["tid"])

    def _post(self, path: str, payload: dict) -> dict:
        response = self._session.post(
            self._api + path, json=payload, timeout=TIMEOUT_SECONDS
        )
        if not response.ok:
            raise PolisError(
                f"POST {path} returned {response.status_code}: "
                f"{response.text[:500].strip()}"
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise PolisError(f"POST {path} returned a non-JSON body") from exc
        if not isinstance(data, dict):
            raise PolisError(f"POST {path} returned unexpected JSON")
        return data


def setup_conversation(client: PolisClient, seeds: Seeds) -> str:
    """Create a conversation, add every seed statement, and leave it open.

    Args:
        client: Client authenticated as the conversation owner.
        seeds: Conversation content.

    Returns:
        The new conversation ID.

    Raises:
        PolisError: If a request fails. If this happens after the
            conversation was created, its ID is logged so it can be cleaned up.
        requests.RequestException: On network errors.
    """
    conversation_id, url = client.create_conversation(seeds.topic, seeds.description)
    log.info("Created conversation %s %s", conversation_id, url)
    try:
        for n, text in enumerate(seeds.statements, 1):
            tid = client.add_seed_statement(conversation_id, text)
            log.info("Seed %d/%d added (tid %d)", n, len(seeds.statements), tid)
    except (PolisError, requests.RequestException):
        log.error(
            "Seeding stopped; conversation %s exists with only some statements",
            conversation_id,
        )
        raise
    log.info("Conversation %s is open for voting", conversation_id)
    return conversation_id


def main(argv: Sequence[str] | None = None) -> int:
    """Run the setup from the command line.

    Args:
        argv: Command-line arguments, excluding the program name.

    Returns:
        Process exit code: 0 success, 1 Pol.is request failed, 2 bad
        configuration or seeds.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--seeds",
        type=Path,
        default=DEFAULT_SEEDS_PATH,
        help="seeds JSON file (default: data/synthetic/seeds.json)",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(message)s"
    )

    try:
        base_url, token = config_from_env(os.environ)
        seeds = load_seeds(args.seeds)
    except (OSError, ValueError) as exc:
        log.error("%s", exc)
        return 2

    try:
        conversation_id = setup_conversation(PolisClient(base_url, token), seeds)
    except (PolisError, requests.RequestException) as exc:
        log.error("%s", exc)
        return 1

    print(conversation_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
