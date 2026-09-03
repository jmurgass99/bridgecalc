"""EN 1991-2 — Traffic loads on bridges (Eurocode).

Implements Load Models LM1..LM4 per EN 1991-2 §4.3 and a simple-span
envelope helper for LM1 (UDL + tandem system).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# Table 4.2 — characteristic values
LM1_LANE_TABLE: Dict[int, Dict[str, float]] = {
    1: {"Qik_kN": 300.0, "qik_kPa": 9.0},
    2: {"Qik_kN": 200.0, "qik_kPa": 2.5},
    3: {"Qik_kN": 100.0, "qik_kPa": 2.5},
}
# Remaining area: qrk = 2.5 kPa
LM1_REMAINING_qrk_kPa = 2.5


@dataclass
class LM1:
    """Load Model 1 — UDL qik per lane + Tandem System (TS) Qik axles."""

    n_lanes: int = 2
    alpha_Q: float = 1.0   # National Annex factor for TS
    alpha_q: float = 1.0   # National Annex factor for UDL
    lane_width: float = 3.0  # m

    def lane_loads(self) -> List[Dict[str, float]]:
        out = []
        for i in range(1, self.n_lanes + 1):
            row = LM1_LANE_TABLE.get(i, {"Qik_kN": 0.0, "qik_kPa": LM1_REMAINING_qrk_kPa})
            out.append({
                "lane": i,
                "Qik_kN": self.alpha_Q * row["Qik_kN"],   # per axle (2 axles per TS)
                "qik_kPa": self.alpha_q * row["qik_kPa"],
            })
        return out

    def udl_per_lane_kN_per_m(self) -> List[float]:
        return [lane["qik_kPa"] * self.lane_width for lane in self.lane_loads()]

    def tandem_axles_kN(self) -> List[float]:
        return [lane["Qik_kN"] for lane in self.lane_loads()]


@dataclass
class LM2:
    """Load Model 2 — single axle. Q_ak = beta_Q * 400 kN (§4.3.3)."""

    beta_Q: float = 1.0

    @property
    def Qak_kN(self) -> float:
        return self.beta_Q * 400.0


@dataclass
class LM3:
    """Load Model 3 — special vehicles (EN 1991-2 Annex A). Configurable axles."""

    name: str = "SV80"
    axles_kN: List[float] = field(default_factory=lambda: [80.0] * 8)
    spacing_m: List[float] = field(default_factory=lambda: [1.5] * 7)

    @property
    def total_load_kN(self) -> float:
        return sum(self.axles_kN)


@dataclass
class LM4:
    """Load Model 4 — crowd loading (§4.3.5). q = 5 kPa."""

    q_kPa: float = 5.0

    def line_load_kN_per_m(self, width_m: float) -> float:
        return self.q_kPa * width_m


def _tandem_max_moment(Q: float, a: float, L: float) -> float:
    """Máximo momento absoluto de dos ejes iguales Q separados ``a``, en luz L.

    Teorema de Barré: con un tren de cargas puntuales, el momento máximo absoluto
    de una viga biapoyada ocurre BAJO uno de los ejes, cuando el centro de luz
    bisecta la distancia entre ese eje y la resultante del grupo.  Para dos ejes
    iguales la resultante cae en el punto medio, a ``a/2`` de cada eje, así que el
    eje crítico se sitúa a ``a/4`` del centro::

        x_c = L/2 - a/4
        R_L = Q[(L - x_c) + (L - x_c - a)] / L
        M   = R_L * x_c

    Verificado contra búsqueda numérica sobre todas las posiciones del tándem y
    todas las secciones (``tests/test_ec1_tandem_barre.py``): L=20 m, Q=300 kN,
    a=1.2 m → 2822.700 kN·m en x=9.70, coincidencia exacta.

    QUÉ HABÍA ANTES, porque cambia un valor de diseño: se colocaban los ejes en
    L/2 ± a/2 y se sumaba ``Q·d1·(L-d1)/L`` —el momento en la sección 9.4 m— con
    ``Q·(L-d2)·x/L`` —el momento en la sección 10.0 m—, como si fueran la misma
    sección.  Daba 2904.600 kN·m, un +2.90 % sobre el máximo real.  El error iba
    del lado seguro; se corrige porque un número que sale de sumar dos secciones
    no se puede razonar, no porque fuera inseguro.  La envolvente de una luz de
    20 m con 2 carriles BAJA de 6566.0 a 6429.5 kN·m.
    """
    un_eje = Q * L / 4.0            # un solo eje centrado
    if a >= L:
        return un_eje               # el segundo eje no entra en la luz
    x_c = L / 2.0 - a / 4.0
    if x_c <= 0.0 or x_c + a > L:
        # La posición de Barré saca el segundo eje fuera de la luz (sólo para
        # a > 2L/3). Con un eje dentro, el centrado manda.
        return un_eje
    R_L = Q * ((L - x_c) + (L - x_c - a)) / L
    return max(un_eje, R_L * x_c)


def traffic_envelope_lm1(
    L_span: float,
    n_lanes: int,
    alpha_Q: float = 1.0,
    alpha_q: float = 1.0,
    lane_width: float = 3.0,
    ts_axle_spacing: float = 1.2,
) -> Tuple[float, float]:
    """Return (M_max [kN·m], V_max [kN]) for a simply supported span.

    Combines LM1 UDL (over full span) and the Tandem System (two axles per
    lane, spaced ts_axle_spacing, placed at mid-span for M and at support
    for V). Sums contributions across active lanes.
    """
    if L_span <= 0:
        raise ValueError("L_span must be > 0")
    lm = LM1(n_lanes=n_lanes, alpha_Q=alpha_Q, alpha_q=alpha_q, lane_width=lane_width)

    # UDL contribution per lane: w in kN/m
    M_udl = 0.0
    V_udl = 0.0
    for w in lm.udl_per_lane_kN_per_m():
        M_udl += w * L_span ** 2 / 8.0
        V_udl += w * L_span / 2.0

    # Tandem system: two axles of Qik separated by 1.2 m (EN 1991-2 §4.3.2).
    M_ts = 0.0
    V_ts = 0.0
    a = ts_axle_spacing
    for Q in lm.tandem_axles_kN():
        M_ts += _tandem_max_moment(Q, a, L_span)

        # V_max: place both axles as close to support as possible (one at x=0+, the other at a)
        # V at left support = sum of reactions from both axles
        R1 = Q * (L_span - 0.0) / L_span  # axle at support
        R2 = Q * (L_span - a) / L_span if a <= L_span else 0.0
        V_ts += R1 + R2

    return M_udl + M_ts, V_udl + V_ts
