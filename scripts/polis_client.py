"""Minimal client for the Pol.is ``/api/v3`` endpoints this toolkit uses.

Shared by ``scripts.polis_setup`` and ``scripts.export_and_transform``.
Endpoints and response shapes were verified against the Pol.is server pinned
in DECISION-008 (docs/POLIS_SANDBOX.md).
"""

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import quote

import requests

TIMEOUT_SECONDS = 30


class PolisError(RuntimeError):
    """A Pol.is API request failed or returned an unexpected response."""


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
    """Client authenticated as a conversation owner.

    Requests are not retried: a retried POST could create a duplicate
    conversation, statement or report.
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
        data = self._json(
            "POST",
            "/conversations",
            dict,
            json={
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
        data = self._json(
            "POST",
            "/comments",
            dict,
            json={"conversation_id": conversation_id, "txt": text, "is_seed": True},
        )
        if "tid" not in data:
            raise PolisError("POST /comments returned no tid")
        return int(data["tid"])

    def get_report_id(self, conversation_id: str) -> str:
        """Return a report ID for a conversation, creating a report if none exists.

        Export files are served per report. Every report of a conversation
        exports the same data, so the first one listed is used.

        Args:
            conversation_id: Conversation to export.

        Returns:
            The report ID.

        Raises:
            PolisError: If a request fails or no report can be found.
            requests.RequestException: On network errors.
        """
        params = {"conversation_id": conversation_id}
        reports = self._json("GET", "/reports", list, params=params)
        if not reports:
            self._json("POST", "/reports", dict, json=params)
            reports = self._json("GET", "/reports", list, params=params)
        report_id = reports[0].get("report_id") if reports else None
        if not isinstance(report_id, str) or not report_id:
            raise PolisError(f"no report found for conversation {conversation_id}")
        return report_id

    def download_export_file(self, report_id: str, filename: str) -> bytes:
        """Download one export file of a report.

        Args:
            report_id: Report to export.
            filename: Export file name, e.g. ``votes.csv`` or ``format.json``.

        Returns:
            The file's raw bytes.

        Raises:
            PolisError: If the request fails.
            requests.RequestException: On network errors.
        """
        path = f"/reportExport/{quote(report_id, safe='')}/{quote(filename)}"
        return self._request("GET", path).content

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        response = self._session.request(
            method, self._api + path, timeout=TIMEOUT_SECONDS, **kwargs
        )
        if not response.ok:
            raise PolisError(
                f"{method} {path} returned {response.status_code}: "
                f"{response.text[:500].strip()}"
            )
        return response

    def _json(self, method: str, path: str, expected: type, **kwargs):
        response = self._request(method, path, **kwargs)
        try:
            data = response.json()
        except ValueError as exc:
            raise PolisError(f"{method} {path} returned a non-JSON body") from exc
        if not isinstance(data, expected):
            raise PolisError(f"{method} {path} returned unexpected JSON")
        return data
