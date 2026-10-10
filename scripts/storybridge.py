"""Turn Pol.is statements into a NarraFirma story import.

Pull the export from the Pol.is API (needs POLIS_BASE_URL and POLIS_TOKEN):

    python -m scripts.storybridge --conversation-id 2rmknavhzs

Or read export files already downloaded from the Pol.is report page:

    python -m scripts.storybridge --input-dir DIR --assembly-id NAME

Writes two CSV files to ``data/output/`` and prints their paths on stdout:

- ``{assembly_id}-story-form.csv``: describes the columns to NarraFirma
  (Collection > Design story forms > "Import story form from CSV file").
- ``{assembly_id}-stories.csv``: one row per statement, imported into a story
  collection that uses that form.

Each statement that was not rejected by moderation becomes one story. Blank
statements and malformed rows are skipped with a warning; a missing file,
column or unsupported export format is an error. The stories file contains
participant-written text, so it stays in the git-ignored output directory.

Exit codes: 0 success, 1 Pol.is request failed, 2 bad arguments,
configuration or export files.

Format details: docs/ARCHITECTURE.md ("Pol.is → NarraFirma"), DECISION-013.
"""

from __future__ import annotations

import argparse
import csv
import io
import logging
import os
import re
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import requests

from scripts.export_and_transform import (
    DEFAULT_OUTPUT_DIR,
    MODERATION_REJECTED,
    ExportFormatError,
    check_export_format,
    pull_export,
    read_table,
    validate_assembly_id,
)
from scripts.polis_client import PolisClient, PolisError, config_from_env

log = logging.getLogger("storybridge")

EXPORT_FILES = ("format.json", "summary.csv", "comments.csv")
COMMENT_COLUMNS = ("timestamp", "comment-id", "author-id", "moderated", "comment-body")

# Column names NarraFirma uses by default when a story form does not override
# them (csvImportExport.ts, processCSVContentsForQuestionnaire). Using them
# keeps the stories file importable even without the story form file.
PARTICIPANT_ID = "Participant ID"
ELICITING_QUESTION = "Eliciting question"
STORY_TITLE = "Story title"
STORY_TEXT = "Story text"
COLLECTION_DATE = "Collection date"
STORY_COLUMNS = (
    PARTICIPANT_ID,
    ELICITING_QUESTION,
    STORY_TITLE,
    STORY_TEXT,
    COLLECTION_DATE,
)
# Header of a NarraFirma story form CSV. Answers must be last: the importer
# gathers every cell from the last header onward into a list.
FORM_COLUMNS = (
    "Data column name",
    "Type",
    "About",
    "Short name",
    "Long name",
    "Options",
    "Answers",
)
ELICITING_ANSWER = "polis"

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


@dataclass
class Stories:
    """Stories converted from Pol.is statements.

    Attributes:
        topic: Conversation topic, used as the eliciting question.
        rows: Story rows keyed by NarraFirma column name.
        skipped: Count of skipped statements per reason.
    """

    topic: str
    rows: list[dict[str, str]] = field(default_factory=list)
    skipped: dict[str, int] = field(default_factory=dict)

    def skip(self, reason: str) -> None:
        """Count one skipped statement.

        Args:
            reason: Why it was skipped.
        """
        self.skipped[reason] = self.skipped.get(reason, 0) + 1


def clean_text(text: str | None) -> str:
    """Normalise statement text for CSV import.

    Windows and old Mac line endings become newlines, control characters
    other than newline and tab are removed, and surrounding whitespace is
    stripped.

    Args:
        text: Raw text, or None for a missing cell.

    Returns:
        Cleaned text; empty if nothing printable is left.
    """
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    return _CONTROL_CHARACTERS.sub("", text).strip()


def read_topic(directory: Path) -> str:
    """Read the conversation topic from ``summary.csv``.

    ``summary.csv`` holds key/value rows with no header.

    Args:
        directory: Directory holding the export files.

    Returns:
        The topic, cleaned and on one line.

    Raises:
        ExportFormatError: If there is no non-blank ``topic`` row.
        OSError: If the file cannot be read.
    """
    with (Path(directory) / "summary.csv").open(encoding="utf-8", newline="") as fh:
        for row in csv.reader(fh):
            if len(row) >= 2 and row[0].strip() == "topic":
                topic = " ".join(clean_text(row[1]).split())
                if topic:
                    return topic
    raise ExportFormatError("summary.csv: no conversation topic")


def build_stories(directory: Path) -> Stories:
    """Convert the statements in a Pol.is export into story rows.

    Statements rejected by moderation are left out. Rows with a missing or
    non-integer ``comment-id``, ``author-id`` or ``moderated``, and statements
    with no text, are skipped and counted. A bad timestamp leaves the date
    blank.

    Args:
        directory: Directory holding ``format.json``, ``summary.csv`` and
            ``comments.csv``.

    Returns:
        The stories, ordered by statement ID.

    Raises:
        ExportFormatError: If a file or column is missing, or the export
            format is not ``polis-export/1``.
        OSError: If a file cannot be read.
    """
    check_export_format(directory, EXPORT_FILES)
    comments = read_table(directory, "comments.csv", COMMENT_COLUMNS)
    stories = Stories(topic=read_topic(directory))

    rows = []
    for n in range(1, len(comments.rows) + 1):
        try:
            statement_id = int(comments.value(n, "comment-id"))
            author_id = int(comments.value(n, "author-id"))
            moderated = int(comments.value(n, "moderated"))
        except ValueError:
            log.warning(
                "comments.csv row %d: bad comment-id, author-id or moderated; skipped",
                n,
            )
            stories.skip("malformed row")
            continue
        if moderated == MODERATION_REJECTED:
            stories.skip("rejected by moderation")
            continue
        text = clean_text(comments.rows[n - 1].get("comment-body"))
        if not text:
            log.warning(
                "comments.csv row %d: statement %d is blank; skipped", n, statement_id
            )
            stories.skip("blank text")
            continue
        rows.append(
            (
                statement_id,
                {
                    PARTICIPANT_ID: str(author_id),
                    ELICITING_QUESTION: ELICITING_ANSWER,
                    STORY_TITLE: f"Statement {statement_id}",
                    STORY_TEXT: text,
                    COLLECTION_DATE: _iso_date(comments.value(n, "timestamp"), n),
                },
            )
        )
    stories.rows = [row for _, row in sorted(rows, key=lambda item: item[0])]
    return stories


def _iso_date(timestamp: str, row_number: int) -> str:
    try:
        return datetime.fromtimestamp(int(timestamp), tz=UTC).date().isoformat()
    except (ValueError, OverflowError, OSError):
        log.warning("comments.csv row %d: bad timestamp; date left blank", row_number)
        return ""


def story_form_rows(topic: str) -> list[list[str]]:
    """Build the NarraFirma story form describing the stories file.

    Args:
        topic: Conversation topic, used as the eliciting question text.

    Returns:
        Rows for the story form CSV, header first.
    """
    # The eliciting answer is "data value|graph label|question text"; a pipe in
    # the topic would split it.
    question = topic.replace("|", "/")
    return [
        list(FORM_COLUMNS),
        ["", "Participant ID column name", "import", "", "", "", PARTICIPANT_ID],
        [
            ELICITING_QUESTION,
            "eliciting",
            "eliciting",
            ELICITING_QUESTION,
            question,
            "",
            f"{ELICITING_ANSWER}|Pol.is statement|{question}",
        ],
        ["", "Story text column name", "import", "", "", "", STORY_TEXT],
        ["", "Story title column name", "import", "", "", "", STORY_TITLE],
        [
            "",
            "Story collection date column name",
            "import",
            "",
            "",
            "",
            COLLECTION_DATE,
        ],
    ]


def to_csv(rows: Sequence[Sequence[str]]) -> str:
    """Serialise rows as CSV (comma-delimited, LF line endings).

    Args:
        rows: Rows of cell values.

    Returns:
        CSV text.
    """
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    return buffer.getvalue()


def write_outputs(stories: Stories, assembly_id: str, output_dir: Path) -> list[Path]:
    """Write the story form and stories CSV files.

    Each file is written to a temporary name and renamed into place.

    Args:
        stories: Converted stories.
        assembly_id: Used to name the files.
        output_dir: Directory to write to; created if missing.

    Returns:
        Paths of the story form file and the stories file.

    Raises:
        OSError: If a file cannot be written.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    contents = {
        f"{assembly_id}-story-form.csv": to_csv(story_form_rows(stories.topic)),
        f"{assembly_id}-stories.csv": to_csv(
            [list(STORY_COLUMNS)]
            + [[row[c] for c in STORY_COLUMNS] for row in stories.rows]
        ),
    }
    paths = []
    for name, text in contents.items():
        path = output_dir / name
        temporary = path.with_name(f".{name}.tmp")
        temporary.write_text(text, encoding="utf-8", newline="")
        os.replace(temporary, path)
        paths.append(path)
    return paths


def main(argv: Sequence[str] | None = None) -> int:
    """Run the conversion from the command line.

    Args:
        argv: Command-line arguments, excluding the program name.

    Returns:
        Process exit code: 0 success, 1 Pol.is request failed, 2 bad
        arguments, configuration or export files.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--conversation-id", help="pull this conversation's export")
    source.add_argument(
        "--input-dir", type=Path, help="read export files already downloaded"
    )
    parser.add_argument(
        "--assembly-id",
        help="names the output files (default: the conversation ID)",
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
            stories = build_stories(args.input_dir)
        else:
            base_url, token = config_from_env(os.environ)
            with tempfile.TemporaryDirectory(prefix="polis-export-") as tmp:
                try:
                    pull_export(
                        PolisClient(base_url, token),
                        args.conversation_id,
                        Path(tmp),
                        EXPORT_FILES,
                    )
                except (PolisError, requests.RequestException) as exc:
                    log.error("%s", exc)
                    return 1
                stories = build_stories(Path(tmp))
        paths = write_outputs(stories, assembly_id, args.output_dir)
    except (OSError, ValueError) as exc:
        log.error("%s", exc)
        return 2

    skipped = ", ".join(f"{n} {why}" for why, n in sorted(stories.skipped.items()))
    log.info("%d stories written; skipped: %s", len(stories.rows), skipped or "none")
    if not stories.rows:
        log.warning("No statements to import")
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
