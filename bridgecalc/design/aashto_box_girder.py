"""
Diseño de cajón de hormigón pretensado — AASHTO LRFD (9ª ed.).

Cubre las verificaciones de superestructura del manual CSiBridge AASHTO 2020:
  - Flexión §5.6.3  : Mn de sección pretensada+pasiva, Mr = phi·Mn.
  - Cortante §5.7   : MCFT simplificado, Vn = Vc + Vs <= 0.25 f'c bv dv.
  - Tensión principal §5.9.2.3.3 : control de tracción principal en el alma.

Unidades: N, mm, MPa (coherentes). Momentos en kN·m, cortantes en kN al reportar.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class BoxGirderSection:
    fc_MPa: float                 # resistencia del hormigón f'c
    bv_mm: float                  # ancho efectivo del alma a cortante (suma de almas)
    dv_mm: float                  # canto efectivo de cortante
    b_flange_mm: float            # ancho del ala comprimida
    Aps_mm2: float = 0.0          # área de acero de pretensado
    fpu_MPa: float = 1860.0       # resistencia del cordón
    dp_mm: float = 0.0            # canto útil del pretensado
    As_mm2: float = 0.0           # acero pasivo a tracción
    fy_MPa: float = 500.0
    ds_mm: float = 0.0            # canto útil del pasivo


@dataclass(frozen=True)
class FlexureResult:
    Mn_kNm: float
    Mr_kNm: float
    a_mm: float
    fps_MPa: float
    ok: bool


def flexural_strength(sec: BoxGirderSection, Mu_kNm: float, phi: float = 1.0) -> FlexureResult:
    """Momento resistente a flexión (AASHTO §5.6.3.1, sección rectangular/T comprimida).

    fps por la aproximación §5.6.3.1.1: fps = fpu·(1 − k·c/dp), k=0.28 (baja relajación).
    """
    fc, b = sec.fc_MPa, sec.b_flange_mm
    k = 0.28
    beta1 = max(0.65, min(0.85, 0.85 - 0.05 * (fc - 28.0) / 7.0))
    dp = sec.dp_mm or sec.ds_mm
    # c por equilibrio (iteración cerrada para sección rectangular):
    # c = (Aps fpu + As fy) / (0.85 f'c beta1 b + k Aps fpu/dp)
    num = sec.Aps_mm2 * sec.fpu_MPa + sec.As_mm2 * sec.fy_MPa
    den = 0.85 * fc * beta1 * b + (k * sec.Aps_mm2 * sec.fpu_MPa / dp if dp else 0.0)
    c = num / den if den else 0.0
    fps = sec.fpu_MPa * (1.0 - k * c / dp) if dp else 0.0
    a = beta1 * c
    Mn_Nmm = (sec.Aps_mm2 * fps * (sec.dp_mm - a / 2.0)
              + sec.As_mm2 * sec.fy_MPa * (sec.ds_mm - a / 2.0))
    Mn = Mn_Nmm * 1e-6
    Mr = phi * Mn
    return FlexureResult(Mn_kNm=Mn, Mr_kNm=Mr, a_mm=a, fps_MPa=fps, ok=Mr >= Mu_kNm)


@dataclass(frozen=True)
class ShearResult:
    Vc_kN: float
    Vs_kN: float
    Vn_kN: float
    Vr_kN: float
    Vmax_kN: float
    ok: bool


def shear_strength(sec: BoxGirderSection, Vu_kN: float, Av_mm2: float, s_mm: float,
                   beta: float = 2.0, theta_deg: float = 36.0, phi: float = 0.90) -> ShearResult:
    """Resistencia a cortante (AASHTO §5.7.3, MCFT simplificado).

    Vc = 0.083·beta·sqrt(f'c)·bv·dv [N, MPa, mm] ; Vs = Av·fy·dv·cot(theta)/s ;
    Vn = min(Vc+Vs, 0.25 f'c bv dv). beta y theta del método simplificado.

    0.083 es el coeficiente SI de la Ec. 5.7.3.3-3 (0.0316 con f'c en ksi y medidas en pulgadas).
    Hasta la versión 1.0 se usaba 0.0316 con f'c en MPa: V_c salía 2,63 veces menor.
    """
    fc, bv, dv = sec.fc_MPa, sec.bv_mm, sec.dv_mm
    Vc = 0.083 * beta * math.sqrt(fc) * bv * dv           # N
    cot = 1.0 / math.tan(math.radians(theta_deg))
    Vs = (Av_mm2 * sec.fy_MPa * dv * cot / s_mm) if s_mm else 0.0
    Vmax = 0.25 * fc * bv * dv
    Vn = min(Vc + Vs, Vmax)
    Vr = phi * Vn
    return ShearResult(Vc_kN=Vc / 1e3, Vs_kN=Vs / 1e3, Vn_kN=Vn / 1e3,
                       Vr_kN=Vr / 1e3, Vmax_kN=Vmax / 1e3, ok=Vr >= Vu_kN)


@dataclass(frozen=True)
class PrincipalStressResult:
    sigma_principal_MPa: float
    limit_MPa: float
    ok: bool


def principal_stress_web(fpc_MPa: float, v_MPa: float, fc_MPa: float,
                         factor: float = 0.29) -> PrincipalStressResult:
    """Tracción principal en el alma (AASHTO §5.9.2.3.3 para Service III en segmentales).

    sigma_1 = fpc/2 − sqrt((fpc/2)^2 + v^2)  (tracción negativa).
    Límite de tracción principal 0.29·sqrt(f'c) MPa (0.110·sqrt(f'c) con f'c en ksi). fpc = compresión
    axial neta (>0). Hasta la versión 1.0 el factor por defecto era 0.110 aplicado a f'c en MPa, un
    límite 2,63 veces más estricto que el de la norma.
    """
    half = fpc_MPa / 2.0
    sigma_1 = half - math.sqrt(half ** 2 + v_MPa ** 2)     # negativo = tracción
    limit = -factor * math.sqrt(fc_MPa)                    # tracción admisible (negativa)
    ok = sigma_1 >= limit                                  # menos traccionado que el límite
    return PrincipalStressResult(sigma_principal_MPa=sigma_1, limit_MPa=limit, ok=ok)


__all__ = [
    "BoxGirderSection", "FlexureResult", "ShearResult", "PrincipalStressResult",
    "flexural_strength", "shear_strength", "principal_stress_web",
]
