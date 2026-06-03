"""
bridgejm.integration.grillage_model — emparrillado de puente para SAP/CSiBridge (idea #12, MVP).

Genera la geometría de un tablero de puente como grid (emparrillado / grillage):
vigas longitudinales (girders) × líneas transversales (diafragmas), con apoyos en
las líneas de pila. La salida (``joints`` / ``frames``) es compatible con
``fastsap.worker_sap2000.StructuralJobInput``; la carga de carril HL-93 viaja como
metadato (``loads.hl93`` ya calcula las envolventes de camión/tándem).

``build_bridge_grillage`` lleva ese modelo a CSiBridge/SAP vía OAPI (joints +
frames, patrón de ``fastcsib.manual_bridge_builder``), mock-testeable con
``preview_only``. Los objetos puente nativos de CSiBridge (vehículos HL-93 y
casos móviles paramétricos) quedan fuera de alcance — la carga de carril viaja
como metadato (``loads.hl93`` calcula las envolventes de camión/tándem).
"""
from __future__ import annotations

from typing import Any

# Carga de carril HL-93 (AASHTO LRFD 3.6.1.2.4): 9.3 kN/m por carril de diseño.
HL93_LANE_LOAD_KN_M = 9.3


def generate_grillage(
    *,
    n_spans: int = 1,
    span_length: float = 20.0,
    n_girders: int = 4,
    girder_spacing: float = 2.5,
    divisions_per_span: int = 8,
    long_section: str = "GIRDER",
    trans_section: str = "DIAPHRAGM",
) -> dict[str, Any]:
    """Devuelve ``{joints, frames, meta}`` del emparrillado.

    - joints: ``{id,x,y,z,restraint}`` (apoyos articulados en las líneas de pila).
    - frames: longitudinales ``L*`` (vigas) + transversales ``T*`` (diafragmas).
    """
    if n_spans < 1 or n_girders < 2 or divisions_per_span < 1:
        raise ValueError("n_spans>=1, n_girders>=2, divisions_per_span>=1")

    nx = n_spans * divisions_per_span + 1            # líneas transversales
    dx = span_length / divisions_per_span
    x_coords = [round(ix * dx, 6) for ix in range(nx)]
    # índices de líneas transversales que caen sobre una pila (x = k·span_length)
    support_ix = {k * divisions_per_span for k in range(n_spans + 1)}

    def jid(ix: int, ig: int) -> str:
        return f"N{ix}_{ig}"

    joints: list[dict[str, Any]] = []
    for ix in range(nx):
        for ig in range(n_girders):
            joints.append({
                "id": jid(ix, ig),
                "x": x_coords[ix],
                "y": round(ig * girder_spacing, 6),
                "z": 0.0,
                # apoyo articulado (pin) en las líneas de pila
                "restraint": [True, True, True, False, False, False] if ix in support_ix else None,
            })

    frames: list[dict[str, Any]] = []
    # Vigas longitudinales: a lo largo de cada girder
    for ig in range(n_girders):
        for ix in range(nx - 1):
            frames.append({"id": f"L{ix}_{ig}", "joint_i": jid(ix, ig),
                           "joint_j": jid(ix + 1, ig), "section": long_section})
    # Diafragmas transversales: en cada línea, entre girders consecutivos
    for ix in range(nx):
        for ig in range(n_girders - 1):
            frames.append({"id": f"T{ix}_{ig}", "joint_i": jid(ix, ig),
                           "joint_j": jid(ix, ig + 1), "section": trans_section})

    return {
        "joints": joints,
        "frames": frames,
        "meta": {
            "n_spans": n_spans, "span_length": span_length, "n_girders": n_girders,
            "girder_spacing": girder_spacing, "divisions_per_span": divisions_per_span,
            "total_length": round(n_spans * span_length, 6),
            "lane_load_kN_m": HL93_LANE_LOAD_KN_M,
        },
    }


def grillage_model(
    L: float,
    W: float,
    n_girders: int = 4,
    n_diaphragms: int = 3,
    *,
    n_spans: int = 1,
    long_section: str = "GIRDER",
    trans_section: str = "DIAPHRAGM",
) -> dict[str, Any]:
    """Modelo de emparrillado de un tablero a partir de luz, ancho y conteos.

    Firma de conveniencia ``grillage_model(L, W, n_girders, n_diaphragms)``
    (idea #12). Reparametriza :func:`generate_grillage`:

    - ``W`` es el ancho TOTAL del tablero → la separación entre vigas es
      ``W / (n_girders - 1)`` (vigas equiespaciadas, bordes incluidos).
    - ``n_diaphragms`` es el número de líneas de diafragma INTERIORES (entre
      apoyos). Con los dos diafragmas de apoyo, hay ``n_diaphragms + 2``
      líneas transversales por vano → ``divisions_per_span = n_diaphragms + 1``.

    Devuelve ``{joints, frames, meta}`` (mismo contrato que consume
    ``fastsap.worker_sap2000.StructuralJobInput``): frames longitudinales
    ``L*`` (vigas) y transversales ``T*`` (diafragmas).
    """
    if n_girders < 2:
        raise ValueError("n_girders>=2")
    if n_diaphragms < 0:
        raise ValueError("n_diaphragms>=0")
    if W <= 0:
        raise ValueError("W>0")
    girder_spacing = W / (n_girders - 1)
    divisions_per_span = n_diaphragms + 1
    return generate_grillage(
        n_spans=n_spans,
        span_length=L,
        n_girders=n_girders,
        girder_spacing=girder_spacing,
        divisions_per_span=divisions_per_span,
        long_section=long_section,
        trans_section=trans_section,
    )


def build_bridge_grillage(
    client: Any,
    *,
    L: float = 30.0,
    W: float = 10.0,
    n_girders: int = 4,
    n_diaphragms: int = 3,
    n_spans: int = 1,
    long_section: str = "GIRDER",
    trans_section: str = "DIAPHRAGM",
    preview_only: bool = False,
) -> dict[str, Any]:
    """Construye el emparrillado en CSiBridge/SAP vía OAPI (idea #12).

    Resuelve el TODO histórico de wiring a CSiBridge. ``client`` puede ser:

    - un ``fastcsib.CsibClient`` / ``fastsap`` client (se usa ``client.SapModel``),
    - o directamente un ``SapModel`` (mock testeable).

    Sigue el patrón de ``fastcsib.manual_bridge_builder.build_curved_viaduct``:
    ``PointObj.AddCartesian`` para cada nodo (+ ``SetRestraint`` en apoyos) y
    ``FrameObj.AddByPoint`` para cada barra. Con ``preview_only=True`` no toca
    el modelo y sólo cuenta entidades — útil para tests sin licencia.

    Returns
    -------
    dict con el modelo generado más ``n_joints`` / ``n_frames`` /
    ``n_frames_long`` / ``n_frames_trans`` / ``n_supports``.
    """
    model = grillage_model(
        L, W, n_girders, n_diaphragms,
        n_spans=n_spans, long_section=long_section, trans_section=trans_section,
    )
    joints = model["joints"]
    frames = model["frames"]
    n_long = sum(1 for f in frames if f["id"].startswith("L"))
    n_trans = sum(1 for f in frames if f["id"].startswith("T"))
    n_supports = sum(1 for j in joints if j["restraint"] is not None)

    summary = {
        **model,
        "n_joints": len(joints),
        "n_frames": len(frames),
        "n_frames_long": n_long,
        "n_frames_trans": n_trans,
        "n_supports": n_supports,
    }
    if preview_only:
        return summary

    sap_model = getattr(client, "SapModel", client)
    if sap_model is None:
        raise RuntimeError(
            "client no expone SapModel (¿conectado a CSiBridge?). "
            "Usa preview_only=True para contar sin tocar el modelo."
        )
    # 1) Nodos + apoyos. AddCartesian(x, y, z, Name, UserName) en la API CSI.
    for j in joints:
        sap_model.PointObj.AddCartesian(j["x"], j["y"], j["z"], j["id"], j["id"])
        if j["restraint"] is not None:
            sap_model.PointObj.SetRestraint(j["id"], list(j["restraint"]))
    # 2) Barras (vigas + diafragmas) con su sección.
    for f in frames:
        sap_model.FrameObj.AddByPoint(
            f["joint_i"], f["joint_j"], "", f["section"], f["id"]
        )
    return summary


__all__ = [
    "generate_grillage", "grillage_model", "build_bridge_grillage",
    "HL93_LANE_LOAD_KN_M",
]
