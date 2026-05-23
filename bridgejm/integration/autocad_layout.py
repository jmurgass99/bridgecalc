"""
Genera layout AutoCAD del puente: líneas de proyección + cotas + nombres de cepas.

Wrappa `dxfstructuraljm.integration.autocad_live.AutoCADClient` si está disponible
(DXFStructuralJm es opcional). Si no, expone una API equivalente que acepta el
mock para tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .revit_export import BridgeGeometry, PierGeometry


@dataclass(frozen=True)
class LayoutStyle:
    line_color: int = 7        # blanco/negro
    dim_color: int = 3         # verde
    pier_color: int = 1        # rojo
    text_height_m: float = 0.5
    elevation_z: float = 0.0


def draw_bridge_layout(client: Any, bridge: BridgeGeometry, style: LayoutStyle | None = None) -> dict[str, int]:
    """
    Dibuja el layout del puente en AutoCAD usando `client` (AutoCADClient o mock
    con la misma interfaz).

    Devuelve un dict con conteos de entidades dibujadas (útil para tests).
    """
    st = style or LayoutStyle()
    counts = {"lines": 0, "texts": 0, "piers": 0}

    # eje del puente
    x_total = sum(bridge.spans_m)
    client.set_layer("BR-AXIS", color=st.line_color)
    client.draw_polyline([(0.0, 0.0), (x_total, 0.0)])
    counts["lines"] += 1

    # piers (sintetiza si vienen vacías)
    piers = list(bridge.piers)
    if not piers:
        x = 0.0
        for span in bridge.spans_m[:-1]:
            x += span
            piers.append(PierGeometry(x_m=x, height_m=10.0))

    client.set_layer("BR-PIER", color=st.pier_color)
    for i, pier in enumerate(piers, start=1):
        x = pier.x_m
        # línea vertical de la cepa
        client.draw_polyline([(x, 0.0), (x, -pier.height_m)])
        counts["lines"] += 1
        client.draw_text((x, -pier.height_m - st.text_height_m * 2),
                         f"P{i}", height=st.text_height_m)
        counts["texts"] += 1
        counts["piers"] += 1

    # cotas (longitudes de luces)
    client.set_layer("BR-DIMS", color=st.dim_color)
    x_cum = 0.0
    for i, span in enumerate(bridge.spans_m, start=1):
        x_start = x_cum
        x_end = x_cum + span
        y_dim = st.text_height_m * 3
        client.draw_polyline([(x_start, y_dim), (x_end, y_dim)])
        counts["lines"] += 1
        client.draw_text(((x_start + x_end) / 2, y_dim + st.text_height_m * 0.5),
                         f"L{i}={span:.2f} m", height=st.text_height_m)
        counts["texts"] += 1
        x_cum = x_end

    # rótulo general
    client.set_layer("BR-TITLE", color=st.line_color)
    client.draw_text((x_total / 2, -max(p.height_m for p in piers) - st.text_height_m * 6 if piers else 0),
                     bridge.project_name, height=st.text_height_m * 1.5)
    counts["texts"] += 1

    return counts


__all__ = ["LayoutStyle", "draw_bridge_layout"]
