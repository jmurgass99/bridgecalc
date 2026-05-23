# -*- coding: utf-8 -*-
"""
Caltrans Bridge Design Practice (2015) — Design of Concrete Shear Keys
=====================================================================
Implementa las ecuaciones de capacidad al cortante y friccion interfacial
para llaves de cortante (shear keys) en estribos de puentes, bajo las
especificaciones de diseno sismico de Caltrans y AASHTO LRFD.
"""
from __future__ import annotations
import math

def shear_key_capacity(
    b_mm: float,            # Ancho de la llave de cortante (mm)
    h_mm: float,            # Peralte/largo en la seccion de friccion (mm)
    fck_MPa: float,         # Resistencia caracteristica del concreto (MPa)
    Avf_mm2: float,         # Area de acero de refuerzo de friccion (mm2)
    fyk_MPa: float,         # Limite elastico del acero (MPa)
    Pc_kN: float = 0.0,     # Carga axial de compresion en la junta (kN)
    cohesion_c_MPa: float = 0.5, # Cohesion en la junta (interfaz de concreto)
    mu_coefficient: float = 1.0, # Coeficiente de friccion interfacial (AASHTO LRFD)
    phi: float = 0.90       # Factor de reduccion Caltrans para cortante de friccion
) -> dict[str, float]:
    """Calcula la capacidad de diseno al corte de friccion de una llave de cortante.
    
    Siguiendo AASHTO LRFD §5.7.4 e instrucciones del Caltrans Bridge Design Practice (Cap 11).
    """
    Acv = b_mm * h_mm # Area de concreto de la interfaz (mm2)
    
    # 1. Fuerza de traccion del acero de friccion (N)
    T_s = Avf_mm2 * fyk_MPa
    P_c_newtons = Pc_kN * 1000.0
    
    # 2. Capacidad por friccion interfacial nominal (N)
    # V_ni = c * A_cv + mu * (A_vf * f_y + P_c)
    V_ni = cohesion_c_MPa * Acv + mu_coefficient * (T_s + P_c_newtons)
    
    # 3. Limites de capacidad (AASHTO LRFD §5.7.4.3)
    # V_ni <= min(0.25 * f'c * Acv,  10.0 * Acv) en N
    limit1 = 0.25 * fck_MPa * Acv
    limit2 = 10.0 * Acv
    V_ni_governing = min(V_ni, limit1, limit2)
    
    # 4. Capacidad de diseno reducida (kN)
    V_di = phi * V_ni_governing / 1000.0
    
    return {
        "Acv_mm2": Acv,
        "steel_force_kN": T_s / 1000.0,
        "nominal_capacity_kN": V_ni / 1000.0,
        "governing_nominal_kN": V_ni_governing / 1000.0,
        "design_capacity_kN": V_di,
        "upper_limit_1_kN": limit1 / 1000.0,
        "upper_limit_2_kN": limit2 / 1000.0,
    }
