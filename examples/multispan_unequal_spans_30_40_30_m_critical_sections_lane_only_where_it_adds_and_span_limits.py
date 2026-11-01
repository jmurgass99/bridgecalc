"""Envolvente HL-93 en una viga continua de luces desiguales 30 + 40 + 30 m: secciones críticas, carril aplicado solo en las zonas que suman, simetría de los apoyos interiores, cuatro vanos de 25 m y los límites de la función (2 a 6 vanos).

`MultiSpanInput(spans_m=(30, 40, 30))` manda sobre `span_m`/`n_spans`. Se enseña el desglose del
momento negativo en cada apoyo, cómo el carril del momento positivo del vano central deja fuera los
vanos laterales (ordenadas negativas), y la tabla completa de cortantes por sección.

Ejecutar:  python examples/multispan_unequal_spans_30_40_30_m_critical_sections_lane_only_where_it_adds_and_span_limits.py
"""
from bridgecalc.loads.hl93 import LANE_LOAD_kN_per_m
from bridgecalc.loads.influence_lines import influence_line_continuous
from bridgecalc.loads.multispan import MAX_SPANS, MultiSpanInput, envelope_multispan


def main() -> None:
    spans = (30.0, 40.0, 30.0)
    r = envelope_multispan(MultiSpanInput(span_m=0.0, n_spans=0, spans_m=spans))
    p, q, v = r.components["M_positive"], r.components["M_negative"], r.components["V"]
    print(f"Viga continua {spans} m, un carril HL-93, IM 1,33:")
    print(f"  M⁺ = {r.M_positive_max_kNm:.0f} kN·m en x = {r.M_positive_x_m:.2f} m (vano {p['span_index'] + 1}): {p['vehicle']} {p['vehicle_with_IM_kNm']:.0f} + carril {p['lane_kNm']:.0f}")
    print(f"  M⁻ = {r.M_negative_max_kNm:.0f} kN·m en x = {r.M_negative_x_m:.0f} m, regla {q['rule']}; carril {q['lane_kNm']:.0f} kN·m, dos camiones {q['two_trucks_kNm']:.0f} kN·m a {q['two_trucks_gap_m']:.0f} m")
    print(f"  V = {r.V_max_kN:.0f} kN en {v['section']}\n")
    print(f"  {'sección de cortante':38} {'signo':>5} {'camión':>7} {'tándem':>7} {'carril':>7} {'V [kN]':>7}")
    for s in v["all_sections"]:
        if s["total_kN"] > 1.0:
            sg = "+" if s["sign"] > 0 else "−"
            print(f"  {s['section']:38} {sg:>5} {s['truck_kN']:7.1f} {s['tandem_kN']:7.1f} {s['lane_kN']:7.1f} {s['total_kN']:7.1f}")
    il_mid = influence_line_continuous(list(spans), 50.0, n_points=300)
    pos = il_mid.ordinates > 0
    x_pos = il_mid.x_m[pos]
    print(f"\nCarril para M⁺ en el centro del vano de 40 m: la LI es positiva solo entre x = {x_pos.min():.1f} y {x_pos.max():.1f} m (el vano central); "
          f"los vanos laterales tienen ordenada negativa (hasta {il_mid.ordinates.min():.3f}) y quedan sin carril: {LANE_LOAD_kN_per_m} kN/m × área positiva = {p['lane_kNm'] if p['span_index'] == 1 else float('nan'):.0f} kN·m frente a 9,34·40²/8 = {9.34 * 1600 / 8:.0f} de la viga simple.")
    il_b = influence_line_continuous(list(spans), 30.0, n_points=300)
    print(f"Carril para M⁻ en el apoyo de 30 m: la LI es negativa en los vanos 1 y 2 y positiva en el 3 (máx {il_b.ordinates.max():+.3f}); el carril carga solo los dos primeros.\n")
    r4 = envelope_multispan(MultiSpanInput(span_m=25.0, n_spans=4, n_eval_per_span=10))
    print(f"Cuatro vanos de 25 m: M⁺ {r4.M_positive_max_kNm:.0f} (x = {r4.M_positive_x_m:.1f} m), M⁻ {r4.M_negative_max_kNm:.0f} (x = {r4.M_negative_x_m:.0f} m), V {r4.V_max_kN:.0f} kN; "
          f"un vano extremo gobierna el positivo y un apoyo contiguo a los vanos extremos (x = 25 o 75 m, simétricos) el negativo")
    for bad in (MultiSpanInput(span_m=30.0, n_spans=1), MultiSpanInput(span_m=30.0, n_spans=MAX_SPANS + 1), MultiSpanInput(span_m=0.0, n_spans=0, spans_m=(20.0, -5.0))):
        try:
            envelope_multispan(bad)
        except ValueError as exc:
            print(f"  Entrada inválida → ValueError: {exc}")
    print("\nCon vanos laterales más cortos (30/40/30 ≈ 0,75) los apoyos interiores son simétricos y el positivo máximo cae en el vano central. "
          "Luces muy distintas o relaciones < 0,6 piden revisar el levantamiento en los vanos cortos: la LI de reacción en el estribo se hace negativa y esta función no publica reacciones.")


if __name__ == "__main__":
    main()
