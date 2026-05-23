"""
Calificación de carga de puentes — AASHTO Manual for Bridge Evaluation (LRFR).

Factor de calificación (MBE Eq. 6A.4.2.1-1):

    RF = (C − γ_DC·DC − γ_DW·DW ± γ_P·P) / (γ_LL·(LL + IM))

con  C = φ_c·φ_s·φ·R_n  (capacidad afectada por factores de condición y sistema).

Niveles: Inventory (γ_LL=1.75) y Operating (γ_LL=1.35) para el estado Strength I.
RF >= 1.0 → el puente admite la carga viva a ese nivel.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# Factores de carga viva LRFR (MBE Tabla 6A.4.2.2-1), Strength I.
LRFR_LIVE_FACTORS = {
    "inventory": 1.75,
    "operating": 1.35,
}


@dataclass(frozen=True)
class RatingInput:
    Rn: float                 # resistencia nominal del elemento (capacidad)
    DC: float                 # efecto de carga muerta estructural
    DW: float                 # efecto de carga muerta de superficie
    LL_IM: float              # efecto de carga viva + impacto (1 camión de calificación)
    P: float = 0.0            # cargas permanentes adicionales (postensado, etc.)
    phi: float = 0.90         # factor de resistencia (Strength)
    phi_c: float = 1.00       # factor de condición (1.0 buena, 0.95, 0.85)
    phi_s: float = 1.00       # factor de sistema (redundancia)
    gamma_DC: float = 1.25
    gamma_DW: float = 1.50
    gamma_P: float = 1.00


@dataclass(frozen=True)
class RatingResult:
    level: str
    RF: float
    capacity_C: float
    gamma_LL: float
    ok: bool                  # RF >= 1.0


def rating_factor(inp: RatingInput, level: Literal["inventory", "operating"] = "inventory") -> RatingResult:
    """Factor de calificación RF para el nivel dado (Strength I)."""
    if level not in LRFR_LIVE_FACTORS:
        raise ValueError("nivel debe ser 'inventory' u 'operating'")
    gLL = LRFR_LIVE_FACTORS[level]
    C = inp.phi_c * inp.phi_s * inp.phi * inp.Rn
    demand_perm = inp.gamma_DC * inp.DC + inp.gamma_DW * inp.DW + inp.gamma_P * inp.P
    live = gLL * inp.LL_IM
    RF = (C - demand_perm) / live if live > 0 else float("inf")
    return RatingResult(level=level, RF=RF, capacity_C=C, gamma_LL=gLL, ok=RF >= 1.0)


def rating_both_levels(inp: RatingInput) -> dict[str, RatingResult]:
    """RF en Inventory y Operating de una vez."""
    return {lvl: rating_factor(inp, lvl) for lvl in LRFR_LIVE_FACTORS}


__all__ = ["RatingInput", "RatingResult", "rating_factor", "rating_both_levels", "LRFR_LIVE_FACTORS"]
