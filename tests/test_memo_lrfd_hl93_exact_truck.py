"""La memoria ligera usa el barrido exacto del camión (antes 145·L/4 − 145·4,3/2 = 776 kN·m en L = 30 m)."""
import pytest

from bridgecalc.loads.hl93 import hl93_envelope
from bridgecalc.memos.lrfd_hl93 import HL93MemoInput, generar_memoria_hl93


def test_camion_coincide_con_la_envolvente_exacta():
    m = generar_memoria_hl93(HL93MemoInput(L_span_m=30.0))
    e = hl93_envelope(30.0)
    assert m.M_truck_kNm == pytest.approx(e["M_truck_kNm"], rel=1e-9)
    assert m.M_tandem_kNm == pytest.approx(e["M_tandem_kNm"], rel=1e-9)
    assert m.M_truck_kNm > 2000.0            # la fórmula antigua daba 775.75
    assert m.M_lane_kNm == pytest.approx(9.34 * 30.0 ** 2 / 8.0)
    assert m.governing_vehicle == "truck"
    assert m.M_LL_IM_kNm == pytest.approx(m.M_truck_kNm * 1.33 + m.M_lane_kNm)
    assert m.M_Strength_I_kNm == pytest.approx(1.25 * m.M_DC_kNm + 1.50 * m.M_DW_kNm + 1.75 * m.M_LL_IM_kNm)


def test_luz_corta_gobierna_el_tandem_y_se_declara():
    m = generar_memoria_hl93(HL93MemoInput(L_span_m=8.0))
    assert m.governing_vehicle == "tandem"
    assert "tandem" in m.markdown
