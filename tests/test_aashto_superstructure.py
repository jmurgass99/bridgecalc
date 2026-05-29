"""Tests for high-level AASHTO LRFD box girder superstructure design checks."""
from __future__ import annotations

import pytest
from bridgejm.design.aashto_superstructure import (
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
        # Vc = 0.0316 * 2.0 * sqrt(30) * 600 * 810 * 1e-3 = 168.22 kN
        # Vs = (400 * 500 * 810 * 1.3764 * 1e-3) / 200 = 1114.88 kN
        # Vn_max = 0.25 * 30 * 600 * 810 * 1e-3 = 3645 kN
        # Vn = min(Vc + Vs, Vn_max) = 168.22 + 1114.88 = 1283.1 kN
        # Vr = 0.9 * 1283.1 = 1154.79 kN
        # DCR = 300 / 1154.79 = 0.2598
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
        assert dcr == pytest.approx(0.2598, abs=1e-3)

    def test_box_girder_shear_no_stirrups(self):
        # Sin estribos (Av = 0), solo Vc aporta resistencia
        # Vc = 168.22 kN, Vr = 0.9 * 168.22 = 151.40 kN
        # DCR = 200 / 151.40 = 1.321
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
        assert dcr == pytest.approx(1.321, abs=1e-3)
