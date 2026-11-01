"""Coeficientes SI de AASHTO LRFD: V_c = 0,083·β·√f'c·b_v·d_v y tracción principal 0,29·√f'c (MPa).

Los coeficientes en unidades US (0,0316 y 0,110 con f'c en ksi) multiplicados por √6,894757 dan los SI.
"""
import math

import pytest

from bridgecalc.design.aashto_box_girder import BoxGirderSection, principal_stress_web, shear_strength
from bridgecalc.design.aashto_superstructure import concrete_box_girder_shear

KSI = 6.894757  # MPa


def test_coeficientes_si_son_la_conversion_de_los_us():
    assert 0.0316 * math.sqrt(KSI) == pytest.approx(0.083, rel=1e-3)
    assert 0.110 * math.sqrt(KSI) == pytest.approx(0.29, rel=5e-3)


def test_vc_igual_en_unidades_us_y_si():
    # f'c = 5 ksi, b_v = 20 in, d_v = 60 in, β = 2 → V_c = 0,0316·2·√5·20·60 = 169,6 kip
    vc_kip = 0.0316 * 2.0 * math.sqrt(5.0) * 20.0 * 60.0
    sec = BoxGirderSection(fc_MPa=5.0 * KSI, bv_mm=20 * 25.4, dv_mm=60 * 25.4, b_flange_mm=2000.0)
    r = shear_strength(sec, Vu_kN=1.0, Av_mm2=0.0, s_mm=0.0)
    assert r.Vc_kN == pytest.approx(vc_kip * 4.448222, rel=2e-3)


def test_superestructura_usa_el_mismo_vc():
    dcr = concrete_box_girder_shear(100.0, 35.0, 600.0, 1000.0, 0.0, 0.0, phi=1.0)
    assert 100.0 / dcr == pytest.approx(0.083 * 2.0 * math.sqrt(35.0) * 600.0 * 900.0 / 1e3, rel=1e-9)


def test_limite_de_traccion_principal_si():
    r = principal_stress_web(fpc_MPa=4.0, v_MPa=2.0, fc_MPa=45.0)
    assert r.limit_MPa == pytest.approx(-0.29 * math.sqrt(45.0))
    assert r.limit_MPa == pytest.approx(-0.110 * math.sqrt(45.0 / KSI) * KSI, rel=5e-3)
