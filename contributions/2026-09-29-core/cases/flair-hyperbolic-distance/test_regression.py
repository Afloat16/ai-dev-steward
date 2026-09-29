"""Full hyperbolic distance module vs explicit Lorentz-product geometry."""
import importlib.util
import os
from pathlib import Path
import pytest
import torch

torch.set_num_threads(1)
p=Path(__file__).parent/os.getenv('VARIANT','after')/'flair/nn/distance/hyperbolic.py'
spec=importlib.util.spec_from_file_location('tested_hyperbolic',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def oracle(x,y):
    # Spatial x,y are embedded as (sqrt(1+||x||^2), x).
    x0=(1+x.square().sum(-1)).sqrt()
    y0=(1+y.square().sum(-1)).sqrt()
    lorentz=x0[:,None]*y0[None,:]-x@y.T
    return torch.acosh(lorentz.clamp(min=1+m.EPSILON)).square()

@pytest.mark.parametrize('dims',[1,2,5,12])
@pytest.mark.parametrize('seed',[4,19])
def test_distance_and_gradients_match_independent_geometry(dims,seed):
    g=torch.Generator().manual_seed(seed)
    x=torch.randn(4,dims,generator=g,dtype=torch.float64,requires_grad=True)
    y=torch.randn(3,dims,generator=g,dtype=torch.float64,requires_grad=True)
    expected=oracle(x,y);actual=m.HyperbolicDistance()(x,y)
    torch.testing.assert_close(actual,expected,rtol=1e-9,atol=1e-9)
    a=torch.autograd.grad(actual.sum(),(x,y),retain_graph=True)
    b=torch.autograd.grad(expected.sum(),(x,y))
    for aa,bb in zip(a,b):torch.testing.assert_close(aa,bb,rtol=1e-8,atol=1e-8)

def test_self_distance_respects_existing_epsilon_floor():
    x=torch.tensor([[1.,0.],[3.,2.]],dtype=torch.float64)
    distance=m.HyperbolicDistance()(x,x)
    floor=torch.acosh(torch.tensor(1+m.EPSILON,dtype=x.dtype)).square()
    torch.testing.assert_close(distance.diag(),floor.expand(2),rtol=1e-9,atol=1e-9)

def test_permuting_spatial_coordinates_does_not_change_distance():
    x=torch.tensor([[2.,.3],[1.,-.5]],dtype=torch.float64)
    y=torch.tensor([[-1.,.4],[3.,-.2]],dtype=torch.float64)
    metric=m.HyperbolicDistance()
    torch.testing.assert_close(metric(x,y),metric(x.flip(-1),y.flip(-1)))

def test_matching_first_coordinate_beats_its_opposite():
    query=torch.tensor([[1.,0.]],dtype=torch.float64)
    candidates=torch.tensor([[1.,0.],[-1.,0.]],dtype=torch.float64)
    scores=m.HyperbolicDistance()(query,candidates)[0]
    assert scores[0]<scores[1]

def test_zero_first_coordinate_is_unchanged():
    x=torch.tensor([[0.,2.],[0.,-1.]],dtype=torch.float64)
    y=torch.tensor([[0.,.5]],dtype=torch.float64)
    torch.testing.assert_close(m.HyperbolicDistance()(x,y),oracle(x,y))
