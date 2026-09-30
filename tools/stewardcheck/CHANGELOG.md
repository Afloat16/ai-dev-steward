# Changelog

## 0.1.0 — 2026-09-30

Initial alpha release of the independent StewardCheck package.

- Task-start working-tree baselines, explicit path contracts, protected paths, and file-count budgets.
- Bounded, whole-file context packets with sensitive-path exclusion and heuristic redaction.
- Static findings for newly detected secrets, test weakening, opaque content, and partial staging.
- Opt-in argv checks with time/output limits and workspace-bound, freshness-checked receipts.
- JSON and Markdown output, a prerequisite inspector, regression tests, and a temporary-repository demo.
- English and Simplified Chinese guides, a threat model, and a documented reference survey.

The receipt schema and Python API are provisional in 0.x. This release does not add provider integrations, automatic edits, rollback, hooks, cryptographic attestation, or a sandbox.
