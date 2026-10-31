"""EN 1998-2 §7 — Ductile design of bridge piers.

Helpers for behavior factor q, confinement reinforcement, plastic hinge
length (Priestley) and DCH target-displacement check.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


# EN 1998-2 Table 4.1 — maximum q values (simplified mapping).
_Q_TABLE: Dict[str, float] = {
    "reinforced_concrete_ductile": 3.5,
    "reinforced_concrete_limited_ductility": 1.5,
    "steel_ductile": 3.5,
    "steel_limited_ductility": 1.5,
    "non_ductile": 1.0,
}


def behavior_factor_q(pier_type: str, geometry: Dict | None = None) -> float:
    """Return q per EN 1998-2 Table 4.1.

    pier_type: one of the keys in _Q_TABLE. geometry may carry
    'shear_span_ratio' = Ls/h; if < 3.0 q is reduced linearly to 1.0
    (per §4.1.6(9) lambda(alpha_s) factor).
    """
    key = pier_type.lower()
    if key not in _Q_TABLE:
        raise ValueError(f"Unknown pier_type {pier_type!r}")
    q = _Q_TABLE[key]
    if geometry:
        alpha_s = geometry.get("shear_span_ratio")
        if alpha_s is not None and alpha_s < 3.0:
            # lambda(alpha_s) = sqrt(alpha_s/3) for 1 <= alpha_s < 3 (Note 1)
            if alpha_s < 1.0:
                q = 1.0
            else:
                q = max(1.0, q * (alpha_s / 3.0) ** 0.5)
    return q


def confinement_required(
    N_Ed: float,
    Ac: float,
    fcd: float,
    alpha_n: float = 1.0,
    alpha_s: float = 1.0,
    fyd: float = 435.0e3,
    Acc: float | None = None,
    omega_w_min: float = 0.12,
) -> float:
    """Mechanical volumetric confinement ratio omega_w,req per §6.2.1.

    omega_w,req = alpha * omega_w >= omega_w,min where
        omega_w = 0.37 * (Ac/Acc) * eta_k + 0.13 * (fyd/fcd) * (rho_l - 0.01)
    For a simplified DCH check we use the basic axial-force driven form:
        omega_w_req = max(omega_w_min, 0.37 * (Ac/Acc) * eta_k / (alpha_n*alpha_s))
    with eta_k = N_Ed / (Ac * fcd).

    Units: forces in N, areas in m^2, stresses in Pa.
    """
    if Ac <= 0 or fcd <= 0:
        raise ValueError("Ac and fcd must be positive")
    if Acc is None:
        Acc = 0.85 * Ac  # typical concrete core / gross ratio
    eta_k = N_Ed / (Ac * fcd)
    alpha = max(alpha_n * alpha_s, 1e-6)
    omega_w = 0.37 * (Ac / Acc) * eta_k / alpha
    return max(omega_w_min, omega_w)


def plastic_hinge_length(Lv: float, fy: float, db: float) -> float:
    """Priestley plastic-hinge length.

    Lp = 0.10*Lv + 0.015*fy*db, with fy in MPa, db and Lv in m, Lp in m.
    """
    if Lv <= 0 or fy <= 0 or db <= 0:
        raise ValueError("Lv, fy, db must be positive")
    return 0.10 * Lv + 0.015 * fy * db


@dataclass
class TargetDisplacementCheck:
    T_eff: float           # effective period [s]
    Sd_T_eff: float        # spectral displacement [m]
    capacity: float        # available displacement capacity [m]

    @property
    def demand(self) -> float:
        return self.Sd_T_eff

    @property
    def ratio(self) -> float:
        return self.demand / self.capacity if self.capacity > 0 else float("inf")

    @property
    def ok(self) -> bool:
        return self.ratio <= 1.0


def target_displacement(T_eff: float, Sd_T_eff: float, capacity: float = float("inf")) -> TargetDisplacementCheck:
    """DCH target-displacement check (EN 1998-2 §7).

    Returns a TargetDisplacementCheck dataclass with demand/capacity and ok flag.
    """
    if T_eff <= 0:
        raise ValueError("T_eff must be > 0")
    return TargetDisplacementCheck(T_eff=T_eff, Sd_T_eff=Sd_T_eff, capacity=capacity)
