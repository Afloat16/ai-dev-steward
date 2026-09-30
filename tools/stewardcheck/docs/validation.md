# Validation records

## 0.2.0 — 2026-09-30

Local environment: Linux, CPython 3.13.5, Git 2.47.3.

- 125 unit/integration tests passed, including 34 new tests with additional parameterized invalid-config cases.
- Coverage.py 7.13.3 measured 94% rounded combined statement/branch coverage: 719 statements, 34 missed statements, 284 branches, 25 partial branches. Config and bounded-file helper coverage was 100% in this run; percentages are not correctness or security proofs.
- Reproduced the 0.1.0 FIFO-state hang in an isolated subprocess stopped after two seconds. New regression tests require state/config FIFOs to return an operational error within a subprocess deadline.
- Built the 0.2.0 wheel with setuptools 82.0.1 and wheel 0.46.3, installed it with no dependencies into a fresh virtual environment, and reran all 125 tests successfully without a source PYTHONPATH.
- The existing isolated demo still verified a passing check, stale receipt, and out-of-scope blocker without executing checks after the blocker.

### Cross-platform read regression

The first PR run passed on Linux and macOS but failed on Windows because the new reader compared `lstat` and `fstat` metadata as interchangeable. CPython's Windows pathname implementation may preserve creation time in `st_ctime`, while descriptor queries report metadata-change time; synthesized permission bits can also differ. The reader now checks full metadata separately within each API and retains cross-API device/inode, file type, size, modification-time, and actual read-length validation. Seven additional regression tests exercise valid representation differences and rejected mutations; no Windows failure was suppressed by skipping a test. Final cross-platform outcomes are recorded in the PR's actual CI runs.

### Synthetic snapshot allocation comparison

Run `python examples/benchmark_snapshot.py` from the installed package checkout. A temporary repository contains 128 text files of 65,536 bytes each (8 MiB total). Both modes hash and scan the same files and produce identical fingerprints.

| Mode | Peak Python-traced allocation | Retained source files |
| --- | ---: | ---: |
| `collect_text=True` | 8,627,752 bytes | 128 |
| `collect_text=False` | 360,564 bytes | 0 |

These are `tracemalloc` measurements in the local environment, not process RSS, elapsed-time measurements, a production benchmark, or a guarantee for arbitrary repositories. The metadata-only mode removes unnecessary retained text; it does not cache or skip hashing. Context packet generation intentionally still retains eligible source text.

The repository workflow runs the original skill suite separately on Linux Python 3.10 and 3.13 and StewardCheck on Linux Python 3.11–3.14, macOS 3.13, and Windows 3.13. Read actual GitHub Actions outcomes rather than inferring success from this configuration. Platform-specific tests skip unsupported filesystem/process features.

---

# Initial validation record

Date: 2026-09-30. Package version: 0.1.0.

## Locally executed

Environment: Linux, CPython 3.13.5, Git 2.47.3.

- 91 unit/integration tests passed against the source package.
- Coverage.py measured 93% combined statement/branch coverage: 647 statements, 35 missed statements, 244 branches, 26 partial branches. This percentage is rounded and is not a correctness guarantee.
- A wheel was built with setuptools, installed without runtime dependencies into a fresh virtual environment, and all 91 tests passed against that installed package.
- The console entrypoint reported `stewardcheck 0.1.0`; the module entrypoint is covered by a regression test.
- The isolated demo ran a real unittest command and verified `passed`, stale `needs-review`, and `blocked` with no execution after an out-of-scope edit.

Reproduction from the package directory:

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
python examples/demo.py
python -m pip install coverage
python -m coverage run -m unittest discover -s tests
python -m coverage report
```

Coverage is optional development tooling, not a runtime dependency. Test credentials are synthetic strings and test repositories are temporary.

## Platform and evidence limits

The local measurements above apply only to the stated Linux environment. The repository workflow defines Linux Python 3.11–3.14, macOS Python 3.13, and Windows Python 3.13 jobs; their actual run results, not the matrix definition, establish CI outcomes. Platform-specific tests explicitly skip unsupported filesystem/process features.

No model-provider integration, production deployment, large-monorepo benchmark, user study, independent security audit, or proof of semantic correctness was performed. Upstream issue reports in the research survey were not independently reproduced. The local Git clean/process-filter regression is an independently constructed fixture for this package's own behavior.
