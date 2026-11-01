"""Tests de las mejoras de ingeniería en bridgecalc:
- Línea de influencia exacta de reacciones en apoyos de vigas continuas y equilibrio Σ R_i(x) = 1.
- Envolvente de reacciones en apoyos (incl. 90% de 2 camiones en pilas interiores y levantamiento/uplift).
- Carriles teóricos EN 1991-2 Tabla 4.1 (incl. 5.4 <= w < 6.0 m) y carga uniforme en área restante.
- Combinaciones EN 1990 Anexo A2 para puentes (γ_Q = 1.35 para tráfico, ψ de Tabla A2.1).
- Combinaciones AASHTO LRFD 9ª ed. (WS = 1.00 en Strength III y V).
"""
from __future__ import annotations

import numpy as np
import pytest

from bridgecalc.loads.en1990_combinations import (
    GAMMA_Q_BRIDGE_TRAFFIC,
    VariableAction,
    uls_bridge_strength,
)
from bridgecalc.loads.eurocode_lm1 import (
    EurocodeLM1Input,
    evaluate_eurocode_lm1,
    notional_lanes_en1991_2,
)
from bridgecalc.loads.influence_lines import influence_line_reaction_continuous
from bridgecalc.loads.load_combinations import factored_effect, gamma
from bridgecalc.loads.multispan import MultiSpanInput, envelope_multispan


def test_reaction_influence_line_partition_of_unity_and_exact_two_span():
    spans = [30.0, 30.0]
    ils = [influence_line_reaction_continuous(spans, i, n_points=100) for i in range(3)]
    total_r = ils[0].ordinates + ils[1].ordinates + ils[2].ordinates
    np.testing.assert_allclose(total_r, np.ones_like(total_r), atol=1e-12)

    # En x = L/2 = 15 m de una viga simétrica de 2 vanos:
    # R_0 = 13/32, R_1 = 22/32 = 11/16, R_2 = -3/32
    r0_mid = float(np.interp(15.0, ils[0].x_m, ils[0].ordinates))
    r1_mid = float(np.interp(15.0, ils[1].x_m, ils[1].ordinates))
    r2_mid = float(np.interp(15.0, ils[2].x_m, ils[2].ordinates))
    assert r0_mid == pytest.approx(13.0 / 32.0, rel=1e-4)
    assert r1_mid == pytest.approx(22.0 / 32.0, rel=1e-4)
    assert r2_mid == pytest.approx(-3.0 / 32.0, rel=1e-4)


def test_multispan_reactions_and_uplift():
    res = envelope_multispan(MultiSpanInput(span_m=30.0, n_spans=2))
    assert len(res.reactions) == 3
    # Apoyo interior (índice 1) gobierna la reacción máxima y supera el cortante de una cara
    assert res.R_max_kN == pytest.approx(res.reactions[1]["R_max_kN"])
    assert res.R_max_kN > res.V_max_kN
    # En los estribos (índices 0 y 2) existe levantamiento (reacción mínima negativa) cuando se carga el vano opuesto
    assert res.R_min_uplift_kN < 0.0
    assert res.reactions[0]["R_min_kN"] < 0.0


def test_notional_lanes_table_4_1_and_remaining_area():
    assert notional_lanes_en1991_2(4.5) == (1, 3.0, 1.5)
    n, w_l, rem = notional_lanes_en1991_2(5.6)
    assert n == 2
    assert w_l == pytest.approx(2.8)
    assert rem == pytest.approx(0.0)
    n3, w_l3, rem3 = notional_lanes_en1991_2(11.0)
    assert (n3, w_l3, rem3) == (3, 3.0, 2.0)

    r_no_rem = evaluate_eurocode_lm1(
        EurocodeLM1Input(carriageway_width_m=11.0, span_m=20.0, include_remaining_area=False)
    )
    r_with_rem = evaluate_eurocode_lm1(
        EurocodeLM1Input(carriageway_width_m=11.0, span_m=20.0, include_remaining_area=True)
    )
    # Área restante = 2.0 m * 2.5 kN/m² = 5.0 kN/m -> M_rem = 5 * 20² / 8 = 250 kN·m
    assert r_no_rem.remaining_area_width_m == pytest.approx(2.0)
    assert r_no_rem.M_remaining_kNm == pytest.approx(250.0)
    assert r_with_rem.M_total_kNm == pytest.approx(r_no_rem.M_total_kNm + 250.0)
    assert r_no_rem.M_total_with_remaining_kNm == pytest.approx(r_with_rem.M_total_kNm)


def test_en1990_annex_a2_bridge_combinations():
    perm = {"G1": 1000.0}
    actions = [
        VariableAction("LM1_TS", 500.0, category="traffic_gr1a_ts"),
        VariableAction("Wind", 100.0, category="wind_bridge"),
    ]
    assert actions[0].effective_gamma_Q() == pytest.approx(GAMMA_Q_BRIDGE_TRAFFIC)
    # Cuando LM1_TS lidera: 1.35*1000 + 1.35*500 + 1.50*0.6*100 = 1350 + 675 + 90 = 2115
    u = uls_bridge_strength(perm, actions, expression="6.10")
    assert u == pytest.approx(2115.0)


def test_aashto_lrfd_9th_edition_wind_factors():
    assert gamma("Strength_III", "WS", edition="7th") == pytest.approx(1.40)
    assert gamma("Strength_III", "WS", edition="9th") == pytest.approx(1.00)
    assert gamma("Strength_V", "WS", edition="9th") == pytest.approx(1.00)
    res9 = factored_effect("Strength_III", {"DC": 100.0, "WS": 50.0}, edition="9th")
    assert res9.factored_effect == pytest.approx(1.25 * 100.0 + 1.00 * 50.0)
