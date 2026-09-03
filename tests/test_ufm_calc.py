import pytest

from ufm_calc import (
    UFMInput,
    compute_ufm,
    gusset_plate_buckling,
    hss_sidewall_plastification,
)


def test_steel_tube_institute_example():
    """Packer & Richardson (2025) Steel Tube Institute example: Pr=130 kips, theta=45deg."""
    gi = UFMInput(Pr=130.0, theta_deg=45.0, eb=9.75, ec=5.0, alpha=13.25, beta=8.5)
    r = compute_ufm(gi)
    assert r.r == pytest.approx(25.75, abs=0.1)
    assert r.Vrc == pytest.approx(42.9, abs=0.2)
    assert r.Hrc == pytest.approx(25.1, abs=0.2)
    assert r.Vrb == pytest.approx(49.0, abs=0.2)
    assert r.Hrb == pytest.approx(66.8, abs=0.2)


def test_gusset_plate_buckling_matches_published_value():
    buck = gusset_plate_buckling(Lw=12.24, tp=0.75, Lc=13.10, K=1.2, Fy=50.0)
    assert buck["phiPn"] == pytest.approx(280.9, abs=0.5)


def test_hss_sidewall_plastification_larger_contact_length():
    hss = hss_sidewall_plastification(Fy=50.0, t_col=0.465, La=16.0, B_col=10.0,
                                       branch_width=6.75, Pu_col=-501.9, Ag_col=17.2)
    assert hss["phiRn"] == pytest.approx(173.9, abs=0.1)


def test_hss_sidewall_plastification_shorter_contact_length_known_discrepancy():
    """Regression test only: LEIA-ME.txt documents that this specific case
    (shortest HSS contact length) does not fully match the published Steel
    Tube Institute example (published ~98.2, this module currently gives
    ~135.9) and recommends checking it manually against AISC Design Guide 24
    before design use. This test locks the current behavior so a future
    change to the formula is a visible, deliberate decision, not a silent
    regression."""
    hss = hss_sidewall_plastification(Fy=50.0, t_col=0.465, La=10.0, B_col=10.0,
                                       branch_width=6.75, Pu_col=-501.9, Ag_col=17.2)
    assert hss["phiRn"] == pytest.approx(135.9, abs=0.5)
