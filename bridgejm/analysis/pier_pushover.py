"""
Pushover de cepa simple — modelo SDOF con idealizacion bilineal.

Genera la curva V_base vs Delta_top para una cepa RC empotrada en
la base, libre en el tope (cantilever), y produce la idealizacion
bilineal por el criterio de igual energia (equal energy).

Ductilidad: mu = Delta_u / Delta_y

Modelo de seccion:
  - Seccion rectangular o circular RC
  - Momento-curvatura simplificado (Priestley et al., 2007)
  - Relacion M-phi bilineal con curvatura de fluencia y ultima

Referencia:
  Priestley, M.J.N., Calvi, G.M., Kowalsky, M.J. (2007).
  Displacement-Based Seismic Design of Structures. IUSS Press.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np


@dataclass(frozen=True)
class PierPushoverInput:
    """Datos de entrada para pushover de cepa."""
    H_m: float                      # altura de la cepa [m]
    B_m: float                      # ancho de la seccion [m]
    D_m: float | None = None        # profundidad (si None, seccion cuadrada B x B)
    fc_MPa: float = 30.0            # resistencia del concreto
    fy_MPa: float = 420.0           # fluencia del acero
    rho_long: float = 0.02          # cuantia longitudinal
    N_axial_kN: float = 1000.0      # carga axial
    cover_m: float = 0.05           # recubrimiento
    section_type: str = "rectangular"  # "rectangular" o "circular"
    phi_u_factor: float = 10.0      # phi_u / phi_y (ductilidad de curvatura)
    n_points: int = 50              # puntos de la curva pushover


@dataclass(frozen=True)
class BilinearCurve:
    """Idealizacion bilineal de la curva pushover."""
    Vy_kN: float                    # cortante de fluencia
    delta_y_mm: float               # desplazamiento de fluencia
    Vu_kN: float                    # cortante ultimo
    delta_u_mm: float               # desplazamiento ultimo
    mu_displacement: float          # ductilidad de desplazamiento
    Ke_kN_per_mm: float             # rigidez elastica
    energy_kNmm: float              # energia (area bajo curva)

    def to_dict(self) -> dict[str, Any]:
        return {
            "Vy_kN": self.Vy_kN,
            "delta_y_mm": self.delta_y_mm,
            "Vu_kN": self.Vu_kN,
            "delta_u_mm": self.delta_u_mm,
            "mu_displacement": self.mu_displacement,
            "Ke_kN_per_mm": self.Ke_kN_per_mm,
            "energy_kNmm": self.energy_kNmm,
        }


@dataclass(frozen=True)
class PierPushoverResult:
    """Resultado completo del pushover."""
    delta_mm: np.ndarray            # vector de desplazamientos [mm]
    V_base_kN: np.ndarray           # vector de cortante basal [kN]
    bilinear: BilinearCurve
    My_kNm: float                   # momento de fluencia
    Mu_kNm: float                   # momento ultimo
    phi_y: float                    # curvatura de fluencia [1/m]
    phi_u: float                    # curvatura ultima [1/m]
    Lp_m: float                     # longitud de rotula plastica

    def to_dict(self) -> dict[str, Any]:
        return {
            "delta_mm": self.delta_mm.tolist(),
            "V_base_kN": self.V_base_kN.tolist(),
            "bilinear": self.bilinear.to_dict(),
            "My_kNm": self.My_kNm,
            "Mu_kNm": self.Mu_kNm,
            "phi_y": self.phi_y,
            "phi_u": self.phi_u,
            "Lp_m": self.Lp_m,
        }


def _section_properties(inp: PierPushoverInput) -> tuple[float, float, float]:
    """Calcula area, inercia efectiva y profundidad efectiva."""
    D = inp.D_m if inp.D_m is not None else inp.B_m

    if inp.section_type == "circular":
        A_gross = math.pi * (D / 2) ** 2
        I_gross = math.pi * D ** 4 / 64.0
        d_eff = D - 2 * inp.cover_m
    else:
        A_gross = inp.B_m * D
        I_gross = inp.B_m * D ** 3 / 12.0
        d_eff = D - 2 * inp.cover_m

    return A_gross, I_gross, d_eff


def _moment_curvature(inp: PierPushoverInput) -> tuple[float, float, float, float]:
    """Estima My, Mu, phi_y, phi_u simplificados (Priestley 2007).

    Returns (My_kNm, Mu_kNm, phi_y [1/m], phi_u [1/m])
    """
    D = inp.D_m if inp.D_m is not None else inp.B_m
    A_gross, I_gross, d_eff = _section_properties(inp)

    # Area de acero
    As = inp.rho_long * A_gross  # m^2

    # Momento de fluencia simplificado (Priestley 2007)
    # F_steel = As [m^2] * fy [MPa] * 1000 [kN/m^2 / MPa] = kN
    # My = 0.9 * F_steel * d_eff + contribucion axial
    fy = inp.fy_MPa
    F_steel_kN = As * fy * 1000.0  # kN
    My = 0.9 * F_steel_kN * d_eff + 0.1 * inp.N_axial_kN * D

    # Momento ultimo (con endurecimiento ~10%)
    Mu = 1.10 * My

    # Curvatura de fluencia (Priestley 2007, ss4.4)
    # phi_y = 2.25 * eps_y / D  para seccion rectangular
    # phi_y = 2.35 * eps_y / D  para seccion circular
    eps_y = fy / (200_000.0)  # deformacion de fluencia del acero
    if inp.section_type == "circular":
        phi_y = 2.35 * eps_y / D
    else:
        phi_y = 2.25 * eps_y / D

    # Curvatura ultima
    phi_u = inp.phi_u_factor * phi_y

    return My, Mu, phi_y, phi_u


def _plastic_hinge_length(H: float, D: float, fy: float,
                            db_est_m: float = 0.025) -> float:
    """Longitud de rotula plastica (Priestley 2007, Eq. 4.31).

    Lp = 0.08*H + 0.022*fy*db  (fy en MPa, db en m -> Lp en m)
    """
    Lp = 0.08 * H + 0.022 * fy * db_est_m * 1000.0 / 1000.0
    # Minimo: 2 veces el diametro de la barra
    Lp = max(Lp, 2 * db_est_m)
    return Lp


def pier_pushover_sdof(inp: PierPushoverInput) -> PierPushoverResult:
    """Genera la curva pushover V_base vs Delta_top para cepa cantilever.

    El modelo es SDOF (grado de libertad unico) con la masa concentrada
    en el tope de la cepa.
    """
    H = inp.H_m
    if H <= 0 or inp.B_m <= 0:
        raise ValueError("H_m y B_m deben ser > 0")

    D = inp.D_m if inp.D_m is not None else inp.B_m
    My, Mu, phi_y, phi_u = _moment_curvature(inp)
    Lp = _plastic_hinge_length(H, D, inp.fy_MPa)

    # Cortante basal de fluencia y ultimo
    Vy = My / H
    Vu = Mu / H

    # Desplazamiento de fluencia (integracion de curvatura)
    # delta_y = phi_y * H^2 / 3  (cantilever con curvatura uniforme ~ lineal)
    delta_y = phi_y * H ** 2 / 3.0  # m

    # Desplazamiento ultimo (con rotula plastica)
    # delta_u = delta_y + (phi_u - phi_y) * Lp * (H - 0.5*Lp)
    theta_p = (phi_u - phi_y) * Lp
    delta_p = theta_p * (H - 0.5 * Lp)
    delta_u = delta_y + delta_p  # m

    # Convertir a mm
    delta_y_mm = delta_y * 1000.0
    delta_u_mm = delta_u * 1000.0

    # Generar curva pushover (trilineal: origen -> yield -> ultimate)
    n = inp.n_points
    n_elastic = n // 2
    n_plastic = n - n_elastic

    delta_elastic = np.linspace(0, delta_y_mm, n_elastic, endpoint=False)
    V_elastic = (Vy / delta_y_mm) * delta_elastic

    delta_plastic = np.linspace(delta_y_mm, delta_u_mm, n_plastic)
    V_plastic = Vy + (Vu - Vy) * (delta_plastic - delta_y_mm) / max(
        delta_u_mm - delta_y_mm, 1e-10
    )

    delta_mm = np.concatenate([delta_elastic, delta_plastic])
    V_base_kN = np.concatenate([V_elastic, V_plastic])

    # Idealizacion bilineal
    bilinear = bilinear_idealization(delta_mm, V_base_kN)

    return PierPushoverResult(
        delta_mm=delta_mm,
        V_base_kN=V_base_kN,
        bilinear=bilinear,
        My_kNm=My,
        Mu_kNm=Mu,
        phi_y=phi_y,
        phi_u=phi_u,
        Lp_m=Lp,
    )


def bilinear_idealization(
    delta_mm: np.ndarray | Sequence[float],
    V_kN: np.ndarray | Sequence[float],
) -> BilinearCurve:
    """Idealizacion bilineal por criterio de igual energia (equal energy).

    Encuentra Vy, delta_y tales que el area bajo la recta bilineal
    iguala el area bajo la curva pushover real.

    El punto ultimo se define como el ultimo punto de la curva.
    """
    d = np.asarray(delta_mm, dtype=float)
    V = np.asarray(V_kN, dtype=float)
    if len(d) < 2:
        raise ValueError("Se requieren al menos 2 puntos")

    delta_u = float(d[-1])
    Vu = float(V[-1])

    # Area bajo la curva (trapezoidal)
    E_total = float(np.trapezoid(V, d))

    # Bilineal: rampa elastica 0->Vy en 0->delta_y, luego
    # horizontal (o pendiente post-yield) Vy->Vu en delta_y->delta_u
    # Area bilineal = 0.5*Vy*delta_y + 0.5*(Vy+Vu)*(delta_u - delta_y)
    # Igualando a E_total:
    # E_total = 0.5*Vy*delta_y + 0.5*(Vy+Vu)*(delta_u - delta_y)
    # Si asumimos Vy = Vu (perfectamente plastico):
    #   E = Vy * (delta_u - delta_y/2)
    #   Vy = E_total / (delta_u - delta_y/2)
    # Pero necesitamos tambien la rigidez inicial. Usamos la pendiente
    # secante al 70% del cortante maximo.
    V_max = float(np.max(V))
    V_70 = 0.70 * V_max
    idx_70 = int(np.argmin(np.abs(V - V_70)))
    if d[idx_70] > 0:
        Ke = V[idx_70] / d[idx_70]  # kN/mm
    else:
        Ke = V[1] / max(d[1], 1e-10)

    # Vy por equal energy con pendiente post-yield
    # Area bilineal = 0.5*Vy*(Vy/Ke) + 0.5*(Vy+Vu)*(delta_u - Vy/Ke)
    # = Vy^2/(2*Ke) + 0.5*(Vy+Vu)*delta_u - 0.5*(Vy+Vu)*Vy/Ke
    # = Vy^2/(2*Ke) + 0.5*Vy*delta_u + 0.5*Vu*delta_u
    #   - 0.5*Vy^2/Ke - 0.5*Vu*Vy/Ke
    # = -Vy^2/(2*Ke) + 0.5*Vy*delta_u + 0.5*Vu*delta_u - 0.5*Vu*Vy/Ke
    # Solve for Vy: quadratic
    # -Vy^2/(2*Ke) + Vy*(0.5*delta_u - 0.5*Vu/Ke) + 0.5*Vu*delta_u - E_total = 0
    # Vy^2/(2*Ke) - Vy*(0.5*delta_u - 0.5*Vu/Ke) - 0.5*Vu*delta_u + E_total = 0
    a_coef = 1.0 / (2.0 * float(Ke))
    b_coef = -(0.5 * delta_u - 0.5 * Vu / float(Ke))
    c_coef = -0.5 * Vu * delta_u + E_total

    disc = b_coef ** 2 - 4 * a_coef * c_coef
    if disc >= 0:
        Vy = (-b_coef - math.sqrt(disc)) / (2 * a_coef)
        if Vy <= 0:
            Vy = (-b_coef + math.sqrt(disc)) / (2 * a_coef)
    else:
        # Fallback: V promedio
        Vy = E_total / delta_u

    Vy = max(Vy, 0.01)
    delta_y = Vy / float(Ke) if Ke > 0 else delta_u * 0.1

    mu = delta_u / max(delta_y, 1e-10)

    return BilinearCurve(
        Vy_kN=float(Vy),
        delta_y_mm=float(delta_y),
        Vu_kN=float(Vu),
        delta_u_mm=float(delta_u),
        mu_displacement=float(mu),
        Ke_kN_per_mm=float(Ke),
        energy_kNmm=float(E_total),
    )


__all__ = [
    "PierPushoverInput", "PierPushoverResult", "BilinearCurve",
    "pier_pushover_sdof", "bilinear_idealization",
]
