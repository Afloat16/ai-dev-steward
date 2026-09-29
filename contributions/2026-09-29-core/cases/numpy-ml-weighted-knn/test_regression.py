"""Full KNN/BallTree/PriorityQueue modules; compare voting with brute force.
A collections.Hashable alias permits the unmodified older module to import on
Python >= 3.10. No neighbor search or voting logic is mocked.
"""
import collections
import collections.abc
import importlib.util
import os
from pathlib import Path
import sys
import types
import numpy as np
import pytest
ROOT = Path(__file__).parent / os.getenv('VARIANT','after')
if not hasattr(collections, 'Hashable'):
    collections.Hashable = collections.abc.Hashable
for name in ['numpy_ml','numpy_ml.utils','numpy_ml.nonparametric']:
    m=types.ModuleType(name); m.__path__=[];sys.modules[name]=m

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
load('numpy_ml.utils.distance_metrics','numpy_ml/utils/distance_metrics.py')
load('numpy_ml.utils.data_structures','numpy_ml/utils/data_structures.py')
KNN=load('numpy_ml.nonparametric.knn','numpy_ml/nonparametric/knn.py').KNN

@pytest.mark.parametrize('labels',[[0,1,1],[1,0,0],[2,1,0],[1,2,0]])
def test_closest_class_wins_even_when_it_is_not_the_last_set_entry(labels):
    x=np.array([[0.1],[1.0],[1.1]])
    model=KNN(k=3,leaf_size=2,weights='distance');model.fit(x,np.array(labels))
    assert model.predict(np.array([[0.0]])).item()==labels[0]

@pytest.mark.parametrize('seed',list(range(8)))
def test_predictions_match_brute_force_distance_weighted_vote(seed):
    rng=np.random.default_rng(seed)
    x=rng.normal(size=(31,3));y=rng.integers(0,4,size=31);queries=rng.normal(size=(9,3))
    model=KNN(k=7,leaf_size=3,weights='distance');model.fit(x,y)
    expected=[]
    for q in queries:
        distances=np.linalg.norm(x-q,axis=1);idx=np.argsort(distances)[:7]
        scores={label:sum(1/distances[i] for i in idx if y[i]==label) for label in set(y[idx])}
        expected.append(max(scores,key=scores.get))
    np.testing.assert_array_equal(model.predict(queries),expected)

def test_uniform_classifier_is_unchanged():
    model=KNN(k=3,weights='uniform');model.fit(np.array([[.1],[1.],[1.1]]),np.array([0,1,1]))
    assert model.predict(np.array([[0.]])).item()==1

def test_distance_weighted_regression_is_unchanged():
    x=np.array([[.1],[1.],[1.1]]);y=np.array([3.,8.,12.])
    model=KNN(k=3,classifier=False,weights='distance');model.fit(x,y)
    np.testing.assert_allclose(model.predict(np.array([[0.]])),[np.average(y,weights=1/x[:,0])])
