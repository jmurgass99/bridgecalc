"""Viga cajón pretensada según AASHTO LRFD: momento resistente con f_ps aproximado (§5.6.3.1.1, k = 0,28), cortante por el método simplificado de la teoría modificada del campo de compresiones (β = 2, θ = 36°) y tracción principal en el alma para Service III (§5.9.2.3.3), con los coeficientes SI (0,083 y 0,29) corregidos en 1.1.0.

`BoxGirderSection` describe la sección (f'c, almas, canto útil, ala comprimida, A_ps, f_pu, d_p, A_s, d_s);
`flexural_strength` resuelve c por equilibrio y devuelve M_n, M_r, a y f_ps; `shear_strength` da V_c,
V_s, V_n ≤ 0,25·f'c·b_v·d_v; `principal_stress_web` compara σ₁ = f_pc/2 − √((f_pc/2)² + v²) con 0,29·√f'c.

Ejecutar:  python examples/box_girder_aashto_5_7_prestressed_flexural_strength_mcft_shear_and_principal_web_stress_service_iii.py
"""
from bridgecalc.design import BoxGirderSection, flexural_strength, principal_stress_web, shear_strength


def main() -> None:
    sec = BoxGirderSection(fc_MPa=45.0, bv_mm=2 * 350.0, dv_mm=1900.0, b_flange_mm=6000.0, Aps_mm2=7000.0, fpu_MPa=1860.0, dp_mm=2000.0, As_mm2=3000.0, fy_MPa=500.0, ds_mm=2100.0)
    Mu, Vu = 25_000.0, 6_500.0
    f = flexural_strength(sec, Mu, phi=1.0)
    print(f"Cajón de dos almas de 350 mm, canto 2,2 m, ala comprimida 6,0 m, f'c = {sec.fc_MPa} MPa; A_ps = {sec.Aps_mm2:.0f} mm² (50 cordones de 140 mm², f_pu 1860) en d_p = {sec.dp_mm:.0f} mm, A_s = {sec.As_mm2:.0f} mm² en d_s = {sec.ds_mm:.0f} mm")
    print(f"  Flexión: c por equilibrio → a = β₁·c = {f.a_mm:.1f} mm, f_ps = f_pu·(1 − 0,28·c/d_p) = {f.fps_MPa:.0f} MPa, M_n = {f.Mn_kNm:,.0f} kN·m; M_u = {Mu:,.0f} kN·m → {'cumple' if f.ok else 'NO cumple'} (φ = 1,0 para pretensado adherente con control por tracción)")
    print(f"\n  {'A_ps [mm²]':>10} {'a [mm]':>7} {'f_ps [MPa]':>10} {'M_n [kN·m]':>11} {'M_n/M_u':>7}")
    for Aps in (4000.0, 5500.0, 7000.0, 8500.0, 10000.0):
        s2 = BoxGirderSection(fc_MPa=45.0, bv_mm=700.0, dv_mm=1900.0, b_flange_mm=6000.0, Aps_mm2=Aps, dp_mm=2000.0, As_mm2=3000.0, ds_mm=2100.0)
        r = flexural_strength(s2, Mu)
        print(f"  {Aps:10.0f} {r.a_mm:7.1f} {r.fps_MPa:10.0f} {r.Mn_kNm:11,.0f} {r.Mn_kNm / Mu:7.2f}")
    print("  f_ps baja al crecer A_ps (más c/d_p); el bloque comprimido a ≈ 0,1 m queda dentro del ala de 0,25 m, así que la hipótesis de sección rectangular vale.\n")
    print(f"Cortante V_u = {Vu:,.0f} kN, b_v = {sec.bv_mm:.0f} mm, d_v = {sec.dv_mm:.0f} mm, β = 2, θ = 36°, φ = 0,90:")
    print(f"  {'estribos':22} {'V_c [kN]':>8} {'V_s [kN]':>8} {'V_n [kN]':>8} {'V_r [kN]':>8} {'V_r/V_u':>7}")
    for Av, s, lbl in ((804.0, 300.0, "4Ø16 a 300 (2 almas)"), (804.0, 200.0, "4Ø16 a 200"), (1256.0, 200.0, "4Ø20 a 200"), (1256.0, 150.0, "4Ø20 a 150")):
        r = shear_strength(sec, Vu, Av, s)
        print(f"  {lbl:22} {r.Vc_kN:8.0f} {r.Vs_kN:8.0f} {r.Vn_kN:8.0f} {r.Vr_kN:8.0f} {r.Vr_kN / Vu:7.2f}")
    r = shear_strength(sec, Vu, 1256.0, 150.0)
    print(f"  Tope V_n,máx = 0,25·f'c·b_v·d_v = {r.Vmax_kN:,.0f} kN, lejos de gobernar.")
    print(f"  Con el coeficiente en ksi aplicado en MPa (versión 1.0) V_c habría sido {r.Vc_kN * 0.0316 / 0.083:.0f} kN en vez de {r.Vc_kN:.0f}.\n")
    print("Tracción principal en el alma (Service III), límite −0,29·√f'c MPa (0,110·√f'c en ksi):")
    print(f"  {'f_pc [MPa]':>10} {'v [MPa]':>7} {'σ₁ [MPa]':>9} {'límite':>7} {'estado':>8}")
    for fpc, v in ((4.0, 1.5), (4.0, 2.5), (2.5, 2.5), (6.0, 3.0), (1.0, 2.0), (2.0, 4.0)):
        p = principal_stress_web(fpc, v, sec.fc_MPa)
        print(f"  {fpc:10.1f} {v:7.1f} {p.sigma_principal_MPa:9.3f} {p.limit_MPa:7.3f} {'OK' if p.ok else 'excede':>8}")
    print("\nLímites del módulo: sección rectangular equivalente (si a supera el espesor del ala habría que pasar a sección en T y no avisa), f_ps por la fórmula aproximada sin compatibilidad de deformaciones, β y θ fijos (sin iterar ε_x), sin pérdidas de pretensado ni fase constructiva. "
          "φ no se deduce de la ductilidad de la sección (§5.5.4.2.1): lo pones tú.")


if __name__ == "__main__":
    main()
