"""Tests BJ-002: trenes de carga adicionales — Eurocode LM1/LM2 + NCh HL-93K."""
import pytest

from bridgejm.loads.eurocode_lm1 import (
    EurocodeLM1Input,
    EurocodeLM2Input,
    evaluate_eurocode_lm1,
    evaluate_eurocode_lm2,
    LM1_TS_AXLE_kN_PER_LANE,
    LM1_UDL_kN_per_m2_PER_LANE,
    LM2_AXLE_LOAD_kN,
)
from bridgejm.loads.hl93 import (
    HL93KNChConfiguration,
    hl93k_nch_envelope,
    NCH_TRUCK_AXLES_kN,
    NCH_TRUCK_AXLE_SPACINGS_m,
)


class TestEurocodeLM1:
    def test_carga_total_TS_carril_1(self):
        """TS carril 1: 2 ejes x 300 kN = 600 kN."""
        r = evaluate_eurocode_lm1(EurocodeLM1Input(
            carriageway_width_m=3.5, span_m=30, n_lanes=1,
        ))
        assert r.total_TS_load_kN == pytest.approx(600.0)

    def test_UDL_carril_1(self):
        """UDL carril 1: 9 kN/m2 x 3m = 27 kN/m."""
        r = evaluate_eurocode_lm1(EurocodeLM1Input(
            carriageway_width_m=3.5, span_m=30, n_lanes=1,
        ))
        assert r.total_UDL_load_kN_per_m == pytest.approx(27.0)

    def test_2_carriles(self):
        r = evaluate_eurocode_lm1(EurocodeLM1Input(
            carriageway_width_m=7.0, span_m=30,
        ))
        assert r.n_lanes == 2
        # TS: 2x300 + 2x200 = 1000 kN
        assert r.total_TS_load_kN == pytest.approx(1000.0)

    def test_3_carriles(self):
        r = evaluate_eurocode_lm1(EurocodeLM1Input(
            carriageway_width_m=12.0, span_m=30,
        ))
        assert r.n_lanes == 3

    def test_M_crece_con_luz(self):
        m20 = evaluate_eurocode_lm1(EurocodeLM1Input(
            carriageway_width_m=7.0, span_m=20,
        )).M_total_kNm
        m40 = evaluate_eurocode_lm1(EurocodeLM1Input(
            carriageway_width_m=7.0, span_m=40,
        )).M_total_kNm
        assert m40 > m20

    def test_alpha_factors(self):
        """Los factores alpha deben reducir las cargas."""
        r_base = evaluate_eurocode_lm1(EurocodeLM1Input(
            carriageway_width_m=7.0, span_m=30,
        ))
        r_reduced = evaluate_eurocode_lm1(EurocodeLM1Input(
            carriageway_width_m=7.0, span_m=30, alpha_Q1=0.8, alpha_q1=0.7,
        ))
        assert r_reduced.M_total_kNm < r_base.M_total_kNm

    def test_input_invalido(self):
        with pytest.raises(ValueError):
            evaluate_eurocode_lm1(EurocodeLM1Input(
                carriageway_width_m=7.0, span_m=0,
            ))

    def test_to_dict(self):
        r = evaluate_eurocode_lm1(EurocodeLM1Input(
            carriageway_width_m=7.0, span_m=25,
        ))
        d = r.to_dict()
        assert "M_total_kNm" in d
        assert d["M_total_kNm"] > 0


class TestEurocodeLM2:
    def test_carga_eje_400kN(self):
        """LM2: eje de 400 kN."""
        r = evaluate_eurocode_lm2(EurocodeLM2Input(span_m=20))
        assert r.axle_load_kN == pytest.approx(400.0)

    def test_M_max(self):
        """M_max = Q*L/4 para eje en midspan."""
        r = evaluate_eurocode_lm2(EurocodeLM2Input(span_m=20))
        assert r.M_max_kNm == pytest.approx(400.0 * 20 / 4)

    def test_V_max(self):
        """V_max = Q para eje en apoyo."""
        r = evaluate_eurocode_lm2(EurocodeLM2Input(span_m=20))
        assert r.V_max_kN == pytest.approx(400.0)

    def test_beta_factor(self):
        r = evaluate_eurocode_lm2(EurocodeLM2Input(span_m=10, beta_Q=0.8))
        assert r.axle_load_kN == pytest.approx(320.0)

    def test_input_invalido(self):
        with pytest.raises(ValueError):
            evaluate_eurocode_lm2(EurocodeLM2Input(span_m=0))


class TestHL93KNCh:
    def test_carga_total_432kN(self):
        """Camion NCh: 62 + 185 + 185 = 432 kN (44 ton)."""
        r = hl93k_nch_envelope(HL93KNChConfiguration(span_m=30))
        assert r.total_truck_load_kN == pytest.approx(432.0)

    def test_posicion_ejes(self):
        """Separaciones: 4.0 + 4.0 m."""
        assert NCH_TRUCK_AXLE_SPACINGS_m == (4.0, 4.0)

    def test_ejes_correctos(self):
        assert NCH_TRUCK_AXLES_kN == (62.0, 185.0, 185.0)

    def test_M_positivo(self):
        r = hl93k_nch_envelope(HL93KNChConfiguration(span_m=25))
        assert r.M_max_kNm > 0
        assert r.V_max_kN > 0

    def test_M_crece_con_luz(self):
        m15 = hl93k_nch_envelope(HL93KNChConfiguration(span_m=15)).M_max_kNm
        m30 = hl93k_nch_envelope(HL93KNChConfiguration(span_m=30)).M_max_kNm
        assert m30 > m15

    def test_comparacion_con_hl93(self):
        """NCh deberia dar M similar al HL-93 (ambos ~430 kN truck)."""
        from bridgejm.loads.hl93 import HL93Configuration, hl93_influence_envelope
        r_nch = hl93k_nch_envelope(HL93KNChConfiguration(span_m=30))
        r_hl93 = hl93_influence_envelope(HL93Configuration(span_m=30))
        # Deben ser del mismo orden de magnitud
        ratio = r_nch.M_max_kNm / r_hl93.M_max_kNm
        assert 0.5 < ratio < 1.5

    def test_input_invalido(self):
        with pytest.raises(ValueError):
            hl93k_nch_envelope(HL93KNChConfiguration(span_m=0))
