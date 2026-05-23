"""Tests for bridgejm.ec1_traffic — EN 1991-2 traffic load models."""
import math
import pytest

from bridgejm.ec1_traffic import (
    LM1,
    LM2,
    LM3,
    LM4,
    traffic_envelope_lm1,
)


def test_lm1_lane_table_default():
    lm = LM1(n_lanes=3)
    lanes = lm.lane_loads()
    assert lanes[0]["Qik_kN"] == 300.0
    assert lanes[0]["qik_kPa"] == 9.0
    assert lanes[1]["Qik_kN"] == 200.0
    assert lanes[2]["Qik_kN"] == 100.0


def test_traffic_envelope_lm1_span20_2lanes():
    M, V = traffic_envelope_lm1(L_span=20.0, n_lanes=2)
    # Sanity: UDL alone: lane1 w=9*3=27 kN/m, lane2 w=2.5*3=7.5 kN/m, sum=34.5
    # M_udl = 34.5*20^2/8 = 1725 kN·m; V_udl = 34.5*20/2 = 345 kN
    assert M > 1725.0
    assert V > 345.0
    # TS adds appreciable moment: 2*(300+200) axles distributed
    assert M < 1725.0 + 2 * (300 + 200) * 20.0 / 4.0


def test_lm2_single_axle():
    lm2 = LM2()
    assert lm2.Qak_kN == 400.0
    lm2b = LM2(beta_Q=0.9)
    assert lm2b.Qak_kN == pytest.approx(360.0)


def test_lm1_alpha_national_annex():
    # Spanish / typical NA: alpha_Q1 = 0.9, alpha_q1 = 0.77
    lm = LM1(n_lanes=2, alpha_Q=0.9, alpha_q=0.77)
    lanes = lm.lane_loads()
    assert lanes[0]["Qik_kN"] == pytest.approx(0.9 * 300.0)
    assert lanes[0]["qik_kPa"] == pytest.approx(0.77 * 9.0)
    # Envelope monotonic in alpha
    M_full, _ = traffic_envelope_lm1(20.0, 2, alpha_Q=1.0, alpha_q=1.0)
    M_red, _ = traffic_envelope_lm1(20.0, 2, alpha_Q=0.9, alpha_q=0.77)
    assert M_red < M_full


def test_lm3_lm4_basic():
    lm3 = LM3(name="SV100", axles_kN=[100.0] * 6, spacing_m=[1.5] * 5)
    assert lm3.total_load_kN == 600.0
    lm4 = LM4()
    assert lm4.q_kPa == 5.0
    assert lm4.line_load_kN_per_m(width_m=3.0) == 15.0
