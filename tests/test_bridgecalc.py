"""Tests para BridgeCalc — HL-93 + fragilidad."""
import numpy as np
import pytest

from bridgecalc.loads import HL93Configuration, hl93_influence_envelope
from bridgecalc.fragility import (
    FragilityCurve,
    lognormal_fragility,
    park_ang_damage_index,
)


class TestHL93:
    def test_M_crece_con_luz(self):
        m_30 = hl93_influence_envelope(HL93Configuration(span_m=30)).M_max_kNm
        m_60 = hl93_influence_envelope(HL93Configuration(span_m=60)).M_max_kNm
        assert m_60 > m_30

    def test_luz_corta_tandem_gobierna(self):
        r = hl93_influence_envelope(HL93Configuration(span_m=8))
        # Para luces cortas (<10–12 m) suele gobernar tandem
        assert r.governing_vehicle in ("tandem", "truck")
        assert r.M_max_kNm > 0
        assert r.V_max_kN > 0

    def test_luz_invalida(self):
        with pytest.raises(ValueError):
            hl93_influence_envelope(HL93Configuration(span_m=0))


class TestParkAng:
    def test_di_creciente_con_delta(self):
        d1 = park_ang_damage_index(delta_max=10, delta_u=50, E_h=100, F_y=100)
        d2 = park_ang_damage_index(delta_max=40, delta_u=50, E_h=500, F_y=100)
        assert d2 > d1

    def test_input_invalido(self):
        with pytest.raises(ValueError):
            park_ang_damage_index(delta_max=10, delta_u=0, E_h=1, F_y=1)


class TestFragility:
    def test_curva_lognormal_monotona(self):
        c = FragilityCurve(median=0.5, beta=0.4)
        assert c.probability(0.3) < c.probability(0.5) < c.probability(1.0)

    def test_fit_lognormal_basico(self):
        # Sintetizar: fallas concentradas en torno a IM=0.5
        ims = np.array([0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
        dam = np.array([False, False, False, True, True, True, True, True, True])
        c = lognormal_fragility(ims, dam)
        # separación perfecta entre 0,4 y 0,5 g: la mediana MLE cae entre los dos grupos
        assert 0.4 <= c.median <= 0.5
