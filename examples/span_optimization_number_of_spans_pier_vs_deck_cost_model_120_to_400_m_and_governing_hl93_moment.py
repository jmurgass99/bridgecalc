"""Número óptimo de vanos para puentes de 120 a 400 m con un modelo de coste paramétrico (pila fija frente a tablero creciente con la luz) y el momento HL-93 de la luz elegida.

`optimize_n_spans` recorre n entre L_total/L_máx y L_total/L_mín, suma (n − 1)·coste_pila + coste_tablero·L_total·(L/30)^(exp − 1)
y devuelve el mínimo con sus candidatos; `M_design_kNm` es la envolvente HL-93 de viga simple de esa
luz. El exponente 1,5 hace que el tablero encarezca con √L: con pilas caras salen pocos vanos largos.

Ejecutar:  python examples/span_optimization_number_of_spans_pier_vs_deck_cost_model_120_to_400_m_and_governing_hl93_moment.py
"""
from bridgecalc.optimization import SpanOptimizationInput, optimize_n_spans


def main() -> None:
    print("Coste pila 250 kUSD, tablero 8 kUSD/m a 30 m con exponente 1,5, luces admitidas 15–80 m:")
    print(f"  {'L total [m]':>11} {'n óptimo':>8} {'luz [m]':>7} {'coste [MUSD]':>12} {'M HL-93 [kN·m]':>14}  candidatos (n: luz → MUSD)")
    for Lt in (120.0, 200.0, 300.0, 400.0):
        r = optimize_n_spans(SpanOptimizationInput(total_length_m=Lt))
        cands = "; ".join(f"{n}: {s:.0f} → {c / 1e6:.2f}" for n, s, c in r.candidates[:6])
        print(f"  {Lt:11.0f} {r.optimal_n_spans:8d} {r.optimal_span_m:7.1f} {r.total_cost_USD / 1e6:12.2f} {r.M_design_kNm:14.0f}  {cands}{'…' if len(r.candidates) > 6 else ''}")
    print("\nSensibilidad al coste de pila (L total = 200 m):")
    print(f"  {'pila [kUSD]':>11} {'n':>3} {'luz [m]':>7} {'coste [MUSD]':>12}")
    for cp in (50_000.0, 150_000.0, 250_000.0, 600_000.0, 2_000_000.0):
        r = optimize_n_spans(SpanOptimizationInput(total_length_m=200.0, cost_pier_USD_per_unit=cp))
        print(f"  {cp / 1e3:11.0f} {r.optimal_n_spans:3d} {r.optimal_span_m:7.1f} {r.total_cost_USD / 1e6:12.2f}")
    print("\nExponente del tablero (L total = 200 m, pila 250 kUSD): " + "; ".join(f"exp {ex}: n = {optimize_n_spans(SpanOptimizationInput(total_length_m=200.0, cost_deck_exp=ex)).optimal_n_spans}" for ex in (1.2, 1.5, 2.0, 2.5)))
    r = optimize_n_spans(SpanOptimizationInput(total_length_m=200.0, span_min_m=40.0, span_max_m=60.0))
    print(f"Luces restringidas a 40–60 m: n = {r.optimal_n_spans}, luz {r.optimal_span_m:.1f} m, candidatos {[(n, round(s, 1)) for n, s, _ in r.candidates]}")
    print("\nEl modelo de coste es ilustrativo: no incluye cimentaciones (que dependen de la altura de pila y el terreno), ni el salto de tipología al pasar de 40–50 m (losa → cajón → pretensado), ni el coste de los estribos; "
          "M_design es el de viga simple, no el del tablero continuo. Sirve para ordenar escenarios, no para presupuestar.")


if __name__ == "__main__":
    main()
