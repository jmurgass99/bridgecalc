"""bridgejm.loads.iap11 — Sobrecargas de tráfico según IAP-11 (Instrucción de Carreteras, España).

Implementa las disposiciones del Capítulo 4 "Sobrecargas de uso de tráfico rodado"
de la Instrucción sobre las acciones a considerar en el proyecto de puentes de carretera
(IAP-11, Orden FOM/2842/2011, BOE de 29 de septiembre de 2011):

1. División de calzada en carriles virtuales (Tabla 4.1):
   - w < 5.4 m: 1 carril virtual de 3.0 m y área remanente w - 3.0 m.
   - 5.4 m <= w < 6.0 m: 2 carriles virtuales de ancho w / 2, sin área remanente.
   - w >= 6.0 m: floor(w / 3) carriles virtuales de 3.0 m y área remanente w - 3*n m.

2. Modelo de Carga 1 (MC1, Art. 4.1.1):
   - Sistema de tándem (TS) de dos ejes separados 1.20 m longitudinalmente:
     * Carril 1: 300 kN por eje (600 kN por vehículo).
     * Carril 2: 200 kN por eje (400 kN por vehículo).
     * Carril 3: 100 kN por eje (200 kN por vehículo).
     * Carril i > 3: 0 kN.
   - Carga uniforme repartida (UDL):
     * Carril 1: 9.0 kN/m² sobre el ancho real del carril.
     * Carril 2: 2.5 kN/m² sobre el ancho real del carril.
     * Carril 3: 2.5 kN/m² sobre el ancho real del carril.
     * Carril i > 3: 2.5 kN/m² sobre el ancho real del carril.
     * Área remanente: 2.5 kN/m² sobre el ancho remanente.
   - Cinemática analítica de viga biapoyada:
     * Teorema de Barré para el tándem: M_max = (P_axle / (2*L)) * (L - 0.60)^2 para L >= 2.05 m.
     * En vanos cortos (L < 2.05 m): rige un solo eje centrado en vano, M_max = P_axle * L / 4.
     * Cortante en apoyo: V_max = P_axle * max(1.0, 2.0 - 1.20 / L).

3. Modelo de Carga 2 (MC2, Art. 4.1.2) / EN 1991-2 LM2:
   - Eje simple de 400 kN (200 kN por rueda) con contacto 0.35 x 0.60 m.
   - Modelo específico para comprobaciones locales de tablero (losas, voladizos, juntas),
     segregado de la flexión global de vigas principales.

4. Factores de combinación y seguridad (Tabla 3.1):
   - gamma_Q = 1.35 (ELU situación persistente/transitoria).
   - psi_0 = 0.75, psi_1 = 0.75, psi_2 = 0.00.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Optional, Sequence


# ---------------------------------------------------------------------------
# Constantes Normativas IAP-11 (Tabla 4.2 y Art. 4.1)
# ---------------------------------------------------------------------------

IAP11_STANDARD_LANE_WIDTH_m = 3.0                 # Ancho estándar de carril virtual [m]
IAP11_TS_AXLE_SPACING_m = 1.20                    # Separación longitudinal entre ejes del tándem [m]
IAP11_TS_AXLES_kN = (300.0, 200.0, 100.0)         # Carga por eje en carril 1, 2, 3 [kN]
IAP11_UDL_kN_m2 = (9.0, 2.5, 2.5)                 # Sobrecarga uniforme carril 1, 2, 3 [kN/m²]
IAP11_REMAINING_UDL_kN_m2 = 2.5                   # Sobrecarga uniforme área remanente [kN/m²]
IAP11_MC2_AXLE_kN = 400.0                         # Eje simple MC2 para comprobaciones locales [kN]
IAP11_GAMMA_Q_ELU = 1.35                          # Coeficiente parcial de acciones variables ELU
IAP11_PSI_0 = 0.75                                # Coeficiente de combinación característica
IAP11_PSI_1 = 0.75                                # Coeficiente de combinación frecuente
IAP11_PSI_2 = 0.00                                # Coeficiente de combinación casi permanente


# ---------------------------------------------------------------------------
# Geometría Transversal (Tabla 4.1)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NotionalLaneLayout:
    """Distribución de carriles virtuales y área remanente según IAP-11 Tabla 4.1."""
    carriageway_width_m: float
    n_lanes: int
    lane_widths_m: tuple[float, ...]
    remaining_width_m: float
    units: dict[str, str] = field(default_factory=lambda: {"length": "m"})

    def to_dict(self) -> dict[str, Any]:
        return {
            "carriageway_width_m": self.carriageway_width_m,
            "n_lanes": self.n_lanes,
            "lane_widths_m": list(self.lane_widths_m),
            "remaining_width_m": self.remaining_width_m,
            "units": dict(self.units),
        }


def iap11_lane_layout(carriageway_width_m: float) -> NotionalLaneLayout:
    """Calcula la división transversal de carriles virtuales según IAP-11 Tabla 4.1.

    Reglas de la instrucción:
    - w < 5.4 m: 1 carril virtual de 3.0 m y área remanente = w - 3.0 m.
    - 5.4 m <= w < 6.0 m: 2 carriles virtuales de ancho w / 2, sin área remanente.
    - w >= 6.0 m: floor(w / 3) carriles virtuales de 3.0 m y área remanente = w - 3*n m.
    """
    if carriageway_width_m <= 0.0:
        raise ValueError("El ancho de calzada debe ser estrictamente positivo")

    w = float(carriageway_width_m)
    if w < 5.4:
        n_lanes = 1
        lane_widths = (min(w, IAP11_STANDARD_LANE_WIDTH_m),)
        rem_w = max(0.0, round(w - lane_widths[0], 6))
    elif w < 6.0:
        n_lanes = 2
        half_w = round(w / 2.0, 6)
        lane_widths = (half_w, half_w)
        rem_w = 0.0
    else:
        n_lanes = int(math.floor(w / IAP11_STANDARD_LANE_WIDTH_m))
        lane_widths = (IAP11_STANDARD_LANE_WIDTH_m,) * n_lanes
        rem_w = max(0.0, round(w - n_lanes * IAP11_STANDARD_LANE_WIDTH_m, 6))

    return NotionalLaneLayout(
        carriageway_width_m=round(w, 4),
        n_lanes=n_lanes,
        lane_widths_m=lane_widths,
        remaining_width_m=rem_w,
    )


def iap11_number_of_lanes(carriageway_width_m: float) -> tuple[int, float]:
    """Determina el número de carriles virtuales y el ancho del área remanente (IAP-11 Tabla 4.1).

    Función de compatibilidad que devuelve (n_lanes, remaining_width_m).
    """
    layout = iap11_lane_layout(carriageway_width_m)
    return layout.n_lanes, layout.remaining_width_m


# ---------------------------------------------------------------------------
# Cinemática Analítica de Cargas Concentradas (Tándem IAP-11)
# ---------------------------------------------------------------------------

def tandem_bending_moment_barre(
    p_axle_kN: float,
    span_m: float,
    axle_spacing_m: float = IAP11_TS_AXLE_SPACING_m,
    units: dict[str, str] | None = None,
) -> float:
    """Calcula el momento flector máximo en viga biapoyada bajo un tándem de 2 ejes.

    Aplica rigurosamente el Teorema de Barré:
    - La posición crítica ocurre cuando un eje y la resultante de los dos ejes equidistan
      del centro de la luz del vano (distancia entre eje y centro = d / 4 = 0.30 m).
    - Para d = 1.20 m, la posición crítica de Barré es válida siempre que ambos ejes
      actúen dentro del vano y superen la solicitación de un eje único centrado:
      L >= (1 + 1/sqrt(2)) * d ≈ 2.0485 m.
      En ese rango:
      M_max = (P_axle / (2 * L)) * (L - d / 2)^2 = (P_axle / (2 * L)) * (L - 0.60)^2.
    - Para vanos cortos L < 2.0485 m: rige un solo eje situado en el centro del vano:
      M_max = P_axle * L / 4.
    """
    if p_axle_kN <= 0.0 or span_m <= 0.0:
        return 0.0

    L = float(span_m)
    d = float(axle_spacing_m)

    # Límite analítico donde Barré con 2 ejes iguala a 1 eje centrado:
    # (L - d/2)^2 / (2*L) >= L / 4  <=>  L^2 - 2*d*L + d^2/2 >= 0
    # L_crit = d * (1 + 1/sqrt(2))
    l_crit = d * (1.0 + 1.0 / math.sqrt(2.0))

    if L >= l_crit:
        # Posición de Barré: x1 = L/2 - d/4
        return (p_axle_kN / (2.0 * L)) * ((L - d / 2.0) ** 2)
    else:
        # Vano corto: un eje único centrado produce mayor momento
        return p_axle_kN * L / 4.0


def tandem_shear_force_support(
    p_axle_kN: float,
    span_m: float,
    axle_spacing_m: float = IAP11_TS_AXLE_SPACING_m,
    units: dict[str, str] | None = None,
) -> float:
    """Calcula el cortante máximo en apoyo de viga biapoyada bajo un tándem de 2 ejes.

    La posición crítica de cortante ocurre con el primer eje situado inmediatamente
    sobre el apoyo (x = 0) y el segundo eje a la distancia longitudinal d = 1.20 m:
    - Si L >= d: V_max = P_axle * (1.0 + (L - d) / L) = P_axle * (2.0 - d / L).
    - Si L < d: el segundo eje está fuera del vano, por lo que actúa únicamente un eje:
      V_max = P_axle * 1.0.
    """
    if p_axle_kN <= 0.0 or span_m <= 0.0:
        return 0.0

    L = float(span_m)
    d = float(axle_spacing_m)

    if L >= d:
        return p_axle_kN * (2.0 - d / L)
    else:
        return p_axle_kN * 1.0


# ---------------------------------------------------------------------------
# Modelo de Carga 2 (MC2 / EN 1991-2 LM2) — Comprobaciones Locales
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EN1991_2_LoadModel2:
    """Modelo de Carga 2 (LM2) según EN 1991-2 §4.3.3 e IAP-11 Art. 4.1.2.

    Definido estrictamente para comprobaciones locales (losas de tablero, voladizos,
    elementos de transición y juntas). No debe mezclarse sin justificación con el
    modelo global MC1 para dimensionamiento longitudinal de vigas principales.
    """
    axle_load_kN: float = IAP11_MC2_AXLE_kN
    wheel_contact_length_m: float = 0.35
    wheel_contact_width_m: float = 0.60
    wheel_transverse_spacing_m: float = 2.00
    units: dict[str, str] = field(default_factory=lambda: {"force": "kN", "length": "m"})

    def local_bending_moment_kNm(self, local_span_m: float) -> float:
        """Momento flector en flexión local de un vano de losa de luz local_span_m."""
        if local_span_m <= 0.0:
            raise ValueError("La luz local debe ser estrictamente positiva")
        return self.axle_load_kN * local_span_m / 4.0

    def local_shear_force_kN(self) -> float:
        """Cortante local máximo generado por el eje simple."""
        return self.axle_load_kN


# ---------------------------------------------------------------------------
# Envolvente Global de Tráfico IAP-11
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IAP11TrafficEnvelope:
    """Envolvente de esfuerzos flectores y cortantes máximos según IAP-11."""
    span_m: float
    carriageway_width_m: float
    n_notional_lanes: int
    lane_widths_m: tuple[float, ...]
    remaining_width_m: float
    # MC1 Efectos Globales Longitudinales
    M_TS_kNm: float
    M_UDL_kNm: float
    M_MC1_total_characteristic_kNm: float
    M_MC1_design_ELU_kNm: float     # Con gamma_Q = 1.35
    V_TS_kN: float
    V_UDL_kN: float
    V_MC1_total_characteristic_kN: float
    V_MC1_design_ELU_kN: float       # Con gamma_Q = 1.35
    # MC2 Comprobación Local de Tablero (Art. 4.1.2)
    M_MC2_characteristic_kNm: float
    V_MC2_characteristic_kN: float
    # Esfuerzos gobernantes característicos para diseño longitudinal de vigas principales (MC1)
    M_governing_characteristic_kNm: float
    V_governing_characteristic_kN: float
    units: dict[str, str] = field(default_factory=lambda: {
        "force": "kN", "moment": "kNm", "pressure": "kN/m2", "length": "m"
    })

    def to_dict(self) -> dict[str, Any]:
        return {
            "standard": "IAP-11 (España)",
            "span_m": self.span_m,
            "carriageway_width_m": self.carriageway_width_m,
            "n_notional_lanes": self.n_notional_lanes,
            "lane_widths_m": list(self.lane_widths_m),
            "remaining_width_m": self.remaining_width_m,
            "units": dict(self.units),
            "M_MC1_characteristic_kNm": self.M_MC1_total_characteristic_kNm,
            "M_MC1_design_ELU_kNm": self.M_MC1_design_ELU_kNm,
            "V_MC1_characteristic_kN": self.V_MC1_total_characteristic_kN,
            "V_MC1_design_ELU_kN": self.V_MC1_design_ELU_kN,
            "M_MC2_local_characteristic_kNm": self.M_MC2_characteristic_kNm,
            "V_MC2_local_characteristic_kN": self.V_MC2_characteristic_kN,
            "M_governing_characteristic_kNm": self.M_governing_characteristic_kNm,
            "V_governing_characteristic_kN": self.V_governing_characteristic_kN,
        }


def evaluate_iap11_traffic_loads(
    span_m: float,
    carriageway_width_m: float,
    gamma_Q: float = IAP11_GAMMA_Q_ELU,
    units: dict[str, str] | None = None,
) -> IAP11TrafficEnvelope:
    """Calcula la envolvente de momentos y cortantes en viga biapoyada según IAP-11.

    Parameters
    ----------
    span_m : float
        Luz longitudinal de cálculo entre apoyos [m].
    carriageway_width_m : float
        Ancho total de calzada entre bordillos o barreras [m].
    gamma_Q : float
        Coeficiente parcial para acciones de tráfico en ELU (IAP-11 Tabla 3.1: 1.35).
    units : dict[str, str], optional
        Diccionario declarativo de unidades para cumplimiento de contrato de ingeniería.

    Returns
    -------
    IAP11TrafficEnvelope
        Objeto inmutable con la descomposición completa de esfuerzos MC1, MC2 y diseño.
    """
    if span_m <= 0.0 or carriageway_width_m <= 0.0:
        raise ValueError("Luz de vano y ancho de calzada deben ser estrictamente positivos")

    L = float(span_m)
    w = float(carriageway_width_m)
    layout = iap11_lane_layout(w)
    n_lanes = layout.n_lanes
    lane_widths = layout.lane_widths_m
    rem_w = layout.remaining_width_m

    # 1. Sistema de Tándem MC1:
    # Cada carril virtual asignado tiene su propio tándem de 2 ejes
    m_ts_total = 0.0
    v_ts_total = 0.0

    for lane_idx in range(n_lanes):
        p_axle = IAP11_TS_AXLES_kN[lane_idx] if lane_idx < len(IAP11_TS_AXLES_kN) else 0.0
        if p_axle <= 0.0:
            continue
        m_lane_ts = tandem_bending_moment_barre(p_axle, L)
        v_lane_ts = tandem_shear_force_support(p_axle, L)
        m_ts_total += m_lane_ts
        v_ts_total += v_lane_ts

    # 2. Carga Uniforme Repartida (UDL) MC1:
    # Se calcula integrando la sobrecarga superficial sobre el ancho real de cada carril
    q_total_linear = 0.0
    for lane_idx, lane_w in enumerate(lane_widths):
        q_lane = IAP11_UDL_kN_m2[lane_idx] if lane_idx < len(IAP11_UDL_kN_m2) else IAP11_REMAINING_UDL_kN_m2
        q_total_linear += q_lane * lane_w
    q_total_linear += IAP11_REMAINING_UDL_kN_m2 * rem_w

    m_udl_total = q_total_linear * (L ** 2) / 8.0
    v_udl_total = q_total_linear * L / 2.0

    # MC1 Totales
    m_mc1_total = m_ts_total + m_udl_total
    v_mc1_total = v_ts_total + v_udl_total

    # 3. Modelo de Carga 2 (MC2, Art. 4.1.2):
    # Eje simple de 400 kN para comprobaciones locales
    lm2 = EN1991_2_LoadModel2()
    m_mc2_local = lm2.local_bending_moment_kNm(L)
    v_mc2_local = lm2.local_shear_force_kN()

    # Para el dimensionamiento longitudinal global de vigas de tablero rige el MC1
    m_gov = m_mc1_total
    v_gov = v_mc1_total

    return IAP11TrafficEnvelope(
        span_m=round(L, 3),
        carriageway_width_m=round(w, 3),
        n_notional_lanes=n_lanes,
        lane_widths_m=lane_widths,
        remaining_width_m=rem_w,
        M_TS_kNm=round(m_ts_total, 2),
        M_UDL_kNm=round(m_udl_total, 2),
        M_MC1_total_characteristic_kNm=round(m_mc1_total, 2),
        M_MC1_design_ELU_kNm=round(m_mc1_total * gamma_Q, 2),
        V_TS_kN=round(v_ts_total, 2),
        V_UDL_kN=round(v_udl_total, 2),
        V_MC1_total_characteristic_kN=round(v_mc1_total, 2),
        V_MC1_design_ELU_kN=round(v_mc1_total * gamma_Q, 2),
        M_MC2_characteristic_kNm=round(m_mc2_local, 2),
        V_MC2_characteristic_kN=round(v_mc2_local, 2),
        M_governing_characteristic_kNm=round(m_gov, 2),
        V_governing_characteristic_kN=round(v_gov, 2),
    )


__all__ = [
    "IAP11TrafficEnvelope",
    "NotionalLaneLayout",
    "EN1991_2_LoadModel2",
    "iap11_lane_layout",
    "iap11_number_of_lanes",
    "tandem_bending_moment_barre",
    "tandem_shear_force_support",
    "evaluate_iap11_traffic_loads",
    "IAP11_STANDARD_LANE_WIDTH_m",
    "IAP11_TS_AXLE_SPACING_m",
    "IAP11_GAMMA_Q_ELU",
    "IAP11_PSI_0",
    "IAP11_PSI_1",
    "IAP11_PSI_2",
]
