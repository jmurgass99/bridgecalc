"""
Generador de combinaciones de acciones — EN 1990 (Eurocódigo 0).

Estados límite últimos (STR/GEO) y de servicio, con la elección automática de la
acción variable dominante (la que maximiza el efecto):

  ULS 6.10   : Σ γG·Gk + γQ1·Qk1 + Σ γQi·ψ0i·Qki
  ULS 6.10a  : Σ γG·Gk + γQ1·ψ0,1·Qk1 + Σ γQi·ψ0i·Qki
  ULS 6.10b  : Σ ξ·γG·Gk + γQ1·Qk1 + Σ γQi·ψ0i·Qki   (ξ=0.85)
  SLS caract.: Σ Gk + Qk1 + Σ ψ0i·Qki
  SLS frec.  : Σ Gk + ψ1,1·Qk1 + Σ ψ2i·Qki
  SLS c.perm.: Σ Gk + Σ ψ2i·Qki
  Sísmica    : Σ Gk + A_Ed + Σ ψ2i·Qki
  Accidental : Σ Gk + A_d + ψ1,1·Qk1 + Σ ψ2i·Qki

Factores parciales: EN 1990 Tabla A1.2(B) y Anexo A2 Tabla A2.4(B); ψ por categoría: Tabla A1.1 y Tabla A2.1.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

# ψ0, ψ1, ψ2 por categoría de acción variable (EN 1990 Tabla A1.1 y Anexo A2 Tabla A2.1 para puentes).
PSI_CATALOG: Dict[str, Tuple[float, float, float]] = {
    "A": (0.7, 0.5, 0.3),   # vivienda
    "B": (0.7, 0.5, 0.3),   # oficinas
    "C": (0.7, 0.7, 0.6),   # zonas de reunión
    "D": (0.7, 0.7, 0.6),   # comercio
    "E": (1.0, 0.9, 0.8),   # almacenes
    "F": (0.7, 0.7, 0.6),   # tráfico <= 30 kN
    "G": (0.7, 0.5, 0.3),   # tráfico 30-160 kN
    "H": (0.0, 0.0, 0.0),   # cubiertas
    "wind": (0.6, 0.2, 0.0),
    "snow": (0.5, 0.2, 0.0),       # <= 1000 m
    "temperature": (0.6, 0.5, 0.0),
    # EN 1990 Anexo A2 Tabla A2.1 (puentes de carretera)
    "traffic_gr1a_ts": (0.75, 0.75, 0.0),
    "traffic_gr1a_udl": (0.40, 0.40, 0.0),
    "traffic_gr1b": (0.0, 0.75, 0.0),
    "traffic_gr2": (0.0, 0.0, 0.0),
    "traffic_gr3": (0.0, 0.0, 0.0),
    "wind_bridge": (0.6, 0.2, 0.0),
    "thermal_bridge": (0.6, 0.6, 0.5),
}

GAMMA_G_SUP = 1.35   # permanente desfavorable
GAMMA_G_INF = 1.00   # permanente favorable
GAMMA_Q = 1.50       # variable desfavorable general (edificación / viento / térmica en puentes)
GAMMA_Q_BRIDGE_TRAFFIC = 1.35  # tráfico de carretera gr1a/gr1b/gr2/gr3 en puentes (EN 1990 Tabla A2.4(B))
XI = 0.85            # factor de reducción 6.10b


@dataclass(frozen=True)
class VariableAction:
    name: str
    Qk: float
    category: str = "A"
    gamma_Q: float | None = None

    def psi(self) -> Tuple[float, float, float]:
        return PSI_CATALOG.get(self.category, (0.7, 0.5, 0.3))

    def effective_gamma_Q(self, default_gamma_Q: float = GAMMA_Q) -> float:
        if self.gamma_Q is not None:
            return self.gamma_Q
        if self.category.startswith("traffic_"):
            return GAMMA_Q_BRIDGE_TRAFFIC
        return default_gamma_Q


def _Gk_sum(permanent: Dict[str, float], gamma_G: float) -> float:
    return gamma_G * sum(permanent.values())


def uls_strength(permanent: Dict[str, float], variables: List[VariableAction],
                 expression: str = "6.10") -> float:
    """ULS STR/GEO. Devuelve el efecto gobernante (acción dominante que maximiza)."""
    if expression not in ("6.10", "6.10a", "6.10b"):
        raise ValueError("expression debe ser 6.10, 6.10a o 6.10b")
    if not variables:
        return _Gk_sum(permanent, GAMMA_G_SUP)
    best = float("-inf")
    for lead in variables:
        gG = XI * GAMMA_G_SUP if expression == "6.10b" else GAMMA_G_SUP
        total = gG * sum(permanent.values())
        for v in variables:
            psi0 = v.psi()[0]
            gQ = v.effective_gamma_Q(GAMMA_Q)
            if v is lead:
                factor = gQ * (psi0 if expression == "6.10a" else 1.0)
            else:
                factor = gQ * psi0
            total += factor * v.Qk
        best = max(best, total)
    return best


def uls_bridge_strength(
    permanent: Dict[str, float],
    variables: List[VariableAction],
    expression: str = "6.10",
) -> float:
    """ULS STR/GEO para puentes según EN 1990 Anexo A2 Tabla A2.4(B).

    Aplica automáticamente ``γ_Q = 1.35`` a las acciones de tráfico (categorías
    ``traffic_gr1a_ts``, ``traffic_gr1a_udl``, ``traffic_gr1b``, ``traffic_gr2``,
    ``traffic_gr3``) y ``γ_Q = 1.50`` al resto de acciones variables salvo que
    ``VariableAction.gamma_Q`` esté fijado explícitamente.
    """
    return uls_strength(permanent, variables, expression=expression)


def uls_governing(permanent: Dict[str, float], variables: List[VariableAction]) -> float:
    """Gobernante del set 6.10 (o el mayor de 6.10a/6.10b si se usa el set alternativo)."""
    a = uls_strength(permanent, variables, "6.10a")
    b = uls_strength(permanent, variables, "6.10b")
    return max(a, b)


def sls_combination(permanent: Dict[str, float], variables: List[VariableAction],
                    kind: str = "characteristic") -> float:
    """SLS: 'characteristic' | 'frequent' | 'quasi_permanent'."""
    G = sum(permanent.values())
    if not variables:
        return G
    if kind == "quasi_permanent":
        return G + sum(v.psi()[2] * v.Qk for v in variables)
    best = float("-inf")
    for lead in variables:
        total = G
        for v in variables:
            psi0, psi1, psi2 = v.psi()
            if kind == "characteristic":
                total += (1.0 if v is lead else psi0) * v.Qk
            elif kind == "frequent":
                total += (psi1 if v is lead else psi2) * v.Qk
            else:
                raise ValueError("kind desconocido: %s" % kind)
        best = max(best, total)
    return best


def seismic_combination(permanent: Dict[str, float], variables: List[VariableAction],
                        AEd: float) -> float:
    """Sísmica (EN 1990 6.12): Σ Gk + A_Ed + Σ ψ2i·Qki."""
    return sum(permanent.values()) + AEd + sum(v.psi()[2] * v.Qk for v in variables)


__all__ = [
    "VariableAction", "PSI_CATALOG", "uls_strength", "uls_bridge_strength", "uls_governing",
    "sls_combination", "seismic_combination",
    "GAMMA_G_SUP", "GAMMA_G_INF", "GAMMA_Q", "GAMMA_Q_BRIDGE_TRAFFIC", "XI",
]
