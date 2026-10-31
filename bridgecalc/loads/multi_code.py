"""
Cargas vivas vehiculares multi-código.

Códigos:
    US:   AASHTO LRFD HL-93 (ya en `hl93.py`)
    EU:   EN 1991-2 LM1 (ya en `eurocode.py`)
    SG:   SS EN 1991-2 (idéntico EU con NA)
    AU:   AS 5100.2 — SM1600 + W80 + A160
    CO:   NSR-10 / INVIAS C-95 (camión CC-14 / CC-40)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# --- AS 5100.2 SM1600 (Australia/NZ) ---
SM1600_AXLES_kN = [60.0, 60.0, 80.0, 80.0, 80.0, 80.0]   # 6 ejes triaxle
SM1600_SPACINGS_m = [3.75, 1.20, 6.25, 1.20, 1.20]
SM1600_UDL_kN_per_m = 6.0


@dataclass(frozen=True)
class AS5100Input:
    span_m: float
    n_lanes: int = 1
    impact_factor: float = 1.30          # AS 5100.2 §6


@dataclass(frozen=True)
class AS5100Result:
    M_max_kNm: float
    V_max_kN: float
    governing: str


def evaluate_as5100(inp: AS5100Input) -> AS5100Result:
    L = inp.span_m
    if L <= 0:
        raise ValueError("span_m debe ser > 0")
    # SM1600 simplificado para viga simple: 0.130·W·L (M_max envolvente)
    # W = (60+60+80+80+80+80) = 440 kN
    W_truck = sum(SM1600_AXLES_kN)
    M_truck = inp.impact_factor * 0.130 * W_truck * L * inp.n_lanes
    M_udl = SM1600_UDL_kN_per_m * L * L / 8 * inp.n_lanes
    M_total = M_truck + M_udl
    V_truck = inp.impact_factor * W_truck * inp.n_lanes
    V_udl = SM1600_UDL_kN_per_m * L / 2 * inp.n_lanes
    return AS5100Result(
        M_max_kNm=M_total, V_max_kN=V_truck + V_udl,
        governing="SM1600 + UDL",
    )


# --- NSR-10 / INVIAS C-95 (Colombia) ---
CC40_AXLES_kN = [40.0, 160.0, 160.0]
CC40_SPACINGS_m = [4.0, 1.2]
CC40_LANE_LOAD_kN_per_m = 9.0


@dataclass(frozen=True)
class CC40Input:
    span_m: float
    impact_factor: float = 1.33          # NSR-10 puentes


def evaluate_cc40(inp: CC40Input) -> dict[str, float]:
    """Camión CC-40 (también CC-14 en zonas urbanas)."""
    L = inp.span_m
    if L <= 0:
        raise ValueError("span_m debe ser > 0")
    W = sum(CC40_AXLES_kN)
    M_truck = inp.impact_factor * W * L / 5.5  # aproximación envelope simple
    M_lane = CC40_LANE_LOAD_kN_per_m * L * L / 8
    return {
        "M_truck_kNm": M_truck,
        "M_lane_kNm": M_lane,
        "M_total_kNm": M_truck + M_lane,
        "V_max_kN": inp.impact_factor * W + CC40_LANE_LOAD_kN_per_m * L / 2,
    }


__all__ = [
    "AS5100Input", "AS5100Result", "evaluate_as5100",
    "CC40Input", "evaluate_cc40",
]
