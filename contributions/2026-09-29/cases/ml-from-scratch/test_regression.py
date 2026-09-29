import importlib.util
import os
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location("target", Path(__file__).with_name(os.environ.get("VARIANT", "after") + ".py"))
target = importlib.util.module_from_spec(spec)
spec.loader.exec_module(target)

import numpy as np
@pytest.mark.parametrize("dtype", [np.int8, np.int32, np.int64])
def test_integer_standardization(dtype):
    x = np.array([[1, 10], [2, 20], [3, 30]], dtype=dtype)
    expected = (x.astype(float) - x.mean(axis=0)) / x.std(axis=0)
    np.testing.assert_allclose(target.standardize(x), expected)

@pytest.mark.parametrize("dtype", [np.float32, np.float64])
def test_float_standardization(dtype):
    x = np.array([[1, 10], [2, 20], [3, 30]], dtype=dtype)
    expected = (x.copy() - x.mean(axis=0)) / x.std(axis=0)
    np.testing.assert_allclose(target.standardize(x), expected, rtol=1e-6)

def test_constant_column_existing_behavior():
    x = np.array([[3., 1.], [3., 2.], [3., 3.]])
    np.testing.assert_array_equal(target.standardize(x)[:, 0], [3.,3.,3.])
