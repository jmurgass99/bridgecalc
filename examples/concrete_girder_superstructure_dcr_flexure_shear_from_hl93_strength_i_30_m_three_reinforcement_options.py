"""Comprobación rápida de una viga de hormigón armado de 30 m con el HL-93: momento y cortante por viga desde la envolvente y el factor de distribución, mayoración Strength I y ratios demanda/capacidad a flexión (§5.6.3) y cortante (§5.7.3 simplificado) para tres armados.

`concrete_box_girder_flexure(M_u, f'c, b_w, d, A_s)` devuelve M_u/(φ·M_n) con a = A_s·f_y/(0,85·f'c·b_w);
`concrete_box_girder_shear(V_u, f'c, b_w, d, A_v, s)` usa V_c = 0,083·2·√f'c·b_w·0,9d (SI) y
V_s = A_v·f_y·0,9d·cot 36°/s. Pese al nombre, son fórmulas de sección rectangular con el ancho de alma.

Ejecutar:  python examples/concrete_girder_superstructure_dcr_flexure_shear_from_hl93_strength_i_30_m_three_reinforcement_options.py
"""
from bridgecalc.design.aashto_superstructure import concrete_box_girder_flexure, concrete_box_girder_shear
from bridgecalc.loads.hl93 import hl93_envelope
from bridgecalc.loads.load_combinations import factored_effect


def main() -> None:
    L, g_M, g_V = 30.0, 0.65, 0.80
    e = hl93_envelope(L)
    DC, DW = 25.0 * L * L / 8, 5.0 * L * L / 8
    M_LL, V_LL = g_M * e["M_max_kNm"], g_V * e["V_max_kN"]
    Mu = factored_effect("Strength_I", {"DC": DC, "DW": DW, "LL": M_LL}).factored_effect
    Vu = factored_effect("Strength_I", {"DC": 25.0 * L / 2, "DW": 5.0 * L / 2, "LL": V_LL}).factored_effect
    print(f"Viga interior L = {L:.0f} m: DC 25 kN/m → M {DC:.0f} kN·m, DW 5 kN/m → M {DW:.0f}; HL-93 {e['M_max_kNm']:.0f} kN·m/carril × g_M {g_M} = {M_LL:.0f} kN·m; V {e['V_max_kN']:.0f} × g_V {g_V} = {V_LL:.0f} kN")
    print(f"  Strength I: M_u = 1,25·{DC:.0f} + 1,50·{DW:.0f} + 1,75·{M_LL:.0f} = {Mu:.0f} kN·m; V_u = {Vu:.0f} kN\n")
    fc, bw, d = 35.0, 600.0, 1750.0
    print(f"Sección f'c = {fc} MPa, b_w = {bw:.0f} mm, d = {d:.0f} mm, f_y = 500 MPa, φ = 0,90:")
    print(f"  {'armado':28} {'A_s [mm²]':>9} {'a [mm]':>7} {'φM_n [kN·m]':>11} {'DCR flexión':>11}")
    for lbl, As in (("16 Ø32", 16 * 804.0), ("20 Ø32", 20 * 804.0), ("24 Ø32", 24 * 804.0)):
        dcr = concrete_box_girder_flexure(Mu, fc, bw, d, As)
        a = As * 500 / (0.85 * fc * bw)
        print(f"  {lbl:28} {As:9.0f} {a:7.1f} {Mu / dcr:11.0f} {dcr:11.3f} {'cumple' if dcr <= 1 else 'NO cumple'}")
    print(f"\n  {'estribos':28} {'A_v [mm²]':>9} {'s [mm]':>6} {'φV_n [kN]':>9} {'DCR cortante':>12}")
    for lbl, Av, s in (("2 ramas Ø12 a 300", 226.0, 300.0), ("2 ramas Ø12 a 200", 226.0, 200.0), ("4 ramas Ø12 a 200", 452.0, 200.0), ("sin estribos (solo V_c)", 0.0, 0.0)):
        dcr = concrete_box_girder_shear(Vu, fc, bw, d, Av, s)
        print(f"  {lbl:28} {Av:9.0f} {s:6.0f} {Vu / dcr:9.0f} {dcr:12.3f} {'cumple' if dcr <= 1 else 'NO cumple'}")
    print(f"\n  Casos límite: A_s = 0 → DCR {concrete_box_girder_flexure(Mu, fc, bw, d, 0.0)}; a ≥ d (A_s = 90 000 mm²) → {concrete_box_girder_flexure(Mu, fc, bw, d, 90_000.0)}: el módulo devuelve infinito en vez de lanzar, así que hay que comprobar el valor.")
    print("\nSon chequeos de anteproyecto: brazo d − a/2 con un solo lecho de armadura, sin acero comprimido, β y θ fijos (sin ε_x), d_v = 0,9·d en vez de máx(0,9d, 0,72h), sin armadura mínima ni separación máxima de estribos. "
          "Usa box_girder_* para pretensado y una comprobación seccional completa para el proyecto.")


if __name__ == "__main__":
    main()
