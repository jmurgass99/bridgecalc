"""Combinaciones EN 1990: 6.10, 6.10a y 6.10b con elección automática de la acción variable dominante, estados de servicio característico, frecuente y casi permanente, y combinación sísmica, aplicadas a los momentos de un tablero.

`en1990_combinations` lleva la tabla ψ de edificación (A1.1); para puentes de carretera se añaden al
catálogo los ψ del Anexo A2 (tándem 0,75/0,75/0; sobrecarga repartida 0,40/0,40/0; viento 0,6/0,2/0;
térmica 0,6/0,6/0,5) y se sobrescribe γ_Q = 1,35 del tráfico (Tabla A2.4(B)), porque la función toma
γ_Q = 1,50 como constante de módulo. Se muestra qué acción dominante gobierna en cada expresión.

Ejecutar:  python examples/en1990_combinations_6_10_6_10a_6_10b_leading_variable_selection_sls_frequent_and_seismic.py
"""
import bridgecalc.loads.en1990_combinations as c


def main() -> None:
    G = {"tablero": 1800.0, "pavimento+barreras": 320.0}
    print(f"Permanentes (kN·m por tablero): {G}; γ_G = {c.GAMMA_G_SUP} desfavorable, ξ = {c.XI}\n")
    print("1) Tabla de edificación (A1.1) tal como viene en el módulo, γ_Q = 1,50:")
    vars_edif = [c.VariableAction("tráfico (cat. G)", 2100.0, "G"), c.VariableAction("viento", 260.0, "wind"), c.VariableAction("temperatura", 180.0, "temperature")]
    for expr in ("6.10", "6.10a", "6.10b"):
        print(f"  ULS {expr:5}: {c.uls_strength(G, vars_edif, expr):8.0f} kN·m")
    print(f"  gobernante del set alternativo máx(6.10a, 6.10b): {c.uls_governing(G, vars_edif):.0f} kN·m")
    for kind in ("characteristic", "frequent", "quasi_permanent"):
        print(f"  SLS {kind:16}: {c.sls_combination(G, vars_edif, kind):8.0f} kN·m")
    print(f"  sísmica G + A_Ed + Σψ2·Q (A_Ed = 950): {c.seismic_combination(G, vars_edif, 950.0):.0f} kN·m\n")

    print("2) Puente de carretera: ψ del Anexo A2 Tabla A2.1 añadidos al catálogo y γ_Q,tráfico = 1,35 (Tabla A2.4(B)):")
    c.PSI_CATALOG["gr1a_TS"] = (0.75, 0.75, 0.0)
    c.PSI_CATALOG["gr1a_UDL"] = (0.40, 0.40, 0.0)
    c.PSI_CATALOG["bridge_wind"] = (0.60, 0.20, 0.0)
    c.PSI_CATALOG["bridge_thermal"] = (0.60, 0.60, 0.50)
    gamma_q_original = c.GAMMA_Q
    c.GAMMA_Q = 1.35
    vars_puente = [c.VariableAction("tándem TS", 1400.0, "gr1a_TS"), c.VariableAction("sobrecarga UDL", 700.0, "gr1a_UDL"), c.VariableAction("viento", 260.0, "bridge_wind"), c.VariableAction("temperatura", 180.0, "bridge_thermal")]
    print(f"  {'dominante':16} {'6.10':>8} {'6.10a':>8} {'6.10b':>8}")
    filas = {}
    for lead in vars_puente:
        fila = []
        for expr in ("6.10", "6.10a", "6.10b"):
            gG = c.XI * c.GAMMA_G_SUP if expr == "6.10b" else c.GAMMA_G_SUP
            total = gG * sum(G.values())
            for v in vars_puente:
                psi0 = v.psi()[0]
                total += c.GAMMA_Q * (psi0 if (v is not lead or expr == "6.10a") else 1.0) * v.Qk
            fila.append(total)
        filas[lead.name] = fila
        print(f"  {lead.name:16} " + " ".join(f"{t:8.0f}" for t in fila))
    gob = max(filas, key=lambda k: filas[k][0])
    print(f"  función (máx. sobre dominantes): 6.10 {c.uls_strength(G, vars_puente, '6.10'):.0f}, 6.10a {c.uls_strength(G, vars_puente, '6.10a'):.0f}, 6.10b {c.uls_strength(G, vars_puente, '6.10b'):.0f} kN·m → en 6.10 gobierna «{gob}» como dominante")
    print("  La sobrecarga repartida gana al tándem como dominante aunque valga la mitad: su ψ0 = 0,40 es el más bajo, así que es la que más sube al pasar de ψ0·Q a Q (0,60·700 = 420 frente a 0,25·1400 = 350 kN·m).")
    print(f"  SLS característica {c.sls_combination(G, vars_puente):.0f}, frecuente {c.sls_combination(G, vars_puente, 'frequent'):.0f}, casi permanente {c.sls_combination(G, vars_puente, 'quasi_permanent'):.0f} kN·m (solo la térmica tiene ψ2 ≠ 0)")
    c.GAMMA_Q = gamma_q_original
    print("\nEN 1990 A2 trata el gr1a (TS + UDL) como un grupo con un solo ψ0 del grupo; aquí se separan para ver el efecto. "
          "El módulo no conoce el Anexo A2: γ_Q, γ_G de puentes (1,35 también) y ψ hay que ponerlos a mano, y GAMMA_Q es estado global del módulo (devuélvelo a 1,50 después, como arriba). "
          "6.10a usa ψ0 también en la dominante; 6.10b reduce las permanentes con ξ = 0,85.")


if __name__ == "__main__":
    main()
