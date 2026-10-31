"""
Memoria LRFD HL-93 con handcalcs — render paso-a-paso.

Genera LaTeX legible con factores gamma, camion HL-93, lane load,
impacto dinamico (IM) y combinacion Strength I (AASHTO LRFD 9th ed.).

Usa ``handcalcs`` si esta disponible; caso contrario genera LaTeX
manual con las mismas formulas.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..loads.hl93 import (
    TRUCK_AXLES_kN,
    TRUCK_AXLE_SPACINGS_m,
    TANDEM_AXLES_kN,
    TANDEM_SPACING_m,
    LANE_LOAD_kN_per_m,
)


@dataclass(frozen=True)
class HL93HandcalcsInput:
    L_span_m: float
    n_lanes: int = 2
    DC_kN_m: float = 25.0          # dead load components
    DW_kN_m: float = 5.0           # wearing surface
    gamma_DC: float = 1.25         # LRFD Table 3.4.1-1
    gamma_DW: float = 1.50
    gamma_LL: float = 1.75         # Strength I
    IM_fraction: float = 0.33      # LRFD ss3.6.2 (33%)
    MPF: float = 1.0               # multiple presence factor


@dataclass(frozen=True)
class HL93HandcalcsResult:
    M_DC_kNm: float
    M_DW_kNm: float
    M_truck_kNm: float
    M_tandem_kNm: float
    M_lane_kNm: float
    IM: float
    M_LL_IM_kNm: float
    M_Strength_I_kNm: float
    governing_vehicle: str
    latex: str
    markdown: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "M_DC_kNm": self.M_DC_kNm,
            "M_DW_kNm": self.M_DW_kNm,
            "M_truck_kNm": self.M_truck_kNm,
            "M_tandem_kNm": self.M_tandem_kNm,
            "M_lane_kNm": self.M_lane_kNm,
            "IM": self.IM,
            "M_LL_IM_kNm": self.M_LL_IM_kNm,
            "M_Strength_I_kNm": self.M_Strength_I_kNm,
            "governing_vehicle": self.governing_vehicle,
            "latex": self.latex,
            "markdown": self.markdown,
        }


def _truck_M_simple(L: float) -> float:
    """Momento maximo del camion HL-93 en viga simple de luz L."""
    import numpy as np
    axle_P = TRUCK_AXLES_kN
    spacings = TRUCK_AXLE_SPACINGS_m
    M_best = 0.0
    for a1 in np.linspace(0, max(L - 0.01, 0.01), 80):
        a2 = a1 + spacings[0]
        a3 = a2 + spacings[1]
        loads = [(a, P) for a, P in zip((a1, a2, a3), axle_P) if 0 <= a <= L]
        if not loads:
            continue
        x = np.linspace(0, L, 200)
        M = np.zeros_like(x)
        for a, P in loads:
            R_left = P * (L - a) / L
            M += np.where(x <= a, R_left * x, R_left * x - P * (x - a))
        M_best = max(M_best, float(np.max(M)))
    return M_best


def _tandem_M_simple(L: float) -> float:
    """Momento maximo del tandem en viga simple de luz L."""
    import numpy as np
    M_best = 0.0
    for a1 in np.linspace(0, max(L - 0.01, 0.01), 80):
        a2 = a1 + TANDEM_SPACING_m
        loads = [(a, P) for a, P in zip((a1, a2), TANDEM_AXLES_kN) if 0 <= a <= L]
        if not loads:
            continue
        x = np.linspace(0, L, 200)
        M = np.zeros_like(x)
        for a, P in loads:
            R_left = P * (L - a) / L
            M += np.where(x <= a, R_left * x, R_left * x - P * (x - a))
        M_best = max(M_best, float(np.max(M)))
    return M_best


def _try_handcalcs_render(inp: HL93HandcalcsInput,
                           M_DC: float, M_DW: float,
                           M_truck: float, M_tandem: float,
                           M_lane: float, IM: float,
                           M_vehicle: float, M_LL_IM: float,
                           M_str: float) -> str:
    """Intenta usar handcalcs para el render; fallback a LaTeX manual."""
    try:
        import handcalcs.render  # noqa: F401
        from handcalcs import handcalc

        # Build a handcalcs-rendered string
        L = inp.L_span_m
        w_DC = inp.DC_kN_m
        w_DW = inp.DW_kN_m
        gamma_DC = inp.gamma_DC
        gamma_DW = inp.gamma_DW
        gamma_LL = inp.gamma_LL

        @handcalc()
        def _dc():
            M_DC_calc = w_DC * L ** 2 / 8  # noqa: F841
            return M_DC_calc

        @handcalc()
        def _strength():
            M_Strength_I = gamma_DC * M_DC + gamma_DW * M_DW + gamma_LL * M_LL_IM  # noqa: F841
            return M_Strength_I

        latex_dc = _dc()[0]
        latex_str = _strength()[0]
        return latex_dc + "\n\n" + latex_str

    except Exception:
        pass

    # Fallback: LaTeX manual
    return _fallback_latex(inp, M_DC, M_DW, M_truck, M_tandem,
                            M_lane, IM, M_vehicle, M_LL_IM, M_str)


def _fallback_latex(inp: HL93HandcalcsInput,
                     M_DC: float, M_DW: float,
                     M_truck: float, M_tandem: float,
                     M_lane: float, IM: float,
                     M_vehicle: float, M_LL_IM: float,
                     M_str: float) -> str:
    """Genera LaTeX manual paso a paso."""
    L = inp.L_span_m
    lines = [
        r"\section*{Memoria LRFD HL-93 -- Strength I}",
        "",
        r"\subsection*{1. Datos de entrada}",
        rf"L = {L:.2f} \; \text{{m}}",
        rf"w_{{DC}} = {inp.DC_kN_m:.2f} \; \text{{kN/m}}",
        rf"w_{{DW}} = {inp.DW_kN_m:.2f} \; \text{{kN/m}}",
        rf"\gamma_{{DC}} = {inp.gamma_DC:.2f}, \;"
        rf"\gamma_{{DW}} = {inp.gamma_DW:.2f}, \;"
        rf"\gamma_{{LL}} = {inp.gamma_LL:.2f}",
        rf"IM = {inp.IM_fraction:.2f}",
        "",
        r"\subsection*{2. Momentos de carga muerta}",
        rf"M_{{DC}} = \frac{{w_{{DC}} \cdot L^2}}{{8}} = "
        rf"\frac{{{inp.DC_kN_m:.2f} \cdot {L:.2f}^2}}{{8}} = {M_DC:.2f} \; \text{{kN·m}}",
        rf"M_{{DW}} = \frac{{w_{{DW}} \cdot L^2}}{{8}} = {M_DW:.2f} \; \text{{kN·m}}",
        "",
        r"\subsection*{3. Carga viva HL-93}",
        rf"M_{{truck}} = {M_truck:.2f} \; \text{{kN·m}} \quad "
        rf"\text{{(ejes {TRUCK_AXLES_kN[0]}-{TRUCK_AXLES_kN[1]}-{TRUCK_AXLES_kN[2]} kN)}}",
        rf"M_{{tandem}} = {M_tandem:.2f} \; \text{{kN·m}} \quad "
        rf"\text{{(2 x {TANDEM_AXLES_kN[0]} kN @ {TANDEM_SPACING_m} m)}}",
        rf"M_{{lane}} = \frac{{w_{{lane}} \cdot L^2}}{{8}} = "
        rf"\frac{{{LANE_LOAD_kN_per_m:.2f} \cdot {L:.2f}^2}}{{8}} = {M_lane:.2f} \; \text{{kN·m}}",
        "",
        r"\subsection*{4. Impacto dinamico}",
        rf"IM = 1 + {inp.IM_fraction:.2f} = {1 + inp.IM_fraction:.2f}",
        rf"M_{{vehicle}} = \max(M_{{truck}}, M_{{tandem}}) \cdot IM = {M_vehicle:.2f} \; \text{{kN·m}}",
        rf"M_{{LL+IM}} = (M_{{vehicle}} + M_{{lane}}) \cdot MPF = {M_LL_IM:.2f} \; \text{{kN·m}}",
        "",
        r"\subsection*{5. Combinacion Strength I}",
        rf"M_u = \gamma_{{DC}} \cdot M_{{DC}} + \gamma_{{DW}} \cdot M_{{DW}} "
        rf"+ \gamma_{{LL}} \cdot M_{{LL+IM}}",
        rf"M_u = {inp.gamma_DC:.2f} \cdot {M_DC:.2f} + "
        rf"{inp.gamma_DW:.2f} \cdot {M_DW:.2f} + "
        rf"{inp.gamma_LL:.2f} \cdot {M_LL_IM:.2f}",
        rf"M_u = {M_str:.2f} \; \text{{kN·m}}",
    ]
    return "\n".join(lines)


def generar_memoria_handcalcs(inp: HL93HandcalcsInput) -> HL93HandcalcsResult:
    """Genera memoria paso-a-paso LRFD HL-93 Strength I.

    Calcula momentos de carga muerta, carga viva (camion vs tandem),
    impacto dinamico y la combinacion Strength I con factores gamma.
    """
    L = inp.L_span_m
    if L <= 0:
        raise ValueError("L_span_m debe ser > 0")

    # 1. Cargas muertas
    M_DC = inp.DC_kN_m * L ** 2 / 8.0
    M_DW = inp.DW_kN_m * L ** 2 / 8.0

    # 2. Carga viva HL-93
    M_truck = _truck_M_simple(L)
    M_tandem = _tandem_M_simple(L)
    M_lane = LANE_LOAD_kN_per_m * L ** 2 / 8.0

    # 3. Impacto dinamico
    IM = 1.0 + inp.IM_fraction
    governing = "truck" if M_truck >= M_tandem else "tandem"
    M_vehicle = max(M_truck, M_tandem) * IM

    # 4. M_LL+IM
    M_LL_IM = (M_vehicle + M_lane) * inp.MPF

    # 5. Strength I
    M_str = inp.gamma_DC * M_DC + inp.gamma_DW * M_DW + inp.gamma_LL * M_LL_IM

    # Render
    latex = _try_handcalcs_render(
        inp, M_DC, M_DW, M_truck, M_tandem, M_lane, IM,
        M_vehicle, M_LL_IM, M_str,
    )

    # Markdown resumen
    md = (
        f"# Memoria LRFD HL-93 -- Strength I\n\n"
        f"## Datos\n"
        f"- L = {L} m, lanes = {inp.n_lanes}\n"
        f"- DC = {inp.DC_kN_m} kN/m, DW = {inp.DW_kN_m} kN/m\n\n"
        f"## Cargas muertas\n"
        f"- M_DC = {M_DC:.2f} kN-m\n"
        f"- M_DW = {M_DW:.2f} kN-m\n\n"
        f"## Carga viva HL-93\n"
        f"- M_truck = {M_truck:.2f} kN-m\n"
        f"- M_tandem = {M_tandem:.2f} kN-m\n"
        f"- Gobierna: {governing}\n"
        f"- M_lane = {M_lane:.2f} kN-m\n"
        f"- IM = {IM:.2f}\n"
        f"- M_LL+IM = {M_LL_IM:.2f} kN-m\n\n"
        f"## Strength I\n"
        f"- gamma_DC={inp.gamma_DC}, gamma_DW={inp.gamma_DW}, "
        f"gamma_LL={inp.gamma_LL}\n"
        f"- M_u = {M_str:.2f} kN-m\n"
    )

    return HL93HandcalcsResult(
        M_DC_kNm=M_DC,
        M_DW_kNm=M_DW,
        M_truck_kNm=M_truck,
        M_tandem_kNm=M_tandem,
        M_lane_kNm=M_lane,
        IM=IM,
        M_LL_IM_kNm=M_LL_IM,
        M_Strength_I_kNm=M_str,
        governing_vehicle=governing,
        latex=latex,
        markdown=md,
    )


__all__ = ["HL93HandcalcsInput", "HL93HandcalcsResult", "generar_memoria_handcalcs"]
