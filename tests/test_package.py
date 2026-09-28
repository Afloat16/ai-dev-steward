"""Portable package checks; not a claim of testing every Agent Skills host."""
import ast
import re
import unittest
from pathlib import Path
from test_steward import s

ROOT = Path(__file__).resolve().parents[1]


class PackageTests(unittest.TestCase):
    def test_frontmatter_version_and_size(self):
        text = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
        self.assertTrue(text.startswith('---\n'))
        front = text.split('---', 2)[1]
        self.assertIn('name: ai-dev-steward', front)
        self.assertIn('description: >-', front)
        self.assertIn('version: "' + s.VERSION + '"', front)
        self.assertLess(len(text.splitlines()), 500)

    def test_relative_skill_links_exist(self):
        text = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
        for path in re.findall(r'\]\(([^)]+)\)', text):
            self.assertTrue((ROOT / path).is_file(), path)

    def test_python310_syntax(self):
        for folder in ('scripts', 'tests'):
            for file in (ROOT / folder).glob('*.py'):
                ast.parse(file.read_text(encoding='utf-8'), feature_version=(3, 10))

    def test_metric_example_is_explicitly_nonpassing(self):
        data = s.read_json(ROOT / 'assets/metrics.example.json')
        out, code = s.compare(data)
        self.assertEqual('EXAMPLE_ONLY', out['status'])
        self.assertEqual(2, code)
        self.assertTrue(all(row['status'] == 'not_run' for row in data['ablations']))

    def test_ledger_example_never_claims_reference_verification(self):
        data = s.read_json(ROOT / 'assets/ledger.example.json')
        self.assertTrue(data['example'])
        self.assertTrue(s.ledger_records(data))
        self.assertIs(False, data['records'][0]['references_checked'])
