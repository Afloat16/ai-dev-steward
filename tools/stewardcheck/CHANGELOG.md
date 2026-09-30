# Changelog

## 0.2.0 — 2026-09-30

- Keep StewardCheck as the independently installable companion in `tools/stewardcheck`; integrate repository entry points and test both components in CI.
- Add explicit `start --config PATH` with schema-1 TOML defaults, strict validation, repository-root-relative paths, and documented CLI replacement precedence. Configuration never auto-loads or executes commands.
- Pin resolved config to the existing task contract. New tasks additionally protect `.stewardcheck.toml` by default; existing task policies are unchanged.
- Reject non-regular state/config files before opening; use bounded reads and POSIX nonblocking open to avoid FIFO hangs and detect file replacement during reads. This is not a hostile-filesystem sandbox.
- Avoid retaining complete source texts in start/check/report snapshots while preserving all hashes and scan metadata. Context packets still receive text. Include a reproducible synthetic memory benchmark.
- Add the producing tool version to receipts and validate malformed task envelopes as operational errors.
- Use SPDX license metadata and include license/attribution notices in wheel metadata; include the TOML example in the source distribution.
- Keep state schema 1 compatible with existing task records; the skill remains v1.1.0 with its Python 3.10+ requirement, while StewardCheck requires Python 3.11+.


## 0.1.0 — 2026-09-30

Initial alpha release of the independent StewardCheck package.

- Task-start working-tree baselines, explicit path contracts, protected paths, and file-count budgets.
- Bounded, whole-file context packets with sensitive-path exclusion and heuristic redaction.
- Static findings for newly detected secrets, test weakening, opaque content, and partial staging.
- Opt-in argv checks with time/output limits and workspace-bound, freshness-checked receipts.
- JSON and Markdown output, a prerequisite inspector, regression tests, and a temporary-repository demo.
- English and Simplified Chinese guides, a threat model, and a documented reference survey.

The receipt schema and Python API are provisional in 0.x. This release does not add provider integrations, automatic edits, rollback, hooks, cryptographic attestation, or a sandbox.
