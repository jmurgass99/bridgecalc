"""Tests para autocad_layout."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from bridgejm.integration import autocad_layout as al
from bridgejm.integration.revit_export import BridgeGeometry, PierGeometry


def _client_mock():
    c = MagicMock()
    return c


def test_draw_layout_with_piers():
    client = _client_mock()
    bridge = BridgeGeometry(
        spans_m=[30.0, 40.0, 30.0],
        piers=[PierGeometry(30.0, 10.0), PierGeometry(70.0, 12.0)],
        project_name="P1",
    )
    counts = al.draw_bridge_layout(client, bridge)
    assert counts["piers"] == 2
    # 1 eje + 2 piers + 3 cotas = 6 líneas mínimo
    assert counts["lines"] >= 6
    # 2 etiquetas P1/P2 + 3 cotas + 1 título = 6 textos
    assert counts["texts"] >= 6
    # set_layer llamado para cada categoría
    layers = {c.args[0] for c in client.set_layer.call_args_list}
    assert {"BR-AXIS", "BR-PIER", "BR-DIMS", "BR-TITLE"} <= layers


def test_draw_layout_synthesizes_piers_when_empty():
    client = _client_mock()
    bridge = BridgeGeometry(spans_m=[20.0, 30.0, 20.0], project_name="P2")
    counts = al.draw_bridge_layout(client, bridge)
    # 3 luces → 2 piers sintetizadas
    assert counts["piers"] == 2


def test_layout_calls_draw_polyline():
    client = _client_mock()
    bridge = BridgeGeometry(spans_m=[10.0, 10.0], piers=[PierGeometry(10.0, 5.0)])
    al.draw_bridge_layout(client, bridge)
    assert client.draw_polyline.called
    assert client.draw_text.called


def test_layout_style_override():
    client = _client_mock()
    bridge = BridgeGeometry(spans_m=[10.0], piers=[])
    style = al.LayoutStyle(text_height_m=1.0)
    al.draw_bridge_layout(client, bridge, style)
    # asegúrate que el height usado coincide en las llamadas a draw_text
    call_heights = [kw.get("height") or args[2] if len(args) >= 3 else kw.get("height")
                    for args, kw in (c[:2] for c in client.draw_text.call_args_list)]
    # al menos un texto con height 1.0
    assert any(h == 1.0 for h in call_heights)


def _sample_converged_bridge_design_result(tmp_path):
    """Ejecuta el bucle de diseño sobre _StatefulBridgeSapMock para obtener un resultado
    completo de puente redimensionado (PG_1900x650x50x28 / HEB 400) sin valores duplicados a mano.
    """
    import importlib.util
    from pathlib import Path
    from jmworkbench.encargo import interpretar_encargo
    from bridgejm.integration.grillage_model import (
        bridge_spec_from_encargo,
        execute_bridge_grillage_design_loop,
    )

    spec_tg = importlib.util.spec_from_file_location(
        "test_grillage_model",
        Path(__file__).with_name("test_grillage_model.py"),
    )
    assert spec_tg is not None and spec_tg.loader is not None
    mod_tg = importlib.util.module_from_spec(spec_tg)
    spec_tg.loader.exec_module(mod_tg)
    _StatefulBridgeSapMock = mod_tg._StatefulBridgeSapMock

    enc = interpretar_encargo(
        "Diseña un puente de 30 m de luz.",
        supuestos={
            "norma": "EN 1991-2",
            "uso": "carretera",
            "ancho_tablero_o_carriles": "ancho de tablero 10 m",
            "material": "acero",
            "apoyos": "simplemente apoyado",
            "galibo": "gálibo de 5,5 m",
            "acciones": "LM1",
        },
    )
    spec = bridge_spec_from_encargo(enc)
    mock_sap = _StatefulBridgeSapMock()
    sdb_file = tmp_path / "puente_30m_mock.sdb"
    ladder = ("HEM 1000", "PG_1500x550x40x24", "PG_1900x650x50x28")
    return execute_bridge_grillage_design_loop(
        mock_sap,
        str(sdb_file),
        spec=spec,
        candidate_girder_ladder=ladder,
    )


def test_export_bridge_grillage_drawings_generates_and_verifies_dxf(tmp_path):
    """Tarea 5 (3.2): Genera el plano DXF a partir del resultado definitivo del bucle de puente,
    reabre el DXF con ezdxf y verifica capas, entidades, cotas, secciones finales asignadas,
    apoyos fijos/móviles, tabla de perfiles y materiales, verificaciones ULS/SLS, estado global
    REQUIERE_REVISION y salvedades normativas.
    """
    import ezdxf

    design_res = _sample_converged_bridge_design_result(tmp_path)
    out_dir = tmp_path / "planos_out"

    cad_report = al.export_bridge_grillage_drawings(
        design_res,
        out_dir,
        base_name="puente_disposicion_general",
        generate_native_dwg=False,
    )

    dxf_path = out_dir / "puente_disposicion_general.dxf"
    assert dxf_path.exists() and dxf_path.stat().st_size > 2000
    assert cad_report["dxf_path"] == str(dxf_path.resolve())
    assert cad_report["dxf_verification"]["ok"] is True
    assert cad_report["dxf_verification"]["errors"] == 0
    assert cad_report["drawing_scope"] == "ESQUEMATICO_DISPOSICION_GENERAL_NO_CONSTRUCTIVO"

    # Reabrir el archivo DXF desde disco e inspeccionar capas, entidades y textos reales
    doc = ezdxf.readfile(str(dxf_path))
    layer_names = {layer.dxf.name for layer in doc.layers}
    expected_layers = {
        "BR-AXIS",
        "BR-PIER",
        "BR-DIMS",
        "BR-TITLE",
        "BR-GIRDER",
        "BR-DIAPHRAGM",
        "BR-SUPPORT",
        "BR-SECTION",
        "BR-TABLE",
        "BR-VERIF",
        "BR-STATUS",
    }
    assert expected_layers <= layer_names

    msp = doc.modelspace()
    texts = [
        e.dxf.text
        for e in msp
        if e.dxftype() in ("TEXT", "MTEXT") and hasattr(e.dxf, "text")
    ]
    joined_text = "\n".join(texts)

    # Debe reflejar los datos reales del modelo definitivo, nunca valores inventados
    assert "PG_1900x650x50x28" in joined_text
    assert "HEB 400" in joined_text
    assert "S355" in joined_text
    assert "30.00 m" in joined_text
    assert "10.00 m" in joined_text
    assert "Apoyo Fijo" in joined_text
    assert "Apoyo Movil" in joined_text or "Apoyo Móvil" in joined_text
    assert "CUMPLE" in joined_text
    assert "REQUIERE_REVISION" in joined_text
    assert "NO CONSTRUCTIVO" in joined_text.upper() or "DISPOSICION GENERAL" in joined_text.upper()

    # Al menos 16 segmentos de viga en capa BR-GIRDER y 15 de diafragma en BR-DIAPHRAGM
    girder_entities = [e for e in msp if e.dxf.layer == "BR-GIRDER"]
    diaph_entities = [e for e in msp if e.dxf.layer == "BR-DIAPHRAGM"]
    assert len(girder_entities) >= 16
    assert len(diaph_entities) >= 15


@pytest.mark.compat
@pytest.mark.live
def test_export_bridge_grillage_drawings_live_autocad_dwg(tmp_path):
    """Tarea 5 (3.2 LIVE): Genera tanto el DXF como el DWG nativo real mediante AutoCAD 2026
    (accoreconsole.exe), reabre el DWG en una segunda sesión limpia de accoreconsole.exe y
    verifica que los recuentos de entidades LINE y TEXT coinciden al 100%.
    """
    from pathlib import Path

    accore = Path(r"C:\Program Files\Autodesk\AutoCAD 2026\accoreconsole.exe")
    if not accore.exists():
        pytest.skip(f"AutoCAD 2026 accoreconsole.exe no instalado en {accore}")

    design_res = _sample_converged_bridge_design_result(tmp_path)
    out_dir = tmp_path / "planos_live_dwg"

    cad_report = al.export_bridge_grillage_drawings(
        design_res,
        out_dir,
        base_name="puente_disposicion_general",
        generate_native_dwg=True,
    )

    dwg_path = Path(cad_report["dwg_path"])
    assert dwg_path.exists()
    assert cad_report["dwg_size_bytes"] > 5000
    assert cad_report["dwg_verification"]["verified_via_accoreconsole"] is True
    assert cad_report["dwg_verification"]["lines_created"] > 30
    assert cad_report["dwg_verification"]["lines_reopened"] == cad_report["dwg_verification"]["lines_created"]
    assert cad_report["dwg_verification"]["texts_created"] > 20
    assert cad_report["dwg_verification"]["texts_reopened"] == cad_report["dwg_verification"]["texts_created"]
    assert cad_report["dwg_verification"]["veredicto"] == "OK"
