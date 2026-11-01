"""Envolvente HL-93 (AASHTO LRFD §3.6.1.2) en vigas simplemente apoyadas de 6 a 60 m: camión frente a tándem, luz de cruce, carril y comprobación a mano por el teorema de Barré en 30 m.

`hl93_envelope(L)` barre el camión (35/145/145 kN a 4,27 m) y el tándem (2 × 110 kN a 1,20 m), aplica
IM = 33 % solo al vehículo y suma el carril de 9,34 kN/m: M = máx(camión, tándem)·1,33 + w·L²/8. Se
tabulan diez luces, se localiza la luz en la que el camión supera al tándem y se recalcula a mano el
camión en 30 m con la posición de Barré (eje central y resultante equidistantes del centro).

Ejecutar:  python examples/hl93_envelope_simple_spans_6_to_60_m_truck_vs_tandem_crossover_and_barre_hand_check_30_m.py
"""
from bridgecalc.loads.hl93 import LANE_LOAD_kN_per_m, TRUCK_AXLE_SPACINGS_m, TRUCK_AXLES_kN, hl93_envelope


def main() -> None:
    print("Envolvente HL-93 por carril de diseño, IM = 1,33 solo sobre el vehículo, carril 9,34 kN/m sin IM")
    print(f"  {'L [m]':>5} {'M_camión':>9} {'M_tándem':>9} {'gobierna':>8} {'M_carril':>9} {'M_máx [kN·m]':>13} {'V_máx [kN]':>10}")
    for L in (6.0, 8.0, 10.0, 12.0, 15.0, 20.0, 30.0, 40.0, 50.0, 60.0):
        e = hl93_envelope(L)
        print(f"  {L:5.0f} {e['M_truck_kNm']:9.0f} {e['M_tandem_kNm']:9.0f} {e['governing_vehicle']:>8} {e['M_lane_kNm']:9.0f} {e['M_max_kNm']:13.0f} {e['V_max_kN']:10.1f}")
    cruce = None
    L = 8.0
    while L <= 20.0 and cruce is None:
        e = hl93_envelope(L)
        if e["M_truck_kNm"] >= e["M_tandem_kNm"]:
            cruce = L
        L += 0.25
    print(f"\nEl camión pasa a gobernar el momento a partir de L ≈ {cruce:.2f} m; por debajo manda el tándem (220 kN en 1,2 m).")

    L = 30.0
    P = TRUCK_AXLES_kN
    s1, s2 = TRUCK_AXLE_SPACINGS_m
    R = sum(P)
    x_R = (P[1] * s1 + P[2] * (s1 + s2)) / R          # resultante medida desde el eje delantero
    d = x_R - s1                                       # distancia resultante–eje central
    x_c = L / 2 - d / 2                                # eje central a d/2 del centro, resultante al otro lado
    R_A = R * (L - (x_c + d)) / L
    M_barre = R_A * x_c - P[0] * s1
    e30 = hl93_envelope(L)
    print(f"\nComprobación a mano en L = 30 m (Barré): resultante {R:.0f} kN a {x_R:.3f} m del eje delantero, {d:.3f} m detrás del eje central;")
    print(f"  eje central en x = {x_c:.4f} m, R_A = {R_A:.2f} kN → M = R_A·x − 35·4,27 = {M_barre:.1f} kN·m; barrido numérico de hl93_envelope: {e30['M_truck_kNm']:.1f} kN·m ({(e30['M_truck_kNm'] / M_barre - 1) * 100:+.2f} %)")
    V_mano = P[2] + P[1] * (L - s2) / L + P[0] * (L - s1 - s2) / L
    print(f"  Cortante con los ejes pesados sobre el apoyo: 145 + 145·(30−4,27)/30 + 35·(30−8,54)/30 = {V_mano:.1f} kN; "
          f"V_máx = {V_mano:.1f}·1,33 + {LANE_LOAD_kN_per_m}·30/2 = {V_mano * 1.33 + LANE_LOAD_kN_per_m * L / 2:.1f} kN (función: {e30['V_max_kN']:.1f})")
    print("\nEl barrido usa 60 posiciones del eje delantero y 200 secciones: queda ≈ 0,1 % por debajo del máximo exacto de Barré, del lado inseguro pero dentro del redondeo de diseño. "
          "Son solicitaciones por carril: multiplica por el factor de distribución (ejemplo distribution_factors_*) y el de presencia múltiple antes de comprobar una viga.")


if __name__ == "__main__":
    main()
