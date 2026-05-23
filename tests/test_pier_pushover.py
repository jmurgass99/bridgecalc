"""Tests BJ-004: pushover de cepa simple — SDOF + bilineal."""
import numpy as np
import pytest

from bridgejm.analysis.pier_pushover import (
    PierPushoverInput,
    pier_pushover_sdof,
    bilinear_idealization,
    BilinearCurve,
)


class TestPierPushover:
    """Cepa RC 8m altura, seccion 1.2x1.2m."""

    def test_cepa_rc_basica(self):
        """Pushover de cepa 8m, 1.2x1.2m con propiedades default."""
        inp = PierPushoverInput(H_m=8.0, B_m=1.2)
        res = pier_pushover_sdof(inp)
        assert res.bilinear.Vy_kN > 0
        assert res.bilinear.delta_y_mm > 0
        assert res.bilinear.delta_u_mm > res.bilinear.delta_y_mm

    def test_ductilidad_mayor_1(self):
        inp = PierPushoverInput(H_m=8.0, B_m=1.2)
        res = pier_pushover_sdof(inp)
        assert res.bilinear.mu_displacement > 1.0

    def test_momento_fluencia_positivo(self):
        inp = PierPushoverInput(H_m=8.0, B_m=1.2)
        res = pier_pushover_sdof(inp)
        assert res.My_kNm > 0
        assert res.Mu_kNm >= res.My_kNm

    def test_curva_monotona(self):
        """La curva pushover debe ser monotonamente creciente."""
        inp = PierPushoverInput(H_m=8.0, B_m=1.2, n_points=100)
        res = pier_pushover_sdof(inp)
        for i in range(1, len(res.V_base_kN)):
            assert res.V_base_kN[i] >= res.V_base_kN[i - 1] - 1e-10

    def test_delta_crece(self):
        """El vector de desplazamiento debe ser monotonamente creciente."""
        inp = PierPushoverInput(H_m=8.0, B_m=1.2)
        res = pier_pushover_sdof(inp)
        for i in range(1, len(res.delta_mm)):
            assert res.delta_mm[i] >= res.delta_mm[i - 1] - 1e-10

    def test_longitud_rotula_plastica(self):
        inp = PierPushoverInput(H_m=8.0, B_m=1.2)
        res = pier_pushover_sdof(inp)
        # Lp ~ 0.08*8 + 0.022*420*0.025 = 0.64 + 0.231 = 0.871 m
        assert 0.5 < res.Lp_m < 1.5

    def test_cepa_alta_mas_flexible(self):
        """Cepa mas alta tiene delta_y mayor."""
        res_8 = pier_pushover_sdof(PierPushoverInput(H_m=8.0, B_m=1.2))
        res_12 = pier_pushover_sdof(PierPushoverInput(H_m=12.0, B_m=1.2))
        assert res_12.bilinear.delta_y_mm > res_8.bilinear.delta_y_mm

    def test_mayor_cuantia_mas_fuerte(self):
        """Mayor cuantia de acero produce mayor cortante de fluencia."""
        res_low = pier_pushover_sdof(PierPushoverInput(
            H_m=8.0, B_m=1.2, rho_long=0.01,
        ))
        res_high = pier_pushover_sdof(PierPushoverInput(
            H_m=8.0, B_m=1.2, rho_long=0.03,
        ))
        assert res_high.bilinear.Vy_kN > res_low.bilinear.Vy_kN

    def test_seccion_rectangular_no_cuadrada(self):
        inp = PierPushoverInput(H_m=8.0, B_m=1.2, D_m=1.5)
        res = pier_pushover_sdof(inp)
        assert res.bilinear.Vy_kN > 0

    def test_input_invalido(self):
        with pytest.raises(ValueError):
            pier_pushover_sdof(PierPushoverInput(H_m=0, B_m=1.2))
        with pytest.raises(ValueError):
            pier_pushover_sdof(PierPushoverInput(H_m=8, B_m=0))

    def test_to_dict(self):
        inp = PierPushoverInput(H_m=8.0, B_m=1.2)
        res = pier_pushover_sdof(inp)
        d = res.to_dict()
        assert "bilinear" in d
        assert "My_kNm" in d
        assert d["bilinear"]["mu_displacement"] > 1.0


class TestBilinearIdealization:
    def test_equal_energy(self):
        """Area bajo bilineal ~ area bajo curva original."""
        delta = np.linspace(0, 100, 50)
        V = 500 * (1 - np.exp(-delta / 20))  # curva elastoplastica
        bl = bilinear_idealization(delta, V)
        E_curve = float(np.trapezoid(V, delta))
        # Area bilineal
        E_bilinear = (0.5 * bl.Vy_kN * bl.delta_y_mm +
                      0.5 * (bl.Vy_kN + bl.Vu_kN) *
                      (bl.delta_u_mm - bl.delta_y_mm))
        assert E_bilinear == pytest.approx(E_curve, rel=0.15)

    def test_ductilidad_correcta(self):
        delta = np.array([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
        V = np.array([0, 200, 350, 450, 480, 490, 495, 498, 499, 499.5, 500])
        bl = bilinear_idealization(delta, V)
        assert bl.mu_displacement == pytest.approx(
            bl.delta_u_mm / bl.delta_y_mm, rel=1e-6
        )

    def test_minimo_puntos(self):
        with pytest.raises(ValueError):
            bilinear_idealization([0], [0])
