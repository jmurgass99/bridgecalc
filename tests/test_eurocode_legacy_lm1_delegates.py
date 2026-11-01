"""``loads.eurocode.evaluate_lm1`` (legado) delega en Barré y avisa; antes daba el tándem a la mitad."""
import warnings

import pytest

from bridgecalc.loads.eurocode import LM1Input, evaluate_lm1
from bridgecalc.loads.eurocode_lm1 import EurocodeLM1Input, evaluate_eurocode_lm1


def test_coincide_con_eurocode_lm1_y_avisa():
    with pytest.warns(DeprecationWarning):
        old = evaluate_lm1(LM1Input(carriageway_width_m=7.0, span_m=30.0))
    new = evaluate_eurocode_lm1(EurocodeLM1Input(carriageway_width_m=7.0, span_m=30.0))
    assert old.n_lanes == new.n_lanes == 2
    assert old.M_TS_kNm == pytest.approx(new.M_TS_kNm)
    assert old.M_UDL_kNm == pytest.approx(new.M_UDL_kNm)
    assert old.V_max_kN == pytest.approx(new.V_total_kN)
    # Barré para dos ejes iguales: Q·((L − d)/2 + d²/(8L)) por carril: 300·14.406 + 200·14.406 = 7203
    assert old.M_TS_kNm == pytest.approx(500.0 * ((30.0 - 1.2) / 2.0 + 1.2 ** 2 / (8.0 * 30.0)), rel=1e-9)
    assert old.M_TS_kNm > 3748.5 * 1.5      # la fórmula antigua daba 3748.5


def test_alpha_qr_se_aplica_a_tandem_y_udl_de_los_carriles_restantes():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        r = evaluate_lm1(LM1Input(carriageway_width_m=7.0, span_m=20.0, alpha_qr=0.5))
    new = evaluate_eurocode_lm1(EurocodeLM1Input(carriageway_width_m=7.0, span_m=20.0, alpha_Qr=0.5, alpha_qr=0.5))
    assert r.M_total_kNm == pytest.approx(new.M_total_kNm)
