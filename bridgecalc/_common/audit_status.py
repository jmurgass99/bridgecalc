"""bridgecalc._common.audit_status
=================================
Estado canónico y NO PERMISIVO de un resultado de cálculo estructural.

Este módulo es la versión MAGRA del contrato de salida auditable: solo el enum de
estado y la regla de máquina de estados que lo gobierna, en Python puro y sin
dependencias externas (igual que el resto de ``bridgecalc._common``). Es el primer
paso, incremental, de un contrato mayor: cuando/si se adopte el envoltorio completo
(referencia normativa, metadatos de motor, nivel de validación, evidencia), este enum
es la pieza estable que subsume.

La razón de existir: en este monorepo aparecieron repetidamente "aprobados
silenciosos" — un dato esencial falta, y en vez de decirlo el cálculo devuelve un
``0.0``, un ``max(P, 1.0)`` o un ``pass=True`` que se LEE como holgado/seguro, la
lectura OPUESTA a la verdadera. La regla aquí es una sola:

    la ausencia se propaga como ausencia.

Un input esencial ausente NO produce un veredicto favorable: produce NO_CALCULADO,
con la lista de lo que falta, y sin publicar demanda/capacidad/ratio ficticios.
"""
from __future__ import annotations

import math
from enum import StrEnum
# `Iterable` se usaba en la firma de `aggregate_calculation_statuses` sin
# importarlo: `typing.get_type_hints` daba `NameError: name 'Iterable' is not
# defined`. Importa especialmente aqui: este modulo es la AUTORIDAD canonica de
# los estados de calculo y su firma es contrato para todo el monorepo.
from typing import Iterable, Sequence


class CalculationStatus(StrEnum):
    """Veredicto de un cálculo. Reemplaza al ``pass: bool`` binario.

    Un booleano solo distingue cumple/no-cumple y NO puede expresar "no lo sé
    porque me falta un dato" — que es precisamente el estado que se colaba como
    "cumple". Estos estados sí lo distinguen (cuatro veredictos de cálculo más
    NO_APLICA, que es una decisión de aplicabilidad, no un veredicto).
    """

    #: Se evaluó la ecuación normativa y la utilización es <= 1.
    CALCULADO_CUMPLE = "CALCULADO_CUMPLE"
    #: Se evaluó la ecuación normativa y la utilización es > 1.
    CALCULADO_FALLA = "CALCULADO_FALLA"
    #: Falta un input esencial: la comprobación NO se hizo. Nunca es un aprobado.
    NO_CALCULADO = "NO_CALCULADO"
    #: Método fuera de alcance, integración no verificada o condición que impide
    #: firmar aunque no falte un input concreto. Requiere ojo humano.
    REQUIERE_REVISION = "REQUIERE_REVISION"
    #: La regla NO PROCEDE para este modelo (p.ej. B29 "uplift en resortes" sobre
    #: un modelo sin resortes). No es un aprobado ni una ausencia: se decidió, con
    #: los inputs presentes, que la comprobación no aplica. Nunca domina una
    #: agregación y nunca sustituye a NO_CALCULADO (la ausencia se evalúa antes).
    NO_APLICA = "NO_APLICA"


#: Las condiciones de evidencia de la Proof Obligation. Un resultado FAVORABLE
#: exige que las SEIS esten declaradas explicitamente como ``True``.
#:
#: Estan aqui, y no solo en la firma, para que un test pueda leerlas y comprobar
#: que ninguna ha recuperado un default permisivo. El defecto que origino este P0
#: no fue que faltara la comprobacion: fue que su default AFIRMABA que todo
#: estaba verificado, de modo que omitir el argumento equivalia a jurar que si.
EVIDENCE_CONDITIONS: tuple[str, ...] = (
    "demand_present",
    "capacity_present",
    "analysis_executed",
    "geometry_present",
    "material_present",
    "reinforcement_present",
)


def resolve_status(
    utilization: float | None,
    *,
    missing_inputs: Sequence[str] = (),
    demand_present: bool | None = None,
    capacity_present: bool | None = None,
    analysis_executed: bool | None = None,
    geometry_present: bool | None = None,
    material_present: bool | None = None,
    reinforcement_present: bool | None = None,
    unsupported_calc: bool = False,
) -> CalculationStatus:
    """Deriva el estado de forma NO PERMISIVA y **CLOSED-BY-DEFAULT**.

    La ausencia de evidencia NO equivale a evidencia afirmativa. Las seis
    condiciones de :data:`EVIDENCE_CONDITIONS` nacen **sin declarar** (``None``), y
    un veredicto favorable exige que las seis se declaren ``True``. Omitir el
    argumento es exactamente igual de bloqueante que declararlo ``False``: la
    diferencia es solo si consta que no se verifico o si no consta nada.

    Reglas, en orden:

    1. Si alguna condición de evidencia no está declarada como ``True`` --porque se
       omitió, o porque se declaró ``False``-- -> ``NO_CALCULADO``. Domina sobre
       todo: sin evidencia la comprobación no está hecha, tenga o no un número.
    2. Si hay ``missing_inputs`` -> ``NO_CALCULADO``.
    3. Si el cálculo no está soportado -> ``REQUIERE_REVISION``.
    4. Si la utilización no es un número FINITO (``NaN``, ``+inf``, ``-inf``) o es
       negativa -> ``REQUIERE_REVISION``, sin excepciones. Un número no finito no
       es una utilización mala: es una que no se pudo calcular, y
       ``CALCULADO_FALLA`` exige una comparación finita que concluya
       incumplimiento.
    5. Evidencia completa y sin utilización computada (``None``) ->
       ``REQUIERE_REVISION``. No se inventa un cumple por ausencia de número.
    6. Evidencia completa y utilización computada: ``<= 1`` es CUMPLE, ``> 1`` es
       FALLA. Una demanda de **cero** con evidencia completa SÍ es CUMPLE con
       DCR = 0: es un resultado, no una ausencia.

    Dos parámetros conservan su valor por defecto **a propósito**, y ninguno de los
    dos es una condición de evidencia:

    * ``missing_inputs=()`` -- una lista vacía significa "no consta que falte nada",
      no "lo verifiqué". No se usa como proxy de evidencia: solo puede AÑADIR
      motivos para no firmar, nunca concederlos, así que su default no abre ningún
      camino hacia un veredicto favorable.
    * ``unsupported_calc=False`` -- es una declaración de *alcance* (el método
      aplica), no de verificación. Es un veto: solo puede degradar el veredicto a
      ``REQUIERE_REVISION``. Con las seis condiciones sin declarar, omitirlo no
      concede nada, porque la regla 1 ya ha devuelto ``NO_CALCULADO``.

    Es decir: no existe ninguna combinación de argumentos OMITIDOS que produzca un
    resultado favorable. Un test lee esta firma y falla si alguien devuelve un
    default permisivo a cualquiera de las seis.
    """
    # Las seis, en el mismo orden que EVIDENCE_CONDITIONS (un test ata las dos
    # listas). `is not True` trata igual el False declarado y el None omitido: los
    # dos significan "no consta que se verificara", y ninguno concede nada.
    declaradas = (
        demand_present,
        capacity_present,
        analysis_executed,
        geometry_present,
        material_present,
        reinforcement_present,
    )
    if any(c is not True for c in declaradas) or bool(missing_inputs):
        return CalculationStatus.NO_CALCULADO

    if unsupported_calc:
        return CalculationStatus.REQUIERE_REVISION

    if utilization is None:
        return CalculationStatus.REQUIERE_REVISION

    # NaN, +inf y -inf: la MISMA familia. Un número no finito no es una
    # utilización mala, es una utilización que no se pudo calcular.
    #
    # Aquí había una rama explícita `if math.isinf(utilization): return
    # CALCULADO_FALLA` (b2be16e), y `-inf` ni siquiera la alcanzaba porque la
    # comparación con cero de más abajo lo capturaba antes: el contrato trataba
    # los dos infinitos de forma distinta, y a `+inf` como veredicto.
    #
    # Un D/C infinito sale de dividir por una capacidad CERO --el patrón
    # `dc = abs(M_Ed) / MRd if MRd > 0 else float("inf")`, que está por todo el
    # monorepo--, es decir, de que la capacidad NO SE PUDO CALCULAR. No se
    # comparó nada contra nada. `CALCULADO_FALLA` está reservado a un estado
    # límite REALMENTE evaluado, con demanda, capacidad, criterio normativo y una
    # comparación matemática FINITA que concluya incumplimiento; dividir por cero
    # no cumple ninguna de las cuatro. Y decir "esta viga no cumple" cuando lo
    # cierto es "no se pudo calcular su capacidad" manda a redimensionar una
    # sección que quizá estaba bien y esconde el defecto real, que está en los
    # datos de entrada.
    #
    # `fastsap.design.contract._ratio_de` --código de producción-- ya lo decía
    # así: "un ratio ausente, None, NaN o infinito no es un ratio malo: es un
    # ratio que no se calculó". Esta rama contradecía al módulo hermano.
    if not math.isfinite(utilization):
        # LOS DOS ORIGENES DE UN `+inf`, que significan cosas OPUESTAS:
        #
        #   (a) la capacidad se EVALUÓ y salió genuinamente CERO, con demanda
        #       real. La sección no resiste nada y está cargada: eso sería un
        #       incumplimiento EVALUADO, y el infinito no es un error sino el
        #       resultado.
        #   (b) la capacidad NO SE PUDO CALCULAR --sección no parseable, armado
        #       ausente, material sin declarar-- y el código hizo
        #       `dc = M/MRd if MRd > 0 else inf`. No se comparó nada contra nada.
        #
        # Esta función no puede adivinar de cuál se trata: la diferencia la sabe
        # QUIEN CALCULÓ, no quien clasifica. En 47afd56 se abrió un parámetro
        # para que el caller lo declarase (`zero_capacity_measured`) y se retiró
        # acto seguido, porque el censo de los productores reales lo desmintió:
        # los TRES únicos sitios que derivan `capacity_present` del valor de la
        # capacidad lo hacen con `> 0` (`csi_workspace/router.py:860`,
        # `SteelConnectionJm/welds.py:240`, `JmWorkbench/orchestrator.py:262`).
        # Ante una capacidad medida IGUAL A CERO --el caso (a)-- esos tres
        # declaran `capacity_present=False`, y la regla 1 devuelve
        # `NO_CALCULADO` antes de llegar aquí. El parámetro era inalcanzable
        # desde el único patrón capaz de producir el infinito, y sí era
        # alcanzable desde `contract.py:349`, que declara
        # `capacity_present=bool(result.checks)` --"hay comprobaciones", que no
        # es una capacidad--: emparejar esas dos cosas habría sentenciado
        # `CALCULADO_FALLA` sin haber evaluado ninguna capacidad.
        #
        # LA FUENTE DE VERDAD YA ESTÁ EN EL SITIO DEL CÁLCULO. Si algún día un
        # productor necesita el caso (a), lo que cambia es su declaración de
        # capacidad, no una bandera aquí, y lo que hay que expresar son los
        # CUATRO estados de una capacidad --MISSING / INVALID / MEASURED_ZERO /
        # POSITIVE-- con UN concepto estructurado, no un segundo booleano en
        # paralelo a `capacity_present` (que ya significa seis cosas distintas en
        # los ocho sitios que la declaran). Mientras nadie lo necesite, este
        # contrato no lleva API sin usar.
        #
        # Así que los tres no finitos son la misma familia. `-inf` y `NaN` no
        # entran en ningún trato: una utilización negativa infinita es una
        # anomalía de convención de signos, y un NaN es un valor del que no se
        # sabe ni qué es. Ninguno de los dos es "una capacidad nula medida".
        return CalculationStatus.REQUIERE_REVISION

    if utilization < 0.0:
        return CalculationStatus.REQUIERE_REVISION

    # LA TOLERANCIA NO ES UN UMBRAL AFLOJADO: ES EL PREDICADO HERMANO.
    #
    # `fastsap.design.contract._check_passes:262` ya comparaba `<= 1.0 + 1e-9` y
    # esta no. Dos predicados sobre el MISMO numero, con veredictos contrarios, y
    # nadie los habia comparado nunca sobre el mismo valor.
    #
    # Importa porque el ratio de una pieza recien DIMENSIONADA aterriza en
    # 1.0 +- unos ULP por construccion: el dimensionador invierte la capacidad y
    # la comprobacion la vuelve a evaluar, y `f(f^-1(M)) == M` no es alcanzable en
    # coma flotante para una `f` no lineal. MEDIDO sobre una 300x550:
    #
    #     NSR-10 (forma cerrada)  ratio > 1.0 en 37/120 vigas; peor exceso 6.66e-16
    #     EC2    (biseccion)      peor deficit 5.7e-14
    #
    # 6.66e-16 son TRES ULP (epsilon del double = 2.22e-16). Sin tolerancia, el
    # 31 % de las vigas correctamente dimensionadas salia CALCULADO_FALLA mientras
    # el vocabulario heredado decia OK.
    #
    # `1e-9` esta seis ordenes por encima de ese error y quince por debajo de
    # cualquier incertidumbre de material o de carga; no absorbe nada con
    # significado fisico (un 0,1 % de exceso sigue siendo FALLA, fijado en
    # `test_los_dos_predicados_de_aprobado_no_discrepan`). La cota del error de
    # ida y vuelta se vigila en
    # `fastsap/tests/test_los_dimensionadores_cumplen_su_propio_contrato.py`.
    return (
        CalculationStatus.CALCULADO_CUMPLE
        if utilization <= 1.0 + 1e-9
        else CalculationStatus.CALCULADO_FALLA
    )


def aggregate_calculation_statuses(
    statuses: Iterable[CalculationStatus | str],
) -> CalculationStatus:
    """Agrega una colección de estados de cálculo de forma determinista y segura.

    ELIMINA EL DEFECTO DE VERDAD VACUA (vacuous truth):
    En Python puro, ``all([]) == True``. Si se evalúa ``all(s == CALCULADO_CUMPLE for s in [])``,
    Python afirma falsamente que una lista vacía de comprobaciones "CUMPLE".
    En ingeniería estructural: ausencia de comprobaciones == NO_CALCULADO.

    Reglas de precedencia de agregación:
    1. Si la lista está vacía -> NO_CALCULADO.
    2. Si cualquier elemento es CALCULADO_FALLA -> CALCULADO_FALLA.
    3. Si cualquier elemento es NO_CALCULADO -> NO_CALCULADO.
    4. Si cualquier elemento es REQUIERE_REVISION -> REQUIERE_REVISION.
    5. Si todos los elementos aplicables son CALCULADO_CUMPLE (o NO_APLICA) -> CALCULADO_CUMPLE.
    """
    raw_list = list(statuses)
    if not raw_list:
        return CalculationStatus.NO_CALCULADO

    normalized: list[CalculationStatus] = []
    for s in raw_list:
        if isinstance(s, CalculationStatus):
            normalized.append(s)
        else:
            try:
                normalized.append(CalculationStatus(str(s)))
            except ValueError:
                normalized.append(CalculationStatus.REQUIERE_REVISION)

    # Filtrar NO_APLICA para evaluación de cumplimiento
    active = [s for s in normalized if s != CalculationStatus.NO_APLICA]
    if not active:
        return CalculationStatus.NO_APLICA

    if any(s == CalculationStatus.CALCULADO_FALLA for s in active):
        return CalculationStatus.CALCULADO_FALLA

    if any(s == CalculationStatus.NO_CALCULADO for s in active):
        return CalculationStatus.NO_CALCULADO

    if any(s == CalculationStatus.REQUIERE_REVISION for s in active):
        return CalculationStatus.REQUIERE_REVISION

    if all(s == CalculationStatus.CALCULADO_CUMPLE for s in active):
        return CalculationStatus.CALCULADO_CUMPLE

    return CalculationStatus.REQUIERE_REVISION


__all__ = ["CalculationStatus", "resolve_status", "aggregate_calculation_statuses"]
