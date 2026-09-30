"""Read-only Git discovery and bounded, symlink-aware workspace snapshots."""

from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
from pathlib import Path, PurePosixPath

from .common import StewardError, digest
from .secrets import findings, sensitive_path, test_metrics

TEXT_LIMIT = 256 * 1024
FILE_LIMIT = 20_000
DEFAULT_SCAN_BYTES = 256 * 1024 * 1024


def git(cwd: Path, *args: str, optional: bool = False) -> bytes:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
    cmd = ["git", "--no-pager", "-c", "core.fsmonitor=false",
           "-c", "core.untrackedCache=false", "-C", str(cwd), *args]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=30, env=env, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise StewardError("Git is unavailable or timed out; install Git and check repository access.") from exc
    if proc.returncode and not optional:
        raise StewardError("Git could not read this repository. Run inside a non-bare Git working tree.")
    return b"" if proc.returncode else proc.stdout


def discover(cwd: Path) -> tuple[Path, Path]:
    root = Path(os.fsdecode(git(cwd, "rev-parse", "--show-toplevel")[:-1])).resolve()
    gitdir = Path(os.fsdecode(git(root, "rev-parse", "--absolute-git-dir")[:-1])).resolve()
    return root, gitdir


def valid_path(value: str) -> None:
    parts = PurePosixPath(value).parts
    if (not parts or value.startswith("/") or "\\" in value
            or any(p in {"..", ".git"} for p in parts)):
        raise StewardError("Unsupported repository path (absolute, backslash, or parent traversal).")


def _read_file(root: Path, name: str, remaining: int) -> tuple[dict | None, str | None, int]:
    valid_path(name)
    path = root / name
    # Never follow a parent symlink, even for a tracked path retained from the baseline.
    for parent in path.relative_to(root).parents:
        candidate = root / parent
        if candidate.is_symlink() or (candidate.exists() and not candidate.is_dir()):
            return {"kind": "unsafe-parent", "sha256": "", "bytes": 0, "mode": 0}, None, 0
    try:
        initial = path.lstat()
    except FileNotFoundError:
        return None, None, 0
    if stat.S_ISLNK(initial.st_mode):
        target = os.fsencode(os.readlink(path))
        return {"kind": "symlink", "sha256": hashlib.sha256(target).hexdigest(),
                "bytes": len(target), "mode": 0}, None, 0
    if stat.S_ISDIR(initial.st_mode):
        return {"kind": "directory", "sha256": "", "bytes": 0, "mode": 0}, None, 0
    if not stat.S_ISREG(initial.st_mode):
        return {"kind": "special", "sha256": "", "bytes": 0, "mode": 0}, None, 0
    if initial.st_size > remaining:
        raise StewardError("Workspace scan byte limit exceeded. Increase --scan-mib at task start.")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    sha = hashlib.sha256()
    data, size = bytearray(), 0
    with os.fdopen(os.open(path, flags), "rb") as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (initial.st_dev, initial.st_ino):
            raise StewardError("A file changed while opening it. Stop concurrent writers and retry.")
        while chunk := stream.read(64 * 1024):
            size += len(chunk)
            if size > remaining:
                raise StewardError("Workspace scan byte limit exceeded.")
            sha.update(chunk)
            if size <= TEXT_LIMIT:
                data.extend(chunk)
        final = os.fstat(stream.fileno())
        if (final.st_size, final.st_mtime_ns, final.st_ctime_ns) != (
                opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns):
            raise StewardError("A file changed during scanning. Stop concurrent writers and retry.")
    info = {"kind": "file", "sha256": sha.hexdigest(), "bytes": size,
            "mode": stat.S_IMODE(initial.st_mode) & 0o111,
            "scan": "oversize" if size > TEXT_LIMIT else "binary",
            "secrets": [], "is_test": False, "assertions": 0, "skips": 0}
    text = None
    if size <= TEXT_LIMIT and b"\0" not in data:
        try:
            text = bytes(data).decode("utf-8")
        except UnicodeDecodeError:
            pass
    if text is not None:
        info["scan"] = "text"
        info["secrets"] = [{k: f[k] for k in ("id", "rule", "line")} for f in findings(text)]
        info.update(test_metrics(name, text))
    return info, text, size


def snapshot(root: Path, known: list[str] | None = None,
             scan_bytes: int = DEFAULT_SCAN_BYTES) -> tuple[dict, dict[str, str]]:
    before_index = git(root, "ls-files", "--stage", "-z")
    head = git(root, "rev-parse", "--verify", "HEAD", optional=True).decode("ascii").strip() or None
    index = {}
    for record in before_index.split(b"\0"):
        if not record:
            continue
        header, raw_name = record.split(b"\t", 1)
        mode, oid, stage = header.decode("ascii").split()
        if stage != "0":
            raise StewardError("Resolve merge conflicts before starting or checking a task.")
        index[os.fsdecode(raw_name)] = {"mode": mode, "oid": oid}
    visible = set(index)
    visible.update(os.fsdecode(n) for n in git(root, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0") if n)
    names = visible | set(known or [])
    if len(names) > FILE_LIMIT:
        raise StewardError(f"Workspace contains more than {FILE_LIMIT} paths. Use a smaller repository.")
    files, texts, consumed = {}, {}, 0
    for name in sorted(names):
        info, text, used = _read_file(root, name, scan_bytes - consumed)
        consumed += used
        if info is not None:
            if index.get(name, {}).get("mode") == "160000":
                info["kind"] = "submodule"
                info["sha256"] = index[name]["oid"]
            files[name] = info
        if text is not None and name in visible and not sensitive_path(name):
            texts[name] = text
    if before_index != git(root, "ls-files", "--stage", "-z") or head != (
            git(root, "rev-parse", "--verify", "HEAD", optional=True).decode("ascii").strip() or None):
        raise StewardError("Git state changed during scanning. Stop concurrent writers and retry.")
    result = {"files": files, "index": index, "head": head}
    result["fingerprint"] = digest(result)
    return result, texts


def unstaged_paths(root: Path) -> set[str]:
    # Even `git diff --name-only` can execute a configured clean/process filter.
    # Read only the filter names, and disable every driver before comparing.
    keys = git(root, "config", "--null", "--name-only", "--get-regexp",
               r"^filter\..*\.(clean|process)$", optional=True)
    drivers = set()
    for raw in keys.split(b"\0"):
        if not raw:
            continue
        key = os.fsdecode(raw)
        if not re.fullmatch(r"filter\.[A-Za-z0-9_.-]+\.(?:clean|process)", key):
            raise StewardError("Unsupported Git filter name; cannot safely compare the index.")
        drivers.add(key.rsplit(".", 1)[0])
    overrides = []
    for driver in sorted(drivers):
        for setting, value in (("clean", ""), ("process", ""), ("required", "false")):
            overrides.extend(["-c", f"{driver}.{setting}={value}"])
    return {os.fsdecode(n) for n in git(root, *overrides, "diff", "--no-ext-diff",
                                       "--no-textconv", "--no-renames", "--name-only", "-z").split(b"\0") if n}

