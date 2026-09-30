# AI Dev Steward

**English** | [简体中文](README.zh-CN.md)

**Focused changes. Traceable evidence. Less clutter.**

AI Dev Steward combines an agent skill for artifact hygiene and algorithm-review discipline with **StewardCheck**, a local CLI for task-scoped coding checks. Use either component independently, or use them together in an existing issue or pull request. No model account, API key, server, or third-party Python runtime dependency is required.

## Choose the right tool

| Your task | Component | Requirements |
| --- | --- | --- |
| Check what changed during a coding task, whether edits stayed in scope, and whether test results are still current | [StewardCheck](tools/stewardcheck/README.md), **0.2.0 alpha** | Python 3.11+ and Git |
| Audit stale artifacts, retain reproducibility evidence, or review attribution across algorithm optimizations | [Agent Skill](SKILL.md) and `scripts/steward.py`, **v1.1.0** | Python 3.10+ and Git |

The distinction matters: the skill's four tools are read-only. StewardCheck stores one local task record in Git metadata and runs declared programs **only with `check --run`**. Neither component automatically edits source, deletes project artifacts, rolls back work, or merges changes.

## Start with StewardCheck

Install the independently packaged CLI from this repository using [pipx](https://pipx.pypa.io/stable/):

```sh
pipx install "git+https://github.com/Afloat16/ai-dev-steward.git#subdirectory=tools/stewardcheck"
stewardcheck --version
```

Alternatively, clone this repository and run `python -m pip install ./tools/stewardcheck` in an activated Python 3.11+ virtual environment. Installation does not require installing an agent skill, and no PyPI release is assumed.

From the Git project you want to change:

```sh
stewardcheck start "Fix empty-input handling" \
  --scope "src/**" --scope "tests/**" \
  --check "python -m unittest discover -s tests" \
  --accept "Preserve behavior outside the requested fix"

stewardcheck packet
# Review the packet, then use it with your existing coding assistant.
# Review the edits and declared command before executing checks.
stewardcheck check --run
stewardcheck report --format json
```

Replace the example check with your project's actual test command. Task baselines include existing dirty and non-ignored untracked files. Scope/protected-path rules, heuristic credential/test-weakening checks, and workspace-bound receipts help distinguish `passed`, `blocked`, and `needs-review`; a pass does not prove human acceptance criteria.

For repeat work, explicitly load a reviewed TOML configuration rather than repeating every flag:

```sh
stewardcheck start "Fix parsing" --config .stewardcheck.toml
```

The file is optional and never auto-loaded. See the [configuration example](tools/stewardcheck/examples/task.toml), [complete CLI guide](tools/stewardcheck/README.md), and [Chinese CLI guide](tools/stewardcheck/README.zh-CN.md). Configured commands remain pinned to the task and still require explicit execution approval.

## Use the agent skill

Place the complete repository in your host's supported skill directory, keeping the directory name `ai-dev-steward`. For hosts that discover `.agents/skills`:

```sh
git clone https://github.com/Afloat16/ai-dev-steward.git .agents/skills/ai-dev-steward
```

Otherwise, clone it separately and ask your agent to read `SKILL.md`. Follow your host's discovery rules; do not keep duplicate active copies. Compatibility with every host has not been tested.

> Use ai-dev-steward to audit old plans, logs, and experimental artifacts. Work read-only, distinguish retained items from review-needed items and quarantine candidates, and explain the evidence. Do not create new planning files.

> Use ai-dev-steward to review the current optimization branch. Pin the compared commits, separate refactoring, algorithm, precision, and caching changes, and identify gaps in tests, ablations, and rollback steps. Put the review in the existing PR and do not rewrite history.

Run the read-only tools directly from the project you want to inspect:

```sh
SKILL=.agents/skills/ai-dev-steward
python -B "$SKILL/scripts/steward.py" audit --root .
python -B "$SKILL/scripts/steward.py" diff --root . --base main --head HEAD
python -B "$SKILL/scripts/steward.py" gate --input /path/to/actual-evidence.json
python -B "$SKILL/scripts/steward.py" review --root . --base main --head HEAD \
  --input /path/to/actual-evidence.json --format markdown
```

Replace the installation path, baseline ref, and evidence path with real values. `diff` compares committed branch changes and reports uncommitted work separately. `gate` checks supplied paired measurements and comparison metadata. `review` checks commit alignment, declared change coverage, dependencies, tests, rollback, and ablations. None of these commands run experiments or authenticate supplied results.

## One repository, complementary evidence

Use StewardCheck **before editing** to capture the actual task-start workspace, and after editing to inspect scope and explicitly run checks. Use the skill's `diff`, `gate`, and `review` when a change makes algorithmic or performance claims that need measured evidence. A StewardCheck receipt is not a replacement for a metrics record or a claim of acceleration.

Keep discussion in the existing issue, PR, or experiment tracker. Do not automatically convert receipts into benchmark evidence or generate another planning hierarchy. Only when no equivalent source exists and persistent lifecycle state is necessary should the skill use at most one `.ai/state.md` and one `.ai/artifacts.json`. StewardCheck's active record lives under `<git-dir>/stewardcheck/`, not in a new source-tree planning directory.

## Safety and interpretation

**Retain first.** Names, age, ignore status, and duplicate hashes do not authorize cleanup. Protect source, raw data, baseline/release evidence, active runs, Git-tracked files, and retained dependencies. Quarantine candidacy requires lifecycle declarations, an eligible ordinary single-link file, a matching hash, and fresh reference-review evidence. It still requires explicit path-level approval and a verified recovery procedure; final deletion requires separate approval. Moving a file does not itself free disk space.

**Keep claims tied to evidence.** Pin compared commits, configurations, data/split fingerprints, protocols, environments, hardware, precision, budgets, pairing units, seeds, and raw-result pointers. Review baseline, individual factors, the full combination, and declared high-risk interactions; disclose unavailable isolated results rather than inventing them. A changed comparison condition may require a controlled comparison instead of a pass. `CHECKS_PASS` only describes the supplied structure and numeric checks, not authenticity, causality, statistical significance, or approval to merge. Example metrics deliberately return `EXAMPLE_ONLY` and a nonzero exit code.

**Checks are not a sandbox.** StewardCheck's explicitly approved programs inherit your permissions and environment and can execute project code, access credentials, change files, or use the network. Its scanners are heuristics with false positives and false negatives; ignored untracked content, opaque repository interiors, external dependencies, and transient between-snapshot changes are not comprehensively covered. Records detect accidental changes, not tampering by a process with the same permissions. See the [skill playbook](references/playbook.md) and [StewardCheck threat model](tools/stewardcheck/SECURITY.md).

## Repository guide and maintenance

| Path | Purpose |
| --- | --- |
| [SKILL.md](SKILL.md) | Agent entry point, mode selection, stop conditions, and delivery requirements. |
| [scripts/steward.py](scripts/steward.py) | Read-only artifact audit, committed diff, metrics gate, and review packet. |
| [tools/stewardcheck/](tools/stewardcheck/) | Independently installable task-baseline, context, and receipt CLI. |
| [references/playbook.md](references/playbook.md) | Lifecycle rules, provenance, attribution, formats, and migration guidance. |
| [assets/](assets/) | Synthetic ledger and metrics examples, not measured results. |
| [tests/](tests/) | Skill regressions and cross-component documentation/version checks. |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Run both suites, package checks, and contribution/release guidance. |
| [CHANGELOG.md](CHANGELOG.md) / [CLI changelog](tools/stewardcheck/CHANGELOG.md) | Independently versioned component histories. |

English is the primary introduction language, with Chinese READMEs for both components. The detailed skill and playbook remain in Chinese. Existing v1.0 ledger records remain readable but missing review evidence stays non-passing; see the playbook. StewardCheck 0.2.0 keeps schema-1 task records readable without silently changing their pinned policies.

StewardCheck's [MIT license](tools/stewardcheck/LICENSE) applies to that package directory. Its [third-party notices](tools/stewardcheck/THIRD_PARTY.md) and [design survey](tools/stewardcheck/docs/research.md) distinguish conceptual references from reused code and dependencies. Other repository material retains its existing notices and licensing status.
