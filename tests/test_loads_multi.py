"""Tests AS 5100 + CC-40 cargas."""
import pytest

from bridgejm.loads.multi_code import (
    AS5100Input, CC40Input, evaluate_as5100, evaluate_cc40,
)


def test_as5100_creciente_luz():
    r1 = evaluate_as5100(AS5100Input(span_m=20))
    r2 = evaluate_as5100(AS5100Input(span_m=50))
    assert r2.M_max_kNm > r1.M_max_kNm


def test_as5100_n_lanes_escala():
    r1 = evaluate_as5100(AS5100Input(span_m=30, n_lanes=1))
    r2 = evaluate_as5100(AS5100Input(span_m=30, n_lanes=3))
    assert r2.M_max_kNm > r1.M_max_kNm


def test_cc40_devuelve_dict():
    r = evaluate_cc40(CC40Input(span_m=25))
    assert "M_total_kNm" in r and r["M_total_kNm"] > 0


def test_input_invalido():
    with pytest.raises(ValueError):
        evaluate_as5100(AS5100Input(span_m=0))
    with pytest.raises(ValueError):
        evaluate_cc40(CC40Input(span_m=0))
