"""Test de integración y golden analítico para cargas de tráfico en puentes.

Norma: EN 1991-2 §4.3.2 (Load Model 1) y §4.3.3 (Load Model 2).
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bridgejm.api.app import create_router
from bridgejm.ec1_traffic import LM1, LM2, traffic_envelope_lm1


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(create_router())
    return TestClient(app)


def test_lm1_hand_calculation_golden():
    """Golden analítico para puente biapoyado L=20 m bajo LM1 (EN 1991-2 §4.3.2).

    CORREGIDO. La versión anterior enunciaba `M_ts1 = 2,904.6` sin derivarlo, y
    ese número salía de sumar el momento de la sección 9.4 m con el de la sección
    10.0 m: `300*(4.982 + 4.700)`. Un momento flector es una magnitud DE UNA
    SECCIÓN. Ver `test_ec1_tandem_barre.py`, que valida la forma cerrada contra
    una búsqueda numérica sobre todas las posiciones y todas las secciones.

    Derivación manual completa:
      UDL:
        Carril 1: 9.0 kPa * 3.0 m = 27.0 kN/m
        Carril 2: 2.5 kPa * 3.0 m =  7.5 kN/m
        Total w = 34.5 kN/m
        M_udl = 34.5 * 20² / 8 = 1,725.0 kN·m
        V_udl = 34.5 * 20 / 2  =   345.0 kN
      Tandem System (a = 1.2 m), máximo absoluto por el teorema de Barré. Para
      dos ejes iguales la resultante cae en el punto medio, luego el eje crítico
      va a a/4 = 0.3 m del centro de luz:
        x_c = 20/2 - 1.2/4 = 9.70 m
        Carril 1 (Q=300): R_L = 300*(10.3+9.1)/20 = 291.0 -> M = 291.0*9.7 = 2,822.7
        Carril 2 (Q=200): R_L = 200*(10.3+9.1)/20 = 194.0 -> M = 194.0*9.7 = 1,881.8
        Total TS: M_ts = 4,704.5 kN·m
        Cortante (sin cambio): un eje sobre el apoyo, el otro a 1.2 m
        V_ts1 = 300 + 300*18.8/20 = 582.0 ; V_ts2 = 200 + 200*18.8/20 = 388.0
      Envolvente:
        M_max = 1725.0 + 4704.5 = 6,429.5 kN·m   (antes 6,566.0; -2.08 %)
        V_max =  345.0 +  970.0 = 1,315.0 kN     (sin cambio)
    """
    L = 20.0
    n_lanes = 2
    M_max, V_max = traffic_envelope_lm1(L_span=L, n_lanes=n_lanes)

    assert M_max == pytest.approx(6429.5, rel=1e-5)
    assert V_max == pytest.approx(1315.0, rel=1e-5)


def test_lm2_single_axle_value():
    """Golden LM2 eje simple de 400 kN (EN 1991-2 §4.3.3)."""
    lm2 = LM2(beta_Q=1.0)
    assert lm2.Qak_kN == pytest.approx(400.0, rel=1e-6)

    lm2_dyn = LM2(beta_Q=1.20)
    assert lm2_dyn.Qak_kN == pytest.approx(480.0, rel=1e-6)


def test_bridge_traffic_api_endpoints(client):
    """Verifica endpoints /api/bridge/traffic/lm1 y /api/bridge/traffic/lm2."""
    # 1. LM1
    resp1 = client.post("/api/bridge/traffic/lm1", json={
        "span_m": 20.0,
        "n_lanes": 2,
        "lane_width": 3.0,
    })
    assert resp1.status_code == 200, resp1.text
    data1 = resp1.json()
    assert data1["M_max_kNm"] == pytest.approx(6429.5, rel=1e-4)
    assert data1["V_max_kN"] == pytest.approx(1315.0, rel=1e-4)
    assert len(data1["lanes"]) == 2

    # 2. LM2
    resp2 = client.post("/api/bridge/traffic/lm2", json={"beta_Q": 1.0})
    assert resp2.status_code == 200, resp2.text
    data2 = resp2.json()
    assert data2["Qak_kN"] == 400.0
