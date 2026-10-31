"""El momento del tandem LM1 sumaba momentos de DOS SECCIONES DISTINTAS.

EL DEFECTO. `traffic_envelope_lm1` colocaba los dos ejes a L/2 +- a/2 y hacia:

    d1 = L/2 - a/2                              # 9.4 m
    d2 = L/2 + a/2                              # 10.6 m
    M1 = Q * d1 * (L - d1) / L                  # momento EN LA SECCION 9.4
    x  = L/2                                    # 10.0 m
    M2 = Q * (L - d2) * x / L                   # momento EN LA SECCION 10.0
    M_ts += M1 + M2                             # sumados como si fueran la misma

Un momento flector es una magnitud DE UNA SECCION. Sumar el de 9.4 m con el de
10.0 m no da el momento de ninguna de las dos.

MEDIDO (L=20 m, dos ejes de 300 kN a 1.2 m):

    codigo:                     2904.600 kN*m   = 300*(4.982 + 4.700)
    maximo real (barrido):      2822.700 kN*m   en x = 9.70
    Barre (forma cerrada):      2822.700 kN*m
    momento en centro de luz:   2820.000 kN*m

    sobrestimacion: +2.90 %

DIRECCION DEL ERROR: el codigo daba MAS momento que el real, o sea que estaba del
lado seguro. Arreglarlo BAJA el momento de diseno, y eso hay que decirlo alto: la
envolvente total de la luz de 20 m con 2 carriles pasa de 6566.0 a 6429.5 kN*m
(-2.08 %). No se corrige porque fuera inseguro, sino porque un numero que sale de
sumar dos secciones no se puede razonar: nadie sabe cuanto margen tiene, y el
siguiente cambio sobre el podria caer del otro lado sin que nadie lo note.

EL ORACULO DE ESTE FICHERO NO ES LA IMPLEMENTACION. `test_la_forma_cerrada_
coincide_con_el_barrido` compara la forma cerrada contra una BUSQUEDA NUMERICA
sobre todas las posiciones del tandem y todas las secciones. Lo que fija no es un
valor capturado, es la definicion de "maximo".
"""
from __future__ import annotations

import pytest

from bridgecalc.ec1_traffic import traffic_envelope_lm1

A_TANDEM = 1.2   # separacion de ejes del TS, EN 1991-2 §4.3.2


def _momento_maximo_por_barrido(Q: float, a: float, L: float,
                                paso: float = 0.01) -> float:
    """Maximo momento por busqueda directa: mueve el tandem y evalua secciones.

    Sin teoremas: para cada posicion del primer eje y cada seccion, calcula el
    momento y se queda con el mayor. Es el oraculo contra el que se valida la
    forma cerrada.
    """
    n = int(round(L / paso))
    mejor = 0.0
    for i in range(n + 1):
        d1 = i * paso
        for j in range(n + 1):
            x = j * paso
            total = 0.0
            for d in (d1, d1 + a):
                if not (0.0 <= d <= L):
                    continue
                if x <= d:
                    total += Q * (L - d) / L * x
                else:
                    total += Q * d * (L - x) / L
            if total > mejor:
                mejor = total
    return mejor


def _tandem_del_envolvente(L: float, Q_carril1: float = 300.0) -> float:
    """Aporte del tandem del carril 1 aislado: envolvente completa menos UDL."""
    M_total, _ = traffic_envelope_lm1(L_span=L, n_lanes=1)
    w = 9.0 * 3.0                       # carril 1: 9.0 kPa * 3.0 m
    return M_total - w * L ** 2 / 8.0


# ---------------------------------------------------------------------------
# El oraculo
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("L", [20.0, 15.0, 30.0])
def test_la_forma_cerrada_coincide_con_el_barrido(L: float) -> None:
    """Lo que hace de esto un golden y no una caracterizacion."""
    barrido = _momento_maximo_por_barrido(300.0, A_TANDEM, L)
    assert _tandem_del_envolvente(L) == pytest.approx(barrido, rel=2e-4)


def test_valor_de_barre_derivado_a_mano() -> None:
    """Derivacion completa, L = 20 m, dos ejes de 300 kN a 1.2 m.

    Teorema de Barre: el maximo absoluto ocurre BAJO uno de los ejes, cuando el
    centro de luz bisecta la distancia entre ese eje y la resultante del grupo.
    Para dos ejes iguales la resultante cae en el punto medio, a a/2 = 0.6 m de
    cada eje, luego el eje critico se situa a a/4 = 0.3 m del centro:

        x_c  = L/2 - a/4        = 10 - 0.3          =  9.70 m
        R_L  = Q[(L-x_c) + (L-x_c-a)]/L
             = 300*(10.3 + 9.1)/20                  = 291.00 kN
        M    = R_L * x_c        = 291.0 * 9.7       = 2822.70 kN*m
    """
    assert _tandem_del_envolvente(20.0) == pytest.approx(2822.70, rel=1e-6)


def test_no_es_el_valor_de_dos_secciones_sumadas() -> None:
    """Guarda explicita contra la reincidencia: 2904.6 = 300*(4.982 + 4.700)."""
    assert _tandem_del_envolvente(20.0) != pytest.approx(2904.60, rel=1e-4)


def test_supera_al_momento_en_centro_de_luz() -> None:
    """Barre esta POR ENCIMA del centro de luz (2822.70 > 2820.00): el maximo
    absoluto no cae en el centro cuando el tandem no es simetrico respecto a el.
    Si alguien 'simplifica' a evaluar en L/2, este test lo ve."""
    centro = 300.0 * 9.4 * (20.0 - 10.0) / 20.0 + 300.0 * (20.0 - 10.6) * 10.0 / 20.0
    assert centro == pytest.approx(2820.0)
    assert _tandem_del_envolvente(20.0) > centro


# ---------------------------------------------------------------------------
# Casos limite
# ---------------------------------------------------------------------------
def test_luz_menor_que_la_separacion_de_ejes_solo_carga_un_eje() -> None:
    """Con L < a solo cabe un eje: M = Q*L/4."""
    L = 1.0
    assert _tandem_del_envolvente(L) == pytest.approx(300.0 * L / 4.0, rel=1e-6)


def test_la_envolvente_completa_baja_un_2_por_ciento() -> None:
    """El numero que hay que mirar antes de aceptar este cambio.

    L = 20 m, 2 carriles:
        UDL   : (9.0*3.0 + 2.5*3.0) * 20^2/8            = 1725.0
        TS c1 : Barre con Q=300                         = 2822.7
        TS c2 : Barre con Q=200 -> R_L=194.0, M=194*9.7 = 1881.8
        M_max                                           = 6429.5   (antes 6566.0)
    """
    M, V = traffic_envelope_lm1(L_span=20.0, n_lanes=2)
    assert M == pytest.approx(6429.5, rel=1e-6)
    assert V == pytest.approx(1315.0, rel=1e-6), "el cortante NO cambia"
