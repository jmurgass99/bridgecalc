"""Tests para revit_export (string matching)."""
from __future__ import annotations

import pytest

from bridgecalc.integration import revit_export as rx


def _sample_bridge() -> rx.BridgeGeometry:
    return rx.BridgeGeometry(
        spans_m=[30.0, 40.0, 30.0],
        piers=[
            rx.PierGeometry(x_m=30.0, height_m=10.0),
            rx.PierGeometry(x_m=70.0, height_m=10.0),
        ],
        deck=rx.DeckGeometry(width_m=10.0, thickness_m=1.2),
        project_name="PuenteJM",
    )


def test_script_contains_required_revit_api_calls():
    script = rx.to_revit_script(_sample_bridge())
    # API symbols
    for needle in (
        "Transaction",
        "NewFamilyInstance",
        "Line.CreateBound",
        "FilteredElementCollector",
        "FamilySymbol",
        "Structure.StructuralType",
        "XYZ(",
    ):
        assert needle in script, f"missing {needle!r}"


def test_script_starts_transaction_and_commits():
    script = rx.to_revit_script(_sample_bridge())
    assert "t.Start()" in script
    assert "t.Commit()" in script


def test_script_has_pier_for_each_input():
    bridge = _sample_bridge()
    script = rx.to_revit_script(bridge)
    # debe haber 2 piers
    assert "pier_inst_0" in script and "pier_inst_1" in script
    assert "BridgeCalc_AdaptivePier" in script


def test_script_has_deck_per_span():
    bridge = _sample_bridge()
    script = rx.to_revit_script(bridge)
    # 3 spans → 3 deck_inst_<i> únicos
    assert script.count("deck_inst_0") >= 1
    assert script.count("deck_inst_1") >= 1
    assert script.count("deck_inst_2") >= 1
    assert "deck_inst_3" not in script
    assert "BridgeCalc_Deck" in script


def test_script_synthesizes_piers_when_empty():
    bridge = rx.BridgeGeometry(spans_m=[20.0, 30.0, 20.0])
    script = rx.to_revit_script(bridge)
    # 3 luces → 2 piers interiores (indexados 0 y 1, no 2)
    assert "pier_inst_0" in script
    assert "pier_inst_1" in script
    assert "pier_inst_2" not in script


def test_save_script(tmp_path):
    path = rx.save_script(_sample_bridge(), tmp_path / "bridge_revit.py")
    content = open(path, encoding="utf-8").read()
    assert "BridgeCalc import" in content


def test_project_name_in_script():
    script = rx.to_revit_script(_sample_bridge())
    assert "PuenteJM" in script


def test_spans_in_script():
    script = rx.to_revit_script(_sample_bridge())
    assert "[30.0, 40.0, 30.0]" in script
