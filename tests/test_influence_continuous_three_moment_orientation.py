"""La ecuación de los tres momentos usa la distancia de la carga al apoyo LEJANO del tramo.

Hasta la versión 1.0 ``influence_line_continuous`` intercambiaba a y b: la línea de influencia
salía reflejada dentro de cada vano (pico en 0,423 L en vez de 0,577 L) y con luces desiguales
daba valores erróneos. Oráculos independientes: la forma cerrada de dos vanos
(``two_span_continuous_M_at_support``, derivada aparte) y un solver de rigidez directa.
"""
import numpy as np
import pytest

from bridgecalc.loads.influence_lines import influence_line_continuous, two_span_continuous_M_at_support


def _stiffness_moment(spans, a, x_query, P=1.0):
    """Momento en x_query por una carga P en a (viga continua, EI = 1), por rigidez directa + estática."""
    sup = [0.0]
    for s in spans:
        sup.append(sup[-1] + s)
    nodes = sorted(set(sup + [a]))
    n = len(nodes)
    K = np.zeros((2 * n, 2 * n))
    for e in range(n - 1):
        Le = nodes[e + 1] - nodes[e]
        k = (1.0 / Le ** 3) * np.array([
            [12, 6 * Le, -12, 6 * Le],
            [6 * Le, 4 * Le * Le, -6 * Le, 2 * Le * Le],
            [-12, -6 * Le, 12, -6 * Le],
            [6 * Le, 2 * Le * Le, -6 * Le, 4 * Le * Le],
        ])
        idx = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        for i_, gi in enumerate(idx):
            for j_, gj in enumerate(idx):
                K[gi, gj] += k[i_, j_]
    F = np.zeros(2 * n)
    F[2 * nodes.index(a)] = -P
    fixed = [2 * nodes.index(s) for s in sup]
    free = [d for d in range(2 * n) if d not in fixed]
    u = np.zeros(2 * n)
    u[free] = np.linalg.solve(K[np.ix_(free, free)], F[free])
    R = K @ u - F
    M = 0.0
    for s in sup:
        if s < x_query - 1e-12:
            M += R[2 * nodes.index(s)] * (x_query - s)
    if a < x_query - 1e-12:
        M -= P * (x_query - a)
    return float(M)


@pytest.mark.parametrize("L", [20.0, 30.0])
def test_dos_vanos_iguales_pico_en_0577L_desde_el_extremo(L):
    il = influence_line_continuous([L, L], L, n_points=300)
    for a in (0.25 * L, L / 3.0, 0.5 * L, 2.0 * L / 3.0):
        i = int(np.argmin(np.abs(il.x_m - a)))
        assert il.ordinates[i] == pytest.approx(-a * (L * L - a * a) / (4 * L * L), rel=1e-6)
    x_min = il.x_m[int(np.argmin(il.ordinates))]
    assert x_min == pytest.approx(L / np.sqrt(3.0), abs=L / 150.0)


@pytest.mark.parametrize("L", [20.0, 30.0])
def test_forma_cerrada_dos_vanos_iguales_picos_simetricos_respecto_al_apoyo(L):
    # Hasta la versión 1.0 el segundo vano de la forma cerrada estaba reflejado (pico en 1.577 L)
    il = two_span_continuous_M_at_support(L, L, n_points=1201)
    s1 = il.ordinates[il.x_m <= L]
    s2 = il.ordinates[il.x_m >= L]
    x1 = il.x_m[il.x_m <= L][int(np.argmin(s1))]
    x2 = il.x_m[il.x_m >= L][int(np.argmin(s2))]
    assert x1 == pytest.approx(L / np.sqrt(3.0), abs=L / 300.0)
    assert x2 == pytest.approx(2.0 * L - L / np.sqrt(3.0), abs=L / 300.0)
    assert np.min(s1) == pytest.approx(np.min(s2), rel=1e-6)
    # pointwise con el solver de tres momentos
    il_solver = influence_line_continuous([L, L], L, n_points=600)
    assert np.max(np.abs(il_solver.ordinates - np.interp(il_solver.x_m, il.x_m, il.ordinates))) < 2e-4 * L


def _eta_support_two_spans(x, L1, L2):
    # Tres momentos con M_A = M_C = 0: 2(L1+L2) M_B = -P a (L1^2 - a^2)/L1 (carga en vano 1, a desde A)
    # y = -P c (L2^2 - c^2)/L2 (carga en vano 2, c desde C).
    x = np.asarray(x, dtype=float)
    a = np.where(x <= L1, x, 0.0)
    c = np.where(x > L1, L1 + L2 - x, 0.0)
    return np.where(x <= L1, -a * (L1 ** 2 - a ** 2) / (2 * L1 * (L1 + L2)), -c * (L2 ** 2 - c ** 2) / (2 * L2 * (L1 + L2)))


def test_dos_vanos_desiguales_coincide_con_la_forma_cerrada_punto_a_punto():
    L1, L2 = 30.0, 15.0
    il = influence_line_continuous([L1, L2], L1, n_points=300)
    assert np.max(np.abs(il.ordinates - _eta_support_two_spans(il.x_m, L1, L2))) < 1e-9 * L1
    closed = two_span_continuous_M_at_support(L1, L2, n_points=601)
    assert np.max(np.abs(closed.ordinates - _eta_support_two_spans(closed.x_m, L1, L2))) < 1e-9 * L1
    assert il.x_m[int(np.argmin(il.ordinates))] == pytest.approx(L1 / np.sqrt(3.0), abs=0.2)
    # en el vano corto el minimo esta a L2/sqrt(3) del extremo derecho C
    mask2 = closed.x_m > L1
    x2 = closed.x_m[mask2][int(np.argmin(closed.ordinates[mask2]))]
    assert x2 == pytest.approx(L1 + L2 - L2 / np.sqrt(3.0), abs=0.1)


@pytest.mark.parametrize("x_eval", [20.0, 35.0, 50.0, 62.0])
def test_tres_vanos_desiguales_contra_rigidez_directa(x_eval):
    spans = [20.0, 30.0, 25.0]
    il = influence_line_continuous(spans, x_eval, n_points=250)
    for a in (8.0, 14.0, 27.0, 44.0, 55.0, 62.0, 70.0):
        eta = float(np.interp(a, il.x_m, il.ordinates))
        assert eta == pytest.approx(_stiffness_moment(spans, a, x_eval), abs=2e-3)
