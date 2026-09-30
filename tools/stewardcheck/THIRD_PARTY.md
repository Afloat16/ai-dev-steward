# References, dependencies, and attribution

Review date: **2026-09-30**.

StewardCheck's implementation, tests, command workflow, packet format, and heuristic patterns are maintained in this package. No implementation files, prompts, test suites, assets, or credential rule catalogs from the surveyed projects are copied or vendored. The references below informed design decisions; they are not runtime dependencies and their maintainers do not endorse this project.

## Conceptual references

| Project | Upstream license reference | Material considered / attribution |
| --- | --- | --- |
| [Repomix — yamadashy and contributors](https://github.com/yamadashy/repomix) | [MIT](https://github.com/yamadashy/repomix/blob/main/LICENSE) | Repository packaging, selection controls, and context/security tradeoffs. |
| [Gitingest — coderamp-labs and contributors](https://github.com/coderamp-labs/gitingest) | [MIT](https://github.com/coderamp-labs/gitingest/blob/main/LICENSE) | Low-friction prompt-friendly codebase extraction. |
| [Aider — Aider-AI and contributors](https://github.com/Aider-AI/aider) | [Apache-2.0](https://github.com/Aider-AI/aider/blob/main/LICENSE.txt) | Terminal coding and Git-aware development workflow. |
| [Cline — Cline Bot Inc. and contributors](https://github.com/cline/cline) | [Apache-2.0](https://github.com/cline/cline/blob/main/LICENSE) | Explicit execution boundaries and reported checkpoint/restore failure modes. |
| [OpenHands — OpenHands and contributors](https://github.com/OpenHands/OpenHands) | [Upstream license](https://github.com/OpenHands/OpenHands/blob/main/LICENSE) | Agent-platform architecture; the repository advertises MIT for community code. Consult upstream terms for any separately licensed components. |
| [Gitleaks — gitleaks and contributors](https://github.com/gitleaks/gitleaks) | [MIT](https://github.com/gitleaks/gitleaks/blob/master/LICENSE) | Specialist secret scanning as a complementary layer, not a borrowed rule set. |
| [pre-commit — pre-commit and contributors](https://github.com/pre-commit/pre-commit) | [MIT](https://github.com/pre-commit/pre-commit/blob/main/LICENSE) | Explicit existing check programs and the distinction between task review and commit hooks. |

See [docs/research.md](docs/research.md) for feature-level source links, issue-report caveats, the observed popularity snapshot, and resulting design choices. Upstream URLs can change; verify upstream licenses again before any future code reuse. License names above describe the inspected references, not a relicensing of their work.

## Interfaces and tooling

The runtime imports only the Python standard library and invokes the installed Git executable. Neither Python nor Git is bundled. Their official documentation is referenced for behavior: [Python subprocess](https://docs.python.org/3/library/subprocess.html), [Git ls-files](https://git-scm.com/docs/git-ls-files), [Git diff](https://git-scm.com/docs/git-diff), and [Git attributes](https://git-scm.com/docs/gitattributes).

[Setuptools](https://github.com/pypa/setuptools) is used for building/installing the package, not as an application runtime dependency. [Coverage.py](https://github.com/nedbat/coveragepy) is an optional development measurement tool. CI uses the separately maintained [actions/checkout](https://github.com/actions/checkout) and [actions/setup-python](https://github.com/actions/setup-python), pinned to specific commits in the workflow. None of these tools is vendored into the package.

The standard MIT license text is included in `LICENSE`. Synthetic credential-shaped test values are assembled from fixture strings and are not usable credentials. Repository/product names are used only for attribution and interoperability context.

## Future contributions

Record the exact source and version of any incorporated third-party material, preserve its required copyright/license notices, and distinguish copied/adapted code from conceptual references. Add new dependencies to package metadata and document their role. Do not copy upstream implementations or rule catalogs and merely rename them.
