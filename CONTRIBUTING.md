# Contributing to AI Dev Steward

This repository maintains two complementary, independently versioned components. Keep discussions in the existing issue or PR and avoid redundant plans or generated report copies.

| Component | Location | Minimum Python | Version source |
| --- | --- | --- | --- |
| Agent skill and read-only tools | `SKILL.md`, `scripts/`, `tests/` | 3.10 | `scripts/steward.py` and skill frontmatter |
| StewardCheck CLI | `tools/stewardcheck/` | 3.11 | `pyproject.toml` and `src/stewardcheck/__init__.py` |

Do not silently raise the skill's Python requirement when modifying the companion CLI. The skill's `audit`, `diff`, `gate`, and `review` remain read-only and do not execute programs found in evidence. StewardCheck executes explicitly declared programs only after `check --run`; it is not a sandbox.

## Run both suites

From the repository root, inside an activated Python 3.11+ virtual environment:

```sh
python -m pip install -e ./tools/stewardcheck
python -B -m unittest discover -s tests -v
python -m unittest discover -s tools/stewardcheck/tests -v
python tools/stewardcheck/examples/demo.py
```

Run these separately: the tests have independent discovery roots. To test only the original skill on Python 3.10, run the first unittest command without installing StewardCheck. Tests use temporary repositories and synthetic evidence, not measured model speedups or production cleanup results.

CI runs the skill and integration suite on Linux Python 3.10/3.13, and the installed CLI on Linux Python 3.11–3.14, macOS 3.13, and Windows 3.13. Inspect actual run results; platform-specific skips must not be described as passing that platform's unsupported features.

## Packaging and performance checks

```sh
python -m pip wheel --no-deps ./tools/stewardcheck --wheel-dir /tmp/stewardcheck-dist
python tools/stewardcheck/examples/benchmark_snapshot.py
```

Use a suitable temporary output directory on your platform. Install the built wheel in a clean virtual environment and rerun the CLI suite without `PYTHONPATH` pointing at the source. Source distributions must contain documentation, notices, tests, and the optional TOML example. Do not assume a PyPI release exists.

The snapshot benchmark is synthetic and reports peak Python-traced allocation, not process RSS or timing. It checks equal fingerprints across text-retaining and metadata-only scans. Do not turn the sample into a general speed or memory guarantee.

## Change checklist

Reproduce the problem, add regression coverage, preserve fail-closed/non-passing behavior, and state compatibility limits. Keep the root and component English/Chinese READMEs aligned, update the relevant component changelog, verify relative links, and preserve original sources and notices. New external references belong in the component's existing research/attribution files, not a copied upstream implementation without license review.

Never weaken a test to hide a failure, mark a missing measurement as verified, silently replace a task contract, or auto-approve checks, cleanup, reset, or merge operations. Existing schema-1 task records keep their pinned policies. Add a documented migration before making an incompatible record change.

See [StewardCheck contribution guidance](tools/stewardcheck/CONTRIBUTING.md) for package-specific details and the [skill playbook](references/playbook.md) for evidence and artifact safety.
