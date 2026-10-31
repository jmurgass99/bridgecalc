# -*- coding: utf-8 -*-
"""Calificación de carga AASHTO LRFR (MBE)."""
import pytest

from bridgecalc.rating.load_rating import (
    RatingInput,
    rating_factor,
    rating_both_levels,
    LRFR_LIVE_FACTORS,
)


def _inp(**kw):
    base = dict(Rn=5000.0, DC=1500.0, DW=300.0, LL_IM=900.0)
    base.update(kw)
    return RatingInput(**base)


class TestRatingFactor:
    def test_formula_inventory(self):
        inp = _inp()
        r = rating_factor(inp, "inventory")
        C = 0.90 * 5000.0
        esperado = (C - 1.25 * 1500.0 - 1.50 * 300.0) / (1.75 * 900.0)
        assert r.RF == pytest.approx(esperado, rel=1e-9)
        assert r.gamma_LL == 1.75

    def test_operating_mayor_que_inventory(self):
        # Operating usa γLL menor -> RF mayor que Inventory.
        inp = _inp()
        rf_inv = rating_factor(inp, "inventory").RF
        rf_op = rating_factor(inp, "operating").RF
        assert rf_op > rf_inv

    def test_rf_mayor_1_pasa(self):
        r = rating_factor(_inp(Rn=8000.0), "inventory")
        assert r.ok and r.RF > 1.0

    def test_rf_menor_1_no_pasa(self):
        r = rating_factor(_inp(Rn=2500.0), "inventory")
        assert not r.ok and r.RF < 1.0

    def test_condition_system_factors_reducen_capacidad(self):
        normal = rating_factor(_inp(), "inventory").RF
        degradado = rating_factor(_inp(phi_c=0.85, phi_s=0.90), "inventory").RF
        assert degradado < normal

    def test_ambos_niveles(self):
        res = rating_both_levels(_inp())
        assert set(res) == set(LRFR_LIVE_FACTORS)
        assert res["operating"].RF > res["inventory"].RF

    def test_nivel_invalido_lanza(self):
        with pytest.raises(ValueError):
            rating_factor(_inp(), "permit")
