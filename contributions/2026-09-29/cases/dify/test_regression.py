import ast
import os
import types
from pathlib import Path
import pytest
import datetime
import pytz

_path=Path(__file__).with_name(os.environ.get('VARIANT','after')+'.py')
_tree=ast.parse(_path.read_text(encoding='utf-8'))
_names=['parse_time_range']
_nodes=[n for n in _tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and n.name in _names]
assert len(_nodes)==len(_names), 'Selected definitions missing from pinned source'
_ns=dict(globals())
exec(compile(ast.Module(body=_nodes,type_ignores=[]),str(_path),'exec'),_ns)
target=types.SimpleNamespace(**_ns)

@pytest.mark.parametrize('zone,text,expected',[
 ('Australia/Lord_Howe','2024-10-06 02:15','2024-10-05T15:45:00+00:00'),
 ('Australia/Lord_Howe','2024-10-06 02:00','2024-10-05T15:30:00+00:00'),
 ('Pacific/Apia','2011-12-30 12:00','2011-12-30T22:00:00+00:00'),
 ('Pacific/Apia','2011-12-30 00:00','2011-12-30T10:00:00+00:00'),
 ('America/New_York','2024-03-10 02:30','2024-03-10T07:30:00+00:00'),
 ('America/New_York','2024-11-03 01:30','2024-11-03T06:30:00+00:00'),
 ('UTC','2024-01-01 12:00','2024-01-01T12:00:00+00:00'),
 ('Asia/Kolkata','2024-01-01 12:00','2024-01-01T06:30:00+00:00'),
])
def test_time_gaps_and_controls(zone,text,expected):
 start,end=target.parse_time_range(text,None,zone)
 assert start.isoformat()==expected
 assert end is None

def test_empty():
 assert target.parse_time_range(None,None,'UTC')==(None,None)

def test_invalid_format():
 with pytest.raises(ValueError,match='Invalid start time format'):
  target.parse_time_range('nonsense',None,'UTC')

def test_invalid_order():
 with pytest.raises(ValueError,match='start must'):
  target.parse_time_range('2024-01-02 12:00','2024-01-01 12:00','UTC')
