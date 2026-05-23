"""Tests Eurocode LM1 + AASHTO §3.10 + abutment Coulomb."""
import pytest

from bridgejm.loads.eurocode import LM1Input, evaluate_lm1
from bridgejm.seismic import (
    AASHTOSeismicInput, AbutmentInput,
    aashto_design_spectrum, coulomb_pressure,
)


class TestLM1:
    def test_2_carriles(self):
        r = evaluate_lm1(LM1Input(carriageway_width_m=7.0, span_m=30))
        assert r.n_lanes == 2
        assert r.M_total_kNm > 0
        assert r.V_max_kN > 0

    def test_3_carriles_maximo(self):
        r = evaluate_lm1(LM1Input(carriageway_width_m=20.0, span_m=30))
        assert r.n_lanes == 3


class TestAASHTOSpectrum:
    def test_spectrum_shape(self):
        r = aashto_design_spectrum(AASHTOSeismicInput(
            PGA_g=0.4, Ss_g=1.0, S1_g=0.4, Fa=1.2, Fv=1.5,
        ))
        assert r.SDS > 0
        assert r.SD1 > 0
        assert r.Ts > 0
        # Sa(0) ≈ As = 0.4
        assert r.Sa_T_g[0][1] == pytest.approx(0.4 * 1.0, abs=0.1)


class TestCoulomb:
    def test_activo_pasivo(self):
        r = coulomb_pressure(AbutmentInput(
            H_m=6.0, gamma_kN_m3=18, phi_deg=30, delta_deg=20,
        ))
        assert 0 < r.Ka < 1
        assert r.Kp > 1
        assert r.Pa_kN_per_m > 0

    def test_sismico_pae_mayor(self):
        r = coulomb_pressure(AbutmentInput(
            H_m=6, phi_deg=30, kh_seismic=0.15,
        ))
        assert r.Pae_kN_per_m > r.Pa_kN_per_m
