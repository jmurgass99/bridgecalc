"""Tests for Spanish highway bridge traffic live load model IAP-11 in BridgeCalc.

Verifies:
- Transverse division of notional lanes per IAP-11 Table 4.1 (including boundaries at 5.4 m and 6.0 m).
- Exact variable lane widths and explicit UDL integration.
- Exact tandem kinematics under Barré's theorem for bending moment and support shear.
- Short span limits where single axle at midspan governs.
- Segregation of EN 1991-2 Load Model 2 (MC2) for local deck slab verifications.
- Characteristic vs. design ELU load combinations (gamma_Q = 1.35, psi_0 = 0.75).
- Input boundary validations and units declarations.
"""
import math
import pytest

from bridgecalc.loads.iap11 import (
    IAP11TrafficEnvelope,
    NotionalLaneLayout,
    EN1991_2_LoadModel2,
    iap11_lane_layout,
    iap11_number_of_lanes,
    tandem_bending_moment_barre,
    tandem_shear_force_support,
    evaluate_iap11_traffic_loads,
    IAP11_STANDARD_LANE_WIDTH_m,
    IAP11_TS_AXLE_SPACING_m,
    IAP11_GAMMA_Q_ELU,
    IAP11_PSI_0,
    IAP11_PSI_1,
    IAP11_PSI_2,
)


def test_iap11_transverse_lane_layout():
    """Verify lane categorization according to IAP-11 Table 4.1."""
    # 1. w < 5.4 m: 1 notional lane of 3.0 m, remainder w - 3.0 m
    layout_4_5 = iap11_lane_layout(4.5)
    assert layout_4_5.n_lanes == 1
    assert layout_4_5.lane_widths_m == (3.0,)
    assert layout_4_5.remaining_width_m == pytest.approx(1.5)

    layout_5_39 = iap11_lane_layout(5.39)
    assert layout_5_39.n_lanes == 1
    assert layout_5_39.lane_widths_m == (3.0,)
    assert layout_5_39.remaining_width_m == pytest.approx(2.39)

    # 2. 5.4 m <= w < 6.0 m: 2 notional lanes of width w / 2, no remaining width
    layout_5_40 = iap11_lane_layout(5.40)
    assert layout_5_40.n_lanes == 2
    assert layout_5_40.lane_widths_m == pytest.approx((2.70, 2.70))
    assert layout_5_40.remaining_width_m == pytest.approx(0.0)

    layout_5_60 = iap11_lane_layout(5.60)
    assert layout_5_60.n_lanes == 2
    assert layout_5_60.lane_widths_m == pytest.approx((2.80, 2.80))
    assert layout_5_60.remaining_width_m == pytest.approx(0.0)

    layout_5_99 = iap11_lane_layout(5.99)
    assert layout_5_99.n_lanes == 2
    assert layout_5_99.lane_widths_m == pytest.approx((2.995, 2.995))
    assert layout_5_99.remaining_width_m == pytest.approx(0.0)

    # 3. w >= 6.0 m: floor(w / 3) lanes of 3.0 m each, remainder w - 3*n
    layout_6_00 = iap11_lane_layout(6.00)
    assert layout_6_00.n_lanes == 2
    assert layout_6_00.lane_widths_m == (3.0, 3.0)
    assert layout_6_00.remaining_width_m == pytest.approx(0.0)

    layout_7_00 = iap11_lane_layout(7.00)
    assert layout_7_00.n_lanes == 2
    assert layout_7_00.lane_widths_m == (3.0, 3.0)
    assert layout_7_00.remaining_width_m == pytest.approx(1.0)

    layout_10_5 = iap11_lane_layout(10.50)
    assert layout_10_5.n_lanes == 3
    assert layout_10_5.lane_widths_m == (3.0, 3.0, 3.0)
    assert layout_10_5.remaining_width_m == pytest.approx(1.5)

    # Compatibility function
    n, rem = iap11_number_of_lanes(5.60)
    assert n == 2
    assert rem == pytest.approx(0.0)


def test_iap11_variable_lane_width_udl_integration():
    """Verify that UDL explicitly integrates over variable lane widths in [5.4, 6.0)."""
    # At w = 5.60 m: 2 lanes of 2.80 m each, 0 remaining
    span_L = 10.0
    width_w = 5.60

    env = evaluate_iap11_traffic_loads(span_m=span_L, carriageway_width_m=width_w)

    # UDL linear intensity:
    # Lane 1: 9.0 kN/m2 * 2.80 m = 25.2 kN/m
    # Lane 2: 2.5 kN/m2 * 2.80 m = 7.0 kN/m
    # Remainder: 2.5 kN/m2 * 0.0 m = 0.0 kN/m
    # Total q = 32.2 kN/m
    expected_q = 9.0 * 2.80 + 2.5 * 2.80
    expected_m_udl = expected_q * (span_L ** 2) / 8.0  # 32.2 * 100 / 8 = 402.5 kNm
    expected_v_udl = expected_q * span_L / 2.0         # 32.2 * 10 / 2 = 161.0 kN

    assert env.M_UDL_kNm == pytest.approx(expected_m_udl, rel=1e-3)
    assert env.V_UDL_kN == pytest.approx(expected_v_udl, rel=1e-3)


def test_tandem_barre_bending_moment():
    """Verify Barré's theorem analytical solution against independent mechanics."""
    p_axle = 300.0  # kN (Carril 1)
    span_L = 20.0   # m
    d = 1.20        # m

    m_barre = tandem_bending_moment_barre(p_axle, span_L, axle_spacing_m=d)

    # Barré analytical formula: M = (P / (2*L)) * (L - d/2)^2
    # For L = 20, d = 1.20:
    # M = (300 / 40) * (20 - 0.6)^2 = 7.5 * (19.4)^2 = 7.5 * 376.36 = 2822.7 kNm
    expected_barre = (300.0 / (2.0 * 20.0)) * ((20.0 - 0.60) ** 2)
    assert m_barre == pytest.approx(expected_barre, rel=1e-4)
    assert m_barre == pytest.approx(2822.7, rel=1e-3)

    # Contrast with symmetric midspan placement:
    # R_A = 300 kN, M_mid = 300 * (10 - 0.6) = 2820.0 kNm
    m_symmetric = 300.0 * (span_L / 2.0 - d / 2.0)
    assert m_barre > m_symmetric  # Barré peak is strictly larger than symmetric placement


def test_tandem_short_spans_governing_case():
    """Verify that single axle midspan governs on short spans (L < 2.049 m)."""
    p_axle = 300.0
    d = 1.20

    # L = 1.50 m: 2 axles in Barré position cannot even fit (second axle at x = 1.65 m > 1.50 m)
    # Single axle at midspan gives: P * L / 4 = 300 * 1.50 / 4 = 112.5 kNm
    m_1_5 = tandem_bending_moment_barre(p_axle, 1.50, axle_spacing_m=d)
    assert m_1_5 == pytest.approx(300.0 * 1.50 / 4.0, rel=1e-4)

    # L = 2.00 m: both axles fit, but single axle at midspan (P*L/4 = 150 kNm)
    # still exceeds Barré 2-axle peak ((P / 4) * (2.0 - 0.6)^2 = 300 / 4 * 1.96 = 147 kNm)
    m_2_0 = tandem_bending_moment_barre(p_axle, 2.00, axle_spacing_m=d)
    assert m_2_0 == pytest.approx(300.0 * 2.00 / 4.0, rel=1e-4)

    # L = 4.00 m: Barré 2-axle peak governs
    m_4_0 = tandem_bending_moment_barre(p_axle, 4.00, axle_spacing_m=d)
    expected_4_0 = (300.0 / (2.0 * 4.0)) * ((4.00 - 0.60) ** 2)
    assert m_4_0 == pytest.approx(expected_4_0, rel=1e-4)


def test_tandem_support_shear():
    """Verify tandem shear at support with one axle directly over support."""
    p_axle = 300.0
    d = 1.20

    # Normal span L = 20.0 m: V = P * (2 - 1.2 / 20) = 300 * 1.94 = 582 kN
    v_20 = tandem_shear_force_support(p_axle, 20.0, axle_spacing_m=d)
    assert v_20 == pytest.approx(300.0 * (2.0 - 1.20 / 20.0), rel=1e-4)
    assert v_20 == pytest.approx(582.0, rel=1e-3)

    # Very short span L = 1.0 m < 1.2 m: second axle is outside span
    v_1_0 = tandem_shear_force_support(p_axle, 1.0, axle_spacing_m=d)
    assert v_1_0 == pytest.approx(300.0, rel=1e-4)


def test_iap11_mc1_load_evaluation_20m():
    """Verify Load Model 1 (MC1 = TS + UDL) analytical moments and shears on 20m span."""
    span_L = 20.0
    width_w = 10.0  # 3 lanes of 3.0 m + 1.0 m remaining

    env = evaluate_iap11_traffic_loads(span_m=span_L, carriageway_width_m=width_w)

    assert env.span_m == 20.0
    assert env.carriageway_width_m == 10.0
    assert env.n_notional_lanes == 3
    assert env.lane_widths_m == (3.0, 3.0, 3.0)
    assert env.remaining_width_m == pytest.approx(1.0)

    # Analytical MC1 TS (Barré):
    # Total P_axles = 300 + 200 + 100 = 600 kN
    # M_TS = (600 / 40) * (19.4)^2 = 15.0 * 376.36 = 5645.4 kNm
    assert env.M_TS_kNm == pytest.approx(5645.4, rel=1e-3)

    # V_TS = 600 * (2.0 - 1.2/20) = 600 * 1.94 = 1164.0 kN
    assert env.V_TS_kN == pytest.approx(1164.0, rel=1e-3)

    # Analytical MC1 UDL:
    # q = (9.0*3 + 2.5*3 + 2.5*3) + 2.5*1.0 = 27 + 7.5 + 7.5 + 2.5 = 44.5 kN/m
    # M_UDL = 44.5 * 400 / 8 = 2225.0 kNm
    # V_UDL = 44.5 * 20 / 2 = 445.0 kN
    assert env.M_UDL_kNm == pytest.approx(2225.0, rel=1e-3)
    assert env.V_UDL_kN == pytest.approx(445.0, rel=1e-3)

    # Total MC1 characteristic:
    assert env.M_MC1_total_characteristic_kNm == pytest.approx(5645.4 + 2225.0, rel=1e-3)
    assert env.V_MC1_total_characteristic_kN == pytest.approx(1164.0 + 445.0, rel=1e-3)

    # ELU design values (gamma_Q = 1.35):
    assert env.M_MC1_design_ELU_kNm == pytest.approx((5645.4 + 2225.0) * 1.35, rel=1e-3)
    assert env.V_MC1_design_ELU_kN == pytest.approx((1164.0 + 445.0) * 1.35, rel=1e-3)

    # Units declaration contract
    assert "force" in env.units
    assert env.units["force"] == "kN"
    assert env.units["moment"] == "kNm"


def test_iap11_mc2_and_en1991_2_lm2_segregation():
    """Verify Load Model 2 (MC2 / LM2: 400 kN single axle) as a separate local check."""
    lm2 = EN1991_2_LoadModel2()
    assert lm2.axle_load_kN == 400.0
    assert lm2.wheel_contact_length_m == 0.35
    assert lm2.wheel_contact_width_m == 0.60
    assert lm2.wheel_transverse_spacing_m == 2.00

    # Local slab bending moment for 3.0 m stringer/beam spacing:
    # M_local = 400 * 3.0 / 4 = 300 kNm
    m_local = lm2.local_bending_moment_kNm(3.0)
    assert m_local == pytest.approx(300.0, rel=1e-4)

    v_local = lm2.local_shear_force_kN()
    assert v_local == pytest.approx(400.0, rel=1e-4)

    # Global envelope correctly distinguishes global beam governing action from local check
    env = evaluate_iap11_traffic_loads(span_m=20.0, carriageway_width_m=8.0)
    assert env.M_MC2_characteristic_kNm == pytest.approx(400.0 * 20.0 / 4.0, rel=1e-3)
    assert env.V_MC2_characteristic_kN == pytest.approx(400.0, rel=1e-3)
    # Global governing moment for bridge sizing is the complete MC1 model
    assert env.M_governing_characteristic_kNm == env.M_MC1_total_characteristic_kNm


def test_iap11_validation_errors():
    """Verify error raises on unphysical geometric inputs."""
    with pytest.raises(ValueError, match="estrictamente positivos"):
        evaluate_iap11_traffic_loads(span_m=0.0, carriageway_width_m=7.0)

    with pytest.raises(ValueError, match="estrictamente positivos"):
        evaluate_iap11_traffic_loads(span_m=20.0, carriageway_width_m=-2.0)

    with pytest.raises(ValueError, match="estrictamente positivo"):
        iap11_lane_layout(0.0)

    lm2 = EN1991_2_LoadModel2()
    with pytest.raises(ValueError, match="estrictamente positiva"):
        lm2.local_bending_moment_kNm(0.0)
