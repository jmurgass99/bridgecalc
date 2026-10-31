"""Configuracion de pytest para BridgeCalc: gateo de tests @pytest.mark.compat y @pytest.mark.live."""
from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    try:
        parser.addoption(
            "--run-compat",
            action="store_true",
            default=False,
            help="Ejecutar tests @pytest.mark.compat contra software comercial instalado (SAP2000).",
        )
    except ValueError:
        pass


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "compat: tests que requieren instancia viva de SAP2000/CSiBridge")
    config.addinivalue_line("markers", "live: tests con software comercial en vivo")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--run-compat"):
        return
    skip_compat = pytest.mark.skip(
        reason="Test compat/live desactivado por defecto. Habilite con: pytest --run-compat"
    )
    for item in items:
        if "compat" in item.keywords or "live" in item.keywords:
            item.add_marker(skip_compat)
