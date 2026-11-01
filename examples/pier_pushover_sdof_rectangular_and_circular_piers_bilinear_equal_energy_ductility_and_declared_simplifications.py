"""Pushover de pila en voladizo como sistema de un grado de libertad: pila rectangular de 1,5 × 1,5 m y circular de Ø 1,8 m, 8 y 12 m de altura, curva V–Δ, idealización bilineal por igualdad de energías y ductilidad de desplazamiento, con las simplificaciones del modelo declaradas.

`pier_pushover_sdof` estima M_y = 0,9·A_s·f_y·d + 0,1·N·D, M_u = 1,1·M_y, φ_y = 2,25·ε_y/D (2,35
circular), φ_u = 10·φ_y, L_p = 0,08·H + 0,022·f_y·d_b (Priestley) y construye la curva trilineal;
`bilinear_idealization` iguala el área con rigidez secante al 70 % del máximo. Es predimensionamiento,
no un análisis momento-curvatura por fibras.

Ejecutar:  python examples/pier_pushover_sdof_rectangular_and_circular_piers_bilinear_equal_energy_ductility_and_declared_simplifications.py
"""
import numpy as np

from bridgecalc.analysis.pier_pushover import PierPushoverInput, bilinear_idealization, pier_pushover_sdof
from bridgecalc.ec8_ductility import plastic_hinge_length


def main() -> None:
    casos = [("rect. 1,5 × 1,5 m, H 8 m", PierPushoverInput(H_m=8.0, B_m=1.5, rho_long=0.015, N_axial_kN=6000.0)),
             ("rect. 1,5 × 1,5 m, H 12 m", PierPushoverInput(H_m=12.0, B_m=1.5, rho_long=0.015, N_axial_kN=6000.0)),
             ("rect. 1,5 × 2,0 m, H 8 m", PierPushoverInput(H_m=8.0, B_m=1.5, D_m=2.0, rho_long=0.015, N_axial_kN=6000.0)),
             ("circular Ø 1,8 m, H 8 m", PierPushoverInput(H_m=8.0, B_m=1.8, rho_long=0.015, N_axial_kN=6000.0, section_type="circular")),
             ("rect. 1,5 × 1,5 m, H 8 m, ρ 3 %", PierPushoverInput(H_m=8.0, B_m=1.5, rho_long=0.03, N_axial_kN=6000.0))]
    print("f'c 30 MPa, f_y 420 MPa, N = 6000 kN, ρ_l 1,5 % salvo indicación:")
    print(f"  {'pila':34} {'M_y [kN·m]':>10} {'M_u':>7} {'φ_y [1/km]':>10} {'L_p [m]':>7} {'V_y [kN]':>8} {'Δ_y [mm]':>8} {'Δ_u [mm]':>8} {'μ_Δ':>5} {'K_e [kN/mm]':>11}")
    for nombre, inp in casos:
        r = pier_pushover_sdof(inp)
        b = r.bilinear
        print(f"  {nombre:34} {r.My_kNm:10.0f} {r.Mu_kNm:7.0f} {r.phi_y * 1000:10.3f} {r.Lp_m:7.3f} {b.Vy_kN:8.0f} {b.delta_y_mm:8.1f} {b.delta_u_mm:8.1f} {b.mu_displacement:5.2f} {b.Ke_kN_per_mm:11.1f}")
    r = pier_pushover_sdof(casos[0][1])
    print(f"\nPila de referencia: {len(r.delta_mm)} puntos; curva trilineal origen → (Δ_y, V_y) → (Δ_u, V_u): tramo elástico hasta {r.delta_mm[len(r.delta_mm) // 2 - 1]:.1f} mm, luego endurecimiento del 10 % hasta {r.delta_mm[-1]:.1f} mm")
    print(f"  Δ_y = φ_y·H²/3 = {r.phi_y:.5f}·8²/3 = {r.phi_y * 64 / 3 * 1000:.1f} mm; Δ_p = (φ_u − φ_y)·L_p·(H − L_p/2) = {(r.phi_u - r.phi_y) * r.Lp_m * (8 - r.Lp_m / 2) * 1000:.1f} mm")
    print(f"  L_p Priestley 2007 (0,08·H + 0,022·f_y·d_b, d_b = 25 mm fijo) = {r.Lp_m:.3f} m frente a EN 1998-2 Anexo E (0,10·L_v + 0,015·f_y·d_b) = {plastic_hinge_length(8.0, 420.0, 0.025):.3f} m")
    delta = np.linspace(0, 120, 61)
    V = 900 * (1 - np.exp(-delta / 18))
    b = bilinear_idealization(delta, V)
    E_bi = 0.5 * b.Vy_kN * b.delta_y_mm + 0.5 * (b.Vy_kN + b.Vu_kN) * (b.delta_u_mm - b.delta_y_mm)
    print(f"\nIdealización bilineal de una curva exponencial V = 900·(1 − e^(−Δ/18)): V_y {b.Vy_kN:.0f} kN, Δ_y {b.delta_y_mm:.1f} mm, K_e {b.Ke_kN_per_mm:.1f} kN/mm (secante al 70 %), μ {b.mu_displacement:.2f}; "
          f"energía curva {b.energy_kNmm:.0f} frente a bilineal {E_bi:.0f} kN·mm ({(E_bi / b.energy_kNmm - 1) * 100:+.1f} %)")
    print("\nLo que NO hace: ni diagrama momento-curvatura por equilibrio de sección (el 0,9·A_s·f_y·d ignora el acero comprimido y la posición real del bloque de compresiones), ni φ_u del hormigón confinado (es 10·φ_y por decreto), "
          "ni P-Δ, ni cortante. El diámetro de barra para L_p está fijo en 25 mm. Úsalo para ordenar alternativas; para capacidades, sección por fibras.")


if __name__ == "__main__":
    main()
