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
    # For M_max place TS straddling mid-span (axles at L/2 ± a/2):
    M_ts = 0.0
    V_ts = 0.0
    a = ts_axle_spacing
    for Q in lm.tandem_axles_kN():
        # Each axle Q (kN) is one wheel pair (already total per axle)
        # Simply supported beam, point load P at distance d from left:
        # reaction R_left = P*(L-d)/L; moment at d: P*d*(L-d)/L
        d1 = L_span / 2.0 - a / 2.0
        d2 = L_span / 2.0 + a / 2.0
        if 0.0 <= d1 <= L_span and 0.0 <= d2 <= L_span:
            M1 = Q * d1 * (L_span - d1) / L_span
            # contribution to moment at section x = L/2 from load at d2
            # M_x = P*(L-d)*x/L for x<=d
            x = L_span / 2.0
            M2 = Q * (L_span - d2) * x / L_span
            M_ts += M1 + M2
        else:
            # Span shorter than tandem; place single axle at mid-span
            M_ts += Q * L_span / 4.0

        # V_max: place both axles as close to support as possible (one at x=0+, the other at a)
        # V at left support = sum of reactions from both axles
        R1 = Q * (L_span - 0.0) / L_span  # axle at support
        R2 = Q * (L_span - a) / L_span if a <= L_span else 0.0
        V_ts += R1 + R2

    return M_udl + M_ts, V_udl + V_ts
