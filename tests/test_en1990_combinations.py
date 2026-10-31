# -*- coding: utf-8 -*-
"""Combinaciones EN 1990 — validado a mano."""
import pytest

from bridgecalc.loads.en1990_combinations import (
    VariableAction,
    uls_strength,
    uls_governing,
    sls_combination,
    seismic_combination,
    PSI_CATALOG,
)

G = {"peso_propio": 100.0}
Q = [VariableAction("uso", 50.0, "A"), VariableAction("viento", 30.0, "wind")]


class TestULS:
    def test_610_gobernante(self):
        # Cada acción no-dominante entra con SU ψ0 (viento ψ0=0.6, uso ψ0=0.7).
        # Q1 (uso) dominante: 1.35·100 + 1.5·50 + 1.5·0.6·30 = 135+75+27 = 237.0
        # Q2 (viento) dom.:   1.35·100 + 1.5·30 + 1.5·0.7·50 = 135+45+52.5 = 232.5
        assert uls_strength(G, Q, "6.10") == pytest.approx(237.0)

    def test_610b_usa_xi(self):
        # 6.10b: 0.85·1.35·100 + 1.5·50 + 1.5·0.6·30 = 114.75 + 75 + 27 = 216.75
        assert uls_strength(G, Q, "6.10b") == pytest.approx(216.75)

    def test_610a_reduce_dominante(self):
        # 6.10a: 1.35·100 + 1.5·0.7·50 + 1.5·0.6·30 = 135 + 52.5 + 27 = 214.5
        assert uls_strength(G, Q, "6.10a") == pytest.approx(214.5)

    def test_governing_max_de_a_b(self):
        assert uls_governing(G, Q) == pytest.approx(max(uls_strength(G, Q, "6.10a"),
                                                        uls_strength(G, Q, "6.10b")))

    def test_solo_permanente(self):
        assert uls_strength(G, [], "6.10") == pytest.approx(135.0)


class TestSLS:
    def test_caracteristica(self):
        # Q1 dom: 100 + 50 + 0.6·30 = 168 ; Q2 dom: 100 + 30 + 0.7·50 = 165 -> 168
        assert sls_combination(G, Q, "characteristic") == pytest.approx(168.0)

    def test_frecuente(self):
        # Q1 dom (psi1_A=0.5): 100 + 0.5·50 + 0·30 = 125 (psi2_wind=0)
        # Q2 dom (psi1_wind=0.2): 100 + 0.2·30 + 0.3·50 = 121 -> gobierna 125
        assert sls_combination(G, Q, "frequent") == pytest.approx(125.0)

    def test_cuasipermanente(self):
        # 100 + 0.3·50 + 0·30 = 115
        assert sls_combination(G, Q, "quasi_permanent") == pytest.approx(115.0)

    def test_orden_uls_mayor_que_sls(self):
        assert uls_strength(G, Q, "6.10") > sls_combination(G, Q, "characteristic")


class TestSismica:
    def test_sismica(self):
        # 100 + AEd(80) + 0.3·50 + 0·30 = 195
        assert seismic_combination(G, Q, AEd=80.0) == pytest.approx(195.0)


def test_psi_catalogo():
    assert PSI_CATALOG["A"] == (0.7, 0.5, 0.3)
    assert PSI_CATALOG["wind"][0] == 0.6
