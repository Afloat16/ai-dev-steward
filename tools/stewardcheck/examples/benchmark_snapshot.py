"""Measure retained-text overhead on a synthetic, temporary repository.

Not a production/monorepo benchmark. No timing or memory threshold is asserted.
Run after installing the package: python examples/benchmark_snapshot.py
"""
from __future__ import annotations

import gc
import json
import os
import platform
import subprocess
import tempfile
import tracemalloc
from pathlib import Path

from stewardcheck.repository import snapshot


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        subprocess.run(["git", "init", "-q", str(root)], check=True,
                       env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")})
        for index in range(128):
            (root / f"file_{index:03d}.txt").write_bytes(b"x" * 65536)
        records = []
        fingerprint = None
        for collect in (True, False):
            gc.collect()
            tracemalloc.start()
            result, texts = snapshot(root, collect_text=collect)
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            if fingerprint is not None and fingerprint != result["fingerprint"]:
                raise RuntimeError("Snapshot fingerprints differ")
            fingerprint = result["fingerprint"]
            records.append({"collect_text": collect, "peak_traced_bytes": peak,
                            "retained_text_files": len(texts)})
            del result, texts
        print(json.dumps({"python": platform.python_version(), "platform": platform.system(),
                          "fixture_files": 128, "fixture_bytes": 128 * 65536,
                          "identical_fingerprints": True, "measurements": records}, indent=2))


if __name__ == "__main__":
    main()
