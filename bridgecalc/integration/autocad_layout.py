"""
Genera layout AutoCAD del puente: líneas de proyección + cotas + nombres de cepas.

Wrappa `rebardxf.integration.autocad_live.AutoCADClient` si está disponible
(DXFStructuralJm es opcional). Si no, expone una API equivalente que acepta el
mock para tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .revit_export import BridgeGeometry, PierGeometry


@dataclass(frozen=True)
class LayoutStyle:
    line_color: int = 7        # blanco/negro
    dim_color: int = 3         # verde
    pier_color: int = 1        # rojo
    text_height_m: float = 0.5
    elevation_z: float = 0.0


def draw_bridge_layout(client: Any, bridge: BridgeGeometry, style: LayoutStyle | None = None) -> dict[str, int]:
    """
    Dibuja el layout del puente en AutoCAD usando `client` (AutoCADClient o mock
    con la misma interfaz).

    Devuelve un dict con conteos de entidades dibujadas (útil para tests).
    """
    st = style or LayoutStyle()
    counts = {"lines": 0, "texts": 0, "piers": 0}

    # eje del puente
    x_total = sum(bridge.spans_m)
    client.set_layer("BR-AXIS", color=st.line_color)
    client.draw_polyline([(0.0, 0.0), (x_total, 0.0)])
    counts["lines"] += 1

    # piers (sintetiza si vienen vacías)
    piers = list(bridge.piers)
    if not piers:
        x = 0.0
        for span in bridge.spans_m[:-1]:
            x += span
            piers.append(PierGeometry(x_m=x, height_m=10.0))

    client.set_layer("BR-PIER", color=st.pier_color)
    for i, pier in enumerate(piers, start=1):
        x = pier.x_m
        # línea vertical de la cepa
        client.draw_polyline([(x, 0.0), (x, -pier.height_m)])
        counts["lines"] += 1
        client.draw_text((x, -pier.height_m - st.text_height_m * 2),
                         f"P{i}", height=st.text_height_m)
        counts["texts"] += 1
        counts["piers"] += 1

    # cotas (longitudes de luces)
    client.set_layer("BR-DIMS", color=st.dim_color)
    x_cum = 0.0
    for i, span in enumerate(bridge.spans_m, start=1):
        x_start = x_cum
        x_end = x_cum + span
        y_dim = st.text_height_m * 3
        client.draw_polyline([(x_start, y_dim), (x_end, y_dim)])
        counts["lines"] += 1
        client.draw_text(((x_start + x_end) / 2, y_dim + st.text_height_m * 0.5),
                         f"L{i}={span:.2f} m", height=st.text_height_m)
        counts["texts"] += 1
        x_cum = x_end

    # rótulo general
    client.set_layer("BR-TITLE", color=st.line_color)
    client.draw_text((x_total / 2, -max(p.height_m for p in piers) - st.text_height_m * 6 if piers else 0),
                     bridge.project_name, height=st.text_height_m * 1.5)
    counts["texts"] += 1

    return counts


class _DualDXFAndAcadClient:
    """Adaptador CAD que recibe primitivas de `draw_bridge_layout` y de las vistas de planta,
    alzado, sección transversal y cuadros técnicos del puente, escribiéndolas simultáneamente en:
    1) Un documento `ezdxf` R2018 (en metros, `INSUNITS = 6`).
    2) Una lista de expresiones AutoLISP `(entmake ...)` deterministas para generar y reabrir un
       archivo nativo `.dwg` mediante `accoreconsole.exe` cuando esté disponible.
    """

    def __init__(self, doc: Any) -> None:
        self.doc = doc
        self.msp = doc.modelspace()
        self.current_layer = "0"
        self.layers_color: dict[str, int] = {}
        self.line_segments: list[tuple[str, tuple[float, float, float], tuple[float, float, float]]] = []
        self.texts_list: list[tuple[str, tuple[float, float, float], float, str]] = []

    def set_layer(self, name: str, color: int | None = None) -> None:
        col = int(color) if color is not None else 7
        self.current_layer = name
        self.layers_color[name] = col
        if name not in self.doc.layers:
            self.doc.layers.add(name=name, color=col)
        else:
            self.doc.layers.get(name).color = col

    def draw_polyline(self, points: Sequence[Sequence[float]]) -> None:
        pts_2d = [(float(p[0]), float(p[1])) for p in points]
        if len(pts_2d) < 2:
            return
        self.msp.add_lwpolyline(pts_2d, dxfattribs={"layer": self.current_layer})
        for idx in range(len(pts_2d) - 1):
            p1 = (pts_2d[idx][0], pts_2d[idx][1], 0.0)
            p2 = (pts_2d[idx + 1][0], pts_2d[idx + 1][1], 0.0)
            if p1 != p2:
                self.line_segments.append((self.current_layer, p1, p2))

    def draw_line(self, p1: Sequence[float], p2: Sequence[float]) -> None:
        a = (float(p1[0]), float(p1[1]))
        b = (float(p2[0]), float(p2[1]))
        if a == b:
            return
        self.msp.add_line(a, b, dxfattribs={"layer": self.current_layer})
        self.line_segments.append((self.current_layer, (a[0], a[1], 0.0), (b[0], b[1], 0.0)))

    def draw_rect(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.draw_polyline([(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)])

    def draw_text(self, p: Sequence[float], text: str, height: float = 0.35) -> None:
        x, y = float(p[0]), float(p[1])
        h = max(0.05, float(height))
        clean_txt = str(text).replace("\r", " ").replace("\n", " ")
        ent = self.msp.add_text(clean_txt, dxfattribs={"layer": self.current_layer, "height": h})
        ent.set_placement((x, y))
        self.texts_list.append((self.current_layer, (x, y, 0.0), h, clean_txt))


def _sanitize_lisp_str(s: str) -> str:
    """Escapa comillas y convierte caracteres no-ASCII para que accoreconsole (AutoLISP) no falle."""
    repl = (
        ("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"),
        ("Á", "A"), ("É", "E"), ("Í", "I"), ("Ó", "O"), ("Ú", "U"),
        ("ñ", "n"), ("Ñ", "N"), ("§", "sec."), ("≤", "<="), ("≥", ">="),
        ("×", "x"), ("·", "*"), ("\"", "'"), ("\\", "/"),
    )
    out = s
    for k, v in repl:
        out = out.replace(k, v)
    return "".join(ch if 32 <= ord(ch) < 127 else "_" for ch in out)


def _build_accore_dwg(
    client: _DualDXFAndAcadClient,
    out_dir: Any,
    base_name: str,
    *,
    accore_path: Any,
    timeout: int = 180,
) -> dict[str, Any]:
    """Ejecuta accoreconsole.exe en dos sesiones independientes:
    1. Crea las capas, segmentos LINE y entidades TEXT y guarda `<base_name>.dwg` (R2018).
    2. Reabre `<base_name>.dwg` desde disco en una sesion limpia, cuenta LINE y TEXT reabiertos
       y traza `<base_name>_AutoCAD.png`.
    """
    import re
    import subprocess
    from pathlib import Path

    out_p = Path(out_dir).resolve()
    dwg_p = out_p / f"{base_name}.dwg"
    if dwg_p.exists():
        dwg_p.unlink()

    w_dir = str(out_p).replace("\\", "/")
    create_lines = [
        '(setvar "CMDECHO" 0)',
        '(setvar "INSUNITS" 6)',
        '(setvar "FILEDIA" 0)',
    ]
    for lay_name, col in sorted(client.layers_color.items()):
        safe_lay = _sanitize_lisp_str(lay_name)
        create_lines.append(
            f'(entmake (list (cons 0 "LAYER") (cons 100 "AcDbSymbolTableRecord") '
            f'(cons 100 "AcDbLayerTableRecord") (cons 2 "{safe_lay}") (cons 70 0) (cons 62 {max(1, min(255, col))})))'
        )
    for lay_name, p1, p2 in client.line_segments:
        safe_lay = _sanitize_lisp_str(lay_name)
        create_lines.append(
            f'(entmake (list (cons 0 "LINE") (cons 8 "{safe_lay}") '
            f'(list 10 {p1[0]:.6f} {p1[1]:.6f} {p1[2]:.6f}) '
            f'(list 11 {p2[0]:.6f} {p2[1]:.6f} {p2[2]:.6f})))'
        )
    for lay_name, pt, h, txt in client.texts_list:
        safe_lay = _sanitize_lisp_str(lay_name)
        safe_txt = _sanitize_lisp_str(txt)
        create_lines.append(
            f'(entmake (list (cons 0 "TEXT") (cons 8 "{safe_lay}") '
            f'(list 10 {pt[0]:.6f} {pt[1]:.6f} {pt[2]:.6f}) '
            f'(cons 40 {h:.6f}) (cons 1 "{safe_txt}")))'
        )

    create_lines += [
        '(princ (strcat "\\nCREADAS_LINE=" (itoa (sslength (ssget "X" (list (cons 0 "LINE")))))))',
        '(princ (strcat "\\nCREADAS_TEXT=" (itoa (sslength (ssget "X" (list (cons 0 "TEXT")))))))',
        '(command "_ZOOM" "_E")',
        f'(command "_SAVEAS" "2018" "{w_dir}/{base_name}.dwg")',
        "_QUIT",
        "",
    ]

    verify_lines = [
        '(setvar "CMDECHO" 0)',
        '(setvar "FILEDIA" 0)',
        '(princ (strcat "\\nREABIERTO_LINE=" (itoa (sslength (ssget "X" (list (cons 0 "LINE")))))))',
        '(princ (strcat "\\nREABIERTO_TEXT=" (itoa (sslength (ssget "X" (list (cons 0 "TEXT")))))))',
        '(command "_ZOOM" "_E")',
        '(command "_-PLOT" "_Y" "Model" "PublishToWeb PNG.pc3" "Sun Hi-Res (1600.00 x 1280.00 Pixels)" '
        f'"_L" "_N" "_E" "_F" "_C" "_Y" "acad.ctb" "_Y" "_N" "{w_dir}/{base_name}_AutoCAD.png" "_N" "_Y")',
        "_QUIT",
        "_Y",
        "",
    ]

    scr_create = out_p / f"_{base_name}_crear.scr"
    scr_verify = out_p / f"_{base_name}_verificar.scr"
    scr_create.write_text("\n".join(create_lines), encoding="utf-8")
    scr_verify.write_text("\n".join(verify_lines), encoding="utf-8")

    def _run_accore(args: list[str]) -> str:
        r = subprocess.run([str(accore_path)] + args + ["/l", "en-US"], capture_output=True, timeout=timeout)
        raw = r.stdout + r.stderr
        return raw.decode("utf-16-le", errors="ignore") if b"\x00" in raw[:400] else raw.decode("utf-8", errors="ignore")

    log1 = _run_accore(["/s", str(scr_create)])
    log2 = _run_accore(["/i", str(dwg_p), "/s", str(scr_verify)]) if dwg_p.exists() else ""
    (out_p / f"_{base_name}_acad.log").write_text(log1 + "\n=====\n" + log2, encoding="utf-8")

    c_line = re.findall(r"CREADAS_LINE=(\d+)", log1)
    r_line = re.findall(r"REABIERTO_LINE=(\d+)", log2)
    c_text = re.findall(r"CREADAS_TEXT=(\d+)", log1)
    r_text = re.findall(r"REABIERTO_TEXT=(\d+)", log2)

    n_line_c = int(c_line[-1]) if c_line else 0
    n_line_r = int(r_line[-1]) if r_line else 0
    n_text_c = int(c_text[-1]) if c_text else 0
    n_text_r = int(r_text[-1]) if r_text else 0

    ok_dwg = (
        dwg_p.exists()
        and dwg_p.stat().st_size > 1000
        and n_line_c == len(client.line_segments)
        and n_line_r == n_line_c
        and n_text_c == len(client.texts_list)
        and n_text_r == n_text_c
    )
    png_p = out_p / f"{base_name}_AutoCAD.png"
    return {
        "verified_via_accoreconsole": True,
        "accoreconsole_path": str(accore_path),
        "dwg_path": str(dwg_p),
        "dwg_size_bytes": dwg_p.stat().st_size if dwg_p.exists() else 0,
        "png_path": str(png_p) if png_p.exists() else None,
        "lines_expected": len(client.line_segments),
        "lines_created": n_line_c,
        "lines_reopened": n_line_r,
        "texts_expected": len(client.texts_list),
        "texts_created": n_text_c,
        "texts_reopened": n_text_r,
        "veredicto": "OK" if ok_dwg else "REQUIERE_REVISION",
    }


def export_bridge_grillage_drawings(
    design_result: dict[str, Any],
    out_dir: str | Any,
    *,
    base_name: str = "puente_disposicion_general",
    generate_native_dwg: bool = True,
) -> dict[str, Any]:
    """Genera los planos esquemáticos de disposición general y predimensionamiento verificado
    a partir del resultado definitivo del bucle de puente (`design_result`), reutilizando
    `draw_bridge_layout` y `rebardxf.export.{save_dxf, verify}`.

    - Obtiene TODOS los datos geométricos, secciones asignadas, materiales, apoyos,
      verificaciones ULS/SLS, DCRs, estado global y salvedades directamente de `design_result`,
      sin duplicar ni inventar valores.
    - Genera siempre `<base_name>.dxf` (R2018), lo reabre con `ezdxf.readfile` y lo audita.
    - Cuando `generate_native_dwg=True` y existe `accoreconsole.exe` (AutoCAD 2026), genera
      también `<base_name>.dwg` nativo y lo reabre en una segunda sesión verificando recuentos.
    """
    from pathlib import Path
    import ezdxf
    from rebardxf.export import save_dxf, verify as verify_dxf
    from .revit_export import DeckGeometry

    out_p = Path(out_dir).expanduser().resolve()
    out_p.mkdir(parents=True, exist_ok=True)

    meta = design_result["meta"]
    fv = design_result.get("final_verification") or design_result
    span_m = float(meta["span_length"])
    total_len_m = float(meta["total_length"])
    width_m = float(meta["width_m"])
    n_spans = int(meta["n_spans"])
    n_girders = int(meta["n_girders"])
    girder_spacing_m = float(meta["girder_spacing"])
    div_per_span = int(meta.get("divisions_per_span") or meta["derived_counts"]["divisions_per_span"])
    n_diaph_int = int(meta.get("n_diaphragms", max(0, div_per_span - 1)))
    dx_diaph_m = span_m / max(1, div_per_span)
    clearance_m = float(meta.get("clearance_m") or 5.5)

    final_girder_sec = str(
        design_result.get("final_girder_section")
        or fv.get("girder_section")
        or list(meta["sections"].keys())[0]
    )
    final_diaph_sec = str(
        design_result.get("final_diaphragm_section")
        or fv.get("diaphragm_section")
        or list(meta["sections"].keys())[-1]
    )
    g_props = meta["sections"][final_girder_sec]
    d_props = meta["sections"].get(final_diaph_sec, g_props)
    mat = meta["material"]
    g_cap = fv.get("girder_capacities", {})

    doc = ezdxf.new(dxfversion="R2018")
    doc.header["$INSUNITS"] = 6  # Metros
    client = _DualDXFAndAcadClient(doc)

    # 1) ALZADO LONGITUDINAL (origen en Y = 0..8 m): reutiliza draw_bridge_layout
    spans_list = [span_m] * n_spans
    abutment_piers = [
        PierGeometry(x_m=0.0, height_m=clearance_m),
        PierGeometry(x_m=total_len_m, height_m=clearance_m),
    ]
    bridge_geom = BridgeGeometry(
        spans_m=spans_list,
        piers=abutment_piers,
        deck=DeckGeometry(width_m=width_m, thickness_m=float(g_props["h_m"])),
        project_name=(
            f"PUENTE METALICO EMPARRILLADO L={total_len_m:.2f} m x W={width_m:.2f} m "
            f"- VIGA {final_girder_sec} / DIAF {final_diaph_sec}"
        ),
    )
    style = LayoutStyle(text_height_m=0.40, elevation_z=0.0)
    base_layout_counts = draw_bridge_layout(client, bridge_geom, style=style)

    # Completar alzado con canto real de la viga armada y losa superior + simbolos de apoyos fijo/movil
    h_girder_m = float(g_props["h_m"])
    slab_t_m = float(meta["loads_summary"].get("slab_thickness_m", 0.25))
    client.set_layer("BR-GIRDER", color=4)
    client.draw_rect(0.0, 0.0, total_len_m, h_girder_m)
    client.draw_rect(0.0, h_girder_m, total_len_m, h_girder_m + slab_t_m)
    # Posiciones de rigidizadores/diafragmas en alzado
    client.set_layer("BR-DIAPHRAGM", color=6)
    for ix in range(div_per_span + 1):
        x_d = ix * dx_diaph_m
        client.draw_line((x_d, 0.0), (x_d, h_girder_m))

    client.set_layer("BR-SUPPORT", color=2)
    # Triangulo de apoyo fijo en x = 0.0 m
    client.draw_polyline([(-0.4, -0.5), (0.4, -0.5), (0.0, 0.0), (-0.4, -0.5)])
    client.draw_text((-1.5, -1.1), "Apoyo Fijo (x=0.00 m: U1,U2,U3)", height=0.32)
    # Triangulo + rodillo de apoyo movil en x = L
    client.draw_polyline([(total_len_m - 0.4, -0.5), (total_len_m + 0.4, -0.5), (total_len_m, 0.0), (total_len_m - 0.4, -0.5)])
    client.draw_line((total_len_m - 0.5, -0.65), (total_len_m + 0.5, -0.65))
    client.draw_text((total_len_m - 2.5, -1.1), f"Apoyo Movil (x={total_len_m:.2f} m: U3 + Guia U2)", height=0.32)

    client.set_layer("BR-DIMS", color=3)
    client.draw_text((total_len_m / 2.0 - 3.5, h_girder_m + slab_t_m + 0.45),
                     f"ALZADO LONGITUDINAL: Luz L = {total_len_m:.2f} m | Canto viga h = {h_girder_m*1000:.0f} mm + Losa {slab_t_m*1000:.0f} mm | Galibo = {clearance_m:.2f} m",
                     height=0.35)

    # 2) PLANTA DEL EMPARRILLADO (desplazada en Y_offset = +10.0 m .. +20.0 m)
    y_plan_0 = 10.0
    client.set_layer("BR-TITLE", color=7)
    client.draw_text((0.0, y_plan_0 + width_m + 1.4),
                     f"PLANTA DE DISPOSICION DEL EMPARRILLADO ({n_girders} VIGAS {final_girder_sec} + {div_per_span + 1} EJES DIAFRAGMA {final_diaph_sec})",
                     height=0.42)

    # Dibujar los 16 segmentos de viga longitudinal reales del modelo
    client.set_layer("BR-GIRDER", color=4)
    for ig in range(n_girders):
        y_g = y_plan_0 + ig * girder_spacing_m
        for ix in range(div_per_span):
            x1 = ix * dx_diaph_m
            x2 = (ix + 1) * dx_diaph_m
            client.draw_line((x1, y_g), (x2, y_g))
            client.draw_text(
                ((x1 + x2) / 2.0 - 0.9, y_g + 0.15),
                f"L{ix}_{ig} ({final_girder_sec})",
                height=0.22,
            )

    # Dibujar los 15 segmentos de diafragma transversal reales del modelo
    client.set_layer("BR-DIAPHRAGM", color=6)
    for ix in range(div_per_span + 1):
        x_d = ix * dx_diaph_m
        for ig in range(n_girders - 1):
            y1 = y_plan_0 + ig * girder_spacing_m
            y2 = y_plan_0 + (ig + 1) * girder_spacing_m
            client.draw_line((x_d, y1), (x_d, y2))
            client.draw_text(
                (x_d + 0.12, (y1 + y2) / 2.0),
                f"T{ix}_{ig} ({final_diaph_sec})",
                height=0.20,
            )

    # Dibujar los 8 apoyos en planta (fijos en x=0, moviles/guiados en x=L)
    client.set_layer("BR-SUPPORT", color=2)
    for ig in range(n_girders):
        y_g = y_plan_0 + ig * girder_spacing_m
        # Estribo fijo x = 0
        client.draw_rect(-0.25, y_g - 0.25, 0.25, y_g + 0.25)
        lbl_0 = "N0_0 (Fijo U1,U2,U3)" if ig == 0 else f"N0_{ig} (Fijo U1,U3)"
        client.draw_text((-3.6, y_g - 0.10), lbl_0, height=0.22)
        # Estribo movil x = L
        client.draw_rect(total_len_m - 0.25, y_g - 0.25, total_len_m + 0.25, y_g + 0.25)
        lbl_L = f"N{div_per_span}_0 (Movil Guia U2,U3)" if ig == 0 else f"N{div_per_span}_{ig} (Movil Libre U3)"
        client.draw_text((total_len_m + 0.45, y_g - 0.10), lbl_L, height=0.22)

    # Cotas de planta (ancho total W y separaciones de vigas y diafragmas)
    client.set_layer("BR-DIMS", color=3)
    client.draw_line((-1.0, y_plan_0), (-1.0, y_plan_0 + width_m))
    client.draw_text((-2.8, y_plan_0 + width_m / 2.0), f"Ancho W = {width_m:.2f} m ({n_girders - 1}x{girder_spacing_m:.2f} m)", height=0.28)
    for ix in range(div_per_span):
        x1 = ix * dx_diaph_m
        x2 = (ix + 1) * dx_diaph_m
        client.draw_line((x1, y_plan_0 - 0.8), (x2, y_plan_0 - 0.8))
        client.draw_text(((x1 + x2) / 2.0 - 0.8, y_plan_0 - 1.25), f"{dx_diaph_m:.2f} m", height=0.25)

    # 3) DETALLE DE SECCION TRANSVERSAL DE VIGA PRINCIPAL Y DIAFRAGMA (en X = 36 m, Y = 10 m, escala 2x)
    x_sec_0 = total_len_m + 7.5
    y_sec_0 = y_plan_0
    scale_sec = 2.5
    h_s = float(g_props["h_m"]) * scale_sec
    b_s = float(g_props["b_m"]) * scale_sec
    tf_s = float(g_props["tf_m"]) * scale_sec
    tw_s = float(g_props["tw_m"]) * scale_sec
    client.set_layer("BR-SECTION", color=5)
    # Ala inferior, ala superior y alma de la viga armada PG_*
    client.draw_rect(x_sec_0, y_sec_0, x_sec_0 + b_s, y_sec_0 + tf_s)
    client.draw_rect(x_sec_0, y_sec_0 + h_s - tf_s, x_sec_0 + b_s, y_sec_0 + h_s)
    client.draw_rect(
        x_sec_0 + 0.5 * (b_s - tw_s),
        y_sec_0 + tf_s,
        x_sec_0 + 0.5 * (b_s + tw_s),
        y_sec_0 + h_s - tf_s,
    )
    client.set_layer("BR-DIMS", color=3)
    client.draw_text(
        (x_sec_0, y_sec_0 + h_s + 0.45),
        f"SECCION VIGA: {final_girder_sec} (h={float(g_props['h_m'])*1000:.0f} mm, b={float(g_props['b_m'])*1000:.0f} mm, "
        f"tf={float(g_props['tf_m'])*1000:.0f} mm, tw={float(g_props['tw_m'])*1000:.0f} mm)",
        height=0.28,
    )
    client.draw_text(
        (x_sec_0, y_sec_0 - 0.55),
        f"SECCION DIAFRAGMA: {final_diaph_sec} (h={float(d_props['h_m'])*1000:.0f} mm, b={float(d_props['b_m'])*1000:.0f} mm, "
        f"tf={float(d_props['tf_m'])*1000:.0f} mm, tw={float(d_props['tw_m'])*1000:.0f} mm)",
        height=0.26,
    )

    # 4) CUADRO DE PERFILES, MATERIALES Y UNIDADES (X = 0 m, Y = -12.5 m)
    y_tbl = -clearance_m - 4.5
    client.set_layer("BR-TABLE", color=7)
    client.draw_rect(0.0, y_tbl - 5.2, 19.5, y_tbl + 0.6)
    table_lines = [
        "CUADRO DE MATERIALES Y SECCIONES DEFINITIVAS (UNIDADES: kN, m, MPa)",
        f"Material Estructural: {mat['name']} | E = {float(mat['E_kPa'])/1000.0:.0f} MPa | fy,nom = {float(mat['fy_MPa']):.0f} MPa | fy,eff = {float(g_cap.get('fy_effective_MPa', mat['fy_MPa'])):.0f} MPa | gamma = {float(mat['gamma_kN_m3']):.1f} kN/m3",
        f"Vigas Longitudinales (16 tramos / 4 vigas): {final_girder_sec} | A = {float(g_props['A_m2']):.5f} m2 | I33 = {float(g_props['I33_m4']):.6f} m4 | Wpl33 = {float(g_props['Wpl33_m3']):.6f} m3",
        f"Diafragmas Transversales (15 tramos / 5 ejes): {final_diaph_sec} | A = {float(d_props['A_m2']):.5f} m2 | I33 = {float(d_props['I33_m4']):.6f} m4 | Wpl33 = {float(d_props['Wpl33_m3']):.6f} m3",
        f"Iteraciones de Redimensionamiento Ejecutadas en SAP2000: {design_result.get('n_iterations', 1)} ({design_result.get('initial_girder_section', final_girder_sec)} -> {final_girder_sec})",
        "ALCANCE DEL PLANO: PLANO ESQUEMATICO DE DISPOSICION GENERAL Y PREDIMENSIONAMIENTO VERIFICADO (NO CONSTRUCTIVO DE TALLER)",
    ]
    for idx, line in enumerate(table_lines):
        client.draw_text((0.3, y_tbl - idx * 0.78), line, height=0.26)

    # 5) CUADRO DE VERIFICACIONES ULS/SLS, ESTADO CANONICO Y SALVEDADES (X = 20.5 m, Y = y_tbl)
    x_ver = 20.5
    checks = fv.get("checks", [])
    unimpl = design_result.get("unimplemented_checks") or fv.get("unimplemented_checks", [])
    impl_status = str(design_result.get("implemented_checks_status") or fv.get("implemented_checks_status", "NO_CALCULADO"))
    calc_status = str(design_result.get("calculation_status") or fv.get("calculation_status", "NO_CALCULADO"))

    client.set_layer("BR-VERIF", color=3)
    box_h = max(6.5, (len(checks) + len(unimpl) + 5) * 0.55)
    client.draw_rect(x_ver, y_tbl - box_h, x_ver + 24.0, y_tbl + 0.6)
    client.draw_text(
        (x_ver + 0.3, y_tbl),
        f"RESUMEN DE VERIFICACIONES NORMATIVAS ({fv.get('norma', 'EN_1991_2')})",
        height=0.28,
    )
    y_cursor = y_tbl - 0.60
    for chk in checks:
        cid = chk["check_id"]
        dcr_v = float(chk["dcr"])
        st_v = chk["status"]
        gov_m = chk.get("governing_member", "")
        gov_c = chk.get("governing_combo", "")
        client.draw_text(
            (x_ver + 0.3, y_cursor),
            f"- {cid}: DCR = {dcr_v:.3f} [{st_v}] (elem={gov_m}, combo={gov_c})",
            height=0.23,
        )
        y_cursor -= 0.50

    client.set_layer("BR-STATUS", color=1)
    client.draw_text(
        (x_ver + 0.3, y_cursor - 0.15),
        f"ESTADO CONTROLES IMPLEMENTADOS: {impl_status} | DCR_ULS_max = {float(fv.get('max_dcr_uls', 0.0)):.3f} | DCR_SLS_max = {float(fv.get('max_dcr_sls', 0.0)):.3f}",
        height=0.26,
    )
    y_cursor -= 0.60
    client.draw_text(
        (x_ver + 0.3, y_cursor - 0.15),
        f"ESTADO GLOBAL DEL CALCULO: {calc_status} (SALVEDADES OBLIGATORIAS PENDIENTES):",
        height=0.26,
    )
    y_cursor -= 0.55
    for idx, salvedad in enumerate(unimpl, start=1):
        client.draw_text(
            (x_ver + 0.3, y_cursor),
            f"  Salvedad {idx}: {salvedad}",
            height=0.20,
        )
        y_cursor -= 0.45

    # Guardar y auditar el archivo DXF
    dxf_path_str = save_dxf(doc, out_p / f"{base_name}.dxf", dxfversion="R2018", audit=True)
    dxf_verif = verify_dxf(dxf_path_str)

    # Reabrir el archivo DXF para contabilizar capas, lineas y textos reales en disco
    reopened_doc = ezdxf.readfile(dxf_path_str)
    reopened_msp = reopened_doc.modelspace()
    reopened_layers = sorted({lay.dxf.name for lay in reopened_doc.layers})
    reopened_entities = list(reopened_msp)
    reopened_texts = [
        e.dxf.text for e in reopened_entities if e.dxftype() in ("TEXT", "MTEXT") and hasattr(e.dxf, "text")
    ]
    dxf_verif.update({
        "reopened_layers": reopened_layers,
        "n_layers": len(reopened_layers),
        "n_texts_reopened": len(reopened_texts),
        "n_line_segments_drawn": len(client.line_segments),
    })

    # Generar y verificar DWG nativo si generate_native_dwg=True y accoreconsole.exe existe
    accore_exe = Path(r"C:\Program Files\Autodesk\AutoCAD 2026\accoreconsole.exe")
    dwg_verif: dict[str, Any] = {
        "verified_via_accoreconsole": False,
        "reason": "generate_native_dwg=False o accoreconsole.exe no disponible",
    }
    dwg_path_str: str | None = None
    dwg_size_bytes = 0
    if generate_native_dwg and accore_exe.exists():
        dwg_verif = _build_accore_dwg(client, out_p, base_name, accore_path=accore_exe)
        dwg_path_str = dwg_verif.get("dwg_path")
        dwg_size_bytes = int(dwg_verif.get("dwg_size_bytes", 0))

    return {
        "dxf_path": dxf_path_str,
        "dxf_size_bytes": Path(dxf_path_str).stat().st_size,
        "dxf_verification": dxf_verif,
        "dwg_path": dwg_path_str,
        "dwg_size_bytes": dwg_size_bytes,
        "dwg_verification": dwg_verif,
        "base_layout_counts": base_layout_counts,
        "drawing_scope": "ESQUEMATICO_DISPOSICION_GENERAL_NO_CONSTRUCTIVO",
        "final_girder_section": final_girder_sec,
        "final_diaphragm_section": final_diaph_sec,
        "implemented_checks_status": impl_status,
        "calculation_status": calc_status,
    }


__all__ = ["LayoutStyle", "draw_bridge_layout", "export_bridge_grillage_drawings"]
