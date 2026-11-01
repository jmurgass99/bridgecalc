"""Tests for bridgecalc.loads.dynamic_impact."""
import pytest
from bridgecalc.loads.dynamic_impact import (
    dynamic_load_allowance,
    wind_pressure_bridge,
    combined_dynamic_truck_wind,
    WindOnBridgeInput,
)


def test_aashto_im_default():
    assert dynamic_load_allowance("other", "AASHTO") == pytest.approx(0.33)
    assert dynamic_load_allowance("deck_joints", "AASHTO") == pytest.approx(0.75)
    assert dynamic_load_allowance("fatigue", "AASHTO") == pytest.approx(0.15)


def test_im_multi_code():
    assert dynamic_load_allowance(code="NSR") == pytest.approx(0.33)
    assert dynamic_load_allowance(code="AS") == pytest.approx(0.30)
    # EN 1991-2: LM1/LM2 ya incluyen la amplificación dinámica -> IM = 0 en carretera
    assert dynamic_load_allowance(code="EU", span_m=20.0) == 0.0
    assert dynamic_load_allowance(code="SG") == 0.0
    # El factor ferroviario φ2 (EN 1991-2 §6.4.5.2) sigue disponible: L=20 m -> 1.44/(4.472-0.2)+0.82 = 1.157
    assert dynamic_load_allowance(code="EU_RAIL", span_m=20.0) == pytest.approx(0.157, abs=1e-3)
    assert dynamic_load_allowance(code="EU_RAIL", span_m=3.0) == pytest.approx(0.67, abs=1e-9)   # 1.44/(1.732-0.2)+0.82 = 1.76 -> tope 1.67
    with pytest.raises(ValueError):
        dynamic_load_allowance(code="EU_RAIL")
    with pytest.raises(ValueError):
        dynamic_load_allowance(code="ZZ")


def test_wind_pressure_basic():
    inp = WindOnBridgeInput(V_ms=40.0, H_m=2.0, L_m=30.0, Cd=1.5, code="AASHTO")
    res = wind_pressure_bridge(inp)
    # q = 0.5 * 1.225 * 1600 * 1.5 = 1470 Pa = 1.47 kPa
    assert res.pressure_kPa == pytest.approx(1.47, rel=1e-3)
    assert res.line_load_kN_per_m == pytest.approx(2.94, rel=1e-3)
    assert res.total_force_kN == pytest.approx(88.2, rel=1e-3)


def test_wind_eurocode_and_combined():
    w = WindOnBridgeInput(V_ms=30.0, H_m=1.5, L_m=25.0, code="EU")
    truck_dyn, wline, total = combined_dynamic_truck_wind(
        static_truck_kN=500.0, span_m=25.0, wind=w
    )
    # Con EN 1991-2 el camión no se mayora por IM (LM1 ya lo incluye)
    assert truck_dyn == pytest.approx(500.0)
    assert wline > 0.0
    assert total > truck_dyn
