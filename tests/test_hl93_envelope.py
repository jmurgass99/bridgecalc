"""Tests de la envolvente HL-93 (idea #12): firma de conveniencia
``hl93_envelope(L_m, ...)`` anclada a un calculo manual AASHTO LRFD.

Viga simplemente apoyada L=30 m. Calculo manual del camion de diseno
(35/145/145 kN @4.27 m), tandem (2x110 kN @1.2 m) y carril (9.34 kN/m),
con IM=33 % aplicado SOLO al vehiculo (LRFD 3.6.1.3 / 3.6.2):

  M_truck (sin IM, posicion critica bajo eje central) ~ 2059 kNm  (GOBIERNA)
  M_tandem (sin IM)                                    ~ 1585 kNm
  M_lane  = 9.34 * 30^2 / 8                             = 1050.75 kNm
  M_max   = 2059*1.33 + 1050.75                         ~ 3789 kNm

  V_truck (sin IM, ejes pesados al apoyo)              ~ 294.4 kN
  V_lane  = 9.34 * 30 / 2                              = 140.1 kN
  V_max   = 294.4*1.33 + 140.1                          ~ 531.6 kN
"""
import pytest

from bridgecalc.loads.hl93 import hl93_envelope


def test_hl93_envelope_L30_momento_ancla_aashto():
    r = hl93_envelope(30.0)
    # Ancla de validacion AASHTO (calculo manual): ~3789 kNm, ~1 % de tol
    # por la discretizacion del barrido.
    assert r["M_max_kNm"] == pytest.approx(3789.0, rel=0.01)
    assert r["governing_vehicle"] == "truck"


def test_hl93_envelope_L30_cortante_ancla_aashto():
    r = hl93_envelope(30.0)
    assert r["V_max_kN"] == pytest.approx(531.6, rel=0.01)


def test_hl93_envelope_desglose():
    r = hl93_envelope(30.0)
    # El carril es exacto (formula cerrada): 9.34 * 30^2 / 8 = 1050.75
    assert r["M_lane_kNm"] == pytest.approx(9.34 * 30.0 ** 2 / 8.0)
    assert r["V_lane_kN"] == pytest.approx(9.34 * 30.0 / 2.0)
    # En luz media el camion gobierna sobre el tandem
    assert r["M_truck_kNm"] > r["M_tandem_kNm"]
    # M_max = max(truck,tandem)*IM + lane (IM solo al vehiculo)
    expected = max(r["M_truck_kNm"], r["M_tandem_kNm"]) * r["IM"] + r["M_lane_kNm"]
    assert r["M_max_kNm"] == pytest.approx(expected, rel=1e-6)
    assert r["IM"] == 1.33


def test_hl93_envelope_IM_configurable():
    sin_im = hl93_envelope(30.0, impact_factor=1.0)
    con_im = hl93_envelope(30.0, impact_factor=1.33)
    # Con IM la solicitacion vehicular crece; el carril no cambia.
    assert con_im["M_max_kNm"] > sin_im["M_max_kNm"]
    assert con_im["M_lane_kNm"] == pytest.approx(sin_im["M_lane_kNm"])


def test_hl93_envelope_tandem_gobierna_luz_corta():
    # En luces cortas el tandem (220 kN concentrados) supera al camion.
    r = hl93_envelope(6.0)
    assert r["M_tandem_kNm"] > r["M_truck_kNm"]
    assert r["governing_vehicle"] == "tandem"


def test_hl93_envelope_luz_invalida():
    with pytest.raises(ValueError):
        hl93_envelope(0.0)
