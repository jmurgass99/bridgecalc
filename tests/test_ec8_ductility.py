"""Tests for bridgecalc.ec8_ductility — EN 1998-2 ductile pier design."""
import pytest

from bridgecalc.ec8_ductility import (
    behavior_factor_q,
    confinement_required,
    plastic_hinge_length,
    target_displacement,
)


def test_behavior_factor_ductile_rc():
    q = behavior_factor_q("reinforced_concrete_ductile")
    assert q == 3.5


def test_behavior_factor_limited_ductility():
    q = behavior_factor_q("reinforced_concrete_limited_ductility")
    assert q == 1.5


def test_behavior_factor_short_pier_reduction():
    # alpha_s = 2 < 3 -> q reduced by sqrt(2/3)
    q = behavior_factor_q("reinforced_concrete_ductile", {"shear_span_ratio": 2.0})
    assert q == pytest.approx(3.5 * (2.0 / 3.0) ** 0.5, rel=1e-6)
    # alpha_s < 1 collapses to 1.0
    q2 = behavior_factor_q("reinforced_concrete_ductile", {"shear_span_ratio": 0.5})
    assert q2 == 1.0


def test_confinement_required_returns_at_least_min():
    # small axial load -> bounded by omega_w_min
    omega = confinement_required(N_Ed=1.0e6, Ac=1.0, fcd=20.0e6)
    assert omega >= 0.12


def test_plastic_hinge_length_priestley():
    # Lv=4 m, fy=500 MPa, db=0.025 m
    Lp = plastic_hinge_length(Lv=4.0, fy=500.0, db=0.025)
    # 0.10*4 + 0.015*500*0.025 = 0.4 + 0.1875 = 0.5875
    assert Lp == pytest.approx(0.5875, rel=1e-6)


def test_target_displacement_check():
    chk = target_displacement(T_eff=1.2, Sd_T_eff=0.08, capacity=0.10)
    assert chk.demand == 0.08
    assert chk.ok
    chk2 = target_displacement(T_eff=1.2, Sd_T_eff=0.15, capacity=0.10)
    assert not chk2.ok
