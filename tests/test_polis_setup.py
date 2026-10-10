"""Unit tests for scripts/polis_setup.py against a mocked Pol.is API.

Response shapes mirror what the pinned Pol.is server returned in the local
sandbox (docs/POLIS_SANDBOX.md).
"""

import json

import pytest
import requests
import responses
from responses import matchers

from scripts import polis_setup
from scripts.polis_client import PolisClient, PolisError
from scripts.polis_setup import Seeds

BASE = "http://polis.test"
API = f"{BASE}/api/v3"
TOKEN = "test-token"
AUTH = matchers.header_matcher({"Authorization": f"Bearer {TOKEN}"})

SEEDS = Seeds(
    topic="[SANDBOX] Topic",
    description="Synthetic description.",
    statements=("First statement.", "Second statement."),
)


def write_seeds(tmp_path, data):
    path = tmp_path / "seeds.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def valid_seed_data(**overrides):
    data = {
        "topic": "[SANDBOX] Topic",
        "description": "Synthetic description.",
        "statements": ["First statement.", "Second statement."],
    }
    data.update(overrides)
    return data


def mock_create(rsps, conversation_id="abc123", status=200):
    body = {"url": f"{BASE}/{conversation_id}", "conversation_id": conversation_id}
    return rsps.post(
        f"{API}/conversations",
        json=body if status == 200 else {"error": "polis_err_x"},
        status=status,
        match=[
            AUTH,
            matchers.json_params_matcher(
                {
                    "topic": SEEDS.topic,
                    "description": SEEDS.description,
                    "is_active": True,
                    "is_draft": False,
                }
            ),
        ],
    )


def mock_seed(rsps, text, tid, conversation_id="abc123", status=200, body=None):
    return rsps.post(
        f"{API}/comments",
        json=body if body is not None else {"tid": tid, "currentPid": 0},
        status=status,
        match=[
            AUTH,
            matchers.json_params_matcher(
                {"conversation_id": conversation_id, "txt": text, "is_seed": True}
            ),
        ],
    )


# load_seeds


def test_load_seeds_strips_whitespace(tmp_path):
    path = write_seeds(
        tmp_path, valid_seed_data(topic="  T  ", statements=["  a  ", "b"])
    )
    seeds = polis_setup.load_seeds(path)
    assert seeds.topic == "T"
    assert seeds.statements == ("a", "b")


def test_repo_seeds_file_is_valid():
    seeds = polis_setup.load_seeds(polis_setup.DEFAULT_SEEDS_PATH)
    assert seeds.topic.startswith("[SANDBOX]")
    assert len(seeds.statements) >= 1


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"topic": ""}, "'topic' must be a non-blank string"),
        ({"topic": 5}, "'topic' must be a non-blank string"),
        ({"topic": "x" * 1001}, "'topic' is longer than 1000"),
        ({"description": None}, "'description' must be a non-blank string"),
        ({"statements": []}, "'statements' must be a non-empty list"),
        ({"statements": "a"}, "'statements' must be a non-empty list"),
        ({"statements": ["ok", "  "]}, "statement 2 must be a non-blank string"),
        ({"statements": ["ok", 3]}, "statement 2 must be a non-blank string"),
        ({"statements": ["x" * 998]}, "statement 1 is 998 characters"),
        ({"statements": ["a", " a "]}, "statement 2 duplicates an earlier one"),
    ],
)
def test_load_seeds_rejects_invalid(tmp_path, overrides, message):
    path = write_seeds(tmp_path, valid_seed_data(**overrides))
    with pytest.raises(ValueError, match=message):
        polis_setup.load_seeds(path)


def test_load_seeds_rejects_non_object(tmp_path):
    path = write_seeds(tmp_path, ["not", "an", "object"])
    with pytest.raises(ValueError, match="top level must be a JSON object"):
        polis_setup.load_seeds(path)


def test_load_seeds_rejects_bad_json(tmp_path):
    path = tmp_path / "seeds.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        polis_setup.load_seeds(path)


# setup_conversation


@responses.activate(assert_all_requests_are_fired=True)
def test_setup_conversation_creates_then_seeds_in_order():
    mock_create(responses)
    mock_seed(responses, "First statement.", tid=0)
    mock_seed(responses, "Second statement.", tid=1)

    assert polis_setup.setup_conversation(PolisClient(BASE, TOKEN), SEEDS) == "abc123"

    sent = [(c.request.url, json.loads(c.request.body)) for c in responses.calls]
    assert [url for url, _ in sent] == [
        f"{API}/conversations",
        f"{API}/comments",
        f"{API}/comments",
    ]
    assert [body.get("txt") for _, body in sent[1:]] == list(SEEDS.statements)


@responses.activate
def test_setup_conversation_logs_id_when_seeding_fails(caplog):
    mock_create(responses)
    mock_seed(responses, "First statement.", tid=0)
    mock_seed(
        responses,
        "Second statement.",
        tid=None,
        status=403,
        body={"error": "polis_err_conversation_is_closed"},
    )

    with pytest.raises(PolisError, match="403"):
        polis_setup.setup_conversation(PolisClient(BASE, TOKEN), SEEDS)
    assert "conversation abc123 exists with only some statements" in caplog.text


# main


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("POLIS_BASE_URL", BASE)
    monkeypatch.setenv("POLIS_TOKEN", TOKEN)


@responses.activate
def test_main_prints_only_conversation_id_to_stdout(env, tmp_path, capsys):
    path = write_seeds(tmp_path, valid_seed_data())
    mock_create(responses)
    mock_seed(responses, "First statement.", tid=0)
    mock_seed(responses, "Second statement.", tid=1)

    assert polis_setup.main(["--seeds", str(path)]) == 0
    out, err = capsys.readouterr()
    assert out == "abc123\n"
    assert TOKEN not in out + err


def test_main_exits_2_on_missing_config(monkeypatch, capsys):
    monkeypatch.delenv("POLIS_BASE_URL", raising=False)
    monkeypatch.delenv("POLIS_TOKEN", raising=False)
    assert polis_setup.main([]) == 2
    assert capsys.readouterr().out == ""


def test_main_exits_2_on_missing_seeds_file(env, tmp_path):
    assert polis_setup.main(["--seeds", str(tmp_path / "nope.json")]) == 2


@responses.activate
def test_main_exits_1_on_polis_error(env, tmp_path, capsys):
    path = write_seeds(tmp_path, valid_seed_data())
    mock_create(responses, status=500)
    assert polis_setup.main(["--seeds", str(path)]) == 1
    assert capsys.readouterr().out == ""


@responses.activate
def test_main_exits_1_on_network_error(env, tmp_path):
    path = write_seeds(tmp_path, valid_seed_data())
    responses.post(f"{API}/conversations", body=requests.ConnectionError("down"))
    assert polis_setup.main(["--seeds", str(path)]) == 1
