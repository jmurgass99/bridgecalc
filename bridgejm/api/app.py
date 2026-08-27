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

    return router


def create_app() -> Any:
    """App FastAPI standalone."""
    from fastapi import FastAPI

    app = FastAPI(title="BridgeJm API", version="0.1.0")
    app.include_router(create_router())
    return app
