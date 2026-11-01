"""Llave de cortante en estribo o cabezal (AASHTO LRFD §5.7.4, práctica Caltrans): capacidad por cortante-fricción V_ni = c·A_cv + μ·(A_vf·f_y + P_c), topes 0,25·f'c·A_cv y 10 MPa·A_cv, y φ = 0,90, barriendo armadura, compresión y coeficiente de fricción.

`shear_key_capacity` devuelve el área de interfaz, la fuerza del acero, la capacidad nominal, el tope
que gobierna y la capacidad de diseño en kN. Se muestra cuándo deja de servir añadir armadura
(gobierna el tope de 0,25·f'c) y cuánto aporta la compresión de la junta.

Ejecutar:  python examples/shear_key_capacity_aashto_5_7_4_friction_cohesion_axial_compression_and_upper_limits_sweep.py
"""
from bridgecalc.design.shear_key import shear_key_capacity


def main() -> None:
    b, h, fck, fyk = 600.0, 400.0, 30.0, 420.0
    base = shear_key_capacity(b, h, fck, Avf_mm2=4 * 201.0, fyk_MPa=fyk)
    print(f"Llave de {b:.0f} × {h:.0f} mm, f'c = {fck} MPa, 4 Ø16 (A_vf = {4 * 201:.0f} mm²) f_y = {fyk} MPa, c = 0,5 MPa, μ = 1,0, sin compresión:")
    print(f"  A_cv = {base['Acv_mm2']:,.0f} mm²; acero {base['steel_force_kN']:.0f} kN; V_ni = 0,5·A_cv + 1,0·A_vf·f_y = {base['nominal_capacity_kN']:.0f} kN; topes {base['upper_limit_1_kN']:.0f} (0,25·f'c·A_cv) y {base['upper_limit_2_kN']:.0f} kN (10·A_cv); V_di = 0,9·{base['governing_nominal_kN']:.0f} = {base['design_capacity_kN']:.0f} kN\n")
    print("Barrido de armadura (μ = 1,0, P_c = 0):")
    print(f"  {'A_vf':>12} {'acero [kN]':>10} {'V_ni':>7} {'gobierna':>8} {'V_di [kN]':>9}")
    for lbl, Avf in (("4 Ø16", 804.0), ("6 Ø16", 1206.0), ("4 Ø20", 1256.0), ("6 Ø20", 1884.0), ("8 Ø25", 3928.0)):
        r = shear_key_capacity(b, h, fck, Avf, fyk)
        gob = "V_ni" if r["governing_nominal_kN"] == r["nominal_capacity_kN"] else ("0,25f'c" if r["governing_nominal_kN"] == r["upper_limit_1_kN"] else "10·Acv")
        print(f"  {lbl:>12} {r['steel_force_kN']:10.0f} {r['nominal_capacity_kN']:7.0f} {gob:>8} {r['design_capacity_kN']:9.0f}")
    print("\nCompresión en la junta P_c (4 Ø20):")
    print(f"  {'P_c [kN]':>8} {'V_ni':>7} {'V_di [kN]':>9} {'+ frente a P_c = 0':>18}")
    r0 = shear_key_capacity(b, h, fck, 1256.0, fyk)
    for Pc in (0.0, 200.0, 500.0, 1000.0):
        r = shear_key_capacity(b, h, fck, 1256.0, fyk, Pc_kN=Pc)
        print(f"  {Pc:8.0f} {r['nominal_capacity_kN']:7.0f} {r['design_capacity_kN']:9.0f} {(r['design_capacity_kN'] / r0['design_capacity_kN'] - 1) * 100:+17.0f} %")
    pares = (("por defecto del módulo", 0.5, 1.0), ("intencionadamente rugosa, 0,24 ksi", 1.65, 1.0), ("no rugosa, 0,075 ksi", 0.52, 0.6))
    print("\nCoeficientes de interfaz (4 Ø20, P_c = 0): " + "; ".join("%s: c %.2f MPa, μ %.1f → V_di %.0f kN" % (lbl, c, mu, shear_key_capacity(b, h, fck, 1256.0, fyk, cohesion_c_MPa=c, mu_coefficient=mu)["design_capacity_kN"]) for lbl, c, mu in pares))
    r8 = shear_key_capacity(b, h, fck, 3928.0, fyk)
    r_tope = shear_key_capacity(b, h, fck, 3928.0, fyk, Pc_kN=500.0)
    print(f"\nCon 8 Ø25, V_ni = {r8['nominal_capacity_kN']:.0f} kN queda a {(1 - r8['nominal_capacity_kN'] / r8['upper_limit_1_kN']) * 100:.0f} % del tope 0,25·f'c·A_cv = {r8['upper_limit_1_kN']:.0f} kN; con 500 kN de compresión ya manda el tope ({r_tope['governing_nominal_kN']:.0f} kN): "
          "a partir de ahí añadir acero no sube la capacidad, hay que agrandar la llave o subir f'c.")
    print("Los pares (c, μ) de AASHTO LRFD §5.7.4.4 para hormigón contra hormigón endurecido son 0,24 ksi / 1,0 con superficie intencionadamente rugosa y 0,075 ksi / 0,6 sin rugosidad (ASPIRE, invierno 2025, Tabla 1); "
          "el módulo toma c = 0,5 MPa y μ = 1,0 por defecto, que no es ninguna fila de esa tabla: pásalos explícitamente. No comprueba A_vf mínimo ni la fuerza sísmica de la llave.")


if __name__ == "__main__":
    main()
