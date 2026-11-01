# Changelog

## 1.1.0 — 2026-11-01

### Corregido
- `loads.influence_lines.influence_line_continuous`: la ecuación de los tres momentos tomaba la distancia de la carga al apoyo **cercano** del tramo en vez de al **lejano**. La línea de influencia salía reflejada dentro de cada vano (pico en 0,423 L en lugar de 0,577 L) y con luces desiguales daba valores erróneos (en 20/30/25 m, hasta ±90 % en el apoyo). Anclado a la forma cerrada de dos vanos y a un solver de rigidez directa (`tests/test_influence_continuous_three_moment_orientation.py`).
- `loads.influence_lines.two_span_continuous_M_at_support` (forma cerrada): el segundo vano usaba la distancia al apoyo central en el factor `(L2 + a)`; la línea de influencia quedaba reflejada en ese vano (pico en L1 + 0,577·L2 en lugar de L1 + 0,423·L2). Los tests dorados no lo veían porque solo miraban el mínimo global, que cae en el primer vano.
- `loads.multispan.envelope_multispan`: devolvía coeficientes 0,080/0,100·w·L² y 0,40·w·L con una «carga uniforme equivalente» del camión (IM·325 kN/L), que no es un procedimiento normativo. Ahora construye líneas de influencia reales, barre el camión en los dos sentidos y el tándem, aplica el carril solo en las zonas del mismo signo y la regla del 90 % de dos camiones a ≥ 15 m para el momento negativo (AASHTO LRFD §3.6.1.3.1); admite de 2 a 6 vanos y luces desiguales (`spans_m`). El resultado publica la sección crítica y el desglose por componente. Para 2 × 30 m (un carril, IM 1,33): M⁺ 1710 → 3013 kN·m, M⁻ 2137 → 3101 kN·m (0,9 × dos camiones), V 285 → 579 kN. La API acepta de 2 a 6 vanos.
- `loads.eurocode.evaluate_lm1` (módulo legado): el momento del tándem se calculaba con la fórmula de una carga repartida (`2·Q·L/8`), la mitad del valor real: L = 30 m, 2 carriles, 3748 → 7203 kN·m. Delega en `eurocode_lm1.evaluate_eurocode_lm1` (Barré) y emite `DeprecationWarning`.
- `memos.lrfd_hl93.generar_memoria_hl93`: el camión se estimaba con `145·L/4 − 145·4,3/2` (776 kN·m en 30 m frente a 2058 del barrido exacto) y se ignoraba el tándem; ahora usa `hl93_envelope` y declara el vehículo que gobierna.
- `loads.dynamic_impact.dynamic_load_allowance("EU")`: devolvía el factor dinámico ferroviario φ2 − 1 (EN 1991-2 §6.4.5.2); LM1/LM2 ya incluyen la amplificación dinámica, así que para carretera IM = 0. El factor φ2 queda en `code="EU_RAIL"`.
- `loads.eurocode_lm1.evaluate_eurocode_lm1`: el cortante del tándem ponía los dos ejes sobre el apoyo (2Q); ahora uno sobre el apoyo y el otro a 1,2 m, Q·(2 − d/L) (L = 20 m, dos carriles: 1345 → 1315 kN). En luces menores de 2,05 m manda un solo eje centrado, Q·L/4 (antes Q·L/2 hasta 1,2 m y la fórmula de dos ejes entre 1,2 y 2,05 m). Las tres rutas de LM1 (`eurocode_lm1`, `ec1_traffic`, `iap11`) comparten ahora las mismas funciones del tándem.
- `damping.bwbn`: el término de β usaba sgn(du·z)·|du| (= sgn(z)·du), con lo que la descarga seguía la ley de carga y no había lazo (energía disipada nula), y z no se normalizaba por u_y = F_y/K₀ (la fuerza no pasaba de ≈ 0,37·F_y con ductilidad 6). Ahora es el Bouc-Wen-Baber-Noori estándar con z adimensional y subpasos de integración.
- `fragility.lognormal_fragility`: decía «MLE» pero devolvía la media y desviación de ln(IM) de las muestras con daño, que no es la fragilidad (mediana real 0,45 g → ajustada 0,88 g). Ahora es máxima verosimilitud binomial por rejilla, sin SciPy; lanza `ValueError` si no hay observaciones con y sin daño.
- `design.aashto_box_girder.shear_strength` y `design.aashto_superstructure.concrete_box_girder_shear`: V_c usaba el coeficiente 0,0316 de la ecuación en ksi con f'c en MPa y medidas en mm; el coeficiente SI es 0,083 (V_c era 2,63 veces menor). `principal_stress_web`: el límite 0,110·√f'c (ksi) se aplicaba en MPa; ahora 0,29·√f'c MPa (antes 2,63 veces más estricto).
- `memos.hl93_handcalcs`: importaba `handcalcs.render`, que llama a `get_ipython()` y solo funciona en Jupyter; la excepción se tragaba y la memoria salía siempre con el LaTeX manual. Ahora usa `handcalcs.decorator` y el resultado declara `latex_engine`.
- `tests/test_examples.py`: la salida de los ejemplos se decodifica como UTF-8 (en Windows se decodificaba con cp1252 y un byte no definido hacía fallar el test).
- `loads.aashto_lrfd.LRFDLoadCombination`: doble decorador `@dataclass(frozen=True) @dataclass`.
- Versión única 1.1.0 en `pyproject.toml`, `bridgecalc.__version__` y la API (antes 1.0.0 / 0.1.0 / 0.1.0).

### Añadido
- 32 casos de uso ejecutables en `examples/` con salida guardada en `examples/output/`, y `tests/test_examples.py` que los ejecuta en CI.
- README reescrito con las salidas reales, límites declarados y referencias.

### Límites documentados (sin cambio de código)
- `loads.multi_code` (AS 5100.2 «SM1600» y CC-40) y `lm3_special.AS_SM1600`: trenes de carga y coeficientes no contrastados con las normas; no usar para diseño.
- `fragility.HAZUS_RC_PIER_PARAMS` y `datasets.concepcion_2010`: parámetros representativos e ilustrativos, no tablas publicadas.
- `analysis.pier_pushover`: M–φ simplificado (M_y = 0,9·A_s·f_y·d + 0,1·N·D, M_u = 1,1·M_y, φ_u = 10·φ_y); predimensionamiento, no análisis seccional.
- `loads.load_combinations`: los γ_WS (1,40 Strength III, 0,40 Strength V, 0,30 Service I, 0,70 Service IV) son los del esquema anterior a la 8ª edición del LRFD (2017).
- `loads.lm3_special`: «SV120», «SV196» y «AS 5100.2 SM1600 T44» son convoyes de ejemplo; no reproducen el Anexo A de EN 1991-2, el anejo nacional británico ni AS 5100.2. El momento se evalúa en el centro de la luz, no en el máximo absoluto.
- `loads.eurocode_lm1`: número de carriles = ⌊w/3⌋ con tope de 3 y sin área remanente (para 5,4 ≤ w < 6 m EN 1991-2 da 2 carriles; usa `iap11_lane_layout`).
- `loads.dynamic_impact.wind_pressure_bridge`: presión dinámica ½·ρ·V²·C_d sin factores de ráfaga, altura ni exposición.
- `api`: el endpoint de Park-Ang clasifica DI ≥ 0,7 como `collapse_risk`; la escala de Park-Ang reserva el colapso para DI > 1,0.
- `design`: secciones rectangulares equivalentes, β y θ fijos del método simplificado, sin pérdidas de pretensado; los DCR devuelven `inf` en vez de lanzar con capacidad nula.
