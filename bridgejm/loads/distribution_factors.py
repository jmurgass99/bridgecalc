"""
Factores de distribución de carga viva — AASHTO LRFD §4.6.2.2.

Para puentes losa-viga típicos (tablero de hormigón sobre vigas de acero o
prefabricadas de hormigón; tipos (a)/(k) de la Tabla 4.6.2.2.1-1). Distribuyen el
momento/cortante de una línea de ruedas a una viga individual (interior/exterior),
para una o varias líneas de tráfico cargadas.

UNIDADES (las fórmulas del LRFD son EMPÍRICAS en pies/pulgadas — se respetan):
  S   separación entre vigas (ft)        L  luz de cálculo (ft)
  ts  espesor de losa (in)               Kg parámetro de rigidez longitudinal (in^4)
  de  distancia borde-viga exterior al bordillo interior de la baranda (ft)

Rangos de aplicabilidad (§4.6.2.2.2b): 3.5<=S<=16 ft, 4.5<=ts<=12 in,
20<=L<=240 ft, Kg típico. Fuera de rango -> usar método refinado (no implementado).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DistributionFactors:
    gm_interior_1: float    # momento, viga interior, 1 carril
    gm_interior_2: float    # momento, viga interior, 2+ carriles
    gv_interior_1: float    # cortante, viga interior, 1 carril
    gv_interior_2: float    # cortante, viga interior, 2+ carriles
    gm_exterior: float      # momento, viga exterior (lever rule + e)
    gv_exterior: float      # cortante, viga exterior

    @property
    def gm_interior(self) -> float:
        return max(self.gm_interior_1, self.gm_interior_2)

    @property
    def gv_interior(self) -> float:
        return max(self.gv_interior_1, self.gv_interior_2)


def _Kg_term(Kg_in4: float, L_ft: float, ts_in: float) -> float:
    """(Kg / (12·L·ts^3))^0.1 — término de rigidez de la Tabla 4.6.2.2.2b-1."""
    return (Kg_in4 / (12.0 * L_ft * ts_in ** 3)) ** 0.1


def moment_interior(S_ft: float, L_ft: float, ts_in: float, Kg_in4: float) -> tuple[float, float]:
    """gm interior (1 carril, 2+ carriles) — Tabla 4.6.2.2.2b-1, tipos (a)/(e)/(k)."""
    kg = _Kg_term(Kg_in4, L_ft, ts_in)
    g1 = 0.06 + (S_ft / 14.0) ** 0.4 * (S_ft / L_ft) ** 0.3 * kg
    g2 = 0.075 + (S_ft / 9.5) ** 0.6 * (S_ft / L_ft) ** 0.2 * kg
    return g1, g2


def shear_interior(S_ft: float) -> tuple[float, float]:
    """gv interior (1 carril, 2+ carriles) — Tabla 4.6.2.2.3a-1."""
    g1 = 0.36 + S_ft / 25.0
    g2 = 0.2 + S_ft / 12.0 - (S_ft / 35.0) ** 2
    return g1, g2


def lever_rule_exterior(S_ft: float, de_ft: float, axle_width_ft: float = 6.0) -> float:
    """Regla de la palanca para la viga exterior (1 carril): reacción de una rueda.

    Coloca la rueda exterior a 2 ft del bordillo (§3.6.1.3); devuelve la fracción de
    la línea de ruedas que toma la viga exterior. Incluye el factor de presencia
    múltiple m=1.20 para un carril.
    """
    # Posición de las ruedas respecto a la viga exterior (centro del ancho de eje).
    # Rueda exterior a (de - 2) del eje de la viga; rueda interior a +axle_width.
    x1 = de_ft - 2.0
    x2 = x1 + axle_width_ft
    R = (x1 + x2) / (2.0 * S_ft)   # reacción por momentos respecto a la viga interior adyacente
    return max(R, 0.0) * 1.20      # m=1.20 (un carril)


def exterior_e_factor(de_ft: float) -> float:
    """Factor e para viga exterior (2+ carriles): e = 0.77 + de/9.1 (§4.6.2.2.2d), e>=1.0 si de>0."""
    return 0.77 + de_ft / 9.1


@dataclass(frozen=True)
class GirderGeometry:
    S_ft: float          # separación de vigas
    L_ft: float          # luz
    ts_in: float         # espesor de losa
    Kg_in4: float        # rigidez longitudinal n·(I + A·eg^2)
    de_ft: float = 2.0   # voladizo borde-viga exterior


def distribution_factors(g: GirderGeometry) -> DistributionFactors:
    """Calcula todos los factores de distribución LRFD para la geometría dada."""
    gm1, gm2 = moment_interior(g.S_ft, g.L_ft, g.ts_in, g.Kg_in4)
    gv1, gv2 = shear_interior(g.S_ft)
    # Exterior: el mayor entre lever rule (1 carril) y e·g_interior (2+ carriles).
    e = exterior_e_factor(g.de_ft)
    gm_ext = max(lever_rule_exterior(g.S_ft, g.de_ft), e * gm2)
    gv_ext = max(lever_rule_exterior(g.S_ft, g.de_ft), e * gv2)
    return DistributionFactors(gm1, gm2, gv1, gv2, gm_ext, gv_ext)


__all__ = [
    "DistributionFactors", "GirderGeometry", "distribution_factors",
    "moment_interior", "shear_interior", "lever_rule_exterior", "exterior_e_factor",
]
