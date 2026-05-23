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
