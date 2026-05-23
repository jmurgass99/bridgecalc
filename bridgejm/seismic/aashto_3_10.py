"""
AASHTO LRFD §3.10 — Espectro de respuesta sísmica de diseño para puentes.

Sa(T) = As   para T ≤ T0
Sa(T) = As + (SDS - As)·(T/T0)  para T0 ≤ T ≤ 0.2·Ts (transición)
Sa(T) = SDS   para 0.2 Ts ≤ T ≤ Ts
Sa(T) = SD1/T   para T > Ts

donde:
  As = Fpga · PGA
  SDS = Fa · Ss
  SD1 = Fv · S1
  T0 = 0.2 · Ts,  Ts = SD1/SDS
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AASHTOSeismicInput:
    PGA_g: float
    Ss_g: float          # Sa at 0.2 s, B-class
    S1_g: float          # Sa at 1.0 s, B-class
    Fpga: float = 1.0
    Fa: float = 1.0
    Fv: float = 1.0


@dataclass(frozen=True)
class AASHTOSeismicResult:
    Sa_T_g: list[tuple[float, float]]
    SDS: float
    SD1: float
    Ts: float
    T0: float


def aashto_design_spectrum(inp: AASHTOSeismicInput,
                             periods: list[float] | None = None
                             ) -> AASHTOSeismicResult:
    As = inp.Fpga * inp.PGA_g
    SDS = inp.Fa * inp.Ss_g
    SD1 = inp.Fv * inp.S1_g
    Ts = SD1 / SDS if SDS > 0 else 0.0
    T0 = 0.2 * Ts

    if periods is None:
        import numpy as np
        periods = np.concatenate([
            np.linspace(0, T0, 4),
            np.linspace(T0, Ts, 6)[1:],
            np.linspace(Ts, 4.0, 16)[1:],
        ]).tolist()

    spectrum: list[tuple[float, float]] = []
    for T in periods:
        if T <= T0 and T0 > 0:
            Sa = As + (SDS - As) * (T / T0)
        elif T <= Ts:
            Sa = SDS
        else:
            Sa = SD1 / max(T, 1e-9)
        spectrum.append((float(T), float(Sa)))

    return AASHTOSeismicResult(
        Sa_T_g=spectrum, SDS=SDS, SD1=SD1, Ts=Ts, T0=T0,
    )


__all__ = ["AASHTOSeismicInput", "AASHTOSeismicResult", "aashto_design_spectrum"]
