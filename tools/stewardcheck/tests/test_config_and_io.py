"""Regression coverage for explicit config, bounded IO, and metadata-only scans."""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout, redirect_stderr

from test_stewardcheck import RepositoryCase
from stewardcheck import __version__
from stewardcheck.cli import main
from stewardcheck.common import StewardError
from stewardcheck.config import CONFIG_LIMIT, load_config
from stewardcheck.core import DEFAULT_PROTECTED
from stewardcheck.files import read_bounded
from stewardcheck.repository import snapshot


class ConfigTests(RepositoryCase):
    def config(self, text):
        return self.write(".stewardcheck.toml", text)

    def test_defaults_and_no_auto_discovery(self):
        self.config('this is deliberately invalid TOML')
        code, _, _ = self.cli("start", "Fix app")
        self.assertEqual(code, 0)
        self.assertEqual(self.project.store.load()["contract"]["scope"], ["**"])

    def test_explicit_config_is_loaded_but_not_executed(self):
        self.config('schema = 1\nscope = ["src/**"]\nchecks = [["nonexistent-check-command"]]\nmax_files = 7\ntimeout = 15\nscan_mib = 8\nacceptance = ["Preserve behavior"]\n')
        code, _, _ = self.cli("start", "Fix app", "--config", ".stewardcheck.toml")
        self.assertEqual(code, 0)
        policy = self.project.store.load()["contract"]
        self.assertEqual(policy["scope"], ["src/**"])
        self.assertEqual(policy["commands"], [["nonexistent-check-command"]])
        self.assertEqual(policy["max_files"], 7)
        self.assertEqual(policy["timeout"], 15)
        self.assertEqual(policy["scan_bytes"], 8 * 1024 * 1024)
        self.assertEqual(policy["acceptance"], ["Preserve behavior"])
        self.assertEqual(policy["protect"], DEFAULT_PROTECTED)
        self.assertEqual(self.project.check()["checks"], [])

    def test_cli_lists_replace_config_lists(self):
        self.config('schema = 1\nscope = ["docs/**"]\nprotect = ["private/**"]\nchecks = [["old-check"]]\nacceptance = ["Old criterion"]\n')
        code, _, _ = self.cli("start", "Fix app", "--config", ".stewardcheck.toml",
                             "--scope", "src/**", "--protect", "secrets/**",
                             "--accept", "New criterion", "--check-json", '["new-check", "a b"]')
        self.assertEqual(code, 0)
        policy = self.project.store.load()["contract"]
        for field, expected in {"scope": ["src/**"], "protect": ["secrets/**"],
                                "acceptance": ["New criterion"], "commands": [["new-check", "a b"]]}.items():
            self.assertEqual(policy[field], expected)

    def test_cli_scalar_overrides(self):
        self.config('schema = 1\nmax_files = 7\ntimeout = 30\nscan_mib = 8\n')
        self.assertEqual(self.cli("start", "Fix", "--config", ".stewardcheck.toml",
                                 "--max-files", "2", "--timeout", "5", "--scan-mib", "4")[0], 0)
        policy = self.project.store.load()["contract"]
        self.assertEqual((policy["max_files"], policy["timeout"], policy["scan_bytes"]),
                         (2, 5, 4 * 1024 * 1024))

    def test_relative_config_is_root_relative(self):
        self.config('schema = 1\nscope = ["src/**"]\n')
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = main(["start", "Fix", "--config", ".stewardcheck.toml", "--root", str(self.root / "src")])
        self.assertEqual(code, 0)
        self.assertEqual(load_config(self.root, self.root / ".stewardcheck.toml")["scope"], ["src/**"])

    def test_missing_config_does_not_create_task(self):
        self.assertEqual(self.cli("start", "Fix", "--config", "absent.toml")[0], 3)
        self.assertFalse(self.project.store.path.exists())

    def test_invalid_toml_does_not_create_task(self):
        self.config('schema = [invalid')
        self.assertEqual(self.cli("start", "Fix", "--config", ".stewardcheck.toml")[0], 3)
        self.assertFalse(self.project.store.path.exists())

    def test_unknown_and_wrong_typed_fields(self):
        for text in ('schema = 2', 'schema = true', 'scope = ["src/**"]',
                     'schema = 1\ncommand = "echo unsafe"', 'schema = 1\nscope = "src/**"',
                     'schema = 1\nprotect = [1]', 'schema = 1\nacceptance = [false]',
                     'schema = 1\nchecks = ["python -m unittest"]',
                     'schema = 1\nchecks = [[1]]', 'schema = 1\nchecks = [[]]',
                     'schema = 1\nmax_files = true', 'schema = 1\nscan_mib = 2.5',
                     'schema = 1\ntimeout = false', 'schema = 1\nscope = []'):
            with self.subTest(text=text), self.assertRaises(StewardError):
                load_config(self.root, self.config(text))

    def test_out_of_range_and_invalid_pattern_values(self):
        for text in ('schema = 1\nmax_files = 0', 'schema = 1\ntimeout = nan',
                     'schema = 1\ntimeout = inf', 'schema = 1\nscan_mib = 9000',
                     'schema = 1\nscope = ["../elsewhere"]', 'schema = 1\nchecks = [[""]]'):
            with self.subTest(text=text), self.assertRaises(StewardError):
                load_config(self.root, self.config(text))

    def test_invalid_config_cannot_be_hidden_by_override(self):
        self.config('schema = 1\ntimeout = -1\n')
        self.assertEqual(self.cli("start", "Fix", "--config", ".stewardcheck.toml", "--timeout", "5")[0], 3)

    def test_config_remains_pinned(self):
        self.config('schema = 1\nscope = ["src/**"]\nchecks = [["original-check"]]\n')
        self.assertEqual(self.cli("start", "Fix", "--config", ".stewardcheck.toml")[0], 0)
        self.config('schema = 1\nchecks = [["replacement-check"]]\n')
        self.assertEqual(self.project.store.load()["contract"]["commands"], [["original-check"]])
        self.assertIn("PROTECTED_PATH", self.codes(self.project.check()))

    def test_empty_protection_is_an_explicit_replacement(self):
        self.config('schema = 1\nprotect = []\nchecks = []\n')
        self.assertEqual(self.cli("start", "Fix", "--config", ".stewardcheck.toml")[0], 0)
        self.assertEqual(self.project.store.load()["contract"]["protect"], [])
        self.edit()
        self.assertIn("NO_CHECKS", self.codes(self.project.check(True)))

    def test_config_budget_and_encoding(self):
        for data in (b"#" * (CONFIG_LIMIT + 1), b"\xffschema = 1"):
            self.config("").write_bytes(data)
            with self.assertRaises(StewardError):
                load_config(self.root, self.root / ".stewardcheck.toml")

    def test_config_directory_and_parent_traversal_rejected(self):
        for path in (self.root / "tests", self.root / "tests" / ".." / ".stewardcheck.toml"):
            with self.assertRaises(StewardError):
                load_config(self.root, path)

    @unittest.skipUnless(os.name == "posix", "Symlink privileges")
    def test_symlink_config_and_parent_rejected(self):
        real = self.config('schema = 1\n')
        link = self.root / "alias.toml"
        link.symlink_to(real)
        parent = self.root / "alias"
        parent.symlink_to(self.root, target_is_directory=True)
        for path in (link, parent / ".stewardcheck.toml"):
            with self.assertRaises(StewardError):
                load_config(self.root, path)

    @unittest.skipUnless(os.name == "posix", "POSIX FIFO")
    def test_fifo_config_fails_without_hanging(self):
        os.mkfifo(self.root / ".stewardcheck.toml")
        result = subprocess.run([sys.executable, "-m", "stewardcheck", "start", "Fix", "--root",
                                 str(self.root), "--config", ".stewardcheck.toml"],
                                capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 3)


class IOTests(RepositoryCase):
    def test_bounded_read_and_size_limit(self):
        path = self.write("record", "abc")
        self.assertEqual(read_bounded(path, 3), b"abc")
        with self.assertRaises(StewardError):
            read_bounded(path, 2)

    def test_growth_after_lstat_is_still_bounded(self):
        path = self.write("record", "abc")
        original_open = os.open
        def growing_open(target, flags, *args, **kwargs):
            path.write_bytes(b"x" * 20)
            return original_open(target, flags, *args, **kwargs)
        with patch("stewardcheck.files.os.open", side_effect=growing_open):
            with self.assertRaises(StewardError):
                read_bounded(path, 3)

    def test_same_inode_change_during_open_is_rejected(self):
        path = self.write("record", "abc")
        original_open = os.open
        def editing_open(target, flags, *args, **kwargs):
            path.write_bytes(b"new data")
            return original_open(target, flags, *args, **kwargs)
        with patch("stewardcheck.files.os.open", side_effect=editing_open):
            with self.assertRaises(StewardError):
                read_bounded(path, 100)

    def test_replacement_during_open_is_rejected(self):
        path = self.write("record", "abc")
        replacement = self.write("replacement", "def")
        original_open = os.open
        def replacing_open(target, flags, *args, **kwargs):
            replacement.replace(path)
            return original_open(target, flags, *args, **kwargs)
        with patch("stewardcheck.files.os.open", side_effect=replacing_open):
            with self.assertRaises(StewardError):
                read_bounded(path, 100)

    @unittest.skipUnless(os.name == "posix", "POSIX nonblocking open")
    def test_nonblocking_flag_used(self):
        path = self.write("record", "abc")
        with patch("stewardcheck.files.os.open", wraps=os.open) as opened:
            read_bounded(path, 3)
        self.assertTrue(opened.call_args.args[1] & os.O_NONBLOCK)

    @unittest.skipUnless(os.name == "posix", "POSIX FIFO")
    def test_fifo_state_fails_without_hanging(self):
        self.start()
        self.project.store.path.unlink()
        os.mkfifo(self.project.store.path)
        result = subprocess.run([sys.executable, "-m", "stewardcheck", "check", "--root", str(self.root)],
                                capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 3)
        self.assertIn(b"regular file", result.stderr)

    def test_state_directory_rejected(self):
        self.start()
        self.project.store.path.unlink()
        self.project.store.path.mkdir()
        self.assertEqual(self.cli("check")[0], 3)

    def test_invalid_state_envelopes_return_operational_error(self):
        self.start()
        original = json.loads(self.project.store.path.read_text())
        without_receipt = dict(original)
        without_receipt.pop("receipt")
        for value in ([], None, without_receipt, dict(original, receipt="not a receipt")):
            self.project.store.path.write_text(json.dumps(value))
            self.assertEqual(self.cli("check")[0], 3)

    def test_snapshot_without_text_preserves_fingerprint(self):
        full, texts = snapshot(self.root)
        metadata, empty = snapshot(self.root, collect_text=False)
        self.assertTrue(texts)
        self.assertEqual(empty, {})
        self.assertEqual(full, metadata)

    def test_only_packet_retains_source_text(self):
        with patch("stewardcheck.core.snapshot", wraps=snapshot) as scanner:
            self.start()
            self.edit()
            receipt = self.project.check()
            self.project.report()
            self.assertEqual(receipt["tool_version"], __version__)
            self.assertTrue(all(call.kwargs.get("collect_text") is False for call in scanner.call_args_list))
            scanner.reset_mock()
            self.assertIn("VALUE = 2", self.project.packet())
            self.assertTrue(scanner.call_args.kwargs.get("collect_text", True))

    def test_checks_still_run_only_after_explicit_approval(self):
        self.start()
        self.edit()
        self.assertEqual(self.project.check()["checks"], [])
        receipt = self.project.check(True)
        self.assertEqual(receipt["verdict"], "passed")
        self.assertEqual(len(receipt["checks"]), 1)
