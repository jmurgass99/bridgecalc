"""
Combinaciones de carga y estados límite — AASHTO LRFD §3.4.1 (Tabla 3.4.1-1).

Cubre TODOS los estados límite del LRFD (no solo Strength I): Strength I-V,
Service I-IV, Fatigue I-II y Extreme Event I-II, con los factores de carga γ por
componente. Las cargas permanentes (DC, DW) usan factor máximo/mínimo (γp) según
si su efecto es desfavorable o favorable.

Notación de componentes (LRFD §3.3.2):
  DC  peso propio estructural        DW  superficie de rodadura/servicios
  LL  carga viva vehicular           IM  incremento dinámico (se aplica a LL)
  WS  viento sobre estructura        WL  viento sobre carga viva
  EQ  sismo                          BR  frenado    CT/CV  colisión
  TU  temperatura uniforme           SE  asentamiento
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal, Mapping

# Factores γ por estado límite. Para DC/DW se da (máx, mín). LL incluye IM.
# En AASHTO LRFD 7ª ed. Tabla 3.4.1-1: WS = 1.40 en Strength_III y 0.40 en Strength_V.
# En AASHTO LRFD 8ª/9ª ed. Tabla 3.4.1-1 (con mapas de viento a nivel último MRI 700 años):
# WS = 1.00 en Strength_III y 1.00 en Strength_V (para 55 mph).
_GAMMA_P_DC = (1.25, 0.90)
_GAMMA_P_DW = (1.50, 0.65)

LOAD_COMBINATIONS: Dict[str, Dict[str, float]] = {
    "Strength_I":   {"DC": _GAMMA_P_DC, "DW": _GAMMA_P_DW, "LL": 1.75, "BR": 1.75, "WA": 1.00},
    "Strength_II":  {"DC": _GAMMA_P_DC, "DW": _GAMMA_P_DW, "LL": 1.35, "BR": 1.35, "WA": 1.00},
    "Strength_III": {"DC": _GAMMA_P_DC, "DW": _GAMMA_P_DW, "LL": 0.00, "WS": 1.40, "WA": 1.00},
    "Strength_IV":  {"DC": (1.50, 0.90), "DW": (1.50, 0.65), "LL": 0.00, "WA": 1.00},
    "Strength_V":   {"DC": _GAMMA_P_DC, "DW": _GAMMA_P_DW, "LL": 1.35, "WS": 0.40, "WL": 1.00, "WA": 1.00},
    "Service_I":    {"DC": 1.00, "DW": 1.00, "LL": 1.00, "WS": 0.30, "WL": 1.00, "WA": 1.00},
    "Service_II":   {"DC": 1.00, "DW": 1.00, "LL": 1.30, "WA": 1.00},
    "Service_III":  {"DC": 1.00, "DW": 1.00, "LL": 0.80, "WA": 1.00},
    "Service_IV":   {"DC": 1.00, "DW": 1.00, "LL": 0.00, "WS": 0.70, "WA": 1.00},
    "Fatigue_I":    {"LL": 1.75},
    "Fatigue_II":   {"LL": 0.80},
    "Extreme_I":    {"DC": _GAMMA_P_DC, "DW": _GAMMA_P_DW, "LL": 0.50, "EQ": 1.00, "WA": 1.00},
    "Extreme_II":   {"DC": _GAMMA_P_DC, "DW": _GAMMA_P_DW, "LL": 0.50, "CT": 1.00, "CV": 1.00, "WA": 1.00},
}

LOAD_COMBINATIONS_LRFD_9TH: Dict[str, Dict[str, float]] = {
    **LOAD_COMBINATIONS,
    "Strength_III": {"DC": _GAMMA_P_DC, "DW": _GAMMA_P_DW, "LL": 0.00, "WS": 1.00, "WA": 1.00},
    "Strength_V":   {"DC": _GAMMA_P_DC, "DW": _GAMMA_P_DW, "LL": 1.35, "WS": 1.00, "WL": 1.00, "WA": 1.00},
    "Service_I":    {"DC": 1.00, "DW": 1.00, "LL": 1.00, "WS": 1.00, "WL": 1.00, "WA": 1.00},
    "Service_IV":   {"DC": 1.00, "DW": 1.00, "LL": 0.00, "WS": 1.00, "WA": 1.00},
}


@dataclass(frozen=True)
class CombinationResult:
    limit_state: str
    factored_effect: float
    contributions: Dict[str, float]


def gamma(
    limit_state: str,
    load: str,
    favorable: bool = False,
    edition: Literal["7th", "9th"] = "7th",
) -> float:
    """Factor de carga γ para (estado límite, componente). ``favorable`` usa el γp mínimo (DC/DW)."""
    table = LOAD_COMBINATIONS_LRFD_9TH if edition == "9th" else LOAD_COMBINATIONS
    ls = table.get(limit_state)
    if ls is None:
        raise ValueError("estado límite desconocido: %s (válidos: %s)" % (limit_state, sorted(table)))
    g = ls.get(load, 0.0)
    if isinstance(g, tuple):
        return g[1] if favorable else g[0]
    return g


def factored_effect(
    limit_state: str,
    effects: Mapping[str, float],
    favorable_permanent: bool = False,
    edition: Literal["7th", "9th"] = "7th",
) -> CombinationResult:
    """Efecto factorizado Σ γ_i·Q_i para un estado límite.

    Args:
        limit_state: clave de LOAD_COMBINATIONS (p.ej. "Strength_I").
        effects: efectos sin factorizar por componente, p.ej. {"DC":100,"DW":20,"LL":80}.
            LL debe venir ya con IM incluido (el incremento dinámico se aplica a LL).
        favorable_permanent: si las cargas permanentes son favorables (usa γp mínimo).
        edition: edición de AASHTO LRFD ("7th" con WS=1.40 o "9th" con WS=1.00).

    Returns:
        CombinationResult con el efecto total y la contribución por componente.
    """
    contrib: Dict[str, float] = {}
    for load, q in effects.items():
        g = gamma(limit_state, load, favorable=favorable_permanent, edition=edition)
        contrib[load] = g * q
    return CombinationResult(limit_state, sum(contrib.values()), contrib)


def governing_strength(
    effects: Mapping[str, float],
    edition: Literal["7th", "9th"] = "7th",
) -> CombinationResult:
    """Devuelve la combinación de RESISTENCIA gobernante (mayor efecto factorizado)."""
    table = LOAD_COMBINATIONS_LRFD_9TH if edition == "9th" else LOAD_COMBINATIONS
    strengths = [k for k in table if k.startswith("Strength")]
    results = [factored_effect(k, effects, edition=edition) for k in strengths]
    return max(results, key=lambda r: r.factored_effect)


__all__ = [
    "LOAD_COMBINATIONS", "LOAD_COMBINATIONS_LRFD_9TH", "CombinationResult", "gamma",
    "factored_effect", "governing_strength",
]
