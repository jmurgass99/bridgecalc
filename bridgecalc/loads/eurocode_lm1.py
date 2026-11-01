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


@dataclass(frozen=True)
class EurocodeLM1Input:
    """Datos de entrada para el modelo de carga LM1."""
    carriageway_width_m: float
    span_m: float
    alpha_Q1: float = 1.0     # factor ajuste TS carril 1
    alpha_q1: float = 1.0     # factor ajuste UDL carril 1
    alpha_Qr: float = 1.0     # factor ajuste TS carriles restantes
    alpha_qr: float = 1.0     # factor ajuste UDL carriles restantes
    n_lanes: int | None = None


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
    else:
        n_lanes = max(1, min(int(W // LM1_NOTIONAL_LANE_WIDTH_m), 3))

    total_TS_load = 0.0
    total_UDL_linear = 0.0
    M_TS = 0.0
    V_TS = 0.0
    M_UDL = 0.0
    V_UDL = 0.0

    for i in range(n_lanes):
        # TS per lane
        Q_axle = LM1_TS_AXLE_kN_PER_LANE[min(i, 2)]
        alpha_Q = inp.alpha_Q1 if i == 0 else inp.alpha_Qr
        Q_eff = alpha_Q * Q_axle

        # 2 ejes a 1.2 m separacion. Teorema de la equidistancia (carga y
        # resultante equidistantes del centro de vano) para dos puntuales
        # iguales separadas d: M_max = P*(L-d)/2 + P*d^2/(8L). Centrar el
        # GRUPO en el vano (formula anterior) da un valor CERCANO pero no
        # exacto, y por encima del maximo fisico alcanzable con esas dos
        # cargas -- verificado: para L=30, d=1.2 daba 14.976*P, mas que el
        # maximo real 14.406*P, un exceso del 3.96% (fisicamente imposible).
        # Desde 1.1.0 momento y cortante salen de las mismas funciones que IAP-11 y ec1_traffic:
        #  - L >= (1 + 1/sqrt(2))·d = 2,05 m: Barré, Q·((L − d)/2 + d²/(8L));
        #  - L < 2,05 m: un solo eje centrado, Q·L/4 (antes Q·L/2 para L <= d, el doble, y la
        #    fórmula de dos ejes entre 1,2 y 2,05 m, por debajo del eje único);
        #  - cortante: un eje sobre el apoyo y el otro a d, Q·(2 − d/L) (antes 2Q, con los dos
        #    ejes a la vez sobre el apoyo, físicamente imposible: +2 % en 30 m, +6 % en 20 m).
        d = LM1_TS_AXLE_SPACING_m
        M_ts_lane = tandem_bending_moment_barre(Q_eff, L, d)

        M_TS += M_ts_lane
        V_TS += tandem_shear_force_support(Q_eff, L, d)
        total_TS_load += 2.0 * Q_eff

        # UDL per lane
        q = LM1_UDL_kN_per_m2_PER_LANE[min(i, 2)]
        alpha_q = inp.alpha_q1 if i == 0 else inp.alpha_qr
        w = alpha_q * q * LM1_NOTIONAL_LANE_WIDTH_m  # kN/m
        M_UDL += w * L ** 2 / 8.0
        V_UDL += w * L / 2.0
        total_UDL_linear += w

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
    "LM1_TS_AXLE_kN_PER_LANE", "LM1_UDL_kN_per_m2_PER_LANE",
    "LM2_AXLE_LOAD_kN",
]
