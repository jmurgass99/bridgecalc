"""Optimizacion multiobjetivo del puente: las alternativas NO calculadas en SAP2000 son una
estimacion de viga aislada, sin factores de alivio inventados, y se declaran como tal.

Defecto (auditoria nocturna 2026-10-25): `evaluate_bridge_design_alternatives` multiplicaba
las demandas estimadas por `grillage_relief_M = 0.72` y las flechas por
`grillage_relief_defl = 0.565` ("calibrados con el emparrillado 3D") para cualquier luz,
numero de vigas y seccion. Las cargas por viga YA incluyen el reparto transversal (Courbon
para el carril, `share_g0` para los ejes), asi que el 0.72 contaba dos veces el mismo efecto,
del lado inseguro, y decidia `feasible` con una etiqueta `GRILLAGE_COUPLED_MODEL` que sugeria
un calculo con modelo que no existio.
"""
from __future__ import annotations

import pytest

from jmworkbench.encargo import interpretar_encargo
from bridgejm.integration.grillage_model import (
    _compute_member_capacities_ec3,
    bridge_spec_from_encargo,
    evaluate_bridge_design_alternatives,
    grillage_model,
    section_props_from_catalog,
)

SUPUESTOS = {"norma": "EN 1991-2", "uso": "carretera", "ancho_tablero_o_carriles": "ancho de tablero 10 m",
             "material": "acero", "apoyos": "simplemente apoyado", "galibo": "gálibo de 5,5 m", "acciones": "LM1"}


@pytest.fixture(scope="module")
def informe():
    spec = bridge_spec_from_encargo(interpretar_encargo("Diseña un puente de 30 m de luz.", supuestos=SUPUESTOS))
    return spec, evaluate_bridge_design_alternatives(spec, candidate_girder_counts=(4,),
                                                     candidate_sections=("HEM 1000", "PG_1900x650x50x28"))


def test_alternativa_estimada_se_declara_no_verificada(informe) -> None:
    _, rep = informe
    for a in rep["all_alternatives"]:
        assert a["verificada_sap2000"] is False
        assert "ESTIMACION" in a["evaluation_source"] and "NO VERIFICADA" in a["evaluation_source"]


def test_estimacion_sin_factor_de_alivio(informe) -> None:
    """M_Ed estimado = momento isostatico de la viga exterior con sus cargas YA repartidas (sin x0.72)."""
    spec, rep = informe
    L = spec.span_m
    ls = grillage_model(L, spec.width_m, n_girders=4, n_diaphragms=spec.n_diaphragms, n_spans=spec.n_spans,
                        long_section=spec.girder_section.name, trans_section=spec.diaphragm_section.name,
                        spec=spec)["meta"]["loads_summary"]
    share = float(ls["transverse_distribution"]["vehicle_axle_share_by_girder"].get(0, 0.0)
                  or ls["transverse_distribution"]["vehicle_axle_share_by_girder"].get("0", 0.0))
    q_lane = float(ls["q_lane_by_girder_kN_m"].get(0, ls["q_lane_by_girder_kN_m"].get("0", 0.0)))
    m_veh = 0.0
    for p, x in zip(ls["vehicle_axles_M_kN"], ls["vehicle_positions_M_m"]):
        p, x = float(p) * share, float(x)
        r_a = p * (L - x) / L
        m_veh += r_a * L / 2 - (p * (L / 2 - x) if x < L / 2 else 0.0)
    sec = section_props_from_catalog("HEM 1000", material_name=spec.material.name)
    q_dead = sec.A_m2 * spec.material.gamma_kN_m3 + float(ls["q_slab_per_girder_kN_m"])
    m_ed = 1.35 * (q_dead + float(ls["q_dw_per_girder_kN_m"])) * L ** 2 / 8 + 1.35 * (q_lane * L ** 2 / 8 + m_veh)
    alt = next(a for a in rep["all_alternatives"] if a["girder_section"] == "HEM 1000")
    assert alt["M_Ed_estimado_kNm"] == pytest.approx(m_ed, rel=1e-6)
    mb = _compute_member_capacities_ec3(sec.to_dict(), spec.material.to_dict(),
                                        L_ltb_m=L / (spec.n_diaphragms + 1))["Mb_Rd_kNm"]
    assert alt["max_dcr_uls"] >= m_ed / mb - 1e-4      # la metrica se publica redondeada a 6 decimales


def test_seccion_clase_4_queda_fuera_de_la_optimizacion(informe) -> None:
    spec, _ = informe
    rep = evaluate_bridge_design_alternatives(spec, candidate_girder_counts=(4,),
                                              candidate_sections=("HEM 1000", "PG_2000x600x40x10"))
    alt = next(a for a in rep["all_alternatives"] if a["girder_section"] == "PG_2000x600x40x10")
    assert alt["feasible"] is False and alt["max_dcr_uls"] is None
    assert "clase 4" in alt["evaluation_source"].lower()
