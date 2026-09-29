"""Exercise full DependencyFile and real asynchronous file I/O in temporary dirs.
Only aread/awrite are selected from the heavy common module; their bodies and
exception decorator are unchanged. No LLM or provider is initialized.
"""
import ast
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import sys
import types
import aiofiles
import chardet
from loguru import logger
import pytest

ROOT = Path(__file__).parent / os.getenv('VARIANT', 'after')
for name in ['metagpt', 'metagpt.utils']:
    module = types.ModuleType(name); module.__path__ = []; sys.modules[name] = module
logs = types.ModuleType('metagpt.logs'); logs.logger = logger; sys.modules[logs.__name__] = logs

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module); return module

exceptions = load('metagpt.utils.exceptions', 'metagpt/utils/exceptions.py')
common = types.ModuleType('metagpt.utils.common')
common.__dict__.update(Path=Path, aiofiles=aiofiles, chardet=chardet, handle_exception=exceptions.handle_exception)
source = ROOT/'metagpt/utils/common.py'
tree = ast.parse(source.read_text())
nodes = [n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name in {'aread','awrite'}]
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), common.__dict__)
sys.modules[common.__name__] = common
DependencyFile = load('metagpt.utils.dependency_file','metagpt/utils/dependency_file.py').DependencyFile

@pytest.mark.parametrize('target,dependency', [
    ('src/main.py','docs/design.md'),
    ('src/主程序.py','docs/设计.md'),
    ('src/main.py','docs/设计.md'),
    ('src/café.py','docs/résumé.md'),
    ('src/🚀.py','docs/🧪.md'),
    ('src/a"b.py','docs/c"d.md'),
    ('src/name\tpart.py','docs/note\nline.md'),
])
def test_update_get_and_fresh_load_roundtrip(tmp_path,target,dependency):
    async def run():
        store = DependencyFile(tmp_path)
        await store.update(tmp_path/target, {tmp_path/dependency})
        assert await store.get(tmp_path/target) == {dependency}
        fresh = DependencyFile(tmp_path)
        assert await fresh.get(tmp_path/target) == {dependency}
        await fresh.update(tmp_path/target, set())
        assert await DependencyFile(tmp_path).get(tmp_path/target) == set()
    asyncio.run(run())

@pytest.mark.parametrize('ensure_ascii',[True,False])
@pytest.mark.parametrize('target,dependencies', [
    (r'src\main.py',[r'docs\design.md']),
    (r'src\主程序.py',[r'docs\设计.md']),
    (r'src\\nested\file.py',[r'docs\\nested\input.md']),
])
def test_legacy_windows_paths_are_normalized_after_json_decoding(tmp_path,ensure_ascii,target,dependencies):
    raw = json.dumps({target:dependencies}, ensure_ascii=ensure_ascii)
    (tmp_path/'.dependencies.json').write_text(raw,encoding='utf-8')
    import re
    normalized_target = re.sub(r'\\+', '/', target)
    expected = {re.sub(r'\\+', '/', p) for p in dependencies}
    async def run():
        assert await DependencyFile(tmp_path).get(normalized_target) == expected
    asyncio.run(run())

def test_an_unrelated_update_does_not_rewrite_existing_unicode_keys(tmp_path):
    async def run():
        store=DependencyFile(tmp_path)
        await store.update('src/甲.py',{'docs/乙.md'})
        await store.update('src/main.py',{'docs/design.md'})
        assert await DependencyFile(tmp_path).get('src/甲.py') == {'docs/乙.md'}
        assert set(json.loads((tmp_path/'.dependencies.json').read_text())) == {'src/甲.py','src/main.py'}
    asyncio.run(run())

def test_absent_file_has_no_dependencies(tmp_path):
    assert asyncio.run(DependencyFile(tmp_path).get('missing.py')) == set()
