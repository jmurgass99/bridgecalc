"""Test API BridgeCalc."""
import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from bridgecalc.api import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_hl93_single(client):
    r = client.post("/api/bridge/hl93/single", json={"span_m": 30.0})
    assert r.status_code == 200
    body = r.json()
    assert body["M_max_kNm"] > 0


def test_multispan(client):
    r = client.post("/api/bridge/hl93/multispan",
                    json={"span_m": 30, "n_spans": 2})
    assert r.status_code == 200
    assert r.json()["M_negative_max_kNm"] > 0


def test_park_ang_endpoint(client):
    r = client.post("/api/bridge/fragility/park-ang", json={
        "delta_max": 10, "delta_u": 50, "E_h": 100, "F_y": 100,
    })
    assert r.status_code == 200
    assert "damage_index" in r.json()
