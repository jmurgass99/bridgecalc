"""Factores de distribución de carga viva AASHTO LRFD §4.6.2.2 para tablero de losa sobre vigas (tipos a/k): viga interior y exterior, momento y cortante, uno y varios carriles, con la regla de la palanca.

Las fórmulas del LRFD son empíricas en pies y pulgadas y así las toma `distribution_factors`:
S separación de vigas [ft], L luz [ft], ts losa [in], Kg = n·(I + A·e_g²) [in⁴], d_e voladizo [ft].
Se calcula un puente de 100 ft con vigas metálicas compuestas a 8 ft, se barre la separación y se
aplica el factor al momento HL-93 por carril para obtener el momento por viga.

Ejecutar:  python examples/distribution_factors_aashto_4_6_2_2_interior_exterior_girders_lever_rule_imperial_inputs.py
"""
from bridgecalc.loads.distribution_factors import GirderGeometry, distribution_factors, exterior_e_factor, lever_rule_exterior
from bridgecalc.loads.hl93 import hl93_envelope

FT = 0.3048


def main() -> None:
    n, I_in4, A_in2, eg_in = 8.0, 14_900.0, 58.8, 48.0        # W40x199 compuesta, n = E_s/E_c ≈ 8
    Kg = n * (I_in4 + A_in2 * eg_in ** 2)
    g = GirderGeometry(S_ft=8.0, L_ft=100.0, ts_in=8.0, Kg_in4=Kg, de_ft=2.5)
    df = distribution_factors(g)
    print(f"Viga W40x199 compuesta: Kg = n·(I + A·e_g²) = {n:.0f}·({I_in4:,.0f} + {A_in2}·{eg_in}²) = {Kg:,.0f} in⁴; S = {g.S_ft} ft, L = {g.L_ft} ft, t_s = {g.ts_in} in, d_e = {g.de_ft} ft\n")
    print(f"  {'factor':34} {'1 carril':>9} {'2+ carriles':>11} {'de diseño':>9}")
    print(f"  {'momento, viga interior (Tabla 4.6.2.2.2b-1)':34} {df.gm_interior_1:9.3f} {df.gm_interior_2:11.3f} {df.gm_interior:9.3f}")
    print(f"  {'cortante, viga interior (Tabla 4.6.2.2.3a-1)':34} {df.gv_interior_1:9.3f} {df.gv_interior_2:11.3f} {df.gv_interior:9.3f}")
    print(f"  {'momento, viga exterior':34} {lever_rule_exterior(g.S_ft, g.de_ft):9.3f} {exterior_e_factor(g.de_ft) * df.gm_interior_2:11.3f} {df.gm_exterior:9.3f}")
    print(f"  {'cortante, viga exterior':34} {lever_rule_exterior(g.S_ft, g.de_ft):9.3f} {exterior_e_factor(g.de_ft) * df.gv_interior_2:11.3f} {df.gv_exterior:9.3f}")
    print(f"  (exterior: regla de la palanca con m = 1,20 para un carril; e = 0,77 + d_e/9,1 = {exterior_e_factor(g.de_ft):.3f} para dos o más)\n")

    e = hl93_envelope(g.L_ft * FT)
    print(f"Momento HL-93 por carril en L = {g.L_ft * FT:.2f} m: {e['M_max_kNm']:.0f} kN·m → por viga interior {df.gm_interior * e['M_max_kNm']:.0f} kN·m, exterior {df.gm_exterior * e['M_max_kNm']:.0f} kN·m")
    print(f"Cortante HL-93 por carril: {e['V_max_kN']:.1f} kN → viga interior {df.gv_interior * e['V_max_kN']:.1f} kN, exterior {df.gv_exterior * e['V_max_kN']:.1f} kN\n")

    print(f"Barrido de la separación S (L = 100 ft, t_s = 8 in, mismo Kg):")
    print(f"  {'S [ft]':>6} {'S [m]':>5} {'g_M int':>8} {'g_V int':>8} {'g_M ext':>8} {'M por viga int [kN·m]':>21}")
    for S in (6.0, 7.0, 8.0, 9.0, 10.0, 12.0):
        d = distribution_factors(GirderGeometry(S_ft=S, L_ft=100.0, ts_in=8.0, Kg_in4=Kg, de_ft=2.5))
        print(f"  {S:6.1f} {S * FT:5.2f} {d.gm_interior:8.3f} {d.gv_interior:8.3f} {d.gm_exterior:8.3f} {d.gm_interior * e['M_max_kNm']:21.0f}")
    print("\nMás separación → más carga por viga, casi linealmente en cortante (0,2 + S/12 − (S/35)²) y con exponente 0,6 en momento. "
          "Rango de validez §4.6.2.2.2b: 3,5 ≤ S ≤ 16 ft, 4,5 ≤ t_s ≤ 12 in, 20 ≤ L ≤ 240 ft, 4 vigas o más; fuera de él la función no avisa.")


if __name__ == "__main__":
    main()
