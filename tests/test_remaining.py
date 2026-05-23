"""Tests influencias + span optimization."""
import numpy as np
import pytest

from bridgejm.loads.influence_lines import (
    envelope_from_il, simple_beam_M_influence,
    simple_beam_V_influence, two_span_continuous_M_at_support,
)
from bridgejm.optimization import SpanOptimizationInput, optimize_n_spans


class TestInfluence:
    def test_M_centro_max(self):
        il = simple_beam_M_influence(L=10, x_target_m=5)
        # Max influence en x = x_target = 5
        idx = int(np.argmax(il.ordinates))
        assert abs(il.x_m[idx] - 5.0) < 0.5

    def test_V_cambio_signo(self):
        il = simple_beam_V_influence(L=10, x_target_m=5)
        # En x=0 ordenada=0 (-x/L), en x=L ordenada=0 ((L-x)/L)
        # Cambio de signo cerca de x_target_m
        n = len(il.ordinates)
        # Cuartil antes negativo, cuartil después positivo
        assert il.ordinates[n // 4] < 0
        assert il.ordinates[3 * n // 4] > 0

    def test_continuous_negative(self):
        il = two_span_continuous_M_at_support(L1=10, L2=10)
        # En apoyo intermedio: ordenadas son negativas
        assert all(o <= 0 for o in il.ordinates)


class TestOptimization:
    def test_optimal_finite(self):
        r = optimize_n_spans(SpanOptimizationInput(total_length_m=200))
        assert r.optimal_n_spans >= 1
        assert r.optimal_span_m > 0
        assert r.total_cost_USD < float("inf")

    def test_costo_pier_alto_favorece_pocos_vanos(self):
        cheap = optimize_n_spans(SpanOptimizationInput(
            total_length_m=200, cost_pier_USD_per_unit=50_000,
        ))
        exp = optimize_n_spans(SpanOptimizationInput(
            total_length_m=200, cost_pier_USD_per_unit=2_000_000,
        ))
        assert exp.optimal_n_spans <= cheap.optimal_n_spans
