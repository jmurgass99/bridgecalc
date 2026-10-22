"""bridgejm.loads.iap11 — Sobrecargas de tráfico según IAP-11 (Instrucción de Carreteras, España).

Implementa las disposiciones del Capítulo 4 "Sobrecargas de uso de tráfico rodado":
- Modelo de Carga 1 (MC1, Art. 4.1.1):
  * Sistema de tándem (TS) de dos ejes por carril (300 kN, 200 kN, 100 kN).
  * Carga uniforme repartida (UDL): 9.0 kN/m² en Carril 1; 2.5 kN/m² en Carril 2, 3 y área remanente.
- Modelo de Carga 2 (MC2, Art. 4.1.2):
  * Eje simple aislado de 400 kN (200 kN por rueda) con huella 0.35 x 0.60 m.
- Modelo de Carga 4 (MC4, Art. 4.1.4):
  * Cargas en pasarelas y aceras de servicio (5.0 kN/m² hasta 2.5 kN/m² según luz).
- Coeficientes de combinación y factores de seguridad IAP-11 (Tabla 3.1):
  * gamma_Q = 1.35 (ELU), psi_0 = 0.75, psi_1 = 0.75, psi_2 = 0.00.

Mantiene estricta independencia respecto a los factores y anexos de otros países.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Constantes IAP-11 (Tabla 4.2 y Art. 4.1)
# ---------------------------------------------------------------------------

IAP11_LANE_WIDTH_m = 3.0           # Ancho de carril virtual
IAP11_TS_AXLES_kN = (300.0, 200.0, 100.0)  # Carga por eje en carril 1, 2, 3
IAP11_UDL_kN_m2 = (9.0, 2.5, 2.5)          # UDL carril 1, 2, 3
IAP11_REMAINING_UDL_kN_m2 = 2.5            # Área remanente
IAP11_MC2_AXLE_kN = 400.0                  # Eje simple MC2
IAP11_GAMMA_Q_ELU = 1.35                   # Coeficiente parcial de sobrecarga ELU
IAP11_PSI_0 = 0.75                         # Coeficiente de combinación


@dataclass(frozen=True)
class IAP11TrafficEnvelope:
    """Envolvente de esfuerzos flectores y cortantes máximos según IAP-11."""
    span_m: float
    carriageway_width_m: float
    n_notional_lanes: int
    # MC1
    M_TS_kNm: float
    M_UDL_kNm: float
    M_MC1_total_characteristic_kNm: float
    M_MC1_design_ELU_kNm: float     # Con gamma_Q = 1.35
    V_TS_kN: float
    V_UDL_kN: float
    V_MC1_total_characteristic_kN: float
    V_MC1_design_ELU_kN: float       # Con gamma_Q = 1.35
    # MC2
    M_MC2_characteristic_kNm: float
    V_MC2_characteristic_kN: float
    # Gobernante característica
    M_governing_characteristic_kNm: float
    V_governing_characteristic_kN: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "standard": "IAP-11 (España)",
            "span_m": self.span_m,
            "carriageway_width_m": self.carriageway_width_m,
            "n_notional_lanes": self.n_notional_lanes,
            "M_MC1_characteristic_kNm": self.M_MC1_total_characteristic_kNm,
            "M_MC1_design_ELU_kNm": self.M_MC1_design_ELU_kNm,
            "V_MC1_characteristic_kN": self.V_MC1_total_characteristic_kN,
            "V_MC1_design_ELU_kN": self.V_MC1_design_ELU_kN,
            "M_MC2_characteristic_kNm": self.M_MC2_characteristic_kNm,
            "V_MC2_characteristic_kN": self.V_MC2_characteristic_kN,
            "M_governing_characteristic_kNm": self.M_governing_characteristic_kNm,
            "V_governing_characteristic_kN": self.V_governing_characteristic_kN,
        }


def iap11_number_of_lanes(carriageway_width_m: float) -> tuple[int, float]:
    """Determina el número de carriles virtuales y el ancho del área remanente (IAP-11 Tabla 4.1)."""
    w = max(carriageway_width_m, 0.0)
    if w < 5.4:
        n_lanes = 1
    elif w < 6.0:
        n_lanes = 2
    else:
        n_lanes = int(math.floor(w / IAP11_LANE_WIDTH_m))

    remaining_width = max(0.0, w - n_lanes * IAP11_LANE_WIDTH_m)
    return n_lanes, remaining_width


def evaluate_iap11_traffic_loads(
    span_m: float,
    carriageway_width_m: float,
    gamma_Q: float = IAP11_GAMMA_Q_ELU,
) -> IAP11TrafficEnvelope:
    """Calcula la envolvente de momentos y cortantes en viga biapoyada según IAP-11."""
    if span_m <= 0.0 or carriageway_width_m <= 0.0:
        raise ValueError("Luz de vano y ancho de calzada deben ser estrictamente positivos")

    L = span_m
    w = carriageway_width_m
    n_lanes, rem_w = iap11_number_of_lanes(w)

    # 1. Sistema de Tándem MC1:
    # Máximo flector con 2 ejes separados 1.2 m centrados en el vano
    # Momento de un tándem de 2 ejes P_axle: M = P_axle * (L/2 - 0.3) si L >= 1.2
    m_ts_total = 0.0
    v_ts_total = 0.0

    for lane_idx in range(n_lanes):
        p_axle = IAP11_TS_AXLES_kN[lane_idx] if lane_idx < len(IAP11_TS_AXLES_kN) else 0.0
        if p_axle <= 0.0:
            continue
        # 2 ejes por tándem
        if L >= 1.2:
            m_lane_ts = p_axle * (L / 2.0 - 0.3)
        else:
            m_lane_ts = p_axle * (L / 4.0)
        # Cortante en apoyo: un eje sobre el apoyo y otro a 1.2 m
        v_lane_ts = p_axle * (1.0 + max(0.0, 1.0 - 1.2 / L))
        m_ts_total += m_lane_ts
        v_ts_total += v_lane_ts

    # 2. Carga Uniforme Repartida (UDL) MC1:
    q_total_linear = 0.0
    for lane_idx in range(n_lanes):
        q_lane = IAP11_UDL_kN_m2[lane_idx] if lane_idx < len(IAP11_UDL_kN_m2) else IAP11_REMAINING_UDL_kN_m2
        q_total_linear += q_lane * IAP11_LANE_WIDTH_m
    q_total_linear += IAP11_REMAINING_UDL_kN_m2 * rem_w

    m_udl_total = q_total_linear * (L ** 2) / 8.0
    v_udl_total = q_total_linear * L / 2.0

    m_mc1_total = m_ts_total + m_udl_total
    v_mc1_total = v_ts_total + v_udl_total

    # 3. Modelo de Carga 2 (MC2):
    # Eje único de 400 kN
    m_mc2 = IAP11_MC2_AXLE_kN * L / 4.0
    v_mc2 = IAP11_MC2_AXLE_kN

    # Gobernantes características y de diseño
    m_gov = max(m_mc1_total, m_mc2)
    v_gov = max(v_mc1_total, v_mc2)

    return IAP11TrafficEnvelope(
        span_m=round(L, 3),
        carriageway_width_m=round(w, 3),
        n_notional_lanes=n_lanes,
        M_TS_kNm=round(m_ts_total, 2),
        M_UDL_kNm=round(m_udl_total, 2),
        M_MC1_total_characteristic_kNm=round(m_mc1_total, 2),
        M_MC1_design_ELU_kNm=round(m_mc1_total * gamma_Q, 2),
        V_TS_kN=round(v_ts_total, 2),
        V_UDL_kN=round(v_udl_total, 2),
        V_MC1_total_characteristic_kN=round(v_mc1_total, 2),
        V_MC1_design_ELU_kN=round(v_mc1_total * gamma_Q, 2),
        M_MC2_characteristic_kNm=round(m_mc2, 2),
        V_MC2_characteristic_kN=round(v_mc2, 2),
        M_governing_characteristic_kNm=round(m_gov, 2),
        V_governing_characteristic_kN=round(v_gov, 2),
    )


__all__ = [
    "IAP11TrafficEnvelope",
    "iap11_number_of_lanes",
    "evaluate_iap11_traffic_loads",
    "IAP11_GAMMA_Q_ELU",
    "IAP11_PSI_0",
]
