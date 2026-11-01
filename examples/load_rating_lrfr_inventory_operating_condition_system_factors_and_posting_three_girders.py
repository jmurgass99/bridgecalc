"""Calificación de carga LRFR (AASHTO MBE §6A.4.2): factor RF a nivel inventario (γ_LL 1,75) y operación (1,35) para tres vigas con distinto estado, factores de condición φ_c y de sistema φ_s, y la decisión de restringir el paso.

RF = (φ_c·φ_s·φ·R_n − γ_DC·DC − γ_DW·DW ± γ_P·P) / (γ_LL·LL_IM). La carga viva por viga sale del
HL-93 de 30 m con un factor de distribución de 0,62. Se muestran tres vigas (buena, regular, mala con
sistema no redundante), la sensibilidad del RF al factor de condición y la lectura: inventario < 1
obliga a evaluar; operación < 1 obliga a restringir.

Ejecutar:  python examples/load_rating_lrfr_inventory_operating_condition_system_factors_and_posting_three_girders.py
"""
from bridgecalc.loads.hl93 import hl93_envelope
from bridgecalc.rating.load_rating import LRFR_LIVE_FACTORS, RatingInput, rating_both_levels, rating_factor


def main() -> None:
    e = hl93_envelope(30.0)
    LL_IM = 0.62 * e["M_max_kNm"]
    print(f"HL-93 en 30 m: {e['M_max_kNm']:.0f} kN·m por carril × g = 0,62 → LL+IM = {LL_IM:.0f} kN·m por viga; γ_LL = {LRFR_LIVE_FACTORS}\n")
    vigas = [("V1 buena, redundante", 9500.0, 1.00, 1.00), ("V2 regular (φ_c 0,95)", 9500.0, 0.95, 1.00), ("V3 mala + no redundante", 9500.0, 0.85, 0.85)]
    print(f"  {'viga':26} {'C = φcφsφRn':>11} {'RF inv':>7} {'RF oper':>8}  lectura")
    for nombre, Rn, phi_c, phi_s in vigas:
        inp = RatingInput(Rn=Rn, DC=2600.0, DW=450.0, LL_IM=LL_IM, phi=0.90, phi_c=phi_c, phi_s=phi_s)
        r = rating_both_levels(inp)
        inv, op = r["inventory"], r["operating"]
        lectura = "admite la carga de diseño" if inv.ok else ("solo a nivel operación: evaluar/mantener" if op.ok else "RF operación < 1: restringir el paso")
        print(f"  {nombre:26} {inv.capacity_C:11.0f} {inv.RF:7.2f} {op.RF:8.2f}  {lectura}")
    print("\nSensibilidad al factor de condición (viga V1):")
    print(f"  {'φ_c':>5} {'RF inv':>7} {'RF oper':>8}")
    for phi_c in (1.00, 0.95, 0.90, 0.85, 0.80):
        inp = RatingInput(Rn=9500.0, DC=2600.0, DW=450.0, LL_IM=LL_IM, phi=0.90, phi_c=phi_c)
        print(f"  {phi_c:5.2f} {rating_factor(inp, 'inventory').RF:7.2f} {rating_factor(inp, 'operating').RF:8.2f}")
    inp_p = RatingInput(Rn=9500.0, DC=2600.0, DW=450.0, LL_IM=LL_IM, phi=0.90, P=-300.0)
    print(f"\nCon un efecto permanente favorable P = −300 kN·m (pretensado secundario): RF inventario {rating_factor(inp_p).RF:.2f} frente a {rating_factor(RatingInput(Rn=9500.0, DC=2600.0, DW=450.0, LL_IM=LL_IM, phi=0.90)).RF:.2f}")
    try:
        rating_factor(inp_p, "legal")
    except ValueError as exc:
        print(f"Nivel desconocido → ValueError: {exc}")
    print("\nEl RF es lineal en la capacidad y en el inverso de la carga viva: un 5 % menos de φ_c baja el RF un 5 % de la capacidad, no del RF. "
          "La función cubre Strength I con γ_DC 1,25 y γ_DW 1,50 (MBE permite 1,25 si el espesor del pavimento está medido); no evalúa cargas legales ni permisos, que usan otros γ_LL.")


if __name__ == "__main__":
    main()
