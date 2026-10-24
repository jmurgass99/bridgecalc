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
import re
from typing import Any

from fastsap.section_catalog import IShape, get_section
from fastsap.utils import csi_enum
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


def section_props_from_catalog(profile_name: str, material_name: str = "S355") -> SectionMechanicalProps:
    """Obtiene propiedades mecanicas completas desde ``fastsap.section_catalog``."""
    sec = get_section(profile_name)
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
    galibo_m = float(m_galibo.group(1).replace(",", ".")) if m_galibo else 5.0

    m_vanos = re.search(r"(\d+)\s*vanos", apoyos_raw, re.I)
    n_spans = int(m_vanos.group(1)) if m_vanos else 1

    n_girders = max(3, min(8, round(width_m / 2.5)))
    n_diaphragms = max(2, round(span_m / 7.5) - 1)

    mat = default_bridge_material(material_raw, norma_code)
    girder_sec, diaph_sec, trace = select_bridge_sections(span_m, mat)

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
    sdb_str = str(p_sdb).replace("/", "\\")
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
    for f in frames_spec:
        sec_assigned = get_section(sap_model.FrameObj, f["id"])
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


__all__ = [
    "APPLICABLE_LIMIT_STATES",
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
    "compute_expected_vertical_loads_kN",
    "courbon_transverse_factors",
    "default_bridge_material",
    "design_lanes_aashto_lrfd",
    "execute_bridge_grillage_analysis_and_reopen",
    "expected_grillage_counts",
    "generate_grillage",
    "grillage_model",
    "notional_lanes_en1991_2",
    "rectangular_concrete_section_props",
    "run_bridge_grillage_sap2000",
    "section_props_from_catalog",
    "select_bridge_sections",
    "verify_kinematic_stability",
]
