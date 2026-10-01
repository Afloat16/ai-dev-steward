# Robotics / Embodied-AI contribution audit

2026-09-28 · Account: Afloat16 · AI-assisted preparation and execution

**This is a personal review branch, NOT an upstream PR, merge, or contributor-status claim.** Three candidate source fixes have been exercised against exact Git-blob-verified files. Baseline: **20 failed, 14 passed**. Patched: **34 passed**. No full upstream CI, GPU training, or hardware tests were run.

The attempted openpi issue creation returned **HTTP 403: Resource not accessible by integration**. No upstream issue or PR was published successfully. The connected tools do not expose Fork creation. Nothing in this directory bypasses those restrictions or posts automatically.

## 3 classic + 7 modern popular projects

Stars are approximate GitHub page counts observed during this audit, not measured weekly growth. Reported issues below are other contributors' work, not defects independently reproduced here unless explicitly marked tested.

| Group | Repository | Stars | Actual work / candidate |
|---|---|---:|---|
| Classic | [PythonRobotics](https://github.com/AtsushiSakai/PythonRobotics) | 30.6k | Repeated-knot validation candidate; 15 tests pass. Final-knot bug already has [PR #1433](https://github.com/AtsushiSakai/PythonRobotics/pull/1433), not duplicated. |
| Classic | [Stable-Baselines3](https://github.com/DLR-RM/stable-baselines3) | 13.8k | Empty statistics update candidate; 11 tests pass. Research only: AI PR policy applies. |
| Classic | [MuJoCo](https://github.com/google-deepmind/mujoco) | 15.4k | [#3533](https://github.com/google-deepmind/mujoco/issues/3533), Windows/AMD Studio startup: report reviewed, not reproduced. |
| Modern | [LeRobot](https://github.com/huggingface/lerobot) | 27.8k | [#3863](https://github.com/huggingface/lerobot/issues/3863), state/action mapping: report and AI policy reviewed; author already has implementation. |
| Modern | [Genesis World](https://github.com/Genesis-Embodied-AI/genesis-world) | 30.0k | [#3401](https://github.com/Genesis-Embodied-AI/genesis-world/issues/3401), emitter reset accumulator: report reviewed; author already has patch. |
| Modern | [openpi](https://github.com/Physical-Intelligence/openpi) | 14.0k | Empty image batches candidate; 8 tests pass. Issue publication blocked by 403. |
| Modern | [Isaac-GR00T](https://github.com/NVIDIA/Isaac-GR00T) | 8.1k | [#771](https://github.com/NVIDIA/Isaac-GR00T/issues/771), negative history indexing: report reviewed, not reproduced. |
| Modern | [IsaacLab](https://github.com/isaac-sim/IsaacLab) | 8.2k | Read develop CircularBuffer; no new confirmed defect. Reviewed [#8035](https://github.com/isaac-sim/IsaacLab/issues/8035) startup-performance report. |
| Modern | [Newton](https://github.com/newton-physics/newton) | 5.7k | [#4243](https://github.com/newton-physics/newton/issues/4243), scalar sparse BLAS: report reviewed, Warp runtime unavailable. |
| Modern | [OpenVLA](https://github.com/openvla/openvla) | 7.1k | Checkpoint condition inspected; overlapping [PR #202](https://github.com/openvla/openvla/pull/202) found. No duplicate fix or training run. |

## Evidence and reproduction

`manifest.json` records exact source paths, blob hashes and edits. `patches/` contains production-code diffs; `tests/` is an independent verification harness, not yet integrated into upstream test layouts. `results.json` records counts and limitations. `drafts.md` contains unpublished issue descriptions with AI disclosure.

```sh
python -m pip install -r requirements-validation.txt
python verify.py
```

The online version retrieves three public, pinned Git blobs. An offline bundle with `baseline/` uses those files instead, or pass `--source-root /path/to/baseline`. SHA mismatches stop validation. Tests and candidate modifications run in a temporary directory; this script does not modify an upstream checkout, fork repositories, open PRs or install dependencies automatically.

Environment actually used: Debian GNU/Linux 13, Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0, Pillow 12.3.0, pytest 9.0.2. Compact real test output is in `reports/summary.txt`; full failure traces are retained in the offline evidence bundle.

## Scope and publication gates

PythonRobotics rejects repeated coordinates before zero-width arithmetic; valid natural-spline derivatives of orders 0-3 match SciPy. The separate final-knot bug is unchanged. openpi's empty-array return and SB3's empty-update no-op are proposed API contracts that still require maintainer agreement; they are not demonstrated failures of a normal robot deployment or default training run.

[SB3 contribution policy](https://github.com/DLR-RM/stable-baselines3/blob/master/CONTRIBUTING.md) requires an issue first and prohibits fully AI-generated PRs unless maintainer-triggered. Its candidate is research only. [LeRobot AI policy](https://github.com/huggingface/lerobot/blob/main/AI_POLICY.md) requires disclosure and accountable human judgment. No human review by the account owner is asserted.

Before upstream publication: obtain suitable authorized Fork/Issue/PR capability, recheck duplicates and latest source, agree on input contracts, integrate regressions into project tests, and run required CI/lint/type/doc checks. Do not batch-submit these materials as completed PRs. No merged contribution, benchmark improvement, attention growth, or upstream affiliation is claimed.
