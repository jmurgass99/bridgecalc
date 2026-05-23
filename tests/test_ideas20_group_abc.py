"""Tests para IDEAS_20 grupos A/B/C en BridgeJm."""
import pytest


def test_lrfd_hl93_corto():
    from bridgejm.memos.lrfd_hl93 import HL93MemoInput, generar_memoria_hl93
    res = generar_memoria_hl93(HL93MemoInput(L_span_m=10))
    assert res.M_DC_kNm > 0
    assert res.M_Strength_I_kNm > 0
    assert "Strength I" in res.markdown


def test_lrfd_hl93_largo():
    from bridgejm.memos.lrfd_hl93 import HL93MemoInput, generar_memoria_hl93
    res = generar_memoria_hl93(HL93MemoInput(L_span_m=30))
    assert res.M_truck_kNm > 0


def test_bwbn_lineal():
    from bridgejm.damping.bwbn import BWBNParams, simulate
    p = BWBNParams()
    u_hist = [0.0, 0.001, 0.002, 0.003, 0.004]
    F = simulate(u_hist, p, dt=0.01)
    assert len(F) == len(u_hist)
    assert F[1] > 0


def test_bwbn_histeresis_no_lineal():
    from bridgejm.damping.bwbn import BWBNParams, simulate
    p = BWBNParams(alpha=0.05)
    u = [0.0]
    for i in range(1, 50):
        u.append(0.01 * (i if i < 25 else 50 - i))
    F = simulate(u, p, dt=0.01)
    assert len(F) == 50
    assert max(F) > 0


def test_dynamics_pushover_cepa():
    from bridgejm.integration.dynamics_pushover import (
        CepaPushoverInput, pushover_cepa,
    )
    res = pushover_cepa(CepaPushoverInput(H_cepa_m=8, D_cepa_m=1.5))
    assert res.Vy_kN > 0
    assert res.delta_u_mm > res.delta_y_mm
    assert res.mu_disp > 1.0


def test_foundation_cepa():
    from bridgejm.integration.foundation_cepa import (
        CepaFoundationInput, disenar_cimiento_cepa,
    )
    res = disenar_cimiento_cepa(CepaFoundationInput(
        N_kN=5000, M_kNm=2000, V_kN=500, D_cepa_m=1.5, n_piles=8,
    ))
    assert res.Q_pile_max_kN > res.Q_pile_min_kN
