"""Prepare hash-pinned utility sources and run the selected regression tests."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
MAX_SOURCE_BYTES = 1_048_576


def git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def write_or_verify(path: Path, content: bytes) -> None:
    """Never overwrite a different existing source file."""
    if path.is_symlink():
        raise ValueError(f"Refusing a source-file symlink: {path}")
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError(f"Existing file differs from pinned/generated content: {path}")
    else:
        path.write_bytes(content)


def prepare(record: dict, offline: bool) -> Path:
    slug = record["slug"]
    repo = record["project"]
    commit = record["source_commit"]
    expected_sha = record["source_blob_sha"]
    source_path = PurePosixPath(record["source_path"])
    if not re.fullmatch(r"[a-z0-9-]+", slug):
        raise ValueError("Invalid case slug")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("Invalid repository identifier")
    if any(not re.fullmatch(r"[0-9a-f]{40}", value) for value in (commit, expected_sha)):
        raise ValueError("Source identifiers must be full Git hashes")
    if source_path.is_absolute() or ".." in source_path.parts or "\\" in str(source_path):
        raise ValueError("Unsafe source path")
    case = ROOT / "cases" / slug
    if not case.is_dir() or not case.resolve().is_relative_to(ROOT):
        raise ValueError(f"Missing or unsafe case directory: {case}")
    before = case / "before.py"
    if before.is_symlink():
        raise ValueError("Refusing a source-file symlink")
    if before.exists():
        raw = before.read_bytes()
    elif offline:
        raise FileNotFoundError(f"Offline source missing: {before}")
    else:
        url = f"https://raw.githubusercontent.com/{repo}/{commit}/{quote(str(source_path), safe='/')}"
        request = Request(url, headers={"User-Agent": "pinned-regression-reproducer"})
        with urlopen(request, timeout=30) as response:
            raw = response.read(MAX_SOURCE_BYTES + 1)
    if len(raw) > MAX_SOURCE_BYTES or git_blob_sha(raw) != expected_sha:
        raise ValueError(f"Source size or Git blob hash mismatch for {slug}")
    patch = case / "fix.patch"
    with tempfile.TemporaryDirectory(prefix=f"repair-{slug}-") as directory:
        original = Path(directory).joinpath(*source_path.parts)
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_bytes(raw)
        for args in (["--check", str(patch)], [str(patch)]):
            subprocess.run(["git", "apply", *args], cwd=directory, check=True,
                           capture_output=True, text=True, timeout=30)
        patched = original.read_bytes()
    write_or_verify(before, raw)
    write_or_verify(case / "after.py", patched)
    return case


def main() -> int:
    records = json.loads((ROOT / "source_index.json").read_text(encoding="utf-8"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=["all", *[r["slug"] for r in records]], default="all")
    parser.add_argument("--variant", choices=["before", "after"], default="after")
    parser.add_argument("--download-only", action="store_true", help="Prepare sources without executing tests")
    parser.add_argument("--offline", action="store_true", help="Require existing hash-matching before.py files")
    args = parser.parse_args()
    if shutil.which("git") is None:
        parser.error("Git is required to verify and apply patches")
    result = 0
    for record in records:
        if args.case not in ("all", record["slug"]):
            continue
        try:
            case = prepare(record, args.offline)
            print(f"{record['slug']}: verified source and patch", flush=True)
            if not args.download_only:
                env = dict(os.environ, VARIANT=args.variant)
                completed = subprocess.run(
                    [sys.executable, "-m", "pytest", "-q", "test_regression.py", "--tb=short"],
                    cwd=case, env=env, timeout=120,
                )
                result = max(result, int(completed.returncode != 0))
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            print(f"{record['slug']}: {exc}", file=sys.stderr)
            result = 1
    return result


if __name__ == "__main__":
    raise SystemExit(main())
