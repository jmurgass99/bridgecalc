"""Plano de disposición general del puente (eje, pilas, cotas de luces y rótulo) dibujado a través de un cliente CAD intercambiable: un grabador puro Python que cuenta primitivas por capa y, si ezdxf está instalado, el adaptador que escribe un DXF R2018 en metros que se reabre y audita.

`draw_bridge_layout(client, bridge, style)` solo necesita un objeto con `set_layer`, `draw_polyline`
y `draw_text` (la clase `_DualDXFAndAcadClient` añade `draw_line` y `draw_rect` y acumula también las
expresiones AutoLISP para accoreconsole). Devuelve los conteos de líneas, textos y pilas dibujadas.

Ejecutar:  python examples/autocad_layout_general_arrangement_dxf_via_ezdxf_adapter_and_recorder_client_entity_counts.py
"""
import os
from collections import Counter
from pathlib import Path

from bridgecalc.integration.autocad_layout import LayoutStyle, draw_bridge_layout
from bridgecalc.integration.revit_export import BridgeGeometry, PierGeometry

OUT = Path(os.environ.get("JM_EXAMPLES_OUT_DIR", Path(__file__).resolve().parent / "out"))
OUT.mkdir(parents=True, exist_ok=True)


class Grabador:
    """Cliente CAD mínimo: registra las primitivas por capa sin dibujar nada."""

    def __init__(self) -> None:
        self.capa = "0"
        self.capas: dict[str, int] = {}
        self.primitivas: Counter = Counter()
        self.textos: list[str] = []

    def set_layer(self, name: str, color: int | None = None) -> None:
        self.capa = name
        self.capas[name] = color if color is not None else 7

    def draw_polyline(self, points) -> None:
        self.primitivas[(self.capa, "polyline")] += 1

    def draw_text(self, p, text: str, height: float = 0.35) -> None:
        self.primitivas[(self.capa, "text")] += 1
        self.textos.append(text)


def main() -> None:
    bridge = BridgeGeometry(spans_m=[30.0, 40.0, 30.0], piers=[PierGeometry(30.0, 12.0), PierGeometry(70.0, 14.0)], project_name="Viaducto demo 30+40+30")
    rec = Grabador()
    counts = draw_bridge_layout(rec, bridge, LayoutStyle(text_height_m=0.6))
    print(f"Puente {bridge.spans_m} m con pilas en x = {[p.x_m for p in bridge.piers]} m. draw_bridge_layout → {counts}")
    print(f"  Capas y color: {rec.capas}")
    print(f"  Primitivas por capa: {dict(rec.primitivas)}")
    print(f"  Textos: {rec.textos}")
    rec2 = Grabador()
    c2 = draw_bridge_layout(rec2, BridgeGeometry(spans_m=[20.0, 20.0], project_name="Sin pilas"))
    print(f"  Puente de 2 luces sin pilas declaradas: se sintetiza {c2['piers']} pila a 10 m de altura; textos {rec2.textos}\n")
    try:
        import ezdxf
    except ImportError:
        print("ezdxf no instalado (extra `dxf`): se omite la escritura del DXF; el grabador de arriba ya demuestra la interfaz.")
        return
    from bridgecalc.integration.autocad_layout import _DualDXFAndAcadClient

    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 6
    client = _DualDXFAndAcadClient(doc)
    counts = draw_bridge_layout(client, bridge, LayoutStyle(text_height_m=0.6))
    client.draw_rect(-2.0, -16.0, 102.0, 4.0)
    p = OUT / "viaducto_demo_disposicion_general.dxf"
    doc.saveas(str(p))
    d = ezdxf.readfile(str(p))
    ents = Counter(e.dxftype() for e in d.modelspace())
    print(f"DXF {p.name}: versión {d.dxfversion}, $INSUNITS = {d.header['$INSUNITS']} (6 = metros), entidades {dict(ents)}, capas {[L.dxf.name for L in d.layers if L.dxf.name not in ('0', 'Defpoints')]}")
    print(f"  Conteos del dibujo {counts}; segmentos AutoLISP acumulados: {len(client.line_segments)} líneas y {len(client.texts_list)} textos (para generar un .dwg nativo con accoreconsole cuando exista)")
    ext = d.modelspace().query("LWPOLYLINE")
    xs = [v[0] for e in ext for v in e.get_points(format="xy")]
    print(f"  Extensión en x: {min(xs):.1f} a {max(xs):.1f} m (eje de {sum(bridge.spans_m):.0f} m más el marco)")
    print("\nEl plano es esquemático: eje en planta, pilas como segmentos verticales hacia −z, cotas como polilíneas y texto; sin bloques, estilos de texto ni acotación real. "
          "export_bridge_grillage_drawings añade planta, alzado, sección y cuadros a partir del resultado del bucle de diseño, pero requiere rebardxf y, para el .dwg, AutoCAD con accoreconsole.")


if __name__ == "__main__":
    main()
