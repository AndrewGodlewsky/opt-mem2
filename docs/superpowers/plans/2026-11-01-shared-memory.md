# OptMM Shared Memory Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver a self-contained, Git-compatible agent memory tool with one-command repository setup.

**Architecture:** Immutable UUID note files are the shared source of truth. Local content-addressed summary caches are rebuilt on demand, with source snapshots guarding reads and submissions. An idempotent installer vendors the Python runtime and agent instructions.

**Tech Stack:** Python 3.10+ standard library, unittest, Git integration tests.

**Spec:** ../../design.md

## Global Constraints

- Python standard library only; Windows, macOS and Linux.
- No mandatory Git hooks, package installation, services or API credentials.
- Preserve raw note contents/IDs and existing repository instructions.
- Write in the new opt-mem2 repository; do not modify the original OptMem code.

## Review Focus

- Branch merges insert older notes: summary must never refer to changed content.
- Repeated install/upgrade: preserve notes, configuration and unrelated instructions.
- Interrupted/concurrent writes: publish complete files; unique permanent IDs.
- Snapshot changes during nap/paging: reject stale submissions and request restart.
- Invalid notes or conflicting JSON: stop clearly; never silently omit knowledge.

### Task 1: Shared notes and CLI

Files: optmm/store.py, optmm/cli.py, memo.py, tests/test_cli.py.
Interface: Store(root).initialize(), load(), add(text), configuration().
- [x] Write CLI test for initialization, immutable notes, validation and stable recall.
- [x] Observe failure, implement store and CLI, verify test.

### Task 2: Summaries and navigation

Files: optmm/memory.py, optmm/cli.py, tests/test_memory.py.
Interface: History(store) exposes snapshot, nodes, cover, pending and submit.
- [x] Write test for agent-supplied summaries, zoom, forget, stale snapshot and merge reuse.
- [x] Observe failure, implement content fingerprints and commands, verify tests.

### Task 3: Repository installation

Files: optmm/install.py, install.py, tests/test_install.py.
Interface: install(target, instruction_files) preserves existing content and vendors runtime.
- [x] Write test for one-command setup, repeated setup, user edits, clone and cross-directory execution.
- [x] Observe failure, implement installer and managed instructions, verify tests.

### Task 4: Migration and team workflows

Files: optmm/cli.py, tests/test_git.py, tests/test_migration.py, README.md, CI workflow.
- [x] Test old OptMem import, two-branch merge, branch switching, concurrency and malformed data.
- [x] Implement remaining behavior and validate complete suite.
- [x] Document setup, team workflow, cache costs and limitations.
- [x] Obtain independent review, fix verified issues, run final checks in destination.

## Execution record

User authorized implementation of this agreed design in opt-mem2. Proceed inline.
Temporary build directory is inside the permitted workspace; deliver and verify in
the explicitly named destination using approved filesystem access. Use the clean
existing destination checkout and a codex/ branch; no additional worktree needed.
Tests cover public CLI and installer boundaries; no extra user clarification needed.

Core implementation: 22 tests passed on native Windows / Python 3.12.13. Real Git
clone tests require unsandboxed local execution because MSYS named objects are
blocked in the sandbox. No network operations are part of the test suite.
Ruling: a cached in-memory index is sufficient; no generated LOG.txt file is needed.
This reduces stale mutable files while retaining binary summary navigation.

Independent review found two important issues: CRLF conversion rejected upgrades,
and unknown hidden note files were silently skipped. Both reproduced with failing
CLI tests before fixes. Managed instruction blocks are explicitly installer-owned;
customizations outside those blocks remain byte-preserved. Full verification follows.

Final verification: 25/25 tests passed in the destination on Windows / Python
3.12.13. A separate installed-copy walkthrough passed on Python 3.14.7. Runtime
files parse under Python 3.10 grammar. Linux/macOS and Python 3.10 execution are
configured in CI but were not run locally. Independent review findings were fixed
with RED-to-GREEN tests; no outstanding review findings remain.
