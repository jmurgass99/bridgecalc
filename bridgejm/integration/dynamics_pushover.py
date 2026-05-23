"""Bridge BridgeJm -> DynamicsJm: pushover de cepa (pier) de puente."""
from __future__ import annotations

import warnings
from dataclasses import dataclass


@dataclass(frozen=True)
class CepaPushoverInput:
    H_cepa_m: float
    D_cepa_m: float
    rho_long: float = 0.02
    fc_MPa: float = 30.0
    fy_MPa: float = 420.0
    N_axial_kN: float = 1000.0


@dataclass(frozen=True)
class CepaPushoverResult:
    Vy_kN: float
    delta_y_mm: float
    delta_u_mm: float
    mu_disp: float


def pushover_cepa(inp: CepaPushoverInput) -> CepaPushoverResult:
    try:
        from dynamicsjm.pushover import pushover_concrete_column
        res = pushover_concrete_column(
            H=inp.H_cepa_m, D=inp.D_cepa_m, rho=inp.rho_long,
            fc=inp.fc_MPa, fy=inp.fy_MPa, N=inp.N_axial_kN,
        )
        return CepaPushoverResult(res["Vy"], res["dy"], res["du"], res["mu"])
    except ImportError:
        warnings.warn("DynamicsJm no disponible - usando estimacion ATC-40")
    # ATC-40 / Priestley aproximado
    import math
    A = math.pi * (inp.D_cepa_m / 2) ** 2 * 1e6
    Mn = 0.6 * inp.fy_MPa * inp.rho_long * A * inp.D_cepa_m * 1e-6  # kNm
    Vy = Mn / inp.H_cepa_m
    Ec = 4700 * math.sqrt(inp.fc_MPa)
    Ig = math.pi * (inp.D_cepa_m * 1000) ** 4 / 64.0
    Ke = 3 * 0.35 * Ec * Ig / (inp.H_cepa_m * 1000) ** 3 / 1000  # kN/mm
    dy = Vy / Ke
    mu = 4.0
    du = mu * dy
    return CepaPushoverResult(Vy, dy, du, mu)


__all__ = ["CepaPushoverInput", "CepaPushoverResult", "pushover_cepa"]
