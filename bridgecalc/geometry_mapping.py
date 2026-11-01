"""Mapeo semántico -> malla de tablero continuo (``BridgeGeometryMapping``):
``support_to_nodes`` y ``span_to_elements`` invariantes bajo refinamiento de malla.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple
from .loads import MultiSpanInput, envelope_multispan


@dataclass
class BridgeGeometryMapping:
    """Mapeo bidireccional entre pilas/vanos semánticos y nudos/elementos de viga continua."""

    support_to_nodes: Dict[int, int] = field(default_factory=dict)
    span_to_elements: Dict[int, List[int]] = field(default_factory=dict)
    nodes_x_m: List[float] = field(default_factory=list)
    elements: List[Tuple[int, int]] = field(default_factory=list)


def build_bridge_mesh(span_m: float, n_spans: int, divisions_per_span: int = 10) -> BridgeGeometryMapping:
    """Construye la malla 1D/3D de un puente continuo de ``n_spans`` vanos de longitud ``span_m``."""
    n_div = max(2, int(divisions_per_span))
    support_to_nodes: Dict[int, int] = {}
    span_to_elements: Dict[int, List[int]] = {}
    nodes_x_m: List[float] = []
    elements: List[Tuple[int, int]] = []

    for s in range(n_spans):
        x0 = s * span_m
        if s == 0:
            support_to_nodes[0] = 0
            nodes_x_m.append(0.0)

        elem_ids: List[int] = []
        for k in range(1, n_div + 1):
            xk = round(x0 + (k / float(n_div)) * span_m, 6)
            n_prev = len(nodes_x_m) - 1
            nodes_x_m.append(xk)
            n_curr = len(nodes_x_m) - 1
            elem_ids.append(len(elements))
            elements.append((n_prev, n_curr))

        support_to_nodes[s + 1] = len(nodes_x_m) - 1
        span_to_elements[s + 1] = elem_ids

    return BridgeGeometryMapping(
        support_to_nodes=support_to_nodes,
        span_to_elements=span_to_elements,
        nodes_x_m=nodes_x_m,
        elements=elements,
    )


def solve_bridge_mesh_hl93(
    span_m: float,
    n_spans: int = 3,
    divisions_per_span: int = 10,
    impact_factor: float = 1.33,
) -> Dict[str, object]:
    """Resuelve la envolvente HL-93 sobre el puente continuo y mapea resultados a la malla."""
    mapping = build_bridge_mesh(span_m, n_spans, divisions_per_span)
    env = envelope_multispan(
        MultiSpanInput(span_m=span_m, n_spans=n_spans, impact_factor=impact_factor)
    )
    env_dict = env.to_dict()
    return {
        "nodes_x_m": mapping.nodes_x_m,
        "elements": [list(e) for e in mapping.elements],
        "geometry_mapping": {
            "support_to_nodes": mapping.support_to_nodes,
            "span_to_elements": mapping.span_to_elements,
        },
        "envelope": env_dict,
    }
