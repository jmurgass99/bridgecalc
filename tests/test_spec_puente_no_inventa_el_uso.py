"""`bridge_spec_from_encargo`: el uso del puente decide el modelo de cargas; si ese modelo no
existe, se para con un motivo claro en vez de calcular con el de carretera.

Defecto (auditoria nocturna 2026-10-25): `uso` solo se guardaba; las cargas eran siempre LM1/HL-93
de CARRETERA. Un puente ferroviario se habria calculado sin LM71/SW (EN 1991-2 §6) -> del lado
INSEGURO; uno peatonal con camiones en vez de la carga de peatones (§5). Ademas un galibo sin
numero pasaba a 5.0 m en silencio, y losa/pavimento/barreras/numero de vigas eran valores fijos
del codigo sin declararse.
"""
from __future__ import annotations
import pytest as _pytest_skip
_pytest_skip.importorskip("jmworkbench")  # dependencia externa opcional: sin ella estos tests se omiten

import pytest

from jmworkbench.encargo import interpretar_encargo
from bridgecalc.integration.grillage_model import bridge_spec_from_encargo

BASE = {"norma": "EN 1991-2", "uso": "carretera", "ancho_tablero_o_carriles": "ancho de tablero 10 m",
        "material": "acero", "apoyos": "simplemente apoyado", "galibo": "gálibo de 5,5 m", "acciones": "LM1"}


def _spec(**cambios):
    return bridge_spec_from_encargo(interpretar_encargo("Diseña un puente de 30 m de luz.",
                                                        supuestos={**BASE, **cambios}))


@pytest.mark.parametrize("uso", ["ferroviario", "peatonal"])
def test_uso_sin_modelo_de_cargas_se_para(uso) -> None:
    with pytest.raises(ValueError, match=uso):
        _spec(uso=uso)


def test_carretera_sigue_funcionando_y_declara_sus_supuestos() -> None:
    spec = _spec()
    sup = " ".join(spec.predimensioning_trace["supuestos_del_flujo"]).lower()
    for palabra in ("losa", "pavimento", "barrera", "vigas", "diafragmas"):
        assert palabra in sup, palabra


def test_galibo_sin_numero_no_se_inventa() -> None:
    with pytest.raises(ValueError, match="libo"):
        _spec(galibo="el habitual")


@pytest.mark.parametrize("uso", ["uso peatón y bicicletas", "vía férrea de ancho ibérico", "tranvía",
                                 "línea de alta velocidad ferroviaria", "Metro ligero", "carril bici"])
def test_usos_sin_modelo_con_tildes_y_sinonimos_se_paran(uso) -> None:
    """Revision FASE 2: la busqueda por subcadena sin normalizar dejaba pasar 'peatón', 'vía férrea' y
    'tranvía' con cargas de CARRETERA (del lado inseguro)."""
    with pytest.raises(ValueError, match="no esta implementado"):
        _spec(uso=uso)


@pytest.mark.parametrize("uso", ["carretera con arcenes de 2 metros", "autovía de 4 carriles",
                                 "carretera, parámetros según EN 1991-2", "carretera nacional"])
def test_carretera_que_menciona_metros_no_se_para(uso) -> None:
    """'metro' por subcadena casaba con 'metros' y paraba un puente de carretera."""
    assert _spec(uso=uso).span_m == pytest.approx(30.0)


@pytest.mark.parametrize("uso", ["puente de ferrocarril", "ferrocarril de vía estrecha", "railroad bridge",
                                 "light rail", "footbridge", "acueducto", "paso de fauna", "oleoducto",
                                 "carretera y ferrocarril", "uso mixto"])
def test_solo_se_calcula_si_el_uso_nombra_trafico_de_carretera(uso) -> None:
    """Revision FASE 2 de C20: una LISTA DE PROHIBIDOS siempre tiene huecos ('ferrocarril', 'railroad',
    'footbridge' pasaban con cargas de carretera). El unico modelo de cargas implementado es el de
    carretera: se exige que el uso lo NOMBRE y que no nombre a la vez otro trafico."""
    with pytest.raises(ValueError, match="no esta implementado"):
        _spec(uso=uso)


@pytest.mark.parametrize("uso", ["carretera", "vehicular", "tráfico rodado", "autopista", "calle urbana",
                                 "highway bridge", "road bridge"])
def test_usos_de_carretera_reconocidos(uso) -> None:
    assert _spec(uso=uso).span_m == pytest.approx(30.0)
