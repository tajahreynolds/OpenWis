# Importing Pol.is statements into NarraFirma

Audience: whoever sets up the NarraFirma project. Technical steps only; how
the stories are interpreted is human work (see `docs/HUMAN_TASKS.md`).

## 1. Make the files

    python -m scripts.storybridge --conversation-id <id>
    # or, from export files downloaded from the Pol.is report page:
    python -m scripts.storybridge --input-dir <dir> --assembly-id <name>

This writes two files to `data/output/`:

| File | Purpose |
|---|---|
| `<name>-story-form.csv` | Tells NarraFirma what each column holds |
| `<name>-stories.csv` | One story per Pol.is statement |

The stories file contains participant-written text. Keep it out of the repo
(`data/output/` is git-ignored) and handle it like any other participant data.

## 2. Import into NarraFirma

1. **Project options**: under "Project administration", set how CSV imports
   treat existing questions (NarraFirma refuses a story form import until
   this is chosen). Leave the CSV delimiter on comma.
2. **Collection > Design story forms**: "Import story form from CSV file",
   choose `<name>-story-form.csv`, and give the form a short name.
3. **Collection > Start story collection**: create a story collection that
   uses that form.
4. **Collection > Enter stories** (with the collection selected): "Import
   stories from CSV file", choose `<name>-stories.csv`. NarraFirma reports
   "Finished sending N stories from M participants".

## What the stories contain

| Column | Value |
|---|---|
| Participant ID | Pol.is participant number of the author (pseudonymous; groups a person's statements) |
| Eliciting question | `polis`, shown as "Pol.is statement", with the conversation topic as the question text |
| Story title | `Statement <Pol.is statement ID>` |
| Story text | Statement text |
| Collection date | Date the statement was written (UTC); if unknown, NarraFirma uses the import date |

Statements rejected by moderation, blank statements and malformed rows are
left out; the script logs each one and prints a count. The column names are
NarraFirma's defaults, so the stories file also imports into a form that was
not made from the story form file.

## Verified with NarraFirma 1.6.14

On 2026-10-10 both files were imported into NarraFirma
`pdfernhout/narrafirma@2b3a4aa198ef826c8a01eff402a7ab772a0cefe4` (v1.6.14,
Node.js server) in the agent container, through NarraFirma's own "Import
story form" and "Import stories" actions, driven by a headless browser:

| Input | NarraFirma reported | Read back |
|---|---|---|
| `tests/fixtures/polis_export/clustered` | 8 stories from 1 participant | all fields as in the table above |
| `tests/fixtures/polis_export/messy` | 5 stories from 4 participants | multi-line text, quotes, `é`, `☕`, a leading `;` and `=` kept exactly |

To repeat it: build NarraFirma (`npm run build`), set a superuser with
`node admin.js update-superuser superuser <password>`, create a project
journal (`add-journal NarraFirmaProject-<name>`), a user (`add-user <user>`,
password on stdin, one line) and grant it `administrator` on the journal,
restart `node NarraFirmaServer.js`, then follow section 2 at
`http://localhost:8080`. Page URLs use names without the `page_` prefix,
e.g. `narrafirma.html#project=<name>&page=designStoryForms`.

NarraFirma quirks seen at that version: `admin.js add-user <user> <password>`
ignores the password argument and prompts instead; the prompt reads all of
stdin as one password.
