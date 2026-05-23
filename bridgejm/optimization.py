"""
Optimización paramétrica del número de tramos para minimizar costo
de un puente (cepa + tablero), evaluado contra HL-93/Eurocode/AS 5100.
"""
from __future__ import annotations

from dataclasses import dataclass

from .loads.hl93 import HL93Configuration, hl93_influence_envelope


@dataclass(frozen=True)
class SpanOptimizationInput:
    total_length_m: float
    cost_pier_USD_per_unit: float = 250_000
    cost_deck_USD_per_m: float = 8_000     # depende cuadráticamente del span
    cost_deck_exp: float = 1.5             # exponente costo/luz
    span_min_m: float = 15.0
    span_max_m: float = 80.0


@dataclass(frozen=True)
class SpanOptimizationResult:
    optimal_n_spans: int
    optimal_span_m: float
    total_cost_USD: float
    M_design_kNm: float
    candidates: list[tuple[int, float, float]]   # (n_spans, span_m, cost)


def optimize_n_spans(inp: SpanOptimizationInput) -> SpanOptimizationResult:
    L_total = inp.total_length_m
    candidates: list[tuple[int, float, float]] = []
    best: tuple[int, float, float] = (0, 0.0, float("inf"))
    best_M = 0.0
    n_min = max(1, int(L_total / inp.span_max_m))
    n_max = max(n_min + 1, int(L_total / inp.span_min_m) + 1)
    for n in range(n_min, n_max + 1):
        span = L_total / n
        if not (inp.span_min_m <= span <= inp.span_max_m):
            continue
        # Costo cepa: n - 1 pilas internas + 2 estribos (constante)
        pier_cost = (n - 1) * inp.cost_pier_USD_per_unit
        # Costo tablero ∝ L_total · (span)^(exp-1)  (cuadrado de inercia)
        deck_cost = inp.cost_deck_USD_per_m * L_total * (span / 30.0) ** (
            inp.cost_deck_exp - 1
        )
        total = pier_cost + deck_cost
        # Evaluar momento para la luz
        r = hl93_influence_envelope(HL93Configuration(span_m=span))
        candidates.append((n, span, total))
        if total < best[2]:
            best = (n, span, total)
            best_M = r.M_max_kNm

    return SpanOptimizationResult(
        optimal_n_spans=best[0], optimal_span_m=best[1],
        total_cost_USD=best[2], M_design_kNm=best_M,
        candidates=sorted(candidates),
    )


__all__ = ["SpanOptimizationInput", "SpanOptimizationResult", "optimize_n_spans"]
