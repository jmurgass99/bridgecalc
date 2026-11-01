"""El estado de una comprobación no es un booleano: `resolve_status` exige seis evidencias declaradas, trata NaN e infinito como «requiere revisión» y `aggregate_calculation_statuses` no aprueba una lista vacía; es el contrato que usa el emparrillado para clasificar sus verificaciones.

`CalculationStatus` tiene cinco valores (CALCULADO_CUMPLE, CALCULADO_FALLA, NO_CALCULADO,
REQUIERE_REVISION, NO_APLICA). `resolve_status(utilización, …)` es cerrado por defecto: omitir una
evidencia equivale a declararla falsa; `missing_inputs` solo puede quitar; un ratio infinito (capacidad
cero, como devuelven los DCR de aashto_superstructure) o NaN es REQUIERE_REVISION; la tolerancia 1e-9
absorbe el error de ida y vuelta pero no un 0,1 % de exceso. Agregación: FALLA > NO_CALCULADO >
REQUIERE_REVISION > CUMPLE; NO_APLICA nunca domina; vacío → NO_CALCULADO.

Ejecutar:  python examples/audit_status_closed_by_default_resolve_and_aggregate_for_bridge_checks.py
"""
import math

from bridgecalc._common.audit_status import EVIDENCE_CONDITIONS, CalculationStatus, aggregate_calculation_statuses, resolve_status
from bridgecalc.design.aashto_superstructure import concrete_box_girder_flexure

FULL = dict(demand_present=True, capacity_present=True, analysis_executed=True, geometry_present=True, material_present=True, reinforcement_present=True)


def main() -> None:
    print(f"Condiciones de evidencia ({len(EVIDENCE_CONDITIONS)}): {EVIDENCE_CONDITIONS}\n")
    casos = [("DCR 0,85 con las seis evidencias", dict(utilization=0.85, **FULL)),
             ("DCR 1,20 con las seis evidencias", dict(utilization=1.20, **FULL)),
             ("DCR 0,85 sin declarar evidencias", dict(utilization=0.85)),
             ("DCR 0,85, analysis_executed=False (SAP2000 no corrió)", dict(utilization=0.85, **{**FULL, "analysis_executed": False})),
             ("DCR 0,85, falta f'c en missing_inputs", dict(utilization=0.85, missing_inputs=("fc_MPa",), **FULL)),
             ("DCR 0,85, método no soportado (hormigón con fórmulas de acero)", dict(utilization=0.85, unsupported_calc=True, **FULL)),
             ("sin número (None) con evidencias", dict(utilization=None, **FULL)),
             ("DCR +inf (A_s = 0 en concrete_box_girder_flexure)", dict(utilization=concrete_box_girder_flexure(5000.0, 35.0, 600.0, 1750.0, 0.0), **FULL)),
             ("DCR NaN", dict(utilization=math.nan, **FULL)),
             ("DCR −0,2 (signo invertido)", dict(utilization=-0.2, **FULL)),
             ("DCR 1 + 6,66e-16 (tres ULP)", dict(utilization=1.0 + 6.66e-16, **FULL)),
             ("DCR 1,001 (0,1 % de exceso)", dict(utilization=1.001, **FULL)),
             ("demanda cero con evidencias", dict(utilization=0.0, **FULL))]
    print(f"  {'caso':62} {'estado':>18}")
    for nombre, kw in casos:
        print(f"  {nombre:62} {resolve_status(**kw).value:>18}")
    print("\nAgregación de los estados de un tablero:")
    C, F, N, R, A = CalculationStatus.CALCULADO_CUMPLE, CalculationStatus.CALCULADO_FALLA, CalculationStatus.NO_CALCULADO, CalculationStatus.REQUIERE_REVISION, CalculationStatus.NO_APLICA
    agg = [("[] (ninguna comprobación)", []), ("[flexión CUMPLE, cortante CUMPLE, flecha CUMPLE]", [C, C, C]), ("[CUMPLE, NO_APLICA (LTB en hormigón)]", [C, A]), ("[NO_APLICA, NO_APLICA]", [A, A]),
           ("[CUMPLE, REQUIERE_REVISION]", [C, R]), ("[CUMPLE, NO_CALCULADO (sin SAP2000)]", [C, N]), ("[CUMPLE, NO_CALCULADO, FALLA]", [C, N, F]), ("[REQUIERE_REVISION, NO_CALCULADO]", [R, N]),
           ("['CALCULADO_CUMPLE', 'texto raro']", ["CALCULADO_CUMPLE", "texto raro"])]
    for nombre, lst in agg:
        print(f"  {nombre:52} → {aggregate_calculation_statuses(lst).value}")
    print(f"\n  all([]) en Python es {all([])}: por eso la lista vacía se trata aparte y da NO_CALCULADO; un tablero con cero comprobaciones no está aprobado, está sin comprobar.")
    print("Este contrato es el que usa verify_bridge_grillage_results para clasificar cada barra y el global, y el que convierte un DCR infinito (capacidad nula) en REQUIERE_REVISION en vez de en FALLA: la ausencia se propaga como ausencia.")


if __name__ == "__main__":
    main()
