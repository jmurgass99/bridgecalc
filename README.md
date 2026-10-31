# bridgecalc

Diseño y calificación de puentes: cargas vivas AASHTO LRFD (HL-93, envolventes, factores de distribución, impacto dinámico), modelos de carga EN 1991-2 (LM1, LM2, LM3 especiales), IAP-11, NCh, combinaciones EN 1990 y AASHTO, líneas de influencia en vigas simples y continuas, calificación de carga (rating factor), superestructura y vigas cajón AASHTO, ductilidad EC8, pushover de pilas y curvas de fragilidad.

[![CI](https://github.com/jmurgass99/bridgecalc/actions/workflows/ci.yml/badge.svg)](https://github.com/jmurgass99/bridgecalc/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Paquete independiente. Única dependencia: `numpy`.

## Instalación

```bash
pip install git+https://github.com/jmurgass99/bridgecalc.git
```

Extras: `api` (REST), `dxf` (planos con ezdxf), `memos` (memorias con handcalcs), `test`.

## Inicio rápido

### Envolvente HL-93 y calificación de carga

```python
from bridgecalc.loads.hl93 import hl93_envelope
from bridgecalc.rating.load_rating import RatingInput, rating_both_levels

e = hl93_envelope(30.0)          # viga simple de 30 m, IM = 33 %
print(e["M_max_kNm"], e["V_max_kN"], e["governing_vehicle"])   # 3787 kN·m, 532 kN, truck

inp = RatingInput(Rn=9500.0, DC=2600.0, DW=450.0, LL_IM=0.62 * e["M_max_kNm"], phi=0.90, phi_c=0.95)
for level, r in rating_both_levels(inp).items():
    print(level, round(r.RF, 2), r.ok)   # inventory 1.02 True, operating 1.32 True
```

### Líneas de influencia y posición crítica de un tren de cargas

```python
from bridgecalc.loads.influence_lines import simple_beam_M_influence, critical_position

il = simple_beam_M_influence(L=25.0, x_target_m=12.5)
axles = [(0.0, 35.0), (4.3, 145.0), (8.6, 145.0)]
x_cr, M_max = critical_position(il, axles, udl_kN_per_m=9.3)   # 8.14 m, 2372 kN·m
```

### Modelo de carga LM1 (EN 1991-2)

```python
from bridgecalc.loads.eurocode_lm1 import EurocodeLM1Input, evaluate_eurocode_lm1
```

Los scripts de `examples/` ejecutan estos flujos completos.

## Módulos

| Paquete | Contenido |
|---|---|
| `loads` | `hl93`, `aashto_lrfd`, `distribution_factors`, `dynamic_impact`, `eurocode_lm1`, `lm3_special`, `iap11`, `en1990_combinations`, `load_combinations`, `influence_lines`, `multispan`, `multi_code` |
| `rating` | Factor de calificación a nivel inventario y operación |
| `design` | Superestructura y vigas cajón AASHTO |
| `seismic`, `ec8_ductility`, `analysis` | Pushover de pilas, ductilidad EC8 |
| `fragility` | Curvas de fragilidad |
| `damping`, `datasets`, `optimization`, `memos/`, `api/` | Amortiguamiento, datos de referencia, optimización, memorias, REST |
| `integration/` | Modelo de emparrillado para SAP2000 y exportación a Revit y AutoCAD. Requieren paquetes externos opcionales (`fastsap`, `rebardxf`, pyRevit); sin ellos el resto del paquete funciona y sus tests se omiten |

## Validación

Tests golden con fichas de cargas de puente, envolventes HL-93 contra cálculo manual, tándem y LM1 de EN 1991-2, combinaciones EN 1990 y calificación de carga.

## Licencia

MIT. Consulta [LICENSE](LICENSE).

---

Parte del toolkit estructural de código abierto **Loadpath**, de [Jesús Murgas](https://github.com/jmurgass99).
