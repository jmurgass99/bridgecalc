"""Amortiguador histerético Bouc-Wen-Baber-Noori paso a paso: historia sinusoidal de desplazamiento con amplitud creciente, lazos fuerza-desplazamiento, energía disipada por ciclo, efecto del exponente n y de la degradación de rigidez y resistencia.

`bwbn_step` avanza la variable histerética z con dz = (A·du − ν·(β·sgn(du·z)·|z|ⁿ·|du| + γ·|z|ⁿ·du))/η
y devuelve F = α·K₀·u + (1 − α)·F_y·z; `simulate` recorre una historia completa. Se calcula la
energía de cada lazo por integración trapezoidal de F·du.

Ejecutar:  python examples/bwbn_hysteresis_damper_sinusoidal_history_force_displacement_loops_dissipated_energy_and_degradation.py
"""
import math

from bridgecalc.damping.bwbn import BWBNParams, simulate


def energia_por_ciclo(u, F, n_ciclos, pts_ciclo):
    out = []
    for c in range(n_ciclos):
        i0, i1 = c * pts_ciclo, (c + 1) * pts_ciclo
        E = sum(0.5 * (F[i] + F[i + 1]) * (u[i + 1] - u[i]) for i in range(i0, min(i1, len(u) - 1)))
        out.append(E)
    return out


def main() -> None:
    p = BWBNParams(alpha=0.05, n=1.0, beta=0.5, gamma=0.5, Fy_kN=250.0, K0_kN_m=20_000.0)
    uy = p.Fy_kN / p.K0_kN_m
    print(f"Parámetros: α = {p.alpha}, n = {p.n}, β = γ = {p.beta}, F_y = {p.Fy_kN} kN, K₀ = {p.K0_kN_m} kN/m → u_y = F_y/K₀ = {uy * 1000:.1f} mm\n")
    pts, ciclos = 200, 5
    amp = [0.5 * uy, 1.0 * uy, 2.0 * uy, 4.0 * uy, 6.0 * uy]
    u = []
    for c in range(ciclos):
        u += [amp[c] * math.sin(2 * math.pi * k / pts) for k in range(pts)]
    u.append(0.0)
    F = simulate(u, p, dt=0.01)
    E = energia_por_ciclo(u, F, ciclos, pts)
    print(f"  {'ciclo':>5} {'amplitud [mm]':>13} {'μ = u/u_y':>9} {'F_máx [kN]':>10} {'F/F_y':>6} {'E_h [kN·m]':>10} {'E/(4·F_y·(u−u_y))':>18}")
    for c in range(ciclos):
        seg = F[c * pts:(c + 1) * pts]
        Fmax = max(seg)
        ratio = "%.2f" % (E[c] / (4 * p.Fy_kN * (amp[c] - uy))) if amp[c] > uy else "— (sin fluencia)"
        print(f"  {c + 1:5d} {amp[c] * 1000:13.1f} {amp[c] / uy:9.1f} {Fmax:10.1f} {Fmax / p.Fy_kN:6.3f} {E[c]:10.3f} {ratio:>18}")
    print("  El lazo elastoplástico ideal disipa 4·F_y·(u_max − u_y) por ciclo; con n = 1 la transición es suave y la energía queda entre el 72 y el 90 % del ideal; "
          f"con α = 0,05 la fuerza sigue creciendo tras F_y ({p.alpha * p.K0_kN_m:.0f} kN/m de rigidez posfluencia), y por debajo de u_y el lazo ya disipa algo (Bouc-Wen no tiene rama elástica pura).\n")
    print("Exponente n (transición elástica-plástica), ciclo a 4·u_y:")
    for n in (1.0, 2.0, 5.0):
        pn = BWBNParams(alpha=0.05, n=n, beta=0.5, gamma=0.5, Fy_kN=250.0, K0_kN_m=20_000.0)
        uc = [4 * uy * math.sin(2 * math.pi * k / pts) for k in range(pts + 1)]
        Fc = simulate(uc, pn, dt=0.01)
        print(f"  n = {n:3.1f}: F_máx {max(Fc):6.1f} kN, E_h {energia_por_ciclo(uc, Fc, 1, pts)[0]:.3f} kN·m")
    print("\nDegradación (δ_ν rigidez, δ_η resistencia) en 5 ciclos iguales a 4·u_y:")
    uc = []
    for c in range(5):
        uc += [4 * uy * math.sin(2 * math.pi * k / pts) for k in range(pts)]
    uc.append(0.0)
    for dnu, deta in ((0.0, 0.0), (0.05, 0.0), (0.0, 0.05), (0.05, 0.05)):
        pd = BWBNParams(alpha=0.05, n=1.0, beta=0.5, gamma=0.5, delta_nu=dnu, delta_eta=deta, Fy_kN=250.0, K0_kN_m=20_000.0)
        Fd = simulate(uc, pd, dt=0.01)
        Ed = energia_por_ciclo(uc, Fd, 5, pts)
        print(f"  δ_ν = {dnu:.2f}, δ_η = {deta:.2f}: F_máx ciclo 1 {max(Fd[:pts]):.1f} → ciclo 5 {max(Fd[4 * pts:5 * pts]):.1f} kN; E_h {Ed[0]:.3f} → {Ed[4]:.3f} kN·m")
    print("\nbwbn_step subdivide cada incremento en subpasos de |du|/u_y ≤ 0,02 (Euler explícito), así que la historia puede ser gruesa. "
          "Hasta 1.0 la descarga seguía la misma ley que la carga (sin lazo: energía nula) y z no se normalizaba por u_y (la fuerza no pasaba de 0,37·F_y con μ = 6). "
          "No hay pinzamiento (los parámetros de pinching de BWBN no están implementados) ni dependencia de la velocidad: es un disipador histerético, no viscoso.")


if __name__ == "__main__":
    main()
