"""Incremento dinámico por código (AASHTO 33/75/15 %, EN 1991-2 incluido en LM1, φ2 ferroviario, NSR-10, AS 5100.2) y los módulos aproximados «AS 5100» y «CC-40», declarados como no normativos.

`dynamic_load_allowance` devuelve IM como fracción; desde 1.1.0 'EU' da 0 (LM1/LM2 ya llevan la
amplificación) y 'EU_RAIL' conserva el φ2 de vía. `multi_code.evaluate_as5100` y `evaluate_cc40` usan
trenes de carga y coeficientes (0,130·W·L, W·L/5,5) que no coinciden con AS 5100.2 ni con la CCP-14:
se ejecutan para enseñar lo que devuelven y por qué no hay que diseñar con ellos.

Ejecutar:  python examples/multi_code_as5100_cc40_dynamic_allowance_by_code_and_declared_non_normative_approximations.py
"""
from bridgecalc.loads.dynamic_impact import dynamic_load_allowance
from bridgecalc.loads.hl93 import hl93_envelope
from bridgecalc.loads.lm3_special import impact_factor
from bridgecalc.loads.multi_code import CC40_AXLES_kN, CC40_LANE_LOAD_kN_per_m, CC40_SPACINGS_m, SM1600_AXLES_kN, SM1600_SPACINGS_m, SM1600_UDL_kN_per_m, AS5100Input, CC40Input, evaluate_as5100, evaluate_cc40


def main() -> None:
    print("Incremento dinámico IM (fracción) por código y componente:")
    for code, comp in (("AASHTO", "other"), ("AASHTO", "deck_joints"), ("AASHTO", "fatigue"), ("NSR", "other"), ("AS", "other"), ("EU", "other"), ("SG", "other")):
        print(f"  {code:6} {comp:11} → IM = {dynamic_load_allowance(comp, code, 30.0):.2f}")
    print("  EU_RAIL φ2 − 1 (EN 1991-2 §6.4.5.2, vía con mantenimiento cuidadoso): " + ", ".join(f"LΦ {L:.0f} m → {dynamic_load_allowance('other', 'EU_RAIL', L):.3f}" for L in (3.0, 5.0, 10.0, 20.0, 50.0)))
    print("  lm3_special.impact_factor (DAF): " + ", ".join(f"{c} {impact_factor(c, 20.0):.2f}" for c in ("EUROCODE", "AASHTO", "INDIA", "AS")))
    print("\nHasta 1.0 'EU' devolvía el φ2 ferroviario (0,16 en 20 m, 0,31 en 10 m) y lo multiplicaba sobre el LM1, que ya incluye la amplificación dinámica: doble conteo del 16–30 %.\n")

    print(f"multi_code.evaluate_as5100 — vehículo del módulo: ejes {SM1600_AXLES_kN} kN a {SM1600_SPACINGS_m} m ({sum(SM1600_AXLES_kN):.0f} kN) + {SM1600_UDL_kN_per_m} kN/m, M_camión = IM·0,130·W·L:")
    print(f"  {'L [m]':>5} {'M AS5100 1 carril':>17} {'V':>7} {'HL-93 M':>8}")
    for L in (20.0, 30.0, 40.0):
        r = evaluate_as5100(AS5100Input(span_m=L))
        print(f"  {L:5.0f} {r.M_max_kNm:17.0f} {r.V_max_kN:7.0f} {hl93_envelope(L)['M_max_kNm']:8.0f}")
    print(f"\nmulti_code.evaluate_cc40 — ejes {CC40_AXLES_kN} kN a {CC40_SPACINGS_m} m + {CC40_LANE_LOAD_kN_per_m} kN/m, M_camión = IM·W·L/5,5:")
    print(f"  {'L [m]':>5} {'M_camión':>9} {'M_carril':>9} {'M_total':>8} {'V':>7}")
    for L in (20.0, 30.0, 40.0):
        r = evaluate_cc40(CC40Input(span_m=L))
        print(f"  {L:5.0f} {r['M_truck_kNm']:9.0f} {r['M_lane_kNm']:9.0f} {r['M_total_kNm']:8.0f} {r['V_max_kN']:7.0f}")
    print("\nPor qué no diseñar con estos dos módulos: ni el vehículo de 6 ejes y 440 kN con M = 0,130·W·L ni el camión de 360 kN con M = W·L/5,5 se han contrastado con AS 5100.2 (cargas M1600/S1600) "
          "ni con la CCP-14 colombiana (basada en AASHTO LRFD); ambos coeficientes son aproximaciones de envolvente sin barrido de posiciones. Se conservan por compatibilidad y están marcados como no normativos en el README. "
          "Para un tren de cargas concreto, barre sus ejes con influence_lines.critical_position o lm3_special.max_moment_simple_span.")


if __name__ == "__main__":
    main()
