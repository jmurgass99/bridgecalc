"""Ductilidad de pilas según EN 1998-2: factor de comportamiento q (Tabla 4.1) con reducción por esbeltez de cortante, cuantía mecánica de confinamiento ω_w (§6.2.1), longitud de rótula plástica (Anexo E) y comprobación de desplazamiento objetivo.

`behavior_factor_q` baja q con √(α_s/3) cuando L_s/h < 3; `confinement_required` da ω_w,req =
máx(ω_w,min, 0,37·(A_c/A_cc)·η_k/(α_n·α_s)) con η_k = N_Ed/(A_c·f_cd); `plastic_hinge_length` es
L_p = 0,10·L_v + 0,015·f_y·d_b; `target_displacement` compara demanda espectral y capacidad.

Ejecutar:  python examples/ec8_ductility_behaviour_factor_q_confinement_omega_w_plastic_hinge_length_and_target_displacement.py
"""
from bridgecalc.ec8_ductility import behavior_factor_q, confinement_required, plastic_hinge_length, target_displacement


def main() -> None:
    print("Factor de comportamiento q (EN 1998-2 Tabla 4.1, forma simplificada del módulo):")
    for tipo in ("reinforced_concrete_ductile", "reinforced_concrete_limited_ductility", "steel_ductile", "non_ductile"):
        print(f"  {tipo:38} q = {behavior_factor_q(tipo):.2f}")
    print("  Reducción por esbeltez de cortante α_s = L_s/h en pila dúctil de hormigón: " + ", ".join(f"α_s {a} → q {behavior_factor_q('reinforced_concrete_ductile', {'shear_span_ratio': a}):.2f}" for a in (4.0, 3.0, 2.0, 1.5, 1.0, 0.8)))
    print()
    print("Confinamiento ω_w,req para una pila de 1,5 × 1,5 m, f_cd = 20 MPa (C30/37, γ_c 1,5), f_yd = 435 MPa:")
    Ac = 1.5 * 1.5
    fcd = 20e6
    print(f"  {'N_Ed [kN]':>9} {'η_k':>6} {'ω_w,req (α_n·α_s = 1)':>21} {'ω_w,req (α = 0,8)':>17}")
    for N in (3000.0, 6000.0, 9000.0, 13500.0, 18000.0):
        w1 = confinement_required(N * 1e3, Ac, fcd)
        w2 = confinement_required(N * 1e3, Ac, fcd, alpha_n=0.9, alpha_s=0.89)
        print(f"  {N:9.0f} {N * 1e3 / (Ac * fcd):6.3f} {w1:21.3f} {w2:17.3f}")
    print(f"  Con η_k ≤ {0.12 / (0.37 / 0.85):.3f} manda el mínimo ω_w,min = 0,12 (zonas dúctiles, rectangular); por encima crece lineal con el axil.\n")
    print("Longitud de rótula plástica L_p = 0,10·L_v + 0,015·f_y·d_b (Anexo E):")
    for Lv, db in ((6.0, 0.020), (8.0, 0.025), (8.0, 0.032), (12.0, 0.025)):
        Lp = plastic_hinge_length(Lv, 500.0, db)
        print(f"  L_v = {Lv:4.1f} m, Ø{db * 1000:.0f}: L_p = {0.10 * Lv:.2f} + {0.015 * 500 * db:.3f} = {Lp:.3f} m ({Lp / Lv * 100:.1f} % de L_v)")
    print()
    print("Desplazamiento objetivo (demanda espectral frente a capacidad):")
    for T, Sd, cap in ((1.2, 0.18, 0.25), (1.8, 0.27, 0.25), (0.9, 0.12, 0.15)):
        c = target_displacement(T, Sd, cap)
        print(f"  T_ef = {T} s, S_d = {Sd * 1000:.0f} mm, capacidad {cap * 1000:.0f} mm → ratio {c.ratio:.2f} {'OK' if c.ok else 'NO CUMPLE'}")
    try:
        behavior_factor_q("timber")
    except ValueError as exc:
        print(f"  Tipo desconocido → ValueError: {exc}")
    print("\nq de la tabla real depende también de la relación axil (η_k > 0,3 lo reduce con λ(η_k)) y del tipo de rótula (vertical/inclinada, en cabeza o pie); el módulo solo aplica la corrección por α_s. "
          "ω_w,req omite el término 0,13·(f_yd/f_cd)·(ρ_L − 0,01) de la fórmula completa de §6.2.1.4: es la forma básica por axil. Unidades SI estrictas (N, m², Pa).")


if __name__ == "__main__":
    main()
