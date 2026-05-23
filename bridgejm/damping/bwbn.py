"""Amortiguadores viscosos - modelo Bouc-Wen-Baber-Noori (BWBN).

Modelo no-lineal histeretico con degradacion de rigidez y resistencia,
y pinching. Implementa la integracion paso-a-paso para una historia de
desplazamientos dada.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp


@dataclass(frozen=True)
class BWBNParams:
    alpha: float = 0.1        # post-yield ratio
    n: float = 1.0
    beta: float = 0.5
    gamma: float = 0.5
    A: float = 1.0
    delta_nu: float = 0.0     # degradacion rigidez
    delta_eta: float = 0.0    # degradacion resistencia
    Fy_kN: float = 200.0
    K0_kN_m: float = 5000.0   # rigidez inicial


def bwbn_step(u: float, u_prev: float, z_prev: float,
              eps_prev: float, p: BWBNParams, dt: float) -> tuple[float, float, float]:
    """Avanza un paso del modelo BWBN. Devuelve (F, z, eps)."""
    nu = 1.0 + p.delta_nu * eps_prev
    eta = 1.0 + p.delta_eta * eps_prev
    du = u - u_prev
    # ecuacion de z: dz = A*du - nu*(beta*sign(du*z)*|z|^n + gamma*|z|^n*du) / eta
    sign_dz = 1.0 if du * z_prev >= 0 else -1.0
    abs_z_n = abs(z_prev) ** p.n
    dz = (p.A * du - nu * (p.beta * sign_dz * abs_z_n * abs(du) + p.gamma * abs_z_n * du)) / max(eta, 1e-9)
    z_new = z_prev + dz
    # disipacion incremental
    eps_new = eps_prev + (1.0 - p.alpha) * p.K0_kN_m * z_prev * du / max(p.Fy_kN, 1e-9)
    F = p.alpha * p.K0_kN_m * u + (1.0 - p.alpha) * p.Fy_kN * z_new
    return F, z_new, eps_new


def simulate(u_history: list[float], p: BWBNParams, dt: float = 0.01) -> list[float]:
    z, eps = 0.0, 0.0
    forces = [0.0]
    for i in range(1, len(u_history)):
        F, z, eps = bwbn_step(u_history[i], u_history[i - 1], z, eps, p, dt)
        forces.append(F)
    return forces


__all__ = ["BWBNParams", "bwbn_step", "simulate"]
