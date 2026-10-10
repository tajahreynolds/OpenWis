"""Export a Pol.is conversation and transform it into canonical assembly JSON.

Pull the export from the Pol.is API (needs POLIS_BASE_URL and POLIS_TOKEN):

    python -m scripts.export_and_transform --conversation-id 2rmknavhzs

Or transform export files already downloaded from the Pol.is report page
("Raw Data Export"):

    python -m scripts.export_and_transform --input-dir DIR --assembly-id NAME

Writes ``data/output/{assembly_id}.json`` (schema:
``schemas/assembly.schema.json``) and prints its path on stdout. Progress and
errors go to stderr. The output holds counts only: no participant IDs and no
statement text. Downloaded export files live in a temporary directory that is
deleted on exit.

Exit codes: 0 success, 1 Pol.is request failed, 2 bad arguments,
configuration, export files or output.

Only Pol.is export format ``polis-export/1`` is accepted. Field definitions
are in ``docs/ARCHITECTURE.md`` (Data Schema) and DECISION-010.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import sys
import tempfile
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import jsonschema
import requests

from scripts.polis_client import PolisClient, PolisError, config_from_env

log = logging.getLogger("export_and_transform")

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "assembly.schema.json"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "output"

EXPORT_FORMAT = "polis-export/1"
EXPORT_FILES = (
    "format.json",
    "comments.csv",
    "votes.csv",
    "participant-votes.csv",
    "comment-groups.csv",
)
REQUIRED_COLUMNS = {
    "comments.csv": ("comment-id", "moderated"),
    "votes.csv": ("comment-id", "voter-id"),
    "participant-votes.csv": ("participant", "group-id"),
    "comment-groups.csv": ("comment-id",),
}
MODERATION_REJECTED = -1
ASSEMBLY_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")
GROUP_COLUMN_PATTERN = re.compile(r"^group-([a-z])-(?:votes|agrees|disagrees|passes)$")


class ExportFormatError(ValueError):
    """Export files are missing, malformed, inconsistent or in another format."""


@dataclass(frozen=True)
class Table:
    """One parsed CSV export file.

    Attributes:
        name: File name, used in error messages.
        columns: Header row.
        rows: Data rows keyed by column name.
    """

    name: str
    columns: tuple[str, ...]
    rows: tuple[dict[str, str], ...]

    def value(self, row_number: int, column: str) -> str:
        """Return a stripped cell value.

        Args:
            row_number: 1-based data row number.
            column: Column name.

        Returns:
            The cell text, or an empty string if the row is short.
        """
        return (self.rows[row_number - 1].get(column) or "").strip()

    def integer(self, row_number: int, column: str) -> int:
        """Return a cell value as an integer.

        Args:
            row_number: 1-based data row number.
            column: Column name.

        Returns:
            The parsed integer.

        Raises:
            ExportFormatError: If the cell is not an integer.
        """
        text = self.value(row_number, column)
        try:
            return int(text)
        except ValueError:
            raise ExportFormatError(
                f"{self.name} row {row_number}: {column} is not an integer: {text!r}"
            ) from None


def validate_assembly_id(assembly_id: str) -> str:
    """Check that an assembly ID is safe to use as a file name.

    Args:
        assembly_id: Proposed assembly ID.

    Returns:
        The same ID.

    Raises:
        ValueError: If it is not 1-100 letters, digits, ``-`` or ``_``,
            starting with a letter or digit.
    """
    if not ASSEMBLY_ID_PATTERN.match(assembly_id or ""):
        raise ValueError(
            f"invalid assembly ID {assembly_id!r}: use 1-100 letters, digits, "
            "'-' or '_', starting with a letter or digit"
        )
    return assembly_id


def read_export(directory: Path) -> dict[str, Table]:
    """Read and check the Pol.is export files in a directory.

    Args:
        directory: Directory holding the files named in ``EXPORT_FILES``.

    Returns:
        Parsed CSV files keyed by file name.

    Raises:
        ExportFormatError: If a file is missing, ``format.json`` does not
            declare ``polis-export/1``, or a required column is absent.
        OSError: If a file cannot be read.
    """
    directory = Path(directory)
    missing = [name for name in EXPORT_FILES if not (directory / name).is_file()]
    if missing:
        raise ExportFormatError(
            f"{directory}: missing export file(s): {', '.join(missing)}"
        )

    try:
        declared = json.loads((directory / "format.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ExportFormatError(f"format.json: not valid JSON ({exc})") from exc
    found = declared.get("format") if isinstance(declared, dict) else None
    if found != EXPORT_FORMAT:
        raise ExportFormatError(
            f"format.json: export format is {found!r}; "
            f"only {EXPORT_FORMAT!r} is supported"
        )

    tables = {}
    for name, required in REQUIRED_COLUMNS.items():
        with (directory / name).open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = tuple(reader.fieldnames or ())
            absent = [column for column in required if column not in columns]
            if absent:
                raise ExportFormatError(
                    f"{name}: missing column(s): {', '.join(absent)}"
                )
            tables[name] = Table(name, columns, tuple(reader))
    return tables


def transform(tables: dict[str, Table], assembly_id: str) -> dict:
    """Compute the canonical assembly document from parsed export files.

    Definitions (DECISION-010):

    - ``statements``: comments not rejected by moderation.
    - ``votes``: distinct (participant, statement) pairs in ``votes.csv`` on
      those statements, so a changed vote counts once; passes included.
    - ``participants``: distinct voters among those votes.
    - ``clusters``: Pol.is opinion groups, sized from ``participant-votes.csv``,
      with ``consensus`` from the group's counts in ``comment-groups.csv``.
    - ``stories_collected`` and ``decisions`` come from other integrations and
      are left at 0 and ``[]``.

    Args:
        tables: Output of ``read_export``.
        assembly_id: Assembly ID to record.

    Returns:
        The assembly document.

    Raises:
        ExportFormatError: If a value is malformed or the files disagree.
    """
    comments = tables["comments.csv"]
    statements = {
        comments.value(n, "comment-id")
        for n in range(1, len(comments.rows) + 1)
        if comments.integer(n, "moderated") != MODERATION_REJECTED
    }

    votes = tables["votes.csv"]
    pairs = set()
    for n in range(1, len(votes.rows) + 1):
        voter, statement = votes.value(n, "voter-id"), votes.value(n, "comment-id")
        if not voter or not statement:
            raise ExportFormatError(
                f"votes.csv row {n}: missing voter-id or comment-id"
            )
        if statement in statements:
            pairs.add((voter, statement))

    return {
        "assembly_id": assembly_id,
        "participants": len({voter for voter, _ in pairs}),
        "statements": len(statements),
        "votes": len(pairs),
        "clusters": _clusters(
            tables["participant-votes.csv"], tables["comment-groups.csv"], statements
        ),
        "stories_collected": 0,
        "decisions": [],
    }


def _clusters(participants: Table, groups: Table, statements: set[str]) -> list:
    sizes = Counter(
        participants.integer(n, "group-id")
        for n in range(1, len(participants.rows) + 1)
        if participants.value(n, "group-id")
    )
    letters = {
        ord(match.group(1)) - ord("a"): match.group(1)
        for column in groups.columns
        if (match := GROUP_COLUMN_PATTERN.match(column))
    }
    if set(sizes) != set(letters):
        raise ExportFormatError(
            f"participant-votes.csv has groups {sorted(sizes)} but "
            f"comment-groups.csv has groups {sorted(letters)}; the files may "
            "come from different math runs, so download them again"
        )

    clusters = []
    for group_id in sorted(sizes):
        agrees, disagrees = (
            f"group-{letters[group_id]}-agrees",
            f"group-{letters[group_id]}-disagrees",
        )
        for column in (agrees, disagrees):
            if column not in groups.columns:
                raise ExportFormatError(f"comment-groups.csv: missing column {column}")
        spread = total = 0
        for n in range(1, len(groups.rows) + 1):
            if groups.value(n, "comment-id") not in statements:
                continue
            a, d = groups.integer(n, agrees), groups.integer(n, disagrees)
            spread += abs(a - d)
            total += a + d
        clusters.append(
            {
                "id": group_id,
                "size": sizes[group_id],
                "consensus": round(spread / total, 4) if total else None,
            }
        )
    return clusters


def validate_document(document: dict) -> None:
    """Check a document against ``schemas/assembly.schema.json``.

    Args:
        document: Assembly document.

    Raises:
        ValueError: If the document does not match the schema.
    """
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(document, schema, cls=jsonschema.Draft202012Validator)
    except jsonschema.ValidationError as exc:
        location = "/".join(str(part) for part in exc.absolute_path) or "(root)"
        raise ValueError(
            f"output does not match schema at {location}: {exc.message}"
        ) from None


def build_document(directory: Path, assembly_id: str) -> dict:
    """Read export files, transform them and validate the result.

    Args:
        directory: Directory holding the export files.
        assembly_id: Assembly ID to record.

    Returns:
        The validated assembly document.

    Raises:
        ExportFormatError: If the export files are unusable.
        ValueError: If the result does not match the schema.
        OSError: If a file cannot be read.
    """
    document = transform(read_export(directory), assembly_id)
    validate_document(document)
    return document


def pull_export(client: PolisClient, conversation_id: str, directory: Path) -> str:
    """Download a conversation's export files into a directory.

    Args:
        client: Client authenticated as the conversation owner.
        conversation_id: Conversation to export.
        directory: Existing directory to write the files to.

    Returns:
        The report ID the files were exported from.

    Raises:
        PolisError: If a request fails.
        requests.RequestException: On network errors.
        OSError: If a file cannot be written.
    """
    report_id = client.get_report_id(conversation_id)
    for name in EXPORT_FILES:
        (Path(directory) / name).write_bytes(
            client.download_export_file(report_id, name)
        )
    return report_id


def write_output(document: dict, output_dir: Path) -> Path:
    """Write a document to ``{output_dir}/{assembly_id}.json``.

    The file is written to a temporary name and renamed, so readers never
    see a partial file.

    Args:
        document: Validated assembly document.
        output_dir: Directory to write to; created if missing.

    Returns:
        Path of the written file.

    Raises:
        OSError: If the file cannot be written.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{document['assembly_id']}.json"
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return path


def main(argv: Sequence[str] | None = None) -> int:
    """Run the export and transform from the command line.

    Args:
        argv: Command-line arguments, excluding the program name.

    Returns:
        Process exit code: 0 success, 1 Pol.is request failed, 2 bad
        arguments, configuration, export files or output.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--conversation-id", help="pull this conversation's export")
    source.add_argument(
        "--input-dir", type=Path, help="transform export files already downloaded"
    )
    parser.add_argument(
        "--assembly-id",
        help="assembly ID and output file name (default: the conversation ID)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="output directory (default: data/output)",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(message)s"
    )

    try:
        if args.input_dir and not args.assembly_id:
            raise ValueError("--assembly-id is required with --input-dir")
        assembly_id = validate_assembly_id(args.assembly_id or args.conversation_id)
        if args.input_dir:
            document = build_document(args.input_dir, assembly_id)
        else:
            base_url, token = config_from_env(os.environ)
            with tempfile.TemporaryDirectory(prefix="polis-export-") as tmp:
                try:
                    report_id = pull_export(
                        PolisClient(base_url, token), args.conversation_id, Path(tmp)
                    )
                except (PolisError, requests.RequestException) as exc:
                    log.error("%s", exc)
                    return 1
                log.info("Downloaded export of report %s", report_id)
                document = build_document(Path(tmp), assembly_id)
        path = write_output(document, args.output_dir)
    except (OSError, ValueError) as exc:
        log.error("%s", exc)
        return 2

    if not document["clusters"]:
        log.warning("No opinion groups in the export; Pol.is math may not have run")
    log.info(
        "Assembly %s: %d participants, %d statements, %d votes, %d clusters",
        assembly_id,
        document["participants"],
        document["statements"],
        document["votes"],
        len(document["clusters"]),
    )
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
