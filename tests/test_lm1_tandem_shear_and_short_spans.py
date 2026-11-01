"""LM1: cortante del tándem con el segundo eje a d y luces cortas con un solo eje; tres rutas coinciden."""
import pytest

from bridgecalc.ec1_traffic import traffic_envelope_lm1
from bridgecalc.loads.eurocode_lm1 import EurocodeLM1Input, evaluate_eurocode_lm1
from bridgecalc.loads.iap11 import evaluate_iap11_traffic_loads


@pytest.mark.parametrize("L", [1.0, 1.5, 2.0, 3.0, 10.0, 20.0, 30.0])
def test_tres_rutas_dan_el_mismo_tandem(L):
    r = evaluate_eurocode_lm1(EurocodeLM1Input(carriageway_width_m=6.0, span_m=L, n_lanes=2))
    M_ec1, V_ec1 = traffic_envelope_lm1(L_span=L, n_lanes=2)
    iap = evaluate_iap11_traffic_loads(L, 6.0)
    assert r.M_total_kNm == pytest.approx(M_ec1, rel=1e-9)
    assert r.V_total_kN == pytest.approx(V_ec1, rel=1e-9)
    assert r.M_TS_kNm == pytest.approx(iap.M_TS_kNm, abs=0.01)
    assert r.V_TS_kN == pytest.approx(iap.V_TS_kN, abs=0.01)


def test_cortante_20m_dos_carriles_1315():
    r = evaluate_eurocode_lm1(EurocodeLM1Input(carriageway_width_m=7.0, span_m=20.0))
    # 300·(2 − 1,2/20) + 200·(2 − 1,2/20) + 34,5·20/2 = 582 + 388 + 345
    assert r.V_total_kN == pytest.approx(1315.0)


def test_luz_corta_un_solo_eje_centrado():
    r = evaluate_eurocode_lm1(EurocodeLM1Input(carriageway_width_m=3.0, span_m=1.0, n_lanes=1))
    assert r.M_TS_kNm == pytest.approx(300.0 * 1.0 / 4.0)     # antes 300·1,0/2 = 150
    assert r.V_TS_kN == pytest.approx(300.0)                  # el segundo eje no cabe
