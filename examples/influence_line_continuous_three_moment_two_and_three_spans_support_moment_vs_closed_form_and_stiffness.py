"""Líneas de influencia en vigas continuas por la ecuación de los tres momentos (Clapeyron): dos vanos iguales frente a la forma cerrada −a(L²−a²)/(4L²), tres vanos desiguales 20/30/25 m frente a un solver de rigidez directa, y el defecto de orientación corregido en 1.1.0.

`influence_line_continuous(spans, x_eval, quantity)` resuelve los momentos de apoyo para una carga
unidad en cada punto de la malla (EI constante) y devuelve el momento o el cortante en x_eval.
Hasta 1.0 tomaba la distancia de la carga al apoyo CERCANO del vano en lugar de al LEJANO: la línea
salía reflejada dentro de cada vano (pico en 0,423 L en vez de 0,577 L) y con luces desiguales daba
valores erróneos. La forma cerrada `two_span_continuous_M_at_support` tenía el mismo espejo en el
segundo vano.

Ejecutar:  python examples/influence_line_continuous_three_moment_two_and_three_spans_support_moment_vs_closed_form_and_stiffness.py
"""
import numpy as np

from bridgecalc.loads.influence_lines import (
    influence_line_continuous,
    influence_line_reaction_continuous,
    two_span_continuous_M_at_support,
)


def stiffness_moment(spans, a, x_query, P=1.0):
    """Oráculo independiente: rigidez directa (nodos en apoyos y bajo la carga, EI = 1) + estática."""
    sup = [0.0]
    for s in spans:
        sup.append(sup[-1] + s)
    nodes = sorted(set(sup + [a]))
    n = len(nodes)
    K = np.zeros((2 * n, 2 * n))
    for e in range(n - 1):
        Le = nodes[e + 1] - nodes[e]
        k = (1.0 / Le ** 3) * np.array([[12, 6 * Le, -12, 6 * Le], [6 * Le, 4 * Le ** 2, -6 * Le, 2 * Le ** 2], [-12, -6 * Le, 12, -6 * Le], [6 * Le, 2 * Le ** 2, -6 * Le, 4 * Le ** 2]])
        idx = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        for i, gi in enumerate(idx):
            for j, gj in enumerate(idx):
                K[gi, gj] += k[i, j]
    F = np.zeros(2 * n)
    F[2 * nodes.index(a)] = -P
    fixed = [2 * nodes.index(s) for s in sup]
    free = [d for d in range(2 * n) if d not in fixed]
    u = np.zeros(2 * n)
    u[free] = np.linalg.solve(K[np.ix_(free, free)], F[free])
    R = K @ u - F
    M = sum(R[2 * nodes.index(s)] * (x_query - s) for s in sup if s < x_query - 1e-12)
    if a < x_query - 1e-12:
        M -= P * (x_query - a)
    return float(M)


def main() -> None:
    L = 30.0
    il = influence_line_continuous([L, L], L, n_points=600)
    closed = two_span_continuous_M_at_support(L, L, n_points=len(il.x_m))
    print(f"Dos vanos iguales de {L:.0f} m, LI del momento en el apoyo central (carga unidad en x):")
    print(f"  {'x [m]':>6} {'tres momentos':>13} {'forma cerrada':>13} {'−a(L²−a²)/(4L²)':>16}")
    for x in (5.0, 10.0, 17.32, 20.0, 25.0, 35.0, 40.0, 42.68, 50.0):
        a = x if x <= L else 2 * L - x
        print(f"  {x:6.2f} {np.interp(x, il.x_m, il.ordinates):13.4f} {np.interp(x, closed.x_m, closed.ordinates):13.4f} {-a * (L * L - a * a) / (4 * L * L):16.4f}")
    i1 = int(np.argmin(np.where(il.x_m <= L, il.ordinates, 0)))
    i2 = int(np.argmin(np.where(il.x_m > L, il.ordinates, 0)))
    print(f"  Mínimos: {il.ordinates[i1]:.4f} en x = {il.x_m[i1]:.2f} m y {il.ordinates[i2]:.4f} en x = {il.x_m[i2]:.2f} m → a* = L/√3 = {L / np.sqrt(3):.2f} m desde cada extremo, η* = −L/(6√3) = {-L / (6 * np.sqrt(3)):.4f}")
    print(f"  Diferencia máxima tres momentos − forma cerrada: {np.max(np.abs(il.ordinates - closed.ordinates)):.2e} m\n")

    spans = [20.0, 30.0, 25.0]
    print(f"Tres vanos desiguales {spans} m: LI contra rigidez directa (EI = 1)")
    print(f"  {'M en':>8} {'carga en x':>10} {'tres momentos':>13} {'rigidez':>9} {'versión 1.0':>11}")
    viejo = {(20.0, 8.0): -1.6729, (20.0, 27.0): -1.3280, (20.0, 44.0): -2.3097, (35.0, 27.0): 1.7440, (35.0, 44.0): 1.3747, (50.0, 27.0): -2.2339, (50.0, 44.0): -0.9410}
    for xq in (20.0, 35.0, 50.0):
        ilq = influence_line_continuous(spans, xq, n_points=300)
        for a in (8.0, 27.0, 44.0):
            v = viejo.get((xq, a))
            print(f"  {xq:8.1f} {a:10.1f} {np.interp(a, ilq.x_m, ilq.ordinates):13.4f} {stiffness_moment(spans, a, xq):9.4f} {('%+.4f' % v) if v is not None else '':>11}")
    il_v = influence_line_continuous([L, L], 15.0, n_points=600, quantity="V")
    print(f"\nLI de cortante en x = 15 m de la viga de 2 × 30 m: salto de {np.interp(14.9, il_v.x_m, il_v.ordinates):+.3f} a {np.interp(15.1, il_v.x_m, il_v.ordinates):+.3f}; en el segundo vano es {np.interp(45.0, il_v.x_m, il_v.ordinates):+.4f} (pequeña y del signo del levantamiento)")
    print("\nLa columna «versión 1.0» muestra el espejo: en el apoyo de 20 m, una carga a 27 m (7 m dentro del vano central) daba −1,33 cuando vale −2,51, y una a 44 m daba −2,31 cuando vale −1,11. "
          "El test dorado de la forma cerrada no lo detectaba porque solo comprobaba el valor del mínimo, idéntico en la LI reflejada. EI constante: no vale para cartelas ni cambios de sección.")

    print("\nLI de reacciones (influence_line_reaction_continuous), viga de 2 × 20 m, frente a la forma cerrada:")
    Lr = 20.0
    for sup in (0, 1):
        il_r = influence_line_reaction_continuous([Lr, Lr], sup, n_points=401)
        for a in (5.0, 10.0, 15.0):
            m1 = -a * (Lr ** 2 - a ** 2) / (4 * Lr ** 2)           # momento en la pila, carga unidad a en el vano 1
            exact = (Lr - a) / Lr + m1 / Lr if sup == 0 else a / Lr - 2 * m1 / Lr
            got = float(np.interp(a, il_r.x_m, il_r.ordinates))
            sym = float(np.interp(2 * Lr - a, il_r.x_m, il_r.ordinates)) if sup == 1 else None
            extra = f"; simétrico x = {2 * Lr - a:.0f} m: {sym:.4f}" if sym is not None else ""
            print(f"  R{sup} con P = 1 en x = {a:4.1f} m: {got:.4f} (forma cerrada {exact:.4f}, {got / exact - 1:+.2%}){extra}")


if __name__ == "__main__":
    main()
