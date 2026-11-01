"""
Envolvente HL-93 en vigas continuas de 2 a 6 vanos por líneas de influencia.

Para cada efecto se construye la línea de influencia exacta (viga de Euler-Bernoulli con EI
constante, ecuación de los tres momentos en ``influence_lines.influence_line_continuous``) y se
barre el tren de cargas sobre ella:

- Momento positivo: puntos de evaluación repartidos en cada vano; camión HL-93 en los dos sentidos
  de marcha, tándem, y carril de 9,34 kN/m solo en las zonas de ordenada positiva (AASHTO LRFD
  §3.6.1.3.1: el carril se aplica únicamente donde contribuye al efecto extremo).
- Momento negativo en cada apoyo interior: lo mayor de (un camión o el tándem, con IM, + carril en
  las zonas negativas) y del 90 % de dos camiones separados al menos 15 m entre el eje trasero de
  uno y el delantero del otro más el 90 % del carril (AASHTO LRFD §3.6.1.3.1).
- Cortante: en el apoyo extremo y a ambas caras de cada apoyo interior.

El incremento dinámico IM se aplica solo al vehículo, no al carril. Hasta la versión 1.0 esta
función devolvía coeficientes 0,080/0,100·w·L² y 0,40·w·L con una «carga uniforme equivalente» del
camión (IM·325 kN / L), que no es ningún procedimiento normativo y para 2 × 30 m daba M⁺ = 1710,
M⁻ = 2137 y V = 285 frente a los valores de la envolvente real.

Limitaciones: EI constante en toda la viga (no modela cambios de inercia ni cartelas), apoyos
puntuales rígidos, un solo carril de diseño (multiplica por el factor de distribución y de
presencia múltiple fuera de aquí), sin fatiga ni deflexiones.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np

from .hl93 import (
    LANE_LOAD_kN_per_m,
    TANDEM_AXLES_kN,
    TANDEM_SPACING_m,
    TRUCK_AXLES_kN,
    TRUCK_AXLE_SPACINGS_m,
)
from .influence_lines import (
    InfluenceLine,
    influence_line_continuous,
    influence_line_reaction_continuous,
)

# AASHTO LRFD §3.6.1.3.1: momento negativo entre puntos de inflexión y reacciones en pilas
TWO_TRUCK_MIN_GAP_m = 15.0      # 50 ft entre eje trasero de un camión y delantero del otro
TWO_TRUCK_FACTOR = 0.90

MAX_SPANS = 6

_TRUCK_FWD: tuple[tuple[float, float], ...] = (
    (0.0, TRUCK_AXLES_kN[0]),
    (TRUCK_AXLE_SPACINGS_m[0], TRUCK_AXLES_kN[1]),
    (TRUCK_AXLE_SPACINGS_m[0] + TRUCK_AXLE_SPACINGS_m[1], TRUCK_AXLES_kN[2]),
)
_TRUCK_REV: tuple[tuple[float, float], ...] = (
    (0.0, TRUCK_AXLES_kN[2]),
    (TRUCK_AXLE_SPACINGS_m[1], TRUCK_AXLES_kN[1]),
    (TRUCK_AXLE_SPACINGS_m[0] + TRUCK_AXLE_SPACINGS_m[1], TRUCK_AXLES_kN[0]),
)
_TANDEM: tuple[tuple[float, float], ...] = ((0.0, TANDEM_AXLES_kN[0]), (TANDEM_SPACING_m, TANDEM_AXLES_kN[1]))
_TRUCK_LENGTH_m = TRUCK_AXLE_SPACINGS_m[0] + TRUCK_AXLE_SPACINGS_m[1]


@dataclass(frozen=True)
class MultiSpanInput:
    span_m: float                       # luz de cada vano (vanos iguales)
    n_spans: int                        # 2 a 6
    impact_factor: float = 1.33         # 1 + IM, solo sobre el vehículo
    spans_m: tuple[float, ...] | None = None   # luces desiguales: si se da, manda sobre span_m/n_spans
    n_points_per_span: int = 200        # malla de la línea de influencia por vano (el carril del cortante tiene un error de malla < 1 %)
    n_eval_per_span: int = 20           # secciones evaluadas por vano para el momento positivo


@dataclass(frozen=True)
class MultiSpanResult:
    M_positive_max_kNm: float
    M_negative_max_kNm: float           # valor absoluto del momento negativo máximo (apoyo interior)
    V_max_kN: float
    governing: str
    M_positive_x_m: float = 0.0
    M_negative_x_m: float = 0.0
    V_x_m: float = 0.0
    R_max_kN: float = 0.0               # reacción máxima vertical en apoyos (incl. 90% de 2 camiones en pilas interiores)
    R_min_uplift_kN: float = 0.0        # reacción mínima (negativa = levantamiento / uplift en estribos o apoyos)
    reactions: list[dict[str, Any]] = field(default_factory=list)
    components: dict[str, Any] = field(default_factory=dict)
    method: str = "líneas de influencia (tres momentos, EI constante) + barrido del tren de cargas"

    def to_dict(self) -> dict[str, Any]:
        return {
            "M_positive_max_kNm": self.M_positive_max_kNm,
            "M_negative_max_kNm": self.M_negative_max_kNm,
            "V_max_kN": self.V_max_kN,
            "governing": self.governing,
            "M_positive_x_m": self.M_positive_x_m,
            "M_negative_x_m": self.M_negative_x_m,
            "V_x_m": self.V_x_m,
            "R_max_kN": self.R_max_kN,
            "R_min_uplift_kN": self.R_min_uplift_kN,
            "reactions": self.reactions,
            "components": self.components,
            "method": self.method,
        }


def _two_trucks(gap_m: float) -> tuple[tuple[float, float], ...]:
    shift = _TRUCK_LENGTH_m + gap_m
    return _TRUCK_FWD + tuple((s + shift, P) for s, P in _TRUCK_FWD)


def _sweep(il: InfluenceLine, train: Sequence[tuple[float, float]], sign: float) -> tuple[float, float]:
    """Máximo de ``sign·efecto`` al barrer el tren sobre la línea de influencia.

    Devuelve (efecto máximo, posición del primer eje). Los ejes fuera de la viga no cargan.
    """
    x = il.x_m
    eta = il.ordinates * sign
    L_total = float(x[-1])
    train_len = max(s for s, _ in train)
    pos0 = np.linspace(-train_len, L_total, max(len(x), 400))
    eff = np.zeros_like(pos0)
    for s, P in train:
        ax = pos0 + s
        inside = (ax >= 0.0) & (ax <= L_total)
        eff += np.where(inside, P * np.interp(np.clip(ax, 0.0, L_total), x, eta), 0.0)
    i = int(np.argmax(eff))
    return float(eff[i]), float(pos0[i])


def _lane(il: InfluenceLine, sign: float, w: float = LANE_LOAD_kN_per_m) -> float:
    """Carril uniforme aplicado solo donde la ordenada tiene el signo buscado (trapecios)."""
    y = np.clip(il.ordinates * sign, 0.0, None)
    x = il.x_m
    return float(w * np.sum(0.5 * (y[1:] + y[:-1]) * np.diff(x)))


def _vehicle_candidates(il: InfluenceLine, sign: float) -> dict[str, tuple[float, float]]:
    fwd = _sweep(il, _TRUCK_FWD, sign)
    rev = _sweep(il, _TRUCK_REV, sign)
    truck = fwd if fwd[0] >= rev[0] else rev
    tandem = _sweep(il, _TANDEM, sign)
    return {"truck": truck, "tandem": tandem}


def _resolve_spans(inp: MultiSpanInput) -> list[float]:
    if inp.spans_m is not None:
        spans = [float(s) for s in inp.spans_m]
    else:
        spans = [float(inp.span_m)] * int(inp.n_spans)
    if not (2 <= len(spans) <= MAX_SPANS):
        raise ValueError(f"Se admiten de 2 a {MAX_SPANS} vanos (recibidos {len(spans)})")
    if any(s <= 0 for s in spans):
        raise ValueError("span_m debe ser > 0")
    if inp.impact_factor <= 0:
        raise ValueError("impact_factor debe ser > 0")
    return spans


def envelope_multispan(inp: MultiSpanInput) -> MultiSpanResult:
    """Envolvente HL-93 (un carril de diseño) en una viga continua por líneas de influencia."""
    spans = _resolve_spans(inp)
    IM = float(inp.impact_factor)
    npts = max(20, int(inp.n_points_per_span))
    n_eval = max(3, int(inp.n_eval_per_span))
    starts = [0.0]
    for s in spans:
        starts.append(starts[-1] + s)
    L_total = starts[-1]

    # ---- momento positivo ------------------------------------------------------------
    best_pos: dict[str, Any] = {"total_kNm": -1.0}
    for k, Lk in enumerate(spans):
        for f in np.linspace(0.1, 0.9, n_eval):
            xe = starts[k] + f * Lk
            il = influence_line_continuous(spans, xe, n_points=npts, quantity="M")
            cand = _vehicle_candidates(il, +1.0)
            lane = _lane(il, +1.0)
            veh_name = "truck" if cand["truck"][0] >= cand["tandem"][0] else "tandem"
            total = IM * cand[veh_name][0] + lane
            if total > best_pos["total_kNm"]:
                best_pos = {
                    "total_kNm": total, "x_m": float(xe), "span_index": k, "vehicle": veh_name,
                    "truck_kNm": cand["truck"][0], "tandem_kNm": cand["tandem"][0],
                    "vehicle_with_IM_kNm": IM * cand[veh_name][0], "lane_kNm": lane,
                    "first_axle_x_m": cand[veh_name][1],
                }

    # ---- momento negativo en apoyos interiores --------------------------------------
    best_neg: dict[str, Any] = {"total_kNm": -1.0}
    gaps = np.linspace(TWO_TRUCK_MIN_GAP_m, max(TWO_TRUCK_MIN_GAP_m, L_total), 16)
    for k in range(1, len(spans)):
        xs = starts[k]
        il = influence_line_continuous(spans, xs, n_points=npts, quantity="M")
        cand = _vehicle_candidates(il, -1.0)
        lane = _lane(il, -1.0)
        veh_name = "truck" if cand["truck"][0] >= cand["tandem"][0] else "tandem"
        single = IM * cand[veh_name][0] + lane
        two_best, two_gap, two_pos = -1.0, 0.0, 0.0
        for g in gaps:
            e, p = _sweep(il, _two_trucks(float(g)), -1.0)
            if e > two_best:
                two_best, two_gap, two_pos = e, float(g), p
        double = TWO_TRUCK_FACTOR * (IM * two_best + lane)
        rule = "0.9·(2 camiones + carril)" if double > single else f"{veh_name} + carril"
        total = max(single, double)
        if total > best_neg["total_kNm"]:
            best_neg = {
                "total_kNm": total, "x_m": float(xs), "support_index": k, "rule": rule,
                "truck_kNm": cand["truck"][0], "tandem_kNm": cand["tandem"][0], "lane_kNm": lane,
                "single_vehicle_total_kNm": single, "two_trucks_kNm": two_best,
                "two_trucks_gap_m": two_gap, "two_trucks_total_kNm": double,
            }

    # ---- cortante --------------------------------------------------------------------
    eps = 1e-3 * min(spans)
    sections: list[tuple[float, str]] = [(eps, "apoyo extremo x=0+")]
    for k in range(1, len(spans)):
        sections.append((starts[k] - eps, f"cara izquierda del apoyo x={starts[k]:.6g}"))
        sections.append((starts[k] + eps, f"cara derecha del apoyo x={starts[k]:.6g}"))
    sections.append((L_total - eps, f"apoyo extremo x={L_total:.6g}-"))
    best_v: dict[str, Any] = {"total_kN": -1.0}
    v_sections: list[dict[str, Any]] = []
    for xe, label in sections:
        il = influence_line_continuous(spans, xe, n_points=npts, quantity="V")
        for sign in (+1.0, -1.0):
            cand = _vehicle_candidates(il, sign)
            lane = _lane(il, sign)
            veh_name = "truck" if cand["truck"][0] >= cand["tandem"][0] else "tandem"
            total = IM * cand[veh_name][0] + lane
            rec = {
                "total_kN": total, "x_m": float(xe), "section": label, "sign": sign, "vehicle": veh_name,
                "truck_kN": cand["truck"][0], "tandem_kN": cand["tandem"][0], "lane_kN": lane,
            }
            v_sections.append(rec)
            if total > best_v["total_kN"]:
                best_v = dict(rec)
    best_v["all_sections"] = v_sections

    # ---- reacciones en apoyos (incl. 90% de 2 camiones en pilas interiores, AASHTO §3.6.1.3.1) ----
    reactions: list[dict[str, Any]] = []
    R_max_kN = -1.0
    R_min_uplift_kN = 0.0
    for sup_idx, xs in enumerate(starts):
        il_r = influence_line_reaction_continuous(spans, sup_idx, n_points=npts)
        cand_pos = _vehicle_candidates(il_r, +1.0)
        lane_pos = _lane(il_r, +1.0)
        veh_pos = "truck" if cand_pos["truck"][0] >= cand_pos["tandem"][0] else "tandem"
        single_r = IM * cand_pos[veh_pos][0] + lane_pos
        is_interior = 0 < sup_idx < len(spans)
        double_r = 0.0
        two_r_best = 0.0
        two_r_gap = 0.0
        if is_interior:
            for g in gaps:
                e, _ = _sweep(il_r, _two_trucks(float(g)), +1.0)
                if e > two_r_best:
                    two_r_best, two_r_gap = e, float(g)
            double_r = TWO_TRUCK_FACTOR * (IM * two_r_best + lane_pos)
        r_max_sup = max(single_r, double_r)
        rule_r = "0.9·(2 camiones + carril)" if (is_interior and double_r > single_r) else f"{veh_pos} + carril"

        # Levantamiento (uplift): reacción negativa máxima
        cand_neg = _vehicle_candidates(il_r, -1.0)
        lane_neg = _lane(il_r, -1.0)
        veh_neg = "truck" if cand_neg["truck"][0] >= cand_neg["tandem"][0] else "tandem"
        r_uplift_mag = IM * cand_neg[veh_neg][0] + lane_neg
        r_min_sup = -r_uplift_mag if r_uplift_mag > 1e-9 else 0.0

        rec_r = {
            "support_index": sup_idx,
            "x_m": float(xs),
            "is_interior": is_interior,
            "R_max_kN": r_max_sup,
            "R_min_kN": r_min_sup,
            "rule": rule_r,
            "single_vehicle_kN": single_r,
            "two_trucks_total_kN": double_r if is_interior else None,
            "two_trucks_gap_m": two_r_gap if is_interior else None,
        }
        reactions.append(rec_r)
        if r_max_sup > R_max_kN:
            R_max_kN = r_max_sup
        if r_min_sup < R_min_uplift_kN:
            R_min_uplift_kN = r_min_sup

    governing = (
        f"M+: {best_pos['vehicle']} + carril en x = {best_pos['x_m']:.2f} m; "
        f"M-: {best_neg['rule']} en apoyo x = {best_neg['x_m']:.2f} m; "
        f"V: {best_v['vehicle']} + carril en {best_v['section']}"
    )
    return MultiSpanResult(
        M_positive_max_kNm=best_pos["total_kNm"],
        M_negative_max_kNm=best_neg["total_kNm"],
        V_max_kN=best_v["total_kN"],
        governing=governing,
        M_positive_x_m=best_pos["x_m"],
        M_negative_x_m=best_neg["x_m"],
        V_x_m=best_v["x_m"],
        R_max_kN=R_max_kN,
        R_min_uplift_kN=R_min_uplift_kN,
        reactions=reactions,
        components={"spans_m": spans, "impact_factor": IM, "lane_kN_per_m": LANE_LOAD_kN_per_m,
                    "M_positive": best_pos, "M_negative": best_neg, "V": best_v, "reactions": reactions},
    )


__all__ = ["MultiSpanInput", "MultiSpanResult", "envelope_multispan", "TWO_TRUCK_MIN_GAP_m", "TWO_TRUCK_FACTOR", "MAX_SPANS"]
