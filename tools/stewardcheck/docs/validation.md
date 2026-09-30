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
