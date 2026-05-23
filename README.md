# BridgeJm

Diseño de puentes — AASHTO LRFD + análisis sísmico (IEG 3260).

## Scope

- `bridgejm.loads.hl93` — envolvente HL-93 (camión + tandem + carril) con IM
- `bridgejm.fragility.park_ang` — índice de daño + curvas de fragilidad lognormales

## Roadmap

- [ ] Bridge a `fastcsib` (CSi Bridge) — actualmente stub
- [ ] Multi-tramo + influencias por integración numérica de superposición
- [ ] PGA → curvas fragilidad de cepas chilenas (Concepción 2010 dataset)

## Integración con Revit y AutoCAD (Grupo G — IDEAS_20)

### Revit (pyRevit script)

`revit_export.to_revit_script(bridge)` genera el código pyRevit que crea las
cepas (Adaptive Component `BridgeJm_AdaptivePier`) y el tablero
(`BridgeJm_Deck`) por cada luz.

```python
from bridgejm.integration.revit_export import (
    BridgeGeometry, PierGeometry, DeckGeometry, save_script
)
bridge = BridgeGeometry(
    spans_m=[30, 40, 30],
    piers=[PierGeometry(30, 10), PierGeometry(70, 10)],
    deck=DeckGeometry(10, 1.2),
    project_name="PuenteJM",
)
save_script(bridge, "bridgejm_revit.py")
```

Instalación de pyRevit: https://www.pyrevitlabs.io/. Copia el `.py` generado
a tu extensión pyRevit y ejecútalo con el proyecto Revit abierto.

Un script genérico de plantilla está en
`bridgejm/integration/pyrevit_scripts/bridgejm_import.py`.

### AutoCAD (layout 2D)

`autocad_layout.draw_bridge_layout` dibuja el alzado del puente (eje, cepas,
cotas) en una sesión AutoCAD viva (vía `dxfstructuraljm.integration.autocad_live`).

```python
from dxfstructuraljm.integration.autocad_live import AutoCADClient
from bridgejm.integration.autocad_layout import draw_bridge_layout

with AutoCADClient() as cad:
    draw_bridge_layout(cad, bridge)
```
