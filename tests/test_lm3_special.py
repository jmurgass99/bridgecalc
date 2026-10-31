"""Tests for LM3 special vehicles + impact factors."""
import math
import pytest

from bridgecalc.loads.lm3_special import (
    SpecialVehicle, EUROCODE_SV120, EUROCODE_SV196,
    IRC_CLASS_A, AS_SM1600, AASHTO_HS20,
    max_moment_simple_span, impact_factor,
)


def test_catalog_sanity():
    assert EUROCODE_SV120.total_load_kN == pytest.approx(6 * 240.0)
    assert EUROCODE_SV120.length_m == pytest.approx(5 * 1.2)
    assert IRC_CLASS_A.code == "INDIA"
    assert AS_SM1600.total_load_kN == pytest.approx(48.0 + 96.0 * 2)
    assert AASHTO_HS20.length_m == pytest.approx(2 * 4.27)


def test_max_moment_single_axle_matches_PL_4():
    # Single 100 kN axle on 20 m span: M_max = PL/4
    v = SpecialVehicle(name="single", axle_loads_kN=(100.0,),
                       axle_spacings_m=(), code="TEST")
    res = max_moment_simple_span(v, span_m=20.0, n_positions=400)
    expected = 100.0 * 20.0 / 4.0
    assert res["M_max_kNm"] == pytest.approx(expected, rel=1e-2)


def test_max_moment_irc_class_a_on_25m():
    res = max_moment_simple_span(IRC_CLASS_A, span_m=25.0, n_positions=400)
    assert res["M_max_kNm"] > 0
    assert res["vehicle"] == "IRC Class A"
    assert res["code"] == "INDIA"


def test_impact_factor_multi_code():
    assert impact_factor("AASHTO", 20.0) == pytest.approx(1.33)
    assert impact_factor("EUROCODE", 30.0) == pytest.approx(1.0)
    assert 1.0 < impact_factor("IRC", 10.0) <= 1.25 + 1.0
    assert impact_factor("AS", 50.0) == pytest.approx(1.30)
    # Unknown code defaults to 1.0
    assert impact_factor("XYZ", 10.0) == 1.0


def test_impact_factor_irc_decreases_with_span():
    short = impact_factor("INDIA", 5.0)
    long = impact_factor("INDIA", 50.0)
    assert short > long
    assert long >= 1.0
