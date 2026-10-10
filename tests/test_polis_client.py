"""Unit tests for scripts/polis_client.py against a mocked Pol.is API.

Response shapes mirror what the pinned Pol.is server returned in the local
sandbox (docs/POLIS_SANDBOX.md).
"""

import pytest
import responses
from responses import matchers

from scripts.polis_client import PolisClient, PolisError, config_from_env

BASE = "http://polis.test"
API = f"{BASE}/api/v3"
TOKEN = "test-token"
AUTH = matchers.header_matcher({"Authorization": f"Bearer {TOKEN}"})


def mock_create(rsps, conversation_id="abc123"):
    return rsps.post(
        f"{API}/conversations",
        json={"url": f"{BASE}/{conversation_id}", "conversation_id": conversation_id},
        match=[
            AUTH,
            matchers.json_params_matcher(
                {"topic": "T", "description": "D", "is_active": True, "is_draft": False}
            ),
        ],
    )


def mock_seed(rsps, text, tid, conversation_id="abc123"):
    return rsps.post(
        f"{API}/comments",
        json={"tid": tid, "currentPid": 0},
        match=[
            AUTH,
            matchers.json_params_matcher(
                {"conversation_id": conversation_id, "txt": text, "is_seed": True}
            ),
        ],
    )


# config_from_env


def test_config_from_env_reads_and_strips():
    env = {"POLIS_BASE_URL": " http://x ", "POLIS_TOKEN": " t "}
    assert config_from_env(env) == ("http://x", "t")


@pytest.mark.parametrize(
    ("env", "missing"),
    [
        ({}, "POLIS_BASE_URL, POLIS_TOKEN"),
        ({"POLIS_BASE_URL": "http://x"}, "POLIS_TOKEN"),
        ({"POLIS_BASE_URL": "http://x", "POLIS_TOKEN": "  "}, "POLIS_TOKEN"),
    ],
)
def test_config_from_env_reports_missing(env, missing):
    with pytest.raises(
        ValueError, match=f"missing environment variable\\(s\\): {missing}"
    ):
        config_from_env(env)


# PolisClient


@responses.activate
def test_create_conversation_posts_open_conversation():
    mock_create(responses)
    client = PolisClient(BASE + "/", TOKEN)  # trailing slash is tolerated
    assert client.create_conversation("T", "D") == (
        "abc123",
        f"{BASE}/abc123",
    )


@responses.activate
def test_create_conversation_requires_conversation_id():
    responses.post(f"{API}/conversations", json={"url": "x"})
    with pytest.raises(PolisError, match="returned no conversation_id"):
        PolisClient(BASE, TOKEN).create_conversation("t", "d")


@responses.activate
def test_add_seed_statement_returns_tid_including_zero():
    mock_seed(responses, "First statement.", tid=0)
    assert (
        PolisClient(BASE, TOKEN).add_seed_statement("abc123", "First statement.") == 0
    )


@responses.activate
def test_add_seed_statement_requires_tid():
    responses.post(f"{API}/comments", json={"currentPid": 0})
    with pytest.raises(PolisError, match="returned no tid"):
        PolisClient(BASE, TOKEN).add_seed_statement("abc123", "x")


@responses.activate
def test_http_error_includes_status_and_polis_error_code():
    responses.post(
        f"{API}/comments",
        json={"error": "polis_err_post_comment_duplicate", "status": 409},
        status=409,
    )
    with pytest.raises(PolisError, match="409.*polis_err_post_comment_duplicate"):
        PolisClient(BASE, TOKEN).add_seed_statement("abc123", "x")


@responses.activate
def test_non_json_body_is_an_error():
    responses.post(f"{API}/conversations", body="<html>proxy page</html>")
    with pytest.raises(PolisError, match="non-JSON body"):
        PolisClient(BASE, TOKEN).create_conversation("t", "d")


@responses.activate
def test_json_that_is_not_an_object_is_an_error():
    responses.post(f"{API}/conversations", json=["unexpected"])
    with pytest.raises(PolisError, match="unexpected JSON"):
        PolisClient(BASE, TOKEN).create_conversation("t", "d")


# reports and export files


def reports_url(conversation_id="abc123"):
    return f"{API}/reports?conversation_id={conversation_id}"


@responses.activate(assert_all_requests_are_fired=True)
def test_get_report_id_uses_existing_report():
    responses.get(
        reports_url(),
        json=[{"report_id": "r1", "conversation_id": "abc123"}],
        match=[AUTH],
    )
    assert PolisClient(BASE, TOKEN).get_report_id("abc123") == "r1"


@responses.activate(assert_all_requests_are_fired=True)
def test_get_report_id_creates_report_when_none_exists():
    responses.get(reports_url(), json=[])
    responses.post(
        f"{API}/reports",
        json={},
        match=[AUTH, matchers.json_params_matcher({"conversation_id": "abc123"})],
    )
    responses.get(reports_url(), json=[{"report_id": "r2"}])

    assert PolisClient(BASE, TOKEN).get_report_id("abc123") == "r2"
    assert [c.request.method for c in responses.calls] == ["GET", "POST", "GET"]


@pytest.mark.parametrize("second_listing", [[], [{"report_id": ""}], [{}]])
@responses.activate
def test_get_report_id_fails_without_a_usable_report(second_listing):
    responses.get(reports_url(), json=[])
    responses.post(f"{API}/reports", json={})
    responses.get(reports_url(), json=second_listing)
    with pytest.raises(PolisError, match="no report found for conversation abc123"):
        PolisClient(BASE, TOKEN).get_report_id("abc123")


@responses.activate
def test_get_report_id_rejects_non_list_listing():
    responses.get(reports_url(), json={"report_id": "r1"})
    with pytest.raises(PolisError, match="GET /reports returned unexpected JSON"):
        PolisClient(BASE, TOKEN).get_report_id("abc123")


@responses.activate
def test_download_export_file_returns_bytes():
    responses.get(
        f"{API}/reportExport/r1/votes.csv", body=b"timestamp,vote\n", match=[AUTH]
    )
    data = PolisClient(BASE, TOKEN).download_export_file("r1", "votes.csv")
    assert data == b"timestamp,vote\n"


@responses.activate
def test_download_export_file_raises_on_http_error():
    responses.get(
        f"{API}/reportExport/r1/comment-groups.csv",
        json={"error": "polis_error_no_pca_data"},
        status=500,
    )
    with pytest.raises(
        PolisError, match="GET /reportExport/r1/comment-groups.csv returned 500"
    ):
        PolisClient(BASE, TOKEN).download_export_file("r1", "comment-groups.csv")
