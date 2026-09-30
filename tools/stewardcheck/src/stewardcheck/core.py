"""Task contracts, static review, and evidence bound to a workspace fingerprint."""

from __future__ import annotations

import copy
from pathlib import Path, PurePosixPath

from . import __version__
from .common import StewardError, any_match, digest, normalize_pattern, utcnow
from .repository import DEFAULT_SCAN_BYTES, discover, snapshot, unstaged_paths
from .runner import run_command
from .secrets import redact, sensitive_path
from .storage import Store

DEFAULT_PROTECTED = ["**/.env", "**/.env.*", "**/*.pem", "**/*.key", "**/.netrc",
                     "**/id_rsa", "**/id_ed25519", ".github/workflows/**",
                     "**/.gitignore", "**/.gitattributes", ".gitmodules", ".stewardcheck.toml"]
CHECK_SURFACES = {"package.json", "pyproject.toml", "pytest.ini", "tox.ini", "setup.cfg",
                  "Makefile", "Cargo.toml", "go.mod", "pom.xml", "build.gradle"}
EXIT_CODES = {"passed": 0, "blocked": 1, "needs-review": 2}


def contract(task: str, *, scope: list[str] | None = None, protect: list[str] | None = None,
             acceptance: list[str] | None = None, commands: list[list[str]] | None = None,
             max_files: int = 20, timeout: float = 120,
             scan_bytes: int = DEFAULT_SCAN_BYTES) -> dict:
    if not isinstance(task, str) or not task.strip() or len(task) > 4000:
        raise StewardError("Task must contain 1 to 4000 characters.")
    if type(max_files) is not int or not 1 <= max_files <= 20_000:
        raise StewardError("--max-files must be between 1 and 20000.")
    if not isinstance(timeout, (int, float)) or not 0 < timeout <= 3600:
        raise StewardError("--timeout must be greater than zero and at most 3600 seconds.")
    if type(scan_bytes) is not int or not 1024 * 1024 <= scan_bytes <= 8192 * 1024 * 1024:
        raise StewardError("--scan-mib must be between 1 and 8192.")
    acceptance, commands = acceptance or [], commands or []
    if len(acceptance) > 20 or any(not isinstance(a, str) or len(a) > 1000 for a in acceptance):
        raise StewardError("Use at most 20 acceptance criteria of up to 1000 characters.")
    if len(commands) > 20:
        raise StewardError("Use at most 20 check commands.")
    for argv in commands:
        if (not isinstance(argv, list) or not argv or len(argv) > 100
                or any(not isinstance(a, str) or not a or len(a) > 8000 or "\0" in a for a in argv)):
            raise StewardError("Each check must be a nonempty argv array of bounded strings.")
    scope = [normalize_pattern(p) for p in (scope or ["**"])]
    protect = [normalize_pattern(p) for p in (DEFAULT_PROTECTED if protect is None else protect)]
    if len(scope) > 50 or len(protect) > 50:
        raise StewardError("Use at most 50 patterns per policy field.")
    return {"task": redact(task.strip()), "scope": scope, "protect": protect,
            "acceptance": [redact(a) for a in acceptance], "commands": commands,
            "max_files": max_files, "timeout": timeout, "scan_bytes": scan_bytes}


def changes(baseline: dict, current: dict) -> list[dict]:
    before, after = baseline["files"], current["files"]
    result = []
    for path in sorted(set(before) | set(after)):
        old, new = before.get(path), after.get(path)
        # Test metrics and scanner versions do not define file identity.
        identity = lambda entry: None if entry is None else (
            entry["sha256"], entry["kind"], entry["mode"], entry["bytes"])
        if identity(old) != identity(new):
            result.append({"path": path,
                           "change": "added" if old is None else "deleted" if new is None else "modified",
                           "before_sha256": old["sha256"] if old else None,
                           "after_sha256": new["sha256"] if new else None,
                           "before_bytes": old["bytes"] if old else 0,
                           "after_bytes": new["bytes"] if new else 0})
    return result


def finding(code: str, severity: str, message: str, path: str | None = None,
            line: int | None = None) -> dict:
    return {"code": code, "severity": severity, "message": message, "path": path, "line": line}


def audit(policy: dict, baseline: dict, current: dict, changed: list[dict],
          unstaged: set[str]) -> list[dict]:
    notes = []
    add = lambda code, level, message, path=None, line=None: notes.append(finding(code, level, message, path, line))
    if not changed:
        add("NO_TASK_CHANGES", "warning", "No working-tree content changes since task start.")
    if policy["scope"] == ["**"]:
        add("UNRESTRICTED_SCOPE", "info", "This task does not restrict file paths.")
    if len(changed) > policy["max_files"]:
        add("CHANGE_BUDGET", "error", f"Changed {len(changed)} files; the task limit is {policy['max_files']}.")
    for change in changed:
        path = change["path"]
        old, new = baseline["files"].get(path, {}), current["files"].get(path, {})
        if not any_match(path, policy["scope"]):
            add("OUTSIDE_SCOPE", "error", "Path is outside the task's allowed scope.", path)
        if any_match(path, policy["protect"]):
            add("PROTECTED_PATH", "error", "Task policy protects this path.", path)
        if PurePosixPath(path).name in {".gitignore", ".gitattributes"}:
            add("DISCOVERY_RULES_CHANGED", "warning", "Ignore or attribute changes require manual review; ignored files are not inspected.", path)
        if PurePosixPath(path).name in CHECK_SURFACES:
            add("CHECK_SURFACE_CHANGED", "warning", "Dependency or check configuration changed; review what the check commands now execute.", path)
        if new and (new["kind"] != "file" or new.get("scan") != "text"):
            add("CONTENT_UNINSPECTED", "warning", "Changed content is non-text, oversized, or a link; review it separately.", path)
        if new.get("kind") == "unsafe-parent":
            add("UNSAFE_PARENT", "error", "A tracked path is now behind a symlink or non-directory parent.", path)
        old_ids = {s["id"] for s in old.get("secrets", [])}
        for secret in new.get("secrets", []):
            if secret["id"] not in old_ids:
                add("POSSIBLE_SECRET", "error", f"New {secret['rule']} pattern; value omitted.", path, secret["line"])
        if old.get("is_test") and not new:
            add("TEST_DELETED", "warning", "An existing test file was deleted.", path)
        elif old.get("is_test") and new.get("is_test") and new["assertions"] < old["assertions"]:
            add("ASSERTIONS_REMOVED", "warning", "Assertion-marker count decreased; review test intent.", path)
        if new.get("skips", 0) > old.get("skips", 0):
            add("TESTS_SKIPPED", "warning", "Test skip/xfail markers increased.", path)
    for path, info in current["files"].items():
        if info["kind"] in {"submodule", "directory", "special", "unsafe-parent"}:
            add("OPAQUE_PATH", "warning", "This path's interior cannot be inspected; it is outside verification coverage.", path)
    old_index, new_index = baseline["index"], current["index"]
    index_changes = {p for p in set(old_index) | set(new_index) if old_index.get(p) != new_index.get(p)}
    for path in sorted(index_changes & unstaged):
        add("PARTIAL_STAGING", "warning", "The index changed, but differs from the checked working-tree file.", path)
    if baseline["head"] != current["head"]:
        add("HEAD_MOVED", "info", "HEAD changed; the task-start content baseline remains in use.")
    return notes


def verdict(notes: list[dict]) -> str:
    if any(n["severity"] == "error" for n in notes):
        return "blocked"
    if any(n["severity"] == "warning" for n in notes):
        return "needs-review"
    return "passed"


class Project:
    def __init__(self, cwd: Path):
        self.root, self.gitdir = discover(cwd)
        self.store = Store(self.gitdir, self.root)

    def start(self, policy: dict, replace: bool = False) -> dict:
        with self.store.locked():
            if (self.store.path.exists() or self.store.path.is_symlink()) and not replace:
                raise StewardError("An active task already exists. Use --replace only to deliberately discard its baseline and receipt.")
            baseline, _ = snapshot(self.root, scan_bytes=policy["scan_bytes"], collect_text=False)
            state = {"schema": 1, "root": str(self.root), "started_at": utcnow(),
                     "contract": policy, "contract_hash": digest(policy),
                     "baseline": baseline, "receipt": None}
            self.store.save(state)
            return {"task": policy["task"], "scope": policy["scope"],
                    "tracked_and_untracked_files": len(baseline["files"]),
                    "baseline_fingerprint": baseline["fingerprint"], "commands": policy["commands"]}

    def check(self, execute: bool = False) -> dict:
        with self.store.locked():
            state = self.store.load()
            policy, baseline = state["contract"], state["baseline"]
            current, _ = snapshot(self.root, list(baseline["files"]), policy["scan_bytes"], collect_text=False)
            changed = changes(baseline, current)
            notes = audit(policy, baseline, current, changed, unstaged_paths(self.root))
            results = []
            if not policy["commands"]:
                notes.append(finding("NO_CHECKS", "warning", "No executable checks were declared; static findings are not a verification pass."))
            elif not execute:
                notes.append(finding("CHECKS_NOT_RUN", "warning", "Checks were not executed. Review the commands, then use check --run."))
            elif verdict(notes) == "blocked":
                notes.append(finding("CHECKS_BLOCKED", "info", "Commands were not executed because static blockers exist."))
            else:
                for argv in policy["commands"]:
                    result = run_command(self.root, argv, policy["timeout"])
                    results.append(result)
                    if result["status"] != "passed":
                        notes.append(finding("CHECK_FAILED", "error", f"Check {len(results)} ended with status {result['status']}."))
                after, _ = snapshot(self.root, list(current["files"]), policy["scan_bytes"], collect_text=False)
                if current["fingerprint"] != after["fingerprint"]:
                    notes.append(finding("WORKSPACE_CHANGED_DURING_CHECKS", "error", "The workspace or index changed during checks. Review those changes, then rerun; results do not certify the new state."))
            receipt = {"schema": 1, "tool": "stewardcheck", "tool_version": __version__, "created_at": utcnow(),
                       "task_started_at": state["started_at"], "task": policy["task"],
                       "scope": policy["scope"], "acceptance_for_human_review": policy["acceptance"],
                       "contract_hash": state["contract_hash"],
                       "baseline_fingerprint": baseline["fingerprint"],
                       "workspace_fingerprint": current["fingerprint"],
                       "baseline_head": baseline["head"], "checked_head": current["head"],
                       "changes": changed, "findings": notes, "checks": results,
                       "declared_checks": len(policy["commands"]),
                       "verdict": verdict(notes), "stale": False,
                       "coverage": "Working-tree task delta; ignored files, submodule interiors, and semantic correctness are not verified."}
            state["receipt"] = receipt
            state["receipt_hash"] = digest(receipt)
            self.store.save(state)
            return receipt

    def report(self) -> dict:
        with self.store.locked():
            state = self.store.load()
            if state["receipt"] is None:
                raise StewardError("No receipt yet. Run stewardcheck check first.")
            if state.get("receipt_hash") != digest(state["receipt"]):
                raise StewardError("Stored receipt is damaged. Run check again.")
            receipt = copy.deepcopy(state["receipt"])
            current, _ = snapshot(self.root, list(state["baseline"]["files"]), state["contract"]["scan_bytes"], collect_text=False)
            if current["fingerprint"] != receipt["workspace_fingerprint"]:
                receipt["stale"] = True
                receipt["findings"].append(finding("STALE_RECEIPT", "warning", "The workspace or index changed after this receipt. Run check again before relying on it."))
                receipt["verdict"] = verdict(receipt["findings"])
            return receipt

    def packet(self, max_bytes: int = 32_000, include: list[str] | None = None) -> str:
        from .render import make_packet

        if not 2048 <= max_bytes <= 1_000_000:
            raise StewardError("--max-bytes must be between 2048 and 1000000.")
        patterns = [normalize_pattern(p) for p in (include or [])]
        with self.store.locked():
            state = self.store.load()
            current, texts = snapshot(self.root, list(state["baseline"]["files"]), state["contract"]["scan_bytes"])
            texts = {p: t for p, t in texts.items() if not sensitive_path(p)}
            return make_packet(state, current, texts, max_bytes, patterns)
