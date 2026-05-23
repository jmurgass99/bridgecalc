"""Memoria handcalcs - Puente LRFD HL-93 paso a paso (AASHTO LRFD 9th ed.)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HL93MemoInput:
    L_span_m: float
    n_lanes: int = 2
    DC_kN_m: float = 25.0
    DW_kN_m: float = 5.0
    DLF: float = 1.33               # impact factor
    MPF: float = 1.0                # multiple presence


@dataclass(frozen=True)
class HL93MemoResult:
    M_DC_kNm: float
    M_DW_kNm: float
    M_truck_kNm: float
    M_lane_kNm: float
    M_LL_IM_kNm: float
    M_Strength_I_kNm: float
    markdown: str


def generar_memoria_hl93(inp: HL93MemoInput) -> HL93MemoResult:
    L = inp.L_span_m
    M_DC = inp.DC_kN_m * L ** 2 / 8.0
    M_DW = inp.DW_kN_m * L ** 2 / 8.0
    # Camion HL-93: ejes 35-145-145 kN @ 4.3 m + (4.3-9.0)
    # Aproximacion simple para luz simple <30m: M_truck = (145*L/4 - 145*4.3/4*2)
    if L <= 12.5:
        M_truck = 0.5 * 145 * L * 0.4
    else:
        M_truck = (145.0 * L / 4.0) - (145.0 * 4.3) / 2.0
    M_lane = 9.3 * L ** 2 / 8.0    # carril 9.3 kN/m
    M_LL_IM = (M_truck * inp.DLF + M_lane) * inp.MPF
    M_str = 1.25 * M_DC + 1.50 * M_DW + 1.75 * M_LL_IM
    md = (
        f"# Memoria LRFD HL-93\n\n"
        f"## Datos\nL = {L} m, lanes = {inp.n_lanes}\n\n"
        f"## DC/DW\n- M_DC = {M_DC:.2f} kNm\n- M_DW = {M_DW:.2f} kNm\n\n"
        f"## LL\n- M_truck = {M_truck:.2f} kNm\n- M_lane = {M_lane:.2f} kNm\n"
        f"- M_LL+IM = (M_truck*1.33 + M_lane) * MPF = {M_LL_IM:.2f} kNm\n\n"
        f"## Strength I\n- 1.25 DC + 1.50 DW + 1.75 (LL+IM) = {M_str:.2f} kNm\n"
    )
    return HL93MemoResult(M_DC, M_DW, M_truck, M_lane, M_LL_IM, M_str, md)


__all__ = ["HL93MemoInput", "HL93MemoResult", "generar_memoria_hl93"]
