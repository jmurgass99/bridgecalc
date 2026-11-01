"""Disipador histerético — modelo Bouc-Wen-Baber-Noori (BWBN) sin pinzamiento.

Variable histerética adimensional z (|z| <= (A/(β+γ))^(1/n)), con el desplazamiento normalizado por
u_y = F_y/K₀ (Baber y Noori 1985; Bouc 1967; Wen 1976):

    dz = [A·dū − ν·(β·|dū|·|z|^(n−1)·z + γ·dū·|z|^n)] / η,    dū = du/u_y
    F  = α·K₀·u + (1 − α)·F_y·z
    ε  = Σ (1 − α)·z·dū       (energía histerética normalizada por F_y·u_y)
    ν = 1 + δ_ν·ε,  η = 1 + δ_η·ε   (degradación de rigidez y de resistencia)

Con β + γ = A = 1 la fuerza histerética tiende a F_y; β > γ da descarga más rígida que la carga y un
lazo que disipa energía. La integración es de Euler explícito con subpasos de |dū| <= 0,02.

Hasta la versión 1.0: el término de β llevaba sgn(du·z)·|du| (que es sgn(z)·du), así que la descarga
seguía la misma ley que la carga y z era función única de u — sin lazo, energía disipada nula — y z
no se normalizaba por u_y, de modo que en metros nunca pasaba de ≈ 0,07 y la fuerza se quedaba en
≈ 0,37·F_y con ductilidad 6.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

_MAX_SUBSTEP = 0.02     # |dū| máximo por subpaso de integración


@dataclass(frozen=True)
class BWBNParams:
    alpha: float = 0.1        # relación de rigidez posfluencia
    n: float = 1.0            # suavidad de la transición elástica-plástica
    beta: float = 0.5
    gamma: float = 0.5
    A: float = 1.0
    delta_nu: float = 0.0     # degradación de rigidez
    delta_eta: float = 0.0    # degradación de resistencia
    Fy_kN: float = 200.0
    K0_kN_m: float = 5000.0   # rigidez inicial

    @property
    def uy_m(self) -> float:
        return self.Fy_kN / self.K0_kN_m


def bwbn_step(u: float, u_prev: float, z_prev: float,
              eps_prev: float, p: BWBNParams, dt: float) -> tuple[float, float, float]:
    """Avanza de u_prev a u. Devuelve (F [kN], z [-], ε [-]). ``dt`` no interviene (modelo independiente de la velocidad)."""
    if p.Fy_kN <= 0 or p.K0_kN_m <= 0:
        raise ValueError("Fy_kN y K0_kN_m deben ser > 0")
    du_n = (u - u_prev) / p.uy_m
    n_sub = max(1, int(math.ceil(abs(du_n) / _MAX_SUBSTEP)))
    h = du_n / n_sub
    z, eps = z_prev, eps_prev
    for _ in range(n_sub):
        nu = 1.0 + p.delta_nu * eps
        eta = 1.0 + p.delta_eta * eps
        az = abs(z)
        zn = az ** p.n
        sgn_z = 1.0 if z > 0 else (-1.0 if z < 0 else 0.0)
        dz = (p.A * h - nu * (p.beta * abs(h) * zn * sgn_z + p.gamma * h * zn)) / max(eta, 1e-9)
        eps += (1.0 - p.alpha) * z * h
        z += dz
    F = p.alpha * p.K0_kN_m * u + (1.0 - p.alpha) * p.Fy_kN * z
    return F, z, eps


def simulate(u_history: list[float], p: BWBNParams, dt: float = 0.01) -> list[float]:
    """Fuerza para una historia de desplazamientos [m] que empieza en reposo (z = 0)."""
    z, eps = 0.0, 0.0
    forces = [p.alpha * p.K0_kN_m * u_history[0]] if u_history else []
    for i in range(1, len(u_history)):
        F, z, eps = bwbn_step(u_history[i], u_history[i - 1], z, eps, p, dt)
        forces.append(F)
    return forces


__all__ = ["BWBNParams", "bwbn_step", "simulate"]
