"""Guards for line endings and encoding of tracked text files (DECISION-007)."""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BOM = b"\xef\xbb\xbf"


def _tracked_text_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
    ).stdout
    files = []
    for name in out.decode().split("\0"):
        path = ROOT / name
        if name and path.is_file() and b"\0" not in path.read_bytes():
            files.append(path)
    return files


TEXT_FILES = _tracked_text_files()


def test_tracked_text_files_found():
    assert TEXT_FILES


@pytest.mark.parametrize("path", TEXT_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_lf_line_endings_and_no_bom(path):
    data = path.read_bytes()
    assert b"\r\n" not in data, "CRLF line endings"
    assert not data.startswith(BOM), "UTF-8 byte-order mark"
