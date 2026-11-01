"""Envolvente HL-93 en vigas continuas de 2 × 30 y 3 × 30 m por líneas de influencia: momento positivo, momento negativo en el apoyo con la regla del 90 % de dos camiones (AASHTO LRFD §3.6.1.3.1), cortante en las caras de los apoyos y comparación con el método de coeficientes de la versión 1.0 y con la viga simple.

`envelope_multispan` barre el camión en los dos sentidos y el tándem sobre la línea de influencia
de cada sección, aplica el carril de 9,34 kN/m solo donde la ordenada tiene el signo buscado, IM al
vehículo y, para el momento negativo, 0,9·(dos camiones a ≥ 15 m + carril). `components` publica el
desglose y la sección crítica.

Ejecutar:  python examples/multispan_hl93_envelope_two_and_three_equal_spans_30_m_influence_lines_two_truck_rule_vs_old_coefficients.py
"""
from bridgecalc.loads.hl93 import hl93_envelope
from bridgecalc.loads.multispan import MultiSpanInput, envelope_multispan

VIEJO = {2: (1709.9, 2137.4, 285.0), 3: (1645.8, 2287.0, 306.4)}


def main() -> None:
    L = 30.0
    simple = hl93_envelope(L)
    print(f"Viga simple de {L:.0f} m como referencia: M = {simple['M_max_kNm']:.0f} kN·m, V = {simple['V_max_kN']:.0f} kN (un carril, IM 1,33)\n")
    for n in (2, 3):
        r = envelope_multispan(MultiSpanInput(span_m=L, n_spans=n))
        p, q, v = r.components["M_positive"], r.components["M_negative"], r.components["V"]
        print(f"{n} × {L:.0f} m — método: {r.method}")
        print(f"  M⁺ = {r.M_positive_max_kNm:.0f} kN·m en x = {r.M_positive_x_m:.2f} m: {p['vehicle']} {p['vehicle_with_IM_kNm']:.0f} (sin IM: camión {p['truck_kNm']:.0f}, tándem {p['tandem_kNm']:.0f}) + carril {p['lane_kNm']:.0f}; 1er eje en x = {p['first_axle_x_m']:.2f} m")
        print(f"  M⁻ = {r.M_negative_max_kNm:.0f} kN·m en el apoyo x = {r.M_negative_x_m:.0f} m, regla «{q['rule']}»: un vehículo {q['single_vehicle_total_kNm']:.0f} (camión {q['truck_kNm']:.0f}·1,33 + carril {q['lane_kNm']:.0f}) frente a 0,9·(2 camiones {q['two_trucks_kNm']:.0f}·1,33 + carril) = {q['two_trucks_total_kNm']:.0f}; separación entre camiones {q['two_trucks_gap_m']:.0f} m")
        print(f"  V = {r.V_max_kN:.0f} kN en {v['section']}: camión {v['truck_kN']:.0f}·1,33 + carril {v['lane_kN']:.0f}")
        print(f"  {'sección':38} {'signo':>5} {'camión':>7} {'tándem':>7} {'carril':>7} {'V [kN]':>7}")
        for s in v["all_sections"]:
            if s["total_kN"] > 1.0:
                print(f"  {s['section']:38} {'+' if s['sign'] > 0 else '−':>5} {s['truck_kN']:7.1f} {s['tandem_kN']:7.1f} {s['lane_kN']:7.1f} {s['total_kN']:7.1f}")
        mp, mn, vv = VIEJO[n]
        print(f"  Versión 1.0 (coeficientes 0,080/0,100·w·L², 0,40·w·L con w = 1,33·325/L + 9,34): M⁺ {mp:.0f}, M⁻ {mn:.0f}, V {vv:.0f} → "
              f"{(r.M_positive_max_kNm / mp - 1) * 100:+.0f} %, {(r.M_negative_max_kNm / mn - 1) * 100:+.0f} %, {(r.V_max_kN / vv - 1) * 100:+.0f} %")
        print(f"  Frente a la viga simple: M⁺ {(r.M_positive_max_kNm / simple['M_max_kNm'] - 1) * 100:+.0f} %, V {(r.V_max_kN / simple['V_max_kN'] - 1) * 100:+.0f} %\n")
    sin = envelope_multispan(MultiSpanInput(span_m=L, n_spans=2, impact_factor=1.0, n_eval_per_span=8))
    print(f"2 × 30 m sin IM: M⁺ {sin.M_positive_max_kNm:.0f}, M⁻ {sin.M_negative_max_kNm:.0f}, V {sin.V_max_kN:.0f} (el carril no cambia: {sin.components['M_negative']['lane_kNm']:.0f} kN·m = 9,34·30²/8 en el apoyo con los dos vanos cargados)")
    print("\nLa continuidad baja el momento positivo un quinto respecto a la viga simple y sube el cortante en la cara del apoyo interior. El momento negativo lo gobierna el par de camiones al 90 %, no el tándem. "
          "Todo por carril y con EI constante: aplica factor de distribución y presencia múltiple fuera, y no lo uses con cartelas.")


if __name__ == "__main__":
    main()
