"""Memoria de cálculo LRFD HL-93 Strength I paso a paso: LaTeX (con handcalcs si está instalado, si no el LaTeX manual) y Markdown guardados en fichero, y la memoria ligera `generar_memoria_hl93`, que desde 1.1.0 usa el barrido exacto del camión en lugar de la fórmula 145·L/4 − 145·4,3/2.

`generar_memoria_handcalcs` calcula M_DC, M_DW, camión, tándem, carril, IM y la combinación
1,25·DC + 1,50·DW + 1,75·(LL+IM) y los renderiza; `generar_memoria_hl93` da el mismo resultado en
Markdown. Se escriben `memoria_hl93_30m.tex` y `.md` en examples/out (o JM_EXAMPLES_OUT_DIR).

Ejecutar:  python examples/memo_hl93_handcalcs_strength_i_latex_markdown_saved_to_file_and_legacy_memo_now_exact.py
"""
import os
from pathlib import Path

from bridgecalc.loads.hl93 import hl93_envelope
from bridgecalc.memos import HL93HandcalcsInput, HL93MemoInput, generar_memoria_handcalcs, generar_memoria_hl93

OUT = Path(os.environ.get("JM_EXAMPLES_OUT_DIR", Path(__file__).resolve().parent / "out"))
OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    inp = HL93HandcalcsInput(L_span_m=30.0, n_lanes=2, DC_kN_m=25.0, DW_kN_m=5.0)
    r = generar_memoria_handcalcs(inp)
    print(f"Memoria handcalcs L = 30 m, DC 25 kN/m, DW 5 kN/m, IM 33 %, MPF 1,0:")
    print(f"  M_DC = {r.M_DC_kNm:.1f}, M_DW = {r.M_DW_kNm:.1f}, M_camión = {r.M_truck_kNm:.1f}, M_tándem = {r.M_tandem_kNm:.1f} (gobierna {r.governing_vehicle}), M_carril = {r.M_lane_kNm:.1f} kN·m")
    print(f"  M_LL+IM = (máx·{r.IM:.2f} + carril)·MPF = {r.M_LL_IM_kNm:.1f}; M_u = 1,25·{r.M_DC_kNm:.0f} + 1,50·{r.M_DW_kNm:.0f} + 1,75·{r.M_LL_IM_kNm:.0f} = {r.M_Strength_I_kNm:.1f} kN·m")
    motor = {"handcalcs": "LaTeX renderizado por handcalcs", "manual": "LaTeX manual de respaldo (handcalcs no instalado)"}[r.latex_engine]
    tex, md = OUT / "memoria_hl93_30m.tex", OUT / "memoria_hl93_30m.md"
    tex.write_text(r.latex, encoding="utf-8")
    md.write_text(r.markdown, encoding="utf-8")
    print(f"  {motor}; {len(r.latex)} caracteres de LaTeX → {tex.name}; {len(r.markdown)} de Markdown → {md.name}")
    print("\nLaTeX generado (primeras líneas):")
    for line in r.latex.strip().splitlines()[:8]:
        print("  | " + line)
    print("\nMarkdown generado:")
    for line in r.markdown.strip().splitlines():
        print("  | " + line)
    e = hl93_envelope(30.0)
    print(f"\nComprobación cruzada con hl93_envelope: camión {e['M_truck_kNm']:.1f} (memoria {r.M_truck_kNm:.1f}, barrido propio de 80 posiciones: {(r.M_truck_kNm / e['M_truck_kNm'] - 1) * 100:+.2f} %), tándem {e['M_tandem_kNm']:.1f} frente a {r.M_tandem_kNm:.1f}")
    m = generar_memoria_hl93(HL93MemoInput(L_span_m=30.0))
    viejo = 145.0 * 30.0 / 4.0 - 145.0 * 4.3 / 2.0
    print(f"\nMemoria ligera generar_memoria_hl93: camión {m.M_truck_kNm:.1f}, tándem {m.M_tandem_kNm:.1f} (gobierna {m.governing_vehicle}), carril {m.M_lane_kNm:.2f} (9,34 kN/m), M_u = {m.M_Strength_I_kNm:.1f} kN·m")
    print(f"  Hasta 1.0 el camión salía de 145·L/4 − 145·4,3/2 = {viejo:.2f} kN·m, {(viejo / m.M_truck_kNm - 1) * 100:+.0f} % frente al barrido, con carril de 9,3 y sin tándem: M_u habría sido {1.25 * m.M_DC_kNm + 1.5 * m.M_DW_kNm + 1.75 * (viejo * 1.33 + 9.3 * 900 / 8):.0f} en vez de {m.M_Strength_I_kNm:.0f} kN·m ({(1.25 * m.M_DC_kNm + 1.5 * m.M_DW_kNm + 1.75 * (viejo * 1.33 + 9.3 * 900 / 8)) / m.M_Strength_I_kNm * 100 - 100:+.0f} %).")
    print("\nLas dos memorias son por carril sin factor de distribución ni presencia múltiple (MPF = 1,0 por defecto): el M_u impreso es el de un carril entero, no el de una viga. Para una viga, multiplica M_LL+IM por g antes o pasa MPF = g.")


if __name__ == "__main__":
    main()
