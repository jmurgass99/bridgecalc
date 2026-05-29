"""
bridgejm.integration.grillage_model — emparrillado de puente para SAP/CSiBridge (idea #12, MVP).

Genera la geometría de un tablero de puente como grid (emparrillado / grillage):
vigas longitudinales (girders) × líneas transversales (diafragmas), con apoyos en
las líneas de pila. La salida (``joints`` / ``frames``) es compatible con
``fastsap.worker_sap2000.StructuralJobInput``; la carga de carril HL-93 viaja como
metadato (``loads.hl93`` ya calcula las envolventes de camión/tándem).

MVP: el wiring a CSiBridge vía ``fastcsib`` (objetos puente nativos, definición de
vehículos y casos móviles) queda como TODO — hoy entregamos el modelo de barras
analizable y la carga de carril.
"""
from __future__ import annotations

from typing import Any

# Carga de carril HL-93 (AASHTO LRFD 3.6.1.2.4): 9.3 kN/m por carril de diseño.
HL93_LANE_LOAD_KN_M = 9.3


def generate_grillage(
    *,
    n_spans: int = 1,
    span_length: float = 20.0,
    n_girders: int = 4,
    girder_spacing: float = 2.5,
    divisions_per_span: int = 8,
    long_section: str = "GIRDER",
    trans_section: str = "DIAPHRAGM",
) -> dict[str, Any]:
    """Devuelve ``{joints, frames, meta}`` del emparrillado.

    - joints: ``{id,x,y,z,restraint}`` (apoyos articulados en las líneas de pila).
    - frames: longitudinales ``L*`` (vigas) + transversales ``T*`` (diafragmas).
    """
    if n_spans < 1 or n_girders < 2 or divisions_per_span < 1:
        raise ValueError("n_spans>=1, n_girders>=2, divisions_per_span>=1")

    nx = n_spans * divisions_per_span + 1            # líneas transversales
    dx = span_length / divisions_per_span
    x_coords = [round(ix * dx, 6) for ix in range(nx)]
    # índices de líneas transversales que caen sobre una pila (x = k·span_length)
    support_ix = {k * divisions_per_span for k in range(n_spans + 1)}

    def jid(ix: int, ig: int) -> str:
        return f"N{ix}_{ig}"

    joints: list[dict[str, Any]] = []
    for ix in range(nx):
        for ig in range(n_girders):
            joints.append({
                "id": jid(ix, ig),
                "x": x_coords[ix],
                "y": round(ig * girder_spacing, 6),
                "z": 0.0,
                # apoyo articulado (pin) en las líneas de pila
                "restraint": [True, True, True, False, False, False] if ix in support_ix else None,
            })

    frames: list[dict[str, Any]] = []
    # Vigas longitudinales: a lo largo de cada girder
    for ig in range(n_girders):
        for ix in range(nx - 1):
            frames.append({"id": f"L{ix}_{ig}", "joint_i": jid(ix, ig),
                           "joint_j": jid(ix + 1, ig), "section": long_section})
    # Diafragmas transversales: en cada línea, entre girders consecutivos
    for ix in range(nx):
        for ig in range(n_girders - 1):
            frames.append({"id": f"T{ix}_{ig}", "joint_i": jid(ix, ig),
                           "joint_j": jid(ix, ig + 1), "section": trans_section})

    return {
        "joints": joints,
        "frames": frames,
        "meta": {
            "n_spans": n_spans, "span_length": span_length, "n_girders": n_girders,
            "girder_spacing": girder_spacing, "divisions_per_span": divisions_per_span,
            "total_length": round(n_spans * span_length, 6),
            "lane_load_kN_m": HL93_LANE_LOAD_KN_M,
        },
    }


__all__ = ["generate_grillage", "HL93_LANE_LOAD_KN_M"]
