"""LM2 (eje aislado de 400 kN, EN 1991-2 §4.3.3) para comprobaciones locales de losa y LM3 (vehículos especiales «SV120» y «SV196» del catálogo del módulo, no normativos) frente al LM1 de un carril en luces de 10 a 40 m, con el IRC Class A indio y el HS20 de referencia.

`evaluate_eurocode_lm2` coloca el eje β_Q·400 kN en el centro (M = Q·L/4) y en el apoyo (V = Q).
`lm3_special.max_moment_simple_span` recorre el convoy y evalúa el momento en el centro de la luz con
la línea de influencia exacta; `impact_factor` da el DAF por código. Se compara con el tándem + carga
repartida de un carril de LM1 (`traffic_envelope_lm1`).

Ejecutar:  python examples/en1991_2_lm2_single_axle_400_kN_and_lm3_special_vehicles_sv120_sv196_vs_lm1_spans_10_to_40_m.py
"""
from bridgecalc.ec1_traffic import traffic_envelope_lm1
from bridgecalc.loads.eurocode_lm1 import LM2_WHEEL_CONTACT_m, LM2_WHEEL_SPACING_m, EurocodeLM2Input, evaluate_eurocode_lm2
from bridgecalc.loads.lm3_special import AASHTO_HS20, AS_SM1600, EUROCODE_SV120, EUROCODE_SV196, IRC_CLASS_A, impact_factor, max_moment_simple_span


def main() -> None:
    print(f"LM2: eje de 400 kN = 2 ruedas de 200 kN a {LM2_WHEEL_SPACING_m} m, huella {LM2_WHEEL_CONTACT_m[0]} × {LM2_WHEEL_CONTACT_m[1]} m; comprobación local de losa entre vigas:")
    print(f"  {'luz local [m]':>13} {'β_Q':>4} {'M = Q·L/4 [kN·m]':>16} {'V = Q [kN]':>10}")
    for Ll, beta in ((2.0, 1.0), (3.0, 1.0), (4.0, 1.0), (4.0, 0.8), (6.0, 1.0)):
        r = evaluate_eurocode_lm2(EurocodeLM2Input(span_m=Ll, beta_Q=beta))
        print(f"  {Ll:13.1f} {beta:4.1f} {r.M_max_kNm:16.1f} {r.V_max_kN:10.0f}")
    print("\nLM3 — vehículos especiales (un carril, sin carga repartida acompañante) frente a LM1 de un carril:")
    vehs = [EUROCODE_SV120, EUROCODE_SV196, IRC_CLASS_A, AASHTO_HS20]
    for v in vehs:
        print(f"  {v.name:12} {len(v.axle_loads_kN):2d} ejes, {v.total_load_kN:6.0f} kN ({v.total_load_kN / 9.81:5.0f} t), longitud {v.length_m:5.2f} m, DAF {impact_factor(v.code, 20.0):.2f} ({v.code})")
    print("  Ojo: «SV196» suma 2400 kN ≈ 245 t y «SV120» 1440 kN ≈ 147 t; los nombres evocan los vehículos SV del anejo nacional británico, pero los ejes no los reproducen, "
          "y el Anexo A de EN 1991-2 define otra serie (600/150, 900/150…). Tómalos como convoyes de ejemplo.")
    print(f"\n  {'L [m]':>5} " + " ".join(f"{v.name:>12}" for v in vehs) + f" {'LM1 1 carril':>12}")
    for L in (10.0, 15.0, 20.0, 30.0, 40.0):
        Ms = [max_moment_simple_span(v, L)["M_max_kNm"] for v in vehs]
        M1, _ = traffic_envelope_lm1(L_span=L, n_lanes=1)
        print(f"  {L:5.0f} " + " ".join(f"{m:12.0f}" for m in Ms) + f" {M1:12.0f}")
    r = max_moment_simple_span(EUROCODE_SV196, 30.0)
    print(f"\nSV196 en 30 m: M = {r['M_max_kNm']:.0f} kN·m con el eje delantero en x = {r['x_front_critical_m']:.2f} m ({r['total_load_kN']:.0f} kN sobre {EUROCODE_SV196.length_m:.1f} m)")
    print(f"IRC Class A: DAF = 1 + 4,5/(6 + L) → {impact_factor('INDIA', 10.0):.3f} en 10 m, {impact_factor('INDIA', 40.0):.3f} en 40 m (tope 1,25)")
    print(f"\nAS_SM1600 del catálogo: {AS_SM1600.axle_loads_kN} kN a {AS_SM1600.axle_spacings_m} m = {AS_SM1600.total_load_kN:.0f} kN: NO es el M1600/S1600 de AS 5100.2 ni el antiguo T44 de 440 kN; tratarlo como un vehículo genérico de 3 ejes, no como norma.")
    L = 20.0
    M_abs = 0.0
    axle_x = [0.0]
    for s in EUROCODE_SV120.axle_spacings_m:
        axle_x.append(axle_x[-1] + s)
    for k in range(2001):
        x_front = -EUROCODE_SV120.length_m + (L + EUROCODE_SV120.length_m) * k / 2000
        pos = [(x_front + a, P) for a, P in zip(axle_x, EUROCODE_SV120.axle_loads_kN) if 0.0 <= x_front + a <= L]
        for xs, _ in pos:
            R_L = sum(P * (L - xp) / L for xp, P in pos)
            M_abs = max(M_abs, R_L * xs - sum(P * (xs - xp) for xp, P in pos if xp < xs))
    M_mid = max_moment_simple_span(EUROCODE_SV120, L, n_positions=2000)["M_max_kNm"]
    print(f"\nLos momentos de LM3 son en el centro de la luz (línea de influencia triangular), no el máximo absoluto de Barré: para el SV120 en 20 m, centro {M_mid:.1f} frente a máximo bajo un eje {M_abs:.1f} kN·m ({(M_abs / M_mid - 1) * 100:+.2f} %). "
          "Para LM3 EN 1991-2 A.4 toma DAF = 1,0 (vehículo a velocidad reducida) y permite combinarlo con LM1 frecuente en los demás carriles, cosa que aquí no se hace.")


if __name__ == "__main__":
    main()
