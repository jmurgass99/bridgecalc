"""
Eurocode LM1 (EN 1991-2) — modelo de carga normal en puentes carreteros.

LM1 = tándem (TS) + uniformly distributed load (UDL).
- TS: 2 ejes × 300 kN (carril 1) / 200 kN (carril 2) / 100 kN (carril 3) ·
  factores α_Q (default 1.0).
- UDL: 9 kN/m² en carril 1, 2.5 kN/m² en demás (factor α_q, default 1.0).
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

from .eurocode_lm1 import EurocodeLM1Input, evaluate_eurocode_lm1

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
    """Envolvente LM1 para viga simple (módulo de compatibilidad; obsoleto).

    Delega en :func:`bridgecalc.loads.eurocode_lm1.evaluate_eurocode_lm1`. Hasta la versión 1.0 el
    momento del tándem se calculaba como ``2·Q·L/8·(1 − (0,6/L)²)``, que es la fórmula de una carga
    REPARTIDA aplicada a dos cargas puntuales: para L = 30 m y dos carriles daba M_TS = 3748 kN·m
    frente a los 7203 kN·m del teorema de Barré (−48 %, del lado inseguro). ``alpha_qr`` se aplica al
    tándem y a la carga repartida de los carriles restantes, como hacía este módulo.
    """
    warnings.warn(
        "bridgecalc.loads.eurocode.evaluate_lm1 está obsoleto: usa "
        "bridgecalc.loads.eurocode_lm1.evaluate_eurocode_lm1",
        DeprecationWarning, stacklevel=2,
    )
    if inp.span_m <= 0 or inp.carriageway_width_m <= 0:
        raise ValueError("span_m y carriageway_width_m deben ser > 0")
    r = evaluate_eurocode_lm1(EurocodeLM1Input(
        carriageway_width_m=inp.carriageway_width_m,
        span_m=inp.span_m,
        alpha_Q1=inp.alpha_Q1,
        alpha_q1=inp.alpha_q1,
        alpha_Qr=inp.alpha_qr,
        alpha_qr=inp.alpha_qr,
        n_lanes=inp.n_lanes,
    ))
    return LM1Result(
        n_lanes=r.n_lanes,
        M_TS_kNm=r.M_TS_kNm,
        M_UDL_kNm=r.M_UDL_kNm,
        M_total_kNm=r.M_total_kNm,
        V_max_kN=r.V_total_kN,
    )


__all__ = ["LM1Input", "LM1Result", "evaluate_lm1"]
