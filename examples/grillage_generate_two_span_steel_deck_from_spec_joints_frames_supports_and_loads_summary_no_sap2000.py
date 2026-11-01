"""Emparrillado completo de un tablero metálico de 2 × 30 m y 10 m de ancho a partir de una especificación trazable (material, viga armada, diafragma, LM1 de EN 1991-2), sin SAP2000: nudos, barras, apoyos, cargas permanentes y de tráfico por viga, posiciones pésimas del vehículo, envolvente analítica y combinaciones.

`BridgeDesignSpec` reúne luz, ancho, vanos, vigas, diafragmas, carriles, norma, materiales y secciones;
`generate_grillage(spec=…)` devuelve `{joints, frames, meta}` con el esquema isostático en planta
(fijo en x = 0, guía Uy en la viga 0), el reparto de Courbon por carril y las cargas puntuales del
tándem sobre las barras. El modelo se guarda como JSON. Con fastsap instalado, `build_bridge_grillage`
lo construye en SAP2000.

Ejecutar:  python examples/grillage_generate_two_span_steel_deck_from_spec_joints_frames_supports_and_loads_summary_no_sap2000.py
"""
import json
import os
from collections import Counter
from pathlib import Path

from bridgecalc.integration.grillage_model import (
    APPLICABLE_LIMIT_STATES,
    MODEL_LIMITATIONS,
    UNIMPLEMENTED_CHECKS,
    BridgeDesignSpec,
    default_bridge_material,
    generate_grillage,
    plate_girder_section_props,
)

OUT = Path(os.environ.get("JM_EXAMPLES_OUT_DIR", Path(__file__).resolve().parent / "out"))
OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    mat = default_bridge_material("acero", "EN_1991_2")
    girder = plate_girder_section_props("PG_1500x500x40x16", 1.5, 0.5, 0.04, 0.016, material_name=mat.name)
    diaph = plate_girder_section_props("PG_800x300x25x12", 0.8, 0.3, 0.025, 0.012, material_name=mat.name)
    spec = BridgeDesignSpec(span_m=30.0, width_m=10.0, n_spans=2, n_girders=4, n_diaphragms=5, n_lanes=3, norma="EN_1991_2", uso="carretera",
                            apoyos_desc="estribo fijo en x=0, pila y estribo móviles", galibo_m=5.3, acciones_desc="LM1 EN 1991-2 + DW", slab_thickness_m=0.25,
                            wearing_surface_kPa=2.0, barrier_load_kN_m_total=5.0, material=mat, girder_section=girder, diaphragm_section=diaph)
    g = generate_grillage(n_spans=2, span_length=30.0, n_girders=4, girder_spacing=10.0 / 3.0, divisions_per_span=6, spec=spec)
    meta = g["meta"]
    print(f"Material {mat.name} ({mat.norm_ref}): E = {mat.E_kPa / 1e6:.0f} GPa, f_y = {mat.fy_MPa:.0f} MPa, γ = {mat.gamma_kN_m3} kN/m³")
    print(f"Vigas {girder.name} ({girder.mass_kg_m:.0f} kg/m, I33 = {girder.I33_m4:.4f} m⁴), diafragmas {diaph.name} ({diaph.mass_kg_m:.0f} kg/m)")
    print(f"\nEmparrillado: {len(g['joints'])} nudos, {len(g['frames'])} barras ({Counter(f['role'] for f in g['frames'])}); recuentos derivados {meta['derived_counts']}")
    apoyos = [j for j in g["joints"] if j["restraint"] is not None]
    print(f"  Apoyos: {len(apoyos)} nudos en x = {sorted({j['x'] for j in apoyos})}; coacciones [Ux,Uy,Uz,Rx,Ry,Rz]: " + "; ".join(f"{j['id']} {j['restraint'][:3]}" for j in apoyos if j["x"] in (0.0, 30.0) and j["y"] < 4.0))
    print(f"  Estabilidad: {meta['kinematic_stability']['global_dofs']}, dilatación longitudinal libre en móviles = {meta['kinematic_stability']['longitudinal_expansion_free_at_movable']}")
    ls = meta["loads_summary"]
    print(f"\nCargas ({ls['traffic_code']}, IM = {ls['impact_factor_IM']}): losa 0,25 m → {ls['q_slab_per_girder_kN_m']} kN/m por viga; DW (2 kPa + 5 kN/m de barreras) → {ls['q_dw_per_girder_kN_m']} kN/m por viga")
    for strip in ls["notional_lanes_detail"]["strips"]:
        print(f"  {strip['strip_id']:14} y = {strip['y_start_m']:.1f}–{strip['y_end_m']:.1f} m, UDL {strip['udl_kN_m']:.1f} kN/m, tándem {strip['ts_axle_kN']:.0f} kN/eje, Courbon {strip['courbon_factors']}")
    print(f"  Carril repartido por viga (Courbon, carriles desde el borde y = 0): {ls['q_lane_by_girder_kN_m']} kN/m (total {ls['transverse_distribution']['q_lane_total_kN_m']} kN/m)")
    print(f"  Vehículo para M⁺: ejes {ls['vehicle_axles_M_kN']} kN en x = {ls['vehicle_positions_M_m']} m (Barré en el vano 1); para V: en x = {ls['vehicle_positions_V_m']} m (desfase {ls['support_shear_offset_m']} m para no caer en el nudo)")
    print(f"  Reparto del eje entre vigas: {ls['transverse_distribution']['vehicle_axle_share_by_girder']}; viga exterior gobernante {ls['transverse_distribution']['governing_exterior_girder']}")
    print(f"  Envolvente analítica de viga simple (comprobación): M = {ls['analytical_envelope_M_kNm']:.0f} kN·m, V = {ls['analytical_envelope_V_kN']:.0f} kN")
    print(f"  Cargas puntuales LIVE_VEHICLE_M: {len(ls['frame_point_loads_LIVE_VEHICLE_M'])} sobre barras, p. ej. {ls['frame_point_loads_LIVE_VEHICLE_M'][0]}")
    combos = ls["combinations"]
    print(f"  Combinaciones ({len(combos)}): " + "; ".join(f"{k}: {v}" for k, v in (combos.items() if isinstance(combos, dict) else enumerate(combos)))[:600])
    p = OUT / "grillage_2x30_steel.json"
    p.write_text(json.dumps(g, indent=1, default=str), encoding="utf-8")
    print(f"\nModelo guardado: {p.name} ({p.stat().st_size / 1024:.0f} kB)")
    print(f"\nLimitaciones declaradas en meta ({len(MODEL_LIMITATIONS)}): " + " | ".join(l[:90] + "…" for l in MODEL_LIMITATIONS))
    print(f"Estados límite aplicables ({len(APPLICABLE_LIMIT_STATES)}) y comprobaciones no implementadas ({len(UNIMPLEMENTED_CHECKS)}): torsión/alabeo, abolladura, conectores, fatiga, aparatos de apoyo quedan fuera.")
    print("\nSin spec, generate_grillage pide perfiles del catálogo EN 10365 de fastsap (HEM 1000 / HEB 400) y falla sin él; con spec y secciones calculadas aquí corre en puro Python. El tándem se aplica en posiciones discretas (M⁺ en el vano 1, V en x = 0+), no como carga móvil.")


if __name__ == "__main__":
    main()
