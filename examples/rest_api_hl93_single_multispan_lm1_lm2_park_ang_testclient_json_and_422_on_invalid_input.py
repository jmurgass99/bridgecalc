"""API REST sin servidor (FastAPI TestClient): envolvente HL-93 de vano simple y de viga continua, LM1 y LM2 de EN 1991-2, índice de Park-Ang, y las respuestas 422 de validación cuando la entrada no es admisible.

`bridgecalc.api.create_app()` monta `/health`, `/api/bridge/hl93/single`, `/api/bridge/hl93/multispan`
(2 a 6 vanos desde 1.1.0), `/api/bridge/traffic/lm1`, `/api/bridge/traffic/lm2` y
`/api/bridge/fragility/park-ang`. Los modelos Pydantic rechazan luces ≤ 0 y vanos fuera de rango con
422; los ValueError del núcleo se traducen a 400. Requiere el extra `api`.

Ejecutar:  python examples/rest_api_hl93_single_multispan_lm1_lm2_park_ang_testclient_json_and_422_on_invalid_input.py
"""


def main() -> None:
    import warnings

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")   # aviso de starlette sobre httpx al importar, ajeno a bridgecalc
            from fastapi.testclient import TestClient

        from bridgecalc.api import create_app
    except ImportError as exc:
        print(f"FastAPI no disponible ({exc}): instala `bridgecalc[api]`.")
        return
    app = create_app()
    client = TestClient(app)
    print(f"API «{app.title}» v{app.version}; GET /health → {client.get('/health').json()}")
    rutas = sorted(p for p in app.openapi()["paths"] if p.startswith("/api"))
    print(f"  Rutas: {rutas}\n")
    r = client.post("/api/bridge/hl93/single", json={"span_m": 30.0})
    print(f"POST hl93/single span 30 → {r.status_code}: {r.json()}")
    r = client.post("/api/bridge/hl93/single", json={"span_m": 30.0, "impact_factor": 1.0})
    print(f"  sin IM: M = {r.json()['M_max_kNm']:.0f} kN·m")
    r = client.post("/api/bridge/hl93/multispan", json={"span_m": 30.0, "n_spans": 2})
    j = r.json()
    print(f"\nPOST hl93/multispan 2 × 30 → {r.status_code}: M⁺ {j['M_positive_max_kNm']:.0f} kN·m en x = {j['M_positive_x_m']:.2f} m, M⁻ {j['M_negative_max_kNm']:.0f} en x = {j['M_negative_x_m']:.0f}, V {j['V_max_kN']:.0f} kN")
    print(f"  método: {j['method']}; gobierna: {j['governing']}")
    print(f"  componentes M⁻: regla «{j['components']['M_negative']['rule']}», carril {j['components']['M_negative']['lane_kNm']:.0f} kN·m, dos camiones a {j['components']['M_negative']['two_trucks_gap_m']:.0f} m")
    r = client.post("/api/bridge/traffic/lm1", json={"span_m": 20.0, "n_lanes": 2})
    j = r.json()
    print(f"\nPOST traffic/lm1 L 20 m, 2 carriles → {r.status_code}: M {j['M_max_kNm']:.1f} kN·m, V {j['V_max_kN']:.1f} kN, {j['code']}; carriles {j['lanes']}")
    r = client.post("/api/bridge/traffic/lm1", json={"span_m": 20.0, "n_lanes": 2, "alpha_Q": 0.9, "alpha_q": 0.8})
    print(f"  con α_Q 0,9 y α_q 0,8 (anexo nacional): M {r.json()['M_max_kNm']:.1f} kN·m")
    r = client.post("/api/bridge/traffic/lm2", json={"beta_Q": 1.0})
    print(f"POST traffic/lm2 → {r.json()}")
    r = client.post("/api/bridge/fragility/park-ang", json={"delta_max": 120.0, "delta_u": 180.0, "E_h": 150000.0, "F_y": 900.0})
    print(f"POST fragility/park-ang → {r.json()}")
    print("  La API llama «collapse_risk» a todo DI ≥ 0,7; la escala de Park-Ang que cita el módulo reserva el colapso para DI > 1,0, así que 0,7–1,0 es daño severo, no colapso.\n")
    for ruta, payload, desc in (("hl93/single", {"span_m": 0.0}, "luz 0"), ("hl93/single", {"span_m": -5.0}, "luz negativa"), ("hl93/multispan", {"span_m": 30.0, "n_spans": 7}, "7 vanos"),
                                ("hl93/multispan", {"span_m": 30.0, "n_spans": 1}, "1 vano"), ("traffic/lm1", {"span_m": 20.0, "n_lanes": 9}, "9 carriles"), ("fragility/park-ang", {"delta_max": 1.0, "delta_u": 0.0, "E_h": 1.0, "F_y": 1.0}, "δ_u = 0")):
        r = client.post(f"/api/bridge/{ruta}", json=payload)
        det = r.json().get("detail")
        if isinstance(det, list):
            det = "; ".join(f"{'.'.join(str(x) for x in d['loc'][1:])}: {d['msg']}" for d in det)
        print(f"  {ruta} con {desc} → {r.status_code}: {det}")
    print("\nLa validación de rango la hace Pydantic (422) antes de llegar al núcleo; los ValueError del núcleo que escapan a esa validación salen como 400. "
          "La API no expone el factor de distribución, IAP-11, la calificación de carga ni los módulos sísmicos: esos van por Python. Sin autenticación ni estado: pensada para montar detrás de un gateway.")


if __name__ == "__main__":
    main()
