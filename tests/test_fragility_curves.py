"""Tests BJ-005: curvas de fragilidad lognormales para cepas RC."""
import pytest
import numpy as np

from bridgejm.fragility.fragility_curves import (
    FragilityCurveSet,
    hazus_rc_pier_fragility,
    fragility_probability,
    compute_discrete_damage_probabilities,
    HAZUS_RC_PIER_PARAMS,
)
from bridgejm.fragility import FragilityCurve


class TestFragilityProbability:
    def test_p_half_at_median(self):
        """P = 0.5 exactamente cuando IM = mediana."""
        for ds, (median, beta) in HAZUS_RC_PIER_PARAMS.items():
            p = fragility_probability(median, median, beta)
            assert p == pytest.approx(0.5, abs=1e-10), f"Fallo en {ds}"

    def test_monotonicidad(self):
        """P crece monotonamente con IM."""
        median, beta = 0.30, 0.55
        ims = np.linspace(0.01, 2.0, 50)
        probs = [fragility_probability(im, median, beta) for im in ims]
        for i in range(1, len(probs)):
            assert probs[i] >= probs[i - 1]

    def test_input_invalido(self):
        with pytest.raises(ValueError):
            fragility_probability(0, 0.5, 0.4)
        with pytest.raises(ValueError):
            fragility_probability(0.5, 0, 0.4)
        with pytest.raises(ValueError):
            fragility_probability(0.5, 0.5, 0)


class TestFragilityCurveSet:
    def test_hazus_defaults(self):
        fcs = hazus_rc_pier_fragility()
        assert fcs.slight.median == pytest.approx(0.15)
        assert fcs.complete.median == pytest.approx(0.80)

    def test_p_half_at_median_set(self):
        fcs = hazus_rc_pier_fragility()
        pa = fcs.probability_all(0.15)
        assert pa["slight"] == pytest.approx(0.5, abs=1e-6)
        pa2 = fcs.probability_all(0.80)
        assert pa2["complete"] == pytest.approx(0.5, abs=1e-6)

    def test_monotonicidad_entre_estados(self):
        """Para cualquier IM dado, P(slight) >= P(moderate) >= ... >= P(complete)."""
        fcs = hazus_rc_pier_fragility()
        for im in [0.1, 0.3, 0.5, 1.0, 2.0]:
            pa = fcs.probability_all(im)
            assert pa["slight"] >= pa["moderate"]
            assert pa["moderate"] >= pa["extensive"]
            assert pa["extensive"] >= pa["complete"]

    def test_custom_params(self):
        custom = {
            "slight": (0.10, 0.40),
            "moderate": (0.25, 0.40),
            "extensive": (0.45, 0.40),
            "complete": (0.70, 0.40),
        }
        fcs = hazus_rc_pier_fragility(custom)
        assert fcs.slight.median == pytest.approx(0.10)

    def test_monotonicidad_con_im_creciente(self):
        """Para cada estado de dano, P crece con IM."""
        fcs = hazus_rc_pier_fragility()
        ims = [0.05, 0.10, 0.20, 0.40, 0.80, 1.60]
        for ds in ["slight", "moderate", "extensive", "complete"]:
            probs = [fcs.probability_all(im)[ds] for im in ims]
            for i in range(1, len(probs)):
                assert probs[i] >= probs[i - 1]


class TestDiscreteDamage:
    def test_probabilities_sum_to_one(self):
        fcs = hazus_rc_pier_fragility()
        for im in [0.1, 0.3, 0.5, 1.0, 2.0]:
            dp = compute_discrete_damage_probabilities(im, fcs)
            total = sum(dp.values())
            assert total == pytest.approx(1.0, abs=1e-10)

    def test_no_negative_probabilities(self):
        fcs = hazus_rc_pier_fragility()
        for im in np.linspace(0.01, 3.0, 20):
            dp = compute_discrete_damage_probabilities(im, fcs)
            for state, p in dp.items():
                assert p >= -1e-12, f"P({state}) = {p} negativa para IM={im}"
