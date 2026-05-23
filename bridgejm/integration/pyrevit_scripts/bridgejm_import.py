"""
pyRevit script DE EJEMPLO — BridgeJm import.

Cómo usar:
    1. Copia este archivo a tu pyRevit extension:
       %APPDATA%\pyRevit\Extensions\<TuExt>.extension\BridgeJm.tab\...\bridgejm_import.pushbutton\script.py
    2. Recarga pyRevit (Reload).
    3. Abre tu proyecto Revit y haz click en el botón.

Requisitos:
    - pyRevit 4.8+ (CPython3 engine).
    - Familias cargadas en el proyecto:
        * BridgeJm_AdaptivePier   (parámetros: Height, Width, Depth)
        * BridgeJm_Deck            (parámetros: Width, Thickness)

Este archivo es solo plantilla. Para generar el script personalizado a tu
geometría, usa `bridgejm.integration.revit_export.to_revit_script(bridge)`
y pega el resultado aquí.
"""
# -*- coding: utf-8 -*-
from Autodesk.Revit.DB import (
    Transaction, XYZ, Line, Structure
)
from pyrevit import revit, DB

doc = revit.doc

# --- parámetros del puente (edítalos o sobreescríbelos desde Dynamo) ---
SPANS_M = [30.0, 40.0, 30.0]
PIER_HEIGHT_M = 10.0
PIER_WIDTH_M = 1.5
PIER_DEPTH_M = 2.0
DECK_WIDTH_M = 10.0
DECK_THICK_M = 1.2
PIER_FAMILY = "BridgeJm_AdaptivePier"
DECK_FAMILY = "BridgeJm_Deck"


def _find_family_symbol(name):
    for s in DB.FilteredElementCollector(doc).OfClass(DB.FamilySymbol):
        if s.Family.Name == name:
            if not s.IsActive:
                s.Activate()
                doc.Regenerate()
            return s
    raise RuntimeError("Family not found: %s" % name)


with Transaction(doc, "BridgeJm import") as t:
    t.Start()

    pier_sym = _find_family_symbol(PIER_FAMILY)
    deck_sym = _find_family_symbol(DECK_FAMILY)

    # Piers en los apoyos intermedios
    x = 0.0
    for span in SPANS_M[:-1]:
        x += span
        pt = XYZ(x, 0.0, 0.0)
        inst = doc.Create.NewFamilyInstance(
            pt, pier_sym, Structure.StructuralType.NonStructural
        )
        inst.LookupParameter("Height").Set(PIER_HEIGHT_M)
        inst.LookupParameter("Width").Set(PIER_WIDTH_M)
        inst.LookupParameter("Depth").Set(PIER_DEPTH_M)

    # Deck por luz
    x = 0.0
    for span in SPANS_M:
        start = XYZ(x, 0.0, PIER_HEIGHT_M)
        end = XYZ(x + span, 0.0, PIER_HEIGHT_M)
        line = Line.CreateBound(start, end)
        deck = doc.Create.NewFamilyInstance(
            line, deck_sym, None, Structure.StructuralType.Beam
        )
        deck.LookupParameter("Width").Set(DECK_WIDTH_M)
        deck.LookupParameter("Thickness").Set(DECK_THICK_M)
        x += span

    t.Commit()

print("BridgeJm: puente generado con %d luces" % len(SPANS_M))
