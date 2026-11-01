"""IAP-11 (España): división en carriles virtuales de la Tabla 4.1 para calzadas de 4,5 a 12 m, envolvente MC1 (tándem + sobrecarga repartida con área remanente) y MC2 (eje de 400 kN) en 20, 30 y 40 m, y comparación con EN 1991-2.

`iap11_lane_layout` aplica las tres reglas de la tabla (w < 5,4 → 1 carril de 3 m; 5,4 ≤ w < 6 → 2 de
w/2; w ≥ 6 → ⌊w/3⌋ de 3 m más área remanente). `evaluate_iap11_traffic_loads` suma tándem de Barré y
carga repartida carril a carril incluyendo los 2,5 kN/m² del área remanente, y mayora con γ_Q = 1,35
(ELU, tráfico). Anclaje: ficha W01630 (IAP-11 Cap. 4): 300/200/100 kN y 9,0/2,5/2,5 kN/m².

Ejecutar:  python examples/iap11_spain_lane_layout_table_4_1_and_mc1_mc2_envelope_vs_en1991_2_widths_4_5_to_12_m.py
"""
from bridgecalc.loads.eurocode_lm1 import EurocodeLM1Input, evaluate_eurocode_lm1
from bridgecalc.loads.iap11 import (
    IAP11_GAMMA_Q_ELU,
    IAP11_PSI_0,
    IAP11_TS_AXLES_kN,
    IAP11_UDL_kN_m2,
    evaluate_iap11_traffic_loads,
    iap11_lane_layout,
    tandem_bending_moment_barre,
    tandem_shear_force_support,
)


def main() -> None:
    print(f"Tándem por carril {IAP11_TS_AXLES_kN} kN/eje, sobrecarga {IAP11_UDL_kN_m2} kN/m², área remanente 2,5 kN/m²; γ_Q ELU = {IAP11_GAMMA_Q_ELU}, ψ0 = {IAP11_PSI_0}\n")
    print("Carriles virtuales (IAP-11 Tabla 4.1):")
    print(f"  {'calzada w [m]':>13} {'carriles':>8} {'anchos [m]':>18} {'remanente [m]':>13}")
    for w in (4.5, 5.0, 5.4, 5.7, 6.0, 7.0, 9.5, 10.5, 12.0):
        lay = iap11_lane_layout(w)
        print(f"  {w:13.1f} {lay.n_lanes:8d} {str(list(lay.lane_widths_m)):>18} {lay.remaining_width_m:13.2f}")
    W = 10.5
    print(f"\nEnvolvente MC1/MC2 para calzada de {W} m (3 carriles + 1,5 m remanente):")
    print(f"  {'L [m]':>5} {'M_TS':>7} {'M_UDL':>7} {'M_MC1 car.':>10} {'M_MC1 ELU':>9} {'V_MC1 car.':>10} {'V ELU':>7} {'M_MC2 local':>11} {'EN 1991-2 M':>11} {'Δ':>6}")
    for L in (20.0, 30.0, 40.0):
        r = evaluate_iap11_traffic_loads(L, W)
        ec = evaluate_eurocode_lm1(EurocodeLM1Input(carriageway_width_m=W, span_m=L))
        print(f"  {L:5.0f} {r.M_TS_kNm:7.0f} {r.M_UDL_kNm:7.0f} {r.M_MC1_total_characteristic_kNm:10.0f} {r.M_MC1_design_ELU_kNm:9.0f} {r.V_MC1_total_characteristic_kN:10.0f} {r.V_MC1_design_ELU_kN:7.0f} {r.M_MC2_characteristic_kNm:11.0f} {ec.M_total_kNm:11.0f} {(r.M_MC1_total_characteristic_kNm / ec.M_total_kNm - 1) * 100:+5.1f}%")
    r30 = evaluate_iap11_traffic_loads(30.0, W)
    print(f"\n  La diferencia con evaluate_eurocode_lm1 es exactamente el área remanente: 2,5 kN/m² × 1,5 m = 3,75 kN/m → {3.75 * 30 ** 2 / 8:.0f} kN·m en 30 m (M_UDL {r30.M_UDL_kNm:.0f} frente a {evaluate_eurocode_lm1(EurocodeLM1Input(carriageway_width_m=W, span_m=30.0)).M_UDL_kNm:.0f}).")
    print(f"\nTándem de Barré por carril en L = 30 m: " + ", ".join(f"{P:.0f} kN → M {tandem_bending_moment_barre(P, 30.0):.0f} kN·m, V {tandem_shear_force_support(P, 30.0):.0f} kN" for P in IAP11_TS_AXLES_kN))
    print(f"Luz corta: en L = 1,5 m (< 2,05 m) manda un solo eje centrado: M = {tandem_bending_moment_barre(300.0, 1.5):.1f} kN·m = 300·1,5/4")
    print(f"\nMC2 en el modelo (L local = luz del vano) es solo orientativo: la comprobación local real usa la luz entre vigas o nervios, no la del tablero. "
          f"El módulo publica un solo ψ0 = {IAP11_PSI_0} (el del tándem); la sobrecarga repartida tiene otro menor en IAP-11, así que para combinar por separado ponlo a mano. El valor de dimensionamiento longitudinal es el MC1.")


if __name__ == "__main__":
    main()
