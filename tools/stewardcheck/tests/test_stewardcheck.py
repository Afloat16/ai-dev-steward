from __future__ import annotations

import io
import json
import os
import shlex
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from stewardcheck import __version__
from stewardcheck.cli import main, parse_checks
from stewardcheck.common import StewardError, digest, display, matches, normalize_pattern
from stewardcheck.core import Project, changes, contract
from stewardcheck.render import fence, json_output, markdown_receipt
from stewardcheck.repository import TEXT_LIMIT, snapshot, unstaged_paths
from stewardcheck.runner import CAPTURE_BYTES, OUTPUT_LIMIT, run_command
from stewardcheck.secrets import findings, redact, sensitive_path, test_metrics

# Synthetic strings, assembled at runtime; never real credentials.
TOKEN = "gh" + "p_" + "0123456789abcdefghij" * 2
TOKEN2 = "gh" + "p_" + "abcdefghij0123456789" * 2


class RepositoryCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.git("init", "-q")
        self.git("config", "user.name", "Test Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.write(".gitignore", "__pycache__/\n*.pyc\n.env\nignored/\n")
        self.write("src/app.py", "VALUE = 1\n")
        self.write("tests/test_app.py", "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertEqual(1, 1)\n")
        self.git("add", ".")
        self.git("commit", "-qm", "Fixture baseline")
        self.project = Project(self.root)

    def git(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        return subprocess.run(["git", "-C", str(self.root), *args], env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout

    def write(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def start(self, **kwargs):
        kwargs.setdefault("scope", ["src/**", "tests/**"])
        kwargs.setdefault("commands", [[sys.executable, "-c", "print('checks passed')"]])
        return self.project.start(contract("Fix the app", **kwargs))

    def edit(self):
        self.write("src/app.py", "VALUE = 2\n")

    def codes(self, receipt):
        return {n["code"] for n in receipt["findings"]}

    def cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main([*args, "--root", str(self.root)])
        return code, out.getvalue(), err.getvalue()


class Primitives(unittest.TestCase):
    def test_glob_segments(self):
        cases = [("x.py", "**/*.py", True), ("src/x.py", "src/*.py", True),
                 ("src/a/x.py", "src/*.py", False), ("src/a/x.py", "src/**", True),
                 ("a/.env", "**/.env", True), (".env", "**/.env", True),
                 ("src2/x.py", "src/**", False), ("src/x1.py", "src/x?.py", True),
                 ("a/b/c", "**/b/**", True), ("a/b", "a/**/b", True),
                 ("a.py", "*.PY", False)]
        for path, glob, expected in cases:
            with self.subTest(path=path, glob=glob):
                self.assertEqual(matches(path, glob), expected)

    def test_pattern_validation(self):
        for pattern in ("../secret", "/root", "x/../y", "!file", "a\\b", "C:/tmp", "a//b", ""):
            with self.subTest(pattern=pattern), self.assertRaises(StewardError):
                normalize_pattern(pattern)
        self.assertEqual(normalize_pattern("./src/"), "src/**")

    def test_secret_redaction(self):
        text = f'api_key = "{TOKEN}"\nurl = "https://name:realpassword@example.invalid"'
        self.assertTrue(findings(text))
        self.assertNotIn(TOKEN, redact(text))
        self.assertNotIn("realpassword", redact(text))

    def test_multiline_private_key(self):
        text = "-----BEGIN PRIVATE KEY-----\nprivate-material\n-----END PRIVATE KEY-----"
        self.assertEqual(redact(text), "[REDACTED]")
        self.assertNotIn("private-material", redact(text.split("-----END")[0]))

    def test_provider_and_aws_patterns(self):
        for token in ("sk-" + "aB01_" * 8, "AKIA" + "AB01" * 4,
                      "github_" + "pat_" + "aB01_" * 8):
            self.assertTrue(findings(token))
            self.assertNotIn(token, redact(token))

    def test_placeholder_literals(self):
        self.assertFalse(findings('api_key = "your_key_here"'))
        self.assertFalse(findings('password = "example_password"'))
        self.assertTrue(findings('password = "a-real-literal-value"'))

    def test_sensitive_paths(self):
        for path in (".env", "src/.env.local", "key.pem", "key.p12", ".npmrc", "a/id_rsa"):
            self.assertTrue(sensitive_path(path))
        self.assertFalse(sensitive_path("src/environment.py"))

    def test_controls(self):
        self.assertEqual(display("\x1b[2J"), "\\u001b[2J")
        self.assertNotIn("\u202e", display("name\u202e.py"))

    def test_markdown_fences(self):
        result = fence("```\n# embedded heading\n```")
        self.assertTrue(result.startswith("````\n"))
        self.assertTrue(result.endswith("````\n"))

    def test_metrics(self):
        metrics = test_metrics("tests/test_x.py", "assert a\nself.assertEqual(a,b)\n@pytest.mark.skip\n")
        self.assertEqual(metrics["assertions"], 2)
        self.assertEqual(metrics["skips"], 1)
        self.assertFalse(test_metrics("src/main.py", "assert a")["is_test"])

    def test_exact_json_argv(self):
        argv = [r"C:\Program Files\Python\python.exe", "-c", "print('ok')"]
        self.assertEqual(parse_checks([], [json.dumps(argv)]), [argv])

    def test_shell_operators_rejected(self):
        with self.assertRaises(StewardError):
            parse_checks(["echo ok && echo unsafe"], [])
        self.assertEqual(parse_checks(["python -c 'print(1); print(2)'"], []),
                         [["python", "-c", "print(1); print(2)"]])

    def test_bad_command_inputs(self):
        for text, js in [(["'unclosed"], []), ([], ["bad json"])]:
            with self.assertRaises(StewardError):
                parse_checks(text, js)
        for commands in ([[]], ["string"], [[1]], [["python", "\0"]]):
            with self.assertRaises(StewardError):
                contract("task", commands=commands)

    def test_bad_contract_inputs(self):
        for kwargs in ({"task": ""}, {"task": "x", "timeout": 0},
                       {"task": "x", "max_files": True}, {"task": "x", "scan_bytes": 1},
                       {"task": "x", "acceptance": ["a"] * 21},
                       {"task": "x", "scope": ["a"] * 51},
                       {"task": "x", "commands": [["true"]] * 21}):
            with self.subTest(kwargs=kwargs), self.assertRaises(StewardError):
                contract(**kwargs)

    def test_digest_order_independent(self):
        self.assertEqual(digest({"a": 1, "b": 2}), digest({"b": 2, "a": 1}))

    def test_json_remains_parseable_after_redaction(self):
        result = json.loads(json_output({"value": TOKEN, "nested": ["\x1b\n"]}))
        self.assertEqual(result["value"], "[REDACTED]")


class WorkflowTests(RepositoryCase):
    def test_happy_path_and_fresh_report(self):
        self.start(); self.edit()
        receipt = self.project.check(True)
        self.assertEqual(receipt["verdict"], "passed")
        self.assertEqual(receipt["checks"][0]["exit_code"], 0)
        self.assertFalse(self.project.report()["stale"])
        self.assertIn("PASSED", markdown_receipt(receipt))

    def test_checks_require_explicit_run(self):
        self.start(commands=[[sys.executable, "-c", "open('MARKER','w').close()"]]); self.edit()
        result = self.project.check(False)
        self.assertIn("CHECKS_NOT_RUN", self.codes(result))
        self.assertFalse((self.root / "MARKER").exists())
        self.assertEqual(result["verdict"], "needs-review")

    def test_static_blockers_prevent_execution(self):
        self.start(commands=[[sys.executable, "-c", "open('MARKER','w').close()"]])
        self.write("outside.txt", "oops")
        result = self.project.check(True)
        self.assertIn("OUTSIDE_SCOPE", self.codes(result))
        self.assertEqual(result["verdict"], "blocked")
        self.assertFalse((self.root / "MARKER").exists())

    def test_no_checks_never_passes(self):
        self.start(commands=[]); self.edit()
        result = self.project.check(True)
        self.assertIn("NO_CHECKS", self.codes(result))
        self.assertEqual(result["verdict"], "needs-review")

    def test_no_changes_never_passes(self):
        self.start()
        result = self.project.check(True)
        self.assertIn("NO_TASK_CHANGES", self.codes(result))
        self.assertNotEqual(result["verdict"], "passed")

    def test_dirty_and_untracked_baseline(self):
        self.write("src/app.py", "PREEXISTING = 1\n")
        self.write("notes.txt", "keep my existing work\n")
        self.start()
        self.write("src/app.py", "PREEXISTING = 2\n")
        result = self.project.check(True)
        self.assertEqual([c["path"] for c in result["changes"]], ["src/app.py"])
        self.assertEqual((self.root / "notes.txt").read_text(), "keep my existing work\n")

    def test_new_untracked_file_is_checked(self):
        self.start()
        self.write("src/new.py", "x = 1\n")
        result = self.project.check(True)
        self.assertEqual(result["changes"][0]["change"], "added")

    def test_deletion(self):
        self.start()
        (self.root / "src/app.py").unlink()
        self.assertEqual(self.project.check(False)["changes"][0]["change"], "deleted")

    def test_protected_workflow(self):
        self.start(scope=["**"])
        self.write(".github/workflows/deploy.yml", "name: changed\n")
        self.assertIn("PROTECTED_PATH", self.codes(self.project.check(True)))

    def test_explicit_protection_replacement(self):
        self.start(scope=[".github/**"], protect=["**/.env"])
        self.write(".github/workflows/new.yml", "name: reviewed\n")
        self.assertEqual(self.project.check(True)["verdict"], "passed")

    def test_file_budget(self):
        self.start(max_files=1); self.edit()
        self.write("src/new.py", "x=1\n")
        self.assertIn("CHANGE_BUDGET", self.codes(self.project.check(True)))

    def test_new_secret_blocked_and_not_stored_raw(self):
        self.start()
        self.write("src/credentials.py", f'api_key = "{TOKEN}"\n')
        result = self.project.check(True)
        self.assertIn("POSSIBLE_SECRET", self.codes(result))
        self.assertNotIn(TOKEN, self.project.store.path.read_text())
        self.assertNotIn(TOKEN, self.project.packet())
        self.assertNotIn(TOKEN, json_output(result))

    def test_preexisting_secret_not_reported_as_new(self):
        self.write("src/key.py", f'key = "{TOKEN}"\n')
        self.start()
        self.write("src/key.py", f'# a comment\nkey = "{TOKEN}"\n')
        self.assertNotIn("POSSIBLE_SECRET", self.codes(self.project.check(True)))

    def test_changed_secret_detected(self):
        self.write("src/key.py", f'key = "{TOKEN}"\n'); self.start()
        self.write("src/key.py", f'key = "{TOKEN2}"\n')
        self.assertIn("POSSIBLE_SECRET", self.codes(self.project.check(True)))

    def test_secret_copied_to_new_file_detected(self):
        self.write("src/key.py", f'key = "{TOKEN}"\n'); self.start()
        self.write("src/copy.py", f'key = "{TOKEN}"\n')
        self.assertIn("POSSIBLE_SECRET", self.codes(self.project.check(True)))

    def test_source_content_not_persisted(self):
        source = "UNIQUE_SOURCE_TEXT_NOT_IN_STATE = 12345\n"
        self.write("src/app.py", source); self.start()
        self.assertNotIn(source.strip(), self.project.store.path.read_text())

    def test_test_assertion_removal(self):
        self.start(); self.write("tests/test_app.py", "# no assertions\n")
        self.assertIn("ASSERTIONS_REMOVED", self.codes(self.project.check(True)))

    def test_test_deletion(self):
        self.start(); (self.root / "tests/test_app.py").unlink()
        self.assertIn("TEST_DELETED", self.codes(self.project.check(True)))

    def test_test_skip_marker(self):
        self.start(); self.write("tests/test_new.py", "@pytest.mark.skip\ndef test_x():\n    assert 1\n")
        self.assertIn("TESTS_SKIPPED", self.codes(self.project.check(True)))

    def test_check_surface_changed(self):
        self.start(scope=["**"]); self.write("package.json", '{"scripts": {"test": "echo done"}}')
        self.assertIn("CHECK_SURFACE_CHANGED", self.codes(self.project.check(True)))

    def test_ignore_rule_change_and_old_paths_retained(self):
        self.start(scope=["**"])
        self.write(".gitignore", "src/\n__pycache__/\n")
        self.edit()
        self.assertIn("DISCOVERY_RULES_CHANGED", self.codes(self.project.check(False)))

    def test_failed_check(self):
        self.start(commands=[[sys.executable, "-c", "raise SystemExit(17)"]]); self.edit()
        result = self.project.check(True)
        self.assertEqual(result["verdict"], "blocked")
        self.assertEqual(result["checks"][0]["exit_code"], 17)

    def test_mutating_check_invalidates_evidence(self):
        self.start(commands=[[sys.executable, "-c", "from pathlib import Path; Path('src/app.py').write_text('VALUE=99\\n')"]]); self.edit()
        result = self.project.check(True)
        self.assertIn("WORKSPACE_CHANGED_DURING_CHECKS", self.codes(result))
        self.assertTrue(self.project.report()["stale"])

    def test_report_after_edit_is_stale(self):
        self.start(); self.edit(); self.project.check(True)
        self.write("src/app.py", "VALUE=3\n")
        result = self.project.report()
        self.assertTrue(result["stale"])
        self.assertEqual(result["verdict"], "needs-review")

    def test_index_change_makes_receipt_stale(self):
        self.start(); self.edit(); self.project.check(True)
        self.git("add", "src/app.py")
        self.assertTrue(self.project.report()["stale"])

    def test_partial_staging_warning(self):
        self.start(); self.edit(); self.git("add", "src/app.py")
        self.write("src/app.py", "VALUE=3\n")
        self.assertIn("PARTIAL_STAGING", self.codes(self.project.check(True)))

    def test_head_move_does_not_reset_baseline(self):
        self.start(); self.edit(); self.git("add", "src/app.py"); self.git("commit", "-qm", "Task edit")
        result = self.project.check(True)
        self.assertIn("HEAD_MOVED", self.codes(result))
        self.assertEqual(len(result["changes"]), 1)

    def test_start_does_not_stage_or_commit(self):
        self.edit()
        before_head = self.git("rev-parse", "HEAD")
        before_index = self.git("ls-files", "--stage", "-z")
        self.start(); self.project.check(False)
        self.assertEqual(before_head, self.git("rev-parse", "HEAD"))
        self.assertEqual(before_index, self.git("ls-files", "--stage", "-z"))

    def test_replace_is_explicit(self):
        self.start()
        with self.assertRaises(StewardError):
            self.start()
        self.project.start(contract("Second task"), replace=True)
        self.assertEqual(self.project.store.load()["contract"]["task"], "Second task")

    def test_report_without_check(self):
        self.start()
        with self.assertRaises(StewardError):
            self.project.report()

    def test_missing_task(self):
        with self.assertRaises(StewardError):
            self.project.check()

    def test_subdirectory_discovery(self):
        self.assertEqual(Project(self.root / "src").root, self.root)

    def test_empty_unborn_repository(self):
        with tempfile.TemporaryDirectory() as other:
            subprocess.run(["git", "init", "-q", other], check=True)
            project = Project(Path(other))
            project.start(contract("Add first file", commands=[[sys.executable, "-c", "pass"]]))
            Path(other, "app.py").write_text("x=1\n")
            self.assertEqual(project.check(True)["verdict"], "passed")

    def test_unicode_space_paths(self):
        self.start(); self.write("src/中文 file.py", "说明 = '你好'\n")
        result = self.project.check(True)
        self.assertEqual(result["changes"][0]["path"], "src/中文 file.py")

    def test_binary_change_requires_review(self):
        self.start(); (self.root / "src/image.bin").write_bytes(b"binary\0data")
        self.assertIn("CONTENT_UNINSPECTED", self.codes(self.project.check(True)))

    def test_oversized_text_requires_review(self):
        self.start(); self.write("src/large.txt", "x" * (TEXT_LIMIT + 1))
        self.assertIn("CONTENT_UNINSPECTED", self.codes(self.project.check(True)))

    def test_scan_limit_fails_closed(self):
        self.write("src/big.txt", "x" * (1024 * 1024 + 1))
        with self.assertRaises(StewardError):
            self.start(scan_bytes=1024 * 1024)

    def test_same_size_and_mtime_edit_detected(self):
        self.start()
        path = self.root / "src/app.py"
        info = path.stat(); self.edit(); os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
        self.assertEqual(len(self.project.check(True)["changes"]), 1)

    @unittest.skipUnless(os.name == "posix", "POSIX executable mode")
    def test_executable_bit_change(self):
        self.start(); (self.root / "src/app.py").chmod(0o755)
        self.assertEqual(len(self.project.check(True)["changes"]), 1)

    @unittest.skipUnless(os.name == "posix", "Symlink creation requires platform privileges")
    def test_symlink_not_followed(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "private"; target.write_text(TOKEN)
            self.start(); (self.root / "src/link").symlink_to(target)
            result = self.project.check(True)
            self.assertIn("CONTENT_UNINSPECTED", self.codes(result))
            self.assertNotIn(TOKEN, self.project.packet())

    @unittest.skipUnless(os.name == "posix", "Symlink creation requires platform privileges")
    def test_parent_symlink_not_followed(self):
        self.start()
        (self.root / "src").rename(self.root / "oldsrc")
        (self.root / "src").symlink_to(self.root / "oldsrc", target_is_directory=True)
        self.assertIn("UNSAFE_PARENT", self.codes(self.project.check(True)))

    def test_parent_replaced_by_file(self):
        self.start(); (self.root / "src/app.py").unlink(); (self.root / "src").rmdir()
        self.write("src", "not a directory")
        self.assertIn("UNSAFE_PARENT", self.codes(self.project.check(True)))

    @unittest.skipUnless(os.name == "posix", "POSIX FIFO")
    def test_fifo_does_not_hang(self):
        self.start(); (self.root / "src/app.py").unlink(); os.mkfifo(self.root / "src/app.py")
        self.assertIn("OPAQUE_PATH", self.codes(self.project.check(True)))

    def test_clean_and_process_filters_not_executed(self):
        self.write(".gitattributes", "*.py filter=spy\n")
        self.git("add", ".gitattributes"); self.git("commit", "-qm", "Fixture attributes")
        self.write("spy.py", "import pathlib,sys; pathlib.Path('MARKER').touch(); sys.stdout.write(sys.stdin.read())\n")
        command = f'"{sys.executable}" spy.py'
        self.git("config", "filter.spy.clean", command)
        self.git("config", "filter.spy.process", command)
        self.git("config", "filter.spy.required", "true")
        self.start(); self.edit(); self.project.check(False)
        self.assertFalse((self.root / "MARKER").exists())

    def test_external_diff_not_executed(self):
        self.write("spy.py", "from pathlib import Path; Path('MARKER').touch()\n")
        self.git("config", "diff.external", f'"{sys.executable}" spy.py')
        self.start(); self.edit(); self.project.check(False)
        self.assertFalse((self.root / "MARKER").exists())

    def test_packet_budget_and_complete_files(self):
        self.write("src/中文.txt", "你好世界\n" * 500)
        self.start()
        packet = self.project.packet(max_bytes=2400)
        self.assertLessEqual(len(packet.encode("utf-8")), 2400)
        self.assertNotIn("你好世界", packet)
        self.assertIn("omitted", packet)

    def test_packet_deterministic(self):
        self.start()
        self.assertEqual(self.project.packet(), self.project.packet())

    def test_packet_excludes_sensitive_names(self):
        self.write("src/secrets.pem", "PRIVATE_CONTENT_WITHOUT_KNOWN_PATTERN")
        self.start()
        self.assertNotIn("PRIVATE_CONTENT", self.project.packet())

    def test_packet_include_does_not_expand_scope(self):
        self.write("readme.txt", "CONTEXT_ONLY_CONTENT")
        self.start()
        self.assertIn("CONTEXT_ONLY_CONTENT", self.project.packet(include=["*.txt"]))
        self.write("readme.txt", "changed")
        self.assertIn("OUTSIDE_SCOPE", self.codes(self.project.check(True)))

    def test_newly_ignored_untracked_not_packed(self):
        self.write("src/local.txt", "DO_NOT_PACK_AFTER_IGNORING")
        self.start()
        self.write(".gitignore", "src/local.txt\n__pycache__/\n")
        self.assertNotIn("DO_NOT_PACK_AFTER_IGNORING", self.project.packet())

    def test_packet_rejects_bad_budget_and_traversal(self):
        self.start()
        for kwargs in ({"max_bytes": 1}, {"include": ["../*"]}):
            with self.assertRaises(StewardError):
                self.project.packet(**kwargs)

    def test_cli_exit_codes_and_json(self):
        self.assertEqual(self.cli("check")[0], 3)
        code, out, _ = self.cli("start", "Fix app", "--scope", "src/**", "--check-json", json.dumps([sys.executable, "-c", "pass"]))
        self.assertEqual(code, 0); json.loads(out); self.edit()
        code, out, _ = self.cli("check", "--format", "json")
        self.assertEqual(code, 2); self.assertEqual(json.loads(out)["verdict"], "needs-review")
        self.assertEqual(self.cli("check", "--run", "--format", "json")[0], 0)
        self.write("outside.txt", "oops")
        self.assertEqual(self.cli("check", "--run")[0], 1)

    def test_doctor_is_advisory(self):
        code, out, _ = self.cli("doctor")
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out)["suggestions_not_executed"])
        self.assertFalse(self.project.store.path.exists())

    def test_corrupt_state_detected(self):
        self.start(); self.project.store.path.write_text("not json")
        self.assertEqual(self.cli("check")[0], 3)

    def test_modified_contract_detected(self):
        self.start()
        state = json.loads(self.project.store.path.read_text())
        state["contract"]["scope"] = ["**"]
        self.project.store.path.write_text(json.dumps(state))
        with self.assertRaises(StewardError):
            self.project.check()

    def test_modified_receipt_detected(self):
        self.start(); self.edit(); self.project.check(True)
        state = json.loads(self.project.store.path.read_text())
        state["receipt"]["task"] = "changed"
        self.project.store.path.write_text(json.dumps(state))
        with self.assertRaises(StewardError):
            self.project.report()

    def test_mutually_exclusive_state_lock(self):
        self.start()
        with self.project.store.locked():
            with self.assertRaises(StewardError):
                self.project.check()
        self.assertFalse((self.project.store.directory / "lock").exists())

    @unittest.skipUnless(os.name == "posix", "POSIX file permissions")
    def test_private_state_permissions(self):
        self.start()
        self.assertEqual(stat.S_IMODE(self.project.store.path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.project.store.directory.stat().st_mode), 0o700)

    @unittest.skipUnless(os.name == "posix", "Symlink privileges")
    def test_symlinked_state_file_refused(self):
        self.start(); state = self.project.store.path.read_text()
        external = self.write("external.json", state)
        self.project.store.path.unlink(); self.project.store.path.symlink_to(external)
        with self.assertRaises(StewardError):
            self.project.check()

    @unittest.skipUnless(os.name == "posix", "Symlink privileges")
    def test_symlinked_state_directory_refused(self):
        external = self.root / "external"; external.mkdir()
        self.project.store.directory.symlink_to(external, target_is_directory=True)
        with self.assertRaises(StewardError):
            self.start()


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_python(self, code, timeout=5):
        return run_command(self.root, [sys.executable, "-c", code], timeout)

    def test_success(self):
        result = self.run_python("print('hello')")
        self.assertEqual(result["status"], "passed")
        self.assertIn("hello", result["output"])

    def test_failure(self):
        self.assertEqual(self.run_python("raise SystemExit(4)")["exit_code"], 4)

    def test_timeout(self):
        self.assertEqual(self.run_python("import time; time.sleep(10)", .05)["status"], "timeout")

    def test_missing_executable(self):
        self.assertEqual(run_command(self.root, ["nonexistent-stewardcheck-fixture-xyz"], 1)["status"], "error")

    def test_output_redaction(self):
        self.assertNotIn(TOKEN, self.run_python(f"print({TOKEN!r})")["output"])

    def test_capture_bounded(self):
        result = self.run_python(f"print('x' * {CAPTURE_BYTES * 2})")
        self.assertTrue(result["output_truncated"])
        self.assertLessEqual(len(result["output"].encode()), CAPTURE_BYTES)

    def test_excessive_output_stops_process(self):
        result = self.run_python(f"import sys; sys.stdout.write('x' * {OUTPUT_LIMIT + 65536})")
        self.assertEqual(result["status"], "output-limit")

    def test_terminal_controls_escaped(self):
        result = self.run_python("print('\\x1b[2Jdanger')")
        self.assertNotIn("\x1b", result["output"])

    @unittest.skipUnless(os.name == "posix", "POSIX process-group cleanup")
    def test_lingering_child_is_terminated(self):
        code = ("import subprocess, sys; subprocess.Popen([sys.executable, '-c', "
                "\"import time,pathlib; time.sleep(2); pathlib.Path('LEAK').touch()\"])")
        result = self.run_python(code)
        self.assertEqual(result["status"], "passed")
        import time
        time.sleep(2.1)
        self.assertFalse((self.root / "LEAK").exists())




class AdditionalBoundaries(RepositoryCase):
    def test_linked_worktrees_have_independent_state(self):
        self.start()
        linked_temp = tempfile.TemporaryDirectory()
        self.addCleanup(linked_temp.cleanup)
        linked = Path(linked_temp.name) / "worktree"
        self.git("worktree", "add", "--detach", str(linked))
        second = Project(linked)
        second.start(contract("Separate task", commands=[[sys.executable, "-c", "print(1)"]]))
        self.assertNotEqual(second.store.path, self.project.store.path)
        self.assertEqual(self.project.store.load()["contract"]["task"], "Fix the app")
        self.assertEqual(second.store.load()["contract"]["task"], "Separate task")

    def test_context_include_preserves_default_scope(self):
        self.write("docs/guide.md", "EXTRA_CONTEXT_MARKER")
        self.start()
        packet = self.project.packet(32000, ["docs/**"])
        self.assertIn("EXTRA_CONTEXT_MARKER", packet)
        self.assertIn("VALUE = 1", packet)
        self.assertEqual(self.project.store.load()["contract"]["scope"], ["src/**", "tests/**"])

    def test_tracked_ignored_file_remains_monitored(self):
        self.write(".env", "NORMAL_VALUE=1")
        self.git("add", "-f", ".env")
        self.start()
        self.write(".env", "NORMAL_VALUE=2")
        receipt = self.project.check()
        self.assertIn("PROTECTED_PATH", self.codes(receipt))
        self.assertIn(".env", [c["path"] for c in receipt["changes"]])

    def test_invalid_utf8_requires_review(self):
        self.start()
        (self.root / "src/app.py").write_bytes(b"\xff\xfe")
        self.assertIn("CONTENT_UNINSPECTED", self.codes(self.project.check()))

    def test_no_assertions_word_is_not_an_assertion(self):
        self.assertEqual(test_metrics("tests/test_x.py", "# no assertions remain")["assertions"], 0)

    def test_module_entrypoint(self):
        import runpy
        with patch.object(sys, "argv", ["stewardcheck", "--version"]), redirect_stdout(io.StringIO()) as out:
            with self.assertRaises(SystemExit) as result:
                runpy.run_module("stewardcheck", run_name="__main__")
        self.assertEqual(result.exception.code, 0)
        self.assertIn(f"stewardcheck {__version__}", out.getvalue())


if __name__ == "__main__":
    unittest.main()
