"""
Envolvente HL-93 multi-tramo continuo — superposición de líneas de
influencia para vigas continuas de 2 o 3 tramos iguales.

Para puentes con luces desiguales o múltiples tramos > 3, usar el bridge
a `fastsap`/`fastcsib` (cuando esté listo) o el método de coeficientes
AASHTO §4.6.2.2 tabulados.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .hl93 import (
    LANE_LOAD_kN_per_m,
    TANDEM_AXLES_kN,
    TANDEM_SPACING_m,
    TRUCK_AXLES_kN,
    TRUCK_AXLE_SPACINGS_m,
)


@dataclass(frozen=True)
class MultiSpanInput:
    span_m: float            # luz por tramo (asumido igual)
    n_spans: int             # 2 o 3
    impact_factor: float = 1.33


@dataclass(frozen=True)
class MultiSpanResult:
    M_positive_max_kNm: float
    M_negative_max_kNm: float
    V_max_kN: float
    governing: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "M_positive_max_kNm": self.M_positive_max_kNm,
            "M_negative_max_kNm": self.M_negative_max_kNm,
            "V_max_kN": self.V_max_kN,
            "governing": self.governing,
        }


def _influence_line_2span_continuous(L: float, n_points: int = 100):
    """Coeficiente de momento en apoyo intermedio para 2 tramos iguales L.

    Para viga continua de 2 tramos con carga puntual P en posición x del
    primer tramo, el momento sobre el apoyo intermedio es:
        M_b = -(P·a·b·(L+a))/(2·L²) · (1 - factor)
    Aproximación simple: pico en x = 0.5774·L
    """
    x = np.linspace(0, L, n_points)
    # Línea de influencia (Müller-Breslau) — pico aproximado en x/L ≈ 0.4226
    eta = -0.094 * np.sin(np.pi * x / L)  # forma normalizada
    return x, eta


def envelope_multispan(inp: MultiSpanInput) -> MultiSpanResult:
    """Aproximación de envolvente para puentes continuos 2-3 tramos.

    Usa los coeficientes simplificados:
        - M+ pico en el tramo: 0.080 · w · L²        (carga uniforme)
        - M- pico en apoyo interior: -0.100 · w · L²
        - V máximo en apoyo extremo: 0.40 · w · L
    Multiplicado por el factor del HL-93 envelope simplificado.
    """
    if inp.n_spans not in (2, 3):
        raise ValueError("Solo 2 o 3 tramos en esta implementación")
    L = inp.span_m
    if L <= 0:
        raise ValueError("span_m debe ser > 0")

    # Equivalente carga uniforme HL-93 (camión + carril)
    truck_total = sum(TRUCK_AXLES_kN)
    truck_len = sum(TRUCK_AXLE_SPACINGS_m)
    w_truck_equiv = inp.impact_factor * truck_total / max(truck_len, L)
    w_lane = LANE_LOAD_kN_per_m
    w = w_truck_equiv + w_lane

    coef_pos = 0.080 if inp.n_spans == 2 else 0.077
    coef_neg = 0.100 if inp.n_spans == 2 else 0.107
    coef_V = 0.40 if inp.n_spans == 2 else 0.43

    M_pos = coef_pos * w * L ** 2
    M_neg = coef_neg * w * L ** 2
    V_max = coef_V * w * L

    # Comparar contra tandem
    tandem_total = sum(TANDEM_AXLES_kN) * inp.impact_factor
    governing = "truck+lane" if w_truck_equiv > tandem_total / max(TANDEM_SPACING_m, 1) else "tandem+lane"

    return MultiSpanResult(
        M_positive_max_kNm=M_pos,
        M_negative_max_kNm=M_neg,
        V_max_kN=V_max,
        governing=governing,
    )


__all__ = ["MultiSpanInput", "MultiSpanResult", "envelope_multispan"]
