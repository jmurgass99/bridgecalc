"""Envolvente HL-93 multivano: componentes del carril contra formas cerradas y reglas AASHTO."""
import pytest

from bridgecalc.loads.hl93 import LANE_LOAD_kN_per_m
from bridgecalc.loads.multispan import TWO_TRUCK_FACTOR, MultiSpanInput, envelope_multispan

L = 30.0
w = LANE_LOAD_kN_per_m


@pytest.fixture(scope="module")
def two_spans():
    return envelope_multispan(MultiSpanInput(span_m=L, n_spans=2))


def test_carril_momento_negativo_dos_vanos_iguales_wL2_8(two_spans):
    # LI del momento en el apoyo central negativa en toda la viga -> carril en los dos vanos: w L^2 / 8
    assert two_spans.components["M_negative"]["lane_kNm"] == pytest.approx(w * L * L / 8.0, rel=2e-3)
    assert two_spans.M_negative_x_m == pytest.approx(L)


def test_carril_cortante_apoyo_extremo_dos_vanos_7wL_16(two_spans):
    # R_A con el vano 1 cargado (la LI de V en 0+ es positiva en todo el vano 1 y negativa en el 2): 7 w L / 16
    fine = envelope_multispan(MultiSpanInput(span_m=L, n_spans=2, n_points_per_span=600, n_eval_per_span=3))
    end = [s for s in fine.components["V"]["all_sections"] if s["x_m"] < 1.0 and s["sign"] > 0][0]
    # la LI del cortante salta de 0 a 1 en el apoyo: con 600 puntos por vano el trapecio pierde < 0,3 %
    assert end["lane_kN"] == pytest.approx(7.0 * w * L / 16.0, rel=5e-3)
    # El cortante máximo de la viga continua está en la cara del apoyo interior, no en el extremo
    assert two_spans.V_x_m == pytest.approx(L, abs=0.1)


def test_carril_momento_positivo_entre_vano_cargado_y_cota_superior(two_spans):
    # Vano 1 completo cargado da 49/512 w L^2; cargar solo la zona positiva de la LI da algo mayor
    lane = two_spans.components["M_positive"]["lane_kNm"]
    assert 49.0 / 512.0 * w * L * L * 0.995 <= lane <= 0.125 * w * L * L
    assert 0.3 * L <= two_spans.M_positive_x_m <= 0.5 * L or 1.5 * L <= two_spans.M_positive_x_m <= 1.7 * L


def test_momento_negativo_regla_dos_camiones_consistente(two_spans):
    neg = two_spans.components["M_negative"]
    assert neg["two_trucks_total_kNm"] == pytest.approx(TWO_TRUCK_FACTOR * (1.33 * neg["two_trucks_kNm"] + neg["lane_kNm"]), rel=1e-9)
    assert two_spans.M_negative_max_kNm == pytest.approx(max(neg["single_vehicle_total_kNm"], neg["two_trucks_total_kNm"]), rel=1e-9)
    assert neg["two_trucks_gap_m"] >= 15.0


def test_im_solo_sobre_el_vehiculo():
    sin = envelope_multispan(MultiSpanInput(span_m=L, n_spans=2, impact_factor=1.0, n_eval_per_span=6))
    con = envelope_multispan(MultiSpanInput(span_m=L, n_spans=2, impact_factor=1.33, n_eval_per_span=6))
    assert con.components["M_negative"]["lane_kNm"] == pytest.approx(sin.components["M_negative"]["lane_kNm"])
    assert con.M_negative_max_kNm > sin.M_negative_max_kNm


def test_luces_desiguales_simetricas_dan_apoyos_simetricos():
    r = envelope_multispan(MultiSpanInput(span_m=0.0, n_spans=0, spans_m=(30.0, 40.0, 30.0), n_eval_per_span=6))
    assert r.components["spans_m"] == [30.0, 40.0, 30.0]
    assert r.M_negative_max_kNm > 0 and r.M_positive_max_kNm > 0 and r.V_max_kN > 0
    assert r.M_negative_x_m in (30.0, 70.0)


def test_valores_antiguos_por_coeficientes_quedan_lejos(two_spans):
    # 2 x 30 m con el método de coeficientes de la versión 1.0: M+ 1710, M- 2137, V 285
    assert abs(two_spans.M_positive_max_kNm - 1709.88) / 1709.88 > 0.10
    assert abs(two_spans.M_negative_max_kNm - 2137.35) / 2137.35 > 0.10
