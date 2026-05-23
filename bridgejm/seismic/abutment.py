"""
Empujes sobre estribos de puente — Coulomb activo/pasivo + sísmico
Mononobe-Okabe (1929, 1926).

Pa = 0.5·γ·H²·Ka       (activo)
Pp = 0.5·γ·H²·Kp       (pasivo)
Sísmico: Mononobe-Okabe modifica Ka → Kae con kh, kv.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, radians, sin, sqrt, tan


@dataclass(frozen=True)
class AbutmentInput:
    H_m: float                # altura del muro/estribo
    gamma_kN_m3: float = 18.0
    phi_deg: float = 30.0     # ángulo fricción suelo
    delta_deg: float = 20.0   # fricción muro-suelo (≈ 2/3 phi)
    beta_deg: float = 0.0     # inclinación trasdós (0 = vertical)
    alpha_deg: float = 0.0    # inclinación talud relleno
    kh_seismic: float = 0.0   # coef. horizontal pseudoestático
    kv_seismic: float = 0.0


@dataclass(frozen=True)
class AbutmentResult:
    Ka: float
    Kp: float
    Kae: float                # con sismo
    Pa_kN_per_m: float        # activo estático
    Pae_kN_per_m: float       # activo sísmico


def coulomb_pressure(inp: AbutmentInput) -> AbutmentResult:
    phi = radians(inp.phi_deg)
    delta = radians(inp.delta_deg)
    beta = radians(inp.beta_deg)
    alpha = radians(inp.alpha_deg)

    # Coulomb Ka (activo)
    num_a = (cos(phi - beta)) ** 2
    den_a_inner = 1 + sqrt(
        sin(phi + delta) * sin(phi - alpha)
        / max(cos(delta + beta) * cos(beta - alpha), 1e-9)
    )
    den_a = (cos(beta)) ** 2 * cos(delta + beta) * den_a_inner ** 2
    Ka = num_a / max(den_a, 1e-9)

    # Coulomb Kp (pasivo)
    num_p = (cos(phi + beta)) ** 2
    den_p_inner = 1 - sqrt(
        sin(phi + delta) * sin(phi + alpha)
        / max(cos(delta - beta) * cos(beta - alpha), 1e-9)
    )
    den_p = (cos(beta)) ** 2 * cos(delta - beta) * den_p_inner ** 2
    Kp = num_p / max(den_p, 1e-9)

    # Mononobe-Okabe sísmico (ángulo de inercia sísmica psi = atan(kh/(1-kv)))
    if inp.kh_seismic != 0 or inp.kv_seismic != 0:
        psi = atan2(inp.kh_seismic, 1.0 - inp.kv_seismic)
        num_ae = (cos(phi - psi - beta)) ** 2
        # El denominador M-O lleva el MISMO factor (1+sqrt(...))^2 que Coulomb,
        # con el relleno medido respecto al ángulo de inercia psi. Omitirlo
        # sobreestima Kae ~3-4x (bug corregido).
        radicand = (sin(phi + delta) * sin(phi - psi - alpha)
                    / max(cos(delta + beta + psi) * cos(alpha - beta), 1e-9))
        den_ae_inner = 1 + sqrt(max(radicand, 0.0))
        den_ae = cos(psi) * (cos(beta)) ** 2 * cos(delta + beta + psi) * den_ae_inner ** 2
        Kae = num_ae / max(den_ae, 1e-9)
        Pae = 0.5 * inp.gamma_kN_m3 * inp.H_m ** 2 * Kae * (1 - inp.kv_seismic)
    else:
        Kae = Ka
        Pae = 0.5 * inp.gamma_kN_m3 * inp.H_m ** 2 * Ka

    Pa = 0.5 * inp.gamma_kN_m3 * inp.H_m ** 2 * Ka
    return AbutmentResult(Ka=Ka, Kp=Kp, Kae=Kae, Pa_kN_per_m=Pa,
                          Pae_kN_per_m=Pae)


__all__ = ["AbutmentInput", "AbutmentResult", "coulomb_pressure"]
