# -*- coding: utf-8 -*-
"""
AASHTO LRFD Bridge Design Specifications (9th Edition, 2020)
===========================================================
Incorpora las combinaciones de carga limite de resistencia y de servicio
y los factores de reducción de resistencia (phi) para el diseno de puentes
segun la auditoria de 757268971-CSI-BRIDGE-AASHTO-LRFD-2020.pdf.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict

# Factores de reduccion de resistencia AASHTO LRFD §5.5.4.2
RESISTANCE_FACTORS = {
    "flexure_tension_controlled_concrete": 0.90,
    "compression_controlled_spirals": 0.75,
    "compression_controlled_other": 0.75,
    "shear_normal_weight_concrete": 0.90,
    "shear_lightweight_concrete": 0.70,
    "torsion_concrete": 0.90,
    "bearing_on_concrete": 0.70,
    "tension_steel": 0.95,
}

# Factores de carga AASHTO LRFD Tabla 3.4.1-1
@dataclass(frozen=True)
class LRFDLoadCombination:
    name: str
    DC: float       # Peso propio componentes estructurales y accesorios
    DW: float       # Peso propio superficie de rodadura y servicios
    LL: float       # Carga viva de vehiculos (HL-93)
    IM: float       # Fracción de impacto dinámico
    EH: float       # Empuje horizontal de suelo
    EV: float       # Presion vertical de suelo
    WA: float       # Flujo de agua y presion de hielo

AASHTO_COMBINATIONS: Dict[str, LRFDLoadCombination] = {
    "STRENGTH_I": LRFDLoadCombination(
        name="Resistencia I (Carga viva de diseño normal sin viento)",
        DC=1.25, DW=1.50, LL=1.75, IM=1.75, EH=1.50, EV=1.35, WA=1.00
    ),
    "STRENGTH_II": LRFDLoadCombination(
        name="Resistencia II (Vehiculo de diseno especial / permisos)",
        DC=1.25, DW=1.50, LL=1.35, IM=1.35, EH=1.50, EV=1.35, WA=1.00
    ),
    "STRENGTH_III": LRFDLoadCombination(
        name="Resistencia III (Puente sometido a viento > 90 km/h sin carga viva)",
        DC=1.25, DW=1.50, LL=0.00, IM=0.00, EH=1.50, EV=1.35, WA=1.00
    ),
    "STRENGTH_V": LRFDLoadCombination(
        name="Resistencia V (Viento de 90 km/h simultaneo con carga viva)",
        DC=1.25, DW=1.50, LL=1.35, IM=1.35, EH=1.50, EV=1.35, WA=1.00
    ),
    "SERVICE_I": LRFDLoadCombination(
        name="Servicio I (Control de deflexiones y fisuracion en concreto)",
        DC=1.00, DW=1.00, LL=1.00, IM=1.00, EH=1.00, EV=1.00, WA=1.00
    ),
    "SERVICE_II": LRFDLoadCombination(
        name="Servicio II (Control de fluencia en estructuras de acero)",
        DC=1.00, DW=1.00, LL=1.30, IM=1.30, EH=1.00, EV=1.00, WA=1.00
    ),
    "SERVICE_III": LRFDLoadCombination(
        name="Servicio III (Verificacion de esfuerzos de traccion en vigas pretensadas)",
        DC=1.00, DW=1.00, LL=0.80, IM=0.80, EH=1.00, EV=1.00, WA=1.00
    )
}

def get_design_force(comb_name: str, forces: dict[str, float]) -> float:
    """Calcula el esfuerzo de diseno combinando las solicitaciones.
    
    forces = {"DC": X, "DW": Y, "LL_IM": Z, "EH": W, "EV": K, "WA": V}
    """
    comb = AASHTO_COMBINATIONS.get(comb_name)
    if not comb:
        raise ValueError(f"Combinación {comb_name} no disponible.")
    
    total = (
        comb.DC * forces.get("DC", 0.0) +
        comb.DW * forces.get("DW", 0.0) +
        comb.LL * forces.get("LL_IM", 0.0) +
        comb.EH * forces.get("EH", 0.0) +
        comb.EV * forces.get("EV", 0.0) +
        comb.WA * forces.get("WA", 0.0)
    )
    return total
