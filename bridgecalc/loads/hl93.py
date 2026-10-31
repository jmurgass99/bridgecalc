"""
AASHTO LRFD HL-93 — tren de carga vehicular.

Implementación de la envolvente para una viga simplemente apoyada bajo:
- Camión HS-20 (8 kips eje delantero + 32 + 32 kips a 4.27 m)
- Tandem (110 kN × 2 a 1.20 m)
- Carril uniforme 9.34 kN/m

LRFD requiere ``max(camión, tandem) + carril``. Esta implementación
calcula M+ y V+ máximos para una longitud de luz dada. Para puentes
multi-tramo o secciones complejas, usar el output como input de
`fastsap`/`fastcsib`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


# Constantes HL-93 en SI
TRUCK_AXLES_kN = (35.0, 145.0, 145.0)
TRUCK_AXLE_SPACINGS_m = (4.27, 4.27)  # 4.27..9.14, default extremo cerrado
TANDEM_AXLES_kN = (110.0, 110.0)
TANDEM_SPACING_m = 1.20
LANE_LOAD_kN_per_m = 9.34


@dataclass(frozen=True)
class HL93Configuration:
    span_m: float
    n_points: int = 200
    impact_factor: float = 1.33  # IM = 0.33 (default LRFD §3.6.2)


@dataclass(frozen=True)
class HL93Result:
    M_max_kNm: float
    V_max_kN: float
    governing_vehicle: str  # 'truck' o 'tandem'

    def to_dict(self) -> dict[str, Any]:
        return {
            "M_max_kNm": self.M_max_kNm,
            "V_max_kN": self.V_max_kN,
            "governing_vehicle": self.governing_vehicle,
        }


def _simple_beam_M_under_point_loads(L: float, loads: list[tuple[float, float]]
                                       ) -> float:
    """Máximo momento positivo en una viga simple por superposición.

    ``loads`` = [(a_i, P_i), ...] con a_i posición del eje desde el apoyo
    izquierdo y P_i la carga puntual.
    """
    # Por simplicidad calculamos sumando M(x) = Σ R_i·x - Σ P_j·(x - a_j)+
    # sobre una malla densa.
    x = np.linspace(0, L, 200)
    M_max = 0.0
    for x0 in x:
        total = 0.0
        for a, P in loads:
            # Reacción en apoyo izquierdo: R = P·(L-a)/L
            R = P * (L - a) / L
            if x0 < a:
                total += R * x0
            else:
                total += R * x0 - P * (x0 - a)
        M_max = max(M_max, total)
    return M_max


def _simple_beam_V_max(L: float, loads: list[tuple[float, float]]) -> float:
    """Cortante máximo (en el apoyo) = suma de reacciones."""
    R_left = sum(P * (L - a) / L for a, P in loads)
    R_right = sum(P * a / L for a, P in loads)
    return max(R_left, R_right)


def _truck_envelope_M(L: float) -> float:
    """Posiciona el camión en la luz buscando max M+."""
    # El camión ocupa 8.54 m (rear axle separation default 4.27+4.27)
    truck_len = sum(TRUCK_AXLE_SPACINGS_m)
    M_best = 0.0
    if L < 0.5:
        return 0.0
    # Posición del eje delantero
    for a1 in np.linspace(0, max(L - 0.01, 0), 60):
        a2 = a1 + TRUCK_AXLE_SPACINGS_m[0]
        a3 = a2 + TRUCK_AXLE_SPACINGS_m[1]
        loads = []
        for a, P in zip((a1, a2, a3), TRUCK_AXLES_kN):
            if 0 <= a <= L:
                loads.append((a, P))
        if loads:
            M_best = max(M_best, _simple_beam_M_under_point_loads(L, loads))
    return M_best


def _tandem_envelope_M(L: float) -> float:
    M_best = 0.0
    for a1 in np.linspace(0, max(L - 0.01, 0), 60):
        a2 = a1 + TANDEM_SPACING_m
        loads = []
        for a, P in zip((a1, a2), TANDEM_AXLES_kN):
            if 0 <= a <= L:
                loads.append((a, P))
        if loads:
            M_best = max(M_best, _simple_beam_M_under_point_loads(L, loads))
    return M_best


def hl93_envelope(
    L_m: float,
    *,
    impact_factor: float = 1.33,
    n_points: int = 200,
) -> dict[str, Any]:
    """Envolvente HL-93 (AASHTO LRFD) en una viga simplemente apoyada.

    Wrapper de conveniencia con firma posicional ``hl93_envelope(L_m, ...)``
    (idea #12): delega en :func:`hl93_influence_envelope` y devuelve un dict
    con el desglose camión / tándem / carril, ya combinado según LRFD
    §3.6.1.3 — ``max(camión, tándem)·IM + carril`` — y el vehículo que
    gobierna. ``M_max_kNm`` / ``V_max_kN`` son las solicitaciones de diseño.

    Parameters
    ----------
    L_m : luz de la viga simplemente apoyada [m].
    impact_factor : 1 + IM (default 1.33 → IM=33 %, LRFD §3.6.2). Se aplica
        SOLO a la componente vehicular, no al carril.
    n_points : densidad de la malla de barrido.

    Returns
    -------
    dict con ``M_max_kNm``, ``V_max_kN``, ``governing_vehicle`` y el desglose
    ``M_truck_kNm`` / ``M_tandem_kNm`` / ``M_lane_kNm`` (sin IM) más ``IM``.
    """
    cfg = HL93Configuration(span_m=L_m, n_points=n_points,
                            impact_factor=impact_factor)
    res = hl93_influence_envelope(cfg)
    L = float(L_m)
    M_truck = _truck_envelope_M(L)
    M_tandem = _tandem_envelope_M(L)
    M_lane = LANE_LOAD_kN_per_m * L * L / 8.0
    V_lane = LANE_LOAD_kN_per_m * L / 2.0
    return {
        "M_max_kNm": res.M_max_kNm,
        "V_max_kN": res.V_max_kN,
        "governing_vehicle": res.governing_vehicle,
        "M_truck_kNm": M_truck,
        "M_tandem_kNm": M_tandem,
        "M_lane_kNm": M_lane,
        "V_lane_kN": V_lane,
        "IM": impact_factor,
        "span_m": L,
    }


def hl93_influence_envelope(cfg: HL93Configuration) -> HL93Result:
    """Calcula la envolvente HL-93 para una viga simple.

    LRFD §3.6.1.3 — se aplica el mayor de camión o tandem, sumado al
    carril uniforme, con el factor de impacto IM = 0.33 sobre la
    componente vehicular (no sobre el carril).
    """
    L = cfg.span_m
    if L <= 0:
        raise ValueError("span_m debe ser > 0")
    M_truck = _truck_envelope_M(L)
    M_tandem = _tandem_envelope_M(L)
    governing = "truck" if M_truck >= M_tandem else "tandem"
    M_vehicle = max(M_truck, M_tandem) * cfg.impact_factor
    M_lane = LANE_LOAD_kN_per_m * L * L / 8.0
    M_total = M_vehicle + M_lane

    V_truck = _simple_beam_V_max(L, [
        (a, P) for a, P in
        [(0.0, TRUCK_AXLES_kN[2]),
         (TRUCK_AXLE_SPACINGS_m[1], TRUCK_AXLES_kN[1]),
         (sum(TRUCK_AXLE_SPACINGS_m), TRUCK_AXLES_kN[0])]
        if 0 <= a <= L
    ])
    V_tandem = _simple_beam_V_max(L, [
        (0.0, TANDEM_AXLES_kN[1]), (TANDEM_SPACING_m, TANDEM_AXLES_kN[0]),
    ]) if L >= TANDEM_SPACING_m else 0.0
    V_vehicle = max(V_truck, V_tandem) * cfg.impact_factor
    V_lane = LANE_LOAD_kN_per_m * L / 2.0
    V_total = V_vehicle + V_lane

    return HL93Result(M_max_kNm=M_total, V_max_kN=V_total,
                       governing_vehicle=governing)


# ---------------------------------------------------------------
# HL-93K variante chilena NCh 3171 — camion de 44 ton
# ---------------------------------------------------------------
# NCh 3171.Of2010 / Manual de Carreteras MOP Chile, Vol. 3 Cap. 3.1004
# Camion tipo: 3 ejes, peso bruto 432 kN (44 ton)
#   Eje delantero:  62 kN
#   Eje central:    185 kN  (a 4.0 m del delantero)
#   Eje trasero:    185 kN  (a 4.0 m del central)
# Carril equivalente: 9.34 kN/m (mismo que AASHTO)
# IM = 0.25 para estado limite de resistencia (NCh 3171)
NCH_TRUCK_AXLES_kN = (62.0, 185.0, 185.0)
NCH_TRUCK_AXLE_SPACINGS_m = (4.0, 4.0)
NCH_LANE_LOAD_kN_per_m = 9.34
NCH_IMPACT_FACTOR = 1.25


@dataclass(frozen=True)
class HL93KNChConfiguration:
    """Configuracion para camion NCh 3171 (Chile, 44 ton)."""
    span_m: float
    n_points: int = 200
    impact_factor: float = NCH_IMPACT_FACTOR


@dataclass(frozen=True)
class HL93KNChResult:
    M_max_kNm: float
    V_max_kN: float
    total_truck_load_kN: float
    axle_positions: tuple[float, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "M_max_kNm": self.M_max_kNm,
            "V_max_kN": self.V_max_kN,
            "total_truck_load_kN": self.total_truck_load_kN,
            "axle_positions": list(self.axle_positions),
        }


def hl93k_nch_envelope(cfg: HL93KNChConfiguration) -> HL93KNChResult:
    """Envolvente del camion NCh 3171 + carril para viga simple.

    Procedimiento analogo a HL-93: max(camion NCh) * IM + lane.
    """
    L = cfg.span_m
    if L <= 0:
        raise ValueError("span_m debe ser > 0")

    # Barrer posiciones del camion
    M_best = 0.0
    for a1 in np.linspace(0, max(L - 0.01, 0), 80):
        a2 = a1 + NCH_TRUCK_AXLE_SPACINGS_m[0]
        a3 = a2 + NCH_TRUCK_AXLE_SPACINGS_m[1]
        loads = [(a, P) for a, P in zip((a1, a2, a3), NCH_TRUCK_AXLES_kN)
                 if 0 <= a <= L]
        if loads:
            M_best = max(M_best, _simple_beam_M_under_point_loads(L, loads))

    M_truck = M_best * cfg.impact_factor
    M_lane = NCH_LANE_LOAD_kN_per_m * L * L / 8.0
    M_total = M_truck + M_lane

    # Cortante: camion con eje pesado en el apoyo
    V_loads = [
        (0.0, NCH_TRUCK_AXLES_kN[2]),
        (NCH_TRUCK_AXLE_SPACINGS_m[1], NCH_TRUCK_AXLES_kN[1]),
        (sum(NCH_TRUCK_AXLE_SPACINGS_m), NCH_TRUCK_AXLES_kN[0]),
    ]
    V_loads_valid = [(a, P) for a, P in V_loads if 0 <= a <= L]
    V_truck = _simple_beam_V_max(L, V_loads_valid) * cfg.impact_factor if V_loads_valid else 0.0
    V_lane = NCH_LANE_LOAD_kN_per_m * L / 2.0
    V_total = V_truck + V_lane

    return HL93KNChResult(
        M_max_kNm=M_total,
        V_max_kN=V_total,
        total_truck_load_kN=sum(NCH_TRUCK_AXLES_kN),
        axle_positions=NCH_TRUCK_AXLE_SPACINGS_m,
    )


__all__ = [
    "HL93Configuration", "HL93Result", "hl93_influence_envelope",
    "hl93_envelope",
    "HL93KNChConfiguration", "HL93KNChResult", "hl93k_nch_envelope",
    "NCH_TRUCK_AXLES_kN", "NCH_TRUCK_AXLE_SPACINGS_m",
]
