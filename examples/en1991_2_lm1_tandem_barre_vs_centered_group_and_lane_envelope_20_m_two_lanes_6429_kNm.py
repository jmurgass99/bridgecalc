"""Modelo de carga LM1 de EN 1991-2 §4.3.2 en una viga biapoyada de 20 m con dos carriles: tándem por el teorema de Barré (2822,7 kN·m) frente a la fórmula «grupo centrado» (2904,6) y a la antigua de carga repartida (1498,7), más la envolvente completa (6429,5 kN·m, 1315 kN).

`ec1_traffic.traffic_envelope_lm1` suma por carril la carga repartida (9,0 y 2,5 kN/m² × 3 m) y el
tándem (2 × 300 y 2 × 200 kN a 1,2 m) colocado en la posición de Barré: eje crítico a d/4 = 0,30 m del
centro. `eurocode_lm1.evaluate_eurocode_lm1` hace lo mismo a partir del ancho de calzada, y el módulo
legado `loads.eurocode.evaluate_lm1` delega en él desde 1.1.0 (antes daba el tándem a la mitad).

Ejecutar:  python examples/en1991_2_lm1_tandem_barre_vs_centered_group_and_lane_envelope_20_m_two_lanes_6429_kNm.py
"""
import warnings

from bridgecalc.ec1_traffic import LM1, traffic_envelope_lm1
from bridgecalc.loads.eurocode import LM1Input, evaluate_lm1
from bridgecalc.loads.eurocode_lm1 import EurocodeLM1Input, evaluate_eurocode_lm1
from bridgecalc.loads.iap11 import tandem_bending_moment_barre


def main() -> None:
    L, d = 20.0, 1.2
    print(f"Viga biapoyada L = {L:.0f} m, dos carriles nocionales de 3,0 m (EN 1991-2 Tabla 4.2):")
    for lane in LM1(n_lanes=2).lane_loads():
        print(f"  carril {lane['lane']}: tándem 2 × {lane['Qik_kN']:.0f} kN, carga repartida {lane['qik_kPa']} kN/m² → {lane['qik_kPa'] * 3.0:.1f} kN/m")
    print("\nMomento máximo de un tándem de dos ejes Q a 1,2 m (carril 1, Q = 300 kN):")
    x_c = L / 2 - d / 4
    R_L = 300.0 * ((L - x_c) + (L - x_c - d)) / L
    print(f"  Barré: eje crítico en x = L/2 − d/4 = {x_c:.2f} m, R_izq = {R_L:.1f} kN → M = {R_L * x_c:.1f} kN·m (función: {tandem_bending_moment_barre(300.0, L):.1f})")
    M_grupo = 300.0 * (L / 2 - d / 2) * (L / 2 + d / 2) / L + 300.0 * (L / 2 - d / 2) * (L / 2) / L
    print(f"  «grupo centrado» sumando dos secciones distintas (9,4 y 10,0 m): {M_grupo:.1f} kN·m, +{(M_grupo / (R_L * x_c) - 1) * 100:.2f} % sobre un máximo físicamente inalcanzable")
    M_viejo = 2 * 300.0 * L / 8 * (1 - (0.6 / L) ** 2)
    print(f"  fórmula de carga repartida 2QL/8·(1 − (0,6/L)²) usada por loads.eurocode hasta 1.0: {M_viejo:.1f} kN·m, {(M_viejo / (R_L * x_c) - 1) * 100:+.1f} % (la mitad, del lado inseguro)")
    M, V = traffic_envelope_lm1(L_span=L, n_lanes=2)
    print(f"\nEnvolvente LM1 dos carriles: carga repartida 34,5 kN/m → M {34.5 * L * L / 8:.1f} kN·m, V {34.5 * L / 2:.1f} kN; tándems {R_L * x_c:.1f} + {tandem_bending_moment_barre(200.0, L):.1f} kN·m, V {300 + 300 * (L - d) / L:.0f} + {200 + 200 * (L - d) / L:.0f} kN")
    print(f"  M_máx = {M:.1f} kN·m, V_máx = {V:.1f} kN")
    r = evaluate_eurocode_lm1(EurocodeLM1Input(carriageway_width_m=7.0, span_m=L))
    print(f"\nevaluate_eurocode_lm1 (calzada 7,0 m → {r.n_lanes} carriles): M_TS {r.M_TS_kNm:.1f}, M_UDL {r.M_UDL_kNm:.1f}, total {r.M_total_kNm:.1f} kN·m; V {r.V_total_kN:.1f} kN; carga total de tándems {r.total_TS_load_kN:.0f} kN")
    print(f"  Mismo cortante que traffic_envelope_lm1 ({V:.0f} kN): un eje sobre el apoyo y el otro a 1,2 m, V_TS = {r.V_TS_kN:.0f} kN. "
          f"Hasta 1.0 evaluate_eurocode_lm1 ponía los dos ejes a la vez sobre el apoyo (2Q = 1000 kN, total 1345 kN).")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        old = evaluate_lm1(LM1Input(carriageway_width_m=7.0, span_m=L))
    print(f"loads.eurocode.evaluate_lm1 (legado): M_total {old.M_total_kNm:.1f} kN·m, idéntico; emite {w[0].category.__name__}: «{str(w[0].message)[:60]}…»")
    print("\nAnchos de calzada y número de carriles que toma evaluate_eurocode_lm1 (tope de 3, sin área remanente):")
    for W in (5.0, 6.0, 7.0, 9.0, 10.5, 12.0):
        r = evaluate_eurocode_lm1(EurocodeLM1Input(carriageway_width_m=W, span_m=L))
        print(f"  w = {W:4.1f} m → {r.n_lanes} carriles, M_total {r.M_total_kNm:7.1f} kN·m, carga repartida {r.total_UDL_load_kN_per_m:.1f} kN/m")
    print("\nEl área remanente (2,5 kN/m² fuera de los carriles) no entra en evaluate_eurocode_lm1: para calzadas que no son múltiplo de 3 m usa evaluate_iap11_traffic_loads, que la reparte. "
          "Los valores son característicos y por tablero completo, sin α nacionales (α = 1) ni reparto transversal entre vigas.")


if __name__ == "__main__":
    main()
