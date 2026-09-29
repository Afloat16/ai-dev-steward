"""Load actual temporary tool modules with the complete FunctionManager."""
import importlib.util
import os
from pathlib import Path
import sys
import types
import pytest

p=Path(__file__).parent/os.getenv('VARIANT','after')/'utils/function_manager.py'
spec=importlib.util.spec_from_file_location('tested_function_manager',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

@pytest.fixture
def tool_dir(tmp_path):
    yield tmp_path
    for name in list(sys.modules):
        if name.startswith('_dynamic_functions.'):
            module=sys.modules[name]
            if str(tmp_path) in str(getattr(module,'__file__','')):sys.modules.pop(name,None)

@pytest.mark.parametrize('extra',['','from typing import ClassVar\n'])
def test_future_annotated_dataclass_tool_is_discovered_and_callable(tool_dir,extra):
    code=('from __future__ import annotations\nfrom dataclasses import dataclass\n'+extra+
          '@dataclass\nclass Payload:\n    value: int\n\ndef increment(value: int) -> int:\n    return Payload(value).value + 1\n')
    (tool_dir/'tools.py').write_text(code)
    manager=m.FunctionManager(tool_dir)
    assert manager.has_function('increment')
    assert manager.call_function('increment',41)==42
    assert 'dataclass' not in manager.list_functions()

def test_module_can_resolve_its_own_future_annotated_class(tool_dir):
    (tool_dir/'tools.py').write_text('from __future__ import annotations\nfrom dataclasses import dataclass\n@dataclass\nclass Payload:\n    parent: Payload | None = None\n\ndef root():\n    return Payload().parent\n')
    assert m.FunctionManager(tool_dir).call_function('root') is None

def test_plain_tool_behavior_is_unchanged(tool_dir):
    (tool_dir/'tools.py').write_text('from math import floor\ndef answer():\n    return 42\ndef _private():\n    return 0\n')
    manager=m.FunctionManager(tool_dir)
    assert list(manager.list_functions())==['answer']
    assert manager.call_function('answer')==42

def test_failed_module_does_not_leave_partial_entry(tool_dir):
    path=tool_dir/'broken.py';path.write_text('raise RuntimeError("expected test failure")\n')
    manager=m.FunctionManager(tool_dir);name=manager._build_module_name(path)
    assert name not in sys.modules
    assert manager.list_functions()=={}
    assert name not in sys.modules

def test_failed_reload_restores_previous_module_entry(tool_dir):
    path=tool_dir/'broken.py';path.write_text('raise RuntimeError("expected test failure")\n')
    manager=m.FunctionManager(tool_dir);name=manager._build_module_name(path)
    old=types.ModuleType(name);old.__file__=str(path);sys.modules[name]=old
    assert manager.list_functions()=={}
    assert sys.modules[name] is old

def test_successful_load_registers_executed_module(tool_dir):
    path=tool_dir/'tools.py';path.write_text('def answer():\n    return 42\n')
    manager=m.FunctionManager(tool_dir);func=manager.get_function('answer')
    assert sys.modules.get(func.__module__) is not None
    assert sys.modules[func.__module__].answer is func
