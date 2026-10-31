"""Tests para envolvente multi-tramo."""
import pytest

from bridgecalc.loads import MultiSpanInput, envelope_multispan


class TestMultiSpan:
    def test_2_tramos_negativo_mayor_positivo(self):
        # En vigas continuas, |M_neg| ≈ M_pos · 1.25
        r = envelope_multispan(MultiSpanInput(span_m=30, n_spans=2))
        assert r.M_negative_max_kNm > r.M_positive_max_kNm

    def test_3_tramos(self):
        r = envelope_multispan(MultiSpanInput(span_m=30, n_spans=3))
        assert r.M_positive_max_kNm > 0
        assert r.V_max_kN > 0

    def test_n_spans_invalido(self):
        with pytest.raises(ValueError):
            envelope_multispan(MultiSpanInput(span_m=30, n_spans=4))

    def test_luz_invalida(self):
        with pytest.raises(ValueError):
            envelope_multispan(MultiSpanInput(span_m=0, n_spans=2))
