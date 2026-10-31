"""
Dynamic Load Allowance (IM) and wind load on bridge superstructure (idea #13).

Implementa el incremento por impacto vehicular (AASHTO LRFD 3.6.2) y la
presión de viento sobre tablero según código (ASCE 7-22, AASHTO 3.8.1,
Eurocode 1991-1-4 y NSR-10 B.6).

Pure Python — sin dependencias externas.
"""
from dataclasses import dataclass
from typing import Tuple

# AASHTO LRFD Table 3.6.2.1-1
_AASHTO_IM = {
    "deck_joints": 0.75,
    "fatigue": 0.15,
    "other": 0.33,
}


def dynamic_load_allowance(
    component: str = "other",
    code: str = "AASHTO",
    span_m: float = 0.0,
) -> float:
    """Return IM as a fraction (e.g. 0.33 = 33%).

    Parameters
    ----------
    component: 'deck_joints' | 'fatigue' | 'other'
    code: 'AASHTO' | 'EU' | 'NSR' | 'AS' | 'SG'
    span_m: luz para códigos que dependen de L (Eurocode dyn factor).
    """
    c = code.upper()
    if c in ("AASHTO", "USA"):
        return _AASHTO_IM.get(component, 0.33)
    if c in ("EU", "EUROCODE"):
        # Eurocode 1991-2 Anejo B: phi2 simplificado dependiendo de luz.
        # phi2 = 1.44/(sqrt(L)-0.2)+0.82 acotado [1.0,1.67] - 1.0 = IM
        if span_m <= 0.0:
            return 0.25
        import math
        phi2 = 1.44 / (math.sqrt(max(span_m, 1.0)) - 0.2) + 0.82
        phi2 = max(1.0, min(1.67, phi2))
        return phi2 - 1.0
    if c in ("NSR", "CO"):
        # NSR-10 Título C.C.3.6 -> 33% similar a AASHTO
        return 0.33
    if c in ("AS", "AU"):
        # AS 5100.2 — dynamic load allowance ~0.30 para SM1600
        return 0.30
    if c in ("SG", "SS"):
        # Singapore adopta BS/Eurocode: similar a EU
        return 0.25
    raise ValueError(f"Código desconocido: {code}")


@dataclass(frozen=True)
class WindOnBridgeInput:
    V_ms: float          # velocidad de viento (m/s)
    H_m: float           # altura tablero/elemento expuesto (m)
    L_m: float           # luz (m)
    Cd: float = 1.5      # coeficiente de arrastre tablero (típico 1.3-1.7)
    code: str = "AASHTO"
    rho_air: float = 1.225  # kg/m3


@dataclass(frozen=True)
class WindOnBridgeResult:
    pressure_kPa: float
    line_load_kN_per_m: float
    total_force_kN: float
    code: str


def wind_pressure_bridge(inp: WindOnBridgeInput) -> WindOnBridgeResult:
    """Presión y carga lineal por viento sobre tablero.

    Fórmula básica q = 0.5*rho*V^2*Cd. Cada código aplica factores extra:
      - AASHTO 3.8.1: factor 1.0 para WS strength
      - Eurocode 1991-1-4: incluye factor c_e por exposición (simplificado 1.0)
      - NSR-10: similar AASHTO
    """
    rho = inp.rho_air
    V = inp.V_ms
    q_Pa = 0.5 * rho * V * V * inp.Cd
    c = inp.code.upper()
    factor = 1.0
    if c in ("EU", "EUROCODE"):
        factor = 1.0  # ya incluido implícito
    elif c in ("AS", "AU"):
        factor = 1.05
    elif c in ("SG", "SS"):
        factor = 1.0
    elif c in ("NSR", "CO"):
        factor = 1.0
    elif c in ("AASHTO", "USA"):
        factor = 1.0
    else:
        raise ValueError(f"Código desconocido: {inp.code}")
    q = q_Pa * factor
    line = q * inp.H_m / 1000.0  # kN/m
    total = line * inp.L_m
    return WindOnBridgeResult(
        pressure_kPa=q / 1000.0,
        line_load_kN_per_m=line,
        total_force_kN=total,
        code=inp.code,
    )


def combined_dynamic_truck_wind(
    static_truck_kN: float,
    span_m: float,
    wind: WindOnBridgeInput,
    component: str = "other",
) -> Tuple[float, float, float]:
    """Devuelve (truck_dinamico_kN, wind_line_kN_m, total_action_kN).

    total_action = truck(1+IM) + wind_line * span.
    """
    im = dynamic_load_allowance(component=component, code=wind.code, span_m=span_m)
    truck_dyn = static_truck_kN * (1.0 + im)
    w = wind_pressure_bridge(wind)
    return truck_dyn, w.line_load_kN_per_m, truck_dyn + w.total_force_kN
