"""Regression proposal; upstream full-package/CI tests have not been run."""
import warnings

import numpy as np
import pytest


@pytest.mark.parametrize("shape", [(), (3,), (2, 2)])
@pytest.mark.parametrize("epsilon", [0.0, 1e-4])
def test_empty_batch_preserves_statistics(load_source, shape, epsilon):
    cls = load_source("sb3_running_mean_std.py").RunningMeanStd
    stats = cls(epsilon=epsilon, shape=shape)
    data = np.arange(4 * max(1, int(np.prod(shape))), dtype=np.float64).reshape((4, *shape))
    stats.update(data)
    before = stats.copy()
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        stats.update(np.empty((0, *shape)))
    np.testing.assert_array_equal(stats.mean, before.mean)
    np.testing.assert_array_equal(stats.var, before.var)
    assert stats.count == before.count


@pytest.mark.parametrize("epsilon", [0.0, 1e-4])
def test_zero_count_moments_are_ignored(load_source, epsilon):
    cls = load_source("sb3_running_mean_std.py").RunningMeanStd
    stats = cls(epsilon=epsilon, shape=(2,))
    before = stats.copy()
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        stats.update_from_moments(np.full(2, np.nan), np.full(2, np.nan), 0)
    np.testing.assert_array_equal(stats.mean, before.mean)
    np.testing.assert_array_equal(stats.var, before.var)
    assert stats.count == before.count


def test_empty_batch_before_first_observation(load_source):
    cls = load_source("sb3_running_mean_std.py").RunningMeanStd
    stats = cls(epsilon=0.0, shape=(2,))
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        stats.update(np.empty((0, 2)))
    stats.update(np.array([[1.0, 2.0], [3.0, 4.0]]))
    np.testing.assert_array_equal(stats.mean, [2.0, 3.0])
    np.testing.assert_array_equal(stats.var, [1.0, 1.0])
    assert stats.count == 2


def test_combine_zero_count_statistics(load_source):
    cls = load_source("sb3_running_mean_std.py").RunningMeanStd
    stats = cls(epsilon=0.0, shape=(2,))
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        stats.combine(cls(epsilon=0.0, shape=(2,)))
    np.testing.assert_array_equal(stats.mean, [0.0, 0.0])
    np.testing.assert_array_equal(stats.var, [1.0, 1.0])
    assert stats.count == 0


def test_nonempty_updates_match_numpy(load_source):
    cls = load_source("sb3_running_mean_std.py").RunningMeanStd
    data = np.array([[1.0, 9.0], [-2.0, 3.0], [8.0, -1.0]])
    stats = cls(epsilon=0.0, shape=(2,))
    stats.update(data[:1])
    stats.update(data[1:])
    np.testing.assert_allclose(stats.mean, data.mean(axis=0))
    np.testing.assert_allclose(stats.var, data.var(axis=0))
    assert stats.count == len(data)
