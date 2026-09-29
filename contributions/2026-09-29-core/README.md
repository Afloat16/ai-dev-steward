# Core correctness repair candidates — 2026-09-29

Nine independent candidate repairs, each with source pins, an applicable patch, and executed regression tests. **Three upstream issue reports were created, six report submissions were denied with HTTP 403, and no upstream PR or merged change was created.** These are not nine accepted code contributions.

| Project | Change | Before failed / passed | After passed | Upstream result |
|---|---|---:|---:|---|
| MetaGPT | Preserve Unicode and quoted dependency paths across persistence | 8 / 7 | 15 | [Issue #2166](https://github.com/FoundationAgents/MetaGPT/issues/2166) |
| Crawl4AI | Separate page budgets across fresh BFS runs | 10 / 2 | 12 | [Issue #2309](https://github.com/unclecode/crawl4ai/issues/2309) |
| ChatDev | Register tool modules before executing postponed-annotation dataclasses | 4 / 3 | 7 | [Issue #681](https://github.com/OpenBMB/ChatDev/issues/681) |
| denoising-diffusion-pytorch | Correct the SDPA custom scale and associated gradients | 11 / 12 | 23 | Report denied: 403 |
| nano-vLLM | Initialize spawned workers' Sequence block size before KV addressing | 3 / 1 | 4 | Report denied: 403 |
| EasyR1 | Apply the GAE recurrence mask independently per trajectory | 15 / 2 | 17 | Report denied: 403 |
| Flair | Include every spatial coordinate in hyperbolic distance | 11 / 1 | 12 | Report denied: 403 |
| numpy-ml | Track the best inverse-distance class vote in KNN | 10 / 4 | 14 | Report denied: 403 |
| BERTopic | Reject mixed-type document iterables while preserving empty-input rejection | 10 / 7 | 17 | Report denied: 403 |

**Total: 82 failed / 39 passed before; 121 passed after.** Each patch passed `git apply --check`, and its applied bytes matched the tested modified files. These are targeted regressions and controls, not the projects' complete suites.

## Core findings

- Attention: for explicit scale `s` and head dimension `d`, the fast path used effective scale `s / d**1.5`. One seeded float64 example differed from the ordinary path by 1.402085253322187 before the fix and 4.440892098500626e-16 after. The tests compare outputs and Q/K/V gradients with an independent softmax formula; CUDA kernels were not tested.
- KV cache: a fresh spawned worker retained Sequence's default block size 256. With configured size 512, 257 tokens and physical block 5, decode selected slot 2560 instead of 2816. Four real-spawn tests cover 29 token-length boundaries. GPU initialization/model imports are replaced at the hardware boundary; real sequence pickling and decode address generation are exercised, not multi-GPU inference.
- GAE: a batch-length mask was used as a scalar condition, and padded single-trajectory states could remain Python integers. The fix uses tensor states and per-trajectory selection, checked against independent NumPy recurrences and masked whitening. No rollout or training was run.
- Hyperbolic distance: the dot product omitted the first spatial feature despite recomputing the time coordinate from all features. Forward and gradient checks preserve the existing numerical floor.
- KNN: `best_score` was never updated, so a later class could replace a larger weighted vote. Actual BallTree/KNN code is compared against brute-force distances and votes; zero-distance/tie behavior is outside this change.

## Reproduce

Use the dependencies recorded in `environment.json`. No model downloads, paid APIs, or automatic dependency installation are performed.

```sh
# Evidence ZIP: pinned source files are already present; works offline.
python reproduce.py --variant after
python reproduce.py --case easyr1-batched-gae --variant before

# GitHub checkout: fetch only the pinned public files once.
python reproduce.py --fetch --verify-only
python reproduce.py --variant after
```

The `before` command intentionally fails. Each case runs in its own process. Existing edited sources are never overwritten. `source_index.json` records full source identities and test results; `test_regression.py` shows all loading scaffolding.

MetaGPT tests use the complete DependencyFile/exception decorator and selected unchanged async file-I/O definitions with real temporary files. Crawl4AI tests use complete traversal/filter/scorer classes with lightweight configuration/result objects and a deterministic crawler at depth zero. Other cases load their full utility modules; numpy-ml needs a compatibility alias for its separate legacy `collections.Hashable` import. These checks do not certify full-package integration or make the patches merge-ready without project-native checks.

## Deduplication and scope

BERTopic's single-feature c-TF-IDF failure was found to match existing [issue #2034](https://github.com/MaartenGr/BERTopic/issues/2034). No duplicate was submitted; a different document-validation defect was investigated instead. The excluded reproduction is retained only in the evidence ZIP and is not counted above.

All patches retain upstream ownership and license obligations. The ZIP contains license and inspected contribution-rule snapshots, full pinned source files, and raw before/after logs. This branch adds repair materials only; it does not modify existing application code or the primary branch. The temporary read-only source-collection workflow was removed after its completed run. The requested thirty-project upstream-contribution target is not complete.
