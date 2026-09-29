# Utility repair candidates — 2026-09-29

## Actual status

Nine locally tested candidate changes are recorded here. They are **not nine upstream contributions**. Eight attempts to open upstream bug reports returned `403 Resource not accessible by integration`. Dify already has the same issue and PR, so no competing report or PR was submitted. This batch created **zero upstream issues, zero upstream pull requests, and zero merged changes**.

| Project | Candidate change | Before failed/passed | After passed | Upstream result |
|---|---|---:|---:|---|
| eriklindernoren/ML-From-Scratch | Preserve fractional standardized values for integer arrays | 3/3 | 6 | Issue creation denied: 403 |
| ddbourgin/numpy-ml | Prevent integer overflow in distance calculations | 12/9 | 21 | Issue creation denied: 403 |
| recommenders-team/recommenders | Return empty arrays for top_k=0 | 5/6 | 11 | Issue creation denied: 403 |
| argosopentech/argos-translate | Preserve literal underscores when decoding SentencePiece tokens | 7/4 | 11 | Issue creation denied: 403 |
| sloria/TextBlob | Handle generator-based tag suffixes consistently | 3/4 | 7 | Issue creation denied: 403 |
| rasbt/mlxtend | Separate appended emoticons from the last word | 6/5 | 11 | Issue creation denied: 403 |
| stanford-oval/storm | Preserve multiple citations after a complete sentence | 5/5 | 10 | Issue creation denied: 403 |
| serengil/deepface | Avoid angular-distance NaNs caused by cosine roundoff | 9/5 | 14 | Issue creation denied: 403 |
| langgenius/dify | Handle non-hour timezone gaps | 4/7 | 11 | Existing issue #39230 / PR #39231; not submitted |

Total: **54 failing and 48 passing tests before; 102 passing tests after**. These are focused regression/control tests, not any project's entire suite.

## Reproduction

The source pins in `source_index.json` identify the complete upstream files. Every original file was checked against its Git blob SHA. Every patch passed `git apply --check`, and applying it reproduced the tested modified file exactly.

Use Python 3.13, Git, pytest, NumPy, SciPy, SentencePiece and pytz. The tested versions are Python 3.13.5, pytest 9.0.2, NumPy 2.3.5 and SciPy 1.17.0; full environment details and execution logs are in the evidence archive provided with this batch.

```sh
python reproduce.py --case textblob --variant before
python reproduce.py --case textblob --variant after
```

The first command intentionally reproduces failing cases. The runner downloads only the pinned public source, verifies its hash, and applies the patch in a temporary directory. Use `--download-only` to prepare source files without running tests. The tests then run locally; they do not call model services or paid APIs. Downloaded source remains subject to its upstream license.

Six cases load the complete standalone utility module. STORM, DeepFace and Dify execute selected definitions from the complete source to avoid unrelated model/service dependencies. Argos uses a locally trained tiny SentencePiece character model. These tests do not establish full-package integration correctness; upstream-native tests and project checks are still needed before a PR.

## Scope notes

- The numpy-ml candidate subtracts integer arrays exactly before converting differences to floating point, preserving distinctions between adjacent large int64 values.
- Argos' existing underscore behavior came from earlier tokenizer changes (#457 / #460); any legacy-package compatibility requirements need maintainer discussion.
- Dify's existing work belongs to its actual authors: https://github.com/langgenius/dify/issues/39230 and https://github.com/langgenius/dify/pull/39231. It is linked for deduplication, not claimed as a contribution from this account.
- No primary branch or upstream source was modified. Temporary source-collection workflows created for this investigation were removed after their completed runs.
- Original source and patch context retain the upstream authors' copyrights and licenses. This repository does not relicense them.
