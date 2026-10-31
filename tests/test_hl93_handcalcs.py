"""Tests BJ-006: memoria handcalcs LRFD HL-93 Strength I."""
import pytest

from bridgecalc.memos.hl93_handcalcs import (
    HL93HandcalcsInput,
    generar_memoria_handcalcs,
)


class TestHL93Handcalcs:
    def test_render_no_vacio(self):
        """El LaTeX generado no debe ser vacio."""
        res = generar_memoria_handcalcs(HL93HandcalcsInput(L_span_m=25))
        assert len(res.latex) > 50
        assert "M" in res.latex

    def test_latex_contiene_formulas(self):
        res = generar_memoria_handcalcs(HL93HandcalcsInput(L_span_m=30))
        # Debe tener secciones o formulas LaTeX
        assert "Strength" in res.latex or "gamma" in res.latex or "\\frac" in res.latex

    def test_markdown_no_vacio(self):
        res = generar_memoria_handcalcs(HL93HandcalcsInput(L_span_m=20))
        assert "Strength I" in res.markdown
        assert "M_u" in res.markdown

    def test_M_DC_correcto(self):
        inp = HL93HandcalcsInput(L_span_m=20, DC_kN_m=25)
        res = generar_memoria_handcalcs(inp)
        expected = 25.0 * 20 ** 2 / 8.0
        assert res.M_DC_kNm == pytest.approx(expected)

    def test_strength_I_factores(self):
        inp = HL93HandcalcsInput(L_span_m=25)
        res = generar_memoria_handcalcs(inp)
        recalc = 1.25 * res.M_DC_kNm + 1.50 * res.M_DW_kNm + 1.75 * res.M_LL_IM_kNm
        assert res.M_Strength_I_kNm == pytest.approx(recalc, rel=1e-6)

    def test_governing_truck_long_span(self):
        res = generar_memoria_handcalcs(HL93HandcalcsInput(L_span_m=40))
        assert res.governing_vehicle == "truck"

    def test_luz_invalida(self):
        with pytest.raises(ValueError):
            generar_memoria_handcalcs(HL93HandcalcsInput(L_span_m=0))

    def test_IM_aplicado_solo_vehicular(self):
        """IM se aplica al vehicular, no al carril."""
        inp = HL93HandcalcsInput(L_span_m=30)
        res = generar_memoria_handcalcs(inp)
        # M_LL_IM debe incluir lane sin IM
        # M_vehicle = max(truck, tandem) * (1 + 0.33)
        # M_LL_IM = (M_vehicle + M_lane) * MPF
        M_vehicle = max(res.M_truck_kNm, res.M_tandem_kNm) * res.IM
        expected = (M_vehicle + res.M_lane_kNm) * inp.MPF
        assert res.M_LL_IM_kNm == pytest.approx(expected, rel=1e-6)

    def test_to_dict(self):
        res = generar_memoria_handcalcs(HL93HandcalcsInput(L_span_m=20))
        d = res.to_dict()
        assert "M_Strength_I_kNm" in d
        assert "latex" in d
        assert d["M_Strength_I_kNm"] > 0
