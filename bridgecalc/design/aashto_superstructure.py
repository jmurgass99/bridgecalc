"""
Diseño de superestructura AASHTO LRFD - Chequeos de diseño rápidos de vigas cajón.

Ecuaciones correspondientes a AASHTO LRFD Sección 5 para flexión y cortante.
Devuelve el ratio Demanda/Capacidad (DCR).
"""
from __future__ import annotations

import math


def concrete_box_girder_flexure(
    M_u_kNm: float,
    f_c_MPa: float,
    b_w_mm: float,
    d_mm: float,
    A_s_mm2: float,
    f_y_MPa: float = 500.0,
    phi: float = 0.90,
) -> float:
    """Calcula el ratio Demanda/Capacidad (DCR) a flexión para una viga cajón de hormigón armado.

    Ecuación AASHTO LRFD §5.6.3.
    """
    if M_u_kNm < 0:
        M_u_kNm = abs(M_u_kNm)
    if A_s_mm2 <= 0 or d_mm <= 0 or b_w_mm <= 0 or f_c_MPa <= 0:
        return float("inf")

    beta1 = max(0.65, min(0.85, 0.85 - 0.05 * (f_c_MPa - 28.0) / 7.0))
    # a = A_s * f_y / (0.85 * f_c * b_w)
    a = (A_s_mm2 * f_y_MPa) / (0.85 * f_c_MPa * b_w_mm)
    
    # Límite de profundidad
    if a >= d_mm:
        return float("inf")

    Mn_Nmm = A_s_mm2 * f_y_MPa * (d_mm - a / 2.0)
    Mn_kNm = Mn_Nmm * 1e-6
    Mr_kNm = phi * Mn_kNm

    if Mr_kNm <= 0:
        return float("inf")
    return M_u_kNm / Mr_kNm


def concrete_box_girder_shear(
    V_u_kN: float,
    f_c_MPa: float,
    b_w_mm: float,
    d_mm: float,
    A_v_mm2: float,
    s_mm: float,
    f_y_MPa: float = 500.0,
    phi: float = 0.90,
) -> float:
    """Calcula el ratio Demanda/Capacidad (DCR) a cortante para una viga cajón de hormigón.

    Ecuación AASHTO LRFD §5.7.3 (MCFT Simplificado).
    """
    if V_u_kN < 0:
        V_u_kN = abs(V_u_kN)
    if d_mm <= 0 or b_w_mm <= 0 or f_c_MPa <= 0:
        return float("inf")

    # dv efectivo aproximado en puentes AASHTO es max(0.9 * d, 0.72 * h) -> usamos 0.9 * d
    dv_mm = 0.9 * d_mm
    beta = 2.0
    theta_deg = 36.0

    # Vc = 0.0316 * beta * sqrt(f'c) * bv * dv [N]
    Vc_N = 0.0316 * beta * math.sqrt(f_c_MPa) * b_w_mm * dv_mm
    Vc_kN = Vc_N * 1e-3

    # Vs = Av * fy * dv * cot(theta) / s [N]
    if A_v_mm2 > 0 and s_mm > 0:
        cot_theta = 1.0 / math.tan(math.radians(theta_deg))
        Vs_N = (A_v_mm2 * f_y_MPa * dv_mm * cot_theta) / s_mm
        Vs_kN = Vs_N * 1e-3
    else:
        Vs_kN = 0.0

    Vn_max_kN = 0.25 * f_c_MPa * b_w_mm * dv_mm * 1e-3
    Vn_kN = min(Vc_kN + Vs_kN, Vn_max_kN)
    Vr_kN = phi * Vn_kN

    if Vr_kN <= 0:
        return float("inf")
    return V_u_kN / Vr_kN
