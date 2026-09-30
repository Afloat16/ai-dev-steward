# StewardCheck

**Keep the coding flow. Check the change.**

**English** | [简体中文](README.zh-CN.md)

StewardCheck is a small, local CLI for LLM coding and vibecoding workflows. Capture a task's starting point, give your coding assistant a bounded context packet, and get a reviewable receipt of what changed and which checks actually ran.

It complements your existing editor or coding agent. There is no model account, API key, server, runtime Python dependency, or automatic source editing.

**0.1.0 · Alpha · Python 3.11+ · Git · MIT**

## Why use it?

A successful test command is not the whole story. Was an unrelated file changed? Were existing tests weakened? Does the test result still describe the files on disk? Did the task start with your own uncommitted work?

StewardCheck connects those questions to one explicit task contract and one local receipt:

| Need | Behavior |
| --- | --- |
| Keep changes focused | Allowed path globs, protected paths, and a changed-file budget. |
| Preserve existing work | Compare with the actual task-start working tree, including dirty and non-ignored untracked files—not only `HEAD`. No automatic rollback. |
| Share useful context | Whole-file Markdown packet with a strict byte budget, sensitive-path exclusion, and heuristic redaction. |
| Make checks accountable | Execute only the argv declared at task start, and only with `check --run`. Bind results to workspace, index, and HEAD fingerprints. |
| Avoid stale confidence | Detect changes during checks and after a receipt. Missing checks and review warnings do not produce a green verdict. |
| Catch common review hazards | Newly detected credential patterns, deleted tests, fewer assertion markers, additional skip markers, and partial staging. |

This is a **working-tree task review**, not a staged-only commit gate, semantic code reviewer, sandbox, backup system, or security certification.

## Install

With [pipx](https://pipx.pypa.io/stable/), install the package from this repository:

```sh
pipx install "git+https://github.com/Afloat16/ai-dev-steward.git#subdirectory=tools/stewardcheck"
stewardcheck --version
```

Alternatively, clone the repository and install `tools/stewardcheck` with `python -m pip install ./tools/stewardcheck` inside an activated virtual environment. This package is independent of the parent repository's agent skill. The documented installation uses Git; no PyPI publication is assumed.

## A small workflow

Run from the Git repository you want to work on. This example assumes a Python project using `unittest`; choose your project's real test command.

```sh
stewardcheck start "Fix empty-input handling" \
  --scope "src/**" --scope "tests/**" \
  --check "python -m unittest discover -s tests" \
  --accept "Empty input returns an empty result without changing existing behavior"

stewardcheck packet
```

Review the packet, then paste it into your coding assistant. Ask it to implement the task within the declared scope. The packet is printed locally; StewardCheck never sends it to a model.

After reviewing the edits and the declared command:

```sh
stewardcheck check --run
stewardcheck report --format json
```

A passing check means the declared commands exited successfully and no implemented rule requires review. It does **not** mean the human acceptance criteria were proven. Those remain explicitly unchecked in the receipt.

For an entirely self-contained demonstration after cloning and installing:

```sh
python tools/stewardcheck/examples/demo.py
```

The demo uses a temporary Git repository and real subprocess checks. It demonstrates a passing fix, a stale receipt, and an out-of-scope blocker without modifying your current project.

## Commands

| Command | Purpose |
| --- | --- |
| `start "task"` | Capture the task contract and actual working-tree baseline. |
| `packet` | Print a bounded context packet. Default maximum: 32,000 UTF-8 bytes. |
| `check` | Inspect the task delta without running declared commands. |
| `check --run` | Inspect the delta and explicitly execute the pinned checks when there are no static blockers. |
| `report` | Print the latest receipt and detect whether it is stale; never rerun commands. |
| `doctor` | Inspect prerequisites and suggest possible check commands without executing them. |

Every subcommand accepts `--root PATH`. `check` and `report` accept `--format markdown` or `--format json`.

### Scope and context are different

`--scope` is repeatable and controls which files may change. Without it, scope is `**` and the receipt explicitly notes that paths are unrestricted. Globs are relative to the repository root and case-sensitive: `*` stays within one path segment; `**` crosses directories and may match zero segments. Negative patterns and absolute paths are not supported.

`packet --include "docs/**"` adds read-only context without expanding the allowed edit scope. `--max-bytes` changes the packet budget; this is a byte limit, **not a model-specific token estimate**. Whole files that do not fit are omitted rather than silently cut in half. Inspect the packet before sharing it, especially outside your organization. Keep any redirected packet or receipt outside the repository being checked, otherwise that new output file can itself become a task change.

### Checks are explicit programs, not shell snippets

Repeat `--check` for multiple commands. Its quoting is POSIX-style on every platform; pipes, redirection, and standalone shell operators are rejected. For exact or Windows-specific arguments, use an argv array:

```sh
stewardcheck start "Fix parsing" --scope "src/**" \
  --check-json '["python", "-m", "pytest", "-q"]'
```

Adapt outer quoting to your shell. Checks run from the repository root as your current user, inherit your environment, and are **not sandboxed**. They can execute project code, access credentials, change files, and use the network. Do not run untrusted checks. Do not put credentials in argv: the exact command contract is stored locally. On Windows, direct `.bat`/`.cmd` execution is refused; invoke a trusted interpreter and its script explicitly instead. For example, use `node` with the reviewed JavaScript test runner rather than `npm.cmd`.

The default timeout is 120 seconds per command; set `--timeout` at task start. Command output is redacted heuristically and bounded; over-limit or timed-out commands cannot pass. A formatter or test that changes monitored content invalidates the checked state: review the change, then rerun.

### Protection and task lifecycle

Default protected paths include environment files, PEM/key files, SSH private-key filenames, `.netrc`, Git ignore/attribute rules, `.gitmodules`, and `.github/workflows/**`. A task needing to modify one of these requires an explicit policy choice. **Supplying `--protect` replaces the default protected list**; it is not additive. Review the complete replacement list carefully.

`--max-files` defaults to 20. Snapshots hash at most 256 MiB by default (`--scan-mib`), with a hard 20,000-path ceiling. UTF-8 text scanning is limited to 256 KiB per file; changed binary, oversized, or linked content requires separate review. Exceeding a resource limit is an operational error, not a pass.

There is one active task per Git working tree. Use `start ... --replace` only when deliberately discarding the previous baseline and receipt. There is no automatic task history or recovery copy. Normal and linked Git worktrees use their own Git metadata directory.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Passed: declared checks ran successfully, no blocking or review-level findings. |
| `1` | Blocked: policy violation, failed check, or changed state during checks. |
| `2` | Needs review: missing/unrun checks, heuristic warnings, stale evidence, or no task changes. |
| `3` | Operational error: invalid task state, Git failure, or resource limit. |
| `130` | Interrupted. Rerun before relying on a receipt. |

Argument syntax errors are reported by Python's argument parser with exit code `2` and no receipt. Treat any nonzero exit as non-passing in automation.

## Privacy and boundaries

State lives in `<git-dir>/stewardcheck/active.json`. It contains task text, paths, content hashes, derived metrics, the exact declared argv, and bounded redacted check output—not copies of source files. POSIX state files are created with restrictive permissions. Git-based discovery respects ignored untracked paths; tracked files remain monitored even when matched by ignore rules, and known baseline paths are retained when ignore rules change.

Ignored untracked files, nested repository/submodule interiors, Git-unlisted special files, external dependencies, and transient changes between snapshots are not comprehensively monitored. Static checks are heuristics: both false positives and false negatives are possible. Hashes detect accidental stale or damaged records, not tampering by another process with the same permissions. Built-in redaction does not replace a dedicated scanner such as [Gitleaks](https://github.com/gitleaks/gitleaks).

See [SECURITY.md](SECURITY.md) for the threat model and platform limits, and [docs/architecture.md](docs/architecture.md) for data flow and receipt semantics.

## Development and references

Run `python -m unittest discover -s tests -v` from this package after installing it. Development details and the release checklist are in [CONTRIBUTING.md](CONTRIBUTING.md).

The design survey covers Repomix, Gitingest, Aider, Cline, OpenHands, Gitleaks, pre-commit, and official Git/Python documentation. [Research and tradeoffs](docs/research.md) records sources, the observed popularity snapshot, design decisions, and evidence limits. [THIRD_PARTY.md](THIRD_PARTY.md) distinguishes conceptual references from dependencies and copied material. No upstream implementation or rule catalog is vendored.

StewardCheck is licensed under [MIT](LICENSE). This license applies to this package directory, not unrelated material elsewhere in the parent repository.
