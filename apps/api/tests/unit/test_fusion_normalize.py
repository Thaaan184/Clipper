"""Unit tests for robust normalization functions."""

import numpy as np

from clipforge.fusion.normalize import robust_z, to_unit


def test_robust_z_invariance():
    # If array has constant offset, robust_z should center it at 0
    x = np.array([10.0, 10.0, 10.0, 15.0, 10.0, 10.0, 10.0, 20.0])
    z = robust_z(x)
    assert np.isclose(np.nanmedian(z), 0.0)
    assert z[7] > z[3] > 0.0


def test_to_unit_clamping():
    z = np.array([-2.0, 0.0, 0.5, 2.25, 4.0, 6.0])
    unit = to_unit(z, z_lo=0.5, z_hi=4.0)

    assert unit[0] == 0.0
    assert unit[1] == 0.0
    assert unit[2] == 0.0  # z_lo maps to 0.0
    assert 0.0 < unit[3] < 1.0
    assert unit[4] == 1.0  # z_hi maps to 1.0
    assert unit[5] == 1.0  # clamped to 1.0
