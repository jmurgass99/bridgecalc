"""Clasificacion de alternativas, gamma_DW de AASHTO e interaccion con M2 (auditoria PR #11).

1. Una alternativa seleccionada que solo es una estimacion de viga aislada se clasificaba
   `MEJOR_SOLUCION_ENCONTRADA`. Sin analisis FEM de esa alternativa no hay solucion verificada.
2. Material no acero (hormigon): el evaluador reventaba con KeyError al buscar el diafragma de
   hormigon en el catalogo de perfiles de acero, despues de haber ejecutado el analisis.
3. AASHTO LRFD Tabla 3.4.1-2 (Strength I, maximos): DC 1.25, DW 1.50. La estimacion aplicaba
   1.25 tambien a DW.
4. Interaccion con el momento del eje debil: coeficiente 1 (EN 1993-1-1 §6.2.1(7) ec. (6.2);
   AASHTO §6.8.2.3 / §6.9.2.2). Se usaba 0.5 sin fuente normativa.
"""
from __future__ import annotations

import dataclasses

import pytest

from jmworkbench.encargo import interpretar_encargo
from bridgejm.integration.grillage_model import (
    _evaluate_concurrent_station_row,
    bridge_spec_from_encargo,
    evaluate_bridge_design_alternatives,
    grillage_model,
)

ORDEN = "Diseña un puente de 30 m de luz."
BASE = {"uso": "carretera", "ancho_tablero_o_carriles": "ancho de tablero 10 m",
        "apoyos": "simplemente apoyado", "galibo": "gálibo de 5,5 m"}
EN = dict(BASE, norma="EN 1991-2", material="acero", acciones="LM1")
AASHTO = dict(BASE, norma="AASHTO LRFD", material="acero", acciones="HL-93")


def _spec(supuestos):
    return bridge_spec_from_encargo(interpretar_encargo(ORDEN, supuestos=supuestos))


class TestClasificacion:
    def test_seleccion_solo_estimada_no_es_mejor_solucion(self):
        rep = evaluate_bridge_design_alternatives(_spec(EN), final_design_result=None)
        sel = rep["selected_alternative"]
        assert sel is not None and sel["feasible"] and sel["verificada_sap2000"] is False
        assert rep["optimization_classification"] == "ESTIMACION_NO_VERIFICADA"
        assert rep["verified_alternatives_count"] == 0

    def test_puente_de_hormigon_no_revienta_y_queda_no_calculado(self):
        spec = _spec(dict(EN, material="hormigon pretensado"))
        assert spec.material.material_type == "concrete"
        rep = evaluate_bridge_design_alternatives(spec, final_design_result=None)
        assert rep["optimization_classification"] == "NO_CALCULADO"
        assert "acero" in rep["motivo"]
        assert rep["all_alternatives"] == [] and rep["selected_alternative"] is None


def _m_ed_y_q_dw(spec, seccion="HEM 1000"):
    rep = evaluate_bridge_design_alternatives(spec, candidate_girder_counts=(4,), candidate_sections=(seccion,))
    alt = rep["all_alternatives"][0]
    ls = grillage_model(spec.span_m, spec.width_m, n_girders=4, n_diaphragms=spec.n_diaphragms,
                        n_spans=spec.n_spans, long_section=spec.girder_section.name,
                        trans_section=spec.diaphragm_section.name, spec=spec)["meta"]["loads_summary"]
    return float(alt["M_Ed_estimado_kNm"]), float(ls["q_dw_per_girder_kN_m"])


@pytest.mark.parametrize("supuestos, gamma_dw", [(AASHTO, 1.50), (EN, 1.35)])
def test_factor_parcial_de_dw_por_sensibilidad(supuestos, gamma_dw):
    """Dos tableros que solo difieren en el pavimento: dM_Ed / (dq_DW * L^2 / 8) = gamma_DW.

    Viga isostatica: M = q L^2 / 8. Ninguna otra carga depende de wearing_surface_kPa, asi que
    la diferencia aisla el factor de DW sin reproducir el resto de la formula del codigo.
    """
    spec_a = _spec(supuestos)
    spec_b = dataclasses.replace(spec_a, wearing_surface_kPa=spec_a.wearing_surface_kPa + 1.0)
    m_a, q_a = _m_ed_y_q_dw(spec_a)
    m_b, q_b = _m_ed_y_q_dw(spec_b)
    assert q_b > q_a
    L = spec_a.span_m
    assert (m_b - m_a) / ((q_b - q_a) * L ** 2 / 8.0) == pytest.approx(gamma_dw, rel=1e-9)


def _cap(**kw):
    base = {"Mc_Rd_kNm": 1000.0, "Mb_Rd_kNm": 1000.0, "Mf_Rd_kNm": 600.0, "Mpl_Rd_kNm": 1100.0,
            "Mcz_Rd_kNm": 200.0, "Vc_Rd_kN": 1000.0, "Npl_Rd_kN": 5000.0}
    base.update(kw)
    return base


def _fila(**kw):
    base = {"frame": "G0_1", "case": "ULS", "station_m": 0.0, "P_kN": 0.0, "V2_kN": 0.0, "M2_kNm": 0.0,
            "M3_kNm": 0.0}
    base.update(kw)
    return base


class TestInteraccionEjeDebil:
    def test_m2_entra_con_coeficiente_uno(self):
        # Sin cortante relevante (V < 0.5 Vc,Rd): 400/1000 + 500/5000 + 50/200 = 0.40 + 0.10 + 0.25
        r = _evaluate_concurrent_station_row(_fila(M3_kNm=400.0, P_kN=500.0, M2_kNm=50.0, V2_kN=100.0),
                                             _cap(), norma="EN_1991_2")
        assert r["dcr_mvn_concurrent"] == pytest.approx(0.75, abs=1e-6)

    def test_m2_con_capacidad_nula_no_se_ignora(self):
        r = _evaluate_concurrent_station_row(_fila(M3_kNm=400.0, M2_kNm=1.0), _cap(Mcz_Rd_kNm=0.0),
                                             norma="EN_1991_2")
        assert r["dcr_mvn_concurrent"] == float("inf")
