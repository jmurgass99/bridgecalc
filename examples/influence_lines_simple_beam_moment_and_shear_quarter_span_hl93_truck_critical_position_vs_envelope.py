"""Líneas de influencia de una viga biapoyada de 25 m: momento en el centro y en el cuarto de la luz, cortante en el cuarto, posición crítica del camión HL-93 en los dos sentidos de marcha y comparación con la envolvente de hl93_envelope.

`simple_beam_M_influence` y `simple_beam_V_influence` dan la línea de influencia (ordenada = efecto
por carga unidad); `critical_position` barre un tren de cargas y coloca el carril solo donde la
ordenada es positiva; `envelope_from_il` evalúa un tren en una posición dada. La línea de influencia
en una sección fija da el máximo EN ESA SECCIÓN; la envolvente mueve además la sección (Barré).

Ejecutar:  python examples/influence_lines_simple_beam_moment_and_shear_quarter_span_hl93_truck_critical_position_vs_envelope.py
"""
import numpy as np

from bridgecalc.loads.hl93 import LANE_LOAD_kN_per_m, TRUCK_AXLE_SPACINGS_m, TRUCK_AXLES_kN, hl93_envelope
from bridgecalc.loads.influence_lines import critical_position, envelope_from_il, simple_beam_M_influence, simple_beam_V_influence

L = 25.0
TRUCK = [(0.0, TRUCK_AXLES_kN[0]), (TRUCK_AXLE_SPACINGS_m[0], TRUCK_AXLES_kN[1]), (sum(TRUCK_AXLE_SPACINGS_m), TRUCK_AXLES_kN[2])]
TRUCK_REV = [(0.0, TRUCK_AXLES_kN[2]), (TRUCK_AXLE_SPACINGS_m[1], TRUCK_AXLES_kN[1]), (sum(TRUCK_AXLE_SPACINGS_m), TRUCK_AXLES_kN[0])]


def main() -> None:
    il_mid = simple_beam_M_influence(L, L / 2, n_points=501)
    il_q = simple_beam_M_influence(L, L / 4, n_points=501)
    print(f"Viga biapoyada L = {L:.0f} m. LI de momento: ordenada máxima en el centro {il_mid.ordinates.max():.3f} m (= L/4), en el cuarto {il_q.ordinates.max():.4f} m (= 3L/16)")
    print(f"  Camión HL-93 {TRUCK_AXLES_kN} kN a {TRUCK_AXLE_SPACINGS_m} m; carril {LANE_LOAD_kN_per_m} kN/m\n")
    print(f"  {'sección / tren':44} {'x 1er eje [m]':>13} {'efecto [kN·m]':>13}")
    for nombre, il in (("M en L/2", il_mid), ("M en L/4", il_q)):
        for lbl, train in (("camión, 35 kN delante", TRUCK), ("camión, 35 kN detrás", TRUCK_REV)):
            x, e = critical_position(il, train)
            print(f"  {nombre + ', ' + lbl:44} {x:13.2f} {e:13.1f}")
        x, e = critical_position(il, TRUCK, udl_kN_per_m=LANE_LOAD_kN_per_m)
        print(f"  {nombre + ', camión + carril en zona positiva':44} {x:13.2f} {e:13.1f}")
    e_env = hl93_envelope(L)
    x, e_il = critical_position(il_mid, TRUCK)
    print(f"\nMomento del camión en la sección central por LI: {e_il:.1f} kN·m; envolvente hl93_envelope (sección móvil, Barré): {e_env['M_truck_kNm']:.1f} kN·m "
          f"({(e_env['M_truck_kNm'] / e_il - 1) * 100:+.2f} %): el máximo absoluto está bajo el eje central a 0,72 m del centro, no en el centro.")
    fijo = envelope_from_il(il_mid, [(8.0, 35.0), (12.27, 145.0), (16.54, 145.0)])
    print(f"Tren en una posición dada (eje delantero en 8,0 m): M_centro = {fijo:.1f} kN·m (envelope_from_il, sin barrido)\n")

    il_v = simple_beam_V_influence(L, L / 4, n_points=501)
    print(f"LI de cortante en x = L/4: salta de {il_v.ordinates[np.searchsorted(il_v.x_m, L / 4) - 1]:+.3f} a {il_v.ordinates[np.searchsorted(il_v.x_m, L / 4) + 1]:+.3f} al pasar la sección (−x/L a (L−x)/L)")
    x, e = critical_position(il_v, TRUCK_REV)
    print(f"  Camión con los ejes pesados justo a la derecha de la sección: x 1er eje = {x:.2f} m → V = {e:.1f} kN; "
          f"con carril en la zona positiva: {critical_position(il_v, TRUCK_REV, udl_kN_per_m=LANE_LOAD_kN_per_m)[1]:.1f} kN")
    print(f"  Cortante en el apoyo (envolvente): {e_env['V_max_kN']:.1f} kN con IM y carril; sin IM el camión solo da {(e_env['V_max_kN'] - e_env['V_lane_kN']) / e_env['IM']:.1f} kN")
    print("\ncritical_position suma el carril sobre toda la zona de ordenada positiva (correcto para máximos positivos); para efectos negativos invierte el signo de la LI antes de llamar. "
          "La malla manda: con 200 puntos el error de posición es L/200; aquí se usan 501.")


if __name__ == "__main__":
    main()
