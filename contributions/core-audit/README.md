# Core contribution candidates — 2026-09-29

Five independent candidate corrections across four projects. This branch preserves the patches and evidence index; it is not an upstream submission or a claim of merged contribution. The complete runnable verification/publishing packet is delivered separately in the conversation as `Afloat16_core_contributions_2026-09-29.zip`.

| Candidate | Baseline failures / passes | Patched passes | Scope |
|---|---:|---:|---|
| [VGGT Newton Jacobian](patches/vggt_newton.patch) | 6 / 9 | 15 | Complete distortion utility; independent camera polynomial and autograd oracle |
| [DreamerV3 Recency](patches/dreamer_recency.patch) | 9 / 0 | 9 | Complete selectors utility; optional recency mode, not default uniform |
| [DreamerV3 delayed priorities](patches/dreamer_priority.patch) | 6 / 1 | 7 | Complete selectors utility; serialized late updates, not full thread safety |
| [TD-MPC2 Gumbel axis](patches/tdmpc_gumbel.patch) | 4 / 3 | 7 | Complete math utility; default one-dimensional planner input unchanged |
| [robomimic explicit generator](patches/robomimic_generator.patch) | 4 / 2 | 6 | Exact sampler class excerpt with real PyTorch/NumPy/DataLoader, not the complete package |

Totals: original **29 failed / 15 passed**, patched **44 passed**. Four standalone proposed upstream test files were rerun independently: **38 passed**, a subset of the same 44, not extra tests. The publisher's **31 offline tests** also pass; its simulated API tests are not live publication success.

## Publication status

Actual issue creation requests to `danijar/dreamerv3` and `nicklashansen/tdmpc2` both returned HTTP 403 `Resource not accessible by integration`. Upstream issues/PRs/merges from this round: **0 / 0 / 0**. This archive branch must not be counted as upstream contribution.

The local `publish.py` packet automates official GitHub CLI preflight, source/policy hash checks, duplicate searches, focused tests, verified account-owned forks, isolated branches, commits and draft PRs. It never force-pushes, modifies main, signs CLA/DCO, or merges. It has not completed a live remote publish in this environment. New duplicates or changed source/rules stop the affected case.

VGGT requires the owner's Meta CLA. robomimic's complete `tests/test.sh` and native package validation remain missing, so automatic publication of its candidate is blocked. No CUDA, model training, full-project CI, measured reward or reconstruction-quality improvement is claimed.

## Source and contribution rules

See [evidence.json](evidence.json) for source blob pins, test counts and reproducibility scope. robomimic patch line numbers are excerpt-relative; apply only after checking the full upstream blob and exact context. The complete packet includes that check.

VGGT's [CONTRIBUTING](https://github.com/facebookresearch/vggt/blob/main/CONTRIBUTING.md), [Meta default CONTRIBUTING](https://github.com/facebookresearch/.github/blob/main/CONTRIBUTING.md), [TD-MPC2 CONTRIBUTING](https://github.com/nicklashansen/tdmpc2/blob/main/CONTRIBUTING.md), [robomimic contributing guide](https://github.com/ARISE-Initiative/robomimic/blob/master/docs/miscellaneous/contributing.md), and DreamerV3 README/root tree were reviewed. No explicit tool-use disclosure clause was found in these named guides; that is not an exhaustive or permanent guarantee about all repository discussions and rules.

## Licenses

The VGGT patch remains under the complete [VGGT License](licenses/VGGT-LICENSE.txt), not MIT. The other patches retain their upstream MIT notices in [MIT notices](licenses/MIT-NOTICES.txt). The patches are derivative modifications of the pinned upstream code. Original ownership and applicable restrictions are preserved.
