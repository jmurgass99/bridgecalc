"""Empujes sobre un estribo de 6 m: Coulomb activo y pasivo con fricción muro-suelo, trasdós inclinado y talud, y Mononobe-Okabe para coeficientes sísmicos k_h de 0 a 0,30 con y sin componente vertical.

`coulomb_pressure` devuelve K_a, K_p, K_ae y los empujes P_a = ½·γ·H²·K_a y P_ae = ½·γ·H²·K_ae·(1 − k_v).
Se tabula el incremento sísmico ΔP_ae = P_ae − P_a, se comprueba que k_h = 0 reproduce Coulomb y se
enseña el límite de M-O cuando φ − ψ − α < 0 (el radicando se anula y K_ae crece sin control).

Ejecutar:  python examples/abutment_coulomb_active_passive_and_mononobe_okabe_seismic_pressure_kh_0_to_0_3.py
"""
import math

from bridgecalc.seismic import AbutmentInput, coulomb_pressure


def main() -> None:
    base = AbutmentInput(H_m=6.0, gamma_kN_m3=19.0, phi_deg=33.0, delta_deg=22.0)
    r0 = coulomb_pressure(base)
    Ka_rankine = math.tan(math.radians(45 - 33 / 2)) ** 2
    print(f"Estribo H = {base.H_m} m, relleno γ = {base.gamma_kN_m3} kN/m³, φ = {base.phi_deg}°, δ = {base.delta_deg}° (2/3 φ), trasdós vertical, talud horizontal:")
    print(f"  Coulomb K_a = {r0.Ka:.4f} (Rankine sin fricción {Ka_rankine:.4f}), K_p = {r0.Kp:.3f}; P_a = ½·γ·H²·K_a = {r0.Pa_kN_per_m:.1f} kN/m\n")
    print("Mononobe-Okabe (ψ = atan(k_h/(1 − k_v))):")
    print(f"  {'k_h':>5} {'k_v':>5} {'ψ [°]':>6} {'K_ae':>7} {'P_ae [kN/m]':>11} {'ΔP_ae':>7} {'K_ae/K_a':>8}")
    for kh, kv in ((0.0, 0.0), (0.05, 0.0), (0.10, 0.0), (0.15, 0.0), (0.20, 0.0), (0.25, 0.0), (0.30, 0.0), (0.20, 0.10), (0.20, -0.10)):
        r = coulomb_pressure(AbutmentInput(H_m=6.0, gamma_kN_m3=19.0, phi_deg=33.0, delta_deg=22.0, kh_seismic=kh, kv_seismic=kv))
        psi = math.degrees(math.atan2(kh, 1 - kv))
        print(f"  {kh:5.2f} {kv:5.2f} {psi:6.2f} {r.Kae:7.4f} {r.Pae_kN_per_m:11.1f} {r.Pae_kN_per_m - r.Pa_kN_per_m:7.1f} {r.Kae / r.Ka:8.3f}")
    print("\nGeometría: trasdós inclinado β y talud α (k_h = 0,15):")
    print(f"  {'β [°]':>5} {'α [°]':>5} {'K_a':>7} {'K_ae':>7} {'P_a':>7} {'P_ae':>7}")
    for beta, alpha in ((0.0, 0.0), (10.0, 0.0), (0.0, 10.0), (0.0, 15.0), (10.0, 10.0)):
        r = coulomb_pressure(AbutmentInput(H_m=6.0, gamma_kN_m3=19.0, phi_deg=33.0, delta_deg=22.0, beta_deg=beta, alpha_deg=alpha, kh_seismic=0.15))
        print(f"  {beta:5.0f} {alpha:5.0f} {r.Ka:7.4f} {r.Kae:7.4f} {r.Pa_kN_per_m:7.1f} {r.Pae_kN_per_m:7.1f}")
    r_lim = coulomb_pressure(AbutmentInput(H_m=6.0, gamma_kN_m3=19.0, phi_deg=33.0, delta_deg=22.0, alpha_deg=15.0, kh_seismic=0.35))
    print(f"\nLímite de M-O: con α = 15° y k_h = 0,35, φ − ψ − α = {33 - math.degrees(math.atan(0.35)) - 15:.1f}° < 0 → el radicando se trunca a 0 y K_ae = {r_lim.Kae:.3f} ya no es fiable (Seed-Whitman o análisis de desplazamientos).")
    print("\nEl punto de aplicación no se calcula: el estático va a H/3 y el incremento ΔP_ae suele colocarse a 0,6·H (Seed & Whitman). "
          "k_h de diseño en estribos = ½·A_s·… según AASHTO 11.6.5 si el estribo puede desplazarse; aquí k_h es un dato. Sin agua ni cohesión.")


if __name__ == "__main__":
    main()
