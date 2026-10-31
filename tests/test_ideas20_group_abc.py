"""Tests para IDEAS_20 grupos A/B/C en BridgeCalc."""
import pytest


def test_lrfd_hl93_corto():
    from bridgecalc.memos.lrfd_hl93 import HL93MemoInput, generar_memoria_hl93
    res = generar_memoria_hl93(HL93MemoInput(L_span_m=10))
    assert res.M_DC_kNm > 0
    assert res.M_Strength_I_kNm > 0
    assert "Strength I" in res.markdown


def test_lrfd_hl93_largo():
    from bridgecalc.memos.lrfd_hl93 import HL93MemoInput, generar_memoria_hl93
    res = generar_memoria_hl93(HL93MemoInput(L_span_m=30))
    assert res.M_truck_kNm > 0


def test_bwbn_lineal():
    from bridgecalc.damping.bwbn import BWBNParams, simulate
    p = BWBNParams()
    u_hist = [0.0, 0.001, 0.002, 0.003, 0.004]
    F = simulate(u_hist, p, dt=0.01)
    assert len(F) == len(u_hist)
    assert F[1] > 0


def test_bwbn_histeresis_no_lineal():
    from bridgecalc.damping.bwbn import BWBNParams, simulate
    p = BWBNParams(alpha=0.05)
    u = [0.0]
    for i in range(1, 50):
        u.append(0.01 * (i if i < 25 else 50 - i))
    F = simulate(u, p, dt=0.01)
    assert len(F) == 50
    assert max(F) > 0
