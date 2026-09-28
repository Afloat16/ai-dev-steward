# AI Dev Steward

**English** | [简体中文](README.zh-CN.md)

**Less clutter. Traceable experiments. Reviewable optimizations.**

AI Dev Steward is an Agent Skill for keeping AI-assisted algorithm development lean, reproducible, and reviewable. It helps consolidate redundant planning files, audit stale experimental artifacts, and organize complex optimization branches into changes that reviewers can trace to tests, measurements, ablations, and rollback steps.

The skill combines a development workflow with four read-only Python tools. It favors existing issues, pull requests, and experiment trackers over new administrative files, and treats cleanup candidates and performance claims as evidence to review—not permission to delete or merge.

**v1.1.0 · Python 3.10+ · Git · No third-party Python dependencies · Read-only tools**

## Why this skill exists

AI-assisted development can leave behind overlapping plans, forgotten logs, intermediate datasets, and experimental outputs. Meanwhile, a single optimization branch may mix refactoring, algorithm changes, precision adjustments, and caching, making it difficult to tell what changed, which experiment measured it, or how to undo it.

AI Dev Steward addresses both problems without creating another layer of planning clutter.

| Problem | Approach |
| --- | --- |
| Duplicate `planning`, `planing`, and versioned plan files | Keep one active plan per task. Preserve unique decisions and acceptance criteria before consolidating old documents. Filename matches are review hints, not proof of duplication. |
| Stale or unowned experiment artifacts | Inventory files and check lifecycle records, ownership, expiry, reproducibility, content hashes, and declared dependencies before identifying quarantine candidates. |
| Cleanup that could damage reproducibility | Retain unknown or protected artifacts and their transitive dependencies. Require explicit, path-level approval and a verified recovery procedure for manual quarantine. |
| Large, mixed-purpose optimization branches | Map logical changes to files, invariants, tests, experiments, and rollback steps; suggest a dependency-aware reading order. |
| Performance improvements without clear attribution | Check paired metrics, comparison conditions, provenance fields, and declared ablation coverage; make missing evidence explicit. |

## Quick start

### Install

Place the complete repository in your agent host's supported skill directory and keep the directory name `ai-dev-steward`. For a host that discovers skills under `.agents/skills`, run this from the project root:

```sh
git clone https://github.com/Afloat16/ai-dev-steward.git .agents/skills/ai-dev-steward
```

Alternatively, clone it into a separate directory and explicitly ask your agent to read its `SKILL.md`. Follow your host's discovery rules and avoid multiple active copies. Compatibility with every client has not been tested.

### Ask your agent

**For artifact hygiene:**

> Use ai-dev-steward to audit old plans, logs, and intermediate experiment artifacts in this project. Work read-only, distinguish retained items from review-needed items and quarantine candidates, and explain the reason for each decision. Do not create new planning files.

**For optimization review:**

> Use ai-dev-steward to review the current optimization branch. Pin the baseline and candidate commits, separate refactoring, algorithm, precision, and caching changes, and identify gaps in tests, ablations, and rollback steps. Put the review in the existing pull request and do not rewrite branch history.

### Run the tools directly

Run these commands from the project you want to inspect. Set `SKILL` to your actual installation path.

```sh
SKILL=.agents/skills/ai-dev-steward

# Inventory artifacts. No ledger is required; no governance files are created.
python -B "$SKILL/scripts/steward.py" audit --root .

# Inspect committed branch changes and separately report uncommitted work.
python -B "$SKILL/scripts/steward.py" diff --root . --base main --head HEAD

# Check real measurements produced by your trusted evaluation workflow.
python -B "$SKILL/scripts/steward.py" gate --input /path/to/actual-evidence.json

# Use the same evidence file, including changes and ablations, for a PR-ready report.
python -B "$SKILL/scripts/steward.py" review --root . --base main --head HEAD \
  --input /path/to/actual-evidence.json --format markdown
```

`/path/to/actual-evidence.json` is a placeholder for your real evaluation record, not a bundled file. Replace `main` with the appropriate baseline ref or fixed commit SHA. If the baseline already contains the candidate changes, choose an earlier baseline or a feature-branch comparison instead.

Output goes to the terminal by default. Save it only to an approved, existing destination when needed; do not create timestamped report copies or commit sensitive raw logs.

## Four tools, one evidence trail

| Command | What it checks or produces |
| --- | --- |
| `audit` | Read-only artifact inventory, retention reasons, planning-file review hints, and evidence-qualified quarantine candidates. Without a ledger, it inventories rather than authorizing cleanup. Use repeated `--scope` arguments to limit discovery in large projects. |
| `diff` | Pinned commit SHAs, an inventory of committed changes from merge-base to head, and a separate working-tree status. Uncommitted and ignored content is outside the committed comparison. |
| `gate` | Paired metrics, units, sample counts, comparison conditions, provenance fields, and both mean and per-pair regression limits. Missing evidence is not silently treated as a pass. |
| `review` | Commit alignment, changed-file coverage, logical dependencies, test and rollback declarations, and declared ablation coverage. Outputs JSON or a Markdown review packet for an existing PR. |

The tools inspect supplied records; they do not run experiments, execute commands from evidence files, or independently authenticate results.

## Workflow principles

### Reuse existing sources of truth

Prefer your existing issue, PR, or experiment tracker. Only when there is no equivalent and persistent state is necessary should you maintain at most one `.ai/state.md` and one `.ai/artifacts.json`. Small changes and ordinary questions do not require a ledger or experiment matrix.

### Retain first; quarantine only with evidence and approval

File age, name, Git ignore status, and duplicate hashes are not sufficient reasons to delete anything. Unknown artifacts stay retained.

Quarantine candidacy requires an eligible path and regenerable artifact type, a closed and expired record, no active or pinned use, no Git tracking or retained dependents, and a regular file with a single hard link. It also requires closure metadata, a reproduction method, a reference-review declaration no more than seven days old, and a SHA-256 matching the current content. The seven-day window is a conservative convention of this tool, not an external standard.

A candidate is not deletion authorization. Manual quarantine requires a fresh check, exact-path approval, and a verified recovery procedure. Final deletion requires a separate approval. Moving a file into quarantine does not itself free disk space.

### Bind optimization claims to the measured change

Freeze the baseline, candidate, configuration and dirty-patch hashes, dataset and split fingerprints, evaluation protocol, environment, hardware, precision, batch size, training budget, pairing units, seeds, measurement procedure, and raw-result pointers.

For two independent optimization factors, review baseline, A, B, and A+B evidence. For larger changes, require the baseline, each factor in isolation, the full combination, and declared high-risk interactions rather than automatically demanding every possible combination. When factors cannot run independently, document their dependencies and attribution limits instead of inventing isolated results.

If hardware, precision, or another comparison condition is itself the intervention, the automatic gate may report the runs as incomparable. Design a controlled comparison; do not change metadata to bypass the check.

## Safety and limitations

**There are no automatic delete, move, training, or merge commands.** The skill also prohibits unauthorized stashing, resets, force pushes, history rewrites, and overwriting uncommitted work.

Source code, raw data, baseline and release models or evidence, active runs, Git-tracked files, and retained dependencies must be protected. Submodules, nested repositories, symbolic links, and hard-linked files are not ordinary cleanup targets.

Ledger records, reference checks, test results, and experiment pointers are declarations, not independently verified facts. A ledger cannot discover every dynamic reference, remote training job, or object-storage consumer. The tools are not a security sandbox for a hostile, concurrently changing filesystem; actual quarantine requires stopping writes and revalidating paths, content, and consumers.

**`CHECKS_PASS` means the supplied structure and numeric checks passed.** It does not establish experiment authenticity, algorithmic correctness, statistical significance, isolated gains, or causation, and it does not approve a merge. Correctness tests, slice regressions, uncertainty analysis, and human review remain necessary.

## Repository guide

| Path | Purpose |
| --- | --- |
| [SKILL.md](SKILL.md) | Agent entry point, mode selection, stop conditions, and delivery requirements. |
| [scripts/steward.py](scripts/steward.py) | The four read-only command-line tools. |
| [tests/](tests/) | Regression and package tests using temporary Git repositories and synthetic metrics. |
| [references/playbook.md](references/playbook.md) | Lifecycle rules, safety boundaries, experiment attribution, data formats, and exit codes. |
| [assets/ledger.example.json](assets/ledger.example.json) | Example artifact ledger; not a real project registry. |
| [assets/metrics.example.json](assets/metrics.example.json) | Example metrics, logical changes, and ablations; not measured results. |
| [CHANGELOG.md](CHANGELOG.md) | Version history and migration notes. |
| [README.zh-CN.md](README.zh-CN.md) | Chinese introduction and usage guide. |

English is the primary language of the repository introduction. The detailed `SKILL.md`, playbook, and changelog currently remain in Chinese; this README update does not translate the entire skill package.

## Tests and migration

Run the included test suite:

```sh
SKILL=.agents/skills/ai-dev-steward
python -B -m unittest discover -s "$SKILL/tests" -v
```

Tests use synthetic data and temporary repositories. They do not demonstrate real model acceleration, real project cleanup, or validation on every operating system or agent host.

The example metrics intentionally return `EXAMPLE_ONLY` and a nonzero exit code. Never present the examples as measured evidence.

Older v1.0 ledgers remain readable, but entries missing the additional review evidence stay `KEEP`. Incomplete experiment provenance is reported rather than silently accepted. See the [playbook](references/playbook.md) and [changelog](CHANGELOG.md) for the format and migration requirements.
