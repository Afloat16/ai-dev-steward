# Contributing

Keep StewardCheck small, explicit, and usable without a model service. Changes should preserve task-start baselines, non-destructive inspection, honest non-passing states, and a narrow dependency surface.

## Local development

From `tools/stewardcheck` in an activated Python 3.11+ virtual environment:

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
python examples/demo.py
```

Tests create temporary Git repositories, synthetic credentials, and short-lived subprocesses. They do not use model APIs or real credentials. Optional coverage measurement:

```sh
python -m pip install coverage
python -m coverage run -m unittest discover -s tests
python -m coverage report
```

Coverage is a development dependency only. A high percentage does not establish correctness or platform compatibility.

## Pull requests

Include the problem, a regression test, user-visible behavior, and any compatibility/security impact. Keep English and Chinese README behavior descriptions aligned. Reference external designs or specifications in `docs/research.md` and update `THIRD_PARTY.md` if third-party code or dependencies are introduced. Do not import upstream source or rule catalogs without checking their license and preserving required notices.

Avoid network calls, automatic edits, automatic command approval, or new persistent planning files in the default workflow. Use the existing issue and pull request for design discussion. A new warning should explain what requires human review; a new blocker should be testable without claiming semantic certainty.

## Release checklist

Run the complete tests, the temporary-repository demo, and a wheel install in a clean virtual environment. Check CLI help, console and module entrypoints, package version consistency, relative documentation links, included licenses, and source-distribution contents. Confirm the CI matrix rather than assuming local Linux results prove Windows or macOS compatibility. Record measured results, unresolved platform failures, and known limitations. Never present an unrun job as passing.

The initial 0.x Python API and receipt schema are provisional. Document incompatible changes in `CHANGELOG.md`; avoid silently trusting task records created by an incompatible schema. Publish source with reviewable commits. The package directory is independently installable and can be moved into a dedicated repository without depending on parent-repository scripts.
