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


def _binomial_loglik(log_im: np.ndarray, dam: np.ndarray, log_med: np.ndarray, beta: np.ndarray) -> np.ndarray:
    """Log-verosimilitud binomial Σ[y·ln Φ(z) + (1−y)·ln(1−Φ(z))] para una rejilla de (ln mediana, β)."""
    z = (log_im[None, None, :] - log_med[:, :, None]) / beta[:, :, None]
    p = 0.5 * (1.0 + np.vectorize(erf)(z / sqrt(2.0)))
    p = np.clip(p, 1e-12, 1.0 - 1e-12)
    y = dam[None, None, :]
    return np.sum(y * np.log(p) + (1.0 - y) * np.log(1.0 - p), axis=2)


def lognormal_fragility(im_samples: Sequence[float],
                          damage_observed: Sequence[bool],
                          beta_min: float = 0.1,
                          beta_max: float = 1.5,
                          ) -> FragilityCurve:
    """Ajusta P(daño | IM) = Φ(ln(IM/θ)/β) por máxima verosimilitud binomial (Baker 2015).

    Cada observación es un ensayo de Bernoulli con probabilidad Φ(ln(IM_i/θ)/β); se maximiza la
    log-verosimilitud con dos rejillas sucesivas sobre (ln θ, β), sin SciPy. β se acota a
    [beta_min, beta_max]: con separación perfecta (todo lo que daña está por encima de todo lo que no)
    la verosimilitud crece al bajar β y el ajuste queda en beta_min.

    Hasta la versión 1.0 se devolvían la media y la desviación de ln(IM) de las muestras CON daño:
    eso describe dónde cayeron los daños, no la fragilidad, y sesga la mediana hacia arriba (con IM
    uniforme entre 0,05 y 1,5 g y mediana real 0,45 g daba 0,88 g).
    """
    im = np.asarray(im_samples, dtype=float)
    dam = np.asarray(damage_observed, dtype=bool).astype(float)
    if im.size != dam.size or im.size == 0:
        raise ValueError("im_samples y damage_observed con misma longitud no vacía")
    if np.any(im <= 0):
        raise ValueError("im_samples debe ser > 0")
    if dam.sum() == 0 or dam.sum() == dam.size:
        raise ValueError("hacen falta observaciones con y sin daño para ajustar una fragilidad")
    log_im = np.log(im)
    lo, hi = float(log_im.min()) - 1.0, float(log_im.max()) + 1.0
    b_lo, b_hi = float(beta_min), float(beta_max)
    best = (0.0, 0.0)
    for _ in range(3):
        lm = np.linspace(lo, hi, 61)
        bb = np.linspace(b_lo, b_hi, 41)
        LM, BB = np.meshgrid(lm, bb, indexing="ij")
        ll = _binomial_loglik(log_im, dam, LM, BB)
        i, j = np.unravel_index(int(np.argmax(ll)), ll.shape)
        best = (float(lm[i]), float(bb[j]))
        dl, db = (hi - lo) / 60.0, (b_hi - b_lo) / 40.0
        lo, hi = best[0] - 2 * dl, best[0] + 2 * dl
        b_lo, b_hi = max(beta_min, best[1] - 2 * db), min(beta_max, best[1] + 2 * db)
    return FragilityCurve(median=float(np.exp(best[0])), beta=float(best[1]))


__all__ = ["FragilityCurve", "park_ang_damage_index", "lognormal_fragility"]
