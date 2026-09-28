# Unpublished contribution drafts

These are drafts only. No upstream issue or PR was created successfully in this run. Significant AI assistance must remain disclosed. Do not state that the account owner manually reviewed or ran the code.

## openpi — issue draft (posting attempt returned HTTP 403)

**Title:** Client resize_with_pad fails on zero-length leading batch dimensions

The NumPy/Pillow helper documents `[..., H, W, C]` input. An already-target-sized empty batch is returned, but an empty batch needing resizing raises `ValueError: need at least one array to stack`.

```python
import numpy as np
from openpi_client.image_tools import resize_with_pad
resize_with_pad(np.empty((0, 8, 12, 3), dtype=np.uint8), height=4, width=6)
```

Leading batch shapes `(2, 0)` and `(0, 2)` behave similarly. A possible use case is an image batch emptied by filtering; this is not a claim of a real robot incident.

Would returning an empty `(0, 4, 6, 3)` array with the original dtype be the intended behavior? An explicit non-empty-batch requirement is another option. A candidate checks `0 in original_shape[:-3]` and returns the appropriately shaped empty array, without changing nonempty resizing.

Complete original file: `packages/openpi-client/src/openpi_client/image_tools.py`, Git blob `7a971b9d5f6b1495fd6cdea202ffa607d8b34bf0`. Imported directly from the exact SHA-verified file, not a full openpi installation. Four new regressions fail before and pass after; four identity/nonempty controls pass both times. Full CI and model/GPU/hardware tests were not run.

Environment: Debian GNU/Linux 13, Python 3.13.5, NumPy 2.3.5, Pillow 12.3.0, pytest 9.0.2. Searches for resize PRs and empty-resize issues did not locate this case; repeat searches immediately before publication.

**AI disclosure:** An AI assistant prepared this report and candidate and executed the local regressions for the account owner. No human review or end-to-end robot validation is claimed.

## PythonRobotics — issue / eventual PR description draft

**Title:** Reject repeated cubic-spline knots before dividing by a zero interval

The constructor rejects descending x coordinates, but permits equal consecutive coordinates. For example:

```python
from PathPlanning.CubicSpline.cubic_spline_planner import CubicSpline1D
CubicSpline1D([0, 0, 1], [0, 1, 2])
```

This passes validation and reaches division by zero; some repeated-node arrangements can also reach a singular solve. Proposed change: require strictly increasing x coordinates (`np.any(h <= 0)`), fail early with `ValueError`, and clarify the constructor docstring. Repeated consecutive 2D waypoints similarly produce a zero arc-length interval and are rejected by the same guard.

The complete source was verified against blob `2391f67c393d5cd3d4137973e163a13bec034bd9`. Six duplicate-input regressions fail on the original and pass after the candidate. Nine controls, including descending-input rejection and natural-spline derivatives of orders 0–3 against SciPy for two valid node sets, pass on both versions.

This does not include the final-knot fix in existing PR #1433. Equal-node handling and final-knot lookup are separate changes. No new runtime dependency is added. Tests currently live in an external verification harness; integrate them into the upstream tests and run full CI before requesting merge.

Environment: Debian GNU/Linux 13, Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0, pytest 9.0.2. No full project CI, lint, documentation build, or hardware validation was run.

**AI disclosure:** Candidate and regressions were prepared and executed by an AI assistant acting for the account owner. Human review has not been asserted.

## Stable-Baselines3 — discussion-only issue draft

**Title:** Should zero-observation RunningMeanStd updates be no-ops rather than poisoning statistics?

```python
import numpy as np
from stable_baselines3.common.running_mean_std import RunningMeanStd
s = RunningMeanStd(epsilon=0.0, shape=(2,))
s.update(np.array([[1., 2.], [3., 4.]]))
print(s.mean, s.var, s.count)  # [2., 3.], [1., 1.], 2
s.update(np.empty((0, 2)))
print(s.mean, s.var, s.count)  # [nan, nan], [nan, nan], 2
```

The undefined mean/variance of an empty input propagates into existing statistics. Subsequent valid updates remain NaN. `update_from_moments` with zero count and undefined moments has the same issue; combining two zero-count objects also divides by zero.

Would an early return for zero-size updates / zero-count moments be appropriate, or should these calls be explicitly rejected? This report does not establish that a default SB3 training path produces empty batches.

The complete `running_mean_std.py` was verified against Git blob `c8f03b212525b558e299a1a05d5f7a3bd48e7b58` and imported by file path. Ten regressions fail before and pass after a local early-return candidate; one nonempty NumPy-reference control passes both. Full SB3 import, training, CI, lint/type/doc checks were not run.

Environment: Debian GNU/Linux 13, Python 3.13.5, NumPy 2.3.5, pytest 9.0.2. The RunningMeanStd PR search found overflow PR #1954, not this zero-observation case. Recheck for duplicates before posting.

**AI disclosure and policy:** This report and local experiment were AI-generated and AI-executed. The project's policy prohibits fully AI-generated PRs unless maintainer-triggered. No such PR is proposed for unsolicited submission here. This draft asks for maintainer direction first.
