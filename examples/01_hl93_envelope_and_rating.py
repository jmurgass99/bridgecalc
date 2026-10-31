"""Envolvente HL-93 (AASHTO LRFD) y calificación de carga de una viga de puente.

Puente de vigas simplemente apoyadas de 20, 30 y 40 m: momento y cortante
máximos por carril bajo HL-93 (camión o tándem + carril, con impacto) y
después el factor de calificación (rating factor) a nivel inventario y
operación para una viga con resistencia y cargas muertas dadas.

Ejecutar:  python examples/01_hl93_envelope_and_rating.py
"""
from bridgecalc.loads.hl93 import hl93_envelope
from bridgecalc.rating.load_rating import RatingInput, rating_both_levels


def main() -> None:
    print("Envolvente HL-93 por carril (IM = 33 %):")
    print(f"  {'L [m]':>6} {'M_max [kN·m]':>13} {'V_max [kN]':>11}  gobierna")
    for L in (20.0, 30.0, 40.0):
        e = hl93_envelope(L)
        print(f"  {L:6.0f} {e['M_max_kNm']:13.0f} {e['V_max_kN']:11.0f}  {e['governing_vehicle']}")

    # Calificación de una viga interior de 30 m (valores por viga, ya con factor de distribución)
    e30 = hl93_envelope(30.0)
    LL_IM = 0.62 * e30["M_max_kNm"]          # factor de distribución de momento g = 0,62
    inp = RatingInput(Rn=9500.0, DC=2600.0, DW=450.0, LL_IM=LL_IM, phi=0.90, phi_c=0.95, phi_s=1.0)
    print(f"\nViga interior L = 30 m: M_LL+IM por viga = {LL_IM:.0f} kN·m, φ_c = 0,95 (condición regular)")
    for level, r in rating_both_levels(inp).items():
        print(f"  {level:<10} γ_LL = {r.gamma_LL:.2f}  C = {r.capacity_C:.0f} kN·m  RF = {r.RF:.2f}  {'OK' if r.ok else 'RF < 1: restringir'}")


if __name__ == "__main__":
    main()
