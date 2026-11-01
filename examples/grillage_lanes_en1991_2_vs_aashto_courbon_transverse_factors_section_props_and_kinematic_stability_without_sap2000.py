"""Piezas puras del generador de emparrillado, sin SAP2000 ni fastsap: carriles nocionales EN 1991-2 frente a carriles de diseño AASHTO para seis anchos de calzada, factores de Courbon de reparto transversal, propiedades mecánicas de una viga armada y de una sección de hormigón, recuentos del emparrillado y verificación de estabilidad cinemática del esquema de apoyos.

`notional_lanes_en1991_2` / `design_lanes_aashto_lrfd` dividen la calzada; `courbon_transverse_factors`
reparte una carga excéntrica entre vigas con Ση = 1 y Ση·y = y_carga; `plate_girder_section_props` y
`rectangular_concrete_section_props` calculan A, I, J, áreas de cortante y módulos resistentes;
`expected_grillage_counts` deriva nudos y barras; `verify_kinematic_stability` comprueba los 6 grados
de libertad globales y la dilatación libre.

Ejecutar:  python examples/grillage_lanes_en1991_2_vs_aashto_courbon_transverse_factors_section_props_and_kinematic_stability_without_sap2000.py
"""
from bridgecalc.integration.grillage_model import (
    courbon_transverse_factors,
    design_lanes_aashto_lrfd,
    expected_grillage_counts,
    notional_lanes_en1991_2,
    plate_girder_section_props,
    rectangular_concrete_section_props,
    verify_kinematic_stability,
)


def main() -> None:
    print("Carriles por ancho de calzada:")
    print(f"  {'w [m]':>5} {'EN 1991-2 n × ancho + remanente':>32} {'AASHTO LRFD n × ancho + remanente':>34}")
    for w in (5.0, 5.7, 6.5, 7.2, 10.5, 12.0):
        e, a = notional_lanes_en1991_2(w), design_lanes_aashto_lrfd(w)
        txt_e = "%d × %.2f + %.2f" % (e["n_notional_lanes"], e["notional_lane_width_m"], e["remaining_width_m"])
        txt_a = "%d × %.2f + %.2f" % (a["n_notional_lanes"], a["notional_lane_width_m"], a["remaining_width_m"])
        print(f"  {w:5.1f} {txt_e:>32} {txt_a:>34}")
    print("  EN: 3,0 m por carril desde 6 m; AASHTO: 3,6 m (12 ft) y dos carriles entre 6,0 y 7,2 m.\n")
    y = [0.0, 3.3333, 6.6667, 10.0]
    print(f"Courbon para 4 vigas en y = {[round(v, 2) for v in y]} m (tablero rígido transversalmente):")
    for yl in (1.5, 5.0, 8.5, 10.0):
        eta = courbon_transverse_factors(y, yl)
        print(f"  carga en y = {yl:4.1f} m → η = {[round(v, 3) for v in eta]}; Ση = {sum(eta):.3f}, Ση·y = {sum(e_ * y_ for e_, y_ in zip(eta, y)):.2f} m")
    print("  Con la carga en el borde la viga opuesta recibe η < 0 (levantamiento): la hipótesis de tablero rígido exagera el reparto en tableros flexibles.\n")
    pg = plate_girder_section_props("PG_1500x500x40x16", 1.5, 0.5, 0.04, 0.016, material_name="S355")
    rc = rectangular_concrete_section_props("VIGA_HA_1800x600", 1.8, 0.6, material_name="C35/45")
    print(f"  {'sección':20} {'A [m²]':>8} {'I33 [m⁴]':>9} {'I22 [m⁴]':>9} {'J [m⁴]':>9} {'Av2 [m²]':>8} {'Wel33 [m³]':>10} {'Wpl33 [m³]':>10} {'masa [kg/m]':>11}")
    for s in (pg, rc):
        print(f"  {s.name:20} {s.A_m2:8.4f} {s.I33_m4:9.5f} {s.I22_m4:9.5f} {s.J_m4:9.5f} {s.Av2_m2:8.4f} {s.Wel33_m3:10.5f} {s.Wpl33_m3:10.5f} {s.mass_kg_m:11.1f}")
    print(f"  Viga armada: A = 2·0,5·0,04 + 1,42·0,016 = {2 * 0.5 * 0.04 + 1.42 * 0.016:.4f} m² ✓; Wpl/Wel = {pg.Wpl33_m3 / pg.Wel33_m3:.3f}. Hormigón: J por la fórmula de Saint-Venant para rectángulo, Av = 5/6·A.\n")
    c = expected_grillage_counts(n_spans=2, n_girders=4, n_diaphragms=3)
    print(f"Emparrillado 2 vanos × 4 vigas × 3 diafragmas interiores: {c}")
    print(f"  Comprobación: n_x = 2·4 + 1 = {c['n_x']}, nudos {c['n_x']}·4 = {c['n_joints']}, longitudinales {(c['n_x'] - 1) * 4}, transversales {c['n_x'] * 3}, apoyos 3 líneas × 4 = {c['n_supports']}\n")

    def joints(fixed_x0=True, guide=True, lock_movable=False):
        out = []
        for ix, x in enumerate((0.0, 20.0, 40.0)):
            for ig in range(4):
                ux = (ix == 0) if fixed_x0 else False
                if lock_movable and ix > 0:
                    ux = True
                uy = (ig == 0) if guide else False
                out.append({"id": f"N{ix}_{ig}", "x": x, "y": 3.3333 * ig, "z": 0.0, "restraint": [ux, uy, True, False, False, False]})
        return out

    rep = verify_kinematic_stability(joints())
    print(f"Esquema de apoyos correcto (fijo en x = 0, guía Uy en la viga 0, resto deslizante): estable_3d = {rep['stable_3d']}, GDL {rep['global_dofs']}, Ux coaccionados {rep['n_ux_restrained']}, Uy {rep['n_uy_restrained']}, Uz {rep['n_uz_restrained']}")
    for lbl, kw in (("sin ningún Ux (tablero libre longitudinalmente)", dict(fixed_x0=False)), ("sin ninguna coacción Uy", dict(guide=False)), ("Ux también en las pilas (coacción térmica)", dict(lock_movable=True))):
        try:
            verify_kinematic_stability(joints(**kw))
            print(f"  {lbl}: aceptado")
        except ValueError as exc:
            msg = str(exc)
            if len(msg) > 100:
                msg = msg.split("[")[0] + "[" + str(msg.count("'") // 2) + " nudos]"
            print(f"  {lbl} → ValueError: {msg}")
    print("\nTodo esto corre sin SAP2000: lo que sí necesita fastsap es section_props_from_catalog (perfiles EN 10365), build_bridge_grillage y los bucles de análisis y rediseño. "
          "Los carriles EN con área remanente coinciden con iap11_lane_layout; AASHTO redondea a 3,6 m por carril y no usa área remanente.")


if __name__ == "__main__":
    main()
