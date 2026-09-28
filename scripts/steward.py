#!/usr/bin/env python3
"""Read-only artifact audit, committed-diff inventory and paired metric gates.

Python 3.10+, standard library only. No delete/move, network or experiment execution.
Outputs JSON (or review Markdown) to stdout; diagnostics go to stderr.
Treat reports as proposals, not cleanup or merge authorization.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import statistics
import subprocess
import sys
from typing import Any

VERSION = "1.1.0"
PROTECTED = (".git", ".agents", ".claude", ".github", "data", "dataset", "datasets",
             "pretrain_models", "checkpoints", "models", "tests", "docs/decisions",
             ".ai/state.md", ".ai/artifacts.json")
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".quarantine"}
KINDS = {"plan", "scratch", "log", "cache", "intermediate"}
CLOSED = {"closed", "superseded", "failed", "abandoned"}
SAFE_SUFFIXES = {".md", ".txt", ".log", ".tmp", ".bak", ".json", ".jsonl", ".csv"}
META = ("dataset", "split", "protocol", "environment", "hardware", "precision", "batch_size")
EXPERIMENT_META = ("training_budget", "measurement", "pairing_unit")
PLAN_NAME = re.compile(r"(?i)(^|[_.-])(plan(?:ning|ing)?)([_.-]|$)")
SHA256 = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def timestamp(value: str) -> datetime:
    require(isinstance(value, str), "timestamp must be a timezone-aware ISO 8601 string")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(dt.tzinfo is not None, "timestamp must include a timezone")
    return dt.astimezone(timezone.utc)


def relative(value: str) -> str:
    require(isinstance(value, str) and bool(value), "path must be a nonempty string")
    p = PurePosixPath(value)
    require(not p.is_absolute() and ".." not in p.parts and "\\" not in value
            and ":" not in value and str(p) == value and value != "."
            and not any(ord(c) < 32 or ord(c) == 127 for c in value)
            and not any(c in value for c in "*?[]"), "unsafe/noncanonical relative path: " + repr(value))
    return value


def beneath(path: str, roots: list[str] | tuple[str, ...]) -> bool:
    return any(path == root or path.startswith(root + "/") for root in roots)


def safe_file(root: Path, rel: str) -> Path:
    p = root
    for part in PurePosixPath(relative(rel)).parts:
        p = p / part
        require(not p.is_symlink(), "symlink is not eligible: " + rel)
    require(p.is_file() and stat.S_ISREG(p.stat().st_mode), "missing/nonregular file: " + rel)
    require(p.stat().st_nlink == 1, "hardlinked file is not eligible: " + rel)
    return p


def secret_path(path: str) -> bool:
    return any(part.lower().startswith(".env") or part.lower() in
               {"secrets", "credentials", ".ssh", ".aws"} for part in PurePosixPath(path).parts)


def read_json(path: Path) -> dict[str, Any]:
    require(not path.is_symlink() and path.is_file(), "JSON input must be a regular, non-symlink file")
    require(path.stat().st_size <= 8 * 1024 * 1024, "JSON input exceeds 8 MiB")
    with path.open("rb") as stream:
        blob = stream.read(8 * 1024 * 1024 + 1)
    require(len(blob) <= 8 * 1024 * 1024, "JSON input exceeds 8 MiB")
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in pairs:
            require(key not in out, "duplicate JSON key: " + key)
            out[key] = value
        return out
    def invalid_constant(value: str) -> None:
        raise ValueError("nonfinite JSON number: " + value)
    data = json.loads(blob.decode("utf-8"), object_pairs_hook=unique,
                      parse_constant=invalid_constant)
    require(isinstance(data, dict), "JSON root must be an object")
    require(type(data.get("schema_version")) is int and data["schema_version"] == 1,
            "schema_version must be 1")
    require(type(data.get("example", False)) is bool, "example must be boolean")
    return data


def git(root: Path, *args: str) -> bytes:
    # Ignore environment overrides that could silently select another repository/index.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GIT_NO_LAZY_FETCH="1",
               GIT_NO_REPLACE_OBJECTS="1", GIT_CONFIG_NOSYSTEM="1")
    result = subprocess.run(["git", "-c", "core.fsmonitor=false", "-c", "diff.ignoreSubmodules=none",
                             "-c", "diff.autoRefreshIndex=false", "-C", str(root), *args],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, env=env)
    require(result.returncode == 0,
            "git failed: " + result.stderr.decode("utf-8", "replace").strip())
    return result.stdout


def nested_repo(root: Path, rel: str) -> bool:
    folder = root
    for part in PurePosixPath(rel).parts[:-1]:
        folder = folder / part
        marker = folder / ".git"
        if marker.exists() or marker.is_symlink():
            return True
    return False


def fingerprint(root: Path, rel: str, limit: int) -> tuple[str, int]:
    path = safe_file(root, rel)
    before = path.stat()
    require(before.st_size <= limit, "hash-budget-exceeded")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        opened = os.fstat(stream.fileno())
        require(stat.S_ISREG(opened.st_mode) and opened.st_nlink == 1, "file type changed")
        blob = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    signature = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns, x.st_ctime_ns)
    require(signature(before) == signature(opened) == signature(after) == signature(path.stat())
            and len(blob) == before.st_size, "artifact changed during audit: " + rel)
    return hashlib.sha256(blob).hexdigest(), len(blob)


def repo_root(path: str) -> Path:
    root = Path(path).resolve()
    actual = Path(os.fsdecode(git(root, "rev-parse", "--show-toplevel")).strip()).resolve()
    require(root == actual, "--root must be the repository root, not a subdirectory")
    return root


def ledger_records(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    require(isinstance(data.get("records"), list), "records must be an array")
    records: dict[str, dict[str, Any]] = {}
    paths: set[str] = set()
    for r in data["records"]:
        require(isinstance(r, dict), "each record must be an object")
        for key in ("id", "path", "kind", "status", "owner"):
            require(isinstance(r.get(key), str) and bool(r[key].strip()), "record missing " + key)
        require(r["id"] not in records and r["path"] not in paths, "duplicate record id/path")
        relative(r["path"])
        for key in ("pinned", "running", "reproducible"):
            require(type(r.get(key)) is bool, "record requires explicit boolean " + key)
        deps = r.get("depends_on")
        require(isinstance(deps, list) and all(isinstance(x, str) for x in deps),
                "depends_on must be an array of artifact IDs")
        if r.get("expires_at") is not None:
            timestamp(r["expires_at"])
        records[r["id"]] = r
        paths.add(r["path"])
    for r in records.values():
        require(all(dep in records for dep in r["depends_on"]), "unknown dependency in " + r["id"])
    return records


def audit(root: Path, data: dict[str, Any], now: datetime, max_files: int = 20000,
          scope: list[str] | None = None) -> dict[str, Any]:
    require(type(data.get("example", False)) is bool, "example must be boolean")
    require(type(max_files) is int and max_files > 0, "max_files must be positive")
    records = ledger_records(data)
    roots = data.get("artifact_roots", [".ai/scratch", "runs", "results", "plans", "planning", "planing"])
    extra = data.get("protected_paths", [])
    require(isinstance(roots, list) and isinstance(extra, list), "path policies must be arrays")
    for item in roots + extra + (scope or []):
        relative(item)
    protected = tuple(PROTECTED) + tuple(extra)
    tracked = set(filter(None, os.fsdecode(git(root, "ls-files", "-z", "--cached")).split("\0")))
    # A staged deletion must not make a committed file appear disposable.
    head = git(root, "rev-parse", "--revs-only", "HEAD").decode().strip()
    head_submodules = []
    if head:
        for item in git(root, "ls-tree", "-r", "-z", head).split(b"\0"):
            if item:
                metadata, path = item.split(b"\t", 1)
                tracked.add(os.fsdecode(path))
                if metadata.startswith(b"160000 "):
                    head_submodules.append(os.fsdecode(path))
    index = git(root, "ls-files", "--stage", "-z")
    submodules = [os.fsdecode(x.split(b"\t", 1)[1]) for x in index.split(b"\0") if x.startswith(b"160000 ")]
    protected += tuple(submodules + head_submodules)
    rows: dict[str, dict[str, Any]] = {}
    possible: set[str] = set()
    budget = 32 * 1024 * 1024
    for key, r in records.items():
        rel = r["path"]
        blockers: list[str] = []
        if data.get("example", False):
            blockers.append("example-input-not-real-evidence")
        if beneath(rel, protected) or secret_path(rel):
            blockers.append("protected-path")
        if nested_repo(root, rel):
            blockers.append("nested-repository-requires-separate-audit")
        if not beneath(rel, roots) or Path(rel).suffix.lower() not in SAFE_SUFFIXES:
            blockers.append("outside-safe-artifact-scope")
        if scope and not beneath(rel, scope):
            blockers.append("outside-selected-scan-scope")
        if r["kind"] not in KINDS or r["status"] not in CLOSED:
            blockers.append("retained-kind-or-open-status")
        if r["pinned"] or r["running"] or not r["reproducible"]:
            blockers.append("pinned-running-or-not-reproducible")
        expires = timestamp(r["expires_at"]) if r.get("expires_at") else None
        if expires is None or expires > now:
            blockers.append("not-expired")
        closed = timestamp(r["closed_at"]) if r.get("closed_at") else None
        if closed is None or closed > now or (expires is not None and expires < closed):
            blockers.append("missing-or-invalid-close-time")
        reviewed = timestamp(r["reviewed_at"]) if r.get("reviewed_at") else None
        if reviewed is None or not now - timedelta(days=7) <= reviewed <= now or (closed and reviewed < closed):
            blockers.append("missing-stale-or-invalid-reference-review")
        if r.get("references_checked") is not True:
            blockers.append("references-not-explicitly-checked")
        if not isinstance(r.get("reproduce_command"), str) or not r["reproduce_command"].strip():
            blockers.append("missing-reproduction-recipe")
        expected = r.get("content_sha256")
        if not isinstance(expected, str) or not SHA256.fullmatch(expected):
            blockers.append("missing-or-invalid-content-sha256")
        if rel in tracked:
            blockers.append("tracked-file-requires-separate-pr")
        size = None
        digest = None
        try:
            size = safe_file(root, rel).stat().st_size
            if not blockers:
                digest, read_bytes = fingerprint(root, rel, min(budget, 1024 * 1024))
                budget -= read_bytes
                if digest != expected:
                    blockers.append("content-hash-mismatch")
        except (ValueError, OSError) as exc:
            blockers.append(str(exc))
        rows[key] = {"id": key, "path": rel, "bytes": size, "blockers": blockers}
        if digest is not None:
            rows[key]["sha256"] = digest
        if not blockers:
            possible.add(key)
    # Hash/freshness failures are retained roots too, so their producers remain safe.
    live = set(records) - possible
    pending = list(live)
    while pending:
        for dep in records[pending.pop()]["depends_on"]:
            if dep not in live:
                live.add(dep)
                pending.append(dep)
    for key, row in rows.items():
        if key in possible and key in live:
            row["blockers"].append("referenced-by-retained-artifact")
        row["decision"] = "KEEP" if row["blockers"] else "QUARANTINE_REVIEW"
    discovery: list[str] = []
    plan_files: set[str] = {r["path"] for r in records.values() if r["kind"] == "plan"}
    scanned = entries = 0
    excluded: set[str] = set()
    registered = {r["path"] for r in records.values()}
    starts = [root]
    if scope:
        selected = sorted(set(scope), key=lambda x: (len(PurePosixPath(x).parts), x))
        unique: list[str] = []
        for rel in selected:
            if not beneath(rel, unique):
                unique.append(rel)
        starts = []
        for rel in unique:
            folder = root
            for part in PurePosixPath(rel).parts:
                folder /= part
                require(not folder.is_symlink(), "scope cannot traverse symlinks")
            require(folder.is_dir(), "scope must be an existing directory: " + rel)
            require(not beneath(rel, protected) and not secret_path(rel)
                    and not nested_repo(root, rel + "/placeholder"), "protected/nested scope: " + rel)
            starts.append(folder)
    def walk_error(exc: OSError) -> None:
        raise exc
    for start in starts:
        for folder, dirs, files in os.walk(start, followlinks=False, onerror=walk_error):
            entries += len(dirs) + len(files)
            require(entries <= max_files * 4, "inventory entry limit reached; use --scope")
            kept = []
            for name in sorted(dirs):
                p = Path(folder) / name
                rel = p.relative_to(root).as_posix()
                marker = p / ".git"
                if (name in SKIP_DIRS or beneath(rel, protected) or secret_path(rel)
                        or p.is_symlink() or marker.exists() or marker.is_symlink()):
                    excluded.add(rel)
                else:
                    kept.append(name)
            dirs[:] = kept
            for name in sorted(files):
                scanned += 1
                require(scanned <= max_files, "inventory file limit reached; use --scope")
                rel = (Path(folder) / name).relative_to(root).as_posix()
                if not secret_path(rel) and not beneath(rel, protected):
                    if PLAN_NAME.search(name):
                        plan_files.add(rel)
                    if rel not in registered and (beneath(rel, roots) or PLAN_NAME.search(name)
                            or re.search(r"(?i)(^|[_.-])(scratch|temp|tmp)([_.-]|$)", name)):
                        discovery.append(rel)
    hashes: dict[str, list[str]] = defaultdict(list)
    for row in rows.values():
        if row["decision"] == "QUARANTINE_REVIEW":
            hashes[row["sha256"]].append(row["path"])
    return {"schema_version": 1, "tool_version": VERSION, "mode": "READ_ONLY", "as_of": now.isoformat(),
            "status": "EXAMPLE_ONLY" if data.get("example", False) else "AUDIT_COMPLETE",
            "records": list(rows.values()), "unregistered_review_only": sorted(discovery),
            "plan_consolidation_review": [{"path": x, "tracked": x in tracked} for x in sorted(plan_files)],
            "plan_policy": "Name matches are discovery hints, not semantic duplicates. Reuse one issue/PR/state; preserve unique decisions before consolidation.",
            "duplicate_hints": [v for v in hashes.values() if len(v) > 1],
            "scanned_files": scanned, "scanned_entries": entries, "scope": scope or ["."],
            "excluded_directories": sorted(excluded),
            "candidate_bytes_not_reclaimed": sum(r["bytes"] for r in rows.values() if r["decision"] == "QUARANTINE_REVIEW"),
            "limitations": "Registry declarations only; external/dynamic references and running jobs need independent verification. No file content was changed; no cleanup authorized."}


def resolve_commit(root: Path, ref: str) -> str:
    require(bool(ref) and not ref.startswith("-"), "invalid revision")
    return git(root, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}").decode().strip()


def working_changes(root: Path) -> dict[str, Any]:
    chunks = git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignore-submodules=none").split(b"\0")
    rows = []
    i = 0
    while i < len(chunks):
        item = chunks[i]
        i += 1
        if not item:
            continue
        code, path = item[:2].decode("ascii"), os.fsdecode(item[3:])
        row = {"status": code, "path": path}
        if "R" in code or "C" in code:
            require(i < len(chunks) and bool(chunks[i]), "invalid git status rename record")
            row["original_path"] = os.fsdecode(chunks[i])
            i += 1
        rows.append(row)
    return {"files": rows, "dirty": bool(rows),
            "ignored_files_included": False,
            "note": "Ignored files require the separate artifact audit; untracked contents are not read."}


def diff_report(root: Path, base: str, head: str) -> dict[str, Any]:
    b, h = resolve_commit(root, base), resolve_commit(root, head)
    ancestors = git(root, "merge-base", "--all", b, h).decode().split()
    require(len(ancestors) == 1, "no unique merge base; choose an explicit review baseline manually")
    raw = git(root, "diff", "--no-ext-diff", "--no-textconv", "--no-renames", "--numstat", "-z",
              ancestors[0], h, "--")
    files = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        added, deleted, path = record.split(b"\t", 2)
        name = os.fsdecode(path)
        lower = name.lower()
        if lower.startswith(("tests/", "test/")) or Path(lower).name.startswith("test"):
            group = "tests"
        elif lower.endswith((".md", ".rst")):
            group = "docs"
        elif lower.startswith((".ai/", "runs/", "results/")):
            group = "artifacts"
        elif lower.endswith((".json", ".yaml", ".yml", ".toml", ".ini")):
            group = "configuration"
        else:
            group = "implementation-review-needed"
        binary = added == b"-"
        files.append({"path": name, "group_hint": group, "binary": binary,
                      "added": None if binary else int(added),
                      "deleted": None if binary else int(deleted)})
    work = working_changes(root)
    lines = sum((f["added"] or 0) + (f["deleted"] or 0) for f in files)
    return {"schema_version": 1, "base": b, "head": h, "merge_base": ancestors[0],
            "scope": "committed changes from merge-base to head; renames counted as delete/add",
            "working_tree_dirty": work["dirty"], "working_tree": work,
            "files": files, "changed_lines": lines, "groups": dict(Counter(f["group_hint"] for f in files)),
            "split_warning": len(files) > 15 or lines > 400,
            "note": "Size thresholds are adjustable review heuristics, not correctness gates. Inspect staged, unstaged, ignored and untracked work separately."}


def finite(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def provenance_gaps(data: dict[str, Any]) -> list[str]:
    gaps = []
    for label in ("baseline", "candidate"):
        run = data[label]
        for key in EXPERIMENT_META + ("command", "raw_results"):
            if not isinstance(run.get(key), str) or not run[key].strip():
                gaps.append(label + ": missing " + key)
        value = run.get("config_sha256")
        if not isinstance(value, str) or not SHA256.fullmatch(value):
            gaps.append(label + ": missing/invalid config_sha256")
        if "dirty_patch_sha256" not in run or (run["dirty_patch_sha256"] is not None and
                (not isinstance(run["dirty_patch_sha256"], str) or not SHA256.fullmatch(run["dirty_patch_sha256"]))):
            gaps.append(label + ": declare dirty_patch_sha256 (null only for clean runs)")
    return gaps


def compare(data: dict[str, Any]) -> tuple[dict[str, Any], int]:
    require(type(data.get("example", False)) is bool, "example must be boolean")
    b, c, gates = data.get("baseline"), data.get("candidate"), data.get("gates")
    require(all(isinstance(x, dict) and x for x in (b, c, gates)), "baseline/candidate/gates must be nonempty objects")
    minimum = data.get("min_pairs", 5)
    require(type(minimum) is int and minimum >= 2, "min_pairs must be an integer >= 2")
    for run in (b, c):
        require(isinstance(run.get("commit"), str) and bool(re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", run["commit"])),
                "pin a full Git commit hash")
        for key in META:
            if key == "batch_size":
                require(type(run.get(key)) is int and run[key] > 0, "batch_size must be a positive integer")
            else:
                require(isinstance(run.get(key), str) and bool(run[key].strip()), "missing context: " + key)
        seeds = run.get("seeds")
        require(isinstance(seeds, list) and all(type(x) is int for x in seeds)
                and len(set(seeds)) == len(seeds), "seeds must be unique integers")
        require(isinstance(run.get("metrics"), dict) and run["metrics"], "metrics must be a nonempty object")
    mismatch = [key for key in META + EXPERIMENT_META if b.get(key) != c.get(key)]
    if b["seeds"] != c["seeds"]:
        mismatch.append("seeds/order")
    if mismatch:
        return {"status": "INCOMPARABLE", "mismatches": mismatch}, 2
    require(set(b["metrics"]) == set(c["metrics"]) == set(gates), "all metrics must exist in both runs and have an explicit gate")
    gaps = provenance_gaps(data)
    rows = []
    insufficient = len(b["seeds"]) < minimum
    for name, rule in gates.items():
        require(isinstance(rule, dict) and rule.get("direction") in ("lower", "higher"), "invalid gate direction")
        require(not (set(rule) - {"direction", "require_each_pair", "max_regression_abs", "max_regression_pct", "min_improvement_abs", "min_improvement_pct"}), "unknown gate field; check threshold spelling")
        limits = {key: rule[key] for key in ("max_regression_abs", "max_regression_pct", "min_improvement_abs", "min_improvement_pct") if key in rule}
        require(bool(limits) and all(finite(v) and v >= 0 for v in limits.values()), "gate thresholds must be finite nonnegative numbers")
        require(type(rule.get("require_each_pair", True)) is bool, "require_each_pair must be boolean")
        arrays = []
        units = []
        for run in (b, c):
            metric = run["metrics"][name]
            require(isinstance(metric, dict) and isinstance(metric.get("unit"), str) and metric["unit"], "metric requires a unit")
            values = metric.get("values")
            require(isinstance(values, list) and len(values) == len(run["seeds"]) and all(finite(v) for v in values),
                    "metric values must be finite, one per paired seed")
            arrays.append(values)
            units.append(metric["unit"])
        require(units[0] == units[1], "metric units differ: " + name)
        if len(arrays[0]) < minimum:
            rows.append({"metric": name, "status": "INSUFFICIENT_EVIDENCE"})
            continue
        x, y = arrays
        sign = 1 if rule["direction"] == "higher" else -1
        mb, mc = statistics.mean(x), statistics.mean(y)
        delta = sign * (mc - mb)
        pct = None if mb == 0 else delta / abs(mb) * 100
        pairs = [sign * (v - u) for u, v in zip(x, y)]
        require(all(finite(v) for v in [mb, mc, delta] + pairs) and (pct is None or finite(pct)), "derived metric overflow")
        failures = []
        for key, limit in limits.items():
            value = pct if key.endswith("pct") else delta
            threshold = -limit if key.startswith("max_regression") else limit
            if value is None:
                failures.append(key + ": undefined for zero baseline; use absolute gate")
                insufficient = True
            elif value + 1e-12 < threshold:
                failures.append(key)
            if rule.get("require_each_pair", True) and key.startswith("max_regression"):
                for i, change in enumerate(pairs):
                    value = (None if x[i] == 0 else change / abs(x[i]) * 100) if key.endswith("pct") else change
                    if value is None:
                        failures.append("zero-baseline-pair:" + str(b["seeds"][i]))
                        insufficient = True
                    elif value + 1e-12 < -limit:
                        failures.append("regressing-pair:" + str(b["seeds"][i]))
        rows.append({"metric": name, "unit": units[0], "n_pairs": len(x),
                     "baseline_mean": mb, "candidate_mean": mc,
                     "baseline_stdev": statistics.stdev(x), "candidate_stdev": statistics.stdev(y),
                     "improvement_abs": delta, "improvement_pct": pct,
                     "paired_improvement_stdev": statistics.stdev(pairs), "failures": failures,
                     "status": "GATE_FAIL" if failures else "NUMERIC_PASS"})
    status = "INSUFFICIENT_EVIDENCE" if insufficient else ("GATE_FAIL" if any(r.get("failures") for r in rows) else "NUMERIC_PASS")
    numeric_status = status
    if gaps and status == "NUMERIC_PASS":
        status = "UNVERIFIED_PROVENANCE"
    if data.get("example", False):
        status = "EXAMPLE_ONLY"
    return {"schema_version": 1, "status": status, "numeric_status": numeric_status, "metrics": rows,
            "example_input": data.get("example", False), "provenance_gaps": gaps,
            "note": "Numeric checks only, not statistical significance, correctness or merge approval. Values and metadata are caller-supplied; provenance requires independent review."}, (2 if insufficient or status in ("EXAMPLE_ONLY", "UNVERIFIED_PROVENANCE") else 1 if status == "GATE_FAIL" else 0)


def review_report(root: Path, base: str, head: str, data: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Check declared traceability and ablation coverage; never run supplied commands."""
    diff = diff_report(root, base, head)
    metrics, metric_code = compare(data)
    gaps: list[str] = []
    if data["baseline"]["commit"] != diff["base"] or data["candidate"]["commit"] != diff["head"]:
        gaps.append("evidence commits do not match the pinned review range")
    if diff["base"] != diff["merge_base"]:
        gaps.append("base advanced beyond the fork point; select an explicit, tested baseline")
    if diff["working_tree_dirty"]:
        gaps.append("uncommitted/untracked work is not covered by the committed review")
    if not diff["files"]:
        gaps.append("no committed changes in review range")
    if metric_code:
        gaps.append("metric gate: " + metrics["status"])
    for label in ("baseline", "candidate"):
        if data[label].get("dirty_patch_sha256") is not None:
            gaps.append(label + " was measured with a dirty patch; commit and remeasure for commit-only review")
    changes = data.get("changes", [])
    require(isinstance(changes, list), "changes must be an array")
    touched = {f["path"] for f in diff["files"]}
    mapped: set[str] = set()
    ids: set[str] = set()
    factors: set[str] = set()
    kinds = {"contract", "refactor", "algorithm", "runtime", "data", "evaluation", "hygiene", "docs"}
    for change in changes:
        require(isinstance(change, dict), "change must be an object")
        cid = change.get("id")
        require(isinstance(cid, str) and bool(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", cid)), "invalid change id")
        require(cid not in ids, "duplicate change id: " + cid)
        ids.add(cid)
        require(change.get("kind") in kinds, "unknown change kind: " + cid)
        paths = change.get("files")
        require(isinstance(paths, list) and paths and all(isinstance(x, str) for x in paths), "change requires files: " + cid)
        mapped.update(paths)
        for key in ("hypothesis", "rollback"):
            if not isinstance(change.get(key), str) or not change[key].strip():
                gaps.append(cid + ": missing " + key)
        invariants = change.get("invariants")
        if not isinstance(invariants, list) or not invariants or not all(isinstance(x, str) and x.strip() for x in invariants):
            gaps.append(cid + ": missing invariants/behavior contract")
        tests = change.get("tests", [])
        require(isinstance(tests, list), "tests must be an array: " + cid)
        if not tests:
            gaps.append(cid + ": no test evidence")
        for test in tests:
            require(isinstance(test, dict), "test entry must be an object")
            if test.get("status") != "passed" or any(not isinstance(test.get(k), str) or not test[k].strip() for k in ("command", "evidence")):
                gaps.append(cid + ": test not passed or missing command/evidence")
        deps = change.get("depends_on", [])
        require(isinstance(deps, list) and all(isinstance(x, str) for x in deps), "change depends_on must be an array")
        if change["kind"] in {"algorithm", "runtime", "data"}:
            factors.add(cid)
    for change in changes:
        require(all(dep in ids for dep in change.get("depends_on", [])), "unknown change dependency")
    # Kahn's algorithm avoids recursive depth limits for a large change map.
    remaining = {c["id"]: set(c.get("depends_on", [])) for c in changes}
    order = []
    while remaining:
        ready = sorted(cid for cid, deps in remaining.items() if not deps)
        require(bool(ready), "cyclic change dependencies; split into reviewable units")
        order.extend(ready)
        for cid in ready:
            del remaining[cid]
        for deps in remaining.values():
            deps.difference_update(ready)
    unmapped, stale = sorted(touched - mapped), sorted(mapped - touched)
    if unmapped:
        gaps.append("changed files missing from the logical change map")
    if stale:
        gaps.append("change map contains files outside the pinned diff")
    required: set[frozenset[str]] = set()
    if factors:
        required = {frozenset(), frozenset(factors)} | {frozenset([x]) for x in factors}
    interactions = data.get("required_interactions", [])
    require(isinstance(interactions, list), "required_interactions must be an array")
    for combination in interactions:
        require(isinstance(combination, list) and len(combination) >= 2 and
                all(isinstance(x, str) and x in factors for x in combination) and len(set(combination)) == len(combination),
                "invalid required interaction")
        required.add(frozenset(combination))
    ablations = data.get("ablations", [])
    require(isinstance(ablations, list), "ablations must be an array")
    seen: set[frozenset[str]] = set()
    measured: set[frozenset[str]] = set()
    for row in ablations:
        require(isinstance(row, dict), "ablation must be an object")
        items = row.get("factors")
        require(isinstance(items, list) and all(isinstance(x, str) and x in factors for x in items)
                and len(set(items)) == len(items), "ablation references unknown/duplicate factors")
        key = frozenset(items)
        require(key not in seen, "duplicate ablation combination")
        seen.add(key)
        valid = (row.get("status") == "measured" and isinstance(row.get("evidence"), str)
                 and bool(row["evidence"].strip()) and isinstance(row.get("commit"), str)
                 and bool(COMMIT.fullmatch(row["commit"])))
        if valid and not key:
            valid = row["commit"] == diff["base"]
        if valid and key == frozenset(factors) and factors:
            valid = row["commit"] == diff["head"]
        if valid:
            measured.add(key)
    missing = sorted((sorted(x) for x in required - measured), key=lambda x: (len(x), x))
    if missing:
        gaps.append("missing baseline/single-factor/full-combination/requested-interaction evidence")
    if data.get("example", False):
        status = "EXAMPLE_ONLY"
    else:
        status = "NEEDS_REVIEW" if gaps else "CHECKS_PASS"
    result = {"schema_version": 1, "tool_version": VERSION, "status": status,
              "diff": diff, "metrics": metrics, "changes": changes, "reading_order": order,
              "unmapped_files": unmapped, "out_of_scope_files": stale,
              "missing_ablations": missing, "ablations": ablations, "gaps": gaps,
              "limitations": "Checks cover declared structure and numeric gates only. Commands are not executed; evidence pointers, single-factor outcomes and causality are not independently verified. CHECKS_PASS is not merge approval."}
    return result, 0 if status == "CHECKS_PASS" else 2


def markdown_review(result: dict[str, Any]) -> str:
    def text(value: Any) -> str:
        out = str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        out = out.replace("\n", " / ").replace("\r", " ")
        for char in "\\`*_{}[]()|#":
            out = out.replace(char, "\\" + char)
        return out
    diff = result["diff"]
    lines = ["# AI Dev Steward 审查包", "", "状态：" + text(result["status"]), "",
             "基线：" + text(diff["base"]), "候选：" + text(diff["head"]),
             "共同祖先：" + text(diff["merge_base"]), "",
             "## 逻辑改动与阅读顺序", "", " → ".join(map(text, result["reading_order"])) or "未提供", ""]
    for c in result["changes"]:
        lines += ["### " + text(c["id"]) + "（" + text(c["kind"]) + "）",
                  "文件：" + ", ".join(map(text, c["files"])),
                  "假设：" + text(c.get("hypothesis", "未提供")),
                  "不变量：" + text(c.get("invariants", [])),
                  "回滚：" + text(c.get("rollback", "未提供"))]
        for test in c.get("tests", []):
            lines.append("测试声明：" + text(test.get("status")) + "；" + text(test.get("command")) + "；证据：" + text(test.get("evidence")))
        lines.append("")
    lines += ["## 指标门槛", "", text(result["metrics"]["status"]), ""]
    for row in result["metrics"].get("metrics", []):
        lines.append("- " + text(row["metric"]) + "：" + text(row["status"]) + "; baseline=" + text(row.get("baseline_mean")) + "; candidate=" + text(row.get("candidate_mean")) + "; " + text(row.get("unit", "")))
    for gap in result["metrics"].get("provenance_gaps", []):
        lines.append("- " + text(gap))
    lines += ["", "## 消融声明", ""]
    for row in result["ablations"]:
        lines.append("- " + text(" + ".join(row["factors"]) or "baseline") + "：" + text(row.get("status", "未验证")) + "；" + text(row.get("evidence", "未提供")))
    lines += ["", "缺失组合：" + text(result["missing_ablations"]), "", "## 风险与缺口", ""]
    lines.extend("- " + text(gap) for gap in result["gaps"])
    lines += ["", "未映射文件：" + text(result["unmapped_files"]),
              "范围外映射：" + text(result["out_of_scope_files"]),
              "未提交工作：" + text(diff["working_tree"]["files"]), "", text(result["limitations"])]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("audit", help="read-only inventory; no automatic deletion")
    a.add_argument("--root", default=".")
    a.add_argument("--ledger", help="repository-relative JSON registry; default .ai/artifacts.json when present")
    a.add_argument("--as-of", help="explicit timezone-aware audit timestamp")
    a.add_argument("--max-files", type=int, default=20000)
    a.add_argument("--scope", action="append", help="limit to a repository-relative directory; repeatable")
    d = sub.add_parser("diff", help="committed merge-base diff inventory")
    d.add_argument("--root", default=".")
    d.add_argument("--base", required=True)
    d.add_argument("--head", default="HEAD")
    g = sub.add_parser("gate", help="paired metrics: 0 numeric pass, 1 regression, 2 invalid/insufficient")
    g.add_argument("--input", required=True)
    r = sub.add_parser("review", help="check traceability and print one PR-ready review packet")
    r.add_argument("--root", default=".")
    r.add_argument("--base", required=True)
    r.add_argument("--head", default="HEAD")
    r.add_argument("--input", required=True)
    r.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    try:
        code = 0
        if args.command == "audit":
            root = repo_root(args.root)
            path = args.ledger or ".ai/artifacts.json"
            if args.ledger or (root / path).exists() or (root / path).is_symlink():
                data = read_json(safe_file(root, path))
            else:
                data = {"schema_version": 1, "records": []}
            require(args.max_files > 0, "--max-files must be positive")
            result = audit(root, data, timestamp(args.as_of) if args.as_of else datetime.now(timezone.utc), args.max_files, args.scope)
            code = 2 if result["status"] == "EXAMPLE_ONLY" else 0
        elif args.command == "diff":
            result = diff_report(repo_root(args.root), args.base, args.head)
        elif args.command == "review":
            result, code = review_report(repo_root(args.root), args.base, args.head, read_json(Path(args.input)))
        else:
            result, code = compare(read_json(Path(args.input)))
        if args.command == "review" and args.format == "markdown":
            print(markdown_review(result), end="")
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False))
        return code
    except (ValueError, OSError, TypeError, OverflowError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "ERROR", "message": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
