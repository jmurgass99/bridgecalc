"""
Eurocode LM1 (EN 1991-2) — modelo de carga normal en puentes carreteros.

LM1 = tándem (TS) + uniformly distributed load (UDL).
- TS: 2 ejes × 300 kN (carril 1) / 200 kN (carril 2) / 100 kN (carril 3) ·
  factores α_Q (default 1.0).
- UDL: 9 kN/m² en carril 1, 2.5 kN/m² en demás (factor α_q, default 1.0).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Tabla 4.2 EN 1991-2
TS_AXLES_kN = [300.0, 200.0, 100.0]    # carril 1, 2, 3
UDL_kN_per_m2 = [9.0, 2.5, 2.5]
TANDEM_AXLE_SPACING_m = 1.2
TANDEM_TRANSVERSE_SPACING_m = 2.0
NOTIONAL_LANE_WIDTH_m = 3.0


@dataclass(frozen=True)
class LM1Input:
    carriageway_width_m: float
    span_m: float
    alpha_Q1: float = 1.0
    alpha_q1: float = 1.0
    alpha_qr: float = 1.0   # carriles restantes
    n_lanes: int | None = None  # None = auto desde carriageway_width


@dataclass(frozen=True)
class LM1Result:
    n_lanes: int
    M_TS_kNm: float       # momento del tándem por viga
    M_UDL_kNm: float
    M_total_kNm: float
    V_max_kN: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_lanes": self.n_lanes,
            "M_TS_kNm": self.M_TS_kNm,
            "M_UDL_kNm": self.M_UDL_kNm,
            "M_total_kNm": self.M_total_kNm,
            "V_max_kN": self.V_max_kN,
        }


def evaluate_lm1(inp: LM1Input) -> LM1Result:
    """Envolvente LM1 para viga simple."""
    if inp.span_m <= 0 or inp.carriageway_width_m <= 0:
        raise ValueError("span_m y carriageway_width_m deben ser > 0")
    if inp.n_lanes is None:
        n_lanes = int(min(inp.carriageway_width_m // NOTIONAL_LANE_WIDTH_m, 3))
        n_lanes = max(n_lanes, 1)
    else:
        n_lanes = int(inp.n_lanes)

    # Tándem (suma por carril, todas las cargas centradas en mid-span = max M)
    L = inp.span_m
    M_TS = 0.0
    V_TS_max = 0.0
    for i in range(n_lanes):
        Q = TS_AXLES_kN[min(i, 2)]
        alpha = inp.alpha_Q1 if i == 0 else inp.alpha_qr
        # 2 ejes a 1.2 m de separación → para luz larga ≈ 2·Q
        # M_max = (2Q·L)/8 · (1 - a²/L²) con a = 0.6 m
        M_lane = alpha * 2 * Q * L / 8 * (1 - (0.6 / L) ** 2) if L > 0.6 else \
                 alpha * 2 * Q * L / 8
        M_TS += M_lane
        V_TS_max += alpha * 2 * Q  # cortante max en apoyo

    # UDL
    M_UDL = 0.0
    V_UDL = 0.0
    for i in range(n_lanes):
        q = UDL_kN_per_m2[min(i, 2)]
        alpha = inp.alpha_q1 if i == 0 else inp.alpha_qr
        # Carril 3 m de ancho, viga toma 1 carril
        w = alpha * q * NOTIONAL_LANE_WIDTH_m  # kN/m
        M_UDL += w * L ** 2 / 8
        V_UDL += w * L / 2

    return LM1Result(
        n_lanes=n_lanes,
        M_TS_kNm=M_TS,
        M_UDL_kNm=M_UDL,
        M_total_kNm=M_TS + M_UDL,
        V_max_kN=V_TS_max + V_UDL,
    )


__all__ = ["LM1Input", "LM1Result", "evaluate_lm1"]
