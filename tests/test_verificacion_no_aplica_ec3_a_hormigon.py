"""El verificador de puente no puede aplicar resistencias de ACERO (EN 1993 / AASHTO §6.10)
a vigas de HORMIGON.

Defecto encontrado (auditoria nocturna 2026-10-25): `verify_bridge_grillage_results` no miraba
el material. Con `material: hormigon` el predimensionado da secciones RECT de hormigon
(`rectangular_concrete_section_props`: tf=h, tw=b, sin armadura) y `fy_MPa = fck = 35`, y el
verificador las pasaba por `_compute_member_capacities_ec3`: clasificacion de alas, Wpl*fy,
pandeo lateral, abolladura de alma... sobre una viga de hormigon SIN ARMADURA. El DCR que sale
no significa nada, y el bucle de redimensionado actuaba sobre el.

Regla: sin verificacion de hormigon implementada (EN 1992-2 / AASHTO §5), el resultado es
NO_CALCULADO con el motivo, sin capacidades ni DCR.
"""
from __future__ import annotations
import pytest as _pytest_skip
_pytest_skip.importorskip("fastsap")  # dependencia externa opcional: sin ella estos tests se omiten

import importlib.util
from pathlib import Path

from bridgecalc._common.audit_status import CalculationStatus

from bridgecalc.integration.grillage_model import (
    default_bridge_material,
    select_bridge_sections,
    verify_bridge_grillage_results,
)

_spec = importlib.util.spec_from_file_location("_tgm", Path(__file__).with_name("test_grillage_model.py"))
_tgm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_tgm)


def _informe_hormigon() -> dict:
    rep = _tgm._make_synthetic_analysis_report()
    mat = default_bridge_material("hormigon armado", "EN 1991-2")
    girder, diaph, _ = select_bridge_sections(30.0, mat)
    rep["meta"]["material"] = mat.to_dict()
    rep["meta"]["sections"] = {girder.name: girder.to_dict(), diaph.name: diaph.to_dict()}
    for f in rep["frames"]:
        f["section"] = girder.name if f.get("role") == "girder" else diaph.name
    return rep


def test_viga_de_hormigon_no_se_verifica_con_formulas_de_acero() -> None:
    verif = verify_bridge_grillage_results(_informe_hormigon())
    assert verif["calculation_status"] == CalculationStatus.NO_CALCULADO, verif.get("calculation_status")
    assert verif["max_dcr_uls"] is None and verif["max_dcr_overall"] is None
    assert verif["checks"] == []
    assert any("hormig" in m.lower() for m in verif["missing_inputs"]), verif["missing_inputs"]


def test_la_viga_de_acero_sigue_verificandose() -> None:
    verif = verify_bridge_grillage_results(_tgm._make_synthetic_analysis_report())
    assert verif["calculation_status"] == CalculationStatus.CALCULADO_FALLA
    assert verif["checks"]


def test_bucle_de_redimensionado_termina_limpio_si_la_verificacion_es_NO_CALCULADO(tmp_path, monkeypatch) -> None:
    """Defecto relacionado (preexistente): cuando el verificador devuelve NO_CALCULADO (analisis que
    no converge, tablas vacias, equilibrio incumplido, material no soportado), su respuesta no trae
    `governing_check`/`girder_capacities`/`sls_deflections` y el bucle los leia ANTES de mirar el
    estado -> KeyError; la rama `INVALID_ANALYSIS_OR_MISSING_RESULTS` era inalcanzable."""
    import bridgecalc.integration.grillage_model as gm
    from jmworkbench.encargo import interpretar_encargo

    enc = interpretar_encargo(
        "Diseña un puente de 30 m de luz.",
        supuestos={"norma": "EN 1991-2", "uso": "carretera", "ancho_tablero_o_carriles": "ancho de tablero 10 m",
                   "material": "acero", "apoyos": "simplemente apoyado", "galibo": "gálibo de 5,5 m",
                   "acciones": "LM1"},
    )
    spec = gm.bridge_spec_from_encargo(enc)

    def _no_calculado(*a, **k):
        return {"calculation_status": CalculationStatus.NO_CALCULADO,
                "implemented_checks_status": CalculationStatus.NO_CALCULADO.value,
                "missing_inputs": ["RunAnalysis_ret=1"], "max_dcr_uls": None, "max_dcr_sls": None,
                "max_dcr_overall": None, "checks": [], "unimplemented_checks": list(gm.UNIMPLEMENTED_CHECKS)}

    monkeypatch.setattr(gm, "verify_bridge_grillage_results", _no_calculado)
    res = gm.execute_bridge_grillage_design_loop(_tgm._StatefulBridgeSapMock(), str(tmp_path / "x.sdb"), spec=spec)
    assert res["termination_reason"] == "INVALID_ANALYSIS_OR_MISSING_RESULTS"
    assert res["implemented_checks_status"] == "NO_CALCULADO"
    assert res["final_girder_section"] == res["initial_girder_section"], "sin verificacion no se redimensiona"


def test_seccion_clase_4_no_se_calcula_con_un_coeficiente_inventado() -> None:
    """Defecto B1: Clase 4 se resolvia con `0.85 * Wel` (comentado como 'reduccion conservadora'),
    un coeficiente que no sale de EN 1993-1-5 (seccion eficaz). Sin seccion eficaz implementada,
    la verificacion es NO_CALCULADO con el motivo, nunca un DCR apoyado en un factor inventado."""
    from bridgecalc.integration.grillage_model import _compute_member_capacities_ec3, plate_girder_section_props

    esbelta = plate_girder_section_props("PG_2000x600x40x10", 2.0, 0.6, 0.040, 0.010).to_dict()
    mat = default_bridge_material("acero", "EN 1991-2").to_dict()
    cap = _compute_member_capacities_ec3(esbelta, mat, L_ltb_m=7.5)
    assert cap["classification"]["section_class"] == 4
    assert cap["Mc_Rd_kNm"] is None and cap["Mb_Rd_kNm"] is None, "sin seccion eficaz no hay resistencia"

    rep = _tgm._make_synthetic_analysis_report()
    rep["meta"]["sections"]["PG_2000x600x40x10"] = esbelta
    for f in rep["frames"]:
        if f.get("role") == "girder":
            f["section"] = "PG_2000x600x40x10"
    verif = verify_bridge_grillage_results(rep)
    assert verif["calculation_status"] == CalculationStatus.NO_CALCULADO
    assert any("clase 4" in m.lower() for m in verif["missing_inputs"]), verif["missing_inputs"]
