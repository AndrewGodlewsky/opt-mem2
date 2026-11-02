# OptMM shared repository memory

Approved direction: one immutable JSON file per memory, permanent UUID IDs,
shared through normal Git operations; local regenerable summaries. Python 3.10+
standard library only, Windows/macOS/Linux, no server, API key or Git hooks.

The repository's notes are authoritative. Sort by UTC creation time and ID.
A binary tree combines adjacent notes; fingerprints cover exact source content.
Cache summaries by fingerprint, never by mutable numeric position. Every command
loads the current note set. Summary submissions and paginated reads include a
snapshot fingerprint and refuse changed inputs. Forget removes only local cached
summaries and their dependents. AI-written summaries remain the coding agent's job.

Install with `python install.py TARGET`. Vendor runtime, launcher, shared config,
and managed AGENTS.md/CLAUDE.md blocks; preserve unrelated content and user edits.
Clone requires only Python; first use creates missing local cache automatically.
No automatic commits, pushes, hook installation, or changes to global settings.

Commands: init, wake, note, nap, recall, get, zoom, forget, config, status, check,
import, install. Migration accepts original OptMem LOG.txt and dated text notes.
Tests exercise the CLI, setup/upgrade, concurrency and real Git clone/merge flows.
