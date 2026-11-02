# OptMM

Shared project memory for coding agents. Original memories have permanent IDs and
live in separate files, so teammates can add notes on different branches and merge
them with normal Git workflows. Summaries are local, replaceable caches.

**Requires Python 3.10+ only.** No pip packages, database, server, API key, Git hook,
or global agent configuration. Your existing coding agent writes the summaries.

## Install into a project

Clone this repository, then run this once for the project that should use memory:

```sh
python install.py /path/to/your-project
```

Windows example, from any directory:

```powershell
python "A:\Claude\opt-mem2\install.py" "A:\Claude\YourProject"
```

Use `python3` on systems where that is the Python 3 command, or `py -3` on Windows.
Check `python --version` first. The target directory must already exist.

The installer adds:

```text
your-project/
  optmm.py                      Portable entry point
  AGENTS.md                     Managed memory instructions, existing text preserved
  CLAUDE.md                     Same integration for Claude-compatible agents
  .gitignore                    Ignore rules for generated files
  .optmm/
    config.json                 Shared reading/output budgets
    install.json                Runtime checksums for safe upgrades
    README.md                   Store documentation
    runtime/optmm/              Vendored Python runtime
    notes/<permanent-id>.json   Shared original memories
    cache/                      Local summaries and locks; ignored by Git
```

Review and commit the setup in the target project:

```sh
git add optmm.py .optmm .gitignore AGENTS.md CLAUDE.md
git commit -m "Add shared project memory"
```

**After that commit, teammates just clone/pull the project.** They do not need this
OptMM source checkout, pip, a setup command, environment variables, or Git config.
Their agent runs `python optmm.py wake`; the local cache is created on first use.
The installed launcher also works by absolute path from another working directory.

By default both instruction files are updated. Choose a different integration with:

```sh
python install.py /path/to/project --instructions agents
python install.py /path/to/project --instructions claude
python install.py /path/to/project --instructions none
```

Existing text outside the marked OptMM blocks is preserved. The marked blocks
belong to the installer and are refreshed on upgrade; put team customizations
outside them. Malformed markers and conflicting or locally modified runtime files
cause installation to stop with an explanation instead of silently overwriting.
Runtime checksum checks tolerate Git's LF/CRLF line-ending conversions.

## Working with the team

1. Your agent reads memory at session start.
2. It records useful project discoveries with `note`.
3. It completes requested `nap` summaries while working.
4. Commit new `.optmm/notes/*.json` files with the related code or documentation.
5. Other developers receive the notes through normal Git synchronization.

Each note gets a UUID when created. Two developers adding notes produce different
files; they do not compete for a sequence number. Repeated merges do not create new
copies of an existing note. The tool never edits or deletes an original note.
Record corrections as new notes referencing the old permanent ID.

Git still governs which notes are visible: a branch switch or revert can remove a
note from the current checkout. OptMM does not pull other branches or restore notes
that Git intentionally removed. Hand-editing the same note on two branches can
still produce a Git conflict; resolve it explicitly.

Every command reads the current shared files. Summary fingerprints cover the exact
source notes and their tree grouping, so a cache from a different branch cannot be
silently applied to the wrong notes. Unchanged groups reuse their cached summaries.
Old caches remain available if you switch back. No merge hooks are necessary.

## Commands

Run these from an installed project's root:

| Command | Purpose |
| --- | --- |
| `python optmm.py wake` | Read a bounded view of the history, with more recent detail |
| `python optmm.py note "text"` | Save one immutable note, at most 280 UTF-8 bytes |
| `python optmm.py nap` | Show the next summarization task |
| `python optmm.py nap TOKEN "summary"` | Submit the agent's summary using the offered token |
| `python optmm.py recall "regex"` | Search all original notes, case-insensitively |
| `python optmm.py get ID` | Read an original note by permanent ID |
| `python optmm.py zoom SUMMARY_ID` | Expand a summary into its two halves |
| `python optmm.py forget SUMMARY_ID` | Invalidate a local summary and cached ancestors |
| `python optmm.py forget all` | Invalidate all local summaries; original notes remain |
| `python optmm.py status` | Show note count, snapshot and summary work remaining |
| `python optmm.py check` | Validate all source notes and configuration |
| `python optmm.py config` | Show reading/output settings |
| `python optmm.py import FILE` | Import original OptMem logs or dated text |

`status --json` and `nap --json` provide machine-readable output. Note references
start with `#`; summaries start with `@`. Full IDs or unambiguous prefixes of at
least eight characters are accepted by `get`, `zoom` and `forget`.

Output is paginated. Follow the printed `--page` and `--snapshot` command exactly.
A changed history, configuration or invalidation revision rejects an outdated
read or summary submission and asks the agent to restart. Commands exit with code
2 for an input/store error or when `wake` requires summary work first.

**`nap` does not call an AI API.** It prints the source material and asks the coding
agent to write a short summary. The agent submits it with the offered token. A
terminal without an agent will display that request and wait for you to act.
Notes are reference material, not executable instructions.

## Reading budget

The default is 96 memory lines. Old history is compressed into summaries; recent
notes get more detail. The original notes remain searchable regardless of budget.

```sh
python optmm.py config WAKE_LINES=48
python optmm.py config WAKE_LINES=
```

An empty value restores the default. Other settings are `ENTRY_BYTES` (maximum
280), `PART_BYTES` (minimum 1024), and `PART_LINES`. These settings are shared in
`.optmm/config.json`. The output budget applies to memory page contents; command
guidance and pending summary prompts add some output beyond that budget.

Summaries are local and are not pushed. A fresh clone may need substantial agent
work to summarize a large history. For N notes the current tree contains N-1
summary nodes. A budget change reuses available summaries; a merge only reuses
summaries whose source groups still match. There is no semantic search or automatic
resolution of contradictory facts. Verify remembered decisions against current code.

The tool scans note files when invoked. This design is intended for project/team
histories; it does not claim the original OptMem's million-record seek performance.
Timestamps provide a deterministic ordering together with IDs, not a guarantee of
causal ordering across computers with different clocks.

## Upgrade

Update this OptMM source checkout and rerun the same installer against the project.
It updates managed runtime files and instruction blocks, preserving notes and
configuration. Review and commit the resulting changes for teammates to receive.
It never changes your global Git settings or automatically commits/pushes.

Do not upgrade the runtime while another process is executing it. If a managed
file was customized, save/reconcile that customization before rerunning setup.

## Import an existing OptMem history

Initialize/install the destination first, then:

```sh
python optmm.py import /path/to/old/memory/LOG.txt
```

Accepted UTF-8 records are `#N YYYY-MM-DD text` (including original fixed-width
padding) or `YYYY-MM-DD text`. Dates and text are preserved; dates become UTC
midnight timestamps with microsecond offsets for same-day ordering. Original
numbered IDs are replaced with deterministic permanent IDs. The old file is never
changed. The entire input is validated before any note is published.

Reimporting the same records in the same order is idempotent, including resuming
after interruption. Two identical lines at different positions remain distinct.
Reordering or editing the import file can generate different IDs; use normal Git
synchronization for ongoing collaboration, not repeated exports/imports. Old
summaries are not imported because their numeric references are incompatible.

## Develop and test OptMM

There are no third-party dependencies:

```sh
python -B -m unittest discover -v
```

Tests use disposable local repositories and cover cloning, divergent branch merges,
branch switching, parallel writers, stale summaries/pages, migration and installation
safety. They use deterministic supplied summaries; they do not measure LLM quality.
CI is configured to run Python 3.10 and 3.12 on Windows, Linux and macOS using the official
[checkout](https://github.com/actions/checkout) and
[setup-python](https://github.com/actions/setup-python) actions.

To exercise the source checkout without installing into another project:

```sh
python memo.py --repo /path/to/scratch-project init
python memo.py --repo /path/to/scratch-project note "A useful discovery."
python memo.py --repo /path/to/scratch-project wake
```

OptMM is inspired by [OptMem](https://github.com/VictorTaelin/OptMem). Its shared
note format, repository installation and summary cache are designed for team Git
workflows; it is not a drop-in replacement for OptMem's on-disk format.
