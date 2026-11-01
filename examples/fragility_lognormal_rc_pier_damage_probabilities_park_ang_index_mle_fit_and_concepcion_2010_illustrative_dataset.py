"""Fragilidad sísmica de pilas de hormigón: curvas lognormales P(DS ≥ ds | IM) por estado de daño, probabilidades discretas que suman 1, índice de daño de Park y Ang, ajuste lognormal a observaciones sintéticas y el conjunto de pilas del Maule 2010 (valores ilustrativos).

`hazus_rc_pier_fragility` crea cuatro curvas (ligero, moderado, extenso, completo) con medianas 0,15–0,80 g
y β 0,55; `compute_discrete_damage_probabilities` resta curvas consecutivas; `park_ang_damage_index`
DI = δ_max/δ_u + β·E_h/(δ_u·F_y); `lognormal_fragility` ajusta mediana y β por momentos de las muestras
con daño. `datasets.concepcion_2010` guarda 5 pilas con M_y, M_u, θ_u y daño observado.

Ejecutar:  python examples/fragility_lognormal_rc_pier_damage_probabilities_park_ang_index_mle_fit_and_concepcion_2010_illustrative_dataset.py
"""
import numpy as np

from bridgecalc.datasets import CONCEPCION_2010_PIERS, fragility_curve, pier_by_name
from bridgecalc.fragility import HAZUS_RC_PIER_PARAMS, FragilityCurve, compute_discrete_damage_probabilities, hazus_rc_pier_fragility, lognormal_fragility, park_ang_damage_index


def main() -> None:
    fcs = hazus_rc_pier_fragility()
    print(f"Parámetros por defecto (mediana [g], β): {HAZUS_RC_PIER_PARAMS}\n")
    print(f"  {'IM [g]':>6} {'P(≥ligero)':>10} {'P(≥moderado)':>12} {'P(≥extenso)':>11} {'P(≥completo)':>12} | {'sin daño':>8} {'ligero':>7} {'moderado':>8} {'extenso':>7} {'completo':>8}")
    for im in (0.10, 0.20, 0.30, 0.50, 0.80, 1.20):
        pa = fcs.probability_all(im)
        d = compute_discrete_damage_probabilities(im, fcs)
        print(f"  {im:6.2f} {pa['slight']:10.3f} {pa['moderate']:12.3f} {pa['extensive']:11.3f} {pa['complete']:12.3f} | {d['none']:8.3f} {d['slight']:7.3f} {d['moderate']:8.3f} {d['extensive']:7.3f} {d['complete']:8.3f}  Σ = {sum(d.values()):.3f}")
    print("  En la mediana de cada estado P = 0,5 exactamente: ligero 0,15 g, completo 0,80 g.\n")
    print("Índice de daño de Park-Ang (DI < 0,4 operacional, 0,4–0,7 reparable, > 1 colapso), δ_u = 180 mm, F_y = 900 kN, β = 0,10:")
    for dmax, Eh in ((40.0, 20_000.0), (90.0, 80_000.0), (130.0, 150_000.0), (170.0, 300_000.0)):
        DI = park_ang_damage_index(dmax, 180.0, Eh, 900.0)
        estado = "operacional" if DI < 0.4 else "reparable" if DI < 0.7 else "daño severo" if DI < 1.0 else "colapso"
        print(f"  δ_max {dmax:5.0f} mm, E_h {Eh / 1000:5.0f} kN·m → DI = {dmax / 180:.3f} + {0.10 * Eh / (180 * 900):.3f} = {DI:.3f} ({estado})")
    rng = np.random.default_rng(7)
    ims = np.round(rng.uniform(0.05, 1.5, 60), 3)
    true = FragilityCurve(median=0.45, beta=0.5)
    dam = rng.uniform(size=60) < true.probability(ims)
    fit = lognormal_fragility(ims, dam)
    print(f"\nAjuste por máxima verosimilitud binomial a 60 observaciones sintéticas generadas con mediana 0,45 g y β 0,50 ({int(dam.sum())} con daño): mediana {fit.median:.3f} g, β {fit.beta:.3f}")
    big_ims = np.round(rng.uniform(0.05, 1.5, 2000), 3)
    big_dam = rng.uniform(size=big_ims.size) < true.probability(big_ims)
    big = lognormal_fragility(big_ims, big_dam)
    print(f"  Con 2000 observaciones: mediana {big.median:.3f} g, β {big.beta:.3f}. Con 60 el error de muestreo es del orden del 10–20 %. "
          "Hasta 1.0 la función devolvía la media de ln(IM) de los casos con daño (0,88 g con estos mismos 60 datos), que describe dónde cayeron los daños, no la fragilidad.\n")
    print("Pilas del Maule 2010 (datasets.concepcion_2010), VALORES ILUSTRATIVOS sembrados a partir de las referencias, no medidos:")
    print(f"  {'pila':18} {'puente':24} {'H [m]':>5} {'M_y':>6} {'M_u':>6} {'θ_u':>6} {'daño observado':>14}")
    for p in CONCEPCION_2010_PIERS:
        print(f"  {p.name:18} {p.bridge:24} {p.height_m:5.1f} {p.M_y_kNm:6.0f} {p.M_u_kNm:6.0f} {p.theta_u_rad:6.3f} {p.observed_ds:>14}")
    pga = 0.65
    print(f"\n  Curvas del conjunto (mediana, β) y P(≥ds | PGA = {pga} g): " + ", ".join(f"{ds} ({fragility_curve(ds).median}, {fragility_curve(ds).beta}) → {float(fragility_curve(ds).probability(pga)):.2f}" for ds in ("slight", "moderate", "extensive", "complete")))
    p = pier_by_name("biobio_p3")
    print(f"  pier_by_name no distingue mayúsculas: {p.name} — {p.notes}")
    print("\nLas medianas 0,15/0,30/0,50/0,80 g con β 0,55 son valores representativos del módulo, no una fila literal de la Tabla 7-9 de HAZUS (que usa β = 0,6 y medianas por clase HWB); pásalos explícitamente a hazus_rc_pier_fragility(params). "
          "Las pilas de Concepción llevan M_y, M_u y θ_u asignados «por juicio» en el código fuente: sirven para probar el flujo, no como evidencia del terremoto.")


if __name__ == "__main__":
    main()
