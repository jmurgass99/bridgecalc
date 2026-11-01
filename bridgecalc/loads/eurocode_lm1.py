"""
Eurocode EN 1991-2 — Load Model 1 (LM1) y Load Model 2 (LM2).

LM1 — carga normal:
  - TS (Tandem System): 2 ejes por carril
    * Carril 1: 2 x 300 kN (alpha_Q1)
    * Carril 2: 2 x 200 kN
    * Carril 3: 2 x 100 kN
  - UDL (Uniformly Distributed Load):
    * Carril 1: 9 kN/m^2 (alpha_q1)
    * Demas: 2.5 kN/m^2

LM2 — eje simple:
  - Eje aislado de 400 kN (2 ruedas x 200 kN)
  - Aplicable para verificaciones locales (punzonamiento, losas)
  - Huella de rueda: 0.35 x 0.60 m
  - Separacion transversal de ruedas: 2.0 m

Referencia: EN 1991-2:2003, Tables 4.2, 4.3, 4.4.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .iap11 import tandem_bending_moment_barre, tandem_shear_force_support

# ---------------------------------------------------------------
# LM1 constantes (EN 1991-2 Table 4.2)
# ---------------------------------------------------------------
LM1_TS_AXLE_kN_PER_LANE = [300.0, 200.0, 100.0]  # carril 1, 2, 3+
LM1_UDL_kN_per_m2_PER_LANE = [9.0, 2.5, 2.5]
LM1_REMAINING_AREA_UDL_kN_per_m2 = 2.5
LM1_TS_AXLE_SPACING_m = 1.2
LM1_TS_TRANSVERSE_SPACING_m = 2.0
LM1_NOTIONAL_LANE_WIDTH_m = 3.0

# ---------------------------------------------------------------
# LM2 constantes (EN 1991-2 ss4.3.3)
# ---------------------------------------------------------------
LM2_AXLE_LOAD_kN = 400.0       # eje simple total
LM2_WHEEL_LOAD_kN = 200.0      # por rueda
LM2_WHEEL_CONTACT_m = (0.35, 0.60)   # ancho x largo
LM2_WHEEL_SPACING_m = 2.0       # transversal


def notional_lanes_en1991_2(carriageway_width_m: float) -> tuple[int, float, float]:
    """División de la calzada en carriles teóricos según EN 1991-2 Tabla 4.1.

    Parameters
    ----------
    carriageway_width_m : ancho de calzada ``w`` [m]

    Returns
    -------
    (n_lanes, lane_width_m, remaining_area_width_m)
        - ``w < 5.4 m``       : ``n_1 = 1``, ``w_l = 3.0 m`` (o ``w`` si ``w < 3.0 m``), resto ``max(0, w - 3.0)``
        - ``5.4 m <= w < 6.0 m`` : ``n_1 = 2``, ``w_l = w / 2``, resto ``0.0``
        - ``w >= 6.0 m``      : ``n_1 = int(w // 3.0)``, ``w_l = 3.0 m``, resto ``w - 3.0 * n_1``
    """
    w = float(carriageway_width_m)
    if w <= 0.0:
        raise ValueError("carriageway_width_m debe ser > 0")
    if w < 5.4:
        w_l = min(w, LM1_NOTIONAL_LANE_WIDTH_m)
        return 1, w_l, max(0.0, w - w_l)
    if w < 6.0:
        return 2, w / 2.0, 0.0
    n_1 = int(w // LM1_NOTIONAL_LANE_WIDTH_m)
    rem = w - n_1 * LM1_NOTIONAL_LANE_WIDTH_m
    return n_1, LM1_NOTIONAL_LANE_WIDTH_m, max(0.0, rem)


@dataclass(frozen=True)
class EurocodeLM1Input:
    """Datos de entrada para el modelo de carga LM1."""
    carriageway_width_m: float
    span_m: float
    alpha_Q1: float = 1.0     # factor ajuste TS carril 1
    alpha_q1: float = 1.0     # factor ajuste UDL carril 1
    alpha_Qr: float = 1.0     # factor ajuste TS carriles restantes
    alpha_qr: float = 1.0     # factor ajuste UDL carriles restantes y área restante
    n_lanes: int | None = None
    include_remaining_area: bool = False  # si True, suma q_rk = 2.5 kN/m² sobre el área restante a M_UDL y V_UDL
    use_table_4_1_lanes: bool = False     # si True, aplica EN 1991-2 Tabla 4.1 (incl. tramo 5.4 <= w < 6.0 m y n_1 > 3)


@dataclass(frozen=True)
class EurocodeLM1Result:
    """Resultado de la envolvente LM1."""
    n_lanes: int
    M_TS_kNm: float           # momento tandem system
    M_UDL_kNm: float          # momento carga uniforme
    M_total_kNm: float
    V_TS_kN: float
    V_UDL_kN: float
    V_total_kN: float
    total_TS_load_kN: float    # carga total del tandem
    total_UDL_load_kN_per_m: float  # carga total lineal
    lane_width_m: float = 3.0
    remaining_area_width_m: float = 0.0
    remaining_UDL_load_kN_per_m: float = 0.0
    M_remaining_kNm: float = 0.0
    V_remaining_kN: float = 0.0
    M_total_with_remaining_kNm: float = 0.0
    V_total_with_remaining_kN: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_lanes": self.n_lanes,
            "M_TS_kNm": self.M_TS_kNm,
            "M_UDL_kNm": self.M_UDL_kNm,
            "M_total_kNm": self.M_total_kNm,
            "V_TS_kN": self.V_TS_kN,
            "V_UDL_kN": self.V_UDL_kN,
            "V_total_kN": self.V_total_kN,
            "total_TS_load_kN": self.total_TS_load_kN,
            "total_UDL_load_kN_per_m": self.total_UDL_load_kN_per_m,
            "lane_width_m": self.lane_width_m,
            "remaining_area_width_m": self.remaining_area_width_m,
            "remaining_UDL_load_kN_per_m": self.remaining_UDL_load_kN_per_m,
            "M_remaining_kNm": self.M_remaining_kNm,
            "V_remaining_kN": self.V_remaining_kN,
            "M_total_with_remaining_kNm": self.M_total_with_remaining_kNm,
            "V_total_with_remaining_kN": self.V_total_with_remaining_kN,
        }


@dataclass(frozen=True)
class EurocodeLM2Input:
    """Datos de entrada para el modelo de carga LM2."""
    span_m: float
    beta_Q: float = 1.0   # factor de ajuste nacional (NAD)


@dataclass(frozen=True)
class EurocodeLM2Result:
    """Resultado LM2."""
    axle_load_kN: float
    M_max_kNm: float
    V_max_kN: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "axle_load_kN": self.axle_load_kN,
            "M_max_kNm": self.M_max_kNm,
            "V_max_kN": self.V_max_kN,
        }


def evaluate_eurocode_lm1(inp: EurocodeLM1Input) -> EurocodeLM1Result:
    """Envolvente LM1 para viga simple.

    AASHTO-like procedure: max M y V considerando TS + UDL por carriles.
    """
    L = inp.span_m
    W = inp.carriageway_width_m
    if L <= 0 or W <= 0:
        raise ValueError("span_m y carriageway_width_m deben ser > 0")

    if inp.n_lanes is not None:
        n_lanes = int(inp.n_lanes)
        lane_width_m = LM1_NOTIONAL_LANE_WIDTH_m if W >= n_lanes * LM1_NOTIONAL_LANE_WIDTH_m else (W / n_lanes)
        rem_width_m = max(0.0, W - n_lanes * lane_width_m)
    elif inp.use_table_4_1_lanes:
        n_lanes, lane_width_m, rem_width_m = notional_lanes_en1991_2(W)
    else:
        n_lanes = max(1, min(int(W // LM1_NOTIONAL_LANE_WIDTH_m), 3))
        lane_width_m = LM1_NOTIONAL_LANE_WIDTH_m
        rem_width_m = max(0.0, W - n_lanes * lane_width_m)

    total_TS_load = 0.0
    total_UDL_linear = 0.0
    M_TS = 0.0
    V_TS = 0.0
    M_UDL = 0.0
    V_UDL = 0.0

    for i in range(n_lanes):
        # TS per lane (EN 1991-2 Table 4.2: solo carriles 1, 2 y 3 tienen TS)
        Q_axle = LM1_TS_AXLE_kN_PER_LANE[i] if i < 3 else 0.0
        alpha_Q = inp.alpha_Q1 if i == 0 else inp.alpha_Qr
        Q_eff = alpha_Q * Q_axle

        d = LM1_TS_AXLE_SPACING_m
        M_ts_lane = tandem_bending_moment_barre(Q_eff, L, d) if Q_eff > 0.0 else 0.0

        M_TS += M_ts_lane
        V_TS += tandem_shear_force_support(Q_eff, L, d) if Q_eff > 0.0 else 0.0
        total_TS_load += 2.0 * Q_eff

        # UDL per lane
        q = LM1_UDL_kN_per_m2_PER_LANE[min(i, 2)]
        alpha_q = inp.alpha_q1 if i == 0 else inp.alpha_qr
        w = alpha_q * q * lane_width_m  # kN/m
        M_UDL += w * L ** 2 / 8.0
        V_UDL += w * L / 2.0
        total_UDL_linear += w

    # Área restante (EN 1991-2 Tabla 4.2: q_rk = 2.5 kN/m² con factor alpha_qr)
    w_rem = inp.alpha_qr * LM1_REMAINING_AREA_UDL_kN_per_m2 * rem_width_m
    M_rem = w_rem * L ** 2 / 8.0
    V_rem = w_rem * L / 2.0

    if inp.include_remaining_area:
        M_UDL += M_rem
        V_UDL += V_rem
        total_UDL_linear += w_rem

    return EurocodeLM1Result(
        n_lanes=n_lanes,
        M_TS_kNm=M_TS,
        M_UDL_kNm=M_UDL,
        M_total_kNm=M_TS + M_UDL,
        V_TS_kN=V_TS,
        V_UDL_kN=V_UDL,
        V_total_kN=V_TS + V_UDL,
        total_TS_load_kN=total_TS_load,
        total_UDL_load_kN_per_m=total_UDL_linear,
        lane_width_m=lane_width_m,
        remaining_area_width_m=rem_width_m,
        remaining_UDL_load_kN_per_m=w_rem,
        M_remaining_kNm=M_rem,
        V_remaining_kN=V_rem,
        M_total_with_remaining_kNm=M_TS + M_UDL + (0.0 if inp.include_remaining_area else M_rem),
        V_total_with_remaining_kN=V_TS + V_UDL + (0.0 if inp.include_remaining_area else V_rem),
    )


def evaluate_eurocode_lm2(inp: EurocodeLM2Input) -> EurocodeLM2Result:
    """Envolvente LM2 para verificacion local — eje unico de 400 kN.

    El eje se posiciona en el centro de la luz para max M, y en el
    apoyo para max V.
    """
    L = inp.span_m
    if L <= 0:
        raise ValueError("span_m debe ser > 0")

    Q = LM2_AXLE_LOAD_kN * inp.beta_Q
    # M_max en midspan
    M_max = Q * L / 4.0
    # V_max en apoyo
    V_max = Q

    return EurocodeLM2Result(
        axle_load_kN=Q,
        M_max_kNm=M_max,
        V_max_kN=V_max,
    )


__all__ = [
    "EurocodeLM1Input", "EurocodeLM1Result", "evaluate_eurocode_lm1",
    "EurocodeLM2Input", "EurocodeLM2Result", "evaluate_eurocode_lm2",
    "notional_lanes_en1991_2",
    "LM1_TS_AXLE_kN_PER_LANE", "LM1_UDL_kN_per_m2_PER_LANE",
    "LM1_REMAINING_AREA_UDL_kN_per_m2",
    "LM2_AXLE_LOAD_kN",
]
