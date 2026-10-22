"""Tests for Spanish highway bridge traffic live load model IAP-11 in BridgeJm.
"""

import pytest
from bridgejm.loads.iap11 import (
    IAP11TrafficEnvelope,
    iap11_number_of_lanes,
    evaluate_iap11_traffic_loads,
    IAP11_GAMMA_Q_ELU,
    IAP11_PSI_0,
)


def test_iap11_number_of_lanes():
    """Verify lane categorization according to IAP-11 Table 4.1."""
    # Single lane road
    n, rem = iap11_number_of_lanes(4.5)
    assert n == 1
    assert rem == pytest.approx(1.5)

    # Transition width [5.4, 6.0) -> 2 lanes
    n, rem = iap11_number_of_lanes(5.6)
    assert n == 2
    assert rem == pytest.approx(0.0)

    # Standard 2-lane bridge (7.0 m width)
    n, rem = iap11_number_of_lanes(7.0)
    assert n == 2
    assert rem == pytest.approx(1.0)

    # Standard 3-lane motorway (10.5 m width)
    n, rem = iap11_number_of_lanes(10.5)
    assert n == 3
    assert rem == pytest.approx(1.5)


def test_iap11_mc1_load_evaluation():
    """Verify Load Model 1 (MC1 = TS + UDL) analytical moments and shears."""
    span_L = 20.0
    width_w = 10.0  # 3 lanes (9.0m) + 1.0m remaining area

    env = evaluate_iap11_traffic_loads(span_m=span_L, carriageway_width_m=width_w)

    assert env.span_m == 20.0
    assert env.carriageway_width_m == 10.0
    assert env.n_notional_lanes == 3

    # Analytical check of MC1 TS:
    # Lane 1: P_axle = 300 kN, Lane 2: P_axle = 200 kN, Lane 3: P_axle = 100 kN
    # Total P_axles = 600 kN
    # For L = 20m, M_TS = (300 + 200 + 100) * (20/2 - 0.3) = 600 * 9.7 = 5820 kNm
    assert env.M_TS_kNm == pytest.approx(5820.0, rel=1e-3)

    # Analytical check of MC1 UDL:
    # Lane 1 (3m): 9.0 kN/m2 * 3m = 27.0 kN/m
    # Lane 2 (3m): 2.5 kN/m2 * 3m = 7.5 kN/m
    # Lane 3 (3m): 2.5 kN/m2 * 3m = 7.5 kN/m
    # Remaining (1m): 2.5 kN/m2 * 1m = 2.5 kN/m
    # Total q = 27.0 + 7.5 + 7.5 + 2.5 = 44.5 kN/m
    # M_UDL = q * L^2 / 8 = 44.5 * 400 / 8 = 2225.0 kNm
    assert env.M_UDL_kNm == pytest.approx(2225.0, rel=1e-3)

    # Total MC1 characteristic
    expected_m_mc1 = 5820.0 + 2225.0
    assert env.M_MC1_total_characteristic_kNm == pytest.approx(expected_m_mc1, rel=1e-3)

    # ELU design moment with gamma_Q = 1.35
    expected_m_elu = expected_m_mc1 * 1.35
    assert env.M_MC1_design_ELU_kNm == pytest.approx(expected_m_elu, rel=1e-3)


def test_iap11_mc2_single_axle_evaluation():
    """Verify Load Model 2 (MC2: single concentrated 400 kN axle)."""
    span_L = 16.0
    width_w = 8.0

    env = evaluate_iap11_traffic_loads(span_m=span_L, carriageway_width_m=width_w)

    # For concentrated load P = 400 kN at midspan:
    # M = P * L / 4 = 400 * 16 / 4 = 1600 kNm
    # Support shear V = 400 kN
    assert env.M_MC2_characteristic_kNm == pytest.approx(1600.0, rel=1e-3)
    assert env.V_MC2_characteristic_kN == pytest.approx(400.0, rel=1e-3)


def test_iap11_governing_case_by_span():
    """Verify that MC1 governs over MC2 for medium/long spans."""
    # 30m span bridge
    env_30 = evaluate_iap11_traffic_loads(span_m=30.0, carriageway_width_m=8.0)
    assert env_30.M_governing_characteristic_kNm == env_30.M_MC1_total_characteristic_kNm
    assert env_30.M_governing_characteristic_kNm > env_30.M_MC2_characteristic_kNm

    # Check to_dict contains standard and required keys
    d = env_30.to_dict()
    assert d["standard"] == "IAP-11 (España)"
    assert d["M_governing_characteristic_kNm"] > 0.0


def test_iap11_validation_errors():
    """Verify error raises on unphysical geometric inputs."""
    with pytest.raises(ValueError, match="estrictamente positivos"):
        evaluate_iap11_traffic_loads(span_m=0.0, carriageway_width_m=7.0)

    with pytest.raises(ValueError, match="estrictamente positivos"):
        evaluate_iap11_traffic_loads(span_m=20.0, carriageway_width_m=-2.0)
