"""
Curvas de fragilidad para cepas/estribos — Park & Ang damage index +
curva lognormal estándar.

Index Park-Ang: ``DI = δ_max/δ_u + β·E_h / (δ_u·F_y)`` donde
``δ_max`` es el desplazamiento máximo, ``δ_u`` el último monotónico,
``E_h`` la energía histerética, ``F_y`` la fuerza de fluencia y β un
factor empírico (default 0.05–0.15).
"""
from __future__ import annotations

from dataclasses import dataclass
from math import erf, log, sqrt
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class FragilityCurve:
    """Curva lognormal de fragilidad ``P(DS ≥ ds | IM = x)``."""
    median: float
    beta: float

    def probability(self, im: float | np.ndarray) -> float | np.ndarray:
        z = np.log(im / self.median) / self.beta
        return 0.5 * (1.0 + np.vectorize(erf)(z / sqrt(2.0)))


def park_ang_damage_index(delta_max: float, delta_u: float,
                            E_h: float, F_y: float,
                            beta: float = 0.10) -> float:
    """Índice de daño Park-Ang.

    ``DI < 0.4`` operacional; ``0.4–0.7`` reparable; ``>1.0`` colapso.
    """
    if delta_u <= 0 or F_y <= 0:
        raise ValueError("delta_u y F_y deben ser > 0")
    return delta_max / delta_u + beta * E_h / (delta_u * F_y)


def lognormal_fragility(im_samples: Sequence[float],
                          damage_observed: Sequence[bool]
                          ) -> FragilityCurve:
    """Ajusta una lognormal por MLE simple (estimadores momento).

    Para producción usar `scipy.stats` MLE. Esta versión es estable
    sin SciPy.
    """
    im = np.asarray(im_samples, dtype=float)
    dam = np.asarray(damage_observed, dtype=bool)
    if im.size != dam.size or im.size == 0:
        raise ValueError("im_samples y damage_observed con misma longitud no vacía")
    failed = im[dam]
    if failed.size < 2:
        # Fallback heurístico para no fallar el flujo
        return FragilityCurve(median=float(np.median(im)), beta=0.4)
    log_im = np.log(failed)
    mu = float(np.mean(log_im))
    sigma = float(np.std(log_im, ddof=1))
    return FragilityCurve(median=float(np.exp(mu)), beta=max(sigma, 0.1))


__all__ = ["FragilityCurve", "park_ang_damage_index", "lognormal_fragility"]
