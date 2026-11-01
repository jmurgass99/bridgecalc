"""BWBN: el ciclo cerrado disipa energía positiva y la fuerza tiende a F_y (antes no había lazo)."""
import math

import pytest

from bridgecalc.damping.bwbn import BWBNParams, simulate


def _ciclo(amp, n=400):
    return [amp * math.sin(2 * math.pi * k / n) for k in range(n + 1)]


def _energia(u, F):
    return sum(0.5 * (F[i] + F[i + 1]) * (u[i + 1] - u[i]) for i in range(len(u) - 1))


def test_ciclo_mas_alla_de_fluencia_disipa_energia_positiva():
    p = BWBNParams(alpha=0.05, n=1.0, beta=0.5, gamma=0.5, Fy_kN=250.0, K0_kN_m=20_000.0)
    u = _ciclo(6 * p.uy_m)
    F = simulate(u, p)
    E = _energia(u, F)
    E_ep = 4 * (1 - p.alpha) * p.Fy_kN * (6 * p.uy_m - p.uy_m)   # elastoplástico perfecto
    assert E > 0.5 * E_ep
    assert E < E_ep


def test_fuerza_tiende_a_fy_con_ductilidad_alta():
    p = BWBNParams(alpha=0.0, n=2.0, beta=0.5, gamma=0.5, Fy_kN=250.0, K0_kN_m=20_000.0)
    u = [10 * p.uy_m * k / 200 for k in range(201)]
    F = simulate(u, p)
    assert F[-1] == pytest.approx(p.Fy_kN, rel=0.01)


def test_rama_elastica_inicial_con_rigidez_k0():
    p = BWBNParams(alpha=0.1, Fy_kN=200.0, K0_kN_m=5000.0)
    u = [0.0, 0.001 * p.uy_m]
    F = simulate(u, p)
    assert F[1] / u[1] == pytest.approx(p.K0_kN_m, rel=1e-3)


def test_descarga_mas_rigida_que_la_carga():
    p = BWBNParams(alpha=0.05, n=1.0, beta=0.5, gamma=0.5, Fy_kN=250.0, K0_kN_m=20_000.0)
    u = [4 * p.uy_m * k / 100 for k in range(101)] + [4 * p.uy_m * (1 - k / 100) for k in range(1, 11)]
    F = simulate(u, p)
    k_carga = (F[100] - F[99]) / (u[100] - u[99])
    k_descarga = (F[101] - F[100]) / (u[101] - u[100])
    assert k_descarga > 5 * k_carga


def test_degradacion_de_resistencia_reduce_la_fuerza_en_ciclos_repetidos():
    base = dict(alpha=0.05, n=1.0, beta=0.5, gamma=0.5, Fy_kN=250.0, K0_kN_m=20_000.0)
    p0, pd = BWBNParams(**base), BWBNParams(delta_eta=0.05, **base)
    u = []
    for _ in range(5):
        u += _ciclo(4 * p0.uy_m)[:-1]
    u.append(0.0)
    F0, Fd = simulate(u, p0), simulate(u, pd)
    assert max(Fd[-400:]) < max(F0[-400:])
