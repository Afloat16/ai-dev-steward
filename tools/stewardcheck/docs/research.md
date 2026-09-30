# Design research and tradeoffs

Research date: **2026-09-30**. Sources are upstream repositories, their documentation, issue reports, and the official Git/Python references. This is a design survey, not a benchmark or proof of market demand. Star counts below are the rounded values displayed on the inspected GitHub pages; they are a popularity snapshot, not exact live counts or a quality ranking.

## Survey

| Project and primary source | Observed stars | Relevant capability | Decision for StewardCheck |
| --- | ---: | --- | --- |
| [Repomix](https://github.com/yamadashy/repomix) | ~28.6k | Repository packing, include/exclude controls, token counting, secret checks, optional structural compression. | Keep context portable, but restrict the first release to task-oriented, complete-file packets with an honest byte budget. Do not reproduce its packing implementation, tokenizer, or rule integration. |
| [Gitingest](https://github.com/coderamp-labs/gitingest) | ~15.8k | Prompt-friendly codebase extraction through a small interface. | Preserve a low-friction CLI, while making the local task baseline and post-edit receipt the primary objects. |
| [Aider](https://github.com/Aider-AI/aider) | ~49.3k | Terminal pair programming, repository context, Git-aware development workflow. | Complement a coding agent rather than build another model interaction loop. Accept any assistant's edits and inspect their task delta locally. |
| [Cline](https://github.com/cline/cline) | ~69.6k | Coding-agent execution across IDE, CLI, and SDK surfaces. | Keep command approval explicit; avoid automatic checkpoint restore or history manipulation. |
| [OpenHands](https://github.com/OpenHands/OpenHands) | ~89.6k | A broader software-development agent platform and execution architecture. | Deliberately omit agent orchestration and hosted infrastructure. Do not describe a plain subprocess runner as a sandbox. |
| [Gitleaks](https://github.com/gitleaks/gitleaks) | ~29.6k | Specialized credential scanning. | Treat the small built-in patterns as review hints and keep dedicated scanning complementary. Do not copy its rule catalog or imply equivalent detection coverage. |
| [pre-commit](https://github.com/pre-commit/pre-commit) | ~15.6k | Multi-language hook management. | Support explicit existing check programs without automatically installing hooks or managing their environments. A task receipt is distinct from a staged-file hook. |

The table describes the aspects considered, not everything those projects can do. Some already provide overlapping verification, context, approval, or checkpoint features. StewardCheck does not claim exclusivity over these ideas. Its chosen combination is a small, independently implemented, provider-neutral workflow: actual task-start baseline + explicit path contract + bounded context + snapshot-bound command receipt.

## Evidence from issue reports

[Cline issue #4388](https://github.com/cline/cline/issues/4388) collects reports about checkpoint storage, restoration, and repository-state problems. [Issue #13550](https://github.com/cline/cline/issues/13550) discusses branch movement during checkpoint restore; [issue #14367](https://github.com/cline/cline/issues/14367) reports an interaction between uncommitted ignore rules and cleanup. These are reports about particular versions and workflows, not claims that all current Cline installations have these problems. The upstream incidents were not independently reproduced for this survey.

The design consequence is narrow: StewardCheck stores no source backup and never attempts restore, stash, reset, clean, or automatic rollback. It preserves an actual working-tree baseline as metadata and leaves recovery to the developer's existing version-control/backup practices. This avoids promising safety for an operation the tool does not implement.

## Why this scope

The target user already has a preferred coding assistant and a test command. Replacing that assistant would require provider integrations, credentials, prompting policy, and potentially expensive execution infrastructure. A repository packer alone would substantially overlap with established tools. A hidden automatic command runner would obscure authority boundaries.

Instead, StewardCheck makes a developer declare what may change and how to check it, then provides a repeatable local answer about the observed task delta. It is useful across languages because path inspection and process exit codes are language-independent; the selected tests and heuristic coverage still depend on the project. Real user studies and repository-scale performance measurements remain future validation work, not completed evidence.

## Technical references and resulting rules

[Git `ls-files`](https://git-scm.com/docs/git-ls-files) documents cached, other, exclude-standard, stage, and NUL-delimited output. StewardCheck uses those interfaces rather than implementing Git ignore semantics itself. Tracked paths remain visible even when ignore rules match them; ignored untracked paths are outside discovery. The task baseline retains previously known names so a later ignore change cannot erase them from the comparison.

[Git attributes](https://git-scm.com/docs/gitattributes) and [Git diff](https://git-scm.com/docs/git-diff) describe content conversion and diff behavior. During local testing, an independently constructed repository fixture showed that a name-only diff can still invoke a configured clean filter. StewardCheck now disables clean/process drivers in the comparison path and has a regression test that asserts the fixture's marker is never created. This test concerns StewardCheck's own inspection path, not a reported vulnerability in an upstream agent.

[Python `subprocess`](https://docs.python.org/3/library/subprocess.html) explains argv execution, process timeout behavior, and Windows batch-file caveats. StewardCheck uses `shell=False`, bounded capture, explicit timeouts, and POSIX process-group cleanup. Direct Windows batch entrypoints are rejected. These choices reduce accidental command interpretation but do not isolate a malicious test program.

## Alternatives deliberately deferred

Model-specific tokenization, AST/import-aware context selection, remote URLs, automatic repository cloning, MCP servers, editor hooks, automatic patching, rollback, signed attestations, historical task dashboards, and dependency isolation are not part of 0.1.0. Adding any of them needs its own threat model and tests. A larger feature list is not the first release's success criterion.

## Evaluation plan

The included tests use temporary repositories and subprocesses to exercise scope violations, existing dirty work, ignored paths, linked worktrees, index changes, new credentials, stale receipts, timeouts, output limits, source/metadata symlinks, Git filters, and packet boundaries. The demo executes a real `unittest` check. These are implementation checks, not a comparative product benchmark or independent security audit.

For broader adoption, measure false-positive rates on representative projects, context usefulness, large-monorepo cost, and whether developers correctly interpret `passed` versus unchecked acceptance criteria. Do not infer adoption or necessity solely from other projects' stars.

License and reuse boundaries are recorded separately in [THIRD_PARTY.md](../THIRD_PARTY.md).

## 0.2.0 implementation references

Reviewed 2026-09-30: [Python tomllib](https://docs.python.org/3/library/tomllib.html) defines TOML parsing in the standard library and recommends limiting untrusted input size; the package uses an explicit 64 KiB config limit. [Python os.open and flags](https://docs.python.org/3/library/os.html#os.open) documents low-level descriptor opening and platform-dependent flags, including `O_NONBLOCK` and `O_NOFOLLOW`. [Python subprocess](https://docs.python.org/3/library/subprocess.html) remains the reference for argv execution and its limits. These are API/behavior references, not copied implementations. The versioned policy schema, non-automatic config loading, precedence rules, and snapshot text-retention switch are local design decisions.

Package metadata follows the [PyPA pyproject.toml guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/#license), using an SPDX license expression and explicit license files with setuptools >=77.0.3. This changes metadata representation, not the package license.

The cross-platform reader also references CPython 3.13's [pathname stat implementation](https://github.com/python/cpython/blob/v3.13.0/Modules/posixmodule.c) and [descriptor stat implementation](https://github.com/python/cpython/blob/v3.13.0/Python/fileutils.c), alongside [Python's stat_result documentation](https://docs.python.org/3.13/library/os.html#os.stat_result). Windows pathname queries preserve legacy `st_ctime` behavior and can synthesize executable permission bits from extensions. The local reader compares full metadata within the same API, and only shared file-identity/content-metadata fields across APIs. The implementations were consulted to understand API behavior; their code was not copied.
