"""Reproduce candidate regressions; never writes to an upstream checkout or GitHub.

Without bundled baseline files, public Git blobs are fetched and SHA-verified.
With --source-root, use existing local source copies and make no network calls.
All modifications and pytest caches are confined to a temporary directory.
"""
from __future__ import annotations

import argparse
import base64
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent


def blob_hash(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def run(source_root: Path | None) -> int:
    specs = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="robotics-audit-") as temp:
        work = Path(temp)
        before, after = work / "baseline", work / "patched"
        before.mkdir()
        after.mkdir()
        shutil.copytree(ROOT / "tests", work / "tests", ignore=shutil.ignore_patterns("__pycache__"))
        for spec in specs:
            if source_root is not None:
                data = (source_root / spec["name"]).read_bytes()
            else:
                url = f'https://api.github.com/repos/{spec["repo"]}/git/blobs/{spec["sha"]}'
                request = urllib.request.Request(url, headers={"User-Agent": "Afloat16-robotics-audit"})
                with urllib.request.urlopen(request, timeout=30) as response:
                    payload = json.loads(response.read(1_000_000))
                if payload.get("encoding") != "base64":
                    raise ValueError("Unexpected GitHub blob encoding")
                data = base64.b64decode(payload["content"])
            if blob_hash(data) != spec["sha"]:
                raise ValueError(f'Baseline mismatch: {spec["name"]}; refusing to run')
            original = data.decode("utf-8")
            changed = original
            for old, new in spec["edits"]:
                if changed.count(old) != 1:
                    raise ValueError(f'Edit anchor mismatch: {spec["name"]}')
                changed = changed.replace(old, new)
            expected_patch = "".join(difflib.unified_diff(
                original.splitlines(True), changed.splitlines(True),
                fromfile=f'a/{spec["path"]}', tofile=f'b/{spec["path"]}'))
            if expected_patch != (ROOT / "patches" / spec["patch"]).read_text(encoding="utf-8"):
                raise ValueError(f'Patch differs from validated edits: {spec["patch"]}')
            (before / spec["name"]).write_bytes(data)
            (after / spec["name"]).write_bytes(changed.encode("utf-8"))
            print(f'Verified upstream blob: {spec["repo"]} {spec["sha"]}', flush=True)
        for label, folder, expected_code, expected_summary in [
            ("BASELINE", before, 1, "20 failed, 14 passed"),
            ("PATCHED", after, 0, "34 passed"),
        ]:
            env = dict(os.environ, SOURCE_ROOT=str(folder), PYTHONDONTWRITEBYTECODE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
            process = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "tests", "--tb=short"],
                cwd=work, env=env, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=90, check=False)
            print(f"\n=== {label} ===\n{process.stdout}", flush=True)
            if process.returncode != expected_code or expected_summary not in process.stdout:
                raise RuntimeError(f"Unexpected {label} result; inspect output, do not claim validation")
        print("Reproduced 20 failing regressions before / 34 passing tests after. Not full upstream CI.")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, help="Directory containing the three original source files")
    args = parser.parse_args()
    sources = args.source_root
    if sources is None and (ROOT / "baseline").is_dir():
        sources = ROOT / "baseline"
    try:
        return run(sources)
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError) as exc:
        print(f"Validation stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
