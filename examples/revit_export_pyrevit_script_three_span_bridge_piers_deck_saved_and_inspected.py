"""Exportación a Revit: script pyRevit (CPython3) generado para un puente de 30 + 40 + 30 m con dos pilas y tablero de 10 × 1,2 m, guardado en disco e inspeccionado (transacción, familias, parámetros), más el caso sin pilas (se sintetizan en los apoyos interiores).

`BridgeGeometry(spans_m, piers, deck, pier_family, deck.family_name, project_name)` describe el puente;
`to_revit_script` devuelve el código que inserta una FamilyInstance por pila y una por luz dentro de
una Transaction; `save_script` lo escribe. El script requiere las familias BridgeCalc_AdaptivePier
(Height, Width, Depth) y BridgeCalc_Deck (Width, Thickness) cargadas en el proyecto.

Ejecutar:  python examples/revit_export_pyrevit_script_three_span_bridge_piers_deck_saved_and_inspected.py
"""
import os
import re
from pathlib import Path

from bridgecalc.integration.revit_export import BridgeGeometry, DeckGeometry, PierGeometry, save_script, to_revit_script

OUT = Path(os.environ.get("JM_EXAMPLES_OUT_DIR", Path(__file__).resolve().parent / "out"))
OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    bridge = BridgeGeometry(spans_m=[30.0, 40.0, 30.0], piers=[PierGeometry(x_m=30.0, height_m=12.0, width_m=1.8, depth_m=2.5), PierGeometry(x_m=70.0, height_m=14.0, width_m=1.8, depth_m=2.5)],
                            deck=DeckGeometry(width_m=10.0, thickness_m=1.2), project_name="Viaducto demo 30+40+30")
    script = to_revit_script(bridge)
    path = save_script(bridge, OUT / "viaducto_demo_pyrevit.py")
    lines = script.splitlines()
    print(f"Script pyRevit generado: {len(lines)} líneas, {len(script)} caracteres → {Path(path).name}")
    familias = sorted(set(re.findall(r'Family\.Name == "([A-Za-z_]+)"', script)))
    parametros = sorted(set(re.findall(r'LookupParameter\("([A-Za-z]+)"\)', script)))
    spans_txt = re.search(r"SPANS_M = (.*)", script).group(1)
    n_tx = script.count("Transaction(doc")
    n_fi = script.count("NewFamilyInstance")
    print(f"  Transacciones: {n_tx}; NewFamilyInstance: {n_fi} ({len(bridge.piers)} pilas + {len(bridge.spans_m)} tramos de tablero); familias: {familias}")
    print(f"  Parámetros fijados: {parametros}")
    print(f"  SPANS_M = {spans_txt}; cota del tablero = altura de la primera pila ({bridge.piers[0].height_m} m) en todos los tramos")
    print("\nFragmento (pila 2 y tramo 2):")
    start = script.index("# Pier 2")
    for ln in script[start:].splitlines()[:12]:
        print("  | " + ln)
    start = script.index("# Deck span 2")
    for ln in script[start:].splitlines()[:8]:
        print("  | " + ln)
    sin_pilas = BridgeGeometry(spans_m=[25.0, 25.0, 25.0, 25.0], project_name="Sin pilas declaradas")
    s2 = to_revit_script(sin_pilas)
    xs_sint = re.findall(r"# Pier \d+ @ x=([0-9.]+)", s2)
    n_sint = s2.count("# Pier")
    print(f"\nSin pilas declaradas: se sintetizan {n_sint} pilas de 10 m en x = {xs_sint} m")
    print("\nEl script coloca el tablero a la cota de la primera pila en todos los tramos (sin pendiente ni peralte) y usa unidades de proyecto sin convertir a pies: en un proyecto en pies las coordenadas en metros salen mal. "
          "Es un arranque geométrico para pyRevit, no un modelo BIM: sin apoyos, estribos ni armado. Plantilla de botón en integration/pyrevit_scripts/bridgecalc_import.py.")


if __name__ == "__main__":
    main()
