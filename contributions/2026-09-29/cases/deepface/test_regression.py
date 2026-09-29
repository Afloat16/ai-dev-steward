import ast
import os
import types
from pathlib import Path
import pytest
import numpy as np
from numpy.typing import NDArray
from typing import Any, List, Union, cast

_path=Path(__file__).with_name(os.environ.get('VARIANT','after')+'.py')
_tree=ast.parse(_path.read_text(encoding='utf-8'))
_names=['find_angular_distance', 'l2_normalize']
_nodes=[n for n in _tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and n.name in _names]
assert len(_nodes)==len(_names), 'Selected definitions missing from pinned source'
_ns=dict(globals())
exec(compile(ast.Module(body=_nodes,type_ignores=[]),str(_path),'exec'),_ns)
target=types.SimpleNamespace(**_ns)

@pytest.mark.parametrize('dim',[2,7,8,128])
@pytest.mark.parametrize('sign',[1,-1])
def test_single_parallel_vectors(dim,sign):
 a=np.ones(dim,dtype=np.float32)
 with np.errstate(invalid='raise'):
  actual=target.find_angular_distance(a,sign*a)
 assert np.isfinite(actual)
 assert float(actual)==pytest.approx(0 if sign==1 else 1,abs=2e-4)

@pytest.mark.parametrize('dim',[7,31])
def test_batch_parallel_vectors(dim):
 a=np.ones((1,dim),dtype=np.float32)
 with np.errstate(invalid='raise'):
  actual=target.find_angular_distance(a,np.concatenate([a,-a]))
 np.testing.assert_allclose(actual,[[0],[1]],atol=2e-4)

@pytest.mark.parametrize('a,b,expected',[
 ([1.,0.],[0.,1.],.5),([1.,0.],[-1.,0.],1),([1.,0.],[1.,0.],0)
])
def test_float64_controls(a,b,expected):
 assert target.find_angular_distance(a,b)==pytest.approx(expected)

def test_invalid_rank():
 with pytest.raises(ValueError):
  target.find_angular_distance(np.zeros((1,1,2)),np.zeros((1,1,2)))
