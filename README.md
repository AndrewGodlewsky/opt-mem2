# OptMM

Shared project memory for coding agents. Original memories have permanent IDs and
live in separate files, so teammates can add notes on different branches and merge
them with normal Git workflows. Summaries are local, replaceable caches.

**Requires Python 3.10+ only.** No pip packages, database, server, API key, Git hook,
or global agent configuration. Your existing coding agent writes the summaries.

## Install into a project

Run **`install.py` once for each project repository** that should use shared memory.
On this machine, the installer is at:

```text
A:\Claude\opt-mem2\install.py
```

The argument is the **root directory of your existing project repository**: the
folder containing that project's `.git` entry. `A:\Claude\YourProject` below is an
example; replace it with your actual project path. Keep the entire OptMM source
folder together while installing. The installed project is self-contained afterward.

### 1. Run the installer

On Windows, run this in PowerShell from any directory. Confirm the version is
Python 3.10 or newer:

```powershell
python --version
python "A:\Claude\opt-mem2\install.py" "A:\Claude\YourProject"
```

If Windows provides Python through `py -3`, use that in place of `python` in these
commands. The target directory must already exist.

On Ubuntu or WSL, use Linux Python and replace these paths with the locations of
your OptMM checkout and target project:

```sh
python3 --version
python3 "/home/you/opt-mem2/install.py" "/home/you/your-project"
```

To use this machine's existing Windows source folder from WSL, if `A:` is mounted
at `/mnt/a`, the equivalent command is:

```sh
python3 "/mnt/a/Claude/opt-mem2/install.py" "/home/you/your-project"
```

For WSL, keeping the project in the Linux filesystem (for example, under `/home/you`)
improves file-access performance compared with a mounted Windows drive such as
`/mnt/c` or `/mnt/a`. See Microsoft's [WSL filesystem guidance](https://learn.microsoft.com/en-us/windows/wsl/filesystems).

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

### 2. Verify it inside your project

On Windows:

```powershell
cd "A:\Claude\YourProject"
python optmm.py check
python optmm.py wake
```

On Ubuntu or WSL:

```sh
cd "/home/you/your-project"
python3 optmm.py check
python3 optmm.py wake
```

`check` should report `OK`. A newly installed, empty store should say `No memories
yet.` and `You are awake.` If the project already has memories and requests `nap`
tasks, have your coding agent complete them and run `wake` again.

Start a new coding-agent session in the project so it reads the installed
`AGENTS.md` or `CLAUDE.md` instructions. Those instructions tell it to read memory,
record useful discoveries, and write requested summaries.

### 3. Commit the installation and share it

From the target project's root, review and commit the installed files:

```sh
git status --short
git add optmm.py .optmm .gitignore AGENTS.md CLAUDE.md
git diff --cached
git commit -m "Add shared project memory"
```

Share that commit through your normal push or pull-request workflow. The installer
does not commit or push for you. The generated `.gitignore` rules exclude the local
cache and temporary files.

### 4. Teammates clone or pull, then use memory

**After the setup commit is shared, teammates just clone/pull the project.** They do not need this
OptMM source checkout, pip, a setup command, environment variables, or Git config.
They need Python 3.10+ available to their coding agent. From their project root,
the agent runs `python optmm.py wake` (`python3 optmm.py wake` on Ubuntu/WSL);
the local cache is created on first use.
The installed launcher also works by absolute path from another working directory.

### Choose which agent instructions to install

By default both instruction files are updated. Choose a different integration with:

```sh
python install.py /path/to/project --instructions agents
python install.py /path/to/project --instructions claude
python install.py /path/to/project --instructions none
```

Run these examples from the OptMM source folder, or replace `install.py` with its
full path as above. If you choose fewer instruction files, include only the files
that were actually updated in the setup commit. With `--instructions none`, add
the memory workflow to your agent's own instructions yourself.

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
midnight timestamps with microsecond offsets for same-day ordering. Internal tabs
and Unicode separators are preserved; LF/CRLF delimit records. Original numbered
IDs are replaced with deterministic permanent IDs. The old file is never
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
