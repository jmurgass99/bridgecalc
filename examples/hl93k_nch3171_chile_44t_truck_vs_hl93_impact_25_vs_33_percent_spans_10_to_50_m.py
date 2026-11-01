"""Camión chileno de 44 t (62/185/185 kN a 4,0 m, IM = 25 %) frente al HL-93 de AASHTO en luces de 10 a 50 m.

`hl93k_nch_envelope` barre el camión chileno y suma el carril de 9,34 kN/m con IM = 1,25, con los
valores que define el módulo (atribuidos al Manual de Carreteras del MOP, Vol. 3; sin contrastar aquí;
el «nch» del nombre es histórico: NCh 3171 es la norma chilena de combinaciones de carga). Se compara
con `hl93_envelope` (IM = 1,33, máx(camión, tándem)) en momento y cortante, y se separa cuánto del
cociente viene del peso bruto (432 frente a 325 kN) y cuánto del incremento dinámico.

Ejecutar:  python examples/hl93k_nch3171_chile_44t_truck_vs_hl93_impact_25_vs_33_percent_spans_10_to_50_m.py
"""
from bridgecalc.loads.hl93 import (
    NCH_IMPACT_FACTOR,
    NCH_TRUCK_AXLE_SPACINGS_m,
    NCH_TRUCK_AXLES_kN,
    TRUCK_AXLES_kN,
    HL93KNChConfiguration,
    hl93_envelope,
    hl93k_nch_envelope,
)


def main() -> None:
    print(f"Camión chileno 44 t: ejes {NCH_TRUCK_AXLES_kN} kN a {NCH_TRUCK_AXLE_SPACINGS_m} m, peso bruto {sum(NCH_TRUCK_AXLES_kN):.0f} kN, IM = {NCH_IMPACT_FACTOR}")
    print(f"Camión HL-93:    ejes {TRUCK_AXLES_kN} kN a (4.27, 4.27) m, peso bruto {sum(TRUCK_AXLES_kN):.0f} kN, IM = 1.33; tándem 2 × 110 kN\n")
    print(f"  {'L [m]':>5} {'M Chile':>8} {'M HL-93':>8} {'cociente':>8} {'V Chile':>7} {'V HL-93':>7} {'cociente':>8}  gobierna HL-93")
    for L in (10.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0):
        n = hl93k_nch_envelope(HL93KNChConfiguration(span_m=L))
        h = hl93_envelope(L)
        print(f"  {L:5.0f} {n.M_max_kNm:8.0f} {h['M_max_kNm']:8.0f} {n.M_max_kNm / h['M_max_kNm']:8.3f} {n.V_max_kN:7.1f} {h['V_max_kN']:7.1f} {n.V_max_kN / h['V_max_kN']:8.3f}  {h['governing_vehicle']}")
    L = 30.0
    n = hl93k_nch_envelope(HL93KNChConfiguration(span_m=L))
    n_sin = hl93k_nch_envelope(HL93KNChConfiguration(span_m=L, impact_factor=1.0))
    h = hl93_envelope(L)
    lane = 9.34 * L * L / 8
    print(f"\nL = 30 m, desglose del momento: camión chileno sin IM {n_sin.M_max_kNm - lane:.0f} kN·m frente a HL-93 camión {h['M_truck_kNm']:.0f} kN·m "
          f"(peso bruto ×{sum(NCH_TRUCK_AXLES_kN) / sum(TRUCK_AXLES_kN):.3f}, separación 4,0 frente a 4,27 m); con IM: {n.M_max_kNm - lane:.0f} frente a {h['M_truck_kNm'] * 1.33:.0f} kN·m; carril común {lane:.0f} kN·m.")
    print(f"  Cociente total {n.M_max_kNm / h['M_max_kNm']:.3f}: el camión chileno pesa un 33 % más pero su IM es menor, y el carril idéntico diluye la diferencia.")
    print("\nLa implementación chilena no incluye tándem ni regla de dos camiones; en luces cortas el tándem del HL-93 acorta la diferencia (cociente 1,135 en 10 m frente a 1,19–1,21 entre 15 y 25 m). Las solicitaciones son por carril, sin factor de distribución.")


if __name__ == "__main__":
    main()
