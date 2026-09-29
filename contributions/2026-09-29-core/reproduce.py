#!/usr/bin/env python3
"""Verify pinned upstream files and run each regression case in a separate process.

The evidence ZIP works offline. A GitHub checkout needs --fetch once to obtain
only the pinned public files. No credentials, model calls, or installation steps
are performed. Existing edited source files are never overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent


def safe_path(base: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError(f'Unsafe source path: {relative!r}')
    return base.joinpath(*path.parts)


def blob_hash(data: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def prepare(case: Path, fetch: bool) -> None:
    manifest = case / 'manifest.json'
    metadata = (json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists()
                else json.loads((ROOT / 'source_index.json').read_text(encoding='utf-8'))[case.name])
    with tempfile.TemporaryDirectory(prefix='core-regression-') as temporary:
        work = Path(temporary)
        for item in metadata['sources']:
            original = safe_path(case / 'before', item['path'])
            if original.exists():
                data = original.read_bytes()
            elif fetch:
                url = f"https://raw.githubusercontent.com/{metadata['repo']}/{metadata['commit']}/{item['path']}"
                with urllib.request.urlopen(url, timeout=30) as response:
                    data = response.read(2_000_001)
                if len(data) > 2_000_000:
                    raise ValueError('Source file exceeds the download bound')
                if blob_hash(data) != item['git_blob']:
                    raise ValueError(f'Unexpected upstream source: {item["path"]}')
                original.parent.mkdir(parents=True, exist_ok=True)
                original.write_bytes(data)
            else:
                raise FileNotFoundError(f'{original} is missing; use the evidence ZIP or --fetch')
            if blob_hash(data) != item['git_blob']:
                raise ValueError(f'Original source was modified: {original}')
            target = safe_path(work, item['path'])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        patch = str((case / 'fix.patch').resolve())
        for command in (['git', 'apply', '--check', patch], ['git', 'apply', patch]):
            subprocess.run(command, cwd=work, check=True, timeout=15, capture_output=True, text=True)
        for item in metadata['sources']:
            data = safe_path(work, item['path']).read_bytes()
            if hashlib.sha256(data).hexdigest() != item['after_sha256']:
                raise ValueError(f'Patched bytes differ from the tested source: {item["path"]}')
            modified = safe_path(case / 'after', item['path'])
            if modified.exists() and modified.read_bytes() != data:
                raise ValueError(f'Refusing to overwrite edited source: {modified}')
            if not modified.exists():
                modified.parent.mkdir(parents=True, exist_ok=True)
                modified.write_bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', default='all', help='Case directory name, or all')
    parser.add_argument('--variant', choices=('before', 'after'), default='after')
    parser.add_argument('--fetch', action='store_true', help='Download missing pinned public source files')
    parser.add_argument('--verify-only', action='store_true', help='Verify source and patch without executing tests')
    args = parser.parse_args()
    if not shutil.which('git'):
        parser.error('Git is required for patch verification')
    cases = sorted(p for p in (ROOT / 'cases').iterdir() if (p / 'test_regression.py').exists())
    if args.case != 'all':
        cases = [p for p in cases if p.name == args.case]
        if not cases:
            parser.error('Unknown case')
    failures = 0
    for case in cases:
        try:
            prepare(case, args.fetch)
            print(f'{case.name}: source hashes and patch application verified', flush=True)
            if args.verify_only:
                continue
            environment = dict(os.environ, VARIANT=args.variant, PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
            result = subprocess.run(
                [sys.executable, '-m', 'pytest', 'test_regression.py', '-q', '--tb=short'],
                cwd=case, env=environment, capture_output=True, text=True, timeout=45,
            )
            output = result.stdout + result.stderr
            (case / f'{args.variant}-recheck.log').write_text(output, encoding='utf-8')
            print(output, end='', flush=True)
            failures += result.returncode != 0
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            failures += 1
            print(f'{case.name}: {error}', file=sys.stderr)
    if args.variant == 'before' and not args.verify_only:
        print('Before tests intentionally reproduce failures; a nonzero exit code is expected.')
    return int(failures != 0)


if __name__ == '__main__':
    raise SystemExit(main())
