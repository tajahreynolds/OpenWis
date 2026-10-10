"""Live check of scripts/polis_setup.py against a running Pol.is (opt-in).

Skipped unless POLIS_LIVE_TESTS=1, so CI and ordinary runs never create
conversations. Point POLIS_BASE_URL and POLIS_TOKEN at a sandbox instance
(docs/POLIS_SANDBOX.md), never a production one.
"""

import os

import pytest
import requests

from scripts import polis_setup

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("POLIS_LIVE_TESTS") != "1",
        reason="set POLIS_LIVE_TESTS=1 to run against a sandbox Pol.is",
    ),
]


def test_setup_conversation_against_live_polis():
    base_url, token = polis_setup.config_from_env(os.environ)
    seeds = polis_setup.load_seeds(polis_setup.DEFAULT_SEEDS_PATH)

    conversation_id = polis_setup.setup_conversation(
        polis_setup.PolisClient(base_url, token), seeds
    )

    api = base_url.rstrip("/") + "/api/v3"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"conversation_id": conversation_id}

    conversation = requests.get(
        f"{api}/conversations", params=params, headers=headers, timeout=30
    )
    conversation.raise_for_status()
    assert conversation.json()["is_active"] is True
    assert conversation.json()["topic"] == seeds.topic

    comments = requests.get(
        f"{api}/comments", params=params, headers=headers, timeout=30
    )
    comments.raise_for_status()
    by_text = {c["txt"]: c for c in comments.json()}
    assert set(by_text) == set(seeds.statements)
    assert all(c["is_seed"] for c in by_text.values())
