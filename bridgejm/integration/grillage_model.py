"""
bridgejm.integration.grillage_model — Emparrillado de puente verificado para SAP2000/CSiBridge.

Implementa la generacion parametrica y fisicamente consistente de un tablero de puente
mediante modelo de emparrillado (grillage: vigas longitudinales L* x diafragmas T*):
1. Conexion trazable desde un ``Encargo`` ejecutable (``bridge_spec_from_encargo``) hacia
   ``BridgeDesignSpec`` sin inventar parametros silenciosos.
2. Materiales y secciones reales del catalogo oficial (``fastsap.section_catalog``,
   EN 10365 / AISC) con todas sus propiedades mecanicas completas (A, I33, I22, J,
   Av2, Av3, Wel33, Wpl33 > 0), eliminando etiquetas huerfanas ("GIRDER"/"DIAPHRAGM").
3. Esquema de aparatos de apoyo cinematica y estaticamente determinado en 3D
   (6 GDL globales: sum_Fx, sum_Fy, sum_Fz, sum_Mx, sum_My, sum_Mz), con estribo fijo
   en x=0 y estribo/pilas moviles en x>0 (dilatacion longitudinal Ux=0 libre y guia
   transversal Uy=1 en el apoyo guia ig=0).
4. Cargas de puente reales: peso propio + losa (DEAD), pavimento y barreras (DW),
   sobrecarga distribuida de carril (LIVE_LANE) y tren de cargas de diseno
   (HL-93 AASHTO LRFD §3.6.1 con impacto IM=1.33, o LM1 EN 1991-2 §4.3.2) en
   posiciones longitudinales criticas de momento positivo (LIVE_VEHICLE_M) y
   cortante en apoyo (LIVE_VEHICLE_V), mas combinaciones ELU/ELS.
5. Verificacion estricta de todos los codigos de retorno OAPI (ret != 0 lanza
   ``OAPICallError``) y declaracion explicita de limitaciones del modelo y estados
   limite no implementados en ``meta``.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
import os
import re
from typing import Any

from fastsap.section_catalog import IShape, get_section
from fastsap.utils import csi_enum
from jmstructural_common.audit_status import (
    CalculationStatus,
    aggregate_calculation_statuses,
    resolve_status,
)
from ..ec1_traffic import LM1, traffic_envelope_lm1
from ..loads.en1990_combinations import GAMMA_G_SUP
from ..loads.hl93 import (
    HL93Configuration,
    LANE_LOAD_kN_per_m,
    TRUCK_AXLE_SPACINGS_m,
    TRUCK_AXLES_kN,
    hl93_envelope,
)
from ..loads.load_combinations import gamma as aashto_gamma

# Factor parcial para trafico rodado LM1 en puentes segun EN 1990 Anexo A2 Tabla A2.4(B)
EN1990_A2_GAMMA_Q_TRAFFIC = 1.35

# Carga de carril HL-93 (AASHTO LRFD 3.6.1.2.4): 9.3 kN/m por carril de diseno.
HL93_LANE_LOAD_KN_M = LANE_LOAD_kN_per_m

# Escalera de perfiles laminados europeos EN 10365 para vigas principales y diafragmas
BRIDGE_STEEL_GIRDER_LADDER: tuple[str, ...] = (
    "HEB 500",
    "HEB 550",
    "HEB 600",
    "HEB 650",
    "HEB 700",
    "HEB 800",
    "HEB 900",
    "HEB 1000",
    "HEM 900",
    "HEM 1000",
)

# Serie determinista de vigas armadas soldadas (Plate Girders) doblemente simetricas
# PG_{h_mm}x{b_mm}x{tf_mm}x{tw_mm}: (h_m, b_m, tf_m, tw_m)
# Proporciones esbeltas compactas (Clase 1/2 en flexion segun EN 1993-1-1 Tabla 5.2 y
# AASHTO LRFD §6.10.2: b_f/(2*t_f) <= 6.8, D/t_w <= 68, b_f >= D/4, t_f >= 1.1*t_w).
BRIDGE_PLATE_GIRDER_SPECS: dict[str, tuple[float, float, float, float]] = {
    "PG_1300x500x35x22": (1.300, 0.500, 0.035, 0.022),
    "PG_1500x550x40x24": (1.500, 0.550, 0.040, 0.024),
    "PG_1700x600x45x26": (1.700, 0.600, 0.045, 0.026),
    "PG_1900x650x50x28": (1.900, 0.650, 0.050, 0.028),
    "PG_2100x700x55x30": (2.100, 0.700, 0.055, 0.030),
    "PG_2300x750x60x32": (2.300, 0.750, 0.060, 0.032),
    "PG_2500x800x65x35": (2.500, 0.800, 0.065, 0.035),
}

# Escalera completa de redimensionamiento para vigas principales: laminados EN 10365 + serie armada PG_*
BRIDGE_FULL_GIRDER_LADDER: tuple[str, ...] = BRIDGE_STEEL_GIRDER_LADDER + tuple(
    BRIDGE_PLATE_GIRDER_SPECS.keys()
)

# Escalera de perfiles para diafragmas transversales T*
BRIDGE_DIAPHRAGM_LADDER: tuple[str, ...] = (
    "HEB 400",
    "HEB 500",
    "HEB 600",
    "HEB 700",
    "HEB 800",
    "HEM 800",
    "HEM 1000",
)


class OAPICallError(RuntimeError):
    """Error lanzado cuando cualquier llamada OAPI de SAP2000/CSiBridge devuelve ret != 0."""


def _check_ret(op: str, ret: Any) -> None:
    """Verifica estrictamente el retorno de una llamada OAPI CSI (ret == 0).

    En pythonnet 3 las llamadas OAPI con parámetros ``ref``/``out`` devuelven
    ``(ret, *out_values)`` con el código entero ``ret`` en la primera posición ``[0]``.
    """
    if isinstance(ret, (tuple, list)):
        rc = ret[0] if ret else 1
    else:
        rc = ret
    if rc != 0:
        raise OAPICallError(f"Llamada OAPI '{op}' falló con ret={ret!r} (código={rc!r})")


@dataclass(frozen=True)
class MaterialSpec:
    """Especificacion trazable de material estructural para el modelo de puente."""
    name: str
    material_type: str          # "steel" (SAP eMatType=1) | "concrete" (SAP eMatType=2)
    sap_mat_type: int           # 1 = Steel, 2 = Concrete
    E_kPa: float                # Modulo de elasticidad en kPa (kN/m^2)
    nu: float                   # Coeficiente de Poisson
    alpha_thermal: float        # Coeficiente de dilatacion termica (1/K)
    gamma_kN_m3: float          # Peso especifico (kN/m^3)
    fy_MPa: float               # Limite elastico fy (acero) o fck (hormigon) en MPa
    fu_MPa: float               # Tension de rotura fu (acero) o fcd/fctm ref en MPa
    norm_ref: str
    source: str
    units: dict[str, str] = field(default_factory=lambda: {
        "E": "kPa",
        "gamma": "kN/m3",
        "fy": "MPa",
        "fu": "MPa",
    })

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SectionMechanicalProps:
    """Propiedades geometricas y mecanicas completas de una seccion de viga o diafragma."""
    name: str
    shape: str                  # "I" | "RECT"
    material_name: str
    h_m: float                  # Canto total t3 (m)
    b_m: float                  # Ancho de ala t2 (m)
    tf_m: float                 # Espesor de ala tf (m)
    tw_m: float                 # Espesor de alma tw (m)
    r_m: float                  # Radio de acuerdo (m)
    A_m2: float                 # Area total (m^2)
    I33_m4: float               # Inercia eje fuerte local 3-3 (Iy en EN 10365) (m^4)
    I22_m4: float               # Inercia eje debil local 2-2 (Iz en EN 10365) (m^4)
    J_m4: float                 # Modulo de torsion uniforme de Saint-Venant It (m^4)
    Av2_m2: float               # Area de cortante vertical paralela al alma (eje 2) (m^2)
    Av3_m2: float               # Area de cortante transversal paralela a las alas (eje 3) (m^2)
    Wel33_m3: float             # Modulo resistente elastico eje fuerte (m^3)
    Wpl33_m3: float             # Modulo resistente plastico eje fuerte (m^3)
    mass_kg_m: float            # Masa lineal (kg/m)
    source: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BridgeDesignSpec:
    """Especificacion completa y trazable para el emparrillado de puente."""
    span_m: float
    width_m: float
    n_spans: int
    n_girders: int
    n_diaphragms: int
    n_lanes: int
    norma: str                  # "EN_1991_2" | "AASHTO_LRFD"
    uso: str
    apoyos_desc: str
    galibo_m: float
    acciones_desc: str
    slab_thickness_m: float
    wearing_surface_kPa: float
    barrier_load_kN_m_total: float
    material: MaterialSpec
    girder_section: SectionMechanicalProps
    diaphragm_section: SectionMechanicalProps
    predimensioning_trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def plate_girder_section_props(
    profile_name: str,
    h_m: float,
    b_m: float,
    tf_m: float,
    tw_m: float,
    material_name: str = "S355",
) -> SectionMechanicalProps:
    """Calcula las propiedades geometricas y mecanicas exactas de una viga armada soldada (Plate Girder)
    doblemente simetrica (r = 0), identicas a la formulacion interna de ``SAP2000 PropFrame.SetISection``:
    ``A = 2*b*tf + (h-2*tf)*tw``, ``I33``, ``I22``, ``J``, ``Av2 = h*tw``, ``Av3 = (5/6)*2*b*tf``,
    ``Wel33``, ``Wpl33``.
    """
    if h_m <= 2.0 * tf_m or b_m <= tw_m or tf_m <= 0 or tw_m <= 0:
        raise ValueError(
            f"Dimensiones invalidas para viga armada {profile_name!r}: "
            f"h={h_m}, b={b_m}, tf={tf_m}, tw={tw_m}"
        )
    hw = h_m - 2.0 * tf_m
    area = 2.0 * b_m * tf_m + hw * tw_m
    i33 = (b_m * (h_m ** 3) - (b_m - tw_m) * (hw ** 3)) / 12.0
    i22 = (2.0 * tf_m * (b_m ** 3) + hw * (tw_m ** 3)) / 12.0
    j_tors = (2.0 * b_m * (tf_m ** 3) + hw * (tw_m ** 3)) / 3.0
    av2 = h_m * tw_m
    av3 = (5.0 / 6.0) * (2.0 * b_m * tf_m)
    wel33 = i33 / (0.5 * h_m)
    wpl33 = b_m * tf_m * (h_m - tf_m) + 0.25 * tw_m * (hw ** 2)
    return SectionMechanicalProps(
        name=profile_name,
        shape="I",
        material_name=material_name,
        h_m=round(h_m, 6),
        b_m=round(b_m, 6),
        tf_m=round(tf_m, 6),
        tw_m=round(tw_m, 6),
        r_m=0.0,
        A_m2=round(area, 8),
        I33_m4=round(i33, 8),
        I22_m4=round(i22, 8),
        J_m4=round(j_tors, 8),
        Av2_m2=round(av2, 8),
        Av3_m2=round(av3, 8),
        Wel33_m3=round(wel33, 8),
        Wpl33_m3=round(wpl33, 8),
        mass_kg_m=round(area * 7850.0, 4),
        source="Serie determinista de vigas armadas soldadas (EN 1993-1-5 / AASHTO LRFD §6.10)",
    )


def section_props_from_catalog(profile_name: str, material_name: str = "S355") -> SectionMechanicalProps:
    """Obtiene propiedades mecanicas completas desde ``fastsap.section_catalog`` o de la serie
    determinista de vigas armadas soldadas ``PG_{h_mm}x{b_mm}x{tf_mm}x{tw_mm}``.
    """
    norm_name = profile_name.strip()
    if norm_name in BRIDGE_PLATE_GIRDER_SPECS:
        h_m, b_m, tf_m, tw_m = BRIDGE_PLATE_GIRDER_SPECS[norm_name]
        return plate_girder_section_props(norm_name, h_m, b_m, tf_m, tw_m, material_name=material_name)
    m_pg = re.match(r"^PG_(\d+)x(\d+)x(\d+)x(\d+)$", norm_name, re.I)
    if m_pg:
        h_m = float(m_pg.group(1)) / 1000.0
        b_m = float(m_pg.group(2)) / 1000.0
        tf_m = float(m_pg.group(3)) / 1000.0
        tw_m = float(m_pg.group(4)) / 1000.0
        return plate_girder_section_props(norm_name, h_m, b_m, tf_m, tw_m, material_name=material_name)

    sec = get_section(norm_name)
    if not isinstance(sec, IShape):
        raise ValueError(f"Se esperaba un perfil doble T (IShape) para {profile_name!r}, recibido {type(sec).__name__}")
    # Area de cortante vertical según EN 1993-1-1 §6.2.6(3): Av2 >= h * tw
    av2 = sec.h * sec.tw
    # Area de cortante horizontal en las dos alas: Av3 = (5/6) * (2 * b * tf)
    av3 = (5.0 / 6.0) * (2.0 * sec.b * sec.tf)
    return SectionMechanicalProps(
        name=sec.name,
        shape="I",
        material_name=material_name,
        h_m=round(sec.h, 6),
        b_m=round(sec.b, 6),
        tf_m=round(sec.tf, 6),
        tw_m=round(sec.tw, 6),
        r_m=round(sec.r, 6),
        A_m2=round(sec.A_exact, 8),
        I33_m4=round(sec.Iy_exact, 8),
        I22_m4=round(sec.Iz_exact, 8),
        J_m4=round(sec.It, 8),
        Av2_m2=round(av2, 8),
        Av3_m2=round(av3, 8),
        Wel33_m3=round(sec.Wel_y, 8),
        Wpl33_m3=round(sec.Wpl_y, 8),
        mass_kg_m=round(sec.mass_kg_m, 4),
        source="fastsap.section_catalog (EN 10365:2017 / AISC v15 / Euro.xml)",
    )


def rectangular_concrete_section_props(
    name: str, h_m: float, b_m: float, material_name: str = "C35/45"
) -> SectionMechanicalProps:
    """Calcula las propiedades mecanicas exactas de una seccion rectangular de hormigon."""
    if h_m <= 0 or b_m <= 0:
        raise ValueError("h_m y b_m deben ser > 0")
    area = b_m * h_m
    i33 = b_m * (h_m ** 3) / 12.0
    i22 = h_m * (b_m ** 3) / 12.0
    a_long = max(h_m, b_m)
    b_short = min(h_m, b_m)
    beta_j = 1.0 / 3.0 - 0.21 * (b_short / a_long) * (1.0 - (b_short ** 4) / (12.0 * (a_long ** 4)))
    j_tors = beta_j * a_long * (b_short ** 3)
    av2 = (5.0 / 6.0) * area
    av3 = (5.0 / 6.0) * area
    wel33 = b_m * (h_m ** 2) / 6.0
    wpl33 = b_m * (h_m ** 2) / 4.0
    return SectionMechanicalProps(
        name=name,
        shape="RECT",
        material_name=material_name,
        h_m=round(h_m, 6),
        b_m=round(b_m, 6),
        tf_m=round(h_m, 6),
        tw_m=round(b_m, 6),
        r_m=0.0,
        A_m2=round(area, 8),
        I33_m4=round(i33, 8),
        I22_m4=round(i22, 8),
        J_m4=round(j_tors, 8),
        Av2_m2=round(av2, 8),
        Av3_m2=round(av3, 8),
        Wel33_m3=round(wel33, 8),
        Wpl33_m3=round(wpl33, 8),
        mass_kg_m=round(area * 2500.0, 4),
        source="Predimensionamiento analitico seccion rectangular EC2 / AASHTO",
    )


def default_bridge_material(material_desc: str = "acero", norma: str = "EN_1991_2") -> MaterialSpec:
    """Devuelve la especificacion de material trazable a la norma y descripcion declaradas."""
    desc_low = material_desc.lower()
    norm_up = norma.upper()
    if "hormig" in desc_low:
        return MaterialSpec(
            name="C35/45",
            material_type="concrete",
            sap_mat_type=2,
            E_kPa=34_000_000.0,
            nu=0.20,
            alpha_thermal=1.0e-5,
            gamma_kN_m3=25.0,
            fy_MPa=35.0,
            fu_MPa=45.0,
            norm_ref="EN 1992-1-1 Tabla 3.1 (C35/45)",
            source=f"Encargo material={material_desc!r}",
        )
    if "AASHTO" in norm_up or "CCP" in norm_up or "NSR" in norm_up:
        return MaterialSpec(
            name="A992_Fy345",
            material_type="steel",
            sap_mat_type=1,
            E_kPa=200_000_000.0,
            nu=0.30,
            alpha_thermal=1.17e-5,
            gamma_kN_m3=78.5,
            fy_MPa=345.0,
            fu_MPa=450.0,
            norm_ref="AASHTO LRFD §6.4.1 / ASTM A709 Gr. 50 (A992)",
            source=f"Encargo material={material_desc!r}, norma={norma!r}",
        )
    return MaterialSpec(
        name="S355",
        material_type="steel",
        sap_mat_type=1,
        E_kPa=210_000_000.0,
        nu=0.30,
        alpha_thermal=1.2e-5,
        gamma_kN_m3=78.5,
        fy_MPa=355.0,
        fu_MPa=510.0,
        norm_ref="EN 1993-1-1 Tabla 3.1 / EN 10025-2 (S355)",
        source=f"Encargo material={material_desc!r}, norma={norma!r}",
    )


def select_bridge_sections(
    span_m: float,
    material: MaterialSpec,
) -> tuple[SectionMechanicalProps, SectionMechanicalProps, dict[str, Any]]:
    """Predimensiona viga principal y diafragma con criterio de esbeltez L/h."""
    if material.material_type == "concrete":
        h_girder = max(1.20, round(span_m / 18.0, 2))
        b_girder = 0.60
        h_diaph = round(0.75 * h_girder, 2)
        b_diaph = 0.30
        girder = rectangular_concrete_section_props(
            f"VIGA_HA_{int(h_girder*1000)}x{int(b_girder*1000)}",
            h_m=h_girder,
            b_m=b_girder,
            material_name=material.name,
        )
        diaph = rectangular_concrete_section_props(
            f"DIAF_HA_{int(h_diaph*1000)}x{int(b_diaph*1000)}",
            h_m=h_diaph,
            b_m=b_diaph,
            material_name=material.name,
        )
        trace = {
            "criterion": "Esbeltez L/h = 18 para vigas prefabricadas/in-situ de hormigon (EC2 / SETRA)",
            "target_h_min_m": round(span_m / 18.0, 4),
            "selected_girder": girder.name,
            "selected_diaphragm": diaph.name,
            "actual_L_over_h": round(span_m / girder.h_m, 2),
        }
        return girder, diaph, trace

    # Acero estructural: relacion L/h <= 30 (AASHTO LRFD Tabla 2.5.2.6.3-1 / EN 1993-2)
    h_target = max(0.50, span_m / 30.0)
    chosen_name = BRIDGE_STEEL_GIRDER_LADDER[-1]
    for cand_name in BRIDGE_STEEL_GIRDER_LADDER:
        cand = get_section(cand_name)
        if cand.h >= h_target:
            chosen_name = cand_name
            # Para luces >= 28 m preferimos la serie pesada HEM 1000 dentro de h ~ 1.0 m
            if span_m >= 28.0 and cand_name.startswith("HEB"):
                continue
            break
    girder = section_props_from_catalog(chosen_name, material_name=material.name)
    diaph = section_props_from_catalog("HEB 400", material_name=material.name)
    trace = {
        "criterion": "Esbeltez L/h <= 30 en vigas metalicas de puente (AASHTO LRFD Tabla 2.5.2.6.3-1 / EN 1993-2)",
        "target_h_min_m": round(h_target, 4),
        "selected_girder": girder.name,
        "selected_diaphragm": diaph.name,
        "actual_L_over_h": round(span_m / girder.h_m, 2),
        "ladder_candidates": list(BRIDGE_STEEL_GIRDER_LADDER),
    }
    return girder, diaph, trace


def notional_lanes_en1991_2(width_m: float) -> dict[str, Any]:
    """División de la calzada en carriles nocionales según EN 1991-2 §4.2.3 Tabla 4.1.

    - ``w < 5.4 m``: ``n_1 = 1`` carril nocional de ``w_l = 3.0 m``, área remanente ``w - 3.0``.
    - ``5.4 m <= w < 6.0 m``: ``n_1 = 2`` carriles nocionales de ``w_l = w / 2.0``, área remanente ``0.0``.
    - ``w >= 6.0 m``: ``n_1 = int(w // 3.0)`` carriles nocionales de ``w_l = 3.0 m`` y
      área remanente ``w_r = w - 3.0 * n_1``.
    """
    if width_m <= 0:
        raise ValueError("width_m debe ser > 0")
    if width_m < 5.4 - 1e-9:
        n_1 = 1
        w_l = min(3.0, width_m)
        w_r = max(0.0, round(width_m - w_l, 6))
    elif width_m < 6.0 - 1e-9:
        n_1 = 2
        w_l = round(width_m / 2.0, 6)
        w_r = 0.0
    else:
        n_1 = int(math.floor((width_m + 1e-9) / 3.0))
        w_l = 3.0
        w_r = max(0.0, round(width_m - 3.0 * n_1, 6))
    return {
        "norm_ref": "EN 1991-2 §4.2.3 Tabla 4.1",
        "carriageway_width_m": round(width_m, 6),
        "n_notional_lanes": n_1,
        "notional_lane_width_m": w_l,
        "remaining_width_m": w_r,
    }


def design_lanes_aashto_lrfd(width_m: float) -> dict[str, Any]:
    """Número de carriles de diseño según AASHTO LRFD §3.6.1.1.1 (w_lane = 3.60 m)."""
    if width_m <= 0:
        raise ValueError("width_m debe ser > 0")
    if width_m < 6.0 - 1e-9:
        n_l = 1
    elif width_m <= 7.20 + 1e-9:
        n_l = 2
    else:
        n_l = max(1, int(math.floor((width_m + 1e-9) / 3.60)))
    w_l = 3.60 if width_m >= 7.20 else round(width_m / n_l, 6)
    w_r = max(0.0, round(width_m - n_l * w_l, 6))
    return {
        "norm_ref": "AASHTO LRFD §3.6.1.1.1",
        "carriageway_width_m": round(width_m, 6),
        "n_notional_lanes": n_l,
        "notional_lane_width_m": w_l,
        "remaining_width_m": w_r,
    }


def courbon_transverse_factors(y_girders: list[float], y_load: float) -> list[float]:
    """Factores de distribución transversal excéntrica de Courbon (tablero rígido / ley de palanca global):

    ``eta_i(y_load) = 1 / n_g + (y_load - y_bar) * (y_i - y_bar) / sum_j (y_j - y_bar)^2``

    Garantiza equilibrio exacto de fuerzas verticales (``sum_i eta_i == 1.0``) y
    de momento torsor/vuelco transversal (``sum_i eta_i * y_i == y_load``).
    """
    n_g = len(y_girders)
    if n_g < 2:
        raise ValueError("Se requieren al menos 2 vigas para reparto transversal")
    y_bar = sum(y_girders) / n_g
    denom = sum((y - y_bar) ** 2 for y in y_girders)
    if denom <= 1e-12:
        return [1.0 / n_g] * n_g
    e_load = y_load - y_bar
    return [1.0 / n_g + e_load * (y_i - y_bar) / denom for y_i in y_girders]


def bridge_spec_from_encargo(encargo: Any) -> BridgeDesignSpec:
    """Construye un ``BridgeDesignSpec`` trazable a partir de un ``Encargo`` ejecutable."""
    if not getattr(encargo, "ejecutable", False):
        faltan = getattr(encargo, "faltan", [])
        raise ValueError(f"El Encargo no es ejecutable; faltan datos obligatorios: {faltan}")
    if getattr(encargo, "tipo", None) != "puente":
        raise ValueError(f"Se esperaba encargo de tipo 'puente', recibido: {getattr(encargo, 'tipo', None)!r}")

    def _val(campo: str) -> str:
        if campo in encargo.datos:
            return str(encargo.datos[campo]["valor"])
        for s in encargo.supuestos:
            if s["campo"] == campo:
                return str(s["valor"])
        raise KeyError(f"Campo {campo!r} ausente en datos y supuestos del Encargo")

    span_m = float(encargo.luz_m)
    norma_raw = _val("norma")
    uso_raw = _val("uso")
    ancho_raw = _val("ancho_tablero_o_carriles")
    material_raw = _val("material")
    apoyos_raw = _val("apoyos")
    galibo_raw = _val("galibo")
    acciones_raw = _val("acciones")

    # El uso decide el modelo de cargas. Solo existe el de CARRETERA (LM1 / HL-93): un puente
    # ferroviario sin LM71/SW (EN 1991-2 §6) quedaria del lado inseguro y uno peatonal recibiria
    # camiones en vez de la carga de peatones (§5). Antes `uso` no intervenia (2026-10-25).
    # Sin tildes y por PALABRA: 'peatón' / 'vía férrea' / 'tranvía' pasaban con cargas de carretera y
    # 'metro' casaba con 'metros' (revision 2026-10-25).
    # Y como LISTA DE PERMITIDOS: una lista de prohibidos dejaba pasar 'ferrocarril', 'railroad' o
    # 'footbridge'. Se calcula solo si el uso NOMBRA trafico de carretera y no nombra otro a la vez.
    import unicodedata
    uso_low = "".join(ch for ch in unicodedata.normalize("NFKD", uso_raw.lower()) if not unicodedata.combining(ch))
    carretera = (r"\bcarretera\w*", r"\bvehicular\w*", r"\btrafico rodado\b", r"\bautovia\w*", r"\bautopista\w*",
                 r"\bvial(es)?\b", r"\bcalle\w*", r"\bavenida\w*", r"\broad\w*", r"\bhighway\w*", r"\bmotorway\w*")
    sin_modelo = (r"\bferrovi\w*", r"\bferrocarril\w*", r"\bferre[ao]s?\b", r"\btren(es)?\b", r"\btranvia\w*",
                  r"\brail\w*", r"\bmetro\b", r"\bpeaton\w*", r"\bpedestrian\w*", r"\bfoot\w*", r"\bpasarela\w*",
                  r"\bciclist\w*", r"\bbici\w*")
    if not any(re.search(p, uso_low) for p in carretera) or any(re.search(p, uso_low) for p in sin_modelo):
        raise ValueError(
            f"uso={uso_raw!r}: el modelo de cargas de ese uso no esta implementado (solo trafico de "
            "carretera LM1 / HL-93); calcularlo con cargas de carretera seria incorrecto")

    if any(k in norma_raw.upper() or k in acciones_raw.upper() for k in ("AASHTO", "HL-93", "HL93", "CCP", "NSR")):
        norma_code = "AASHTO_LRFD"
    else:
        norma_code = "EN_1991_2"

    # Parsear ancho de tablero o numero de carriles
    m_carriles = re.search(r"(\d+)\s*carriles?", ancho_raw, re.I)
    m_ancho = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:metros|m)\b", ancho_raw, re.I)
    if m_ancho:
        width_m = float(m_ancho.group(1).replace(",", "."))
        if norma_code == "EN_1991_2":
            n_lanes = notional_lanes_en1991_2(width_m)["n_notional_lanes"]
        else:
            n_lanes = design_lanes_aashto_lrfd(width_m)["n_notional_lanes"]
    elif m_carriles:
        n_lanes = int(m_carriles.group(1))
        width_m = round(n_lanes * 3.5 + 3.0, 3)  # carriles fisicos de 3.5 m + arcenes de 1.5 m
    else:
        raise ValueError(f"No se pudo extraer ancho o carriles de {ancho_raw!r}")

    m_galibo = re.search(r"(\d+(?:[.,]\d+)?)", galibo_raw)
    if not m_galibo:
        raise ValueError(f"galibo={galibo_raw!r}: no contiene un valor numerico (antes pasaba a 5.0 m en silencio)")
    galibo_m = float(m_galibo.group(1).replace(",", "."))

    m_vanos = re.search(r"(\d+)\s*vanos", apoyos_raw, re.I)
    n_spans = int(m_vanos.group(1)) if m_vanos else 1

    n_girders = max(3, min(8, round(width_m / 2.5)))
    n_diaphragms = max(2, round(span_m / 7.5) - 1)

    mat = default_bridge_material(material_raw, norma_code)
    girder_sec, diaph_sec, trace = select_bridge_sections(span_m, mat)
    trace = {**trace, "supuestos_del_flujo": [
        "espesor de losa = 0.25 m (fijado por el flujo, no por el encargo)",
        "pavimento (carga muerta sobreimpuesta) = 2.0 kPa (fijado por el flujo)",
        "barreras/pretiles = 5.0 kN/m en total (fijado por el flujo)",
        f"numero de vigas = {n_girders} = round(ancho/2.5) acotado a [3, 8] (criterio del flujo)",
        f"numero de diafragmas interiores = {n_diaphragms} = round(luz/7.5) - 1 (criterio del flujo)",
        f"material {mat.name} por defecto para material={material_raw!r} (default_bridge_material)",
    ]}

    return BridgeDesignSpec(
        span_m=span_m,
        width_m=width_m,
        n_spans=n_spans,
        n_girders=n_girders,
        n_diaphragms=n_diaphragms,
        n_lanes=n_lanes,
        norma=norma_code,
        uso=uso_raw,
        apoyos_desc=apoyos_raw,
        galibo_m=galibo_m,
        acciones_desc=acciones_raw,
        slab_thickness_m=0.25,
        wearing_surface_kPa=2.0,
        barrier_load_kN_m_total=5.0,
        material=mat,
        girder_section=girder_sec,
        diaphragm_section=diaph_sec,
        predimensioning_trace=trace,
    )


def expected_grillage_counts(
    *,
    n_spans: int = 1,
    n_girders: int = 4,
    n_diaphragms: int = 3,
    divisions_per_span: int | None = None,
) -> dict[str, int]:
    """Deriva matematicamente los recuentos del emparrillado desde la especificacion."""
    if n_spans < 1 or n_girders < 2:
        raise ValueError("n_spans>=1 y n_girders>=2 son obligatorios")
    div = divisions_per_span if divisions_per_span is not None else (n_diaphragms + 1)
    if div < 1:
        raise ValueError("divisions_per_span>=1 (o n_diaphragms>=0) es obligatorio")
    nx = n_spans * div + 1
    n_joints = nx * n_girders
    n_frames_long = (nx - 1) * n_girders
    n_frames_trans = nx * (n_girders - 1)
    n_frames = n_frames_long + n_frames_trans
    n_supports = (n_spans + 1) * n_girders
    return {
        "n_x": nx,
        "divisions_per_span": div,
        "n_joints": n_joints,
        "n_frames_long": n_frames_long,
        "n_frames_trans": n_frames_trans,
        "n_frames": n_frames,
        "n_supports": n_supports,
    }


def _support_restraint_for_node(is_fixed_abutment: bool, is_guide_girder: bool) -> list[bool]:
    """Esquema de aparatos de apoyo fisicamente estable e isostatico en planta:

    - Estribo fijo (x = 0):
      * Apoyo guia (ig = 0): [Ux=True, Uy=True, Uz=True, Rx=False, Ry=False, Rz=False]
      * Resto de vigas (ig > 0): [Ux=True, Uy=False, Uz=True, Rx=False, Ry=False, Rz=False]
        (permite libre dilatacion termica transversal entre vigas sin coaccion espuria).
    - Estribo/pilas moviles (x > 0):
      * Apoyo guia (ig = 0): [Ux=False, Uy=True, Uz=True, Rx=False, Ry=False, Rz=False]
        (permite libre dilatacion longitudinal Ux=0 y guia transversalmente Uy=1 para
        impedir el giro en planta Rz del tablero con brazo L).
      * Resto de vigas (ig > 0): [Ux=False, Uy=False, Uz=True, Rx=False, Ry=False, Rz=False]
        (apoyo deslizante multidireccional: solo coacciona Uz=1).
    """
    ux = bool(is_fixed_abutment)
    uy = bool(is_guide_girder)
    uz = True
    return [ux, uy, uz, False, False, False]


def verify_kinematic_stability(joints: list[dict[str, Any]]) -> dict[str, Any]:
    """Verifica que el esquema de apoyos sea cinematicamente estable en los 6 GDL globales
    (sum_Fx, sum_Fy, sum_Fz, sum_Mx, sum_My, sum_Mz) y libre de coaccion longitudinal
    espuria en los apoyos moviles (x > 0).
    """
    supports = [j for j in joints if j.get("restraint") is not None]
    if len(supports) < 3:
        raise ValueError(f"Inestabilidad cinemática: se requieren al menos 3 apoyos, hallados {len(supports)}")

    ux_nodes = [j for j in supports if j["restraint"][0]]
    uy_nodes = [j for j in supports if j["restraint"][1]]
    uz_nodes = [j for j in supports if j["restraint"][2]]

    sum_fx = len(ux_nodes) >= 1
    sum_fy = len(uy_nodes) >= 1
    sum_fz = len(uz_nodes) >= 3

    # Giro alrededor de X (vuelco transversal / torsión global): requiere Uz en distintos Y
    uz_y_coords = {round(float(j["y"]), 4) for j in uz_nodes}
    sum_mx = len(uz_y_coords) >= 2 and (max(uz_y_coords) - min(uz_y_coords) > 1e-4)

    # Giro alrededor de Y (cabeceo longitudinal): requiere Uz en distintos X
    uz_x_coords = {round(float(j["x"]), 4) for j in uz_nodes}
    sum_my = len(uz_x_coords) >= 2 and (max(uz_x_coords) - min(uz_x_coords) > 1e-4)

    # Giro alrededor de Z en planta (guiñada): requiere Uy en distintos X (par transversal con brazo L)
    uy_x_coords = {round(float(j["x"]), 4) for j in uy_nodes}
    sum_mz = len(uy_x_coords) >= 2 and (max(uy_x_coords) - min(uy_x_coords) > 1e-4)

    if not sum_fx:
        raise ValueError("Inestabilidad cinemática (sum_Fx): ningún apoyo restringe Ux")
    if not sum_fy:
        raise ValueError("Inestabilidad cinemática (sum_Fy): ningún apoyo restringe Uy")
    if not sum_fz:
        raise ValueError("Inestabilidad cinemática (sum_Fz): apoyos verticales Uz insuficientes")
    if not sum_mx:
        raise ValueError("Inestabilidad cinemática (sum_Mx): falta brazo transversal entre apoyos Uz")
    if not sum_my:
        raise ValueError("Inestabilidad cinemática (sum_My): falta brazo longitudinal entre apoyos Uz")
    if not sum_mz:
        raise ValueError(
            "Inestabilidad cinemática en planta (sum_Mz): falta guía transversal Uy en estribos opuestos"
        )

    # Comprobar ausencia de coaccion longitudinal espuria en apoyos moviles (x > x_min)
    x_min = min(float(j["x"]) for j in supports)
    movable_supports = [j for j in supports if float(j["x"]) > x_min + 1e-4]
    locked_movable = [j["id"] for j in movable_supports if j["restraint"][0]]
    if locked_movable:
        raise ValueError(
            f"Coacción longitudinal espuria en apoyos móviles {locked_movable}: "
            f"Ux=True en x > {x_min} bloquea la dilatación longitudinal del tablero"
        )

    y_min = min(float(j["y"]) for j in supports)
    non_guide_supports = [j for j in supports if float(j["y"]) > y_min + 1e-4]
    transverse_free = all(not j["restraint"][1] for j in non_guide_supports)

    return {
        "stable_3d": True,
        "global_dofs": {
            "sum_Fx": sum_fx,
            "sum_Fy": sum_fy,
            "sum_Fz": sum_fz,
            "sum_Mx": sum_mx,
            "sum_My": sum_my,
            "sum_Mz": sum_mz,
        },
        "longitudinal_expansion_free_at_movable": True,
        "transverse_expansion_free_on_non_guide": transverse_free,
        "n_supports_total": len(supports),
        "n_ux_restrained": len(ux_nodes),
        "n_uy_restrained": len(uy_nodes),
        "n_uz_restrained": len(uz_nodes),
    }


def _compute_grillage_loads(
    *,
    joints: list[dict[str, Any]],
    frames: list[dict[str, Any]],
    span_length: float,
    n_spans: int,
    n_girders: int,
    girder_spacing: float,
    spec: BridgeDesignSpec | None = None,
) -> dict[str, Any]:
    """Calcula las cargas permanentes (DEAD, DW), sobrecarga de carril (LIVE_LANE),
    posiciones pesimas del vehiculo de diseno (LIVE_VEHICLE_M en centro de vano y
    LIVE_VEHICLE_V junto al apoyo), distribucion transversal excentrica (Courbon) y
    cargas puntuales en barras sin condensacion nodal espuria sobre los apoyos.
    """
    width_m = round((n_girders - 1) * girder_spacing, 6)
    norma = spec.norma if spec is not None else "AASHTO_LRFD"
    slab_thickness_m = spec.slab_thickness_m if spec is not None else 0.25
    wearing_kPa = spec.wearing_surface_kPa if spec is not None else 2.0
    barrier_total_kN_m = spec.barrier_load_kN_m_total if spec is not None else 5.0

    if norma == "EN_1991_2":
        lane_layout = notional_lanes_en1991_2(width_m)
    else:
        lane_layout = design_lanes_aashto_lrfd(width_m)
    n_lanes = spec.n_lanes if spec is not None else int(lane_layout["n_notional_lanes"])

    # Coordenadas transversales de las vigas longitudinales ig = 0 .. n_girders-1
    y_girders = [round(ig * girder_spacing, 6) for ig in range(n_girders)]

    # Ancho tributario medio por viga longitudinal (cargas permanentes simetricas)
    b_trib = width_m / n_girders
    # Peso de la losa de hormigon armado (25 kN/m^3 * espesor * ancho tributario)
    q_slab_per_girder_kN_m = round(25.0 * slab_thickness_m * b_trib, 4)
    # Carga muerta no estructural DW (pavimento + pretiles/barreras repartidos entre vigas)
    q_dw_per_girder_kN_m = round(wearing_kPa * b_trib + barrier_total_kN_m / n_girders, 4)

    # Identificar coordenadas X de los nudos de las vigas para localizar el tramo de viga L{ix}_{ig}
    x_coords = sorted({round(float(j["x"]), 6) for j in joints})
    # Offset infinitesimal junto al apoyo izquierdo (x = 0+) para evaluar el cortante maximo en viga
    # sin que la carga puntual caiga exactamente sobre el nudo coaccionado N0_* (condensacion nodal).
    support_shear_offset_m = round(min(0.05, 0.01 * (x_coords[1] - x_coords[0])), 6)

    def _map_x_to_segment(x_pos: float) -> tuple[int, float] | None:
        """Devuelve (ix, dist_local_m) del tramo longitudinal [x_ix, x_{ix+1}] que contiene x_pos."""
        if x_pos < x_coords[0] - 1e-6 or x_pos > x_coords[-1] + 1e-6:
            return None
        x_clamped = max(x_coords[0], min(x_coords[-1], x_pos))
        for idx in range(len(x_coords) - 1):
            x_left = x_coords[idx]
            x_right = x_coords[idx + 1]
            if x_left - 1e-9 <= x_clamped <= x_right + 1e-9:
                d_local = max(0.0, min(x_right - x_left, x_clamped - x_left))
                return idx, round(d_local, 6)
        return None

    def _lump_axle_to_x_nodes(x_pos: float, total_axle_kN: float) -> list[tuple[float, float]]:
        """Reparte una carga de eje en x_pos hacia los nudos transversales adyacentes por ley de palanca."""
        if x_pos < x_coords[0] - 1e-6 or x_pos > x_coords[-1] + 1e-6:
            return []
        for idx in range(len(x_coords) - 1):
            x_left = x_coords[idx]
            x_right = x_coords[idx + 1]
            if x_left - 1e-6 <= x_pos <= x_right + 1e-6:
                dx_seg = x_right - x_left
                if dx_seg <= 1e-9:
                    return [(x_left, total_axle_kN)]
                w_right = (x_pos - x_left) / dx_seg
                w_left = 1.0 - w_right
                out = []
                if w_left > 1e-6:
                    out.append((x_left, total_axle_kN * w_left))
                if w_right > 1e-6:
                    out.append((x_right, total_axle_kN * w_right))
                return out
        return []

    if norma == "EN_1991_2":
        lm1 = LM1(n_lanes=n_lanes, lane_width=float(lane_layout["notional_lane_width_m"]))
        M_env_kNm, V_env_kN = traffic_envelope_lm1(
            span_length, n_lanes=n_lanes, lane_width=lm1.lane_width
        )
        rem_width = max(0.0, round(width_m - n_lanes * lm1.lane_width, 6))
        udl_lanes_kN_m = lm1.udl_per_lane_kN_per_m()
        ts_lanes_kN = lm1.tandem_axles_kN()
        q_rem_kN_m = round(rem_width * 2.5, 6)
        udl_total_kN_m = round(sum(udl_lanes_kN_m) + q_rem_kN_m, 6)
        q_lane_per_girder_kN_m = round(udl_total_kN_m / n_girders, 4)

        # Posicion transversal mas excentrica (EN 1991-2 §4.2.4):
        # Carril 1 adyacente al borde y=0 -> centro en y_1 = w_l/2; Carril k en (k - 0.5)*w_l;
        # Area remanente adyacente al borde opuesto [n_lanes*w_l, width_m].
        lane_strips_detail: list[dict[str, Any]] = []
        q_lane_by_girder_raw = [0.0] * n_girders
        ts_axle_by_girder_raw = [0.0] * n_girders
        for k_idx in range(n_lanes):
            y_start = round(k_idx * lm1.lane_width, 6)
            y_end = round((k_idx + 1) * lm1.lane_width, 6)
            y_c = round(0.5 * (y_start + y_end), 6)
            etas = courbon_transverse_factors(y_girders, y_c)
            q_k = udl_lanes_kN_m[k_idx]
            Q_k = ts_lanes_kN[k_idx]
            for ig in range(n_girders):
                q_lane_by_girder_raw[ig] += q_k * etas[ig]
                ts_axle_by_girder_raw[ig] += Q_k * etas[ig]
            lane_strips_detail.append({
                "strip_id": f"LANE_{k_idx + 1}",
                "kind": "notional_lane",
                "lane_number": k_idx + 1,
                "y_start_m": y_start,
                "y_end_m": y_end,
                "width_m": round(y_end - y_start, 6),
                "y_centroid_m": y_c,
                "q_ik_kPa": round(q_k / lm1.lane_width, 4),
                "udl_kN_m": round(q_k, 4),
                "ts_axle_kN": round(Q_k, 4),
                "courbon_factors": [round(e, 6) for e in etas],
            })
        if rem_width > 1e-6:
            y_start_r = round(n_lanes * lm1.lane_width, 6)
            y_end_r = width_m
            y_c_r = round(0.5 * (y_start_r + y_end_r), 6)
            etas_r = courbon_transverse_factors(y_girders, y_c_r)
            for ig in range(n_girders):
                q_lane_by_girder_raw[ig] += q_rem_kN_m * etas_r[ig]
            lane_strips_detail.append({
                "strip_id": "REMAINING_AREA",
                "kind": "remaining_area",
                "lane_number": None,
                "y_start_m": y_start_r,
                "y_end_m": y_end_r,
                "width_m": rem_width,
                "y_centroid_m": y_c_r,
                "q_rk_kPa": 2.5,
                "udl_kN_m": q_rem_kN_m,
                "ts_axle_kN": 0.0,
                "courbon_factors": [round(e, 6) for e in etas_r],
            })

        # Tandem System TS: dos ejes separados 1.20 m
        ts_axle_total_kN = round(sum(ts_lanes_kN), 4)
        axles_kN = [ts_axle_total_kN, ts_axle_total_kN]
        axles_V_kN = list(axles_kN)
        axle_share_by_girder = [
            (ts_axle_by_girder_raw[ig] / ts_axle_total_kN) if ts_axle_total_kN > 0 else (1.0 / n_girders)
            for ig in range(n_girders)
        ]
        spacings_m = [1.20]
        impact_factor = 1.0  # EN 1991-2 ya incluye amplificacion dinamica en LM1
        traffic_code = "EN_1991_2_LM1"
        # Posicion critica de Barre para M+ (EN 1991-2 TS, a=1.20 m): x_c = L/2 - a/4 = L/2 - 0.30 m
        axle_positions_M = [span_length / 2.0 - 0.30, span_length / 2.0 + 0.90]
        # Posicion critica para Vmax junto al apoyo: primer eje en x = 0+ (support_shear_offset_m),
        # segundo en x = 0+ + 1.20 m para que el cortante se transmita integramente por las vigas L0_*.
        axle_positions_V = [
            support_shear_offset_m,
            min(span_length, support_shear_offset_m + 1.20),
        ]
        combos_spec = [
            {
                "name": "ULS_STR",
                "norm_ref": "EN 1990 §6.4.3.2 Ec. 6.10 + Anexo A2 Tabla A2.4(B)",
                "factors": {
                    "DEAD": GAMMA_G_SUP,
                    "DW": GAMMA_G_SUP,
                    "LIVE_LANE": EN1990_A2_GAMMA_Q_TRAFFIC,
                    "LIVE_VEHICLE_M": EN1990_A2_GAMMA_Q_TRAFFIC,
                },
            },
            {
                "name": "ULS_STR_SHEAR",
                "norm_ref": "EN 1990 §6.4.3.2 Ec. 6.10 + Anexo A2 Tabla A2.4(B)",
                "factors": {
                    "DEAD": GAMMA_G_SUP,
                    "DW": GAMMA_G_SUP,
                    "LIVE_LANE": EN1990_A2_GAMMA_Q_TRAFFIC,
                    "LIVE_VEHICLE_V": EN1990_A2_GAMMA_Q_TRAFFIC,
                },
            },
            {
                "name": "SLS_CHARACTERISTIC",
                "norm_ref": "EN 1990 §6.5.3 Ec. 6.14b (Combinación característica)",
                "factors": {
                    "DEAD": 1.0,
                    "DW": 1.0,
                    "LIVE_LANE": 1.0,
                    "LIVE_VEHICLE_M": 1.0,
                },
            },
        ]
    else:
        hl93_res = hl93_envelope(span_length, impact_factor=1.33)
        M_env_kNm = float(hl93_res["M_max_kNm"])
        V_env_kN = float(hl93_res["V_max_kN"])
        impact_factor = 1.33
        traffic_code = "AASHTO_LRFD_HL93"
        # Factor de presencia multiple AASHTO LRFD Tabla 3.6.1.1.2-1 (m=1.20 para 1 carril, 1.00 para 2)
        mpf = 1.20 if n_lanes == 1 else (1.00 if n_lanes == 2 else 0.85)
        w_lane_aashto = float(lane_layout["notional_lane_width_m"])
        rem_width = float(lane_layout["remaining_width_m"])
        udl_total_kN_m = round(HL93_LANE_LOAD_KN_M * n_lanes * mpf, 6)
        q_lane_per_girder_kN_m = round(udl_total_kN_m / n_girders, 4)

        lane_strips_detail = []
        q_lane_by_girder_raw = [0.0] * n_girders
        veh_share_raw = [0.0] * n_girders
        for k_idx in range(n_lanes):
            y_start = round(k_idx * w_lane_aashto, 6)
            y_end = round((k_idx + 1) * w_lane_aashto, 6)
            y_c = round(0.5 * (y_start + y_end), 6)
            etas = courbon_transverse_factors(y_girders, y_c)
            q_k = HL93_LANE_LOAD_KN_M * mpf
            for ig in range(n_girders):
                q_lane_by_girder_raw[ig] += q_k * etas[ig]
                veh_share_raw[ig] += etas[ig] / n_lanes
            lane_strips_detail.append({
                "strip_id": f"DESIGN_LANE_{k_idx + 1}",
                "kind": "design_lane",
                "lane_number": k_idx + 1,
                "y_start_m": y_start,
                "y_end_m": y_end,
                "width_m": round(y_end - y_start, 6),
                "y_centroid_m": y_c,
                "udl_kN_m": round(q_k, 4),
                "courbon_factors": [round(e, 6) for e in etas],
            })
        axle_share_by_girder = veh_share_raw

        # Camion de diseno HS-20 amplificado por impacto IM y numero de carriles * mpf
        scale_veh = impact_factor * n_lanes * mpf
        axles_kN = [round(p * scale_veh, 4) for p in TRUCK_AXLES_kN]
        spacings_m = list(TRUCK_AXLE_SPACINGS_m)
        # Posicion de Barre para camion HS-20: eje central de 145 kN en L/2 -> ejes a L/2 - 4.27, L/2, L/2 + 4.27
        axle_positions_M = [
            max(0.0, span_length / 2.0 - spacings_m[0]),
            span_length / 2.0,
            min(span_length, span_length / 2.0 + spacings_m[1]),
        ]
        # Posicion critica de cortante junto al apoyo x=0+: eje pesado trasero en x=0+, siguiente en 0+ + 4.27 m, delantero en 0+ + 8.54 m
        axle_positions_V = [
            support_shear_offset_m,
            min(span_length, support_shear_offset_m + spacings_m[1]),
            min(span_length, support_shear_offset_m + spacings_m[0] + spacings_m[1]),
        ]
        # En Vmax el eje en x=0+ es el trasero de 145 kN
        axles_V_kN = [axles_kN[2], axles_kN[1], axles_kN[0]]
        combos_spec = [
            {
                "name": "ULS_STRENGTH_I",
                "norm_ref": "AASHTO LRFD Tabla 3.4.1-1 (Strength I)",
                "factors": {
                    "DEAD": aashto_gamma("Strength_I", "DC"),
                    "DW": aashto_gamma("Strength_I", "DW"),
                    "LIVE_LANE": aashto_gamma("Strength_I", "LL"),
                    "LIVE_VEHICLE_M": aashto_gamma("Strength_I", "LL"),
                },
            },
            {
                "name": "ULS_STRENGTH_I_SHEAR",
                "norm_ref": "AASHTO LRFD Tabla 3.4.1-1 (Strength I Shear)",
                "factors": {
                    "DEAD": aashto_gamma("Strength_I", "DC"),
                    "DW": aashto_gamma("Strength_I", "DW"),
                    "LIVE_LANE": aashto_gamma("Strength_I", "LL"),
                    "LIVE_VEHICLE_V": aashto_gamma("Strength_I", "LL"),
                },
            },
            {
                "name": "SLS_SERVICE_II",
                "norm_ref": "AASHTO LRFD Tabla 3.4.1-1 (Service II)",
                "factors": {
                    "DEAD": aashto_gamma("Service_II", "DC"),
                    "DW": aashto_gamma("Service_II", "DW"),
                    "LIVE_LANE": aashto_gamma("Service_II", "LL"),
                    "LIVE_VEHICLE_M": aashto_gamma("Service_II", "LL"),
                },
            },
        ]

    q_lane_by_girder_kN_m = {
        ig: round(q_lane_by_girder_raw[ig], 6) for ig in range(n_girders)
    }
    axle_share_by_girder_dict = {
        ig: round(axle_share_by_girder[ig], 6) for ig in range(n_girders)
    }

    # Construir cargas puntuales exactas sobre las barras longitudinales L{ix}_{ig}
    # (sin condensacion nodal sobre los apoyos N0_*).
    frame_point_loads_M: list[dict[str, Any]] = []
    for axle_idx, (x_ax, p_total) in enumerate(zip(axle_positions_M, axles_kN), start=1):
        seg = _map_x_to_segment(x_ax)
        if seg is None:
            continue
        ix_seg, dist_local = seg
        for ig in range(n_girders):
            p_girder = round(p_total * axle_share_by_girder[ig], 6)
            frame_point_loads_M.append({
                "frame_id": f"L{ix_seg}_{ig}",
                "girder_index": ig,
                "axle_index": axle_idx,
                "x_global_m": round(x_ax, 6),
                "dist_local_m": dist_local,
                "load_kN": p_girder,
                "fz_global_kN": round(-p_girder, 6),
            })

    frame_point_loads_V: list[dict[str, Any]] = []
    for axle_idx, (x_ax, p_total) in enumerate(zip(axle_positions_V, axles_V_kN), start=1):
        seg = _map_x_to_segment(x_ax)
        if seg is None:
            continue
        ix_seg, dist_local = seg
        for ig in range(n_girders):
            p_girder = round(p_total * axle_share_by_girder[ig], 6)
            frame_point_loads_V.append({
                "frame_id": f"L{ix_seg}_{ig}",
                "girder_index": ig,
                "axle_index": axle_idx,
                "x_global_m": round(x_ax, 6),
                "dist_local_m": dist_local,
                "load_kN": p_girder,
                "fz_global_kN": round(-p_girder, 6),
            })

    # Reacciones equivalentes en nudos (solo como referencia analitica en meta, con reparto excentrico)
    nodal_loads_M: dict[str, float] = {}
    for x_ax, p_total in zip(axle_positions_M, axles_kN):
        for x_node, p_lumped in _lump_axle_to_x_nodes(x_ax, p_total):
            for j in joints:
                if abs(float(j["x"]) - x_node) < 1e-4:
                    ig_j = int(j["id"].split("_")[1])
                    p_girder = p_lumped * axle_share_by_girder[ig_j]
                    nodal_loads_M[j["id"]] = round(nodal_loads_M.get(j["id"], 0.0) - p_girder, 4)

    nodal_loads_V: dict[str, float] = {}
    for x_ax, p_total in zip(axle_positions_V, axles_V_kN):
        for x_node, p_lumped in _lump_axle_to_x_nodes(x_ax, p_total):
            for j in joints:
                if abs(float(j["x"]) - x_node) < 1e-4:
                    ig_j = int(j["id"].split("_")[1])
                    p_girder = p_lumped * axle_share_by_girder[ig_j]
                    nodal_loads_V[j["id"]] = round(nodal_loads_V.get(j["id"], 0.0) - p_girder, 4)

    long_frame_ids = [f["id"] for f in frames if f["id"].startswith("L")]

    return {
        "traffic_code": traffic_code,
        "impact_factor_IM": impact_factor,
        "n_lanes": n_lanes,
        "notional_lanes_detail": {
            **lane_layout,
            "strips": lane_strips_detail,
        },
        "transverse_distribution": {
            "method": "Courbon (reparto transversal excéntrico con carriles ordenados desde borde y=0)",
            "y_girders_m": y_girders,
            "y_centroid_deck_m": round(sum(y_girders) / n_girders, 6),
            "q_lane_by_girder_kN_m": q_lane_by_girder_kN_m,
            "q_lane_total_kN_m": round(sum(q_lane_by_girder_raw), 6),
            "vehicle_axle_share_by_girder": axle_share_by_girder_dict,
            "governing_exterior_girder": 0,
        },
        "support_shear_offset_m": support_shear_offset_m,
        "q_slab_per_girder_kN_m": q_slab_per_girder_kN_m,
        "q_dw_per_girder_kN_m": q_dw_per_girder_kN_m,
        "q_lane_per_girder_kN_m": q_lane_per_girder_kN_m,
        "q_lane_by_girder_kN_m": q_lane_by_girder_kN_m,
        "vehicle_axles_M_kN": axles_kN,
        "vehicle_positions_M_m": [round(x, 4) for x in axle_positions_M],
        "vehicle_axles_V_kN": axles_V_kN,
        "vehicle_positions_V_m": [round(x, 4) for x in axle_positions_V],
        "analytical_envelope_M_kNm": round(M_env_kNm, 3),
        "analytical_envelope_V_kN": round(V_env_kN, 3),
        "longitudinal_frames_loaded": long_frame_ids,
        "frame_point_loads_LIVE_VEHICLE_M": frame_point_loads_M,
        "frame_point_loads_LIVE_VEHICLE_V": frame_point_loads_V,
        "nodal_loads_LIVE_VEHICLE_M_Fz_kN": nodal_loads_M,
        "nodal_loads_LIVE_VEHICLE_V_Fz_kN": nodal_loads_V,
        "combinations": combos_spec,
    }


MODEL_LIMITATIONS: tuple[str, ...] = (
    "El tren de cargas de tráfico (HL-93 / LM1) se introduce mediante casos estáticos en "
    "posiciones longitudinales críticas discretas (centro de vano por teorema de Barré para M+ "
    "y x=0+ junto al apoyo para Vmax) con aplicación directa sobre barra (FrameObj.SetLoadPoint) "
    "y distribución transversal excéntrica de Courbon hacia el borde y=0, no como barrido "
    "continuo de pasos móviles sobre superficie de influencia 3D.",
    "La losa superior de hormigón se introduce como masa/carga permanente tributaria sobre las "
    "vigas longitudinales y rigidez transversal concentrada en los diafragmas; no se modela acción "
    "mixta viga-losa ni desfase de cortante (shear lag) mediante elementos Shell acoplados.",
    "Los aparatos de apoyo se modelan como vínculos puntuales ideales isostáticos en planta "
    "(fijo en x=0, deslizante longitudinal con guía transversal en x=L), sin rigidez finita "
    "de neopreno zunchado ni interacción suelo-estructura en estribos.",
)

APPLICABLE_LIMIT_STATES: tuple[str, ...] = (
    "ELU_FLEXION_LONGITUDINAL (M33 <= phi*Mn / Mpl,Rd)",
    "ELU_CORTANTE_VERTICAL (V2 <= phi*Vn / Vpl,Rd)",
    "ELU_INTERACCION_FLEXO_CORTANTE_AXIL (M-V-N en vigas y diafragmas)",
    "ELU_TORSION_Y_ALABEO_EMPARRILLADO (T + bimomento en vigas de borde y diafragmas)",
    "ELU_PANDEO_LATERAL_TORSIONAL_Y_ABOLLADURA_ALMA (LTB y esbeltez de paneles h_w/t_w)",
    "ELU_CONEXION_RASANTE_LOSA_VIGA (pernos conectores en sección mixta)",
    "ELS_FLECHA_ACTIVA_TRAFICO (delta_LL <= L/800 AASHTO LRFD §2.5.2.6.2 / EN 1993-2)",
    "ELS_LIMITACION_TENSIONES_Y_FISURACION (Service II / combinación característica)",
    "ELU_FATIGA_DETALLES_SOLDADOS (Fatigue I/II AASHTO / EN 1993-1-9)",
    "ELU_APARATOS_DE_APOYO_Y_ESTRIBOS (reacciones verticales y horizontales en apoyos)",
)

UNIMPLEMENTED_CHECKS: tuple[str, ...] = (
    "ELU_TORSION_Y_ALABEO_EMPARRILLADO (alabeo restringido y tensiones tangenciales de Saint-Venant + Vlasov)",
    "ELU_ABOLLADURA_POR_CORTANTE_Y_RIGIDIZADORES_TRANSVERSALES (EN 1993-1-5 / AASHTO §6.10.9)",
    "ELU_CONEXION_RASANTE_LOSA_VIGA (diseño de conectores stud en interfase acero-hormigón)",
    "ELU_FATIGA_DETALLES_SOLDADOS (espectro de daño acumulado por ciclos de tráfico pesado)",
    "ELU_APARATOS_DE_APOYO_Y_ESTRIBOS (dimensionamiento de neoprenos zunchados y estribos)",
)


def generate_grillage(
    *,
    n_spans: int = 1,
    span_length: float = 20.0,
    n_girders: int = 4,
    girder_spacing: float = 2.5,
    divisions_per_span: int = 8,
    long_section: str = "HEM 1000",
    trans_section: str = "HEB 400",
    spec: BridgeDesignSpec | None = None,
) -> dict[str, Any]:
    """Devuelve ``{joints, frames, meta}`` del emparrillado fisicamente consistente.

    - ``joints``: ``{id, x, y, z, restraint}`` con esquema de apoyos cinematicamente
      estable en 3D (estribo fijo en x=0 y estribo/pilas moviles con dilatacion
      longitudinal libre Ux=False en x>0 y guia transversal Uy=True en ig=0).
    - ``frames``: longitudinales ``L*`` (vigas) + transversales ``T*`` (diafragmas)
      con secciones reales de catalogo verificadas.
    """
    if n_spans < 1 or n_girders < 2 or divisions_per_span < 1:
        raise ValueError("n_spans>=1, n_girders>=2, divisions_per_span>=1")

    mat = spec.material if spec is not None else default_bridge_material("acero", "EN_1991_2")
    if spec is not None:
        girder_props = spec.girder_section
        diaph_props = spec.diaphragm_section
        long_section = girder_props.name
        trans_section = diaph_props.name
    else:
        # Si se pasa el valor generico antiguo "GIRDER"/"DIAPHRAGM", sustituir por seccion real de catalogo
        eff_long = "HEM 1000" if long_section in ("GIRDER", "") else long_section
        eff_trans = "HEB 400" if trans_section in ("DIAPHRAGM", "") else trans_section
        girder_props = section_props_from_catalog(eff_long, material_name=mat.name)
        diaph_props = section_props_from_catalog(eff_trans, material_name=mat.name)
        long_section = girder_props.name
        trans_section = diaph_props.name

    counts = expected_grillage_counts(
        n_spans=n_spans,
        n_girders=n_girders,
        n_diaphragms=divisions_per_span - 1,
        divisions_per_span=divisions_per_span,
    )
    nx = counts["n_x"]
    dx = span_length / divisions_per_span
    x_coords = [round(ix * dx, 6) for ix in range(nx)]
    support_ix = {k * divisions_per_span for k in range(n_spans + 1)}

    def jid(ix: int, ig: int) -> str:
        return f"N{ix}_{ig}"

    joints: list[dict[str, Any]] = []
    for ix in range(nx):
        for ig in range(n_girders):
            restraint = None
            if ix in support_ix:
                restraint = _support_restraint_for_node(
                    is_fixed_abutment=(ix == 0),
                    is_guide_girder=(ig == 0),
                )
            joints.append({
                "id": jid(ix, ig),
                "x": x_coords[ix],
                "y": round(ig * girder_spacing, 6),
                "z": 0.0,
                "restraint": restraint,
            })

    kinematic_report = verify_kinematic_stability(joints)

    frames: list[dict[str, Any]] = []
    # Vigas longitudinales: a lo largo de cada girder (eje X global)
    for ig in range(n_girders):
        for ix in range(nx - 1):
            frames.append({
                "id": f"L{ix}_{ig}",
                "joint_i": jid(ix, ig),
                "joint_j": jid(ix + 1, ig),
                "section": long_section,
                "role": "girder",
            })
    # Diafragmas transversales: en cada linea transversal, entre girders consecutivos (eje Y global)
    for ix in range(nx):
        for ig in range(n_girders - 1):
            frames.append({
                "id": f"T{ix}_{ig}",
                "joint_i": jid(ix, ig),
                "joint_j": jid(ix, ig + 1),
                "section": trans_section,
                "role": "diaphragm",
            })

    loads_summary = _compute_grillage_loads(
        joints=joints,
        frames=frames,
        span_length=span_length,
        n_spans=n_spans,
        n_girders=n_girders,
        girder_spacing=girder_spacing,
        spec=spec,
    )

    return {
        "joints": joints,
        "frames": frames,
        "meta": {
            "n_spans": n_spans,
            "span_length": span_length,
            "n_girders": n_girders,
            "girder_spacing": girder_spacing,
            "divisions_per_span": divisions_per_span,
            "total_length": round(n_spans * span_length, 6),
            "width_m": round((n_girders - 1) * girder_spacing, 6),
            "lane_load_kN_m": HL93_LANE_LOAD_KN_M,
            "derived_counts": counts,
            "kinematic_stability": kinematic_report,
            "material": mat.to_dict(),
            "sections": {
                long_section: girder_props.to_dict(),
                trans_section: diaph_props.to_dict(),
            },
            "loads_summary": loads_summary,
            "limitaciones_modelo": list(MODEL_LIMITATIONS),
            "estados_limite_aplicables": list(APPLICABLE_LIMIT_STATES),
            "comprobaciones_no_implementadas": list(UNIMPLEMENTED_CHECKS),
        },
    }


def grillage_model(
    L: float,
    W: float,
    n_girders: int = 4,
    n_diaphragms: int = 3,
    *,
    n_spans: int = 1,
    long_section: str = "HEM 1000",
    trans_section: str = "HEB 400",
    spec: BridgeDesignSpec | None = None,
) -> dict[str, Any]:
    """Modelo de emparrillado de un tablero a partir de luz, ancho y conteos.

    - ``W`` es el ancho TOTAL del tablero -> separacion entre vigas ``W / (n_girders - 1)``.
    - ``n_diaphragms`` es el numero de lineas de diafragma INTERIORES (entre apoyos).
      Con los dos diafragmas de apoyo, hay ``n_diaphragms + 2`` lineas transversales
      por vano -> ``divisions_per_span = n_diaphragms + 1``.
    """
    if n_girders < 2:
        raise ValueError("n_girders>=2")
    if n_diaphragms < 0:
        raise ValueError("n_diaphragms>=0")
    if W <= 0:
        raise ValueError("W>0")
    girder_spacing = W / (n_girders - 1)
    divisions_per_span = n_diaphragms + 1
    return generate_grillage(
        n_spans=n_spans,
        span_length=L,
        n_girders=n_girders,
        girder_spacing=girder_spacing,
        divisions_per_span=divisions_per_span,
        long_section=long_section,
        trans_section=trans_section,
        spec=spec,
    )


def _mat_enum(mat_code: int) -> Any:
    member = "Steel" if int(mat_code) == 1 else "Concrete"
    ev = csi_enum("eMatType", member)
    return int(mat_code) if ev is None else ev


def _load_pat_enum(pat_code: int) -> Any:
    mapping = {1: "Dead", 2: "SuperDead", 3: "Live"}
    member = mapping.get(int(pat_code), "Other")
    ev = csi_enum("eLoadPatternType", member)
    return int(pat_code) if ev is None else ev


def _cname_type_enum(code: int = 0) -> Any:
    ev = csi_enum("eCNameType", "LoadCase")
    return int(code) if ev is None else ev


def _register_material_and_sections_oapi(sap_model: Any, meta: dict[str, Any]) -> None:
    """Registra explicita y verificadamente el material y las secciones en SapModel."""
    mat = meta["material"]
    mat_name = mat["name"]
    if hasattr(sap_model, "PropMaterial"):
        _check_ret(
            "SetMaterial",
            sap_model.PropMaterial.SetMaterial(mat_name, _mat_enum(int(mat["sap_mat_type"]))),
        )
        _check_ret(
            "SetMPIsotropic",
            sap_model.PropMaterial.SetMPIsotropic(
                mat_name, float(mat["E_kPa"]), float(mat["nu"]), float(mat["alpha_thermal"])
            ),
        )
        _check_ret(
            "SetWeightAndMass",
            sap_model.PropMaterial.SetWeightAndMass(mat_name, 1, float(mat["gamma_kN_m3"])),
        )

    if hasattr(sap_model, "PropFrame"):
        for sec_name, sec in meta["sections"].items():
            if sec["shape"] == "I":
                _check_ret(
                    "SetISection",
                    sap_model.PropFrame.SetISection(
                        sec_name,
                        sec["material_name"],
                        float(sec["h_m"]),
                        float(sec["b_m"]),
                        float(sec["tf_m"]),
                        float(sec["tw_m"]),
                        float(sec["b_m"]),
                        float(sec["tf_m"]),
                    ),
                )
            else:
                _check_ret(
                    "SetRectangle",
                    sap_model.PropFrame.SetRectangle(
                        sec_name,
                        sec["material_name"],
                        float(sec["h_m"]),
                        float(sec["b_m"]),
                    ),
                )


def _add_or_update_load_pattern(
    sap_model: Any, name: str, pat_code: int, sw_mult: float
) -> None:
    """Registra un patron de carga en SAP2000 verificando retorno (idempotente para DEAD)."""
    lp = sap_model.LoadPatterns
    ret = lp.Add(name, _load_pat_enum(pat_code), float(sw_mult), True)
    rc = ret[0] if isinstance(ret, (tuple, list)) and ret else ret
    if rc != 0 and name == "DEAD" and hasattr(lp, "SetSelfWTMultiplier"):
        _check_ret("LoadPatterns.SetSelfWTMultiplier", lp.SetSelfWTMultiplier(name, float(sw_mult)))
        return
    _check_ret("LoadPatterns.Add", ret)


def _apply_bridge_loads_and_combos_oapi(sap_model: Any, meta: dict[str, Any]) -> None:
    """Crea patrones de carga (DEAD, DW, LIVE_LANE, LIVE_VEHICLE_M, LIVE_VEHICLE_V),
    asigna cargas distribuidas (con reparto transversal excentrico Courbon en LIVE_LANE)
    y cargas puntuales de ejes sobre barra (FrameObj.SetLoadPoint, Dir=10 Gravity)
    y define combinaciones normativas.
    """
    loads = meta["loads_summary"]
    if hasattr(sap_model, "LoadPatterns"):
        # eLoadPatternType: 1=Dead, 2=SuperDead, 3=Live
        _add_or_update_load_pattern(sap_model, "DEAD", 1, 1.0)
        _add_or_update_load_pattern(sap_model, "DW", 2, 0.0)
        _add_or_update_load_pattern(sap_model, "LIVE_LANE", 3, 0.0)
        _add_or_update_load_pattern(sap_model, "LIVE_VEHICLE_M", 3, 0.0)
        _add_or_update_load_pattern(sap_model, "LIVE_VEHICLE_V", 3, 0.0)

    if hasattr(sap_model, "FrameObj") and hasattr(sap_model.FrameObj, "SetLoadDistributed"):
        q_slab = float(loads["q_slab_per_girder_kN_m"])
        q_dw = float(loads["q_dw_per_girder_kN_m"])
        q_lane_by_girder = loads.get("q_lane_by_girder_kN_m", {})
        q_lane_uniform = float(loads["q_lane_per_girder_kN_m"])
        # Dir=10 en SAP2000 OAPI es Gravity (hacia -Z global con valor positivo)
        for fid in loads["longitudinal_frames_loaded"]:
            ig = int(fid.split("_")[1])
            q_lane_ig = float(
                q_lane_by_girder.get(ig, q_lane_by_girder.get(str(ig), q_lane_uniform))
            )
            _check_ret(
                "SetLoadDistributed",
                sap_model.FrameObj.SetLoadDistributed(fid, "DEAD", 1, 10, 0.0, 1.0, q_slab, q_slab),
            )
            _check_ret(
                "SetLoadDistributed",
                sap_model.FrameObj.SetLoadDistributed(fid, "DW", 1, 10, 0.0, 1.0, q_dw, q_dw),
            )
            _check_ret(
                "SetLoadDistributed",
                sap_model.FrameObj.SetLoadDistributed(fid, "LIVE_LANE", 1, 10, 0.0, 1.0, q_lane_ig, q_lane_ig),
            )

    if hasattr(sap_model, "FrameObj") and hasattr(sap_model.FrameObj, "SetLoadPoint"):
        for pt in loads.get("frame_point_loads_LIVE_VEHICLE_M", []):
            _check_ret(
                "SetLoadPoint",
                sap_model.FrameObj.SetLoadPoint(
                    pt["frame_id"],
                    "LIVE_VEHICLE_M",
                    1,
                    10,
                    float(pt["dist_local_m"]),
                    float(pt["load_kN"]),
                    "Global",
                    False,
                    False,
                ),
            )
        for pt in loads.get("frame_point_loads_LIVE_VEHICLE_V", []):
            _check_ret(
                "SetLoadPoint",
                sap_model.FrameObj.SetLoadPoint(
                    pt["frame_id"],
                    "LIVE_VEHICLE_V",
                    1,
                    10,
                    float(pt["dist_local_m"]),
                    float(pt["load_kN"]),
                    "Global",
                    False,
                    False,
                ),
            )
    elif hasattr(sap_model, "PointObj") and hasattr(sap_model.PointObj, "SetLoadForce"):
        for jid, fz_kN in loads["nodal_loads_LIVE_VEHICLE_M_Fz_kN"].items():
            _check_ret(
                "SetLoadForce",
                sap_model.PointObj.SetLoadForce(jid, "LIVE_VEHICLE_M", [0.0, 0.0, float(fz_kN), 0.0, 0.0, 0.0]),
            )
        for jid, fz_kN in loads["nodal_loads_LIVE_VEHICLE_V_Fz_kN"].items():
            _check_ret(
                "SetLoadForce",
                sap_model.PointObj.SetLoadForce(jid, "LIVE_VEHICLE_V", [0.0, 0.0, float(fz_kN), 0.0, 0.0, 0.0]),
            )

    if hasattr(sap_model, "RespCombo"):
        cname_type = _cname_type_enum(0)
        for combo in loads["combinations"]:
            cname = combo["name"]
            # ComboType=0 -> Linear Additive
            _check_ret("RespCombo.Add", sap_model.RespCombo.Add(cname, 0))
            for case_name, factor in combo["factors"].items():
                # eCNameType=0 -> LoadCase
                _check_ret(
                    "RespCombo.SetCaseList",
                    sap_model.RespCombo.SetCaseList(cname, cname_type, case_name, float(factor)),
                )


def build_bridge_grillage(
    client: Any,
    *,
    L: float = 30.0,
    W: float = 10.0,
    n_girders: int = 4,
    n_diaphragms: int = 3,
    n_spans: int = 1,
    long_section: str = "HEM 1000",
    trans_section: str = "HEB 400",
    spec: BridgeDesignSpec | None = None,
    preview_only: bool = False,
) -> dict[str, Any]:
    """Construye el emparrillado de puente en SAP2000/CSiBridge vía OAPI verificando cada retorno.

    Si se proporciona ``spec`` (``BridgeDesignSpec`` procedente de ``bridge_spec_from_encargo``),
    sus dimensiones, conteos, materiales, secciones y cargas gobiernan la generacion.
    Cada llamada OAPI comprueba ``ret == 0``; si cualquier llamada devuelve ``ret != 0``,
    lanza inmediatamente :class:`OAPICallError`.
    """
    if spec is not None:
        L = spec.span_m
        W = spec.width_m
        n_girders = spec.n_girders
        n_diaphragms = spec.n_diaphragms
        n_spans = spec.n_spans
        long_section = spec.girder_section.name
        trans_section = spec.diaphragm_section.name

    model = grillage_model(
        L,
        W,
        n_girders,
        n_diaphragms,
        n_spans=n_spans,
        long_section=long_section,
        trans_section=trans_section,
        spec=spec,
    )
    joints = model["joints"]
    frames = model["frames"]
    counts = model["meta"]["derived_counts"]

    summary = {
        **model,
        "n_joints": counts["n_joints"],
        "n_frames": counts["n_frames"],
        "n_frames_long": counts["n_frames_long"],
        "n_frames_trans": counts["n_frames_trans"],
        "n_supports": counts["n_supports"],
    }
    if preview_only:
        return summary

    sap_model = getattr(client, "SapModel", client)
    if sap_model is None:
        raise RuntimeError(
            "client no expone SapModel (¿conectado a SAP2000/CSiBridge?). "
            "Usa preview_only=True para contar sin tocar el modelo."
        )

    # 1) Definir materiales y secciones transversales reales antes de crear barras
    _register_material_and_sections_oapi(sap_model, model["meta"])

    # 2) Nodos + apoyos cinematica y estaticamente estables en 3D
    for j in joints:
        _check_ret(
            "AddCartesian",
            sap_model.PointObj.AddCartesian(j["x"], j["y"], j["z"], j["id"], j["id"]),
        )
        if j["restraint"] is not None:
            _check_ret(
                "SetRestraint",
                sap_model.PointObj.SetRestraint(j["id"], list(j["restraint"])),
            )

    # 3) Barras (vigas longitudinales + diafragmas transversales)
    for f in frames:
        _check_ret(
            "AddByPoint",
            sap_model.FrameObj.AddByPoint(
                f["joint_i"], f["joint_j"], "", f["section"], f["id"]
            ),
        )

    # 4) Cargas de puente (DEAD, DW, LIVE_LANE, LIVE_VEHICLE_M, LIVE_VEHICLE_V) y combinaciones
    _apply_bridge_loads_and_combos_oapi(sap_model, model["meta"])

    return summary


def _safe_name_list(subobj: Any) -> list[str]:
    """Lee GetNameList de un subobjeto OAPI (o mock) verificando ret == 0."""
    if subobj is None or not hasattr(subobj, "GetNameList"):
        return []
    res = subobj.GetNameList(0, None)
    _check_ret(f"{type(subobj).__name__}.GetNameList", res)
    if isinstance(res, (tuple, list)) and len(res) >= 3:
        return [str(x) for x in (res[2] or []) if x]
    return []


def compute_expected_vertical_loads_kN(meta: dict[str, Any]) -> dict[str, float]:
    """Calcula la carga vertical gravitatoria total aplicada (hacia -Z, en kN) por patron y combo.

    - ``DEAD``: peso propio de vigas longitudinales (L_total * n_girders * A_girder * gamma)
      + peso propio de diafragmas transversales (n_x * W * A_diaph * gamma)
      + carga muerta de losa de hormigon sobre las vigas longitudinales.
    - ``DW``: pavimento + barreras sobre todas las vigas longitudinales.
    - ``LIVE_LANE``: sobrecarga uniforme de los carriles nocionales + area remanente.
    - ``LIVE_VEHICLE_M``: suma de ejes del vehiculo de diseno en posicion de M+.
    - ``LIVE_VEHICLE_V``: suma de ejes del vehiculo de diseno en posicion de Vmax.
    """
    loads = meta["loads_summary"]
    mat = meta["material"]
    sections = meta["sections"]
    gamma = float(mat["gamma_kN_m3"])
    L_tot = float(meta["total_length"])
    W = float(meta["width_m"])
    n_girders = int(meta["n_girders"])
    nx = int(meta["derived_counts"]["n_x"])

    sec_names = list(sections.keys())
    girder_sec = sections[sec_names[0]]
    diaph_sec = sections[sec_names[1]] if len(sec_names) > 1 else girder_sec

    # En SAP2000 SetISection(h, b, tf, tw, b, tf) modela las dos alas y el alma sin radios de acuerdo r;
    # cuando existe A_sap_iset_m2 leido de PropFrame.GetSectProps o calculado de 2*b*tf + (h-2*tf)*tw,
    # ese es el area que SAP2000 multiplica por gamma para el peso propio del elemento.
    def _sap_area(sec_dict: dict[str, Any]) -> float:
        if "A_sap_m2" in sec_dict:
            return float(sec_dict["A_sap_m2"])
        if sec_dict.get("shape") == "I":
            h_s = float(sec_dict["h_m"])
            b_s = float(sec_dict["b_m"])
            tf_s = float(sec_dict["tf_m"])
            tw_s = float(sec_dict["tw_m"])
            return 2.0 * b_s * tf_s + max(0.0, h_s - 2.0 * tf_s) * tw_s
        return float(sec_dict["A_m2"])

    sw_girders_kN = n_girders * L_tot * _sap_area(girder_sec) * gamma
    sw_diaphs_kN = nx * W * _sap_area(diaph_sec) * gamma
    slab_kN = n_girders * L_tot * float(loads["q_slab_per_girder_kN_m"])
    dead_total_kN = sw_girders_kN + sw_diaphs_kN + slab_kN

    dw_total_kN = n_girders * L_tot * float(loads["q_dw_per_girder_kN_m"])
    q_lane_by_g = loads.get("q_lane_by_girder_kN_m", {})
    if q_lane_by_g:
        live_lane_total_kN = sum(float(v) for v in q_lane_by_g.values()) * L_tot
    else:
        live_lane_total_kN = n_girders * L_tot * float(loads["q_lane_per_girder_kN_m"])

    veh_m_total_kN = sum(float(pt["load_kN"]) for pt in loads.get("frame_point_loads_LIVE_VEHICLE_M", []))
    veh_v_total_kN = sum(float(pt["load_kN"]) for pt in loads.get("frame_point_loads_LIVE_VEHICLE_V", []))

    out: dict[str, float] = {
        "DEAD_self_weight_girders_kN": round(sw_girders_kN, 4),
        "DEAD_self_weight_diaphragms_kN": round(sw_diaphs_kN, 4),
        "DEAD_slab_kN": round(slab_kN, 4),
        "DEAD": round(dead_total_kN, 4),
        "DW": round(dw_total_kN, 4),
        "LIVE_LANE": round(live_lane_total_kN, 4),
        "LIVE_VEHICLE_M": round(veh_m_total_kN, 4),
        "LIVE_VEHICLE_V": round(veh_v_total_kN, 4),
    }
    for combo in loads.get("combinations", []):
        cname = combo["name"]
        c_tot = 0.0
        for pat_name, sf in combo["factors"].items():
            c_tot += float(sf) * out.get(pat_name, 0.0)
        out[cname] = round(c_tot, 4)
    return out


def execute_bridge_grillage_analysis_and_reopen(
    client: Any,
    sdb_path: str,
    *,
    spec: BridgeDesignSpec | None = None,
    L: float = 30.0,
    W: float = 10.0,
    n_girders: int = 4,
    n_diaphragms: int = 3,
    n_spans: int = 1,
    equilibrium_tol_rel: float = 0.005,
) -> dict[str, Any]:
    """Ejecuta el ciclo nativo completo en SAP2000 sobre un cliente conectado (o mock de contrato):

    1. Construye el modelo con ``build_bridge_grillage(client, ...)`` verificando retornos OAPI.
    2. Verifica recuentos reales en memoria antes de guardar.
    3. Guarda el archivo ``.sdb`` y verifica su existencia y tamano en disco.
    4. Activa todos los casos de carga y ejecuta ``Analyze.RunAnalysis()``.
    5. Extrae desplazamientos nodales, reacciones en apoyos y esfuerzos concurrentes
       ``(P, V2, V3, T, M2, M3)`` en todas las barras longitudinales y transversales.
    6. Verifica equilibrio global entre cargas gravitatorias aplicadas y suma de reacciones ``Rz``,
       ausencia de coaccion longitudinal espuria en el estribo movil (``sum Rx(x=L) ~ 0``) y
       comportamiento transversal activo bajo carga excentrica.
    7. Reinicializa en blanco y reabre el archivo ``.sdb`` desde disco (``File.OpenFile``),
       leyendo de vuelta nudos, barras, apoyos, materiales, secciones, patrones y combinaciones,
       y evalua el contrato de reapertura ``fastsap.s2k_build.verdict.veredicto``.
    """
    from pathlib import Path
    from fastsap.oapi import (
        get_coord_cartesian,
        get_frame_forces,
        get_joint_displacements,
        get_joint_reactions,
        get_points,
        get_section,
    )
    from fastsap.s2k_build.verdict import veredicto

    sap_model = getattr(client, "SapModel", client)
    if sap_model is None:
        raise RuntimeError("client no expone SapModel")

    # 1) Construir el emparrillado verificando cada retorno OAPI
    build_summary = build_bridge_grillage(
        client,
        L=L,
        W=W,
        n_girders=n_girders,
        n_diaphragms=n_diaphragms,
        n_spans=n_spans,
        spec=spec,
    )
    meta = build_summary["meta"]
    expected_counts = meta["derived_counts"]
    joints_spec = build_summary["joints"]
    frames_spec = build_summary["frames"]
    support_joints = [j["id"] for j in joints_spec if j["restraint"] is not None]
    long_frames = [f["id"] for f in frames_spec if f["id"].startswith("L")]
    trans_frames = [f["id"] for f in frames_spec if f["id"].startswith("T")]

    # Configurar estaciones de salida en barras para incluir cargas puntuales y extremos
    if hasattr(sap_model, "FrameObj") and hasattr(sap_model.FrameObj, "SetOutputStations"):
        for f in frames_spec:
            _check_ret(
                f"FrameObj.SetOutputStations({f['id']})",
                sap_model.FrameObj.SetOutputStations(f["id"], 2, 0.0, 9, True, True),
            )

    # 2) Recuentos reales en el motor antes de guardar
    created_points = int(sap_model.PointObj.Count()) if hasattr(sap_model.PointObj, "Count") else len(joints_spec)
    created_frames = int(sap_model.FrameObj.Count()) if hasattr(sap_model.FrameObj, "Count") else len(frames_spec)
    created_materials = _safe_name_list(getattr(sap_model, "PropMaterial", None))
    created_sections = _safe_name_list(getattr(sap_model, "PropFrame", None))
    created_patterns = _safe_name_list(getattr(sap_model, "LoadPatterns", None))
    created_combos = _safe_name_list(getattr(sap_model, "RespCombo", None))

    if created_points != expected_counts["n_joints"]:
        raise RuntimeError(
            f"Recuento de nudos creados ({created_points}) != esperado ({expected_counts['n_joints']})"
        )
    if created_frames != expected_counts["n_frames"]:
        raise RuntimeError(
            f"Recuento de barras creadas ({created_frames}) != esperado ({expected_counts['n_frames']})"
        )

    # 3) Guardar el archivo .sdb
    p_sdb = Path(sdb_path).expanduser().resolve()
    p_sdb.parent.mkdir(parents=True, exist_ok=True)
    sdb_str = str(p_sdb).replace("/", "\\") if os.name == "nt" else str(p_sdb)
    if hasattr(client, "save"):
        client.save(sdb_str)
    else:
        _check_ret("File.Save", sap_model.File.Save(sdb_str))

    if not p_sdb.exists() or p_sdb.stat().st_size == 0:
        raise RuntimeError(f"El archivo .sdb no existe o está vacío tras File.Save: {p_sdb}")
    sdb_size_bytes = p_sdb.stat().st_size

    # 4) Ejecutar el analisis estatico en SAP2000
    if hasattr(sap_model, "Analyze"):
        if hasattr(sap_model.Analyze, "SetRunCaseFlag"):
            _check_ret("Analyze.SetRunCaseFlag", sap_model.Analyze.SetRunCaseFlag("", True, True))
        run_ret = sap_model.Analyze.RunAnalysis()
        _check_ret("Analyze.RunAnalysis", run_ret)
        run_rc = run_ret[0] if isinstance(run_ret, (tuple, list)) and run_ret else int(run_ret)
    else:
        raise RuntimeError("SapModel no expone Analyze.RunAnalysis")

    # 5) Seleccionar todos los casos y combinaciones para salida y extraer resultados
    load_cases = ["DEAD", "DW", "LIVE_LANE", "LIVE_VEHICLE_M", "LIVE_VEHICLE_V"]
    combo_names = [c["name"] for c in meta["loads_summary"]["combinations"]]

    if hasattr(sap_model, "Results") and hasattr(sap_model.Results, "Setup"):
        setup = sap_model.Results.Setup
        _check_ret("DeselectAllCasesAndCombosForOutput", setup.DeselectAllCasesAndCombosForOutput())
        for lc in load_cases:
            _check_ret(f"SetCaseSelectedForOutput({lc})", setup.SetCaseSelectedForOutput(lc))
        for cb in combo_names:
            _check_ret(f"SetComboSelectedForOutput({cb})", setup.SetComboSelectedForOutput(cb))

    # Extraer reacciones en los apoyos
    reactions_rows: list[dict[str, Any]] = []
    for jid in support_joints:
        for r in get_joint_reactions(sap_model, jid):
            reactions_rows.append({
                "joint": str(r["joint"]),
                "case": str(r["case"]),
                "Fx_kN": float(r["F1"]),
                "Fy_kN": float(r["F2"]),
                "Fz_kN": float(r["F3"]),
                "Mx_kNm": float(r["M1"]),
                "My_kNm": float(r["M2"]),
                "Mz_kNm": float(r["M3"]),
            })

    # Extraer desplazamientos nodales en todos los nudos
    displacements_rows: list[dict[str, Any]] = []
    for j in joints_spec:
        for d in get_joint_displacements(sap_model, j["id"]):
            displacements_rows.append({
                "joint": str(d["joint"]),
                "case": str(d["case"]),
                "Ux_m": float(d["Ux"]),
                "Uy_m": float(d["Uy"]),
                "Uz_m": float(d["Uz"]),
                "Rx_rad": float(d["Rx"]),
                "Ry_rad": float(d["Ry"]),
                "Rz_rad": float(d["Rz"]),
            })

    # Extraer esfuerzos concurrentes (P, V2, V3, T, M2, M3) en todas las barras
    frame_forces_rows: list[dict[str, Any]] = []
    for f in frames_spec:
        for fr in get_frame_forces(sap_model, f["id"]):
            frame_forces_rows.append({
                "frame": str(fr["obj"]),
                "role": f["role"],
                "station_m": float(fr["station"]),
                "case": str(fr["case"]),
                "P_kN": float(fr["P"]),
                "V2_kN": float(fr["V2"]),
                "V3_kN": float(fr["V3"]),
                "T_kNm": float(fr["T"]),
                "M2_kNm": float(fr["M2"]),
                "M3_kNm": float(fr["M3"]),
            })

    # 6) Comprobar equilibrio global entre cargas aplicadas y reacciones
    expected_fz = compute_expected_vertical_loads_kN(meta)
    equilibrium_by_case: dict[str, dict[str, Any]] = {}
    movable_joints = {
        j["id"] for j in joints_spec if j["restraint"] is not None and float(j["x"]) > 1e-4
    }
    for case_name in load_cases + combo_names:
        case_reac = [r for r in reactions_rows if r["case"] == case_name]
        sum_fx = sum(r["Fx_kN"] for r in case_reac)
        sum_fy = sum(r["Fy_kN"] for r in case_reac)
        sum_fz = sum(r["Fz_kN"] for r in case_reac)
        sum_fx_movable = sum(r["Fx_kN"] for r in case_reac if r["joint"] in movable_joints)
        applied_fz = float(expected_fz.get(case_name, 0.0))
        diff_fz = abs(sum_fz - applied_fz)
        rel_err = diff_fz / max(1.0, abs(applied_fz))
        ok_case = (rel_err <= equilibrium_tol_rel) and (abs(sum_fx_movable) <= 1e-3)
        equilibrium_by_case[case_name] = {
            "applied_vertical_load_kN": round(applied_fz, 4),
            "sum_Rz_reactions_kN": round(sum_fz, 4),
            "abs_diff_kN": round(diff_fz, 4),
            "rel_error": round(rel_err, 6),
            "sum_Rx_kN": round(sum_fx, 6),
            "sum_Ry_kN": round(sum_fy, 6),
            "sum_Rx_movable_abutment_kN": round(sum_fx_movable, 6),
            "equilibrium_ok": bool(ok_case),
        }
        if not ok_case:
            raise RuntimeError(
                f"Fallo de equilibrio global en caso {case_name!r}: "
                f"aplicada={applied_fz:.3f} kN, sum_Rz={sum_fz:.3f} kN (err={rel_err:.4%}), "
                f"sum_Rx_movil={sum_fx_movable:.6f} kN"
            )

    # Resumen de esfuerzos maximos y desplazamientos por rol (vigas longitudinales vs diafragmas)
    summary_by_case: dict[str, dict[str, Any]] = {}
    for case_name in load_cases + combo_names:
        f_long = [r for r in frame_forces_rows if r["case"] == case_name and r["role"] == "girder"]
        f_trans = [r for r in frame_forces_rows if r["case"] == case_name and r["role"] == "diaphragm"]
        d_case = [d for d in displacements_rows if d["case"] == case_name]

        # Esfuerzos por viga individual ig=0..n_girders-1 para evidenciar excentricidad transversal
        girder_peaks: dict[int, dict[str, float]] = {}
        for ig in range(int(meta["n_girders"])):
            f_ig = [r for r in f_long if r["frame"].endswith(f"_{ig}")]
            girder_peaks[ig] = {
                "M3_max_kNm": round(max((abs(r["M3_kNm"]) for r in f_ig), default=0.0), 3),
                "V2_max_kN": round(max((abs(r["V2_kN"]) for r in f_ig), default=0.0), 3),
                "T_max_kNm": round(max((abs(r["T_kNm"]) for r in f_ig), default=0.0), 3),
            }

        best_m3_row = max(f_long, key=lambda r: abs(r["M3_kNm"]), default=None)
        best_v2_row = max(f_long, key=lambda r: abs(r["V2_kN"]), default=None)
        best_diaph_m3 = max(f_trans, key=lambda r: abs(r["M3_kNm"]), default=None)
        best_diaph_v2 = max(f_trans, key=lambda r: abs(r["V2_kN"]), default=None)
        min_uz_row = min(d_case, key=lambda d: d["Uz_m"], default=None)

        summary_by_case[case_name] = {
            "girder_M3_max_kNm": round(abs(best_m3_row["M3_kNm"]), 3) if best_m3_row else 0.0,
            "girder_M3_governing": best_m3_row,
            "girder_V2_max_kN": round(abs(best_v2_row["V2_kN"]), 3) if best_v2_row else 0.0,
            "girder_V2_governing": best_v2_row,
            "girder_peaks_by_index": girder_peaks,
            "diaphragm_M3_max_kNm": round(abs(best_diaph_m3["M3_kNm"]), 3) if best_diaph_m3 else 0.0,
            "diaphragm_V2_max_kN": round(abs(best_diaph_v2["V2_kN"]), 3) if best_diaph_v2 else 0.0,
            "min_Uz_m": round(float(min_uz_row["Uz_m"]), 6) if min_uz_row else 0.0,
            "min_Uz_mm": round(float(min_uz_row["Uz_m"]) * 1000.0, 3) if min_uz_row else 0.0,
            "min_Uz_joint": min_uz_row["joint"] if min_uz_row else "",
        }

    # Guardar nuevamente con los resultados de analisis antes de cerrar/reabrir
    if hasattr(client, "save"):
        client.save(sdb_str)
    else:
        _check_ret("File.Save", sap_model.File.Save(sdb_str))

    # 7) Cerrar / reinicializar modelo en blanco y REABRIR el archivo .sdb persistido
    if hasattr(client, "new_blank_model"):
        client.new_blank_model()
    elif hasattr(sap_model, "File") and hasattr(sap_model.File, "NewBlank"):
        _check_ret("File.NewBlank", sap_model.File.NewBlank())

    if hasattr(client, "open_file"):
        client.open_file(sdb_str)
    else:
        _check_ret("File.OpenFile", sap_model.File.OpenFile(sdb_str))

    reopened_points = int(sap_model.PointObj.Count()) if hasattr(sap_model.PointObj, "Count") else 0
    reopened_frames = int(sap_model.FrameObj.Count()) if hasattr(sap_model.FrameObj, "Count") else 0
    reopened_materials = _safe_name_list(getattr(sap_model, "PropMaterial", None))
    reopened_sections = _safe_name_list(getattr(sap_model, "PropFrame", None))
    reopened_patterns = _safe_name_list(getattr(sap_model, "LoadPatterns", None))
    reopened_combos = _safe_name_list(getattr(sap_model, "RespCombo", None))

    # Verificar coordenadas y apoyos de los nudos reabiertos y secciones de las barras reabiertas
    reopened_supports_count = 0
    if hasattr(sap_model.PointObj, "GetRestraint"):
        for j in joints_spec:
            res_r = sap_model.PointObj.GetRestraint(j["id"], [False] * 6)
            _check_ret(f"PointObj.GetRestraint({j['id']})", res_r)
            r_vals = list(res_r[1]) if isinstance(res_r, (tuple, list)) and len(res_r) >= 2 else []
            if any(r_vals):
                reopened_supports_count += 1
            coords = get_coord_cartesian(sap_model.PointObj, j["id"])
            if (
                abs(coords[0] - float(j["x"])) > 1e-3
                or abs(coords[1] - float(j["y"])) > 1e-3
                or abs(coords[2] - float(j["z"])) > 1e-3
            ):
                raise RuntimeError(f"Coordenadas reabiertas de {j['id']} difieren: {coords} vs {j}")
    else:
        reopened_supports_count = expected_counts["n_supports"]

    undefined_sections: list[str] = []
    reopened_frame_sections: dict[str, str] = {}
    for f in frames_spec:
        sec_assigned = get_section(sap_model.FrameObj, f["id"])
        reopened_frame_sections[f["id"]] = sec_assigned
        if sec_assigned != f["section"] or sec_assigned not in reopened_sections:
            undefined_sections.append(f"{f['id']}:{sec_assigned}")
        pts = get_points(sap_model.FrameObj, f["id"])
        if pts != (f["joint_i"], f["joint_j"]):
            raise RuntimeError(f"Conectividad reabierta de {f['id']} difiere: {pts}")

    if reopened_points != expected_counts["n_joints"]:
        raise RuntimeError(f"Reapertura: nudos={reopened_points} != {expected_counts['n_joints']}")
    if reopened_frames != expected_counts["n_frames"]:
        raise RuntimeError(f"Reapertura: barras={reopened_frames} != {expected_counts['n_frames']}")
    if reopened_supports_count != expected_counts["n_supports"]:
        raise RuntimeError(
            f"Reapertura: apoyos={reopened_supports_count} != {expected_counts['n_supports']}"
        )

    verdict_input = {
        "barras_unicas_s2k": expected_counts["n_frames"],
        "n_barras": created_frames,
        "reabierto_barras": reopened_frames,
        "n_puntos_s2k": expected_counts["n_joints"],
        "n_puntos": created_points,
        "reabierto_puntos": reopened_points,
        "secciones_sin_definir": undefined_sections,
        "RunAnalysis_ret": run_rc,
        "predimensionado": False,
    }
    verdict_Persistence = veredicto(verdict_input)

    return {
        "sdb_path": sdb_str,
        "sdb_size_bytes": sdb_size_bytes,
        "units": "kN_m_C",
        "RunAnalysis_ret": run_rc,
        "counts": {
            "expected": expected_counts,
            "created": {
                "n_joints": created_points,
                "n_frames": created_frames,
                "n_frames_long": len(long_frames),
                "n_frames_trans": len(trans_frames),
                "n_supports": len(support_joints),
                "materials": created_materials,
                "sections": created_sections,
                "load_patterns": created_patterns,
                "combinations": created_combos,
            },
            "reopened": {
                "n_joints": reopened_points,
                "n_frames": reopened_frames,
                "n_supports": reopened_supports_count,
                "materials": reopened_materials,
                "sections": reopened_sections,
                "frame_sections": reopened_frame_sections,
                "load_patterns": reopened_patterns,
                "combinations": reopened_combos,
            },
        },
        "persistence_verdict": verdict_Persistence,
        "equilibrium_by_case": equilibrium_by_case,
        "summary_by_case": summary_by_case,
        "reactions": reactions_rows,
        "displacements": displacements_rows,
        "frame_forces": frame_forces_rows,
        "meta": meta,
        "structural_design_status": "PENDIENTE_TAREA_4_VERIFICACION_NORMATIVA",
    }


def _effective_fy_en10025_2(fy_nom_MPa: float, t_max_m: float) -> float:
    """Reduccion de limite elastico por espesor de chapa segun EN 10025-2 Tabla 7 / EN 1993-1-1 §3.2.1."""
    t_mm = t_max_m * 1000.0
    if fy_nom_MPa >= 350.0:  # S355
        if t_mm <= 16.0:
            return 355.0
        if t_mm <= 40.0:
            return 345.0
        if t_mm <= 63.0:
            return 335.0
        if t_mm <= 80.0:
            return 325.0
        return 315.0
    if fy_nom_MPa >= 270.0:  # S275
        if t_mm <= 16.0:
            return 275.0
        if t_mm <= 40.0:
            return 265.0
        if t_mm <= 63.0:
            return 255.0
        return 245.0
    return float(fy_nom_MPa)


def _classify_i_section_ec3(
    sec: dict[str, Any], fy_eff_MPa: float
) -> dict[str, Any]:
    """Clasifica una seccion doble T (laminada o armada soldada PG_*) segun EN 1993-1-1 §5.5 Tabla 5.2."""
    h = float(sec["h_m"])
    b = float(sec["b_m"])
    tf = float(sec["tf_m"])
    tw = float(sec["tw_m"])
    r = float(sec.get("r_m", 0.0))
    is_welded = str(sec["name"]).upper().startswith("PG_") or r <= 1e-6
    eps = math.sqrt(235.0 / max(1.0, fy_eff_MPa))
    # Vuelo libre de ala en compresion (EN 1993-1-1 Tabla 5.2 Hoja 2): c_f = (b - tw - 2*r) / 2
    # En viga soldada sin acuerdo laminado, se descuenta garganta nominal de soldadura a_w ~ 0 o c_f = (b - tw)/2
    cf = max(1e-6, 0.5 * (b - tw - 2.0 * r))
    cf_over_tf = cf / tf
    if cf_over_tf <= 9.0 * eps:
        flange_class = 1
    elif cf_over_tf <= 10.0 * eps:
        flange_class = 2
    elif cf_over_tf <= 14.0 * eps:
        flange_class = 3
    else:
        flange_class = 4

    # Alma en flexion pura (EN 1993-1-1 Tabla 5.2 Hoja 1): c_w = h - 2*tf - 2*r
    cw = max(1e-6, h - 2.0 * tf - 2.0 * r)
    cw_over_tw = cw / tw
    if cw_over_tw <= 72.0 * eps:
        web_class = 1
    elif cw_over_tw <= 83.0 * eps:
        web_class = 2
    elif cw_over_tw <= 124.0 * eps:
        web_class = 3
    else:
        web_class = 4

    sec_class = max(flange_class, web_class)
    return {
        "section_class": sec_class,
        "flange_class": flange_class,
        "web_class": web_class,
        "is_welded": is_welded,
        "epsilon": round(eps, 6),
        "cf_over_tf": round(cf_over_tf, 4),
        "cf_limit_class1": round(9.0 * eps, 4),
        "cf_limit_class2": round(10.0 * eps, 4),
        "cf_limit_class3": round(14.0 * eps, 4),
        "cw_over_tw": round(cw_over_tw, 4),
        "cw_limit_class1": round(72.0 * eps, 4),
        "cw_limit_class2": round(83.0 * eps, 4),
        "cw_limit_class3": round(124.0 * eps, 4),
    }


def _compute_member_capacities_ec3(
    sec: dict[str, Any],
    mat: dict[str, Any],
    *,
    L_ltb_m: float,
    gamma_M0: float = 1.00,
    gamma_M1: float = 1.10,
) -> dict[str, Any]:
    """Calcula las resistencias normativas de una seccion metalica segun
    EN 1993-1-1:2005+A1:2014 + EN 1993-2:2006 (puentes) + EN 1993-1-5:2006 (placas chapas):

    1. Clasificacion de seccion (§5.5 Tabla 5.2) y reduccion de fy por espesor (EN 10025-2).
    2. Resistencia plastica/elastica a flexion (§6.2.5): ``Mc,Rd = Wy * fy / gamma_M0``.
    3. Pandeo lateral-torsional LTB (§6.3.2.2 / §6.3.2.3): ``Mb,Rd = chi_LT * Wy * fy / gamma_M1``
       con longitud de arriostramiento ``L_LT`` igual a la separacion entre diafragmas ``T*``.
    4. Cortante plastico (§6.2.6) y abolladura del alma por cortante (EN 1993-1-5 §5.1-5.3):
       ``Vpl,Rd``, limite de alma no rigidizada ``hw/tw <= (72/eta)*eps``, ``Vb,Rd`` y ``Vc,Rd``.
    5. Resistencia axil ``Npl,Rd`` y flexion de eje debil ``Mc,z,Rd`` para interaccion concurrente M-V-N.
    """
    from fastsap.codes.ec3_ltb import Mcr_simple, chi_LT, lambda_LT

    h = float(sec["h_m"])
    b = float(sec["b_m"])
    tf = float(sec["tf_m"])
    tw = float(sec["tw_m"])
    r = float(sec.get("r_m", 0.0))
    hw = max(1e-6, h - 2.0 * tf)
    area = float(sec["A_m2"])
    i33 = float(sec["I33_m4"])
    i22 = float(sec["I22_m4"])
    j_tors = float(sec["J_m4"])
    av2 = float(sec["Av2_m2"])
    wel33 = float(sec["Wel33_m3"])
    wpl33 = float(sec["Wpl33_m3"])
    wel22 = i22 / max(1e-6, 0.5 * b)
    wpl22 = 0.5 * tf * (b ** 2) + 0.25 * hw * (tw ** 2)
    # Constante de alabeo Iw para perfil doble T simetrico: Iw = Iz * (h - tf)^2 / 4
    iw = i22 * ((h - tf) ** 2) / 4.0

    E_MPa = float(mat["E_kPa"]) / 1000.0
    nu = float(mat.get("nu", 0.30))
    G_MPa = E_MPa / (2.0 * (1.0 + nu))
    fy_nom_MPa = float(mat["fy_MPa"])
    t_max = max(tf, tw)
    fy_eff_MPa = _effective_fy_en10025_2(fy_nom_MPa, t_max)

    cls_info = _classify_i_section_ec3(sec, fy_eff_MPa)
    sec_class = int(cls_info["section_class"])
    is_welded = bool(cls_info["is_welded"])
    eps = float(cls_info["epsilon"])

    # Modulo resistente eficaz Wy segun clase (Clase 1/2 -> Wpl,y; Clase 3 -> Wel,y; Clase 4 -> reducido)
    if sec_class in (1, 2):
        wy_m3 = wpl33
        wz_m3 = wpl22
    elif sec_class == 3:
        wy_m3 = wel33
        wz_m3 = wel22
    else:
        # Clase 4 exige la seccion eficaz de EN 1993-1-5 §4, que NO esta implementada. Antes se
        # usaba `0.85 * Wel`, un coeficiente sin respaldo normativo (2026-10-25). Sin seccion eficaz
        # no hay resistencia: se devuelve la clasificacion y la marca, y el verificador lo trata
        # como NO_CALCULADO.
        return {
            "norma_aplicada": "EN 1993-1-1:2005+A1:2014 + EN 1993-2:2006 + EN 1993-1-5:2006",
            "fy_nominal_MPa": fy_nom_MPa,
            "fy_effective_MPa": fy_eff_MPa,
            "gamma_M0": gamma_M0,
            "gamma_M1": gamma_M1,
            "classification": cls_info,
            "class4_effective_section_not_implemented": True,
            "Wy_m3": None, "Wz_m3": None, "Iw_m6": round(iw, 10),
            "Mc_Rd_kNm": None, "Mpl_Rd_kNm": None, "Mel_Rd_kNm": None, "Mf_Rd_kNm": None,
            "Mcz_Rd_kNm": None, "Npl_Rd_kN": None, "L_LT_m": round(L_ltb_m, 4), "Mcr_kNm": None,
            "lambda_bar_LT": None, "ltb_curve": None, "chi_LT": None, "Mb_Rd_kNm": None,
            "Vpl_Rd_kN": None, "Vb_Rd_kN": None, "Vc_Rd_kN": None,
            "hw_over_tw": None, "hw_over_tw_unstiffened_limit": None, "lambda_w": None, "chi_w": None,
            "shear_buckling_active": None,
        }

    # Resistencia de seccion a flexion Mc,Rd (kN*m) y axil Npl,Rd (kN)
    # Nota: Wy (m^3) * fy (MPa = 1000 kN/m^2) -> kN*m
    Mc_Rd_kNm = (wy_m3 * fy_eff_MPa * 1000.0) / gamma_M0
    Mpl_Rd_kNm = (wpl33 * fy_eff_MPa * 1000.0) / gamma_M0
    Mel_Rd_kNm = (wel33 * fy_eff_MPa * 1000.0) / gamma_M0
    Mcz_Rd_kNm = (wz_m3 * fy_eff_MPa * 1000.0) / gamma_M0
    # Momento resistido solo por las alas Mf,Rd (EN 1993-1-5 §7.1)
    Mf_Rd_kNm = (b * tf * (h - tf) * fy_eff_MPa * 1000.0) / gamma_M0
    Npl_Rd_kN = (area * fy_eff_MPa * 1000.0) / gamma_M0

    # Pandeo lateral-torsional (LTB) con L_LT = distancia entre diafragmas T*
    # Reutilizamos directamente fastsap.codes.ec3_ltb (Mcr_simple, lambda_LT, chi_LT) en metros y MPa
    L_eff_m = max(0.10, L_ltb_m)
    Mcr_Nm = Mcr_simple(L_eff_m, i22, j_tors, iw, E_MPa=E_MPa, G_MPa=G_MPa, C1=1.0)
    Mcr_kNm = Mcr_Nm / 1000.0
    lam_bar_LT = lambda_LT(wy_m3, fy_eff_MPa, Mcr_Nm)
    hb_ratio = h / max(1e-6, b)
    if is_welded:
        ltb_curve = "d" if hb_ratio > 2.0 else "c"
        prof_cls = "welded_h_b_gt_2" if hb_ratio > 2.0 else "welded_h_b_le_2"
        chi_lt = chi_LT(lam_bar_LT, curve=ltb_curve, method="general", profile_class=prof_cls)
    else:
        ltb_curve = "c" if hb_ratio > 2.0 else "b"
        prof_cls = "rolled_h_b_gt_2" if hb_ratio > 2.0 else "rolled_h_b_le_2"
        chi_lt = chi_LT(lam_bar_LT, curve=ltb_curve, method="rolled", profile_class=prof_cls)
    Mb_Rd_kNm = (chi_lt * wy_m3 * fy_eff_MPa * 1000.0) / gamma_M1

    # Cortante plastico EN 1993-1-1 §6.2.6 y abolladura por cortante EN 1993-1-5 §5
    eta_w = 1.20 if fy_eff_MPa <= 460.0 else 1.00
    Vpl_Rd_kN = (av2 * (fy_eff_MPa / math.sqrt(3.0)) * 1000.0) / gamma_M0
    # Esbeltez del alma hw/tw frente al limite sin rigidizadores (72/eta)*eps (EN 1993-1-5 §5.1(2))
    hw_over_tw = (h - 2.0 * tf - 2.0 * r) / tw
    hw_over_tw_limit = (72.0 / eta_w) * eps
    k_tau = 5.34  # Alma sin rigidizadores intermedios transversales (EN 1993-1-5 §5.3)
    lam_w = hw_over_tw / (37.4 * eps * math.sqrt(k_tau))
    if hw_over_tw <= hw_over_tw_limit:
        chi_w = eta_w
        Vb_Rd_kN = (eta_w * hw * tw * (fy_eff_MPa / math.sqrt(3.0)) * 1000.0) / gamma_M1
        shear_buckling_active = False
    else:
        # EN 1993-1-5 Tabla 5.1 (apoyo extremo no rigido)
        if lam_w < 0.83 / eta_w:
            chi_w = eta_w
        elif lam_w < 1.08:
            chi_w = 0.83 / lam_w
        else:
            chi_w = 1.37 / (0.7 + lam_w)
        Vb_Rd_kN = (chi_w * hw * tw * (fy_eff_MPa / math.sqrt(3.0)) * 1000.0) / gamma_M1
        shear_buckling_active = True

    Vc_Rd_kN = min(Vpl_Rd_kN, Vb_Rd_kN)

    return {
        "norma_aplicada": "EN 1993-1-1:2005+A1:2014 + EN 1993-2:2006 + EN 1993-1-5:2006",
        "fy_nominal_MPa": fy_nom_MPa,
        "fy_effective_MPa": fy_eff_MPa,
        "gamma_M0": gamma_M0,
        "gamma_M1": gamma_M1,
        "classification": cls_info,
        "Wy_m3": round(wy_m3, 8),
        "Wz_m3": round(wz_m3, 8),
        "Iw_m6": round(iw, 10),
        "Mc_Rd_kNm": round(Mc_Rd_kNm, 3),
        "Mpl_Rd_kNm": round(Mpl_Rd_kNm, 3),
        "Mel_Rd_kNm": round(Mel_Rd_kNm, 3),
        "Mf_Rd_kNm": round(Mf_Rd_kNm, 3),
        "Mcz_Rd_kNm": round(Mcz_Rd_kNm, 3),
        "Npl_Rd_kN": round(Npl_Rd_kN, 3),
        "L_LT_m": round(L_ltb_m, 4),
        "Mcr_kNm": round(Mcr_kNm, 3),
        "lambda_bar_LT": round(lam_bar_LT, 4),
        "ltb_curve": ltb_curve,
        "chi_LT": round(chi_lt, 4),
        "Mb_Rd_kNm": round(Mb_Rd_kNm, 3),
        "Vpl_Rd_kN": round(Vpl_Rd_kN, 3),
        "Vb_Rd_kN": round(Vb_Rd_kN, 3),
        "Vc_Rd_kN": round(Vc_Rd_kN, 3),
        "hw_over_tw": round(hw_over_tw, 3),
        "hw_over_tw_unstiffened_limit": round(hw_over_tw_limit, 3),
        "lambda_w": round(lam_w, 4),
        "chi_w": round(chi_w, 4),
        "shear_buckling_active": shear_buckling_active,
    }


def _compute_member_capacities_aashto(
    sec: dict[str, Any],
    mat: dict[str, Any],
    *,
    L_b_m: float,
    phi_f: float = 1.00,
    phi_v: float = 1.00,
) -> dict[str, Any]:
    """Calcula las resistencias normativas de una seccion metalica segun AASHTO LRFD 9th Ed. §6.10
    (flexion, LTB §6.10.8.2.3, cortante y abolladura del alma §6.10.9.2).
    """
    h = float(sec["h_m"])
    b = float(sec["b_m"])
    tf = float(sec["tf_m"])
    tw = float(sec["tw_m"])
    hw = max(1e-6, h - 2.0 * tf)
    area = float(sec["A_m2"])
    i22 = float(sec["I22_m4"])
    wel33 = float(sec["Wel33_m3"])
    wpl33 = float(sec["Wpl33_m3"])
    wel22 = i22 / max(1e-6, 0.5 * b)

    E_MPa = float(mat["E_kPa"]) / 1000.0
    fy_MPa = float(mat["fy_MPa"])
    eps = math.sqrt(E_MPa / max(1.0, fy_MPa))

    # Proporciones de ala y alma AASHTO LRFD §6.10.2 y §6.10.6.2
    lambda_f = b / (2.0 * tf)
    lambda_pf = 0.38 * eps
    lambda_rf = 0.56 * eps
    compact_flange = lambda_f <= lambda_pf

    lambda_w = hw / tw
    lambda_pw = 2.59 * eps
    lambda_rw = 5.70 * eps
    compact_web = lambda_w <= lambda_pw
    sec_class = 1 if (compact_flange and compact_web) else (2 if lambda_f <= lambda_rf and lambda_w <= lambda_rw else 3)

    Mp_kNm = wpl33 * fy_MPa * 1000.0
    My_kNm = wel33 * fy_MPa * 1000.0
    Mc_Rd_kNm = phi_f * (Mp_kNm if sec_class == 1 else My_kNm)

    # Radio de giro efectivo para LTB AASHTO §6.10.8.2.3: rt = b_fc / sqrt(12*(1 + (1/3)*D_c*t_w/(b_fc*t_fc)))
    dc = 0.5 * hw
    rt_m = b / math.sqrt(12.0 * (1.0 + (dc * tw) / (3.0 * b * tf)))
    Lp_m = 1.0 * rt_m * eps
    Lr_m = math.pi * rt_m * math.sqrt(E_MPa / (0.7 * fy_MPa))
    if L_b_m <= Lp_m:
        Mn_ltb_kNm = Mp_kNm if sec_class == 1 else My_kNm
    elif L_b_m <= Lr_m:
        Fnc = fy_MPa * (1.0 - 0.3 * ((L_b_m - Lp_m) / max(1e-6, Lr_m - Lp_m)))
        Mn_ltb_kNm = min(Mp_kNm, wel33 * Fnc * 1000.0)
    else:
        Fcr = (math.pi ** 2 * E_MPa) / ((L_b_m / max(1e-6, rt_m)) ** 2)
        Mn_ltb_kNm = min(Mp_kNm, wel33 * Fcr * 1000.0)
    Mb_Rd_kNm = phi_f * Mn_ltb_kNm

    # Cortante AASHTO LRFD §6.10.9.2 (alma sin rigidizadores k = 5.0)
    k_v = 5.0
    lim1 = 1.12 * math.sqrt(E_MPa * k_v / fy_MPa)
    lim2 = 1.40 * math.sqrt(E_MPa * k_v / fy_MPa)
    if lambda_w <= lim1:
        C_v = 1.0
    elif lambda_w <= lim2:
        C_v = lim1 / lambda_w
    else:
        C_v = (1.57 * E_MPa * k_v) / ((lambda_w ** 2) * fy_MPa)
    Vp_kN = 0.58 * fy_MPa * hw * tw * 1000.0
    Vc_Rd_kN = phi_v * C_v * Vp_kN

    return {
        "norma_aplicada": "AASHTO LRFD Bridge Design Specifications 9th Ed. §6.10",
        "fy_nominal_MPa": fy_MPa,
        "fy_effective_MPa": fy_MPa,
        "phi_f": phi_f,
        "phi_v": phi_v,
        "classification": {
            "section_class": sec_class,
            "is_welded": str(sec["name"]).upper().startswith("PG_"),
            "lambda_f": round(lambda_f, 4),
            "lambda_pf": round(lambda_pf, 4),
            "lambda_w": round(lambda_w, 4),
            "lambda_pw": round(lambda_pw, 4),
        },
        "Wy_m3": round(wpl33 if sec_class == 1 else wel33, 8),
        "Wz_m3": round(wel22, 8),
        "Mc_Rd_kNm": round(Mc_Rd_kNm, 3),
        "Mpl_Rd_kNm": round(phi_f * Mp_kNm, 3),
        "Mel_Rd_kNm": round(phi_f * My_kNm, 3),
        "Mf_Rd_kNm": round(phi_f * b * tf * (h - tf) * fy_MPa * 1000.0, 3),
        "Mcz_Rd_kNm": round(phi_f * wel22 * fy_MPa * 1000.0, 3),
        "Npl_Rd_kN": round(phi_f * area * fy_MPa * 1000.0, 3),
        "L_LT_m": round(L_b_m, 4),
        "Lp_m": round(Lp_m, 4),
        "Lr_m": round(Lr_m, 4),
        "Mb_Rd_kNm": round(Mb_Rd_kNm, 3),
        "Vpl_Rd_kN": round(phi_v * Vp_kN, 3),
        "Vb_Rd_kN": round(Vc_Rd_kN, 3),
        "Vc_Rd_kN": round(Vc_Rd_kN, 3),
        "hw_over_tw": round(lambda_w, 3),
        "hw_over_tw_unstiffened_limit": round(lim1, 3),
        "C_v": round(C_v, 4),
        "shear_buckling_active": C_v < 1.0 - 1e-6,
    }


def verify_sap_section_properties(
    sap_model: Any,
    sec_props: SectionMechanicalProps | dict[str, Any],
    *,
    tol_rel: float = 0.03,
) -> dict[str, Any]:
    """Lee de vuelta ``PropFrame.GetSectProps`` desde SAP2000 y verifica que las propiedades
    geométricas/mecánicas creadas por el motor (``Area``, ``As2``, ``I33``, ``I22``, ``S33``, ``Z33``)
    coinciden con las propiedades esperadas de ``sec_props``.
    """
    from fastsap.oapi import get_section_props

    sec_d = sec_props.to_dict() if hasattr(sec_props, "to_dict") else dict(sec_props)
    name = str(sec_d["name"])
    h = float(sec_d["h_m"])
    b = float(sec_d["b_m"])
    tf = float(sec_d["tf_m"])
    tw = float(sec_d["tw_m"])
    hw = max(0.0, h - 2.0 * tf)
    # Propiedades analiticas exactas de la seccion 3-rectangulos que SAP2000 construye en SetISection
    exp_area = 2.0 * b * tf + hw * tw
    exp_i33 = (b * (h ** 3) - (b - tw) * (hw ** 3)) / 12.0
    exp_i22 = (2.0 * tf * (b ** 3) + hw * (tw ** 3)) / 12.0
    exp_s33 = exp_i33 / (0.5 * h)
    exp_z33 = b * tf * (h - tf) + 0.25 * tw * (hw ** 2)
    exp_as2 = h * tw

    prop_frame = getattr(sap_model, "PropFrame", None)
    if prop_frame is None or not hasattr(prop_frame, "GetSectProps"):
        return {
            "section_name": name,
            "verified_via_oapi": False,
            "A_sap_m2": round(exp_area, 8),
            "I33_sap_m4": round(exp_i33, 8),
            "I22_sap_m4": round(exp_i22, 8),
            "S33_sap_m3": round(exp_s33, 8),
            "Z33_sap_m3": round(exp_z33, 8),
            "As2_sap_m2": round(exp_as2, 8),
            "max_rel_diff": 0.0,
        }

    try:
        sap_p = get_section_props(prop_frame, name)
    except Exception:
        raw = prop_frame.GetSectProps(name, *(0.0,) * 12)
        _check_ret(f"PropFrame.GetSectProps({name})", raw)
        sap_p = {
            "area": float(raw[1]),
            "as2": float(raw[2]),
            "as3": float(raw[3]),
            "torsion": float(raw[4]),
            "i22": float(raw[5]),
            "i33": float(raw[6]),
            "s22": float(raw[7]),
            "s33": float(raw[8]),
            "z22": float(raw[9]),
            "z33": float(raw[10]),
            "r22": float(raw[11]),
            "r33": float(raw[12]),
        }

    comparisons = {
        "area": (sap_p["area"], exp_area),
        "i33": (sap_p["i33"], exp_i33),
        "i22": (sap_p["i22"], exp_i22),
        "s33": (sap_p["s33"], exp_s33),
        "z33": (sap_p["z33"], exp_z33),
        "as2": (sap_p["as2"], exp_as2),
    }
    rel_diffs: dict[str, float] = {}
    for k, (val_sap, val_exp) in comparisons.items():
        diff = abs(val_sap - val_exp) / max(1e-9, abs(val_exp))
        rel_diffs[k] = round(diff, 6)
        if diff > tol_rel:
            raise ValueError(
                f"Propiedad {k!r} de seccion {name!r} en SAP2000 ({val_sap:.6g}) "
                f"difiere de la esperada ({val_exp:.6g}) en {diff:.2%} > {tol_rel:.2%}"
            )

    return {
        "section_name": name,
        "verified_via_oapi": True,
        "A_sap_m2": round(sap_p["area"], 8),
        "I33_sap_m4": round(sap_p["i33"], 8),
        "I22_sap_m4": round(sap_p["i22"], 8),
        "S33_sap_m3": round(sap_p["s33"], 8),
        "Z33_sap_m3": round(sap_p["z33"], 8),
        "As2_sap_m2": round(sap_p["as2"], 8),
        "J_sap_m4": round(sap_p["torsion"], 8),
        "rel_diffs": rel_diffs,
        "max_rel_diff": max(rel_diffs.values()) if rel_diffs else 0.0,
    }


def _evaluate_concurrent_station_row(
    row: dict[str, Any],
    cap: dict[str, Any],
    *,
    norma: str,
) -> dict[str, Any]:
    """Evalua en una UNICA fila concurrente ``(frame, case, station_m)`` todos los ratios ULS:
    - Flexion pura de seccion: ``|M3| / Mc,Rd``
    - Estabilidad por pandeo lateral-torsional (LTB): ``|M3| / Mb,Rd``
    - Cortante vertical y abolladura del alma: ``|V2| / Vc,Rd``
    - Interaccion concurrente Flexion + Cortante + Axil (M-V-N) en la misma estacion:
      * Segun EN 1993-1-1 §6.2.8 / §6.2.9 / §6.3.3 y EN 1993-1-5 §7.1:
        cuando ``|V2,Ed| > 0.5 * Vc,Rd``, se reduce la resistencia del alma mediante
        ``rho = (2*|V2,Ed|/Vc,Rd - 1)^2``, penalizando tanto ``Mc,Rd,red`` como ``Mb,Rd,red``,
        y se suma la interaccion de esfuerzo axil concurrente ``|P| / Npl,Rd`` y momento
        transversal ``|M2| / Mcz,Rd``.
    """
    P_Ed = abs(float(row["P_kN"]))
    V2_Ed = abs(float(row["V2_kN"]))
    V3_Ed = abs(float(row.get("V3_kN", 0.0)))
    T_Ed = abs(float(row.get("T_kNm", 0.0)))
    M2_Ed = abs(float(row.get("M2_kNm", 0.0)))
    M3_Ed = abs(float(row["M3_kNm"]))

    Mc_Rd = float(cap["Mc_Rd_kNm"])
    Mb_Rd = float(cap["Mb_Rd_kNm"])
    Mf_Rd = float(cap["Mf_Rd_kNm"])
    Mpl_Rd = float(cap["Mpl_Rd_kNm"])
    Mcz_Rd = float(cap["Mcz_Rd_kNm"])
    Vc_Rd = float(cap["Vc_Rd_kN"])
    Npl_Rd = float(cap["Npl_Rd_kN"])

    dcr_flex_sec = M3_Ed / Mc_Rd if Mc_Rd > 0 else float("inf")
    dcr_ltb = M3_Ed / Mb_Rd if Mb_Rd > 0 else float("inf")
    dcr_shear = V2_Ed / Vc_Rd if Vc_Rd > 0 else float("inf")
    dcr_axial = P_Ed / Npl_Rd if Npl_Rd > 0 else float("inf")
    dcr_m2 = M2_Ed / Mcz_Rd if Mcz_Rd > 0 else 0.0

    # Interaccion concurrente M-V-N en la MISMA estacion y combinacion
    if dcr_shear > 0.5:
        rho = min(1.0, (2.0 * dcr_shear - 1.0) ** 2)
        # Fraccion resistida por el alma que se reduce por factor (1 - rho):
        # M_Rd,red = max(Mf_Rd, M_Rd - rho * (Mpl_Rd - Mf_Rd)) escalado para Mc_Rd y Mb_Rd
        web_moment_share = max(0.0, Mpl_Rd - Mf_Rd)
        Mc_Rd_mv = max(Mf_Rd, Mc_Rd - rho * web_moment_share)
        chi_ratio = Mb_Rd / max(1e-6, Mc_Rd)
        Mb_Rd_mv = max(chi_ratio * Mf_Rd, Mb_Rd - rho * chi_ratio * web_moment_share)
        dcr_mv_sec = M3_Ed / max(1e-6, Mc_Rd_mv)
        dcr_mv_ltb = M3_Ed / max(1e-6, Mb_Rd_mv)
        # Ecuacion (7.1) de EN 1993-1-5 §7.1: eta_1 + (1 - Mf,Rd/Mpl,Rd)*(2*eta_3 - 1)^2
        eta_1 = M3_Ed / max(1e-6, Mpl_Rd)
        dcr_en1993_1_5_eq71 = eta_1 + (1.0 - min(1.0, Mf_Rd / max(1e-6, Mpl_Rd))) * rho
    else:
        rho = 0.0
        Mc_Rd_mv = Mc_Rd
        Mb_Rd_mv = Mb_Rd
        dcr_mv_sec = dcr_flex_sec
        dcr_mv_ltb = dcr_ltb
        dcr_en1993_1_5_eq71 = dcr_flex_sec

    # Interaccion completa M3 + V2 + N + M2 concurrentes (EN 1993-1-1 §6.2.9 / §6.3.3 / AASHTO §6.8.2.3)
    dcr_mvn_concurrent = max(dcr_mv_sec, dcr_mv_ltb, dcr_en1993_1_5_eq71) + dcr_axial + 0.5 * dcr_m2

    checks_at_station = {
        "ELU_FLEXION_SECCION": round(dcr_flex_sec, 6),
        "ELU_PANDEO_LATERAL_TORSIONAL_LTB": round(dcr_ltb, 6),
        "ELU_CORTANTE_Y_ABOLLADURA_ALMA": round(dcr_shear, 6),
        "ELU_INTERACCION_CONCURRENTE_M_V_N": round(dcr_mvn_concurrent, 6),
    }
    gov_check_name = max(checks_at_station, key=lambda k: checks_at_station[k])
    gov_dcr = checks_at_station[gov_check_name]

    return {
        "frame": str(row["frame"]),
        "role": str(row.get("role", "girder")),
        "case": str(row["case"]),
        "station_m": round(float(row["station_m"]), 4),
        "P_kN": round(float(row["P_kN"]), 3),
        "V2_kN": round(float(row["V2_kN"]), 3),
        "V3_kN": round(V3_Ed, 3),
        "T_kNm": round(T_Ed, 3),
        "M2_kNm": round(M2_Ed, 3),
        "M3_kNm": round(float(row["M3_kNm"]), 3),
        "rho_shear_reduction": round(rho, 6),
        "Mc_Rd_effective_kNm": round(Mc_Rd_mv, 3),
        "Mb_Rd_effective_kNm": round(Mb_Rd_mv, 3),
        "Vc_Rd_kN": round(Vc_Rd, 3),
        "dcr_flexure_section": round(dcr_flex_sec, 6),
        "dcr_ltb": round(dcr_ltb, 6),
        "dcr_shear": round(dcr_shear, 6),
        "dcr_mvn_concurrent": round(dcr_mvn_concurrent, 6),
        "governing_check_at_station": gov_check_name,
        "max_dcr_at_station": round(gov_dcr, 6),
    }


def verify_bridge_grillage_results(
    analysis_report: dict[str, Any],
    *,
    spec: BridgeDesignSpec | None = None,
    live_deflection_ratio_limit: float = 800.0,
    total_deflection_ratio_limit: float = 500.0,
    gamma_M0: float = 1.00,
    gamma_M1: float = 1.10,
) -> dict[str, Any]:
    """Verificador normativo concurrente ULS/SLS sobre los esfuerzos y desplazamientos
    extraídos de SAP2000.

    - Evalúa cada estación, combinación y barra de forma estrictamente **concurrente**
      (``P, V2, V3, T, M2, M3`` de la misma fila ``(frame, case, station_m)``), sin combinar
      jamás máximos independientes de distintas estaciones o combinaciones.
    - No mezcla normativas: utiliza **EN 1993-1-1 + EN 1993-2 + EN 1993-1-5** cuando
      ``norma == "EN_1991_2"`` o **AASHTO LRFD 9th Ed. §6.10** cuando ``norma == "AASHTO_LRFD"``.
    - Si el análisis no convergió (``RunAnalysis_ret != 0``), faltan unidades o tablas de
      esfuerzos/desplazamientos/reacciones, o falla el equilibrio global, devuelve
      :attr:`CalculationStatus.NO_CALCULADO`.
    - Conserva las comprobaciones no implementadas (``UNIMPLEMENTED_CHECKS``) y resuelve:
      * ``CalculationStatus.CALCULADO_FALLA`` cuando algún estado límite implementado tiene ``DCR > 1.0``.
      * ``CalculationStatus.REQUIERE_REVISION`` cuando todos los estados límite implementados
        cumplen (``DCR <= 1.0``) pero existen comprobaciones obligatorias no implementadas
        (alabeo/bimomento, rigidizadores transversales, conectores de cortante, fatiga, neoprenos).
    """
    missing_inputs: list[str] = []
    if not isinstance(analysis_report, dict):
        missing_inputs.append("analysis_report")
    else:
        if analysis_report.get("RunAnalysis_ret") != 0:
            missing_inputs.append(f"RunAnalysis_ret={analysis_report.get('RunAnalysis_ret')!r}")
        if analysis_report.get("units") != "kN_m_C":
            missing_inputs.append(f"units={analysis_report.get('units')!r} (requerido 'kN_m_C')")
        if not analysis_report.get("frame_forces"):
            missing_inputs.append("frame_forces vacio")
        if not analysis_report.get("displacements"):
            missing_inputs.append("displacements vacio")
        if not analysis_report.get("reactions"):
            missing_inputs.append("reactions vacio")
        eq_map = analysis_report.get("equilibrium_by_case") or {}
        if not eq_map or any(not v.get("equilibrium_ok", False) for v in eq_map.values()):
            missing_inputs.append("equilibrium_by_case invalido o incumplido")

    if missing_inputs:
        status_nc = resolve_status(
            None,
            missing_inputs=missing_inputs,
            demand_present=False,
            capacity_present=False,
            analysis_executed=False,
            geometry_present=False,
            material_present=False,
            reinforcement_present=False,
        )
        return {
            "calculation_status": status_nc,
            "implemented_checks_status": CalculationStatus.NO_CALCULADO.value,
            "missing_inputs": missing_inputs,
            "max_dcr_uls": None,
            "max_dcr_sls": None,
            "max_dcr_overall": None,
            "checks": [],
            "unimplemented_checks": list(UNIMPLEMENTED_CHECKS),
        }

    meta = analysis_report["meta"]
    mat = meta["material"]
    sections = meta["sections"]
    # Las resistencias de abajo son de ACERO (EN 1993 / AASHTO §6.10). Una viga de hormigon
    # (seccion RECT, fy_MPa = fck, sin armadura) no se puede verificar con ellas (2026-10-25).
    if str(mat.get("material_type", "steel")).lower() != "steel":
        motivo = (f"verificacion de {mat.get('material_type')} ({mat.get('name')}) no implementada: "
                  "las vigas de hormigon requieren EN 1992-2 / AASHTO LRFD §5 con armadura, "
                  "no las resistencias de acero de este verificador")
        return {
            "calculation_status": CalculationStatus.NO_CALCULADO,
            "implemented_checks_status": CalculationStatus.NO_CALCULADO.value,
            "missing_inputs": [motivo],
            "max_dcr_uls": None,
            "max_dcr_sls": None,
            "max_dcr_overall": None,
            "checks": [],
            "unimplemented_checks": list(UNIMPLEMENTED_CHECKS),
        }
    span_m = float(meta["span_length"])
    width_m = float(meta["width_m"])
    n_girders = int(meta["n_girders"])
    div_per_span = int(meta["divisions_per_span"])
    girder_spacing_m = float(meta["girder_spacing"])
    L_ltb_girder_m = span_m / max(1, div_per_span)
    L_ltb_diaph_m = girder_spacing_m

    loads_sum = meta["loads_summary"]
    traffic_code = str(loads_sum.get("traffic_code", "EN_1991_2_LM1"))
    norma = spec.norma if spec is not None else ("AASHTO_LRFD" if "AASHTO" in traffic_code else "EN_1991_2")

    frame_forces: list[dict[str, Any]] = analysis_report["frame_forces"]
    displacements: list[dict[str, Any]] = analysis_report["displacements"]
    reactions: list[dict[str, Any]] = analysis_report["reactions"]

    # Identificar nombres de seccion de viga longitudinal y diafragma transversal
    sec_names = list(sections.keys())
    girder_sec_name = sec_names[0]
    diaph_sec_name = sec_names[1] if len(sec_names) > 1 else sec_names[0]
    for f in analysis_report.get("frames", []):
        if f.get("role") == "girder":
            girder_sec_name = f["section"]
            break
    for f in analysis_report.get("frames", []):
        if f.get("role") == "diaphragm":
            diaph_sec_name = f["section"]
            break

    girder_sec = sections[girder_sec_name]
    diaph_sec = sections.get(diaph_sec_name, girder_sec)

    if norma == "AASHTO_LRFD":
        girder_cap = _compute_member_capacities_aashto(girder_sec, mat, L_b_m=L_ltb_girder_m)
        diaph_cap = _compute_member_capacities_aashto(diaph_sec, mat, L_b_m=L_ltb_diaph_m)
        uls_combos = ["ULS_STRENGTH_I", "ULS_STRENGTH_I_SHEAR"]
        sls_total_combo = "SLS_SERVICE_II"
    else:
        girder_cap = _compute_member_capacities_ec3(
            girder_sec, mat, L_ltb_m=L_ltb_girder_m, gamma_M0=gamma_M0, gamma_M1=gamma_M1
        )
        diaph_cap = _compute_member_capacities_ec3(
            diaph_sec, mat, L_ltb_m=L_ltb_diaph_m, gamma_M0=gamma_M0, gamma_M1=gamma_M1
        )
        uls_combos = ["ULS_STR", "ULS_STR_SHEAR"]
        sls_total_combo = "SLS_CHARACTERISTIC"

    clase4 = [f"{rol} {nom}" for rol, nom, cap in (("viga", girder_sec_name, girder_cap),
                                                    ("diafragma", diaph_sec_name, diaph_cap))
              if cap.get("class4_effective_section_not_implemented")]
    if clase4:
        return {
            "calculation_status": CalculationStatus.NO_CALCULADO,
            "implemented_checks_status": CalculationStatus.NO_CALCULADO.value,
            "missing_inputs": [f"seccion clase 4 ({', '.join(clase4)}): la seccion eficaz de "
                               "EN 1993-1-5 §4 no esta implementada"],
            "max_dcr_uls": None,
            "max_dcr_sls": None,
            "max_dcr_overall": None,
            "checks": [],
            "unimplemented_checks": list(UNIMPLEMENTED_CHECKS),
        }

    # Filtrar filas ULS de vigas longitudinales (L*) y diafragmas (T*)
    girder_uls_rows = [
        r for r in frame_forces if r.get("role") == "girder" and r["case"] in uls_combos
    ]
    diaph_uls_rows = [
        r for r in frame_forces if r.get("role") == "diaphragm" and r["case"] in uls_combos
    ]

    if not girder_uls_rows:
        return {
            "calculation_status": CalculationStatus.NO_CALCULADO,
            "implemented_checks_status": CalculationStatus.NO_CALCULADO.value,
            "missing_inputs": ["Sin filas ULS para vigas longitudinales"],
            "max_dcr_uls": None,
            "max_dcr_sls": None,
            "max_dcr_overall": None,
            "checks": [],
            "unimplemented_checks": list(UNIMPLEMENTED_CHECKS),
        }

    girder_evals = [_evaluate_concurrent_station_row(r, girder_cap, norma=norma) for r in girder_uls_rows]
    diaph_evals = [_evaluate_concurrent_station_row(r, diaph_cap, norma=norma) for r in diaph_uls_rows]

    gov_flex_row = max(girder_evals, key=lambda e: e["dcr_flexure_section"])
    gov_ltb_row = max(girder_evals, key=lambda e: e["dcr_ltb"])
    gov_shear_row = max(girder_evals, key=lambda e: e["dcr_shear"])
    gov_mvn_row = max(girder_evals, key=lambda e: e["dcr_mvn_concurrent"])
    gov_diaph_row = max(diaph_evals, key=lambda e: e["dcr_mvn_concurrent"]) if diaph_evals else None

    # Evaluacion SLS de flechas nodales reales en SAP2000:
    # 1. Flecha activa de trafico (LIVE_LANE + LIVE_VEHICLE_M concurrentes en el mismo nudo)
    # 2. Flecha caracteristica / Service total (SLS_CHARACTERISTIC o SLS_SERVICE_II)
    uz_by_joint_case: dict[tuple[str, str], float] = {
        (str(d["joint"]), str(d["case"])): float(d["Uz_m"]) for d in displacements
    }
    all_joints = sorted({str(d["joint"]) for d in displacements})

    best_live_defl_mm = 0.0
    best_live_joint = ""
    for jid in all_joints:
        uz_lane = uz_by_joint_case.get((jid, "LIVE_LANE"), 0.0)
        uz_veh_m = uz_by_joint_case.get((jid, "LIVE_VEHICLE_M"), 0.0)
        uz_veh_v = uz_by_joint_case.get((jid, "LIVE_VEHICLE_V"), 0.0)
        defl_m_mm = abs(uz_lane + uz_veh_m) * 1000.0
        defl_v_mm = abs(uz_lane + uz_veh_v) * 1000.0
        defl_j_mm = max(defl_m_mm, defl_v_mm)
        if defl_j_mm >= best_live_defl_mm:
            best_live_defl_mm = defl_j_mm
            best_live_joint = jid

    best_total_defl_mm = 0.0
    best_total_joint = ""
    for jid in all_joints:
        uz_sls = uz_by_joint_case.get((jid, sls_total_combo), 0.0)
        defl_tot_mm = abs(uz_sls) * 1000.0
        if defl_tot_mm >= best_total_defl_mm:
            best_total_defl_mm = defl_tot_mm
            best_total_joint = jid

    live_limit_mm = (span_m * 1000.0) / live_deflection_ratio_limit
    total_limit_mm = (span_m * 1000.0) / total_deflection_ratio_limit
    dcr_sls_live = best_live_defl_mm / max(1e-6, live_limit_mm)
    dcr_sls_total = best_total_defl_mm / max(1e-6, total_limit_mm)

    # Verificacion de reacciones en apoyos (compresion vertical sin levantamiento bajo cargas gravitatorias)
    uls_reactions = [r for r in reactions if r["case"] in uls_combos]
    min_rz_uls_kN = min((float(r["Fz_kN"]) for r in uls_reactions), default=0.0)
    max_rz_uls_kN = max((float(r["Fz_kN"]) for r in uls_reactions), default=0.0)
    max_rx_uls_kN = max((abs(float(r["Fx_kN"])) for r in uls_reactions), default=0.0)
    max_ry_uls_kN = max((abs(float(r["Fy_kN"])) for r in uls_reactions), default=0.0)
    # Si hay levantamiento neto significativo (Fz < -1.0 kN), penalizar con DCR > 1.0
    dcr_support_uplift = 0.0 if min_rz_uls_kN >= -1e-3 else (1.0 + abs(min_rz_uls_kN) / max(1.0, max_rz_uls_kN))

    def _status_for_dcr(dcr_val: float) -> CalculationStatus:
        return resolve_status(
            dcr_val,
            demand_present=True,
            capacity_present=True,
            analysis_executed=True,
            geometry_present=True,
            material_present=True,
            reinforcement_present=True,
        )

    checks_list: list[dict[str, Any]] = [
        {
            "check_id": "ELU_FLEXION_SECCION_VIGA",
            "category": "ULS",
            "role": "girder",
            "section": girder_sec_name,
            "norm_ref": (
                "EN 1993-1-1 §6.2.5 + EN 1993-2 §6.2.5"
                if norma != "AASHTO_LRFD"
                else "AASHTO LRFD §6.10.7 / §6.10.8"
            ),
            "governing_member": gov_flex_row["frame"],
            "governing_combo": gov_flex_row["case"],
            "governing_station_m": gov_flex_row["station_m"],
            "demand_M3_kNm": round(abs(gov_flex_row["M3_kNm"]), 3),
            "concurrent_V2_kN": round(abs(gov_flex_row["V2_kN"]), 3),
            "concurrent_P_kN": round(abs(gov_flex_row["P_kN"]), 3),
            "concurrent_T_kNm": round(abs(gov_flex_row["T_kNm"]), 3),
            "capacity_Mc_Rd_kNm": girder_cap["Mc_Rd_kNm"],
            "dcr": gov_flex_row["dcr_flexure_section"],
            "status": _status_for_dcr(gov_flex_row["dcr_flexure_section"]).value,
        },
        {
            "check_id": "ELU_PANDEO_LATERAL_TORSIONAL_LTB_VIGA",
            "category": "ULS",
            "role": "girder",
            "section": girder_sec_name,
            "norm_ref": (
                f"EN 1993-1-1 §6.3.2 + EN 1993-2 §6.3.2 (L_LT={L_ltb_girder_m:.2f} m, curva {girder_cap.get('ltb_curve', 'c')})"
                if norma != "AASHTO_LRFD"
                else f"AASHTO LRFD §6.10.8.2.3 (L_b={L_ltb_girder_m:.2f} m)"
            ),
            "governing_member": gov_ltb_row["frame"],
            "governing_combo": gov_ltb_row["case"],
            "governing_station_m": gov_ltb_row["station_m"],
            "demand_M3_kNm": round(abs(gov_ltb_row["M3_kNm"]), 3),
            "concurrent_V2_kN": round(abs(gov_ltb_row["V2_kN"]), 3),
            "concurrent_P_kN": round(abs(gov_ltb_row["P_kN"]), 3),
            "capacity_Mb_Rd_kNm": girder_cap["Mb_Rd_kNm"],
            "dcr": gov_ltb_row["dcr_ltb"],
            "status": _status_for_dcr(gov_ltb_row["dcr_ltb"]).value,
        },
        {
            "check_id": "ELU_CORTANTE_Y_ABOLLADURA_ALMA_VIGA",
            "category": "ULS",
            "role": "girder",
            "section": girder_sec_name,
            "norm_ref": (
                "EN 1993-1-1 §6.2.6 + EN 1993-1-5 §5.1-5.3"
                if norma != "AASHTO_LRFD"
                else "AASHTO LRFD §6.10.9.2"
            ),
            "governing_member": gov_shear_row["frame"],
            "governing_combo": gov_shear_row["case"],
            "governing_station_m": gov_shear_row["station_m"],
            "demand_V2_kN": round(abs(gov_shear_row["V2_kN"]), 3),
            "concurrent_M3_kNm": round(abs(gov_shear_row["M3_kNm"]), 3),
            "concurrent_P_kN": round(abs(gov_shear_row["P_kN"]), 3),
            "capacity_Vc_Rd_kN": girder_cap["Vc_Rd_kN"],
            "dcr": gov_shear_row["dcr_shear"],
            "status": _status_for_dcr(gov_shear_row["dcr_shear"]).value,
        },
        {
            "check_id": "ELU_INTERACCION_CONCURRENTE_M_V_N_VIGA",
            "category": "ULS",
            "role": "girder",
            "section": girder_sec_name,
            "norm_ref": (
                "EN 1993-1-1 §6.2.8/§6.2.9/§6.3.3 + EN 1993-1-5 §7.1"
                if norma != "AASHTO_LRFD"
                else "AASHTO LRFD §6.8.2.3 / §6.10.8"
            ),
            "governing_member": gov_mvn_row["frame"],
            "governing_combo": gov_mvn_row["case"],
            "governing_station_m": gov_mvn_row["station_m"],
            "demand_M3_kNm": round(abs(gov_mvn_row["M3_kNm"]), 3),
            "concurrent_V2_kN": round(abs(gov_mvn_row["V2_kN"]), 3),
            "concurrent_P_kN": round(abs(gov_mvn_row["P_kN"]), 3),
            "concurrent_M2_kNm": round(abs(gov_mvn_row["M2_kNm"]), 3),
            "rho_shear_reduction": gov_mvn_row["rho_shear_reduction"],
            "capacity_Mb_Rd_effective_kNm": gov_mvn_row["Mb_Rd_effective_kNm"],
            "dcr": gov_mvn_row["dcr_mvn_concurrent"],
            "status": _status_for_dcr(gov_mvn_row["dcr_mvn_concurrent"]).value,
        },
    ]

    if gov_diaph_row is not None:
        checks_list.append({
            "check_id": "ELU_DIAFRAGMA_TRANSVERSAL_M_V_CONCURRENTE",
            "category": "ULS",
            "role": "diaphragm",
            "section": diaph_sec_name,
            "norm_ref": (
                "EN 1993-1-1 §6.2.5/§6.2.6/§6.2.8"
                if norma != "AASHTO_LRFD"
                else "AASHTO LRFD §6.10.7/§6.10.9"
            ),
            "governing_member": gov_diaph_row["frame"],
            "governing_combo": gov_diaph_row["case"],
            "governing_station_m": gov_diaph_row["station_m"],
            "demand_M3_kNm": round(abs(gov_diaph_row["M3_kNm"]), 3),
            "concurrent_V2_kN": round(abs(gov_diaph_row["V2_kN"]), 3),
            "capacity_Mc_Rd_kNm": diaph_cap["Mc_Rd_kNm"],
            "capacity_Vc_Rd_kN": diaph_cap["Vc_Rd_kN"],
            "dcr": gov_diaph_row["dcr_mvn_concurrent"],
            "status": _status_for_dcr(gov_diaph_row["dcr_mvn_concurrent"]).value,
        })

    checks_list.extend([
        {
            "check_id": "ELU_ESTABILIDAD_VERTICAL_APOYOS_SIN_LEVANTAMIENTO",
            "category": "ULS",
            "role": "support",
            "section": "BEARINGS",
            "norm_ref": "EN 1990 Anexo A2 §A2.4.1 / AASHTO LRFD §3.11 (R_z,min >= 0 sin despegue)",
            "governing_member": "SUPPORTS",
            "governing_combo": uls_combos[0],
            "governing_station_m": 0.0,
            "min_Rz_kN": round(min_rz_uls_kN, 3),
            "max_Rz_kN": round(max_rz_uls_kN, 3),
            "max_Rx_kN": round(max_rx_uls_kN, 3),
            "max_Ry_kN": round(max_ry_uls_kN, 3),
            "dcr": round(dcr_support_uplift, 6),
            "status": _status_for_dcr(dcr_support_uplift).value,
        },
        {
            "check_id": "ELS_FLECHA_ACTIVA_TRAFICO",
            "category": "SLS",
            "role": "girder",
            "section": girder_sec_name,
            "norm_ref": (
                f"EN 1993-2 §7.2 / IAP-11 / AASHTO LRFD §2.5.2.6.2 (delta_LL <= L/{int(live_deflection_ratio_limit)} = {live_limit_mm:.2f} mm)"
            ),
            "governing_member": best_live_joint,
            "governing_combo": "LIVE_LANE+LIVE_VEHICLE_M",
            "governing_station_m": round(span_m / 2.0, 3),
            "demand_deflection_mm": round(best_live_defl_mm, 3),
            "limit_deflection_mm": round(live_limit_mm, 3),
            "dcr": round(dcr_sls_live, 6),
            "status": _status_for_dcr(dcr_sls_live).value,
        },
        {
            "check_id": "ELS_FLECHA_TOTAL_CARACTERISTICA",
            "category": "SLS",
            "role": "girder",
            "section": girder_sec_name,
            "norm_ref": (
                f"EN 1990 §6.5.3 / EN 1993-2 §7.2 (delta_total <= L/{int(total_deflection_ratio_limit)} = {total_limit_mm:.2f} mm)"
            ),
            "governing_member": best_total_joint,
            "governing_combo": sls_total_combo,
            "governing_station_m": round(span_m / 2.0, 3),
            "demand_deflection_mm": round(best_total_defl_mm, 3),
            "limit_deflection_mm": round(total_limit_mm, 3),
            "dcr": round(dcr_sls_total, 6),
            "status": _status_for_dcr(dcr_sls_total).value,
        },
    ])

    uls_checks = [c for c in checks_list if c["category"] == "ULS"]
    sls_checks = [c for c in checks_list if c["category"] == "SLS"]
    max_dcr_uls = max(c["dcr"] for c in uls_checks)
    max_dcr_sls = max(c["dcr"] for c in sls_checks)
    gov_overall_check = max(checks_list, key=lambda c: c["dcr"])
    max_dcr_overall = gov_overall_check["dcr"]

    agg_implemented = aggregate_calculation_statuses([c["status"] for c in checks_list])
    unimplemented = list(meta.get("comprobaciones_no_implementadas", UNIMPLEMENTED_CHECKS))

    # Regla innegociable de honestidad:
    # - Si cualquier estado limite implementado falla (DCR > 1.0) -> CALCULADO_FALLA (implemented_checks_status="FALLA").
    # - Si todos los estados limite implementados cumplen (DCR <= 1.0), implemented_checks_status="CUMPLE",
    #   pero si existen comprobaciones obligatorias de puente no implementadas -> calculation_status=REQUIERE_REVISION.
    # - Solo si todas las comprobaciones aplicables estuvieran implementadas y cumplieran -> CALCULADO_CUMPLE.
    if agg_implemented == CalculationStatus.CALCULADO_FALLA:
        overall_status = CalculationStatus.CALCULADO_FALLA
        implemented_status_str = "FALLA"
    elif agg_implemented == CalculationStatus.NO_CALCULADO:
        overall_status = CalculationStatus.NO_CALCULADO
        implemented_status_str = CalculationStatus.NO_CALCULADO.value
    elif unimplemented:
        overall_status = CalculationStatus.REQUIERE_REVISION
        implemented_status_str = "CUMPLE"
    else:
        overall_status = agg_implemented
        implemented_status_str = "CUMPLE"

    return {
        "norma": norma,
        "girder_section": girder_sec_name,
        "diaphragm_section": diaph_sec_name,
        "girder_capacities": girder_cap,
        "diaphragm_capacities": diaph_cap,
        "checks": checks_list,
        "governing_check": gov_overall_check,
        "governing_girder_uls_station": gov_mvn_row,
        "governing_diaphragm_uls_station": gov_diaph_row,
        "max_dcr_uls": round(max_dcr_uls, 6),
        "max_dcr_sls": round(max_dcr_sls, 6),
        "max_dcr_overall": round(max_dcr_overall, 6),
        "sls_deflections": {
            "active_traffic_deflection_mm": round(best_live_defl_mm, 3),
            "active_traffic_limit_mm": round(live_limit_mm, 3),
            "active_traffic_ratio_limit": f"L/{int(live_deflection_ratio_limit)}",
            "active_traffic_governing_joint": best_live_joint,
            "active_traffic_dcr": round(dcr_sls_live, 6),
            "total_characteristic_deflection_mm": round(best_total_defl_mm, 3),
            "total_characteristic_limit_mm": round(total_limit_mm, 3),
            "total_characteristic_ratio_limit": f"L/{int(total_deflection_ratio_limit)}",
            "total_characteristic_governing_joint": best_total_joint,
            "total_characteristic_dcr": round(dcr_sls_total, 6),
            "criterion_justification": (
                f"Flecha activa de tráfico limitada a L/{int(live_deflection_ratio_limit)} ({live_limit_mm:.2f} mm) "
                f"conforme a IAP-11 §4.3.2 / AASHTO LRFD §2.5.2.6.2 / EN 1993-2 §7.2 para puentes de carretera "
                f"y flecha total característica limitada a L/{int(total_deflection_ratio_limit)} ({total_limit_mm:.2f} mm)."
            ),
        },
        "implemented_checks_status": implemented_status_str,
        "calculation_status": overall_status,
        "unimplemented_checks": unimplemented,
        "missing_inputs": [],
    }


def run_bridge_grillage_sap2000(
    sdb_path: str,
    *,
    spec: BridgeDesignSpec | None = None,
    L: float = 30.0,
    W: float = 10.0,
    n_girders: int = 4,
    n_diaphragms: int = 3,
    n_spans: int = 1,
    visible: bool = False,
    keep_open: bool = False,
    sap_install_dir: str | None = None,
) -> dict[str, Any]:
    """Arranca una sesion real de SAP2000 v26 en unidades ``kN_m_C``, construye y analiza
    el emparrillado de puente, verifica equilibrio global y reapertura del ``.sdb`` y
    cierra limpiamente la instancia creada.
    """
    from fastsap.client import SapClient

    with SapClient(
        sap_install_dir=sap_install_dir,
        visible=visible,
        units="kN_m_C",
        keep_open=keep_open,
        run_probe=False,
    ) as client:
        return execute_bridge_grillage_analysis_and_reopen(
            client,
            sdb_path,
            spec=spec,
            L=L,
            W=W,
            n_girders=n_girders,
            n_diaphragms=n_diaphragms,
            n_spans=n_spans,
        )


def _run_single_sap_analysis_and_extract(
    client: Any,
    sap_model: Any,
    sdb_str: str,
    *,
    meta: dict[str, Any],
    joints_spec: list[dict[str, Any]],
    frames_spec: list[dict[str, Any]],
    equilibrium_tol_rel: float = 0.005,
) -> dict[str, Any]:
    """Guarda el modelo ``.sdb``, ejecuta ``Analyze.RunAnalysis()``, extrae reacciones,
    desplazamientos y esfuerzos concurrentes ``(P, V2, V3, T, M2, M3)``, y comprueba el
    equilibrio global con el peso propio de las secciones vigentes en ``meta``.
    """
    from pathlib import Path
    from fastsap.oapi import (
        get_frame_forces,
        get_joint_displacements,
        get_joint_reactions,
    )

    support_joints = [j["id"] for j in joints_spec if j["restraint"] is not None]
    p_sdb = Path(sdb_str)

    if hasattr(client, "save"):
        client.save(sdb_str)
    else:
        _check_ret("File.Save", sap_model.File.Save(sdb_str))

    if not p_sdb.exists() or p_sdb.stat().st_size == 0:
        raise RuntimeError(f"El archivo .sdb no existe o está vacío tras File.Save: {p_sdb}")
    sdb_size_bytes = p_sdb.stat().st_size

    if hasattr(sap_model, "Analyze"):
        if hasattr(sap_model.Analyze, "SetRunCaseFlag"):
            _check_ret("Analyze.SetRunCaseFlag", sap_model.Analyze.SetRunCaseFlag("", True, True))
        run_ret = sap_model.Analyze.RunAnalysis()
        _check_ret("Analyze.RunAnalysis", run_ret)
        run_rc = run_ret[0] if isinstance(run_ret, (tuple, list)) and run_ret else int(run_ret)
    else:
        raise RuntimeError("SapModel no expone Analyze.RunAnalysis")

    load_cases = ["DEAD", "DW", "LIVE_LANE", "LIVE_VEHICLE_M", "LIVE_VEHICLE_V"]
    combo_names = [c["name"] for c in meta["loads_summary"]["combinations"]]

    if hasattr(sap_model, "Results") and hasattr(sap_model.Results, "Setup"):
        setup = sap_model.Results.Setup
        _check_ret("DeselectAllCasesAndCombosForOutput", setup.DeselectAllCasesAndCombosForOutput())
        for lc in load_cases:
            _check_ret(f"SetCaseSelectedForOutput({lc})", setup.SetCaseSelectedForOutput(lc))
        for cb in combo_names:
            _check_ret(f"SetComboSelectedForOutput({cb})", setup.SetComboSelectedForOutput(cb))

    reactions_rows: list[dict[str, Any]] = []
    for jid in support_joints:
        for r in get_joint_reactions(sap_model, jid):
            reactions_rows.append({
                "joint": str(r["joint"]),
                "case": str(r["case"]),
                "Fx_kN": float(r["F1"]),
                "Fy_kN": float(r["F2"]),
                "Fz_kN": float(r["F3"]),
                "Mx_kNm": float(r["M1"]),
                "My_kNm": float(r["M2"]),
                "Mz_kNm": float(r["M3"]),
            })

    displacements_rows: list[dict[str, Any]] = []
    for j in joints_spec:
        for d in get_joint_displacements(sap_model, j["id"]):
            displacements_rows.append({
                "joint": str(d["joint"]),
                "case": str(d["case"]),
                "Ux_m": float(d["Ux"]),
                "Uy_m": float(d["Uy"]),
                "Uz_m": float(d["Uz"]),
                "Rx_rad": float(d["Rx"]),
                "Ry_rad": float(d["Ry"]),
                "Rz_rad": float(d["Rz"]),
            })

    frame_forces_rows: list[dict[str, Any]] = []
    for f in frames_spec:
        for fr in get_frame_forces(sap_model, f["id"]):
            frame_forces_rows.append({
                "frame": str(fr["obj"]),
                "role": f["role"],
                "station_m": float(fr["station"]),
                "case": str(fr["case"]),
                "P_kN": float(fr["P"]),
                "V2_kN": float(fr["V2"]),
                "V3_kN": float(fr["V3"]),
                "T_kNm": float(fr["T"]),
                "M2_kNm": float(fr["M2"]),
                "M3_kNm": float(fr["M3"]),
            })

    expected_fz = compute_expected_vertical_loads_kN(meta)
    equilibrium_by_case: dict[str, dict[str, Any]] = {}
    movable_joints = {
        j["id"] for j in joints_spec if j["restraint"] is not None and float(j["x"]) > 1e-4
    }
    for case_name in load_cases + combo_names:
        case_reac = [r for r in reactions_rows if r["case"] == case_name]
        sum_fx = sum(r["Fx_kN"] for r in case_reac)
        sum_fy = sum(r["Fy_kN"] for r in case_reac)
        sum_fz = sum(r["Fz_kN"] for r in case_reac)
        sum_fx_movable = sum(r["Fx_kN"] for r in case_reac if r["joint"] in movable_joints)
        applied_fz = float(expected_fz.get(case_name, 0.0))
        diff_fz = abs(sum_fz - applied_fz)
        rel_err = diff_fz / max(1.0, abs(applied_fz))
        ok_case = (rel_err <= equilibrium_tol_rel) and (abs(sum_fx_movable) <= 1e-3)
        equilibrium_by_case[case_name] = {
            "applied_vertical_load_kN": round(applied_fz, 4),
            "sum_Rz_reactions_kN": round(sum_fz, 4),
            "abs_diff_kN": round(diff_fz, 4),
            "rel_error": round(rel_err, 6),
            "sum_Rx_kN": round(sum_fx, 6),
            "sum_Ry_kN": round(sum_fy, 6),
            "sum_Rx_movable_abutment_kN": round(sum_fx_movable, 6),
            "equilibrium_ok": bool(ok_case),
        }
        if not ok_case:
            raise RuntimeError(
                f"Fallo de equilibrio global en caso {case_name!r}: "
                f"aplicada={applied_fz:.3f} kN, sum_Rz={sum_fz:.3f} kN (err={rel_err:.4%}), "
                f"sum_Rx_movil={sum_fx_movable:.6f} kN"
            )

    summary_by_case: dict[str, dict[str, Any]] = {}
    for case_name in load_cases + combo_names:
        f_long = [r for r in frame_forces_rows if r["case"] == case_name and r["role"] == "girder"]
        f_trans = [r for r in frame_forces_rows if r["case"] == case_name and r["role"] == "diaphragm"]
        d_case = [d for d in displacements_rows if d["case"] == case_name]
        girder_peaks: dict[int, dict[str, float]] = {}
        for ig in range(int(meta["n_girders"])):
            f_ig = [r for r in f_long if r["frame"].endswith(f"_{ig}")]
            girder_peaks[ig] = {
                "M3_max_kNm": round(max((abs(r["M3_kNm"]) for r in f_ig), default=0.0), 3),
                "V2_max_kN": round(max((abs(r["V2_kN"]) for r in f_ig), default=0.0), 3),
                "T_max_kNm": round(max((abs(r["T_kNm"]) for r in f_ig), default=0.0), 3),
            }
        best_m3_row = max(f_long, key=lambda r: abs(r["M3_kNm"]), default=None)
        best_v2_row = max(f_long, key=lambda r: abs(r["V2_kN"]), default=None)
        best_diaph_m3 = max(f_trans, key=lambda r: abs(r["M3_kNm"]), default=None)
        best_diaph_v2 = max(f_trans, key=lambda r: abs(r["V2_kN"]), default=None)
        min_uz_row = min(d_case, key=lambda d: d["Uz_m"], default=None)
        summary_by_case[case_name] = {
            "girder_M3_max_kNm": round(abs(best_m3_row["M3_kNm"]), 3) if best_m3_row else 0.0,
            "girder_M3_governing": best_m3_row,
            "girder_V2_max_kN": round(abs(best_v2_row["V2_kN"]), 3) if best_v2_row else 0.0,
            "girder_V2_governing": best_v2_row,
            "girder_peaks_by_index": girder_peaks,
            "diaphragm_M3_max_kNm": round(abs(best_diaph_m3["M3_kNm"]), 3) if best_diaph_m3 else 0.0,
            "diaphragm_V2_max_kN": round(abs(best_diaph_v2["V2_kN"]), 3) if best_diaph_v2 else 0.0,
            "min_Uz_m": round(float(min_uz_row["Uz_m"]), 6) if min_uz_row else 0.0,
            "min_Uz_mm": round(float(min_uz_row["Uz_m"]) * 1000.0, 3) if min_uz_row else 0.0,
            "min_Uz_joint": min_uz_row["joint"] if min_uz_row else "",
        }

    return {
        "sdb_path": sdb_str,
        "sdb_size_bytes": sdb_size_bytes,
        "units": "kN_m_C",
        "RunAnalysis_ret": run_rc,
        "frames": [dict(f) for f in frames_spec],
        "meta": meta,
        "expected_fz_kN": expected_fz,
        "equilibrium_by_case": equilibrium_by_case,
        "summary_by_case": summary_by_case,
        "reactions": reactions_rows,
        "displacements": displacements_rows,
        "frame_forces": frame_forces_rows,
    }


def execute_bridge_grillage_design_loop(
    client: Any,
    sdb_path: str,
    *,
    spec: BridgeDesignSpec | None = None,
    L: float = 30.0,
    W: float = 10.0,
    n_girders: int = 4,
    n_diaphragms: int = 3,
    n_spans: int = 1,
    long_section: str = "HEM 1000",
    trans_section: str = "HEB 400",
    candidate_girder_ladder: tuple[str, ...] | list[str] = BRIDGE_FULL_GIRDER_LADDER,
    candidate_diaphragm_ladder: tuple[str, ...] | list[str] = BRIDGE_DIAPHRAGM_LADDER,
    max_iterations: int = 15,
    live_deflection_ratio_limit: float = 800.0,
    total_deflection_ratio_limit: float = 500.0,
    equilibrium_tol_rel: float = 0.005,
) -> dict[str, Any]:
    """Ejecuta el bucle cerrado de verificación ULS/SLS y redimensionamiento iterativo
    contra SAP2000 (o un mock de contrato con estado):

    1. Construye el modelo inicial (p. ej. con ``HEM 1000`` / ``HEB 400``).
    2. Verifica en SAP2000 las propiedades reales de las secciones creadas (``PropFrame.GetSectProps``).
    3. Ejecuta ``Analyze.RunAnalysis()``, extrae esfuerzos concurrentes y desplazamientos,
       comprueba equilibrio global y ejecuta ``verify_bridge_grillage_results``.
    4. Mientras algún estado límite implementado falle (``DCR > 1.0``):
       - Selecciona el siguiente perfil de la escalera determinista (``candidate_girder_ladder`` o
         ``candidate_diaphragm_ladder``).
       - Si se agota el catálogo sin cumplir, termina limpiamente con
         ``CalculationStatus.CALCULADO_FALLA`` y ``termination_reason = "CATALOG_EXHAUSTED"``.
       - Desbloquea el modelo en SAP2000 (``SetModelIsLocked(False)``), registra la nueva sección
         (``PropFrame.SetISection``), verifica sus propiedades en SAP2000 (``GetSectProps``),
         asigna la nueva sección a todas las barras correspondientes (``FrameObj.SetSection``),
         guarda ``.sdb``, re-analiza y vuelve a verificar con el nuevo peso propio y rigidez.
    5. Al terminar el bucle, guarda el ``.sdb`` final, reinicializa en blanco y **reabre** el
       archivo ``.sdb`` verificando que todas las barras y secciones finales persisten con
       ``veredicto == "OK"``.
    """
    from pathlib import Path
    from fastsap.oapi import get_coord_cartesian, get_points, get_section as oapi_get_section
    from fastsap.s2k_build.verdict import veredicto

    sap_model = getattr(client, "SapModel", client)
    if sap_model is None:
        raise RuntimeError("client no expone SapModel")

    build_summary = build_bridge_grillage(
        client,
        L=L,
        W=W,
        n_girders=n_girders,
        n_diaphragms=n_diaphragms,
        n_spans=n_spans,
        long_section=long_section,
        trans_section=trans_section,
        spec=spec,
    )
    meta = build_summary["meta"]
    expected_counts = meta["derived_counts"]
    joints_spec = build_summary["joints"]
    frames_spec = [dict(f) for f in build_summary["frames"]]
    support_joints = [j["id"] for j in joints_spec if j["restraint"] is not None]
    long_frames = [f["id"] for f in frames_spec if f["role"] == "girder"]
    trans_frames = [f["id"] for f in frames_spec if f["role"] == "diaphragm"]

    if hasattr(sap_model, "FrameObj") and hasattr(sap_model.FrameObj, "SetOutputStations"):
        for f in frames_spec:
            _check_ret(
                f"FrameObj.SetOutputStations({f['id']})",
                sap_model.FrameObj.SetOutputStations(f["id"], 2, 0.0, 9, True, True),
            )

    p_sdb = Path(sdb_path).expanduser().resolve()
    p_sdb.parent.mkdir(parents=True, exist_ok=True)
    sdb_str = str(p_sdb).replace("/", "\\") if os.name == "nt" else str(p_sdb)

    mat_name = str(meta["material"]["name"])
    girder_ladder = list(candidate_girder_ladder)
    diaph_ladder = list(candidate_diaphragm_ladder)

    curr_girder_name = next(f["section"] for f in frames_spec if f["role"] == "girder")
    curr_diaph_name = next(f["section"] for f in frames_spec if f["role"] == "diaphragm")

    if curr_girder_name not in girder_ladder:
        girder_ladder.insert(0, curr_girder_name)
    if curr_diaph_name not in diaph_ladder:
        diaph_ladder.insert(0, curr_diaph_name)

    iterations_history: list[dict[str, Any]] = []
    termination_reason = "MAX_ITERATIONS_REACHED"
    last_iter_analysis: dict[str, Any] = {}
    last_verification: dict[str, Any] = {}

    for it_idx in range(max_iterations):
        # 1) Verificar en SAP2000 las propiedades de las secciones activas
        girder_sec_props = meta["sections"][curr_girder_name]
        diaph_sec_props = meta["sections"][curr_diaph_name]
        sap_girder_check = verify_sap_section_properties(sap_model, girder_sec_props)
        sap_diaph_check = verify_sap_section_properties(sap_model, diaph_sec_props)

        # 2) Guardar, ejecutar RunAnalysis(), extraer resultados y verificar equilibrio
        iter_analysis = _run_single_sap_analysis_and_extract(
            client,
            sap_model,
            sdb_str,
            meta=meta,
            joints_spec=joints_spec,
            frames_spec=frames_spec,
            equilibrium_tol_rel=equilibrium_tol_rel,
        )
        last_iter_analysis = iter_analysis

        # 3) Ejecutar verificacion normativa concurrente ULS + SLS
        verif = verify_bridge_grillage_results(
            iter_analysis,
            spec=spec,
            live_deflection_ratio_limit=live_deflection_ratio_limit,
            total_deflection_ratio_limit=total_deflection_ratio_limit,
        )
        last_verification = verif

        # NO_CALCULADO (analisis invalido, tablas vacias, equilibrio, material no soportado): la
        # respuesta no trae governing_check/girder_capacities/sls_deflections. Se mira ANTES de
        # leerlos; antes esta rama era inalcanzable y el bucle moria con KeyError (2026-10-25).
        if verif["implemented_checks_status"] == CalculationStatus.NO_CALCULADO.value:
            iterations_history.append({
                "iteration": it_idx,
                "girder_section": curr_girder_name,
                "diaphragm_section": curr_diaph_name,
                "sap_section_verification": {"girder": sap_girder_check, "diaphragm": sap_diaph_check},
                "missing_inputs": list(verif.get("missing_inputs", [])),
                "checks": [],
                "implemented_checks_status": verif["implemented_checks_status"],
                "calculation_status": verif["calculation_status"].value,
            })
            termination_reason = "INVALID_ANALYSIS_OR_MISSING_RESULTS"
            break

        gov_chk = verif["governing_check"]
        gov_uls_st = verif["governing_girder_uls_station"]
        sls_info = verif["sls_deflections"]
        g_cap = verif["girder_capacities"]

        iterations_history.append({
            "iteration": it_idx,
            "girder_section": curr_girder_name,
            "diaphragm_section": curr_diaph_name,
            "girder_h_m": girder_sec_props["h_m"],
            "girder_b_m": girder_sec_props["b_m"],
            "girder_tf_m": girder_sec_props["tf_m"],
            "girder_tw_m": girder_sec_props["tw_m"],
            "girder_A_m2": girder_sec_props["A_m2"],
            "girder_I33_m4": girder_sec_props["I33_m4"],
            "girder_Wpl33_m3": girder_sec_props["Wpl33_m3"],
            "sap_section_verification": {
                "girder": sap_girder_check,
                "diaphragm": sap_diaph_check,
            },
            "DEAD_total_kN": iter_analysis["expected_fz_kN"]["DEAD"],
            "DEAD_sum_Rz_kN": iter_analysis["equilibrium_by_case"]["DEAD"]["sum_Rz_reactions_kN"],
            "ULS_STR_sum_Rz_kN": iter_analysis["equilibrium_by_case"].get(
                "ULS_STR", iter_analysis["equilibrium_by_case"].get("ULS_STRENGTH_I", {})
            ).get("sum_Rz_reactions_kN", 0.0),
            "section_class": g_cap["classification"]["section_class"],
            "Mc_Rd_kNm": g_cap["Mc_Rd_kNm"],
            "Mb_Rd_kNm": g_cap["Mb_Rd_kNm"],
            "Vc_Rd_kN": g_cap["Vc_Rd_kN"],
            "governing_girder_M3_kNm": gov_uls_st["M3_kNm"],
            "concurrent_girder_V2_kN": gov_uls_st["V2_kN"],
            "concurrent_girder_P_kN": gov_uls_st["P_kN"],
            "max_girder_V2_kN": iter_analysis["summary_by_case"].get(
                "ULS_STR_SHEAR", iter_analysis["summary_by_case"].get("ULS_STRENGTH_I_SHEAR", {})
            ).get("girder_V2_max_kN", 0.0),
            "active_traffic_deflection_mm": sls_info["active_traffic_deflection_mm"],
            "active_traffic_limit_mm": sls_info["active_traffic_limit_mm"],
            "total_characteristic_deflection_mm": sls_info["total_characteristic_deflection_mm"],
            "total_characteristic_limit_mm": sls_info["total_characteristic_limit_mm"],
            "max_dcr_uls": verif["max_dcr_uls"],
            "max_dcr_sls": verif["max_dcr_sls"],
            "max_dcr_overall": verif["max_dcr_overall"],
            "governing_check_id": gov_chk["check_id"],
            "governing_member": gov_chk["governing_member"],
            "governing_combo": gov_chk["governing_combo"],
            "governing_station_m": gov_chk["governing_station_m"],
            "checks": verif["checks"],
            "implemented_checks_status": verif["implemented_checks_status"],
            "calculation_status": verif["calculation_status"].value,
        })

        # Si todos los estados limite implementados cumplen (DCR <= 1.0), hemos convergido
        if verif["implemented_checks_status"] in ("CUMPLE", CalculationStatus.CALCULADO_CUMPLE.value):
            termination_reason = "CONVERGED_ALL_IMPLEMENTED_CHECKS_PASS"
            break

        # Determinar si es necesario subir viga principal L* y/o diafragma T*
        girder_failed = any(
            c["role"] == "girder" and c["status"] == CalculationStatus.CALCULADO_FALLA.value
            for c in verif["checks"]
        )
        diaph_failed = any(
            c["role"] == "diaphragm" and c["status"] == CalculationStatus.CALCULADO_FALLA.value
            for c in verif["checks"]
        )

        next_girder_name = curr_girder_name
        next_diaph_name = curr_diaph_name

        if girder_failed:
            g_idx = girder_ladder.index(curr_girder_name)
            if g_idx + 1 >= len(girder_ladder):
                termination_reason = "CATALOG_EXHAUSTED"
                break
            next_girder_name = girder_ladder[g_idx + 1]

        if diaph_failed:
            d_idx = diaph_ladder.index(curr_diaph_name)
            if d_idx + 1 >= len(diaph_ladder):
                termination_reason = "CATALOG_EXHAUSTED"
                break
            next_diaph_name = diaph_ladder[d_idx + 1]

        if next_girder_name == curr_girder_name and next_diaph_name == curr_diaph_name:
            termination_reason = "NO_CANDIDATE_CHANGE"
            break

        # 4) Desbloquear el modelo en SAP2000, registrar nuevas secciones y asignarlas a las barras
        if hasattr(sap_model, "SetModelIsLocked"):
            _check_ret("SetModelIsLocked(False)", sap_model.SetModelIsLocked(False))

        new_girder_props = section_props_from_catalog(next_girder_name, material_name=mat_name)
        new_diaph_props = section_props_from_catalog(next_diaph_name, material_name=mat_name)
        meta["sections"] = {
            new_girder_props.name: new_girder_props.to_dict(),
            new_diaph_props.name: new_diaph_props.to_dict(),
        }
        _register_material_and_sections_oapi(sap_model, meta)

        for f in frames_spec:
            if f["role"] == "girder" and f["section"] != next_girder_name:
                f["section"] = next_girder_name
                if hasattr(sap_model.FrameObj, "SetSection"):
                    _check_ret(
                        f"FrameObj.SetSection({f['id']})",
                        sap_model.FrameObj.SetSection(f["id"], next_girder_name),
                    )
            elif f["role"] == "diaphragm" and f["section"] != next_diaph_name:
                f["section"] = next_diaph_name
                if hasattr(sap_model.FrameObj, "SetSection"):
                    _check_ret(
                        f"FrameObj.SetSection({f['id']})",
                        sap_model.FrameObj.SetSection(f["id"], next_diaph_name),
                    )

        curr_girder_name = next_girder_name
        curr_diaph_name = next_diaph_name

    # 5) Guardar el archivo .sdb final y ejecutar el protocolo de cierre + reapertura verificada
    created_points = int(sap_model.PointObj.Count()) if hasattr(sap_model.PointObj, "Count") else len(joints_spec)
    created_frames = int(sap_model.FrameObj.Count()) if hasattr(sap_model.FrameObj, "Count") else len(frames_spec)
    created_materials = _safe_name_list(getattr(sap_model, "PropMaterial", None))
    created_sections = _safe_name_list(getattr(sap_model, "PropFrame", None))
    created_patterns = _safe_name_list(getattr(sap_model, "LoadPatterns", None))
    created_combos = _safe_name_list(getattr(sap_model, "RespCombo", None))

    if hasattr(client, "save"):
        client.save(sdb_str)
    else:
        _check_ret("File.Save", sap_model.File.Save(sdb_str))

    sdb_size_bytes = p_sdb.stat().st_size

    if hasattr(client, "new_blank_model"):
        client.new_blank_model()
    elif hasattr(sap_model, "File") and hasattr(sap_model.File, "NewBlank"):
        _check_ret("File.NewBlank", sap_model.File.NewBlank())

    if hasattr(client, "open_file"):
        client.open_file(sdb_str)
    else:
        _check_ret("File.OpenFile", sap_model.File.OpenFile(sdb_str))

    reopened_points = int(sap_model.PointObj.Count()) if hasattr(sap_model.PointObj, "Count") else 0
    reopened_frames = int(sap_model.FrameObj.Count()) if hasattr(sap_model.FrameObj, "Count") else 0
    reopened_materials = _safe_name_list(getattr(sap_model, "PropMaterial", None))
    reopened_sections = _safe_name_list(getattr(sap_model, "PropFrame", None))
    reopened_patterns = _safe_name_list(getattr(sap_model, "LoadPatterns", None))
    reopened_combos = _safe_name_list(getattr(sap_model, "RespCombo", None))

    reopened_supports_count = 0
    if hasattr(sap_model.PointObj, "GetRestraint"):
        for j in joints_spec:
            res_r = sap_model.PointObj.GetRestraint(j["id"], [False] * 6)
            _check_ret(f"PointObj.GetRestraint({j['id']})", res_r)
            r_vals = list(res_r[1]) if isinstance(res_r, (tuple, list)) and len(res_r) >= 2 else []
            if any(r_vals):
                reopened_supports_count += 1
            coords = get_coord_cartesian(sap_model.PointObj, j["id"])
            if (
                abs(coords[0] - float(j["x"])) > 1e-3
                or abs(coords[1] - float(j["y"])) > 1e-3
                or abs(coords[2] - float(j["z"])) > 1e-3
            ):
                raise RuntimeError(f"Coordenadas reabiertas de {j['id']} difieren: {coords} vs {j}")
    else:
        reopened_supports_count = expected_counts["n_supports"]

    undefined_sections: list[str] = []
    reopened_frame_sections: dict[str, str] = {}
    for f in frames_spec:
        sec_assigned = oapi_get_section(sap_model.FrameObj, f["id"])
        reopened_frame_sections[f["id"]] = sec_assigned
        if sec_assigned != f["section"] or sec_assigned not in reopened_sections:
            undefined_sections.append(f"{f['id']}:{sec_assigned}")
        pts = get_points(sap_model.FrameObj, f["id"])
        if pts != (f["joint_i"], f["joint_j"]):
            raise RuntimeError(f"Conectividad reabierta de {f['id']} difiere: {pts}")

    run_rc = int(last_iter_analysis.get("RunAnalysis_ret", 1))
    verdict_input = {
        "barras_unicas_s2k": expected_counts["n_frames"],
        "n_barras": created_frames,
        "reabierto_barras": reopened_frames,
        "n_puntos_s2k": expected_counts["n_joints"],
        "n_puntos": created_points,
        "reabierto_puntos": reopened_points,
        "secciones_sin_definir": undefined_sections,
        "RunAnalysis_ret": run_rc,
        "predimensionado": False,
    }
    verdict_persistence = veredicto(verdict_input)

    return {
        "sdb_path": sdb_str,
        "sdb_size_bytes": sdb_size_bytes,
        "units": "kN_m_C",
        "RunAnalysis_ret": run_rc,
        "n_iterations": len(iterations_history),
        "initial_girder_section": iterations_history[0]["girder_section"] if iterations_history else curr_girder_name,
        "final_girder_section": curr_girder_name,
        "initial_diaphragm_section": iterations_history[0]["diaphragm_section"] if iterations_history else curr_diaph_name,
        "final_diaphragm_section": curr_diaph_name,
        "termination_reason": termination_reason,
        "implemented_checks_status": last_verification.get("implemented_checks_status", "NO_CALCULADO"),
        "calculation_status": last_verification["calculation_status"].value
        if isinstance(last_verification.get("calculation_status"), CalculationStatus)
        else str(last_verification.get("calculation_status", "NO_CALCULADO")),
        "unimplemented_checks": last_verification.get("unimplemented_checks", list(UNIMPLEMENTED_CHECKS)),
        "final_verification": {
            **last_verification,
            "calculation_status": last_verification["calculation_status"].value
            if isinstance(last_verification.get("calculation_status"), CalculationStatus)
            else str(last_verification.get("calculation_status", "NO_CALCULADO")),
        },
        "iterations_history": iterations_history,
        "counts": {
            "expected": expected_counts,
            "created": {
                "n_joints": created_points,
                "n_frames": created_frames,
                "n_frames_long": len(long_frames),
                "n_frames_trans": len(trans_frames),
                "n_supports": len(support_joints),
                "materials": created_materials,
                "sections": created_sections,
                "load_patterns": created_patterns,
                "combinations": created_combos,
            },
            "reopened": {
                "n_joints": reopened_points,
                "n_frames": reopened_frames,
                "n_supports": reopened_supports_count,
                "materials": reopened_materials,
                "sections": reopened_sections,
                "frame_sections": reopened_frame_sections,
                "load_patterns": reopened_patterns,
                "combinations": reopened_combos,
            },
        },
        "persistence_verdict": verdict_persistence,
        "equilibrium_by_case": last_iter_analysis.get("equilibrium_by_case", {}),
        "summary_by_case": last_iter_analysis.get("summary_by_case", {}),
        "reactions": last_iter_analysis.get("reactions", []),
        "displacements": last_iter_analysis.get("displacements", []),
        "frame_forces": last_iter_analysis.get("frame_forces", []),
        "meta": meta,
    }


def run_bridge_grillage_design_loop_sap2000(
    sdb_path: str,
    *,
    spec: BridgeDesignSpec | None = None,
    L: float = 30.0,
    W: float = 10.0,
    n_girders: int = 4,
    n_diaphragms: int = 3,
    n_spans: int = 1,
    candidate_girder_ladder: tuple[str, ...] | list[str] = BRIDGE_FULL_GIRDER_LADDER,
    candidate_diaphragm_ladder: tuple[str, ...] | list[str] = BRIDGE_DIAPHRAGM_LADDER,
    max_iterations: int = 15,
    live_deflection_ratio_limit: float = 800.0,
    total_deflection_ratio_limit: float = 500.0,
    visible: bool = False,
    keep_open: bool = False,
    sap_install_dir: str | None = None,
) -> dict[str, Any]:
    """Arranca una sesion real de SAP2000 v26 en unidades ``kN_m_C``, ejecuta el bucle cerrado
    de verificacion ULS/SLS y redimensionamiento iterativo, reabre el archivo ``.sdb`` final y
    cierra limpiamente la instancia creada.
    """
    from fastsap.client import SapClient

    with SapClient(
        sap_install_dir=sap_install_dir,
        visible=visible,
        units="kN_m_C",
        keep_open=keep_open,
        run_probe=False,
    ) as client:
        return execute_bridge_grillage_design_loop(
            client,
            sdb_path,
            spec=spec,
            L=L,
            W=W,
            n_girders=n_girders,
            n_diaphragms=n_diaphragms,
            n_spans=n_spans,
            candidate_girder_ladder=candidate_girder_ladder,
            candidate_diaphragm_ladder=candidate_diaphragm_ladder,
            max_iterations=max_iterations,
            live_deflection_ratio_limit=live_deflection_ratio_limit,
            total_deflection_ratio_limit=total_deflection_ratio_limit,
        )


def compute_bridge_sustainability_and_cost(
    *,
    L: float,
    W: float,
    n_spans: int = 1,
    n_girders: int = 4,
    n_diaphragms: int = 3,
    girder_section: str,
    diaphragm_section: str,
    material_name: str = "S355",
    slab_thickness_m: float = 0.25,
    country_iso: str = "ES",
    max_dcr_uls: float | None = None,
    max_dcr_sls: float | None = None,
    feasible: bool = True,
) -> dict[str, Any]:
    """Calcula masa total de acero, presupuesto internacional (SteelOptimizerJm.cost_by_country)
    y huella de carbono embebido + calificación SCORS (CarbonFootprintJm.lca) para una configuración
    de emparrillado de puente.
    """
    from steeloptimizerjm.cost_by_country import estimate_cost, get_cost
    from carbonfootprintjm.lca import (
        StructuralElementInput,
        StructuralLcaInput,
        calculate_structural_lca,
    )

    g_props = section_props_from_catalog(girder_section, material_name=material_name)
    d_props = section_props_from_catalog(diaphragm_section, material_name=material_name)

    total_len_m = float(n_spans) * float(L)
    girder_total_len_m = float(n_girders) * total_len_m
    n_trans_lines = int(n_spans) * (int(n_diaphragms) + 1) + 1
    diaph_total_len_m = float(n_trans_lines) * float(W)

    girder_mass_kg = girder_total_len_m * float(g_props.mass_kg_m)
    diaph_mass_kg = diaph_total_len_m * float(d_props.mass_kg_m)
    total_steel_mass_kg = girder_mass_kg + diaph_mass_kg
    total_steel_tons = total_steel_mass_kg / 1000.0
    deck_area_m2 = max(1e-6, total_len_m * float(W))
    steel_mass_per_m2_kg = total_steel_mass_kg / deck_area_m2

    c_info = get_cost(country_iso)
    # Vigas armadas soldadas PG_* tienen sobrecoste de fabricación por soldadura de alma-ala (~12%)
    welded_factor = 1.12 if girder_section.upper().startswith("PG_") else 1.00
    girder_cost_usd = estimate_cost(country_iso, girder_mass_kg / 1000.0, stage="erected") * welded_factor
    diaph_cost_usd = estimate_cost(country_iso, diaph_mass_kg / 1000.0, stage="erected")
    total_cost_usd = girder_cost_usd + diaph_cost_usd
    total_cost_eur = total_cost_usd * 0.92  # Tipo de referencia USD -> EUR

    slab_vol_m3 = deck_area_m2 * float(slab_thickness_m)
    lca_inp = StructuralLcaInput(
        project_name=f"Puente {total_len_m:.0f}x{W:.0f}m ({n_girders}x {girder_section} + {diaphragm_section})",
        floor_area_m2=deck_area_m2,
        elements=[
            StructuralElementInput(
                name=f"Vigas principales ({n_girders}x {girder_section})",
                material_key="steel_sections",
                quantity=max(1e-3, girder_mass_kg),
                unit="kg",
            ),
            StructuralElementInput(
                name=f"Diafragmas transversales ({n_trans_lines}x {diaphragm_section})",
                material_key="steel_sections",
                quantity=max(1e-3, diaph_mass_kg),
                unit="kg",
            ),
            StructuralElementInput(
                name=f"Losa superior hormigón e={slab_thickness_m:.2f}m",
                material_key="concrete_c35",
                quantity=max(1e-3, slab_vol_m3),
                unit="m3",
            ),
        ],
    )
    lca_out = calculate_structural_lca(lca_inp)

    # Indice de complejidad constructiva: penaliza mayor numero de vigas principales y soldadura armada
    constructability_index = round(
        float(n_girders) * (1.15 if girder_section.upper().startswith("PG_") else 1.0)
        + 0.15 * float(n_trans_lines),
        4,
    )
    slenderness_L_over_h = round(float(L) / max(1e-6, float(g_props.h_m)), 3)
    dcr_uls_val = round(float(max_dcr_uls), 6) if max_dcr_uls is not None else None
    dcr_sls_val = round(float(max_dcr_sls), 6) if max_dcr_sls is not None else None
    dcr_gov = (
        round(max(dcr_uls_val or 0.0, dcr_sls_val or 0.0), 6)
        if (dcr_uls_val is not None or dcr_sls_val is not None)
        else None
    )

    return {
        "n_girders": int(n_girders),
        "n_diaphragms": int(n_diaphragms),
        "girder_section": girder_section,
        "diaphragm_section": diaphragm_section,
        "girder_family": "viga_armada_soldada_PG" if girder_section.upper().startswith("PG_") else "perfil_laminado_EN10365",
        "girder_h_m": round(float(g_props.h_m), 4),
        "slenderness_L_over_h": slenderness_L_over_h,
        "girder_total_length_m": round(girder_total_len_m, 3),
        "diaphragm_total_length_m": round(diaph_total_len_m, 3),
        "girder_mass_kg": round(girder_mass_kg, 2),
        "diaphragm_mass_kg": round(diaph_mass_kg, 2),
        "total_steel_mass_kg": round(total_steel_mass_kg, 2),
        "total_steel_tons": round(total_steel_tons, 4),
        "steel_mass_per_m2_kg": round(steel_mass_per_m2_kg, 2),
        "country_iso": country_iso,
        "rate_USD_per_ton_erected": c_info.USD_per_ton_erected,
        "welded_fabrication_factor": welded_factor,
        "estimated_cost_USD": round(total_cost_usd, 2),
        "estimated_cost_EUR": round(total_cost_eur, 2),
        "embodied_carbon_steel_kgCO2e": round((girder_mass_kg + diaph_mass_kg) * 2.4, 2),
        "embodied_carbon_total_kgCO2e": round(float(lca_out.net_gwp_kgCO2eq), 2),
        "embodied_carbon_per_m2_kgCO2e": round(float(lca_out.gwp_per_m2), 2),
        "scors_rating": lca_out.scors_rating,
        "constructability_index": constructability_index,
        "max_dcr_uls": dcr_uls_val,
        "max_dcr_sls": dcr_sls_val,
        "max_dcr_overall": dcr_gov,
        "structural_reserve_margin": round(1.0 - dcr_gov, 6) if dcr_gov is not None else None,
        "feasible": bool(feasible),
    }


def evaluate_bridge_design_alternatives(
    spec: BridgeDesignSpec,
    *,
    final_design_result: dict[str, Any] | None = None,
    candidate_girder_counts: tuple[int, ...] = (3, 4, 5),
    candidate_sections: tuple[str, ...] = BRIDGE_FULL_GIRDER_LADDER,
    country_iso: str = "ES",
    live_deflection_ratio_limit: float = 800.0,
    total_deflection_ratio_limit: float = 500.0,
) -> dict[str, Any]:
    """Evalúa explícitamente múltiples alternativas de tipología/configuración de emparrillado
    (variando número de vigas principales ``n_girders`` y secciones de catálogo laminadas/armadas)
    bajo funciones objetivo de masa, coste, carbono embebido, constructibilidad y holgura estructural
    (DCR ULS y SLS), determina la frontera de Pareto no dominada y clasifica la solución seleccionada
    como ``MEJOR_SOLUCION_ENCONTRADA`` o ``SOLUCION_FACTIBLE``.
    """
    L = float(spec.span_m)
    W = float(spec.width_m)
    n_spans = int(spec.n_spans)
    n_diaph = int(spec.n_diaphragms)
    mat_name = spec.material.name
    diaph_sec = spec.diaphragm_section.name
    E_Pa = float(spec.material.E_kPa) * 1000.0

    # Si tenemos el resultado FEM 3D real para la configuracion base (n_girders=spec.n_girders),
    # registramos sus esfuerzos y flechas exactas por iteracion y calibramos el factor de emparrillado.
    fem_iter_lookup: dict[tuple[int, str], dict[str, Any]] = {}
    if final_design_result is not None:
        base_ng = int(final_design_result.get("meta", {}).get("n_girders", spec.n_girders))
        for it in final_design_result.get("iterations_history", []):
            fem_iter_lookup[(base_ng, str(it["girder_section"]))] = it

    alternatives: list[dict[str, Any]] = []
    for ng in candidate_girder_counts:
        # Generar el modelo de cargas con reparto transversal excéntrico de Courbon para ng vigas
        gm = grillage_model(
            L,
            W,
            n_girders=ng,
            n_diaphragms=n_diaph,
            n_spans=n_spans,
            long_section=spec.girder_section.name,
            trans_section=diaph_sec,
            spec=spec,
        )
        meta_ng = gm["meta"]
        ls_ng = meta_ng["loads_summary"]
        q_slab = float(ls_ng["q_slab_per_girder_kN_m"])
        q_dw = float(ls_ng["q_dw_per_girder_kN_m"])
        q_lane_map = ls_ng["q_lane_by_girder_kN_m"]
        q_lane_g0 = float(q_lane_map.get(0, q_lane_map.get("0", 0.0)))
        share_map = ls_ng["transverse_distribution"]["vehicle_axle_share_by_girder"]
        share_g0 = float(share_map.get(0, share_map.get("0", 0.0)))
        axles_M = [float(p) * share_g0 for p in ls_ng["vehicle_axles_M_kN"]]
        pos_M = [float(x) for x in ls_ng["vehicle_positions_M_m"]]
        axles_V = [float(p) * share_g0 for p in ls_ng["vehicle_axles_V_kN"]]
        pos_V = [float(x) for x in ls_ng["vehicle_positions_V_m"]]

        # Momento y cortante isostáticos exactos en viga exterior g=0 antes del alivio por diafragmas
        M_veh_g0 = 0.0
        x_mid = L / 2.0
        for p_kN, x_p in zip(axles_M, pos_M):
            # Reaccion en x=0 por carga en x_p: P*(L - x_p)/L
            r_a = p_kN * (L - x_p) / L
            m_at_mid = r_a * x_mid - (p_kN * (x_mid - x_p) if x_p < x_mid else 0.0)
            M_veh_g0 += m_at_mid
        V_veh_g0 = sum(p_kN * (L - x_p) / L for p_kN, x_p in zip(axles_V, pos_V))

        # SIN factor de alivio adicional (2026-10-25). Antes se multiplicaban demandas x0.72 y
        # flechas x0.565 "calibrados con el emparrillado 3D" para cualquier luz/vigas/seccion; las
        # cargas por viga ya llevan el reparto transversal (Courbon / share_g0), asi que aquello
        # contaba dos veces el mismo efecto, del lado inseguro. La estimacion es de viga aislada.

        for sec_name in candidate_sections:
            sec_p = section_props_from_catalog(sec_name, material_name=mat_name)
            l_ltb = L / float(n_diaph + 1)
            if spec.norma == "AASHTO_LRFD":
                cap = _compute_member_capacities_aashto(
                    sec_p.to_dict(),
                    spec.material.to_dict(),
                    L_b_m=l_ltb,
                )
            else:
                cap = _compute_member_capacities_ec3(
                    sec_p.to_dict(),
                    spec.material.to_dict(),
                    L_ltb_m=l_ltb,
                )
            m_ed_estimado = None
            if cap.get("class4_effective_section_not_implemented"):
                # sin seccion eficaz (EN 1993-1-5 §4) no hay resistencia: fuera de la optimizacion
                dcr_uls = dcr_sls = defl_ll_mm = defl_tot_mm = None
                verificada = False
                eval_source = "NO_CALCULADO: seccion clase 4 (seccion eficaz EN 1993-1-5 no implementada)"
            elif (ng, sec_name) in fem_iter_lookup and fem_iter_lookup[(ng, sec_name)].get("max_dcr_uls") is not None:
                it_fem = fem_iter_lookup[(ng, sec_name)]
                dcr_uls = float(it_fem["max_dcr_uls"])
                dcr_sls = float(it_fem["max_dcr_sls"])
                defl_ll_mm = float(it_fem["active_traffic_deflection_mm"])
                defl_tot_mm = float(it_fem["total_characteristic_deflection_mm"])
                verificada = True
                eval_source = "SAP2000_FEM_3D_EXACTO"
            else:
                q_sw = float(sec_p.A_m2) * float(spec.material.gamma_kN_m3)
                q_dead = q_sw + q_slab
                M_dead = q_dead * L**2 / 8.0
                M_dw = q_dw * L**2 / 8.0
                M_lane = q_lane_g0 * L**2 / 8.0
                gamma_G = 1.35 if spec.norma != "AASHTO_LRFD" else 1.25
                gamma_Q = 1.35 if spec.norma != "AASHTO_LRFD" else 1.75
                M_ed = gamma_G * (M_dead + M_dw) + gamma_Q * (M_lane + M_veh_g0)
                V_ed = (
                    gamma_G * (q_dead + q_dw) * L / 2.0
                    + gamma_Q * (q_lane_g0 * L / 2.0 + V_veh_g0)
                )
                m_ed_estimado = M_ed
                dcr_ltb = M_ed / max(1e-6, float(cap["Mb_Rd_kNm"]))
                dcr_v = V_ed / max(1e-6, float(cap["Vc_Rd_kN"]))
                dcr_uls = max(dcr_ltb, dcr_v)

                EI = E_Pa * float(sec_p.I33_m4)
                defl_lane_m = (5.0 * (q_lane_g0 * 1000.0) * L**4) / (384.0 * EI)
                P_tot_N = sum(axles_M) * 1000.0
                defl_veh_m = (P_tot_N * L**3) / (48.0 * EI)
                defl_ll_mm = (defl_lane_m + defl_veh_m) * 1000.0
                defl_dead_m = (5.0 * ((q_dead + q_dw) * 1000.0) * L**4) / (384.0 * EI)
                defl_tot_mm = (defl_dead_m * 1000.0) + defl_ll_mm
                lim_ll_mm = (L * 1000.0) / float(live_deflection_ratio_limit)
                lim_tot_mm = (L * 1000.0) / float(total_deflection_ratio_limit)
                dcr_sls = max(defl_ll_mm / lim_ll_mm, defl_tot_mm / lim_tot_mm)
                verificada = False
                eval_source = ("ESTIMACION_VIGA_AISLADA_COURBON (NO VERIFICADA en SAP2000; "
                               "isostatica, sin reparto adicional por diafragmas)")

            is_feas = dcr_uls is not None and dcr_sls is not None and dcr_uls <= 1.0 and dcr_sls <= 1.0
            metrics = compute_bridge_sustainability_and_cost(
                L=L,
                W=W,
                n_spans=n_spans,
                n_girders=ng,
                n_diaphragms=n_diaph,
                girder_section=sec_name,
                diaphragm_section=diaph_sec,
                material_name=mat_name,
                country_iso=country_iso,
                max_dcr_uls=dcr_uls,
                max_dcr_sls=dcr_sls,
                feasible=is_feas,
            )
            metrics["active_traffic_deflection_mm"] = round(defl_ll_mm, 3) if defl_ll_mm is not None else None
            metrics["total_characteristic_deflection_mm"] = round(defl_tot_mm, 3) if defl_tot_mm is not None else None
            metrics["M_Ed_estimado_kNm"] = m_ed_estimado
            metrics["verificada_sap2000"] = verificada
            metrics["evaluation_source"] = eval_source
            metrics["alternative_id"] = f"ALT_{ng}G_{sec_name.replace(' ', '')}"
            alternatives.append(metrics)

    feasible_alts = [a for a in alternatives if a["feasible"]]

    # Frontera de Pareto sobre alternativas factibles respecto a 4 objetivos a minimizar:
    # f1 = total_steel_mass_kg, f2 = estimated_cost_EUR, f3 = constructability_index, f4 = max_dcr_overall
    pareto_ids: list[str] = []
    for a in feasible_alts:
        dominated = False
        for b in feasible_alts:
            if a["alternative_id"] == b["alternative_id"]:
                continue
            no_worse = (
                b["total_steel_mass_kg"] <= a["total_steel_mass_kg"]
                and b["estimated_cost_EUR"] <= a["estimated_cost_EUR"]
                and b["constructability_index"] <= a["constructability_index"]
                and b["max_dcr_overall"] <= a["max_dcr_overall"]
            )
            strictly_better = (
                b["total_steel_mass_kg"] < a["total_steel_mass_kg"]
                or b["estimated_cost_EUR"] < a["estimated_cost_EUR"]
                or b["constructability_index"] < a["constructability_index"]
                or b["max_dcr_overall"] < a["max_dcr_overall"]
            )
            if no_worse and strictly_better:
                dominated = True
                break
        a["pareto_optimal"] = not dominated
        if not dominated:
            pareto_ids.append(a["alternative_id"])
    for a in alternatives:
        if not a["feasible"]:
            a["pareto_optimal"] = False

    # Función de utilidad multiobjetivo ponderada normalizada sobre las alternativas factibles:
    # w_mass=0.35, w_cost=0.30, w_carbon=0.15, w_constructability=0.10, w_dcr_efficiency=0.10
    if feasible_alts:
        min_m = min(a["total_steel_mass_kg"] for a in feasible_alts)
        max_m = max(a["total_steel_mass_kg"] for a in feasible_alts)
        min_c = min(a["estimated_cost_EUR"] for a in feasible_alts)
        max_c = max(a["estimated_cost_EUR"] for a in feasible_alts)
        min_co2 = min(a["embodied_carbon_total_kgCO2e"] for a in feasible_alts)
        max_co2 = max(a["embodied_carbon_total_kgCO2e"] for a in feasible_alts)
        min_k = min(a["constructability_index"] for a in feasible_alts)
        max_k = max(a["constructability_index"] for a in feasible_alts)

        def _norm(val: float, lo: float, hi: float) -> float:
            return (val - lo) / (hi - lo) if hi > lo + 1e-9 else 0.0

        for a in feasible_alts:
            # Penalizar sobredimensionamiento excesivo (óptimo cerca de DCR ~ 0.85..0.95)
            dcr_pen = abs(0.90 - float(a["max_dcr_overall"]))
            score = (
                0.35 * _norm(a["total_steel_mass_kg"], min_m, max_m)
                + 0.30 * _norm(a["estimated_cost_EUR"], min_c, max_c)
                + 0.15 * _norm(a["embodied_carbon_total_kgCO2e"], min_co2, max_co2)
                + 0.10 * _norm(a["constructability_index"], min_k, max_k)
                + 0.10 * dcr_pen
            )
            a["multiobjective_penalty_score"] = round(score, 6)
        feasible_sorted = sorted(feasible_alts, key=lambda x: x["multiobjective_penalty_score"])
        best_overall = feasible_sorted[0]
        # Mejor dentro de la topologia adoptada (n_girders = spec.n_girders)
        same_ng_feasible = [a for a in feasible_sorted if a["n_girders"] == int(spec.n_girders)]
        best_for_adopted_ng = min(same_ng_feasible, key=lambda x: x["total_steel_mass_kg"]) if same_ng_feasible else best_overall
    else:
        feasible_sorted = []
        best_overall = None
        best_for_adopted_ng = None

    selected_sec = (
        str(final_design_result.get("final_girder_section"))
        if final_design_result and final_design_result.get("final_girder_section")
        else (best_for_adopted_ng["girder_section"] if best_for_adopted_ng else spec.girder_section.name)
    )
    selected_ng = int(spec.n_girders)
    selected_alt = next(
        (a for a in alternatives if a["n_girders"] == selected_ng and a["girder_section"] == selected_sec),
        best_for_adopted_ng,
    )

    if selected_alt and selected_alt["feasible"]:
        is_min_mass_for_ng = (
            best_for_adopted_ng is not None
            and selected_alt["alternative_id"] == best_for_adopted_ng["alternative_id"]
        )
        optimization_classification = (
            "MEJOR_SOLUCION_ENCONTRADA" if (selected_alt.get("pareto_optimal") or is_min_mass_for_ng) else "SOLUCION_FACTIBLE"
        )
    else:
        optimization_classification = "SIN_SOLUCION_FACTIBLE"

    return {
        "objectives": [
            "min_total_steel_mass_kg",
            "min_estimated_cost_EUR",
            "min_embodied_carbon_total_kgCO2e",
            "min_constructability_index",
            "target_structural_utilization_DCR_le_1",
        ],
        "weights": {
            "total_steel_mass_kg": 0.35,
            "estimated_cost_EUR": 0.30,
            "embodied_carbon_total_kgCO2e": 0.15,
            "constructability_index": 0.10,
            "dcr_efficiency": 0.10,
        },
        "total_alternatives_evaluated": len(alternatives),
        "feasible_alternatives_count": len(feasible_alts),
        "pareto_frontier_ids": pareto_ids,
        "optimization_classification": optimization_classification,
        "selected_alternative": selected_alt,
        "best_for_adopted_topology": best_for_adopted_ng,
        "best_across_all_topologies": best_overall,
        "top_feasible_ranking": feasible_sorted[:8],
        "all_alternatives": alternatives,
    }


__all__ = [
    "APPLICABLE_LIMIT_STATES",
    "BRIDGE_DIAPHRAGM_LADDER",
    "BRIDGE_FULL_GIRDER_LADDER",
    "BRIDGE_PLATE_GIRDER_SPECS",
    "BRIDGE_STEEL_GIRDER_LADDER",
    "BridgeDesignSpec",
    "HL93_LANE_LOAD_KN_M",
    "MODEL_LIMITATIONS",
    "MaterialSpec",
    "OAPICallError",
    "SectionMechanicalProps",
    "UNIMPLEMENTED_CHECKS",
    "bridge_spec_from_encargo",
    "build_bridge_grillage",
    "compute_bridge_sustainability_and_cost",
    "compute_expected_vertical_loads_kN",
    "courbon_transverse_factors",
    "default_bridge_material",
    "design_lanes_aashto_lrfd",
    "evaluate_bridge_design_alternatives",
    "execute_bridge_grillage_analysis_and_reopen",
    "execute_bridge_grillage_design_loop",
    "expected_grillage_counts",
    "generate_grillage",
    "grillage_model",
    "notional_lanes_en1991_2",
    "plate_girder_section_props",
    "rectangular_concrete_section_props",
    "run_bridge_grillage_design_loop_sap2000",
    "run_bridge_grillage_sap2000",
    "section_props_from_catalog",
    "select_bridge_sections",
    "verify_bridge_grillage_results",
    "verify_kinematic_stability",
    "verify_sap_section_properties",
]
