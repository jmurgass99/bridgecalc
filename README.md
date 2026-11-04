# bridgecalc

**Español** · [English](README.en.md)

Cargas de tráfico, envolventes y comprobaciones de puentes en Python.

[![CI](https://github.com/jmurgass99/bridgecalc/actions/workflows/ci.yml/badge.svg)](https://github.com/jmurgass99/bridgecalc/actions/workflows/ci.yml)
[![Licencia: MIT](https://img.shields.io/badge/licencia-MIT-green)](LICENSE)

## Qué hace

- Envolventes HL-93 de AASHTO LRFD en vano simple y en vigas continuas por líneas de influencia.
- Modelos de carga LM1, LM2 y LM3 de EN 1991-2, IAP-11 española y camión chileno de 44 t.
- Factores de distribución, combinaciones de AASHTO y EN 1990, y calificación de carga LRFR.
- Sísmica: espectro AASHTO, empujes de Mononobe-Okabe, ductilidad EN 1998-2, pushover de pilas y fragilidad.
- Emparrillado para SAP2000 y exportación a Revit y AutoCAD.

## Instalación

```bash
pip install git+https://github.com/jmurgass99/bridgecalc.git
```

Extras opcionales: `api`, `dxf`, `memos`. Única dependencia base: `numpy`.

## Ejemplo

Envolvente HL-93 para un vano simple de 30 m:

```python
from bridgecalc.loads.hl93 import hl93_envelope

r = hl93_envelope(30.0)
print(round(r["M_max_kNm"]), round(r["V_max_kN"], 1))   # 3787 531.6
```

Más casos en [`examples/`](examples).

## Qué no hace

- El cálculo de proyecto de un puente: no hay modelo de elementos finitos propio, fases constructivas, fluencia, retracción, pérdidas de pretensado ni fatiga.
- Normas que solo aproxima: los módulos `multi_code` (AS 5100.2 y Colombia) y los convoyes de `lm3_special` están marcados como no contrastados.
- Capacidad sísmica de una pila existente: el pushover usa un momento-curvatura simplificado, válido para comparar alternativas, no para evaluar.
- Secciones de hormigón complejas: `design` usa sección rectangular equivalente con β y θ fijos.

El detalle está en [docs/LIMITACIONES.md](docs/LIMITACIONES.md).

## Pruebas

```bash
pip install -e ".[test]"
pytest -q
```

## Licencia

MIT. Ver [LICENSE](LICENSE). Autor: [Jesús Murgas](https://github.com/jmurgass99).
