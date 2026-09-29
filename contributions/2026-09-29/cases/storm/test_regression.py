import ast
import os
import types
from pathlib import Path
import pytest
import re
from typing import List, Dict, Optional

_path=Path(__file__).with_name(os.environ.get('VARIANT','after')+'.py')
_tree=ast.parse(_path.read_text(encoding='utf-8'))
_names=['ArticleTextProcessing']
_nodes=[n for n in _tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and n.name in _names]
assert len(_nodes)==len(_names), 'Selected definitions missing from pinned source'
_ns=dict(globals())
exec(compile(ast.Module(body=_nodes,type_ignores=[]),str(_path),'exec'),_ns)
target=types.SimpleNamespace(**_ns)

@pytest.mark.parametrize('text, expected', [
 ('A fact.[1][2]', 'A fact.[1][2]'),
 ('A fact. [1][2][3]', 'A fact. [1][2][3]'),
 ('A fact. [1] [2]', 'A fact. [1] [2]'),
 ('A fact.[1][2] Unfinished', 'A fact.[1][2]'),
 ('A fact! [2][1][2]', 'A fact! [1][2]'),
 ('A fact.[1]', 'A fact.[1]'),
 ('A fact.', 'A fact.'),
 ('A fact. Unfinished', 'A fact.'),
 ('No punctuation', 'No punctuation'),
 ('', ''),
])
def test_trailing_citations(text,expected):
 actual=target.ArticleTextProcessing.remove_uncompleted_sentences_with_citations(text)
 assert actual==expected
