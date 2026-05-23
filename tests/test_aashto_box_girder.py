# -*- coding: utf-8 -*-
"""Diseño AASHTO de cajón de hormigón (flexión, cortante, tensión principal)."""
import math

import pytest

from bridgejm.design.aashto_box_girder import (
    BoxGirderSection,
    flexural_strength,
    shear_strength,
    principal_stress_web,
)


def _sec():
    # Cajón pretensado representativo (canto 2.5 m, almas 2x400 mm).
    return BoxGirderSection(
        fc_MPa=45.0, bv_mm=800.0, dv_mm=2150.0, b_flange_mm=6000.0,
        Aps_mm2=8400.0, fpu_MPa=1860.0, dp_mm=2300.0,
        As_mm2=4000.0, fy_MPa=500.0, ds_mm=2350.0,
    )


class TestFlexure:
    def test_Mr_positivo_y_fps(self):
        r = flexural_strength(_sec(), Mu_kNm=20000.0)
        assert r.Mn_kNm > 0 and r.Mr_kNm > 0
        # fps debe estar por debajo de fpu y ser razonable (>0.9 fpu para baja c/dp).
        assert 0.85 * 1860.0 < r.fps_MPa < 1860.0
        assert r.a_mm > 0

    def test_cumple_si_demanda_baja(self):
        r = flexural_strength(_sec(), Mu_kNm=10000.0)
        assert r.ok and r.Mr_kNm >= 10000.0

    def test_falla_si_demanda_excesiva(self):
        r = flexural_strength(_sec(), Mu_kNm=10_000_000.0)
        assert not r.ok

    def test_mas_pretensado_mas_capacidad(self):
        base = _sec()
        more = BoxGirderSection(**{**base.__dict__, "Aps_mm2": base.Aps_mm2 * 1.5})
        assert flexural_strength(more, 0).Mn_kNm > flexural_strength(base, 0).Mn_kNm


class TestShear:
    def test_Vn_acotado_por_compresion(self):
        r = shear_strength(_sec(), Vu_kN=3000.0, Av_mm2=1600.0, s_mm=150.0)
        # Vn no puede superar 0.25 f'c bv dv
        assert r.Vn_kN <= r.Vmax_kN + 1e-6
        assert r.Vc_kN > 0 and r.Vs_kN > 0

    def test_formula_Vc(self):
        s = _sec()
        r = shear_strength(s, Vu_kN=1.0, Av_mm2=1600.0, s_mm=150.0, beta=2.0)
        Vc = 0.0316 * 2.0 * math.sqrt(s.fc_MPa) * s.bv_mm * s.dv_mm / 1e3
        assert r.Vc_kN == pytest.approx(Vc, rel=1e-6)

    def test_mas_estribos_mas_Vs(self):
        a = shear_strength(_sec(), 1.0, 1600.0, 200.0).Vs_kN
        b = shear_strength(_sec(), 1.0, 1600.0, 100.0).Vs_kN
        assert b > a   # menor espaciamiento -> más Vs


class TestPrincipalStress:
    def test_traccion_principal(self):
        # fpc=6 MPa compresión, v=2 MPa cortante.
        r = principal_stress_web(fpc_MPa=6.0, v_MPa=2.0, fc_MPa=45.0)
        esperado = 3.0 - math.sqrt(3.0 ** 2 + 2.0 ** 2)
        assert r.sigma_principal_MPa == pytest.approx(esperado, rel=1e-9)

    def test_cumple_con_buena_compresion(self):
        r = principal_stress_web(fpc_MPa=8.0, v_MPa=1.5, fc_MPa=45.0)
        assert r.ok    # poca tracción principal, dentro del límite

    def test_falla_con_cortante_alto(self):
        r = principal_stress_web(fpc_MPa=2.0, v_MPa=6.0, fc_MPa=45.0)
        assert not r.ok    # tracción principal excede el límite
