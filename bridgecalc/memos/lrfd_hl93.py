"""Memoria LRFD HL-93 en Markdown — Strength I paso a paso (AASHTO LRFD 9ª ed.).

Versión ligera (sin LaTeX) de :mod:`bridgecalc.memos.hl93_handcalcs`: momentos de camión y tándem
por el barrido exacto de :func:`bridgecalc.loads.hl93.hl93_envelope`, carril de 9,34 kN/m, IM solo
sobre el vehículo y combinación 1,25·DC + 1,50·DW + 1,75·(LL+IM).

Hasta la versión 1.0 el momento del camión se estimaba con ``145·L/4 − 145·4,3/2`` (L > 12,5 m) o
``0,5·145·L·0,4`` (L ≤ 12,5 m): para L = 30 m daba 776 kN·m frente a los 2058 kN·m del barrido
exacto, el tándem no se consideraba y el carril era 9,3 kN/m.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..loads.hl93 import LANE_LOAD_kN_per_m, hl93_envelope


@dataclass(frozen=True)
class HL93MemoInput:
    L_span_m: float
    n_lanes: int = 2
    DC_kN_m: float = 25.0
    DW_kN_m: float = 5.0
    DLF: float = 1.33               # 1 + IM, solo sobre el vehículo
    MPF: float = 1.0                # factor de presencia múltiple


@dataclass(frozen=True)
class HL93MemoResult:
    M_DC_kNm: float
    M_DW_kNm: float
    M_truck_kNm: float
    M_lane_kNm: float
    M_LL_IM_kNm: float
    M_Strength_I_kNm: float
    markdown: str
    M_tandem_kNm: float = 0.0
    governing_vehicle: str = "truck"


def generar_memoria_hl93(inp: HL93MemoInput) -> HL93MemoResult:
    L = inp.L_span_m
    if L <= 0:
        raise ValueError("L_span_m debe ser > 0")
    M_DC = inp.DC_kN_m * L ** 2 / 8.0
    M_DW = inp.DW_kN_m * L ** 2 / 8.0
    env = hl93_envelope(L, impact_factor=inp.DLF)
    M_truck = float(env["M_truck_kNm"])
    M_tandem = float(env["M_tandem_kNm"])
    governing = "truck" if M_truck >= M_tandem else "tandem"
    M_lane = LANE_LOAD_kN_per_m * L ** 2 / 8.0
    M_LL_IM = (max(M_truck, M_tandem) * inp.DLF + M_lane) * inp.MPF
    M_str = 1.25 * M_DC + 1.50 * M_DW + 1.75 * M_LL_IM
    md = (
        f"# Memoria LRFD HL-93\n\n"
        f"## Datos\nL = {L} m, lanes = {inp.n_lanes}\n\n"
        f"## DC/DW\n- M_DC = {M_DC:.2f} kNm\n- M_DW = {M_DW:.2f} kNm\n\n"
        f"## LL\n- M_truck = {M_truck:.2f} kNm (barrido exacto, ejes 35/145/145 kN a 4,27 m)\n"
        f"- M_tandem = {M_tandem:.2f} kNm (2 x 110 kN a 1,20 m)\n"
        f"- Gobierna: {governing}\n"
        f"- M_lane = {LANE_LOAD_kN_per_m} x L^2/8 = {M_lane:.2f} kNm\n"
        f"- M_LL+IM = (max(M_truck, M_tandem) x {inp.DLF} + M_lane) x MPF = {M_LL_IM:.2f} kNm\n\n"
        f"## Strength I\n- 1.25 DC + 1.50 DW + 1.75 (LL+IM) = {M_str:.2f} kNm\n"
    )
    return HL93MemoResult(M_DC, M_DW, M_truck, M_lane, M_LL_IM, M_str, md, M_tandem, governing)


__all__ = ["HL93MemoInput", "HL93MemoResult", "generar_memoria_hl93"]
