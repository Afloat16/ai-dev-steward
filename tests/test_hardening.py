"""Safety/traceability regression tests. All evidence is synthetic test data."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

from test_steward import AuditTests as _Fixture, s, record, evidence, NOW, SCRIPT


# Use the fixture without inheriting/re-running its original test methods.
class HardeningTests(unittest.TestCase):
    setUp = _Fixture.setUp
    tearDown = _Fixture.tearDown
    git = _Fixture.git
    put = _Fixture.put
    run_audit = _Fixture.run_audit

    def test_missing_new_ledger_proof_keeps_v1_records(self):
        for key in ('closed_at', 'reviewed_at', 'references_checked', 'reproduce_command', 'content_sha256'):
            r = record()
            del r[key]
            with self.subTest(key=key):
                self.assertEqual('KEEP', self.run_audit(r)['records'][0]['decision'])

    def test_example_ledger_never_emits_candidates(self):
        r = record()
        self.put(r['path'])
        out = s.audit(self.root, {'records': [r], 'example': True}, NOW)
        self.assertEqual('EXAMPLE_ONLY', out['status'])
        self.assertEqual('KEEP', out['records'][0]['decision'])
        self.assertEqual(0, out['candidate_bytes_not_reclaimed'])

    def test_hash_mismatch_protects_transitive_dependency(self):
        a, b = record('a', depends_on=['b']), record('b')
        self.put(a['path'], 'new unreviewed decisions')
        self.put(b['path'])
        out = s.audit(self.root, {'records': [a, b]}, NOW)
        self.assertTrue(all(r['decision'] == 'KEEP' for r in out['records']))
        self.assertIn('content-hash-mismatch', out['records'][0]['blockers'])
        self.assertIn('referenced-by-retained-artifact', out['records'][1]['blockers'])

    def test_stale_future_and_invalid_lifecycle_are_kept(self):
        variants = [{'reviewed_at': '2026-09-01T00:00:00Z'},
                    {'reviewed_at': '2026-09-29T00:00:00Z'},
                    {'closed_at': '2026-10-01T00:00:00Z'},
                    {'closed_at': '2026-01-02T00:00:00Z'}]
        for changes in variants:
            with self.subTest(changes=changes):
                self.assertEqual('KEEP', self.run_audit(record(**changes))['records'][0]['decision'])

    def test_staged_deletion_remains_protected_by_head(self):
        r = record()
        self.put(r['path'])
        self.git('add', '.')
        self.git('commit', '-qm', 'baseline')
        self.git('rm', '--cached', r['path'])
        self.assertIn('tracked-file-requires-separate-pr', self.run_audit(r)['records'][0]['blockers'])

    def test_nested_repo_is_not_scanned_or_candidate(self):
        folder = self.root / 'runs/child'
        folder.mkdir(parents=True)
        subprocess.run(['git', '-C', str(folder), 'init', '-q'], check=True)
        r = record(path='runs/child/plan.md')
        out = self.run_audit(r)
        self.assertIn('nested-repository-requires-separate-audit', out['records'][0]['blockers'])
        self.assertIn('runs/child', out['excluded_directories'])

    def test_scope_limits_inventory_and_keeps_outside_records(self):
        a, b = record('a', path='runs/a.md'), record('b', path='plans/b.md')
        self.put(a['path']); self.put(b['path']); self.put('elsewhere/temp.md')
        out = self.run_audit(a, b, scope=['runs', 'runs'])
        self.assertEqual('QUARANTINE_REVIEW', out['records'][0]['decision'])
        self.assertEqual('KEEP', out['records'][1]['decision'])
        self.assertNotIn('elsewhere/temp.md', out['unregistered_review_only'])

    def test_protected_or_symlink_scope_refused(self):
        self.put('data/file.txt')
        (self.root / 'link').symlink_to(self.root / 'data', target_is_directory=True)
        for scope in (['data'], ['link'], ['../outside']):
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                s.audit(self.root, {'records': []}, NOW, scope=scope)

    def test_hash_budget_large_file_kept(self):
        r = record()
        self.put(r['path'], 'x' * (1024 * 1024 + 1))
        out = self.run_audit(r)
        self.assertIn('hash-budget-exceeded', out['records'][0]['blockers'])

    def test_planing_typo_and_tracked_plan_detected(self):
        self.put('planing_old.md'); self.put('plan-v2.md')
        self.git('add', 'plan-v2.md')
        out = self.run_audit()
        hints = {x['path']: x['tracked'] for x in out['plan_consolidation_review']}
        self.assertFalse(hints['planing_old.md'])
        self.assertTrue(hints['plan-v2.md'])
        self.assertFalse(out['records'])

    def test_empty_file_can_be_hashed(self):
        r = record(content_sha256=hashlib.sha256(b'').hexdigest())
        self.put(r['path'], '')
        self.assertEqual('QUARANTINE_REVIEW', self.run_audit(r)['records'][0]['decision'])

    def test_git_environment_does_not_redirect_root_or_index(self):
        self.put('tracked.md')
        self.git('add', 'tracked.md')
        with mock.patch.dict(os.environ, {'GIT_DIR': '/nonexistent/git', 'GIT_INDEX_FILE': '/nonexistent/index'}):
            self.assertEqual(self.root, s.repo_root(str(self.root)))
            self.assertIn(b'tracked.md', s.git(self.root, 'ls-files'))

    def test_globs_in_ledger_paths_refused(self):
        for value in ('runs/*.json', 'runs/[abc].log', 'runs/?.md', 'runs/bad\x7f.md'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                s.relative(value)

    def test_symlink_json_refused(self):
        target = self.put('real.json', json.dumps(evidence()))
        link = self.root / 'linked.json'
        link.symlink_to(target)
        with self.assertRaises(ValueError):
            s.read_json(link)

    def test_empty_directories_are_bounded(self):
        for i in range(10):
            (self.root / str(i)).mkdir()
        with self.assertRaises(ValueError):
            self.run_audit(max_files=1)

    def test_gate_missing_provenance_does_not_pass(self):
        for key in ('training_budget', 'measurement', 'pairing_unit', 'command', 'raw_results', 'config_sha256', 'dirty_patch_sha256'):
            data = evidence()
            for run in ('baseline', 'candidate'):
                del data[run][key]
            out, code = s.compare(data)
            self.assertEqual('UNVERIFIED_PROVENANCE', out['status'], key)
            self.assertEqual(2, code)

    def test_budget_or_measurement_mismatch_is_incomparable(self):
        for key in ('training_budget', 'measurement', 'pairing_unit'):
            data = evidence()
            data['candidate'][key] = 'changed'
            self.assertEqual('INCOMPARABLE', s.compare(data)[0]['status'])

    def test_example_flag_must_be_boolean(self):
        for function, data in ((s.compare, evidence()), (lambda d: s.audit(self.root, d, NOW), {'records': []})):
            data['example'] = 'false'
            with self.assertRaises(ValueError):
                function(data)

    def review_fixture(self):
        self.put('model.py', 'def value():\n    return 1\n')
        self.git('add', '.'); self.git('commit', '-qm', 'base')
        base = self.git('rev-parse', 'HEAD').decode().strip()
        self.put('model.py', 'def value():\n    return 2\n')
        self.git('add', '.'); self.git('commit', '-qm', 'candidate')
        head = self.git('rev-parse', 'HEAD').decode().strip()
        data = evidence()
        data['baseline']['commit'], data['candidate']['commit'] = base, head
        data['changes'] = [dict(id='a', kind='algorithm', files=['model.py'], hypothesis='synthetic',
                                invariants=['same interface'], tests=[dict(command='DO_NOT_EXECUTE', status='passed', evidence='fixture://test')],
                                rollback='git revert ' + head),
                           dict(id='b', kind='runtime', files=['model.py'], hypothesis='synthetic',
                                invariants=['same output'], tests=[dict(command='DO_NOT_EXECUTE', status='passed', evidence='fixture://test')],
                                rollback='disable synthetic flag', depends_on=['a'])]
        data['ablations'] = [dict(factors=factors, status='measured', commit=head if factors else base, evidence='fixture://ablation')
                             for factors in ([], ['a'], ['b'], ['a', 'b'])]
        return base, head, data

    def test_review_complete_declared_map_passes_without_executing_commands(self):
        base, head, data = self.review_fixture()
        out, code = s.review_report(self.root, base, head, data)
        self.assertEqual(0, code, out['gaps'])
        self.assertEqual('CHECKS_PASS', out['status'])
        self.assertEqual(['a', 'b'], out['reading_order'])
        self.assertIn('not merge approval', out['limitations'])

    def test_review_missing_single_factor_not_hidden_by_full_improvement(self):
        base, head, data = self.review_fixture()
        data['ablations'] = [row for row in data['ablations'] if row['factors'] != ['b']]
        out, code = s.review_report(self.root, base, head, data)
        self.assertEqual([['b']], out['missing_ablations'])
        self.assertEqual(2, code)

    def test_review_unmapped_and_stale_files(self):
        base, head, data = self.review_fixture()
        for c in data['changes']:
            c['files'] = ['wrong.py']
        out, code = s.review_report(self.root, base, head, data)
        self.assertEqual(['model.py'], out['unmapped_files'])
        self.assertEqual(['wrong.py'], out['out_of_scope_files'])
        self.assertEqual(2, code)

    def test_review_commit_mismatch_and_dirty_evidence(self):
        base, head, data = self.review_fixture()
        data['candidate']['commit'] = 'a' * 40
        data['candidate']['dirty_patch_sha256'] = 'b' * 64
        out, code = s.review_report(self.root, base, head, data)
        self.assertEqual(2, code)
        self.assertTrue(any('commits do not match' in x for x in out['gaps']))
        self.assertTrue(any('dirty patch' in x for x in out['gaps']))

    def test_review_missing_tests_rollback_invariants_blocked(self):
        base, head, data = self.review_fixture()
        c = data['changes'][0]
        c['tests'], c['rollback'], c['invariants'] = [], '', []
        out, code = s.review_report(self.root, base, head, data)
        self.assertEqual(2, code)
        self.assertTrue(any('no test evidence' in x for x in out['gaps']))

    def test_review_dependency_cycle_rejected(self):
        base, head, data = self.review_fixture()
        data['changes'][0]['depends_on'] = ['b']
        with self.assertRaises(ValueError):
            s.review_report(self.root, base, head, data)

    def test_review_dirty_tree_is_explicit(self):
        base, head, data = self.review_fixture()
        self.put('untracked.py', 'new code')
        out, code = s.review_report(self.root, base, head, data)
        self.assertEqual(2, code)
        self.assertTrue(out['diff']['working_tree_dirty'])
        self.assertEqual('untracked.py', out['diff']['working_tree']['files'][0]['path'])

    def test_review_examples_never_pass(self):
        base, head, data = self.review_fixture()
        data['example'] = True
        out, code = s.review_report(self.root, base, head, data)
        self.assertEqual('EXAMPLE_ONLY', out['status'])
        self.assertEqual(2, code)

    def test_review_markdown_escapes_html_and_links(self):
        base, head, data = self.review_fixture()
        data['changes'][0]['hypothesis'] = '<img src="evil"> [go](https://evil.invalid)'
        out, _ = s.review_report(self.root, base, head, data)
        text = s.markdown_review(out)
        self.assertNotIn('<img', text)
        self.assertNotIn('[go](', text)
        self.assertIn('AI Dev Steward', text)

    def test_ablation_wrong_baseline_sha_not_accepted(self):
        base, head, data = self.review_fixture()
        data['ablations'][0]['commit'] = head
        out, code = s.review_report(self.root, base, head, data)
        self.assertIn([], out['missing_ablations'])
        self.assertEqual(2, code)

    def test_duplicate_ablation_rejected(self):
        base, head, data = self.review_fixture()
        data['ablations'].append(copy.deepcopy(data['ablations'][0]))
        with self.assertRaises(ValueError):
            s.review_report(self.root, base, head, data)

    def test_cli_review_markdown_and_no_new_files(self):
        base, head, data = self.review_fixture()
        # Keep input outside the reviewed tree, so untracked work is not concealed.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'evidence.json'
            path.write_text(json.dumps(data))
            before = self.git('status', '--porcelain')
            out = subprocess.run([sys.executable, '-B', str(SCRIPT), 'review', '--root', str(self.root),
                                  '--base', base, '--head', head, '--input', str(path), '--format', 'markdown'], capture_output=True)
            self.assertEqual(0, out.returncode, out.stderr)
            self.assertIn(b'CHECKS\\_PASS', out.stdout)
            self.assertEqual(before, self.git('status', '--porcelain'))


    def test_explicit_high_risk_interaction_is_required(self):
        base, head, data = self.review_fixture()
        third = copy.deepcopy(data['changes'][1])
        third['id'], third['depends_on'] = 'c', []
        data['changes'].append(third)
        data['ablations'] = [row for row in data['ablations'] if row['factors'] != ['a', 'b']]
        data['ablations'] += [dict(factors=f, status='measured', commit=head, evidence='fixture://ablation')
                              for f in (['c'], ['a', 'b', 'c'])]
        data['required_interactions'] = [['a', 'b']]
        out, code = s.review_report(self.root, base, head, data)
        self.assertEqual([['a', 'b']], out['missing_ablations'])
        self.assertEqual(2, code)

    def test_staged_deleted_gitlink_remains_protected_without_git_marker(self):
        self.put('base.md')
        self.git('add', '.'); self.git('commit', '-qm', 'base')
        head = self.git('rev-parse', 'HEAD').decode().strip()
        self.git('update-index', '--add', '--cacheinfo', '160000,' + head + ',runs/module')
        self.git('commit', '-qm', 'gitlink')
        self.git('rm', '--cached', 'runs/module')
        r = record(path='runs/module/old.md')
        out = self.run_audit(r)
        self.assertIn('protected-path', out['records'][0]['blockers'])
        self.assertEqual('KEEP', out['records'][0]['decision'])

    def test_worktree_rename_reports_original_path(self):
        self.put('old.py', 'x=1')
        self.git('add', '.'); self.git('commit', '-qm', 'base')
        self.git('mv', 'old.py', 'new.py')
        out = s.working_changes(self.root)
        self.assertEqual('new.py', out['files'][0]['path'])
        self.assertEqual('old.py', out['files'][0]['original_path'])


del _Fixture
