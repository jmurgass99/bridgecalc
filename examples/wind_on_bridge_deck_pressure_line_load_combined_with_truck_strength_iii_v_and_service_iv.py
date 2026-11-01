"""Viento sobre el tablero (q = ½·ρ·V²·C_d) para AASHTO, Eurocódigo y AS 5100: presión, carga lineal y fuerza total en un tablero de 40 m, combinación con el camión mayorado por IM y mayoración en Strength III, Strength V y Service IV.

`wind_pressure_bridge` convierte velocidad, altura expuesta y coeficiente de arrastre en kPa y kN/m;
`combined_dynamic_truck_wind` suma camión·(1 + IM) y viento·L; `load_combinations.factored_effect`
aplica los γ de la Tabla 3.4.1-1. Es la presión dinámica básica sin coeficientes de ráfaga, exposición
ni altura: valores de anteproyecto, no de norma.

Ejecutar:  python examples/wind_on_bridge_deck_pressure_line_load_combined_with_truck_strength_iii_v_and_service_iv.py
"""
from bridgecalc.loads.dynamic_impact import WindOnBridgeInput, combined_dynamic_truck_wind, wind_pressure_bridge
from bridgecalc.loads.load_combinations import factored_effect, gamma


def main() -> None:
    V, H, L, Cd = 44.7, 2.5, 40.0, 1.5
    print(f"Tablero de {L:.0f} m, altura expuesta {H} m, C_d = {Cd}, V = {V} m/s (100 mph, velocidad base de las ediciones del LRFD anteriores a la 8ª):")
    print(f"  {'código':7} {'q [kPa]':>8} {'w [kN/m]':>9} {'F total [kN]':>12}")
    for code in ("AASHTO", "EU", "AS", "NSR"):
        w = wind_pressure_bridge(WindOnBridgeInput(V_ms=V, H_m=H, L_m=L, Cd=Cd, code=code))
        print(f"  {code:7} {w.pressure_kPa:8.3f} {w.line_load_kN_per_m:9.3f} {w.total_force_kN:12.1f}")
    print(f"  Comprobación: ½·1,225·{V}²·{Cd} = {0.5 * 1.225 * V * V * Cd / 1000:.3f} kPa; AS aplica un factor 1,05 propio del módulo.\n")
    print("Velocidad y coeficiente de arrastre (AASHTO):")
    print(f"  {'V [m/s]':>7} {'km/h':>5} {'Cd':>4} {'w [kN/m]':>9}")
    for v_, cd in ((30.0, 1.3), (40.0, 1.5), (44.7, 1.5), (50.0, 1.7)):
        w = wind_pressure_bridge(WindOnBridgeInput(V_ms=v_, H_m=H, L_m=L, Cd=cd))
        print(f"  {v_:7.1f} {v_ * 3.6:5.0f} {cd:4.1f} {w.line_load_kN_per_m:9.3f}")
    wind = WindOnBridgeInput(V_ms=V, H_m=H, L_m=L, Cd=Cd, code="AASHTO")
    truck_dyn, w_line, total = combined_dynamic_truck_wind(static_truck_kN=325.0, span_m=L, wind=wind)
    print(f"\nCamión HL-93 de 325 kN con IM 33 % → {truck_dyn:.1f} kN; viento {w_line:.3f} kN/m × {L:.0f} m = {w_line * L:.1f} kN; suma sin mayorar {total:.1f} kN (vertical + horizontal, solo orientativa)")
    _, w_eu, _ = combined_dynamic_truck_wind(static_truck_kN=325.0, span_m=L, wind=WindOnBridgeInput(V_ms=V, H_m=H, L_m=L, Cd=Cd, code="EU"))
    print(f"Con código EU el camión no se mayora (LM1 ya incluye la amplificación): {combined_dynamic_truck_wind(325.0, L, WindOnBridgeInput(V_ms=V, H_m=H, L_m=L, Cd=Cd, code='EU'))[0]:.1f} kN\n")
    efectos = {"DC": 2600.0, "DW": 450.0, "LL": 1850.0, "WS": 0.12 * w_line * L * 10.0, "WL": 40.0}
    print(f"Mayoración de un efecto transversal (kN·m) con WS = {efectos['WS']:.0f} y WL = {efectos['WL']:.0f}:")
    for ls in ("Strength_I", "Strength_III", "Strength_V", "Service_I", "Service_IV"):
        r = factored_effect(ls, efectos)
        print(f"  {ls:13} γ_LL {gamma(ls, 'LL'):.2f} γ_WS {gamma(ls, 'WS'):.2f} γ_WL {gamma(ls, 'WL'):.2f} → {r.factored_effect:.0f}")
    print("\nStrength III (viento sin tráfico) y V (viento con tráfico) rara vez gobiernan la flexión longitudinal, pero sí los apoyos y la subestructura. "
          "Los γ_WS son los del esquema anterior a la 8ª edición del LRFD (Strength III 1,40); desde 2017 Strength III usa 1,0 con la presión de la nueva sección 3.8. "
          "El módulo no aplica factores de ráfaga, altura ni exposición (AASHTO 3.8 o c_e y c_f de EN 1991-1-4): úsalo para órdenes de magnitud.")


if __name__ == "__main__":
    main()
