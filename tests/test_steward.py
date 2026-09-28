"""Synthetic tests only; never load project datasets or execute training code."""
import copy
from datetime import datetime, timezone
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "steward.py"
spec = importlib.util.spec_from_file_location("steward", SCRIPT)
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
NOW = datetime(2026, 9, 28, tzinfo=timezone.utc)


def record(key="old", **changes):
    r = dict(id=key, path=f".ai/scratch/{key}.md", kind="plan", status="superseded",
             owner="test-owner", expires_at="2026-01-01T00:00:00Z", pinned=False,
             running=False, reproducible=True, depends_on=[],
             closed_at="2026-01-01T00:00:00Z", reviewed_at="2026-09-28T00:00:00Z",
             references_checked=True, reproduce_command="restore from approved source",
             content_sha256=hashlib.sha256(b"same content").hexdigest())
    r.update(changes)
    return r


def evidence():
    base = dict(commit="a" * 40, dataset="dataset:fixture-v1", split="test-v1",
                protocol="protocol-v1", environment="python-fixture", hardware="cpu-fixture",
                precision="fp32", batch_size=1, training_budget="fixed-100-steps",
                measurement="warmup-10;sync;io-excluded;fixed-harness-v1", pairing_unit="independent-seed",
                config_sha256="c"*64, dirty_patch_sha256=None, command="python eval.py --fixture",
                raw_results="fixture://synthetic-result", seeds=[0, 1, 2, 3, 4],
                metrics={"latency": {"unit": "ms", "values": [100, 100, 100, 100, 100]}})
    candidate = copy.deepcopy(base)
    candidate["commit"] = "b" * 40
    candidate["metrics"]["latency"]["values"] = [90, 90, 90, 90, 90]
    return dict(schema_version=1, baseline=base, candidate=candidate,
                gates={"latency": dict(direction="lower", max_regression_pct=0, min_improvement_pct=5)})


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.PIPE)

    def put(self, rel, text="same content"):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def run_audit(self, *records, **kwargs):
        for r in records:
            if not (self.root / r["path"]).exists():
                self.put(r["path"])
        return s.audit(self.root, {"records": list(records)}, NOW, **kwargs)

    def test_default_empty_ledger_never_proposes_removal(self):
        self.put("planning_old.md")
        result = self.run_audit()
        self.assertEqual([], result["records"])
        self.assertIn("planning_old.md", result["unregistered_review_only"])

    def test_explicit_expired_candidate_is_only_proposal(self):
        result = self.run_audit(record())
        self.assertEqual("QUARANTINE_REVIEW", result["records"][0]["decision"])
        self.assertTrue((self.root / record()["path"]).exists())

    def test_old_mtime_not_expiry(self):
        r = record(expires_at=None)
        p = self.put(r["path"])
        os.utime(p, (1, 1))
        self.assertEqual("KEEP", self.run_audit(r)["records"][0]["decision"])

    def test_pinned_running_not_reproducible_and_active_are_kept(self):
        for changes in ({"pinned": True}, {"running": True}, {"reproducible": False}, {"status": "active"}):
            with self.subTest(changes=changes):
                self.assertEqual("KEEP", self.run_audit(record(**changes))["records"][0]["decision"])

    def test_transitive_dependencies_and_cycles(self):
        result = self.run_audit(record("root", pinned=True, depends_on=["mid"]),
                                record("mid", depends_on=["leaf"]), record("leaf", depends_on=["mid"]))
        self.assertTrue(all(r["decision"] == "KEEP" for r in result["records"]))

    def test_unknown_dependency_fails_closed(self):
        with self.assertRaises(ValueError):
            self.run_audit(record(depends_on=["missing"]))

    def test_protected_data_and_source_suffix(self):
        for path in ("data/raw.csv", ".ai/scratch/worker.py", ".ai/scratch/.env.json", "pretrain_models/model.json"):
            with self.subTest(path=path):
                self.assertEqual("KEEP", self.run_audit(record(path=path))["records"][0]["decision"])

    def test_tracked_file_is_kept(self):
        r = record()
        self.put(r["path"])
        self.git("add", r["path"])
        self.assertIn("tracked-file-requires-separate-pr", self.run_audit(r)["records"][0]["blockers"])

    def test_symlink_and_hardlink_are_kept(self):
        target = self.put("target.md")
        link = self.root / ".ai/scratch/link.md"
        link.parent.mkdir(parents=True)
        link.symlink_to(target)
        self.assertEqual("KEEP", self.run_audit(record(path=".ai/scratch/link.md"))["records"][0]["decision"])
        link.unlink()
        os.link(target, link)
        self.assertEqual("KEEP", self.run_audit(record(path=".ai/scratch/link.md"))["records"][0]["decision"])

    def test_parent_symlink_is_kept(self):
        self.put("elsewhere/file.md")
        (self.root / "runs").symlink_to(self.root / "elsewhere", target_is_directory=True)
        self.assertEqual("KEEP", self.run_audit(record(path="runs/file.md"))["records"][0]["decision"])

    def test_duplicate_hints_and_no_content_mutation(self):
        for r in (record("a"), record("b")):
            self.put(r["path"])
        before = {str(p): p.read_bytes() for p in (self.root / ".ai").rglob("*.md")}
        result = self.run_audit(record("a"), record("b"))
        after = {str(p): p.read_bytes() for p in (self.root / ".ai").rglob("*.md")}
        self.assertEqual(before, after)
        self.assertEqual(1, len(result["duplicate_hints"]))

    def test_inventory_limit_fails_explicitly(self):
        self.put("a.txt")
        self.put("b.txt")
        with self.assertRaises(ValueError):
            self.run_audit(max_files=1)

    def test_duplicate_ids_and_paths_fail(self):
        with self.assertRaises(ValueError):
            self.run_audit(record(), record())

    def test_non_boolean_flags_fail(self):
        with self.assertRaises(ValueError):
            self.run_audit(record(pinned="false"))

    def test_diff_handles_tabs_newlines_binary_and_dirty_tree(self):
        self.put("base.txt", "base\n")
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        base = self.git("rev-parse", "HEAD").decode().strip()
        self.put("odd\tname\n.py", "print('hi')\n")
        (self.root / "binary.dat").write_bytes(b"\0\xff")
        self.git("add", ".")
        self.git("commit", "-qm", "candidate")
        self.put("uncommitted.txt")
        result = s.diff_report(self.root, base, "HEAD")
        self.assertTrue(result["working_tree_dirty"])
        self.assertEqual(2, len(result["files"]))
        self.assertIn("odd\tname\n.py", [f["path"] for f in result["files"]])
        self.assertTrue(any(f["binary"] for f in result["files"]))

    def test_invalid_ref_not_fallback(self):
        with self.assertRaises(ValueError):
            s.diff_report(self.root, "--help", "HEAD")

    def test_unsafe_paths_fail(self):
        for path in ("../outside", "/tmp/file", "a/../b", "a\\b", "a//b", "./file", "C:/file"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                s.relative(path)

    def test_timestamp_requires_timezone(self):
        with self.assertRaises(ValueError):
            s.timestamp("2026-01-01")


class GateTests(unittest.TestCase):
    def test_pass_lower_and_higher(self):
        for direction, values in (("lower", [90] * 5), ("higher", [110] * 5)):
            data = evidence()
            data["gates"]["latency"]["direction"] = direction
            data["candidate"]["metrics"]["latency"]["values"] = values
            result, code = s.compare(data)
            self.assertEqual(0, code)
            self.assertEqual("NUMERIC_PASS", result["status"])
            self.assertAlmostEqual(10, result["metrics"][0]["improvement_pct"])

    def test_metadata_and_seed_order_mismatch(self):
        for key, value in (("hardware", "different"), ("split", "train"), ("seeds", [4, 3, 2, 1, 0])):
            data = evidence()
            data["candidate"][key] = value
            self.assertEqual("INCOMPARABLE", s.compare(data)[0]["status"])

    def test_mean_hides_pair_regression(self):
        data = evidence()
        data["candidate"]["metrics"]["latency"]["values"] = [101, 80, 80, 80, 80]
        self.assertEqual(1, s.compare(data)[1])

    def test_missing_metric_or_unit_mismatch_fails(self):
        data = evidence()
        data["candidate"]["metrics"]["latency"]["unit"] = "s"
        with self.assertRaises(ValueError):
            s.compare(data)
        data = evidence()
        data["gates"]["unknown"] = data["gates"]["latency"]
        with self.assertRaises(ValueError):
            s.compare(data)

    def test_insufficient_pairs(self):
        data = evidence()
        data["min_pairs"] = 6
        self.assertEqual(2, s.compare(data)[1])

    def test_zero_baseline_relative_is_not_false_pass(self):
        data = evidence()
        for run in ("baseline", "candidate"):
            data[run]["metrics"]["latency"]["values"] = [0] * 5
        self.assertEqual("INSUFFICIENT_EVIDENCE", s.compare(data)[0]["status"])
        data["gates"]["latency"] = dict(direction="lower", max_regression_abs=0)
        self.assertEqual(0, s.compare(data)[1])

    def test_nan_bool_negative_tolerance_rejected(self):
        for value in (float("nan"), float("inf"), True):
            data = evidence()
            data["candidate"]["metrics"]["latency"]["values"][0] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                s.compare(data)
        data = evidence()
        data["gates"]["latency"]["max_regression_pct"] = -1
        with self.assertRaises(ValueError):
            s.compare(data)

    def test_example_is_never_real_evidence(self):
        data = evidence()
        data["example"] = True
        result, code = s.compare(data)
        self.assertEqual("EXAMPLE_ONLY", result["status"])
        self.assertEqual("NUMERIC_PASS", result["numeric_status"])
        self.assertEqual(2, code)

    def test_unknown_gate_field_fails(self):
        data = evidence()
        data["gates"]["latency"]["max_regression_pcnt"] = 0
        with self.assertRaises(ValueError):
            s.compare(data)

    def test_cli_exit_codes_and_invalid_json(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.json"
            for data, expected in ((evidence(), 0), ({**evidence(), "min_pairs": 10}, 2)):
                path.write_text(json.dumps(data))
                result = subprocess.run([sys.executable, "-B", str(SCRIPT), "gate", "--input", str(path)], capture_output=True)
                self.assertEqual(expected, result.returncode)
            data = evidence()
            data["candidate"]["metrics"]["latency"]["values"] = [110] * 5
            path.write_text(json.dumps(data))
            self.assertEqual(1, subprocess.run([sys.executable, "-B", str(SCRIPT), "gate", "--input", str(path)], capture_output=True).returncode)
            for text in ('{"schema_version": 1, "schema_version": 1}', '{"schema_version": 1, "value": NaN}'):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    s.read_json(path)


if __name__ == "__main__":
    unittest.main()
