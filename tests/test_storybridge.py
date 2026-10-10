"""Tests for scripts/storybridge.py.

The NarraFirma rules below are copied from NarraFirma 1.6.14
(webapp/source/csvImportExport.ts: processCSVContents and
processCSVContentsForQuestionnaire). Both output files were also imported
into a running NarraFirma 1.6.14; see docs/NARRAFIRMA_IMPORT.md.
"""

import csv
import io
import logging
import shutil
from pathlib import Path

import pytest
import requests
import responses
from responses import matchers

from scripts import storybridge as sb
from scripts.export_and_transform import ExportFormatError

FIXTURES = Path(__file__).parent / "fixtures" / "polis_export"
CLUSTERED = FIXTURES / "clustered"
NO_MATH = FIXTURES / "no_math"
MESSY = FIXTURES / "messy"

BASE = "http://polis.test"
API = f"{BASE}/api/v3"
TOKEN = "test-token"
AUTH = matchers.header_matcher({"Authorization": f"Bearer {TOKEN}"})

# NarraFirma spec ---------------------------------------------------------

FORM_REQUIRED_HEADERS = {"Short name", "Long name", "Type", "About", "Answers"}
IMPORT_TYPES = {
    "Participant ID column name",
    "Story text column name",
    "Story title column name",
    "Story collection date column name",
    "Language column name",
}


def narrafirma_rows(text):
    """Split CSV text the way NarraFirma's processCSVContents does.

    Empty rows and rows whose first cell starts with ';' are skipped. The
    header ends at its first empty cell, and a non-empty cell after that is
    an error.
    """
    header, rows = None, []
    for row in csv.reader(io.StringIO(text)):
        if not any(row) or row[0].strip().startswith(";"):
            continue
        if header is None:
            ended = False
            header = []
            for cell in row:
                if cell and ended:
                    raise AssertionError("header has an empty cell before its end")
                if cell:
                    header.append(cell)
                else:
                    ended = True
        else:
            rows.append(row)
    return header, rows


def narrafirma_form_items(text):
    """Read a story form CSV like processCSVContentsForQuestionnaire."""
    header, rows = narrafirma_rows(text)
    items = []
    for row in rows:
        item = {}
        for index, value in enumerate(row):
            name = header[min(index, len(header) - 1)]
            if index < len(header) - 1:
                item[name] = value.strip()
            elif value.strip():
                item.setdefault(name, []).append(value.strip())
        items.append(item)
    return header, items


def assert_narrafirma_compatible(form_text, stories_text, expected_stories):
    form_header, items = narrafirma_form_items(form_text)
    assert FORM_REQUIRED_HEADERS <= set(form_header)
    assert form_header[-1] == "Answers"

    declared = {}
    for item in items:
        if item["About"] == "import":
            assert item["Type"] in IMPORT_TYPES
            declared[item["Answers"][0]] = item["Type"]
        elif item["About"] == "eliciting":
            assert item["Type"] == "eliciting"
            declared[item["Data column name"]] = "eliciting"
            data_values = [answer.split("|")[0] for answer in item["Answers"]]
            assert sb.ELICITING_ANSWER in data_values
            assert all(len(answer.split("|")) == 3 for answer in item["Answers"])
        else:
            raise AssertionError(f"unexpected story form row: {item}")

    story_header, story_rows = narrafirma_rows(stories_text)
    assert len(set(story_header)) == len(story_header), "duplicate headers"
    assert set(story_header) == set(declared), "every column must be declared"
    # Every story survives NarraFirma's reader (none mistaken for a comment).
    assert len(story_rows) == expected_stories


# Fixture outputs ----------------------------------------------------------


def read_output(paths):
    form, stories = (p.read_text(encoding="utf-8") for p in paths)
    return form, stories, list(csv.DictReader(io.StringIO(stories)))


def test_clustered_export_produces_importable_files(tmp_path):
    stories = sb.build_stories(CLUSTERED)
    form, text, rows = read_output(sb.write_outputs(stories, "testville", tmp_path))

    assert_narrafirma_compatible(form, text, expected_stories=8)
    assert list(rows[0]) == list(sb.STORY_COLUMNS)
    assert [r["Story title"] for r in rows] == [f"Statement {i}" for i in range(8)]
    assert rows[0] == {
        "Participant ID": "0",
        "Eliciting question": "polis",
        "Story title": "Statement 0",
        "Story text": "The Testville library should open earlier on weekdays.",
        "Collection date": "2026-10-10",
    }
    assert stories.skipped == {}


def test_story_form_declares_default_columns_and_topic():
    rows = sb.story_form_rows("[SANDBOX] Testville library opening hours")
    assert rows[0] == list(sb.FORM_COLUMNS)
    assert rows[2][4] == "[SANDBOX] Testville library opening hours"
    assert rows[2][6] == (
        "polis|Pol.is statement|[SANDBOX] Testville library opening hours"
    )


def test_export_before_math_still_has_statements(tmp_path):
    stories = sb.build_stories(NO_MATH)
    assert len(stories.rows) == 8


def test_messy_comments_are_handled_gracefully(tmp_path, caplog):
    stories = sb.build_stories(MESSY)
    form, text, rows = read_output(sb.write_outputs(stories, "messy", tmp_path))

    assert_narrafirma_compatible(form, text, expected_stories=5)
    assert stories.skipped == {
        "blank text": 1,
        "malformed row": 1,
        "rejected by moderation": 1,
    }
    assert [(r["Participant ID"], r["Story title"]) for r in rows] == [
        ("0", "Statement 0"),
        ("3", "Statement 1"),
        ("4", "Statement 2"),
        ("7", "Statement 6"),
        ("3", "Statement 7"),
    ]
    by_title = {r["Story title"]: r for r in rows}
    assert by_title["Statement 1"]["Story text"] == (
        'Multi-line statement:\nsecond line, with "quotes" and commas, café ☕'
    )
    assert by_title["Statement 2"]["Story text"] == ";Starts with a semicolon"
    assert by_title["Statement 6"]["Collection date"] == ""
    assert "\x07" not in by_title["Statement 7"]["Story text"]
    assert "row 7: bad comment-id, author-id or moderated" in caplog.text
    assert "row 8: bad timestamp" in caplog.text
    # A pipe in the topic would split the eliciting answer.
    assert "Testville / " in form


# Text cleaning ------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        (None, ""),
        ("  \n ", ""),
        ("a\r\nb\rc", "a\nb\nc"),
        ("tab\there\x00\x1b[0m", "tab\there[0m"),
        ("  keep inner  spaces ", "keep inner  spaces"),
    ],
)
def test_clean_text(raw, clean):
    assert sb.clean_text(raw) == clean


# Export problems ----------------------------------------------------------


@pytest.fixture
def export_dir(tmp_path):
    return Path(shutil.copytree(CLUSTERED, tmp_path / "export"))


def test_missing_summary_file(export_dir):
    (export_dir / "summary.csv").unlink()
    with pytest.raises(
        ExportFormatError, match="missing export file\\(s\\): summary.csv"
    ):
        sb.build_stories(export_dir)


@pytest.mark.parametrize(
    "summary",
    ["url,http://x\n", 'topic,"   "\n', "topic\n"],
    ids=["absent", "blank", "short"],
)
def test_summary_without_topic(export_dir, summary):
    (export_dir / "summary.csv").write_text(summary, encoding="utf-8")
    with pytest.raises(ExportFormatError, match="no conversation topic"):
        sb.build_stories(export_dir)


def test_topic_is_put_on_one_line(export_dir):
    (export_dir / "summary.csv").write_text('topic,"Two\nlines"\n', encoding="utf-8")
    assert sb.build_stories(export_dir).topic == "Two lines"


def test_missing_comment_column(export_dir):
    path = export_dir / "comments.csv"
    path.write_text(
        path.read_text(encoding="utf-8").replace("author-id", "author"),
        encoding="utf-8",
    )
    with pytest.raises(
        ExportFormatError, match="comments.csv: missing column\\(s\\): author-id"
    ):
        sb.build_stories(export_dir)


def test_unsupported_export_format(export_dir):
    (export_dir / "format.json").write_text(
        '{"format": "polis-export/2"}', encoding="utf-8"
    )
    with pytest.raises(ExportFormatError, match="polis-export/2"):
        sb.build_stories(export_dir)


# Output files -------------------------------------------------------------


def test_write_outputs_names_and_encoding(tmp_path):
    out = tmp_path / "data" / "output"
    paths = sb.write_outputs(sb.build_stories(MESSY), "messy", out)

    assert [p.name for p in paths] == ["messy-story-form.csv", "messy-stories.csv"]
    assert sorted(p.name for p in out.iterdir()) == sorted(p.name for p in paths)
    for path in paths:
        data = path.read_bytes()
        assert b"\r\n" not in data
        assert not data.startswith(b"\xef\xbb\xbf")
        data.decode("utf-8")


# Command line -------------------------------------------------------------


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("POLIS_BASE_URL", BASE)
    monkeypatch.setenv("POLIS_TOKEN", TOKEN)


def test_main_reads_input_dir(tmp_path, capsys, caplog):
    caplog.set_level(logging.INFO)
    args = ["--input-dir", str(MESSY), "--assembly-id", "messy"]
    assert sb.main([*args, "--output-dir", str(tmp_path)]) == 0
    assert capsys.readouterr().out.splitlines() == [
        str(tmp_path / "messy-story-form.csv"),
        str(tmp_path / "messy-stories.csv"),
    ]
    assert (
        "5 stories written; skipped: 1 blank text, 1 malformed row, "
        "1 rejected by moderation" in caplog.text
    )


def test_main_warns_when_nothing_to_import(export_dir, tmp_path, caplog):
    path = export_dir / "comments.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns, rows = reader.fieldnames, list(reader)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows({**row, "moderated": "-1"} for row in rows)

    args = ["--input-dir", str(export_dir), "--assembly-id", "empty"]
    assert sb.main([*args, "--output-dir", str(tmp_path)]) == 0
    assert "No statements to import" in caplog.text


@responses.activate(assert_all_requests_are_fired=True)
def test_main_pulls_only_the_files_it_needs(env, tmp_path):
    responses.get(
        f"{API}/reports?conversation_id=2rmknavhzs",
        json=[{"report_id": "r1"}],
        match=[AUTH],
    )
    for name in sb.EXPORT_FILES:
        responses.get(
            f"{API}/reportExport/r1/{name}",
            body=(CLUSTERED / name).read_bytes(),
            match=[AUTH],
        )
    assert (
        sb.main(["--conversation-id", "2rmknavhzs", "--output-dir", str(tmp_path)]) == 0
    )
    assert (tmp_path / "2rmknavhzs-stories.csv").is_file()
    assert len(responses.calls) == 1 + len(sb.EXPORT_FILES)


@pytest.mark.parametrize(
    "args",
    [
        ["--input-dir", str(MESSY)],
        ["--input-dir", str(MESSY), "--assembly-id", "a/b"],
        ["--input-dir", str(FIXTURES), "--assembly-id", "x"],
    ],
)
def test_main_exits_2_on_bad_arguments_or_files(args, tmp_path, capsys):
    assert sb.main([*args, "--output-dir", str(tmp_path)]) == 2
    assert capsys.readouterr().out == ""
    assert list(tmp_path.iterdir()) == []


def test_main_exits_2_without_polis_config(monkeypatch, tmp_path):
    monkeypatch.delenv("POLIS_BASE_URL", raising=False)
    monkeypatch.delenv("POLIS_TOKEN", raising=False)
    assert sb.main(["--conversation-id", "abc", "--output-dir", str(tmp_path)]) == 2


@responses.activate
def test_main_exits_1_on_polis_error(env, tmp_path):
    responses.get(f"{API}/reports?conversation_id=abc", status=403, json={})
    assert sb.main(["--conversation-id", "abc", "--output-dir", str(tmp_path)]) == 1
    assert list(tmp_path.iterdir()) == []


@responses.activate
def test_main_exits_1_on_network_error(env, tmp_path):
    responses.get(
        f"{API}/reports?conversation_id=abc", body=requests.ConnectionError("down")
    )
    assert sb.main(["--conversation-id", "abc", "--output-dir", str(tmp_path)]) == 1
