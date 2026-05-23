"""Combinaciones de carga AASHTO LRFD §3.4.1 + factores de distribución §4.6.2."""
import pytest

from bridgejm.loads.load_combinations import (
    LOAD_COMBINATIONS,
    factored_effect,
    gamma,
    governing_strength,
)
from bridgejm.loads.distribution_factors import (
    GirderGeometry,
    distribution_factors,
    moment_interior,
    shear_interior,
    exterior_e_factor,
)


class TestLoadCombinations:
    def test_todos_los_estados_limite_presentes(self):
        for ls in ("Strength_I", "Strength_II", "Strength_III", "Strength_IV", "Strength_V",
                   "Service_I", "Service_II", "Service_III", "Service_IV",
                   "Fatigue_I", "Fatigue_II", "Extreme_I", "Extreme_II"):
            assert ls in LOAD_COMBINATIONS

    def test_strength_i_factorizado(self):
        # 1.25·DC + 1.50·DW + 1.75·(LL+IM)
        r = factored_effect("Strength_I", {"DC": 100.0, "DW": 20.0, "LL": 80.0})
        assert r.factored_effect == pytest.approx(1.25 * 100 + 1.50 * 20 + 1.75 * 80)
        assert r.contributions["LL"] == pytest.approx(140.0)

    def test_permanente_favorable_usa_gp_minimo(self):
        # Carga muerta favorable -> γp = 0.90 (DC), 0.65 (DW)
        r = factored_effect("Strength_I", {"DC": 100.0, "DW": 20.0}, favorable_permanent=True)
        assert r.factored_effect == pytest.approx(0.90 * 100 + 0.65 * 20)

    def test_service_iii_ll_080(self):
        assert gamma("Service_III", "LL") == 0.80

    def test_fatigue_i_175(self):
        assert gamma("Fatigue_I", "LL") == 1.75

    def test_strength_iii_sin_ll_con_viento(self):
        assert gamma("Strength_III", "LL") == 0.0
        assert gamma("Strength_III", "WS") == 1.40

    def test_governing_strength(self):
        r = governing_strength({"DC": 100.0, "DW": 20.0, "LL": 80.0})
        assert r.limit_state.startswith("Strength")
        # Para LL alto, Strength I (1.75 LL) suele gobernar.
        assert r.limit_state == "Strength_I"

    def test_estado_desconocido_lanza(self):
        with pytest.raises(ValueError):
            gamma("Strength_VI", "LL")


class TestDistributionFactors:
    def test_momento_interior_formula(self):
        # gm1 = 0.06 + (S/14)^0.4 (S/L)^0.3 (Kg/(12 L ts^3))^0.1
        S, L, ts, Kg = 8.0, 80.0, 8.0, 500000.0
        g1, g2 = moment_interior(S, L, ts, Kg)
        kg = (Kg / (12 * L * ts ** 3)) ** 0.1
        assert g1 == pytest.approx(0.06 + (S / 14) ** 0.4 * (S / L) ** 0.3 * kg, rel=1e-9)
        assert g2 == pytest.approx(0.075 + (S / 9.5) ** 0.6 * (S / L) ** 0.2 * kg, rel=1e-9)
        assert g2 > g1  # 2+ carriles gobierna sobre 1 carril (separaciones típicas)

    def test_cortante_interior_formula(self):
        S = 8.0
        g1, g2 = shear_interior(S)
        assert g1 == pytest.approx(0.36 + S / 25.0)
        assert g2 == pytest.approx(0.2 + S / 12.0 - (S / 35.0) ** 2)

    def test_factor_e_exterior(self):
        assert exterior_e_factor(2.0) == pytest.approx(0.77 + 2.0 / 9.1, rel=1e-9)

    def test_factores_completos_y_rangos(self):
        df = distribution_factors(GirderGeometry(S_ft=8.0, L_ft=80.0, ts_in=8.0, Kg_in4=500000.0, de_ft=2.5))
        # Valores físicamente razonables (fracción de línea de ruedas por viga).
        assert 0.2 < df.gm_interior < 1.2
        assert 0.3 < df.gv_interior < 1.5
        assert df.gm_exterior > 0
        # interior toma el máx de 1 y 2+ carriles.
        assert df.gm_interior == max(df.gm_interior_1, df.gm_interior_2)

    def test_gm_crece_con_separacion(self):
        a = distribution_factors(GirderGeometry(6.0, 80.0, 8.0, 5e5))
        b = distribution_factors(GirderGeometry(12.0, 80.0, 8.0, 5e5))
        assert b.gm_interior > a.gm_interior  # más separación -> más carga por viga
