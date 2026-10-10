"""Guards for CI configuration that lives in pyproject.toml."""

import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _load() -> dict:
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)


def test_coverage_gate_is_at_least_80_percent():
    report = _load()["tool"]["coverage"]["report"]
    assert report["fail_under"] >= 80


def test_coverage_measures_integration_scripts():
    run = _load()["tool"]["coverage"]["run"]
    assert run["source"] == ["scripts"]
