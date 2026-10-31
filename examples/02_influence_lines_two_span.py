"""Líneas de influencia y posición crítica de un tren de cargas.

Viga continua de dos vanos (25 + 25 m): línea de influencia del momento en el
apoyo central, efecto máximo de un vehículo de tres ejes y posición crítica
del tren. También la línea de influencia de momento a L/2 en una viga simple
y el efecto combinado con una carga de carril uniforme.

Ejecutar:  python examples/02_influence_lines_two_span.py
"""
from bridgecalc.loads.influence_lines import (
    critical_position,
    envelope_from_il,
    simple_beam_M_influence,
    two_span_continuous_M_at_support,
)

# Tren de cargas: (posición relativa al primer eje [m], carga [kN]) — camión tipo HS
AXLES = [(0.0, 35.0), (4.3, 145.0), (8.6, 145.0)]
LANE_KN_M = 9.3   # carga de carril HL-93


def main() -> None:
    il_mid = simple_beam_M_influence(L=25.0, x_target_m=12.5)
    print(f"Viga simple L = 25 m, LI de momento en x = 12,5 m: ordenada máxima = {il_mid.ordinates.max():.3f} m")
    print(f"  Efecto del tren de 3 ejes (posición de referencia): M = {envelope_from_il(il_mid, AXLES):.0f} kN·m")
    x_cr, m_cr = critical_position(il_mid, AXLES, udl_kN_per_m=LANE_KN_M)
    print(f"  Posición crítica del primer eje: x = {x_cr:.2f} m → M_max = {m_cr:.0f} kN·m (con carril {LANE_KN_M} kN/m)\n")

    il_sup = two_span_continuous_M_at_support(L1=25.0, L2=25.0)
    print(f"Viga continua 25 + 25 m, LI de momento en el apoyo central: ordenada mínima = {il_sup.ordinates.min():.3f} m")
    # El momento en el apoyo es negativo: se barre la posición del tren y se toma el mínimo
    best_x, best_m = None, 0.0
    for x0 in il_sup.x_m:
        m = sum(P * il_sup.ordinates[int(abs(il_sup.x_m - (x0 + a)).argmin())] for a, P in AXLES
                if 0.0 <= x0 + a <= il_sup.x_m[-1])
        if m < best_m:
            best_x, best_m = float(x0), float(m)
    m_lane = LANE_KN_M * float(il_sup.ordinates.clip(max=0.0).sum() * (il_sup.x_m[1] - il_sup.x_m[0]))
    print(f"  Posición crítica del primer eje: x = {best_x:.2f} m → M_apoyo (tren) = {best_m:.0f} kN·m")
    print(f"  Carril {LANE_KN_M} kN/m en ambos vanos: {m_lane:.0f} kN·m → total {best_m + m_lane:.0f} kN·m")


if __name__ == "__main__":
    main()
