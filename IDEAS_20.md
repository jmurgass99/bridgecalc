# BridgeJm — 20 mejoras propuestas

| # | Idea | Prio | Esfuerzo | Estado |
|---|---|---|---|---|
| 1 | REST API (FastAPI) con `/api/bridge/hl93/single` y `/multispan` | P0 | 1d | ✅ Hecho |
| 2 | Multi-tramo continuo 2-3 tramos con coeficientes simplificados | P0 | 1d | ✅ Hecho |
| 3 | Park-Ang damage index endpoint | P0 | 0.5d | ✅ Hecho |
| 4 | Trenes adicionales: HL-93K (NCh), Eurocode LM1, COBRA | P1 | 3d | 🔄 |
| 5 | Influencias por integración numérica (Müller-Breslau) para luces desiguales | P1 | 4d | 🔄 |
| 6 | Pushover de cepa simple (reusar `DynamicsJm.analysis.pushover`) | P1 | 4d | 🔄 |
| 7 | Curvas de fragilidad cepas chilenas (dataset Concepción 2010) | P1 | 6d | 🔄 |
| 8 | Memoria handcalcs LRFD HL-93 paso a paso | P1 | 3d | 🔄 |
| 9 | Bridge a `fastcsib` para automatizar generación en CSi Bridge | P0 | 5d | 🔄 |
| 10 | Análisis sísmico AASHTO §3.10 (espectro de diseño) | P1 | 3d | 🔄 |
| 11 | Empujes activos/pasivos sobre estribos (Coulomb) | P1 | 2d | 🔄 |
| 12 | Verificación cepa-fundación (pile cap bridge a `FoundationDesignJm`) | P1 | 2d | 🔄 |
| 13 | Cargas dinámicas (impacto camión + viento ASCE 7) | P1 | 3d | 🔄 |
| 14 | Memoria de revisión post-sismo (índices de daño globales) | P2 | 4d | 🔄 |
| 15 | Visualizador 3D del puente con React Three Fiber | P2 | 8d | 🔄 |
| 16 | Línea de influencia interactiva para vigas continuas | P2 | 5d | 🔄 |
| 17 | Curvas Sa-D para análisis pushover de cepas | P2 | 3d | 🔄 |
| 18 | Modelo BWBN para amortiguadores viscosos en aislamiento | P2 | 5d | 🔄 |
| 19 | Optimización paramétrica del número de tramos para minimizar costo | P3 | 6d | 🔄 |
| 20 | Plugin Revit/Tekla para exportar geometría a BridgeJm | P3 | 10d | 🔄 |

## Próximas 3 a implementar (top según ROI)

- **#4 Trenes adicionales** — abre mercado europeo + chileno (Eurocode LM1 + HL-93K)
- **#8 Memoria handcalcs LRFD** — entregable directo al cliente
- **#11 Empujes activos/pasivos** — completa el diseño de estribos
