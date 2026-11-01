"""Combinaciones AASHTO LRFD Tabla 3.4.1-1: los trece estados límite (Strength I–V, Service I–IV, Fatigue I–II, Extreme Event I–II) aplicados a los momentos de una viga, con γ_p máximo o mínimo para las cargas permanentes.

`load_combinations.factored_effect` multiplica cada componente (DC, DW, LL+IM, WS, WL, EQ, BR…) por su
γ; `governing_strength` elige la combinación de resistencia que gobierna; `favorable_permanent` usa
el γ_p mínimo (0,90/0,65) cuando la carga permanente alivia. Se cruza con `aashto_lrfd.get_design_force`
(tabla paralela con EH/EV) y se listan los factores de resistencia φ de §5.5.4.2.

Ejecutar:  python examples/load_combinations_aashto_3_4_1_thirteen_limit_states_factored_moments_and_governing_strength.py
"""
from bridgecalc.loads.aashto_lrfd import AASHTO_COMBINATIONS, RESISTANCE_FACTORS, get_design_force
from bridgecalc.loads.load_combinations import LOAD_COMBINATIONS, factored_effect, gamma, governing_strength


def main() -> None:
    M = {"DC": 2600.0, "DW": 450.0, "LL": 1850.0, "WS": 120.0, "WL": 40.0, "EQ": 900.0, "BR": 60.0, "CT": 300.0, "WA": 0.0}
    print("Momentos sin mayorar por viga [kN·m]: " + ", ".join(f"{k} = {v:.0f}" for k, v in M.items()) + " (LL ya incluye IM)\n")
    print(f"  {'estado límite':14} {'γ_DC':>5} {'γ_DW':>5} {'γ_LL':>5} {'γ_WS':>5} {'γ_EQ':>5} {'M_u [kN·m]':>11}")
    for ls in LOAD_COMBINATIONS:
        r = factored_effect(ls, M)
        print(f"  {ls:14} {gamma(ls, 'DC'):5.2f} {gamma(ls, 'DW'):5.2f} {gamma(ls, 'LL'):5.2f} {gamma(ls, 'WS'):5.2f} {gamma(ls, 'EQ'):5.2f} {r.factored_effect:11.0f}")
    gov = governing_strength(M)
    print(f"\nGobierna en resistencia: {gov.limit_state} con M_u = {gov.factored_effect:.0f} kN·m; contribuciones: "
          + ", ".join(f"{k} {v:.0f}" for k, v in gov.contributions.items() if v))
    fav = factored_effect("Strength_I", {"DC": 2600.0, "DW": 450.0}, favorable_permanent=True)
    print(f"Permanentes favorables (γ_p mínimo 0,90/0,65), por ejemplo para comprobar levantamiento: {fav.factored_effect:.0f} kN·m frente a {factored_effect('Strength_I', {'DC': 2600.0, 'DW': 450.0}).factored_effect:.0f} con γ_p máximo")
    s1 = get_design_force("STRENGTH_I", {"DC": 2600.0, "DW": 450.0, "LL_IM": 1850.0})
    print(f"\nTabla paralela aashto_lrfd.get_design_force('STRENGTH_I'): {s1:.0f} kN·m = 1,25·DC + 1,50·DW + 1,75·LL; los {gov.factored_effect - s1:.0f} kN·m de diferencia con load_combinations son el frenado BR (1,75·60), que esta tabla no contempla; combinaciones disponibles: {list(AASHTO_COMBINATIONS)}")
    print(f"  STRENGTH_I: {AASHTO_COMBINATIONS['STRENGTH_I'].name}; EH = {AASHTO_COMBINATIONS['STRENGTH_I'].EH}, EV = {AASHTO_COMBINATIONS['STRENGTH_I'].EV} (empujes de tierras para estribos)")
    print("\nFactores de resistencia φ (§5.5.4.2): " + ", ".join(f"{k} {v}" for k, v in RESISTANCE_FACTORS.items()))
    print("\nStrength IV (1,50·DC) solo gobierna con mucha carga permanente frente a la viva; Extreme I usa 0,50·LL con el sismo. "
          "Los γ_WS del módulo (1,40 Strength III, 0,40 Strength V, 0,30 Service I, 0,70 Service IV) son los del esquema anterior a la 8ª edición (2017); desde ésta el viento parte de una ráfaga de 3 s "
          "y Strength III pasó a γ_WS = 1,0, con velocidades propias para Strength V y Service I. Revisa la Tabla 3.4.1-1 de la edición que te aplique.")


if __name__ == "__main__":
    main()
