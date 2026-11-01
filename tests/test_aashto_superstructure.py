"""Tests for high-level AASHTO LRFD box girder superstructure design checks."""
from __future__ import annotations

import pytest
from bridgecalc.design.aashto_superstructure import (
    concrete_box_girder_flexure,
    concrete_box_girder_shear,
)


class TestAASHTOSuperstructure:
    def test_box_girder_flexure_limits(self):
        # Flexión: momento de demanda Mu=500 kNm
        # As=2000 mm², fc=30 MPa, bw=600 mm, d=900 mm, fy=500 MPa, phi=0.9
        # a = 2000 * 500 / (0.85 * 30 * 600) = 65.36 mm
        # Mn = 2000 * 500 * (900 - 32.68) * 1e-6 = 867.32 kNm
        # Mr = 0.9 * 867.32 = 780.59 kNm
        # DCR = 500 / 780.59 = 0.6405
        dcr = concrete_box_girder_flexure(
            M_u_kNm=500.0,
            f_c_MPa=30.0,
            b_w_mm=600.0,
            d_mm=900.0,
            A_s_mm2=2000.0,
            f_y_MPa=500.0,
            phi=0.90,
        )
        assert dcr == pytest.approx(0.6405, abs=1e-3)

    def test_box_girder_flexure_invalid(self):
        # Área de acero nula o negativa debe dar infinito DCR
        assert concrete_box_girder_flexure(500, 30, 600, 900, 0) == float("inf")
        # Altura nula debe dar infinito DCR
        assert concrete_box_girder_flexure(500, 30, 600, 0, 2000) == float("inf")

    def test_box_girder_shear_limits(self):
        # Cortante: demanda Vu=300 kN
        # fc=30 MPa, bw=600 mm, d=900 mm, Av=400 mm² (e.g. estribos de 2 ramas d=16), s=200 mm
        # dv = 0.9 * 900 = 810 mm
        # Vc = 0.083 * 2.0 * sqrt(30) * 600 * 810 * 1e-3 = 441.88 kN  (coeficiente SI; 0.0316 es con ksi)
        # Vs = (400 * 500 * 810 * 1.3764 * 1e-3) / 200 = 1114.87 kN
        # Vn_max = 0.25 * 30 * 600 * 810 * 1e-3 = 3645 kN
        # Vn = min(Vc + Vs, Vn_max) = 441.88 + 1114.87 = 1556.75 kN
        # Vr = 0.9 * 1556.75 = 1401.08 kN
        # DCR = 300 / 1401.08 = 0.2141
        dcr = concrete_box_girder_shear(
            V_u_kN=300.0,
            f_c_MPa=30.0,
            b_w_mm=600.0,
            d_mm=900.0,
            A_v_mm2=400.0,
            s_mm=200.0,
            f_y_MPa=500.0,
            phi=0.90,
        )
        assert dcr == pytest.approx(0.2141, abs=1e-3)

    def test_box_girder_shear_no_stirrups(self):
        # Sin estribos (Av = 0), solo Vc aporta resistencia
        # Vc = 441.88 kN, Vr = 0.9 * 441.88 = 397.69 kN
        # DCR = 200 / 397.69 = 0.5029
        dcr = concrete_box_girder_shear(
            V_u_kN=200.0,
            f_c_MPa=30.0,
            b_w_mm=600.0,
            d_mm=900.0,
            A_v_mm2=0.0,
            s_mm=0.0,
            f_y_MPa=500.0,
            phi=0.90,
        )
        assert dcr == pytest.approx(0.5029, abs=1e-3)
