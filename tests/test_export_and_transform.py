"""Tests for scripts/export_and_transform.py.

Fixtures are real Pol.is exports of synthetic conversations
(tests/fixtures/polis_export/README.md). Expected values were computed by
hand from the fixture CSVs, independently of the implementation.
"""

import csv
import json
import shutil
from pathlib import Path

import pytest
import requests
import responses
from responses import matchers

from scripts import export_and_transform as et
from scripts.polis_client import PolisClient

FIXTURES = Path(__file__).parent / "fixtures" / "polis_export"
CLUSTERED = FIXTURES / "clustered"
NO_MATH = FIXTURES / "no_math"

BASE = "http://polis.test"
API = f"{BASE}/api/v3"
TOKEN = "test-token"
AUTH = matchers.header_matcher({"Authorization": f"Bearer {TOKEN}"})

# clustered/: 208 vote rows, one of them a changed vote, so 207 current votes
# from 30 voters on 8 statements. participant-votes.csv puts 12 voters in
# group 0 and 10 in group 1. From comment-groups.csv:
#   group a: sum|agrees - disagrees| = 59, sum(agrees + disagrees) = 77
#   group b: 54 / 68
EXPECTED_CLUSTERED = {
    "assembly_id": "testville",
    "participants": 30,
    "statements": 8,
    "votes": 207,
    "clusters": [
        {"id": 0, "size": 12, "consensus": round(59 / 77, 4)},
        {"id": 1, "size": 10, "consensus": round(54 / 68, 4)},
    ],
    "stories_collected": 0,
    "decisions": [],
}


@pytest.fixture
def export_dir(tmp_path):
    """A writable copy of the clustered fixture."""
    return Path(shutil.copytree(CLUSTERED, tmp_path / "export"))


def rewrite_csv(path, change):
    """Rewrite a CSV file: change(columns, rows) returns new (columns, rows)."""
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns, rows = list(reader.fieldnames), list(reader)
    columns, rows = change(columns, rows)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows({c: row.get(c, "") for c in columns} for row in rows)


# The acceptance test: fixture CSV from Pol.is -> JSON matching the schema


def test_clustered_export_matches_schema_and_expected_values():
    document = et.build_document(CLUSTERED, "testville")
    et.validate_document(document)
    assert document == EXPECTED_CLUSTERED


def test_export_before_math_has_no_clusters():
    document = et.build_document(NO_MATH, "testville")
    assert document == {
        **EXPECTED_CLUSTERED,
        "participants": 3,
        "votes": 6,
        "clusters": [],
    }


# transform rules


def test_vote_change_is_counted_once():
    rows = list(csv.DictReader((CLUSTERED / "votes.csv").open(encoding="utf-8")))
    assert len(rows) == 208
    assert et.build_document(CLUSTERED, "testville")["votes"] == 207


def test_rejected_statement_is_excluded_everywhere(export_dir):
    def reject_statement_6(columns, rows):
        for row in rows:
            if row["comment-id"] == "6":
                row["moderated"] = "-1"
        return columns, rows

    rewrite_csv(export_dir / "comments.csv", reject_statement_6)
    document = et.build_document(export_dir, "testville")

    # Statement 6 had 23 current votes; each group gave it 10 agrees, 0 disagrees.
    assert document["statements"] == 7
    assert document["votes"] == 207 - 23
    assert document["participants"] == 30
    assert document["clusters"] == [
        {"id": 0, "size": 12, "consensus": round((59 - 10) / (77 - 10), 4)},
        {"id": 1, "size": 10, "consensus": round((54 - 10) / (68 - 10), 4)},
    ]


def test_consensus_is_null_when_group_only_passed(export_dir):
    def only_passes_in_group_b(columns, rows):
        for row in rows:
            row["group-b-agrees"] = row["group-b-disagrees"] = "0"
        return columns, rows

    rewrite_csv(export_dir / "comment-groups.csv", only_passes_in_group_b)
    document = et.build_document(export_dir, "testville")
    assert document["clusters"][1] == {"id": 1, "size": 10, "consensus": None}


# export format checks


def test_missing_export_file(export_dir):
    (export_dir / "votes.csv").unlink()
    with pytest.raises(
        et.ExportFormatError, match="missing export file\\(s\\): votes.csv"
    ):
        et.read_export(export_dir)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ('{"format": "polis-export/2"}', "export format is 'polis-export/2'"),
        ("[]", "export format is None"),
        ("{not json", "format.json: not valid JSON"),
    ],
)
def test_unsupported_or_broken_format_declaration(export_dir, content, message):
    (export_dir / "format.json").write_text(content, encoding="utf-8")
    with pytest.raises(et.ExportFormatError, match=message):
        et.read_export(export_dir)


def test_missing_required_column(export_dir):
    rewrite_csv(
        export_dir / "votes.csv",
        lambda columns, rows: ([c for c in columns if c != "voter-id"], rows),
    )
    with pytest.raises(
        et.ExportFormatError, match="votes.csv: missing column\\(s\\): voter-id"
    ):
        et.read_export(export_dir)


def test_non_integer_value_names_file_row_and_column(export_dir):
    def corrupt(columns, rows):
        rows[2]["moderated"] = "yes"
        return columns, rows

    rewrite_csv(export_dir / "comments.csv", corrupt)
    with pytest.raises(
        et.ExportFormatError,
        match="comments.csv row 3: moderated is not an integer: 'yes'",
    ):
        et.build_document(export_dir, "testville")


def test_vote_row_without_voter(export_dir):
    def blank_voter(columns, rows):
        rows[0]["voter-id"] = ""
        return columns, rows

    rewrite_csv(export_dir / "votes.csv", blank_voter)
    with pytest.raises(et.ExportFormatError, match="votes.csv row 1: missing voter-id"):
        et.build_document(export_dir, "testville")


def test_groups_that_disagree_between_files(export_dir):
    rewrite_csv(
        export_dir / "comment-groups.csv",
        lambda columns, rows: (
            [c for c in columns if not c.startswith("group-b-")],
            rows,
        ),
    )
    with pytest.raises(et.ExportFormatError, match="different math runs"):
        et.build_document(export_dir, "testville")


def test_group_without_agree_column(export_dir):
    rewrite_csv(
        export_dir / "comment-groups.csv",
        lambda columns, rows: ([c for c in columns if c != "group-a-agrees"], rows),
    )
    with pytest.raises(et.ExportFormatError, match="missing column group-a-agrees"):
        et.build_document(export_dir, "testville")


# schema and assembly IDs


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda d: d.pop("votes"), "'votes' is a required property"),
        (lambda d: d.update(extra=1), "Additional properties"),
        (lambda d: d["clusters"][0].update(consensus=1.5), "clusters/0/consensus"),
        (lambda d: d.update(participants=-1), "participants"),
    ],
)
def test_validate_document_rejects_invalid_documents(change, message):
    document = json.loads(json.dumps(EXPECTED_CLUSTERED))
    change(document)
    with pytest.raises(ValueError, match=message):
        et.validate_document(document)


@pytest.mark.parametrize("assembly_id", ["a", "Testville-2026_q4", "x" * 100])
def test_valid_assembly_ids(assembly_id):
    assert et.validate_assembly_id(assembly_id) == assembly_id


@pytest.mark.parametrize(
    "assembly_id", ["", "-lead", "a/b", "../x", "a b", "x" * 101, None]
)
def test_invalid_assembly_ids(assembly_id):
    with pytest.raises(ValueError, match="invalid assembly ID"):
        et.validate_assembly_id(assembly_id)


# output


def test_write_output_creates_directory_and_replaces_file(tmp_path):
    out = tmp_path / "data" / "output"
    first = et.write_output(EXPECTED_CLUSTERED, out)
    second = et.write_output({**EXPECTED_CLUSTERED, "votes": 1}, out)

    assert first == second == out / "testville.json"
    assert json.loads(second.read_text(encoding="utf-8"))["votes"] == 1
    assert sorted(p.name for p in out.iterdir()) == ["testville.json"]


# pulling from the API


def mock_export_api(
    rsps, report_id="r1", source=CLUSTERED, conversation_id="2rmknavhzs"
):
    rsps.get(
        f"{API}/reports?conversation_id={conversation_id}",
        json=[{"report_id": report_id}],
        match=[AUTH],
    )
    for name in et.EXPORT_FILES:
        rsps.get(
            f"{API}/reportExport/{report_id}/{name}",
            body=(source / name).read_bytes(),
            match=[AUTH],
        )


@responses.activate(assert_all_requests_are_fired=True)
def test_pull_export_downloads_every_file(tmp_path):
    mock_export_api(responses)
    report_id = et.pull_export(PolisClient(BASE, TOKEN), "2rmknavhzs", tmp_path)

    assert report_id == "r1"
    for name in et.EXPORT_FILES:
        assert (tmp_path / name).read_bytes() == (CLUSTERED / name).read_bytes()


# command line


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("POLIS_BASE_URL", BASE)
    monkeypatch.setenv("POLIS_TOKEN", TOKEN)


def test_main_transforms_input_dir(tmp_path, capsys):
    args = ["--input-dir", str(CLUSTERED), "--assembly-id", "testville"]
    assert et.main([*args, "--output-dir", str(tmp_path)]) == 0

    out = capsys.readouterr().out
    assert out == f"{tmp_path / 'testville.json'}\n"
    assert json.loads((tmp_path / "testville.json").read_text()) == EXPECTED_CLUSTERED


def test_main_warns_when_there_are_no_clusters(tmp_path, caplog):
    args = ["--input-dir", str(NO_MATH), "--assembly-id", "early"]
    assert et.main([*args, "--output-dir", str(tmp_path)]) == 0
    assert "Pol.is math may not have run" in caplog.text


@responses.activate
def test_main_pulls_conversation(env, tmp_path, capsys):
    mock_export_api(responses)
    assert (
        et.main(["--conversation-id", "2rmknavhzs", "--output-dir", str(tmp_path)]) == 0
    )

    written = json.loads((tmp_path / "2rmknavhzs.json").read_text())
    assert written == {**EXPECTED_CLUSTERED, "assembly_id": "2rmknavhzs"}
    assert TOKEN not in capsys.readouterr().err


@pytest.mark.parametrize(
    "args",
    [
        ["--input-dir", str(CLUSTERED)],
        ["--input-dir", str(CLUSTERED), "--assembly-id", "../escape"],
        ["--input-dir", str(FIXTURES), "--assembly-id", "x"],
    ],
)
def test_main_exits_2_on_bad_arguments_or_files(args, tmp_path, capsys):
    assert et.main([*args, "--output-dir", str(tmp_path)]) == 2
    assert capsys.readouterr().out == ""
    assert list(tmp_path.iterdir()) == []


def test_main_exits_2_without_polis_config(monkeypatch, tmp_path):
    monkeypatch.delenv("POLIS_BASE_URL", raising=False)
    monkeypatch.delenv("POLIS_TOKEN", raising=False)
    assert et.main(["--conversation-id", "abc", "--output-dir", str(tmp_path)]) == 2


@responses.activate
def test_main_exits_1_on_polis_error(env, tmp_path, capsys):
    responses.get(f"{API}/reports?conversation_id=abc", json={"error": "x"}, status=403)
    assert et.main(["--conversation-id", "abc", "--output-dir", str(tmp_path)]) == 1
    assert capsys.readouterr().out == ""
    assert list(tmp_path.iterdir()) == []


@responses.activate
def test_main_exits_1_on_network_error(env, tmp_path):
    responses.get(
        f"{API}/reports?conversation_id=abc", body=requests.ConnectionError("down")
    )
    assert et.main(["--conversation-id", "abc", "--output-dir", str(tmp_path)]) == 1
