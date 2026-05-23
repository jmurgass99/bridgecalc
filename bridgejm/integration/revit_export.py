"""
Exporta geometría BridgeJm a Revit vía script pyRevit.

Flujo:
    1. Calculas/defines tu puente en BridgeJm.
    2. `to_revit_script(bridge)` devuelve un string con código pyRevit CPython3.
    3. Pegas el string en pyRevit (o lo guardas como `.py` en tu extension).
    4. Corres el script desde Revit con el documento del proyecto abierto.

El script generado:
    - Abre una Transaction
    - Inserta `FamilyInstance` (Adaptive Components) en cada cepa
    - Inserta el Family del tablero como un Loft a lo largo de los ejes de luces
"""
from __future__ import annotations

from dataclasses import dataclass, field
from textwrap import dedent
from typing import Sequence


# ---- dataclasses de entrada ------------------------------------------

@dataclass(frozen=True)
class PierGeometry:
    """Geometría de una cepa (pier)."""
    x_m: float            # abscisa a lo largo del eje del puente
    height_m: float       # altura desde fundación a tablero
    width_m: float = 1.5
    depth_m: float = 2.0


@dataclass(frozen=True)
class DeckGeometry:
    """Tablero (deck)."""
    width_m: float        # ancho total
    thickness_m: float    # peralte
    family_name: str = "BridgeJm_Deck"


@dataclass(frozen=True)
class BridgeGeometry:
    """Geometría completa simplificada del puente."""
    spans_m: list[float]                  # luces sucesivas
    piers: list[PierGeometry] = field(default_factory=list)
    deck: DeckGeometry = field(default_factory=lambda: DeckGeometry(10.0, 1.2))
    pier_family: str = "BridgeJm_AdaptivePier"
    project_name: str = "Puente"


# ---- generador del script --------------------------------------------

_HEADER = '''"""
pyRevit script — autogenerado por BridgeJm.
Corre con un documento Revit abierto. Requiere pyRevit >= 4.8 (CPython3).
"""
# -*- coding: utf-8 -*-
from Autodesk.Revit.DB import (
    Transaction, XYZ, FamilyInstance, Line, Structure
)
from pyrevit import revit, DB

doc = revit.doc
'''


def to_revit_script(bridge: BridgeGeometry) -> str:
    """Genera el código pyRevit para construir el puente."""
    pier_lines = []
    x_cum = 0.0
    # Si el usuario no pasa piers, sintetiza una por luz interior
    piers = list(bridge.piers)
    if not piers and len(bridge.spans_m) >= 2:
        for span in bridge.spans_m[:-1]:
            x_cum += span
            piers.append(PierGeometry(x_m=x_cum, height_m=10.0))

    # ---- piers ----------------------------------------------------
    for i, pier in enumerate(piers):
        pier_lines.append(
            f'    # Pier {i+1} @ x={pier.x_m:.3f} m\n'
            f'    pier_pt_{i} = XYZ({pier.x_m}, 0.0, 0.0)\n'
            f'    pier_sym_{i} = next(s for s in DB.FilteredElementCollector(doc)\n'
            f'                       .OfClass(DB.FamilySymbol)\n'
            f'                       if s.Family.Name == "{bridge.pier_family}")\n'
            f'    if not pier_sym_{i}.IsActive:\n'
            f'        pier_sym_{i}.Activate(); doc.Regenerate()\n'
            f'    pier_inst_{i} = doc.Create.NewFamilyInstance(\n'
            f'        pier_pt_{i}, pier_sym_{i}, Structure.StructuralType.NonStructural)\n'
            f'    pier_inst_{i}.LookupParameter("Height").Set({pier.height_m})\n'
            f'    pier_inst_{i}.LookupParameter("Width").Set({pier.width_m})\n'
            f'    pier_inst_{i}.LookupParameter("Depth").Set({pier.depth_m})\n'
        )

    # ---- deck (un FamilyInstance por luz) -------------------------
    deck_lines = []
    x_cum = 0.0
    for i, span in enumerate(bridge.spans_m):
        x_start = x_cum
        x_end = x_cum + span
        x_cum = x_end
        deck_lines.append(
            f'    # Deck span {i+1}: {x_start:.2f} → {x_end:.2f} m\n'
            f'    deck_start_{i} = XYZ({x_start}, 0.0, {piers[0].height_m if piers else 10.0})\n'
            f'    deck_end_{i}   = XYZ({x_end}, 0.0, {piers[0].height_m if piers else 10.0})\n'
            f'    deck_line_{i} = Line.CreateBound(deck_start_{i}, deck_end_{i})\n'
            f'    deck_sym_{i} = next(s for s in DB.FilteredElementCollector(doc)\n'
            f'                       .OfClass(DB.FamilySymbol)\n'
            f'                       if s.Family.Name == "{bridge.deck.family_name}")\n'
            f'    if not deck_sym_{i}.IsActive:\n'
            f'        deck_sym_{i}.Activate(); doc.Regenerate()\n'
            f'    deck_inst_{i} = doc.Create.NewFamilyInstance(\n'
            f'        deck_line_{i}, deck_sym_{i}, None, Structure.StructuralType.Beam)\n'
            f'    deck_inst_{i}.LookupParameter("Width").Set({bridge.deck.width_m})\n'
            f'    deck_inst_{i}.LookupParameter("Thickness").Set({bridge.deck.thickness_m})\n'
        )

    body = "\n".join(pier_lines) + "\n" + "\n".join(deck_lines)

    script = (
        _HEADER
        + f'\nPROJECT_NAME = "{bridge.project_name}"\n'
        + f'SPANS_M = {list(bridge.spans_m)!r}\n\n'
        + 'with Transaction(doc, "BridgeJm import - %s" % PROJECT_NAME) as t:\n'
        + '    t.Start()\n'
        + body
        + '    t.Commit()\n'
        + '\nprint("BridgeJm: puente generado con %d luces" % len(SPANS_M))\n'
    )
    return script


# ---- guardado ---------------------------------------------------------

def save_script(bridge: BridgeGeometry, path: str) -> str:
    """Convierte y guarda en disco. Devuelve la ruta absoluta."""
    from pathlib import Path
    script = to_revit_script(bridge)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(script, encoding="utf-8")
    return str(p.resolve())


__all__ = [
    "PierGeometry",
    "DeckGeometry",
    "BridgeGeometry",
    "to_revit_script",
    "save_script",
]
