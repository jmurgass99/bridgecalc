"""La memoria usa handcalcs fuera de Jupyter cuando está instalado y declara el motor."""
import pytest

from bridgecalc.memos.hl93_handcalcs import HL93HandcalcsInput, generar_memoria_handcalcs


def test_motor_declarado_y_coherente_con_el_latex():
    r = generar_memoria_handcalcs(HL93HandcalcsInput(L_span_m=30.0))
    assert r.latex_engine in ("handcalcs", "manual")
    assert r.to_dict()["latex_engine"] == r.latex_engine
    if r.latex_engine == "manual":
        assert "Memoria LRFD HL-93 -- Strength I" in r.latex
    else:
        assert "(handcalcs)" in r.latex


def test_con_handcalcs_instalado_no_cae_al_respaldo():
    pytest.importorskip("handcalcs")
    r = generar_memoria_handcalcs(HL93HandcalcsInput(L_span_m=30.0))
    assert r.latex_engine == "handcalcs"
    assert "2812.500" in r.latex          # M_DC = 25·30²/8 renderizado por handcalcs
