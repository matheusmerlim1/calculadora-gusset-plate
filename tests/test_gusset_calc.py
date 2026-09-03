import pytest

from gusset_calc import GussetInput, compute_geometry


def _example_1():
    """Example 1 from Chambers & Bartley (2007), Table 2."""
    gi = GussetInput(
        H=20.0, W=21.5, a=19.7, b=14.5, L=13, Le=2, s=3,
        theta_b_deg=15.0, theta_c_deg=30.0, theta_bb_deg=-10.0, theta_cc_deg=-8.0,
    )
    return compute_geometry(gi)


def test_example_1_matches_published_values():
    res = _example_1()
    assert res.yb == pytest.approx(11.406, abs=0.001)
    assert res.yc == pytest.approx(10.291, abs=0.001)
    assert res.L1 == pytest.approx(9.462, abs=0.001)
    assert res.L2 == pytest.approx(5.046, abs=0.001)
    assert res.L3 == pytest.approx(0.630, abs=0.001)


def test_theta_B_is_geometry_derived_not_user_input():
    res = _example_1()
    assert res.theta_B_deg == pytest.approx(18.122, abs=0.001)


def test_H_equal_b_raises():
    gi = GussetInput(H=10.0, W=20.0, a=5.0, b=10.0, L=13, Le=2, s=3)
    with pytest.raises(ValueError):
        compute_geometry(gi)
