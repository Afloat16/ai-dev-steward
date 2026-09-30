"""A runnable, isolated demonstration. All fixture changes stay in a temporary directory."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from stewardcheck.core import Project, contract


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="stewardcheck-demo-") as directory:
        root = Path(directory)
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        subprocess.run(["git", "init", "-q", str(root)], check=True, env=env)
        (root / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
        (root / "app.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
        (root / "test_app.py").write_text(
            "import unittest\nfrom app import add\n"
            "class Addition(unittest.TestCase):\n"
            "    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n",
            encoding="utf-8",
        )
        project = Project(root)
        project.start(contract("Correct addition", scope=["app.py", "test_app.py"],
                               commands=[[sys.executable, "-B", "-m", "unittest", "-v"]],
                               acceptance=["Addition returns the sum for supported inputs."]))
        packet = project.packet(4096)
        assert len(packet.encode("utf-8")) <= 4096
        print(f"Context packet: {len(packet.encode('utf-8'))} bytes (limit: 4096)")
        (root / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        receipt = project.check(execute=True)
        assert receipt["verdict"] == "passed", receipt
        print("Fix with real unittest check:", receipt["verdict"])
        (root / "app.py").write_text("def add(a, b):\n    return a + b + 1\n", encoding="utf-8")
        stale = project.report()
        assert stale["stale"] and stale["verdict"] == "needs-review", stale
        print("Edit after check:", stale["verdict"], "(stale receipt)")
        (root / "unrelated.txt").write_text("out of scope\n", encoding="utf-8")
        blocked = project.check(execute=True)
        assert blocked["verdict"] == "blocked" and not blocked["checks"], blocked
        print("Unrelated file:", blocked["verdict"], "(commands not executed)")
        print("Demo completed; the temporary repository is removed on exit.")


if __name__ == "__main__":
    main()
