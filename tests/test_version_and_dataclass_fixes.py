"""Versión única en pyproject, paquete y API; LRFDLoadCombination es un dataclass congelado."""
import dataclasses
import tomllib
from pathlib import Path

import pytest

import bridgecalc
from bridgecalc.loads.aashto_lrfd import AASHTO_COMBINATIONS, LRFDLoadCombination, get_design_force


def test_version_unica():
    pyproject = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    assert bridgecalc.__version__ == pyproject["project"]["version"] == "1.1.0"


def test_api_publica_la_misma_version():
    pytest.importorskip("fastapi")
    from bridgecalc.api import create_app
    assert create_app().version == bridgecalc.__version__


def test_combinacion_congelada_una_sola_vez():
    comb = AASHTO_COMBINATIONS["STRENGTH_I"]
    assert isinstance(comb, LRFDLoadCombination)
    with pytest.raises(dataclasses.FrozenInstanceError):
        comb.DC = 9.9
    assert get_design_force("STRENGTH_I", {"DC": 100.0, "DW": 20.0, "LL_IM": 80.0}) == pytest.approx(1.25 * 100 + 1.5 * 20 + 1.75 * 80)
