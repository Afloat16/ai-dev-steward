"""Batched masked GAE compared with independent per-trajectory recurrences."""
import importlib.util
import os
from pathlib import Path
import sys
import types

import numpy as np
import pytest
import torch

BASE=Path(__file__).parent/os.environ.get('VARIANT','after')
for name, path in [('verl','verl'),('verl.utils','verl/utils'),('verl.trainer','verl/trainer')]:
    package=types.ModuleType(name)
    package.__path__=[str(BASE/path)]
    sys.modules[name]=package

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,BASE/path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module

load('verl.utils.torch_dtypes','verl/utils/torch_dtypes.py')
load('verl.utils.torch_functional','verl/utils/torch_functional.py')
alg=load('verl.trainer.core_algos','verl/trainer/core_algos.py')

def reference(rewards,values,mask,gamma,lam):
    result=np.zeros_like(values)
    for row in range(len(values)):
        next_value=0.0
        running=0.0
        for t in range(values.shape[1]-1,-1,-1):
            if mask[row,t]:
                running=rewards[row,t]+gamma*next_value-values[row,t]+gamma*lam*running
                next_value=values[row,t]
            result[row,t]=running
    returns=result+values
    count=mask.sum()
    mean=(result*mask).sum()/(count+1e-8)
    variance=(((result-mean)**2)*mask).sum()/(count+1e-8)
    if count>1:
        variance*=count/(count-1)
    whitened=(result-mean)/np.sqrt(variance+1e-8)
    return whitened,returns

MASKS=[
    [[1,1,1,1]],
    [[1,1,0,0]],
    [[1,1,1,1],[1,1,1,1]],
    [[1,1,1,0],[1,0,0,0]],
    [[1,0,1,0],[0,1,0,1]],
    [[0,0,0,0],[1,1,1,1]],
    [[1,1,0,0],[1,1,1,0],[1,1,1,1]],
]
@pytest.mark.parametrize('mask_values',MASKS)
@pytest.mark.parametrize('mask_dtype',[torch.long,torch.bool])
def test_batched_recurrence(mask_values,mask_dtype):
    rng=np.random.default_rng(190)
    mask=np.array(mask_values,dtype=np.float64)
    rewards=rng.normal(size=mask.shape)
    values=rng.normal(size=mask.shape)
    expected=reference(rewards,values,mask,.97,.91)
    actual=alg.compute_advantage_return(alg.AdvantageEstimator.GAE,
        token_level_rewards=torch.tensor(rewards),values=torch.tensor(values),
        response_mask=torch.tensor(mask_values,dtype=mask_dtype),gamma=.97,lam=.91)
    for got,want in zip(actual,expected):
        np.testing.assert_allclose(got.numpy(),want,rtol=1e-7,atol=1e-8)

@pytest.mark.parametrize('gamma,lam',[(0.,0.),(1.,1.),(.93,.4)])
def test_no_cross_trajectory_leakage_and_no_grad(gamma,lam):
    values=torch.tensor([[.2,.4,.1],[.9,-.3,.7]],dtype=torch.float64,requires_grad=True)
    rewards=torch.tensor([[0.,0.,2.],[0.,1.,0.]],dtype=torch.float64,requires_grad=True)
    mask=torch.tensor([[1.,1.,1.],[1.,1.,0.]],dtype=torch.float64)
    advantages,returns=alg.compute_gae_advantage_return(rewards,values,mask,gamma,lam)
    expected=reference(rewards.detach().numpy(),values.detach().numpy(),mask.numpy(),gamma,lam)
    np.testing.assert_allclose(returns.numpy(),expected[1],rtol=1e-12,atol=1e-12)
    np.testing.assert_allclose(advantages.numpy(),expected[0],rtol=1e-7,atol=1e-8)
    assert not returns.requires_grad and not advantages.requires_grad
