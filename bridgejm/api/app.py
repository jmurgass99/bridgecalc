"""FastAPI app para BridgeJm — HL-93 envelope + fragilidad."""
from typing import Any


def create_router() -> Any:
    """Devuelve el APIRouter con los endpoints. Mountable en gateway."""
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field

    from ..loads import (
        HL93Configuration, MultiSpanInput,
        envelope_multispan, hl93_influence_envelope,
    )
    from ..fragility import park_ang_damage_index, lognormal_fragility

    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    class HL93Payload(BaseModel):
        span_m: float = Field(..., gt=0)
        impact_factor: float = Field(1.33, gt=0)

    @router.post("/api/bridge/hl93/single", summary="Tren de cargas HL-93 en vano simple según AASHTO LRFD §3.6.1")
    def hl93_single(payload: HL93Payload) -> dict[str, Any]:
        try:
            r = hl93_influence_envelope(HL93Configuration(
                span_m=payload.span_m, impact_factor=payload.impact_factor,
            ))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return r.to_dict()

    class MultiSpanPayload(BaseModel):
        span_m: float = Field(..., gt=0)
        n_spans: int = Field(..., ge=2, le=3)
        impact_factor: float = Field(1.33, gt=0)

    @router.post("/api/bridge/hl93/multispan", summary="Tren de cargas HL-93 en puente continuo multivano según AASHTO LRFD §3.6.1")
    def hl93_multispan(payload: MultiSpanPayload) -> dict[str, Any]:
        try:
            r = envelope_multispan(MultiSpanInput(**payload.model_dump()))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return r.to_dict()

    class ParkAngPayload(BaseModel):
        delta_max: float
        delta_u: float = Field(..., gt=0)
        E_h: float
        F_y: float = Field(..., gt=0)
        beta: float = 0.10

    @router.post("/api/bridge/fragility/park-ang", summary="Índice de daño sísmico de pilas según modelo de Park & Ang (1985)")
    def fragility_park_ang(payload: ParkAngPayload) -> dict[str, Any]:
        try:
            DI = park_ang_damage_index(**payload.model_dump())
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"damage_index": DI,
                "status": "operational" if DI < 0.4 else
                          "repairable" if DI < 0.7 else
                          "collapse_risk"}

    class LM1Payload(BaseModel):
        span_m: float = Field(..., gt=0)
        n_lanes: int = Field(2, ge=1, le=5)
        alpha_Q: float = Field(1.0, gt=0)
        alpha_q: float = Field(1.0, gt=0)
        lane_width: float = Field(3.0, gt=0)

    @router.post("/api/bridge/traffic/lm1", summary="Tren de cargas Load Model 1 (LM1) y envolvente según EN 1991-2 §4.3.2")
    def traffic_lm1(payload: LM1Payload) -> dict[str, Any]:
        from ..ec1_traffic import LM1, traffic_envelope_lm1
        try:
            lm1 = LM1(
                n_lanes=payload.n_lanes,
                alpha_Q=payload.alpha_Q,
                alpha_q=payload.alpha_q,
                lane_width=payload.lane_width,
            )
            lanes = lm1.lane_loads()
            M_max_kNm, V_max_kN = traffic_envelope_lm1(
                L_span=payload.span_m,
                n_lanes=payload.n_lanes,
                alpha_Q=payload.alpha_Q,
                alpha_q=payload.alpha_q,
                lane_width=payload.lane_width,
            )
            return {
                "span_m": payload.span_m,
                "n_lanes": payload.n_lanes,
                "lanes": lanes,
                "M_max_kNm": M_max_kNm,
                "V_max_kN": V_max_kN,
                "code": "EN 1991-2 §4.3.2 (LM1)",
            }
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    class LM2Payload(BaseModel):
        beta_Q: float = Field(1.0, gt=0)

    @router.post("/api/bridge/traffic/lm2", summary="Tren de cargas Load Model 2 (LM2: eje 400 kN) según EN 1991-2 §4.3.3")
    def traffic_lm2(payload: LM2Payload) -> dict[str, Any]:
        from ..ec1_traffic import LM2
        try:
            lm2 = LM2(beta_Q=payload.beta_Q)
            return {
                "Qak_kN": lm2.Qak_kN,
                "beta_Q": payload.beta_Q,
                "contact_surfaces_m": "2 x (0.35 x 0.60)",
                "transverse_spacing_m": 2.0,
                "code": "EN 1991-2 §4.3.3 (LM2)",
            }
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    return router


def create_app() -> Any:
    """App FastAPI standalone."""
    from fastapi import FastAPI

    app = FastAPI(title="BridgeJm API", version="0.1.0")
    app.include_router(create_router())
    return app
