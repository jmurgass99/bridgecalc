from __future__ import annotations

import pytest
from bridgecalc.geometry_mapping import build_bridge_mesh, solve_bridge_mesh_hl93


def test_bridge_geometry_mapping_and_hl93_envelope():
    m = build_bridge_mesh(span_m=30.0, n_spans=3, divisions_per_span=8)
    assert len(m.nodes_x_m) == 3 * 8 + 1
    assert len(m.elements) == 24
    assert m.support_to_nodes[0] == 0
    assert m.support_to_nodes[1] == 8
    assert m.support_to_nodes[2] == 16
    assert m.support_to_nodes[3] == 24
    assert len(m.span_to_elements[2]) == 8

    res = solve_bridge_mesh_hl93(span_m=30.0, n_spans=3, divisions_per_span=8)
    assert res["envelope"]["M_positive_max_kNm"] > 1000.0
    assert abs(res["envelope"]["M_negative_max_kNm"]) > 500.0
