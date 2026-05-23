"""
Eurocode LM3 (EN 1991-2 §4.3.4) — special vehicles.

LM3 corresponds to abnormal/heavy vehicles allowed on bridges via
special transit permits. Each annex SV120, SV196, SV-Train... gives
total weight & axle distribution. We model SV-Train (12 axles, 12 t each
+ 4 axles 24 t) parametrically for one-lane traversal of a simply
supported span.

Reference: EN 1991-2 Annex A (informative) Table A1.

Also includes simplified Indian IRC Class A (IRC:6-2017) and Australian
AS 5100.2 SM1600 vehicle for multi-code coverage.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SpecialVehicle:
    name: str
    axle_loads_kN: tuple[float, ...]
    axle_spacings_m: tuple[float, ...]    # gaps; len = len(axles)-1
    code: str = "EUROCODE"

    @property
    def total_load_kN(self) -> float:
        return sum(self.axle_loads_kN)

    @property
    def length_m(self) -> float:
        return sum(self.axle_spacings_m)


# Catálogo
EUROCODE_SV120: SpecialVehicle = SpecialVehicle(
    name="SV120",
    axle_loads_kN=(240.0,) * 6,
    axle_spacings_m=(1.2,) * 5,
    code="EUROCODE",
)

EUROCODE_SV196: SpecialVehicle = SpecialVehicle(
    name="SV196",
    axle_loads_kN=(180.0,) * 8 + (240.0,) * 4,   # 8×180 + 4×240
    axle_spacings_m=(1.5,) * 11,
    code="EUROCODE",
)

# IRC Class A — 8 axles total
IRC_CLASS_A: SpecialVehicle = SpecialVehicle(
    name="IRC Class A",
    axle_loads_kN=(27.0, 27.0, 114.0, 114.0, 68.0, 68.0, 68.0, 68.0),
    axle_spacings_m=(1.1, 3.2, 1.2, 4.3, 3.0, 3.0, 3.0),
    code="INDIA",
)

# AS 5100.2 SM1600 idealised T44 (3-axle truck)
AS_SM1600: SpecialVehicle = SpecialVehicle(
    name="AS 5100.2 SM1600 T44",
    axle_loads_kN=(48.0, 96.0, 96.0),
    axle_spacings_m=(3.0, 1.2),
    code="AS",
)

# AASHTO HS20 truck (reference) — 3 axles
AASHTO_HS20: SpecialVehicle = SpecialVehicle(
    name="HS20-44",
    axle_loads_kN=(35.6, 142.3, 142.3),
    axle_spacings_m=(4.27, 4.27),
    code="USA",
)


def max_moment_simple_span(vehicle: SpecialVehicle, span_m: float,
                            n_positions: int = 200) -> dict:
    """
    Calcula el momento máximo en el centro de una viga simplemente apoyada
    para un vehículo que recorre el puente axle por axle (envolvente
    discretizada en n_positions posiciones).

    El método utiliza la línea de influencia exacta del momento al
    centro: y(x) = x/2 si x ≤ L/2 else (L-x)/2.
    """
    if span_m <= 0:
        raise ValueError("span_m debe ser > 0")
    L = span_m
    axles = list(vehicle.axle_loads_kN)
    spacings = list(vehicle.axle_spacings_m)
    # cumulative axle distances from first axle
    axle_x = [0.0]
    for s in spacings:
        axle_x.append(axle_x[-1] + s)
    Lveh = axle_x[-1]

    # Move the front (first) axle from x_front=0 to x_front=L+Lveh
    M_max = 0.0
    x_critical = 0.0
    total_travel = L + Lveh
    for k in range(n_positions + 1):
        x_front = total_travel * k / n_positions - Lveh
        M = 0.0
        for ax_x, P in zip(axle_x, axles):
            pos = x_front + ax_x
            if 0.0 <= pos <= L:
                # influence line at midspan
                if pos <= L / 2:
                    y = pos / 2.0
                else:
                    y = (L - pos) / 2.0
                M += P * y
        if M > M_max:
            M_max = M
            x_critical = x_front
    return {
        "vehicle": vehicle.name,
        "code": vehicle.code,
        "span_m": span_m,
        "M_max_kNm": round(M_max, 2),
        "x_front_critical_m": round(x_critical, 3),
        "total_load_kN": vehicle.total_load_kN,
    }


def impact_factor(code: str, span_m: float) -> float:
    """
    Factor de impacto dinámico DAF para vehículos pesados.

    EUROCODE: ya incluido en LM1.  Para LM3 (EN 1991-2 A.4) DAF≈1.0 por
        ser carga lenta controlada.
    USA AASHTO LRFD §3.6.2:  IM = 33% (truck) → DAF = 1.33.
    INDIA IRC 6-2017 §211.3 Class A:
        I = 4.5 / (6 + L)  para L en m (max 25%) → DAF = 1 + I.
    AS 5100.2 §7.7: α_d = 0.3  → DAF = 1.30.
    """
    c = code.upper()
    if c in ("EUROCODE", "EU"):
        return 1.0
    if c in ("USA", "AASHTO", "US"):
        return 1.33
    if c in ("INDIA", "IRC"):
        I = 4.5 / (6.0 + span_m)
        return 1.0 + min(I, 0.25)
    if c in ("AS", "AUSTRALIA", "AU"):
        return 1.30
    return 1.0


__all__ = [
    "SpecialVehicle", "EUROCODE_SV120", "EUROCODE_SV196",
    "IRC_CLASS_A", "AS_SM1600", "AASHTO_HS20",
    "max_moment_simple_span", "impact_factor",
]
