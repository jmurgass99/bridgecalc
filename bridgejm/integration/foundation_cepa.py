"""Bridge BridgeJm -> FoundationDesignJm: diseno cimiento de cepa."""
from __future__ import annotations

import warnings
from dataclasses import dataclass


@dataclass(frozen=True)
class CepaFoundationInput:
    N_kN: float
    M_kNm: float
    V_kN: float
    D_cepa_m: float
    n_piles: int = 6
    pile_D_m: float = 1.0
    pile_L_m: float = 20.0


@dataclass(frozen=True)
class CepaFoundationResult:
    Q_pile_max_kN: float
    Q_pile_min_kN: float
    cumple: bool


def disenar_cimiento_cepa(inp: CepaFoundationInput) -> CepaFoundationResult:
    # patron de pilotes circular con n_piles
    import math
    R = max(1.5, inp.D_cepa_m * 0.8)
    sum_y2 = 0.0
    for i in range(inp.n_piles):
        theta = 2 * math.pi * i / inp.n_piles
        y = R * math.sin(theta)
        sum_y2 += y ** 2
    Q_avg = inp.N_kN / inp.n_piles
    delta_Q = inp.M_kNm * R / sum_y2 if sum_y2 > 0 else 0
    Q_max = Q_avg + delta_Q
    Q_min = Q_avg - delta_Q
    try:
        from foundationdesignjm.analysis.pile_capacity import pile_axial_capacity
        cap = pile_axial_capacity(D=inp.pile_D_m, L=inp.pile_L_m)
    except Exception:
        warnings.warn("FoundationDesignJm no disponible - usando estimacion")
        cap = 0.5 * 1000 * inp.pile_D_m ** 2 * inp.pile_L_m
    return CepaFoundationResult(Q_max, Q_min, Q_max <= cap and Q_min > -0.2 * cap)


__all__ = ["CepaFoundationInput", "CepaFoundationResult", "disenar_cimiento_cepa"]
