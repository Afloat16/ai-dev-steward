# Architecture and receipt semantics

StewardCheck keeps the enforcement path deterministic and local. It does not ask a model to judge its own changes.

## Data flow

```text
start:  explicit task + argv -> read Git paths -> hash actual files -> local baseline
packet: baseline + current text -> scope/context selection -> redaction -> bounded stdout
check:  baseline + current snapshot -> static findings -> optional declared commands
        -> second snapshot -> verdict + receipt
report: saved receipt + current fingerprint -> fresh or stale -> stdout
```

`repository.py` owns Git discovery and bounded file reads. `core.py` defines task contracts, delta rules, and verdicts. `runner.py` handles opt-in execution. `secrets.py` contains independently implemented heuristic patterns. `storage.py` owns the worktree-local record and lock. `render.py` formats portable output. `cli.py` provides the public command surface.

## Baseline rather than a shadow checkout

The baseline contains file identities and derived metadata, not source copies. An already modified or untracked file at `start` is existing work; only later identity changes contribute to the task delta. No commit is required, so an unborn Git repository works. Deleted files remain attributable because their baseline names and hashes survive. Renames are represented as a deletion and an addition, not guessed semantic identity.

Git discovery uses `ls-files --stage -z` and `ls-files --others --exclude-standard -z`. NUL separators preserve ordinary whitespace and newline-containing names. Backslash paths, parent traversal, and `.git` path components are refused. Known baseline names remain in subsequent scans even if an ignore rule changes. New ignored untracked files are not discovered. Unmerged index stages are an operational error.

The fingerprint covers the file map, index entries, and HEAD. File identities include SHA-256, byte size, executable permission bits, and file kind. Every selected regular file is streamed and hashed; only UTF-8, NUL-free files at most 256 KiB receive text heuristics. The path and aggregate byte limits fail closed. Symlink contents are not followed. Submodule or nested repository interiors are opaque and explicitly require review when represented in the path inventory.

## Verification, not approval

A static error blocks command execution. Otherwise `check --run` executes only the stored argv, from the repository root, without a shell. A second snapshot detects persistent monitored changes made during checks. A nonzero check, timeout, over-limit output, or changed workspace blocks the receipt. Warnings produce `needs-review`; missing commands, skipped execution, and zero task changes also cannot pass.

A passing receipt means the declared commands returned zero against an unchanged monitored snapshot and no implemented rule demanded review. It says nothing about test adequacy, unmonitored data, or whether acceptance criteria are satisfied. Check results describe the working tree, not necessarily what a partially staged commit would contain. Index changes during a task that still differ from the worktree get a review warning.

`report` recomputes the fingerprint and downgrades stale evidence. It does not automatically rerun commands. A later `check` replaces the previous receipt; `start --replace` deliberately replaces the task and its baseline. Schema version 1 is provisional; there is no migration or historical-task store in 0.1.0.

## Storage and command output

`<absolute-git-dir>/stewardcheck/active.json` contains one task record. A create-exclusive lock serializes this tool's writers; a temporary file, fsync, and replace keep normal writes atomic. Linked worktrees naturally receive separate stores. The lock is not automatically broken after a timeout. After a crash, first confirm no operation is running, then remove only the stale lock.

The contract and baseline are hashed for consistency; the receipt has its own digest. These detect accidental corruption, not a same-user attacker who can recompute all hashes. Task text and acceptance criteria are redacted; exact argv is retained for reproducible execution, so never put secrets in command arguments. Paths and derived metrics may themselves be sensitive.

Check output retains at most 32 KiB before redaction. A command producing more than 8 MiB is terminated; truncated trailing lines are dropped rather than exposing a partial token. The output hash describes captured stream bytes, not an authenticated log. Timeouts and interrupted operations need a fresh check. POSIX process groups are terminated; Windows descendant cleanup is best effort.

## Context budgets

Packets include complete eligible files, ranked first by task changes, then task words in paths, test paths, and lexical order. `--include` adds context paths to the normal task scope but never changes edit permissions. The budget includes headings, fences, and coverage notes. Dynamic fences keep literal backticks inside file excerpts. Controls are escaped for terminal display. This is simple ranking, not an AST, import graph, tokenizer, or proof against prompt injection.

See [SECURITY.md](../SECURITY.md) for assumptions and excluded threat classes, and [research.md](research.md) for the external references behind the design choices.

## Explicit configuration and IO in 0.2.0

`config.load_config` reads a bounded, ordinary UTF-8 TOML file only when `start --config` is used. Schema and field validation happen before CLI overrides. Configuration is flattened into the existing contract, so check/report never reread or execute a configuration file. No configuration fingerprint is used as a substitute for the pinned resolved policy.

`files.read_bounded` validates file type before open, bounds the actual read, and compares device/inode, mode, size and timestamps around the read. POSIX nonblocking open prevents a substituted FIFO from blocking before descriptor validation. State and config share this primitive; source-file scanning retains streaming hashing and also uses nonblocking open. These checks do not provide protection against every concurrently changing parent directory or malicious process.

`snapshot(..., collect_text=False)` returns identical file metadata and fingerprints but an empty text map. Start, check (including its after-check scan), and report use it. Packet keeps text collection enabled. Every file is still hashed and eligible text still scanned; this optimization does not introduce an mtime cache or reduce coverage.

Pathname and descriptor queries are compared within their own API for complete metadata stability. Cross-API comparisons use device/inode, file type, size, and modification time, not permission bits or `ctime`, whose Windows representations can differ. The returned byte count must also match the opened file size. This avoids rejecting an unchanged Windows file without discarding mutation checks.
