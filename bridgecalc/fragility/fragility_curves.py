"""
Curvas de fragilidad lognormales para cepas RC de puentes.

P(DS >= ds | IM) = Phi[(ln(IM) - ln(IM_median)) / beta]

4 estados de dano:
  - slight     : fisuracion superficial, dano cosmetico
  - moderate   : fluencia del acero, fisuras anchas
  - extensive  : pandeo barras, aplastamiento recubrimiento
  - complete   : perdida de capacidad de carga, colapso

Parametros calibrados segun:
  - Nielson, B. G. (2005). Analytical Fragility Curves for Highway Bridges
    in Moderate Seismic Zones (PhD, Georgia Tech).
  - HAZUS-MH MR5 Technical Manual, FEMA (2020), Table 7-9.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import erf, log, sqrt
from typing import Literal, Sequence

import numpy as np

from .park_ang import FragilityCurve

# ---------------------------------------------------------------
# Parametros HAZUS-MH para cepas RC tipicas (multi-column bent,
# conventional design, puente continuo concreto, clase HWB10).
# IM = Sa(1.0 s) [g].
# ---------------------------------------------------------------
DamageState = Literal["slight", "moderate", "extensive", "complete"]

HAZUS_RC_PIER_PARAMS: dict[DamageState, tuple[float, float]] = {
    "slight":    (0.15, 0.55),   # (median [g], beta)
    "moderate":  (0.30, 0.55),
    "extensive": (0.50, 0.55),
    "complete":  (0.80, 0.55),
}


@dataclass(frozen=True)
class FragilityCurveSet:
    """Conjunto de 4 curvas lognormales, una por estado de dano."""
    slight: FragilityCurve
    moderate: FragilityCurve
    extensive: FragilityCurve
    complete: FragilityCurve

    def probability_all(self, im: float) -> dict[DamageState, float]:
        """P(DS >= ds | IM) para los 4 estados."""
        return {
            "slight": float(self.slight.probability(im)),
            "moderate": float(self.moderate.probability(im)),
            "extensive": float(self.extensive.probability(im)),
            "complete": float(self.complete.probability(im)),
        }


def hazus_rc_pier_fragility(
    params: dict[DamageState, tuple[float, float]] | None = None,
) -> FragilityCurveSet:
    """Crea el conjunto de curvas de fragilidad para cepa RC tipica.

    Parameters
    ----------
    params : dict, optional
        {damage_state: (median_g, beta)}.  Si None usa HAZUS default.
    """
    p = params or HAZUS_RC_PIER_PARAMS
    return FragilityCurveSet(
        slight=FragilityCurve(median=p["slight"][0], beta=p["slight"][1]),
        moderate=FragilityCurve(median=p["moderate"][0], beta=p["moderate"][1]),
        extensive=FragilityCurve(median=p["extensive"][0], beta=p["extensive"][1]),
        complete=FragilityCurve(median=p["complete"][0], beta=p["complete"][1]),
    )


def fragility_probability(im: float, median: float, beta: float) -> float:
    """P(DS >= ds | IM) = Phi[(ln(IM) - ln(median)) / beta].

    Standalone function without requiring a FragilityCurve object.
    """
    if im <= 0 or median <= 0 or beta <= 0:
        raise ValueError("im, median y beta deben ser > 0")
    z = (log(im) - log(median)) / beta
    return 0.5 * (1.0 + erf(z / sqrt(2.0)))


def compute_discrete_damage_probabilities(
    im: float, curves: FragilityCurveSet,
) -> dict[str, float]:
    """Probabilidad discreta de cada estado de dano (sumando = 1.0).

    P(DS=none) = 1 - P(slight)
    P(DS=slight) = P(slight) - P(moderate)
    P(DS=moderate) = P(moderate) - P(extensive)
    P(DS=extensive) = P(extensive) - P(complete)
    P(DS=complete) = P(complete)
    """
    pa = curves.probability_all(im)
    return {
        "none": 1.0 - pa["slight"],
        "slight": pa["slight"] - pa["moderate"],
        "moderate": pa["moderate"] - pa["extensive"],
        "extensive": pa["extensive"] - pa["complete"],
        "complete": pa["complete"],
    }


__all__ = [
    "DamageState",
    "HAZUS_RC_PIER_PARAMS",
    "FragilityCurveSet",
    "hazus_rc_pier_fragility",
    "fragility_probability",
    "compute_discrete_damage_probabilities",
]
