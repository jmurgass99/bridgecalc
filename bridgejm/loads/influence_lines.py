"""
Líneas de influencia por Müller-Breslau (1886) — para vigas continuas
de luces desiguales o secciones complejas donde HL93/LM1 fórmulas
cerradas no aplican.

Implementación: liberación de la restricción asociada al esfuerzo
buscado + desplazamiento unitario → la deformada es la línea de
influencia (a escala).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

import numpy as np


@dataclass(frozen=True)
class InfluenceLine:
    x_m: np.ndarray
    ordinates: np.ndarray
    quantity: Literal["M", "V", "R"]
    location_m: float


def simple_beam_M_influence(L: float, x_target_m: float,
                              n_points: int = 200) -> InfluenceLine:
    """Línea de influencia de momento en x_target para viga simple L."""
    x = np.linspace(0, L, n_points)
    eta = np.where(
        x <= x_target_m,
        x * (L - x_target_m) / L,
        x_target_m * (L - x) / L,
    )
    return InfluenceLine(x_m=x, ordinates=eta, quantity="M",
                          location_m=x_target_m)


def simple_beam_V_influence(L: float, x_target_m: float,
                              n_points: int = 200) -> InfluenceLine:
    """Línea de influencia de cortante en x_target."""
    x = np.linspace(0, L, n_points)
    eta = np.where(x < x_target_m, -x / L, (L - x) / L)
    return InfluenceLine(x_m=x, ordinates=eta, quantity="V",
                          location_m=x_target_m)


def two_span_continuous_M_at_support(L1: float, L2: float,
                                       n_points: int = 200) -> InfluenceLine:
    """Línea de influencia de momento sobre apoyo intermedio,
    vigas continuas 2 tramos L1+L2 (Müller-Breslau solución cerrada)."""
    total = L1 + L2
    x = np.linspace(0, total, n_points)
    eta = np.zeros_like(x)
    for i, xi in enumerate(x):
        if xi <= L1:
            a = xi
            b = L1 - a
            # Müller-Breslau: η = -a·b·(L1+a)/(2·L1·(L1+L2))
            eta[i] = -a * b * (L1 + a) / (2 * L1 * total)
        else:
            a = xi - L1
            b = L2 - a
            eta[i] = -a * b * (L2 + a) / (2 * L2 * total)
    return InfluenceLine(x_m=x, ordinates=eta, quantity="M", location_m=L1)


def envelope_from_il(il: InfluenceLine, loads: Sequence[tuple[float, float]],
                      udl_kN_per_m: float = 0.0) -> float:
    """Evalúa el efecto de un tren de cargas puntuales (lista de (pos_m, P_kN))
    + UDL aplicado en las regiones positivas (envelope max).

    Returns el valor máximo absoluto del efecto.
    """
    # Tren puntual
    effect = 0.0
    for pos, P in loads:
        idx = int(np.argmin(np.abs(il.x_m - pos)))
        effect += P * il.ordinates[idx]
    # UDL: aplicar donde la ordenada es del signo del max
    if udl_kN_per_m > 0:
        positive_region = np.maximum(il.ordinates, 0.0)
        negative_region = np.minimum(il.ordinates, 0.0)
        dx = il.x_m[1] - il.x_m[0]
        # Usar la región que aporta a maximizar |efecto|
        if abs(np.sum(positive_region)) > abs(np.sum(negative_region)):
            effect += udl_kN_per_m * np.sum(positive_region) * dx
        else:
            effect += udl_kN_per_m * np.sum(negative_region) * dx
    return float(effect)


def influence_line_continuous(
    spans: Sequence[float],
    x_eval: float,
    n_points: int = 200,
    quantity: Literal["M", "V"] = "M",
) -> InfluenceLine:
    """Linea de influencia de momento positivo en x_eval para viga continua
    de N tramos con luces dadas por ``spans``.

    Metodo: rigidez directa (stiffness method) con viga Euler-Bernoulli,
    EI constante unitario.  Se libera el grado de libertad asociado al
    efecto buscado, se impone un desplazamiento unitario y se resuelve
    la deformada — que por el teorema de Muller-Breslau es la linea de
    influencia (a escala).

    Para simplificar la implementacion sin solver FE completo, se usa
    superposicion de vigas simples + compatibilidad en apoyos internos
    (three-moment equation / Clapeyron).

    Parameters
    ----------
    spans : secuencia de luces [m] (p.ej. [20, 25, 20])
    x_eval : posicion global [m] donde se evalua el efecto
    n_points : puntos por tramo
    quantity : 'M' para momento, 'V' para cortante

    Returns
    -------
    InfluenceLine con x_m sobre toda la viga y ordinates
    """
    n_spans = len(spans)
    total_L = sum(spans)
    if x_eval < 0 or x_eval > total_L:
        raise ValueError(f"x_eval={x_eval} fuera del rango [0, {total_L}]")

    # Crear malla global
    x_global = np.array([], dtype=float)
    span_starts: list[float] = []
    acc = 0.0
    for s in spans:
        span_starts.append(acc)
        x_span = np.linspace(acc, acc + s, n_points, endpoint=False)
        x_global = np.concatenate([x_global, x_span])
        acc += s
    x_global = np.concatenate([x_global, [total_L]])

    # Posiciones de apoyo (incluyendo extremos)
    supports = [0.0]
    acc = 0.0
    for s in spans:
        acc += s
        supports.append(acc)

    # --- Three-moment equation (Clapeyron) para resolver momentos en
    # apoyos internos bajo carga puntual unitaria P=1 en posicion x_P ---
    def _solve_support_moments(x_P: float) -> list[float]:
        """Momentos en los apoyos internos bajo P=1 en x_P."""
        n_int = n_spans - 1  # apoyos internos
        if n_int == 0:
            return [0.0, 0.0]  # simply supported

        # Three-moment eq: L_i*M_{i-1} + 2(L_i+L_{i+1})*M_i + L_{i+1}*M_{i+1}
        #                  = -6*[A_i*a_i/L_i + A_{i+1}*b_{i+1}/L_{i+1}]
        # con A_i*a_i / L_i = contribucion de P=1 en el tramo i
        A = np.zeros((n_int, n_int))
        b_rhs = np.zeros(n_int)

        for k in range(n_int):
            i_left = k      # tramo izquierdo del apoyo k+1
            i_right = k + 1  # tramo derecho
            L_l = spans[i_left]
            L_r = spans[i_right]

            # Diagonal principal
            A[k, k] = 2.0 * (L_l + L_r)
            # Subdiagonales
            if k > 0:
                A[k, k - 1] = L_l
            if k < n_int - 1:
                A[k, k + 1] = L_r

            # RHS: Three-moment equation for P=1
            # For support k (between span i_left and i_right):
            #   RHS = -6 * [A_left * a_bar_left / L_left
            #              + A_right * b_bar_right / L_right]
            # For a point load P=1 at distance 'a' from the left end
            # of a span of length L:
            #   6*A*a_bar/L = P*b*(L^2 - b^2) / L   (contrib to RIGHT support)
            #   6*A*b_bar/L = P*a*(L^2 - a^2) / L   (contrib to LEFT support)
            # where b = L - a.
            #
            # Left span contributes to this support via the RIGHT end:
            #   term = P * b * (L^2 - b^2) / L  with a=x_P-x_start, b=L-a
            # Right span contributes to this support via the LEFT end:
            #   term = P * a * (L^2 - a^2) / L  with a=x_P-x_start_right
            rhs_val = 0.0
            # Tramo izquierdo (load contributes to the right support of this span)
            x_start_l = supports[i_left]
            x_end_l = supports[i_left + 1]
            if x_start_l <= x_P <= x_end_l:
                a_loc = x_P - x_start_l
                b_loc = L_l - a_loc
                rhs_val -= b_loc * (L_l ** 2 - b_loc ** 2) / L_l

            # Tramo derecho (load contributes to the left support of this span)
            x_start_r = supports[i_right]
            x_end_r = supports[i_right + 1]
            if x_start_r <= x_P <= x_end_r:
                a_loc = x_P - x_start_r
                rhs_val -= a_loc * (L_r ** 2 - a_loc ** 2) / L_r

            b_rhs[k] = rhs_val

        if n_int == 1:
            M_int = [b_rhs[0] / A[0, 0]]
        else:
            M_int = np.linalg.solve(A, b_rhs).tolist()

        return [0.0] + M_int + [0.0]

    def _moment_at_x(x_query: float, x_P: float, M_sup: list[float]) -> float:
        """Momento en x_query bajo P=1 en x_P dado M en apoyos."""
        # Encontrar el tramo de x_query
        span_idx = 0
        for i, s in enumerate(spans):
            if x_query <= supports[i + 1] + 1e-12:
                span_idx = i
                break
        else:
            span_idx = n_spans - 1

        x_start = supports[span_idx]
        L_s = spans[span_idx]
        xi = x_query - x_start  # local coordinate

        M_left = M_sup[span_idx]
        M_right = M_sup[span_idx + 1]

        # Moment from support moments (linear interpolation)
        M_support = M_left * (1.0 - xi / L_s) + M_right * (xi / L_s)

        # Simple beam moment from P=1 (only if load is in same span)
        M_simple = 0.0
        if x_start <= x_P <= x_start + L_s:
            a_loc = x_P - x_start
            b_loc = L_s - a_loc
            if xi <= a_loc:
                M_simple = 1.0 * b_loc * xi / L_s
            else:
                M_simple = 1.0 * a_loc * (L_s - xi) / L_s

        return M_support + M_simple

    # Calcular la linea de influencia: para cada posicion de carga x_P
    # calcular el efecto (momento) en x_eval
    ordinates = np.zeros(len(x_global))
    for j, x_P in enumerate(x_global):
        M_sup = _solve_support_moments(x_P)
        if quantity == "M":
            ordinates[j] = _moment_at_x(x_eval, x_P, M_sup)
        else:  # "V"
            # Cortante = dM/dx evaluado por diferencia
            dx = total_L * 1e-5
            x_a = max(x_eval - dx, 0)
            x_b = min(x_eval + dx, total_L)
            M_a = _moment_at_x(x_a, x_P, M_sup)
            M_b = _moment_at_x(x_b, x_P, M_sup)
            ordinates[j] = (M_b - M_a) / (x_b - x_a)

    return InfluenceLine(x_m=x_global, ordinates=ordinates,
                          quantity=quantity, location_m=x_eval)


def critical_position(
    il: InfluenceLine,
    truck_loads: Sequence[tuple[float, float]],
    udl_kN_per_m: float = 0.0,
) -> tuple[float, float]:
    """Encuentra la posicion critica de un tren de carga sobre una linea
    de influencia para maximizar el efecto.

    Parameters
    ----------
    il : linea de influencia
    truck_loads : [(spacing_from_first_axle_m, P_kN), ...]
        El primer eje tiene spacing = 0.  Los demas son distancias
        acumuladas desde el primer eje.
    udl_kN_per_m : carga uniforme adicional

    Returns
    -------
    (position_first_axle, max_effect) — posicion del primer eje que
    maximiza el efecto y el valor del efecto.
    """
    x = il.x_m
    L_total = float(x[-1])
    truck_len = max(s for s, _ in truck_loads) if truck_loads else 0.0

    best_pos = 0.0
    best_effect = -1e30

    # Barrer posiciones del primer eje
    sweep = np.linspace(-truck_len, L_total, max(len(x), 300))
    for pos0 in sweep:
        effect = 0.0
        for spacing, P in truck_loads:
            axle_pos = pos0 + spacing
            if axle_pos < 0 or axle_pos > L_total:
                continue
            idx = int(np.argmin(np.abs(x - axle_pos)))
            effect += P * il.ordinates[idx]

        # UDL: colocar solo en regiones que suman al max efecto
        if udl_kN_per_m > 0:
            positive_region = np.maximum(il.ordinates, 0.0)
            dx = float(x[1] - x[0]) if len(x) > 1 else 1.0
            effect += udl_kN_per_m * float(np.sum(positive_region)) * dx

        if effect > best_effect:
            best_effect = effect
            best_pos = pos0

    return float(best_pos), float(best_effect)


__all__ = [
    "InfluenceLine",
    "simple_beam_M_influence", "simple_beam_V_influence",
    "two_span_continuous_M_at_support",
    "envelope_from_il",
    "influence_line_continuous",
    "critical_position",
]
