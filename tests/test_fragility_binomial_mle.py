"""lognormal_fragility es ahora MLE binomial: recupera la mediana y β con que se generan los datos."""
import numpy as np
import pytest

from bridgecalc.fragility import FragilityCurve, lognormal_fragility


def test_recupera_parametros_de_datos_sinteticos():
    rng = np.random.default_rng(11)
    ims = rng.uniform(0.05, 1.5, 2000)
    true = FragilityCurve(median=0.45, beta=0.5)
    dam = rng.uniform(size=ims.size) < true.probability(ims)
    fit = lognormal_fragility(ims, dam)
    assert fit.median == pytest.approx(0.45, rel=0.08)
    assert fit.beta == pytest.approx(0.5, rel=0.15)


def test_separacion_perfecta_queda_en_beta_minimo_con_mediana_entre_los_grupos():
    ims = np.array([0.2, 0.3, 0.4, 0.5, 0.6, 0.7])
    dam = np.array([False, False, False, True, True, True])
    fit = lognormal_fragility(ims, dam)
    assert 0.4 <= fit.median <= 0.5
    assert fit.beta == pytest.approx(0.1)


def test_sin_daño_o_todo_dañado_no_se_puede_ajustar():
    with pytest.raises(ValueError):
        lognormal_fragility([0.1, 0.2], [False, False])
    with pytest.raises(ValueError):
        lognormal_fragility([0.1, 0.2], [True, True])
