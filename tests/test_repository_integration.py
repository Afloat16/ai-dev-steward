"""Cross-component documentation checks, compatible with Python 3.10."""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "tools" / "stewardcheck"


class RepositoryIntegrationTests(unittest.TestCase):
    def test_readme_relative_links_exist(self):
        for directory in (ROOT, PACKAGE):
            for name in ("README.md", "README.zh-CN.md", "CONTRIBUTING.md"):
                document = directory / name
                for target in re.findall(r"\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
                    if "://" in target or target.startswith("#"):
                        continue
                    path = target.split("#", 1)[0]
                    with self.subTest(document=str(document), target=target):
                        self.assertTrue((directory / path).exists())

    def test_versions_match_package_metadata_and_readmes(self):
        module = ast.parse((PACKAGE / "src/stewardcheck/__init__.py").read_text(encoding="utf-8"))
        version = next(ast.literal_eval(node.value) for node in module.body
                       if isinstance(node, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets))
        metadata = (PACKAGE / "pyproject.toml").read_text(encoding="utf-8")
        self.assertEqual(re.search(r'^version = "([^"]+)"', metadata, re.MULTILINE).group(1), version)
        for directory in (ROOT, PACKAGE):
            for name in ("README.md", "README.zh-CN.md"):
                self.assertIn(version, (directory / name).read_text(encoding="utf-8"))

    def test_root_routes_both_components_and_languages(self):
        english = (ROOT / "README.md").read_text(encoding="utf-8")
        chinese = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
        self.assertIn("[简体中文](README.zh-CN.md)", english)
        self.assertIn("[English](README.md)", chinese)
        for text in (english, chinese):
            for path in ("SKILL.md", "scripts/steward.py", "tools/stewardcheck/", "CONTRIBUTING.md"):
                self.assertIn(path, text)
