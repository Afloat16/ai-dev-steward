# Security model

## Intended use

Use StewardCheck in a repository and execution environment you control to make ordinary coding mistakes more visible. Its task contract records user intent; its receipt records observed changes and declared command results. It is not an adversarial containment boundary, cryptographic attestation, backup, or replacement for review and specialist scanning.

## Read-only inspection and explicit execution

`start`, `packet`, `check` without `--run`, and `report` do not execute declared project checks. They read the worktree and maintain local metadata. `doctor` reads prerequisites only. No command edits source, stages, stashes, resets, cleans, rewrites history, installs hooks, or uploads data on its own.

Inspection disables Git fsmonitor, external diff, text conversion, and configured clean/process filters used by the index comparison. A regression test verifies that a configured filter cannot create its marker during static inspection. This is defense in depth, not a promise that an arbitrary compromised Git binary or adversarial configuration is safe.

`check --run` executes user-declared argv as the current user, with the current environment, without a sandbox. Project tests can execute arbitrary code, access credentials, use the network, spawn processes, and modify files. Review executable paths, project code, and check configuration before enabling execution. Even a pinned argv can reference a changed script or interpreter. Dependency/configuration changes receive a review warning where recognized, not comprehensive dependency verification.

Shell operators are not interpreted by StewardCheck. An explicitly declared interpreter can still interpret its own program or shell commands. Windows `.cmd`/`.bat` entrypoints are refused to avoid implicit batch-shell behavior. POSIX cleanup targets the command process group; Windows cleanup does not guarantee termination of all descendants. Resource limits are safeguards against accidents, not OS-level resource isolation.

## Data and coverage limits

Only Git-discovered tracked and non-ignored untracked names, plus retained baseline names, are snapshotted. Ignored untracked files and Git-unlisted special files are not monitored. Nested repositories and submodule interiors are opaque. Binary/non-UTF-8 text and files over 256 KiB are hashed but not content-scanned. New opaque or oversized content requires review; resource ceilings fail rather than silently passing.

Snapshots are not filesystem transactions. Concurrent writes, edits followed by restoration between snapshots, hostile parent-directory replacement races, dependencies outside the repository, and test behavior influenced by ignored files or the environment cannot be fully detected. Stop concurrent writers when checking. Same-size edits are still hashed; per-file and Git-state consistency checks catch some, not all, races.

The credential detector uses a small set of independently written patterns and per-file baseline fingerprints. It can miss credentials, classify placeholders incorrectly, or ignore additional occurrences of an already-present value within the same file. Test-weakening warnings count textual markers, not executable test semantics. Treat findings as review evidence, never proof of safety or intent.

## Local state and disclosure

The state directory contains no source-file backup, but filenames, task text, derived metrics, exact check argv, and bounded redacted output may be sensitive. Never put secrets in argv. Heuristic redaction is not a guarantee: inspect packets and receipts before sharing. No telemetry or model network request is built in; declared checks may still communicate externally.

On POSIX, newly created state files use mode 0600 and the state directory uses 0700. Windows permissions follow the platform and parent directory's ACLs. Store/baseline hashes detect accidental damage or stale state; an attacker with the same write permissions can alter and rehash them. Symlinked state records/directories are refused, but same-user adversarial races are out of scope.

## Reporting

For non-sensitive bugs, open an issue in the parent repository with the StewardCheck version, OS, Git/Python versions, a minimized reproducer, and sanitized output. Do not post live credentials, private source, raw task records, or exploitable confidential details in a public issue. For a suspected sensitive vulnerability, first contact the maintainer through an available private channel or request a private reporting channel without publishing the exploit details. No response-time commitment or independent security audit is claimed.

## Configuration and record reads

Configuration is opt-in with `start --config`, never implicitly discovered. Review the argv and complete protection list before using it. CLI overrides replace configured lists rather than silently combining policies. Changing the file does not update an active contract. Configuration is not executable code, but commands it declares can execute code once explicitly approved with `check --run`.

State/config readers reject non-regular files before opening and bound actual reads. POSIX descriptors use nonblocking open so a FIFO substituted during opening cannot cause an indefinite blocking read. Metadata checks detect some concurrent replacements and edits, not all hostile filesystem races. Source scans use the same nonblocking-open precaution without changing the scan coverage limits.
