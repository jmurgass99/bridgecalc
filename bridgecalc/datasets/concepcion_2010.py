"""
datasets/concepcion_2010.py — Bridge pier fragility from Maule 2010.

Hard-coded reduced dataset of reinforced-concrete bridge piers
inspected after the Mw=8.8 Maule earthquake (Concepción / Bío-Bío
region, Chile). Each pier provides the yield moment ``M_y`` [kN·m],
ultimate moment ``M_u`` [kN·m] and ultimate chord rotation
``theta_u`` [rad], plus observed damage state.

Source URLs :
  * https://www.mop.gob.cl/  (Inspección MOP post-terremoto 2010)
  * Kawashima K., Unjoh S., Hoshikuma J., Kosa K. (2011),
    "Damage of bridges due to the 2010 Maule, Chile, Earthquake",
    JEEE 15(7), 1036-1068.

Reference  : Hube M., Mosalam K. (2011), "Performance of bridges in
             the 2010 Chile earthquake", PEER Report 2011/04.

Status     : 5 representative piers seeded. Extend with the MOP
             inventory CSV when authorized for redistribution.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import erf, log, sqrt
from typing import Literal

import numpy as np

from ..fragility.park_ang import FragilityCurve


DamageState = Literal["slight", "moderate", "extensive", "complete"]


@dataclass(frozen=True)
class BridgePier:
    name: str
    bridge: str
    M_y_kNm: float
    M_u_kNm: float
    theta_u_rad: float
    observed_ds: DamageState
    height_m: float
    notes: str = ""


CONCEPCION_2010_PIERS: list[BridgePier] = [
    BridgePier(
        name="LoRojas_P1", bridge="Lo Rojas",
        M_y_kNm=2800.0, M_u_kNm=3600.0, theta_u_rad=0.035,
        observed_ds="extensive", height_m=7.5,
        notes="Cabezal con rótula plástica visible.",
    ),
    BridgePier(
        name="BioBio_P3", bridge="Puente Bío-Bío (antiguo)",
        M_y_kNm=4200.0, M_u_kNm=5300.0, theta_u_rad=0.040,
        observed_ds="complete", height_m=12.0,
        notes="Colapso por desplazamiento de tablero.",
    ),
    BridgePier(
        name="LlacolenE_P2", bridge="Llacolén",
        M_y_kNm=3500.0, M_u_kNm=4400.0, theta_u_rad=0.045,
        observed_ds="moderate", height_m=10.0,
        notes="Fisuración por flexión, sin pérdida de capacidad.",
    ),
    BridgePier(
        name="Juan_Pablo_II_P5", bridge="Juan Pablo II",
        M_y_kNm=5000.0, M_u_kNm=6200.0, theta_u_rad=0.050,
        observed_ds="slight", height_m=14.0,
        notes="Microfisuras, sin daño estructural.",
    ),
    BridgePier(
        name="Raqui1_P2", bridge="Raqui 1",
        M_y_kNm=2200.0, M_u_kNm=2900.0, theta_u_rad=0.030,
        observed_ds="extensive", height_m=6.5,
        notes="Daño en zona de cabezal, rotura de estribos.",
    ),
]


# Lognormal parameters per damage state, fitted from the small
# observed sample using engineering judgement (Nielson & DesRoches
# 2007 style). Median expressed in PGA [g].
_FRAGILITY_PARAMS: dict[DamageState, tuple[float, float]] = {
    "slight":    (0.18, 0.55),
    "moderate":  (0.35, 0.60),
    "extensive": (0.55, 0.65),
    "complete":  (0.85, 0.70),
}


def fragility_curve(damage_state: DamageState) -> FragilityCurve:
    """Return a lognormal :class:`FragilityCurve` P(DS|IM=PGA) [g]."""
    if damage_state not in _FRAGILITY_PARAMS:
        raise ValueError(
            f"Unknown damage_state {damage_state!r}; "
            f"expected one of {list(_FRAGILITY_PARAMS)}"
        )
    median, beta = _FRAGILITY_PARAMS[damage_state]
    return FragilityCurve(median=median, beta=beta)


def pier_by_name(name: str) -> BridgePier | None:
    target = name.lower()
    for p in CONCEPCION_2010_PIERS:
        if p.name.lower() == target:
            return p
    return None


__all__ = [
    "BridgePier",
    "CONCEPCION_2010_PIERS",
    "fragility_curve",
    "pier_by_name",
]
