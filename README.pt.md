# bridgecalc — cargas de tráfego, envolventes e verificações de pontes em Python

[Español](README.md) · [English](README.en.md) · **Português** · [Italiano](README.it.md)

Envolventes HL-93 da AASHTO LRFD em vão simples e em vigas contínuas por linhas de influência, modelos de carga LM1, LM2 e LM3 da EN 1991-2, IAP-11 espanhola, camião chileno de 44 t, fatores de distribuição, combinações AASHTO e EN 1990, avaliação da capacidade de carga LRFR, vigas-caixão e chaves de corte, espectro AASHTO, impulsos de Mononobe-Okabe, ductilidade EN 1998-2, pushover de pilares, fragilidade sísmica, amortecedor de Bouc-Wen, grelha para o SAP2000 e exportação para o Revit e o AutoCAD. Dependência única: `numpy`.

[![CI](https://github.com/jmurgass99/bridgecalc/actions/workflows/ci.yml/badge.svg)](https://github.com/jmurgass99/bridgecalc/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## Que problema resolve

No estudo prévio de uma ponte as primeiras perguntas são de ordens de grandeza: que momento o tráfego deixa numa viga de 30 m, quanto muda com a continuidade, que norma condiciona num país, se uma viga existente admite a carga de cálculo ou se um pilar tem ductilidade suficiente. As folhas de cálculo que respondem a essas perguntas costumam esconder fórmulas aproximadas que ninguém revê: o tandem do LM1 calculado como carga distribuída, o camião HL-93 resolvido com um coeficiente, o coeficiente em ksi da AASHTO aplicado a MPa. O `bridgecalc` dá essas respostas com o método à vista: varrimento do comboio de cargas ou teorema de Barré, linhas de influência exatas pela equação dos três momentos, combinações com a ação de base escolhida por cálculo, e cada simplificação declarada no código, no exemplo e neste README.

**Use quando**

- precisar da envolvente de momento e esforço transverso por via do HL-93, LM1, IAP-11 ou do camião chileno numa viga simples, ou da do HL-93 numa viga contínua de 2 a 6 vãos com a regra dos dois camiões;
- quiser linhas de influência de vigas contínuas com vãos desiguais, a posição crítica de um comboio de eixos ou comparar veículos especiais;
- tiver de repartir a carga entre vigas (AASHTO §4.6.2.2 ou Courbon), combiná-la nos treze estados limite AASHTO ou com a EN 1990, ou calcular o fator de avaliação LRFR de uma viga existente;
- estiver a pré-dimensionar um pilar ou um encontro para sismo: espectro AASHTO, impulso de Mononobe-Okabe, coeficiente q, confinamento, rótula plástica, pushover simplificado e probabilidades de dano;
- quiser gerar a geometria e as cargas de uma grelha de tabuleiro, um script do Revit ou um desenho esquemático de disposição geral a partir de Python.

**Não use para**

- o cálculo de projeto de uma ponte: não há modelo de elementos finitos próprio, nem fases construtivas, fluência, retração, perdas de pré-esforço, fadiga ou deformações;
- normas que o pacote só aproxima: os módulos `multi_code` (AS 5100.2 e Colômbia) e os veículos especiais de `lm3_special` não reproduzem essas normas e estão marcados como não normativos;
- capacidades sísmicas de um pilar existente: o pushover usa um momento-curvatura simplificado com φ_u = 10·φ_y, válido para comparar alternativas, não para avaliar;
- secções de betão complexas: as verificações de `design` são de secção retangular equivalente com β e θ fixos.

## Instalação

```bash
pip install git+https://github.com/jmurgass99/bridgecalc.git
```

Extras: `api` (FastAPI, pydantic, httpx), `dxf` (ezdxf para o desenho de disposição geral), `memos` (handcalcs; sem ele a memória sai com um LaTeX manual equivalente e declara-o em `latex_engine`), `test`. Para desenvolvimento: `git clone`, `pip install -e ".[test,api]"`, `pytest -q` (45 ficheiros de testes; `tests/test_examples.py` executa os 32 exemplos como subprocessos). No Windows, se a consola não for UTF-8, execute os exemplos com `python -X utf8 examples/<nome>.py`. Os exemplos escrevem os seus ficheiros (JSON, DXF, script pyRevit, memórias) em `examples/out/`, que não se versiona, e a saída de consola em `examples/output/`.

## Capacidades

| Capacidade | Módulos | Norma ou referência | Casos de uso |
|---|---|---|---|
| Sobrecargas AASHTO: envolvente HL-93 por varrimento (camião, tandem, via, IM só no veículo), camião chileno de 44 t, fatores de distribuição interior e exterior com a regra da alavanca, treze estados limite com γ_p máximo e mínimo, avaliação LRFR ao nível de inventário e de operação, vento sobre o tabuleiro | `loads.hl93`, `loads.distribution_factors`, `loads.load_combinations`, `loads.aashto_lrfd`, `rating.load_rating`, `loads.dynamic_impact` | AASHTO LRFD §3.4.1, §3.6.1, §3.6.2, §4.6.2.2; AASHTO MBE §6A.4.2 | [6 casos](#1-cargas-aashto-camião-chileno-e-avaliação-da-capacidade-de-carga) |
| Eurocódigo e Espanha: LM1 com tandem de Barré, LM2 de 400 kN, veículos especiais, vias fictícias e MC1/MC2 da IAP-11 com área remanescente, combinações 6.10/6.10a/6.10b e de serviço com escolha da ação de base, incremento dinâmico por norma | `loads.eurocode_lm1`, `ec1_traffic`, `loads.lm3_special`, `loads.iap11`, `loads.en1990_combinations`, `loads.multi_code` | EN 1991-2 §4.2.3, §4.3.2, §4.3.3, §6.4.5.2; EN 1990 Anexo A2; IAP-11 Cap. 4 | [5 casos](#2-eurocódigo-iap-11-e-outras-normas) |
| Linhas de influência e vigas contínuas: viga simples, contínua de N vãos pelos três momentos (momento e esforço transverso), forma fechada de dois vãos, posição crítica de um comboio, envolvente HL-93 de 2 a 6 vãos com a regra dos dois camiões a 90 %, número ótimo de vãos pelo custo | `loads.influence_lines`, `loads.multispan`, `optimization` | Müller-Breslau, Clapeyron; AASHTO LRFD §3.6.1.3.1 | [5 casos](#3-linhas-de-influência-e-vigas-contínuas) |
| Sismo e fragilidade: espectro de cálculo AASHTO, impulsos de Coulomb e Mononobe-Okabe, coeficiente q, confinamento e rótula plástica da EN 1998-2, pushover de pilar com idealização bilinear, curvas de fragilidade lognormais ajustadas por máxima verosimilhança, índice de Park-Ang, amortecedor de Bouc-Wen-Baber-Noori | `seismic`, `ec8_ductility`, `analysis.pier_pushover`, `fragility`, `datasets.concepcion_2010`, `damping.bwbn` | AASHTO LRFD §3.10; EN 1998-2 §4.1, §6.2.1, Anexo E; Park e Ang (1985); Baber e Noori (1985) | [6 casos](#4-sismo-ductilidade-e-fragilidade) |
| Superestrutura e memórias: viga-caixão pré-esforçada (M_n com f_ps aproximado, esforço transverso simplificado, tração principal na alma), razões exigência/capacidade de viga de betão, chave de corte por corte-atrito, memória Strength I em LaTeX e Markdown, estado de cálculo fechado por defeito | `design`, `memos`, `_common.audit_status` | AASHTO LRFD §5.6.3, §5.7.3, §5.7.4, §5.9.2.3.3 | [5 casos](#5-superestrutura-memórias-e-estado-de-cálculo) |
| Integrações: vias EN e AASHTO, repartição de Courbon, propriedades de vigas de alma cheia e de betão, grelha com apoios isostáticos em planta e cargas de tráfego (sem SAP2000), script pyRevit, desenho de disposição geral em DXF, API REST | `integration.grillage_model`, `integration.revit_export`, `integration.autocad_layout`, `api` | EN 1991-2 Tabela 4.1; AASHTO LRFD §3.6.1.1.1 | [5 casos](#6-integrações-e-api-rest) |

Os 32 scripts de `examples/` foram executados num ambiente limpo antes de serem publicados; a saída está em `examples/output/` e é a que se reproduz aqui. Vários verificam o resultado do pacote face a um cálculo à mão ou a um método independente dentro do próprio exemplo.

## Casos de uso

As saídas reproduzem-se exatamente como os scripts as imprimem, em espanhol.

### 1. Cargas AASHTO, camião chileno e avaliação da capacidade de carga

#### Envolvente HL-93 de 6 a 60 m: camião face ao tandem, vão de cruzamento e verificação à mão por Barré em 30 m

<details><summary>Saída real de <code>python examples/hl93_envelope_simple_spans_6_to_60_m_truck_vs_tandem_crossover_and_barre_hand_check_30_m.py</code></summary>

```text
Envolvente HL-93 por carril de diseño, IM = 1,33 solo sobre el vehículo, carril 9,34 kN/m sin IM
  L [m]  M_camión  M_tándem gobierna  M_carril  M_máx [kN·m] V_máx [kN]
      6       178       267   tandem        42           397      291.4
      8       289       376   tandem        75           575      320.1
     10       445       486   tandem       117           763      356.8
     12       604       596    truck       168           972      386.5
     15       845       760    truck       263          1386      420.9
     20      1248      1035    truck       467          2127      464.6
     30      2058      1585    truck      1051          3787      531.6
     40      2867      2134    truck      1868          5681      588.5
     50      3680      2684    truck      2919          7814      641.3
     60      4489      3234    truck      4203         10173      692.1

El camión pasa a gobernar el momento a partir de L ≈ 11.75 m; por debajo manda el tándem (220 kN en 1,2 m).

Comprobación a mano en L = 30 m (Barré): resultante 325 kN a 5.715 m del eje delantero, 1.445 m detrás del eje central;
  eje central en x = 14.2774 m, R_A = 154.67 kN → M = R_A·x − 35·4,27 = 2058.9 kN·m; barrido numérico de hl93_envelope: 2057.6 kN·m (-0.06 %)
  Cortante con los ejes pesados sobre el apoyo: 145 + 145·(30−4,27)/30 + 35·(30−8,54)/30 = 294.4 kN; V_máx = 294.4·1,33 + 9.34·30/2 = 531.6 kN (función: 531.6)

El barrido usa 60 posiciones del eje delantero y 200 secciones: queda ≈ 0,1 % por debajo del máximo exacto de Barré, del lado inseguro pero dentro del redondeo de diseño. Son solicitaciones por carril: multiplica por el factor de distribución (ejemplo distribution_factors_*) y el de presencia múltiple antes de comprobar una viga.
```

</details>

#### Camião chileno de 44 t com IM de 25 % face ao HL-93 em vãos de 10 a 50 m

<details><summary>Saída real de <code>python examples/hl93k_nch3171_chile_44t_truck_vs_hl93_impact_25_vs_33_percent_spans_10_to_50_m.py</code></summary>

```text
Camión chileno 44 t: ejes (62.0, 185.0, 185.0) kN a (4.0, 4.0) m, peso bruto 432 kN, IM = 1.25
Camión HL-93:    ejes (35.0, 145.0, 145.0) kN a (4.27, 4.27) m, peso bruto 325 kN, IM = 1.33; tándem 2 × 110 kN

  L [m]  M Chile  M HL-93 cociente V Chile V HL-93 cociente  gobierna HL-93
     10      865      763    1.135   432.2   356.8    1.211  tandem
     15     1681     1386    1.213   507.0   420.9    1.205  truck
     20     2556     2127    1.202   556.1   464.6    1.197  truck
     25     3493     2927    1.193   595.0   500.2    1.190  truck
     30     4487     3787    1.185   628.6   531.6    1.182  truck
     40     6654     5681    1.171   688.2   588.5    1.169  truck
     50     9051     7814    1.158   742.6   641.3    1.158  truck

L = 30 m, desglose del momento: camión chileno sin IM 2749 kN·m frente a HL-93 camión 2058 kN·m (peso bruto ×1.329, separación 4,0 frente a 4,27 m); con IM: 3437 frente a 2737 kN·m; carril común 1051 kN·m.
  Cociente total 1.185: el camión chileno pesa un 33 % más pero su IM es menor, y el carril idéntico diluye la diferencia.

La implementación chilena no incluye tándem ni regla de dos camiones; en luces cortas el tándem del HL-93 acorta la diferencia (cociente 1,135 en 10 m frente a 1,19–1,21 entre 15 y 25 m). Las solicitaciones son por carril, sin factor de distribución.
```

</details>

#### Fatores de distribuição AASHTO §4.6.2.2 para viga interior e exterior, e varrimento do espaçamento

<details><summary>Saída real de <code>python examples/distribution_factors_aashto_4_6_2_2_interior_exterior_girders_lever_rule_imperial_inputs.py</code></summary>

```text
Viga W40x199 compuesta: Kg = n·(I + A·e_g²) = 8·(14,900 + 58.8·48.0²) = 1,203,002 in⁴; S = 8.0 ft, L = 100.0 ft, t_s = 8.0 in, d_e = 2.5 ft

  factor                              1 carril 2+ carriles de diseño
  momento, viga interior (Tabla 4.6.2.2.2b-1)     0.461       0.657     0.657
  cortante, viga interior (Tabla 4.6.2.2.3a-1)     0.680       0.814     0.814
  momento, viga exterior                 0.525       0.687     0.687
  cortante, viga exterior                0.525       0.851     0.851
  (exterior: regla de la palanca con m = 1,20 para un carril; e = 0,77 + d_e/9,1 = 1.045 para dos o más)

Momento HL-93 por carril en L = 30.48 m: 3872 kN·m → por viga interior 2544 kN·m, exterior 2658 kN·m
Cortante HL-93 por carril: 534.5 kN → viga interior 435.3 kN, exterior 454.8 kN

Barrido de la separación S (L = 100 ft, t_s = 8 in, mismo Kg):
  S [ft] S [m]  g_M int  g_V int  g_M ext M por viga int [kN·m]
     6.0  1.83    0.537    0.671    0.700                  2081
     7.0  2.13    0.598    0.743    0.625                  2316
     8.0  2.44    0.657    0.814    0.687                  2544
     9.0  2.74    0.715    0.884    0.747                  2767
    10.0  3.05    0.771    0.952    0.805                  2985
    12.0  3.66    0.880    1.082    0.920                  3408

Más separación → más carga por viga, casi linealmente en cortante (0,2 + S/12 − (S/35)²) y con exponente 0,6 en momento. Rango de validez §4.6.2.2.2b: 3,5 ≤ S ≤ 16 ft, 4,5 ≤ t_s ≤ 12 in, 20 ≤ L ≤ 240 ft, 4 vigas o más; fuera de él la función no avisa.
```

</details>

#### Os treze estados limite da Tabela 3.4.1-1 aplicados a uma viga e a combinação de resistência condicionante

<details><summary>Saída real de <code>python examples/load_combinations_aashto_3_4_1_thirteen_limit_states_factored_moments_and_governing_strength.py</code></summary>

```text
Momentos sin mayorar por viga [kN·m]: DC = 2600, DW = 450, LL = 1850, WS = 120, WL = 40, EQ = 900, BR = 60, CT = 300, WA = 0 (LL ya incluye IM)

  estado límite   γ_DC  γ_DW  γ_LL  γ_WS  γ_EQ  M_u [kN·m]
  Strength_I      1.25  1.50  1.75  0.00  0.00        7268
  Strength_II     1.25  1.50  1.35  0.00  0.00        6504
  Strength_III    1.25  1.50  0.00  1.40  0.00        4093
  Strength_IV     1.50  1.50  0.00  0.00  0.00        4575
  Strength_V      1.25  1.50  1.35  0.40  0.00        6510
  Service_I       1.00  1.00  1.00  0.30  0.00        4976
  Service_II      1.00  1.00  1.30  0.00  0.00        5455
  Service_III     1.00  1.00  0.80  0.00  0.00        4530
  Service_IV      1.00  1.00  0.00  0.70  0.00        3134
  Fatigue_I       0.00  0.00  1.75  0.00  0.00        3238
  Fatigue_II      0.00  0.00  0.80  0.00  0.00        1480
  Extreme_I       1.25  1.50  0.50  0.00  1.00        5750
  Extreme_II      1.25  1.50  0.50  0.00  0.00        5150

Gobierna en resistencia: Strength_I con M_u = 7268 kN·m; contribuciones: DC 3250, DW 675, LL 3238, BR 105
Permanentes favorables (γ_p mínimo 0,90/0,65), por ejemplo para comprobar levantamiento: 2632 kN·m frente a 3925 con γ_p máximo

Tabla paralela aashto_lrfd.get_design_force('STRENGTH_I'): 7162 kN·m = 1,25·DC + 1,50·DW + 1,75·LL; los 105 kN·m de diferencia con load_combinations son el frenado BR (1,75·60), que esta tabla no contempla; combinaciones disponibles: ['STRENGTH_I', 'STRENGTH_II', 'STRENGTH_III', 'STRENGTH_V', 'SERVICE_I', 'SERVICE_II', 'SERVICE_III']
  STRENGTH_I: Resistencia I (Carga viva de diseño normal sin viento); EH = 1.5, EV = 1.35 (empujes de tierras para estribos)

Factores de resistencia φ (§5.5.4.2): flexure_tension_controlled_concrete 0.9, compression_controlled_spirals 0.75, compression_controlled_other 0.75, shear_normal_weight_concrete 0.9, shear_lightweight_concrete 0.7, torsion_concrete 0.9, bearing_on_concrete 0.7, tension_steel 0.95

Strength IV (1,50·DC) solo gobierna con mucha carga permanente frente a la viva; Extreme I usa 0,50·LL con el sismo. Los γ_WS del módulo (1,40 Strength III, 0,40 Strength V, 0,30 Service I, 0,70 Service IV) son los del esquema anterior a la 8ª edición (2017); desde ésta el viento parte de una ráfaga de 3 s y Strength III pasó a γ_WS = 1,0, con velocidades propias para Strength V y Service I. Revisa la Tabla 3.4.1-1 de la edición que te aplique.
```

</details>

#### Avaliação LRFR de três vigas em diferentes estados: inventário, operação e restrição do tráfego

<details><summary>Saída real de <code>python examples/load_rating_lrfr_inventory_operating_condition_system_factors_and_posting_three_girders.py</code></summary>

```text
HL-93 en 30 m: 3787 kN·m por carril × g = 0,62 → LL+IM = 2348 kN·m por viga; γ_LL = {'inventory': 1.75, 'operating': 1.35}

  viga                       C = φcφsφRn  RF inv  RF oper  lectura
  V1 buena, redundante              8550    1.13     1.46  admite la carga de diseño
  V2 regular (φ_c 0,95)             8122    1.02     1.32  admite la carga de diseño
  V3 mala + no redundante           6177    0.55     0.71  RF operación < 1: restringir el paso

Sensibilidad al factor de condición (viga V1):
    φ_c  RF inv  RF oper
   1.00    1.13     1.46
   0.95    1.02     1.32
   0.90    0.92     1.19
   0.85    0.81     1.05
   0.80    0.71     0.92

Con un efecto permanente favorable P = −300 kN·m (pretensado secundario): RF inventario 1.20 frente a 1.13
Nivel desconocido → ValueError: nivel debe ser 'inventory' u 'operating'

El RF es lineal en la capacidad y en el inverso de la carga viva: un 5 % menos de φ_c baja el RF un 5 % de la capacidad, no del RF. La función cubre Strength I con γ_DC 1,25 y γ_DW 1,50 (MBE permite 1,25 si el espesor del pavimento está medido); no evalúa cargas legales ni permisos, que usan otros γ_LL.
```

</details>

#### Vento sobre o tabuleiro, combinação com o camião e majoração em Strength III, Strength V e Service IV

<details><summary>Saída real de <code>python examples/wind_on_bridge_deck_pressure_line_load_combined_with_truck_strength_iii_v_and_service_iv.py</code></summary>

```text
Tablero de 40 m, altura expuesta 2.5 m, C_d = 1.5, V = 44.7 m/s (100 mph, velocidad base de las ediciones del LRFD anteriores a la 8ª):
  código   q [kPa]  w [kN/m] F total [kN]
  AASHTO     1.836     4.589        183.6
  EU         1.836     4.589        183.6
  AS         1.928     4.819        192.8
  NSR        1.836     4.589        183.6
  Comprobación: ½·1,225·44.7²·1.5 = 1.836 kPa; AS aplica un factor 1,05 propio del módulo.

Velocidad y coeficiente de arrastre (AASHTO):
  V [m/s]  km/h   Cd  w [kN/m]
     30.0   108  1.3     1.792
     40.0   144  1.5     3.675
     44.7   161  1.5     4.589
     50.0   180  1.7     6.508

Camión HL-93 de 325 kN con IM 33 % → 432.2 kN; viento 4.589 kN/m × 40 m = 183.6 kN; suma sin mayorar 615.8 kN (vertical + horizontal, solo orientativa)
Con código EU el camión no se mayora (LM1 ya incluye la amplificación): 325.0 kN

Mayoración de un efecto transversal (kN·m) con WS = 220 y WL = 40:
  Strength_I    γ_LL 1.75 γ_WS 0.00 γ_WL 0.00 → 7162
  Strength_III  γ_LL 0.00 γ_WS 1.40 γ_WL 0.00 → 4233
  Strength_V    γ_LL 1.35 γ_WS 0.40 γ_WL 1.00 → 6551
  Service_I     γ_LL 1.00 γ_WS 0.30 γ_WL 1.00 → 5006
  Service_IV    γ_LL 0.00 γ_WS 0.70 γ_WL 0.00 → 3204

Strength III (viento sin tráfico) y V (viento con tráfico) rara vez gobiernan la flexión longitudinal, pero sí los apoyos y la subestructura. Los γ_WS son los del esquema anterior a la 8ª edición del LRFD (Strength III 1,40); desde 2017 Strength III usa 1,0 con la presión de la nueva sección 3.8. El módulo no aplica factores de ráfaga, altura ni exposición (AASHTO 3.8 o c_e y c_f de EN 1991-1-4): úsalo para órdenes de magnitud.
```

</details>

### 2. Eurocódigo, IAP-11 e outras normas

#### LM1 numa viga de 20 m com duas vias: tandem de Barré face às duas fórmulas erradas e envolvente de 6429,5 kN·m

<details><summary>Saída real de <code>python examples/en1991_2_lm1_tandem_barre_vs_centered_group_and_lane_envelope_20_m_two_lanes_6429_kNm.py</code></summary>

```text
Viga biapoyada L = 20 m, dos carriles nocionales de 3,0 m (EN 1991-2 Tabla 4.2):
  carril 1: tándem 2 × 300 kN, carga repartida 9.0 kN/m² → 27.0 kN/m
  carril 2: tándem 2 × 200 kN, carga repartida 2.5 kN/m² → 7.5 kN/m

Momento máximo de un tándem de dos ejes Q a 1,2 m (carril 1, Q = 300 kN):
  Barré: eje crítico en x = L/2 − d/4 = 9.70 m, R_izq = 291.0 kN → M = 2822.7 kN·m (función: 2822.7)
  «grupo centrado» sumando dos secciones distintas (9,4 y 10,0 m): 2904.6 kN·m, +2.90 % sobre un máximo físicamente inalcanzable
  fórmula de carga repartida 2QL/8·(1 − (0,6/L)²) usada por loads.eurocode hasta 1.0: 1498.7 kN·m, -46.9 % (la mitad, del lado inseguro)

Envolvente LM1 dos carriles: carga repartida 34,5 kN/m → M 1725.0 kN·m, V 345.0 kN; tándems 2822.7 + 1881.8 kN·m, V 582 + 388 kN
  M_máx = 6429.5 kN·m, V_máx = 1315.0 kN

evaluate_eurocode_lm1 (calzada 7,0 m → 2 carriles): M_TS 4704.5, M_UDL 1725.0, total 6429.5 kN·m; V 1315.0 kN; carga total de tándems 1000 kN
  Mismo cortante que traffic_envelope_lm1 (1315 kN): un eje sobre el apoyo y el otro a 1,2 m, V_TS = 970 kN. Hasta 1.0 evaluate_eurocode_lm1 ponía los dos ejes a la vez sobre el apoyo (2Q = 1000 kN, total 1345 kN).
loads.eurocode.evaluate_lm1 (legado): M_total 6429.5 kN·m, idéntico; emite DeprecationWarning: «bridgecalc.loads.eurocode.evaluate_lm1 está obsoleto: usa br…»

Anchos de calzada y número de carriles que toma evaluate_eurocode_lm1 (tope de 3, sin área remanente):
  w =  5.0 m → 1 carriles, M_total  4172.7 kN·m, carga repartida 27.0 kN/m
  w =  6.0 m → 2 carriles, M_total  6429.5 kN·m, carga repartida 34.5 kN/m
  w =  7.0 m → 2 carriles, M_total  6429.5 kN·m, carga repartida 34.5 kN/m
  w =  9.0 m → 3 carriles, M_total  7745.4 kN·m, carga repartida 42.0 kN/m
  w = 10.5 m → 3 carriles, M_total  7745.4 kN·m, carga repartida 42.0 kN/m
  w = 12.0 m → 3 carriles, M_total  7745.4 kN·m, carga repartida 42.0 kN/m

El área remanente (2,5 kN/m² fuera de los carriles) no entra en evaluate_eurocode_lm1: para calzadas que no son múltiplo de 3 m usa evaluate_iap11_traffic_loads, que la reparte. Los valores son característicos y por tablero completo, sin α nacionales (α = 1) ni reparto transversal entre vigas.
```

</details>

#### LM2 para a laje e veículos especiais face ao LM1 de uma via

<details><summary>Saída real de <code>python examples/en1991_2_lm2_single_axle_400_kN_and_lm3_special_vehicles_sv120_sv196_vs_lm1_spans_10_to_40_m.py</code></summary>

```text
LM2: eje de 400 kN = 2 ruedas de 200 kN a 2.0 m, huella 0.35 × 0.6 m; comprobación local de losa entre vigas:
  luz local [m]  β_Q M = Q·L/4 [kN·m] V = Q [kN]
            2.0  1.0            200.0        400
            3.0  1.0            300.0        400
            4.0  1.0            400.0        400
            4.0  0.8            320.0        320
            6.0  1.0            600.0        400

LM3 — vehículos especiales (un carril, sin carga repartida acompañante) frente a LM1 de un carril:
  SV120         6 ejes,   1440 kN (  147 t), longitud  6.00 m, DAF 1.00 (EUROCODE)
  SV196        12 ejes,   2400 kN (  245 t), longitud 16.50 m, DAF 1.00 (EUROCODE)
  IRC Class A   8 ejes,    554 kN (   56 t), longitud 18.80 m, DAF 1.17 (INDIA)
  HS20-44       3 ejes,    320 kN (   33 t), longitud  8.54 m, DAF 1.33 (USA)
  Ojo: «SV196» suma 2400 kN ≈ 245 t y «SV120» 1440 kN ≈ 147 t; los nombres evocan los vehículos SV del anejo nacional británico, pero los ejes no los reproducen, y el Anexo A de EN 1991-2 define otra serie (600/150, 900/150…). Tómalos como convoyes de ejemplo.

  L [m]        SV120        SV196  IRC Class A      HS20-44 LM1 1 carril
     10         2304         1900          534          421         1663
     15         4104         3866          970          821         2833
     20         5904         6508         1492         1221         4173
     30         9504        12504         2756         2022         7359
     40        13104        18504         4141         2822        11221

SV196 en 30 m: M = 12504 kN·m con el eje delantero en x = 6.05 m (2400 kN sobre 16.5 m)
IRC Class A: DAF = 1 + 4,5/(6 + L) → 1.250 en 10 m, 1.098 en 40 m (tope 1,25)

AS_SM1600 del catálogo: (48.0, 96.0, 96.0) kN a (3.0, 1.2) m = 240 kN: NO es el M1600/S1600 de AS 5100.2 ni el antiguo T44 de 440 kN; tratarlo como un vehículo genérico de 3 ejes, no como norma.

Los momentos de LM3 son en el centro de la luz (línea de influencia triangular), no el máximo absoluto de Barré: para el SV120 en 20 m, centro 5904.0 frente a máximo bajo un eje 5910.5 kN·m (+0.11 %). Para LM3 EN 1991-2 A.4 toma DAF = 1,0 (vehículo a velocidad reducida) y permite combinarlo con LM1 frecuente en los demás carriles, cosa que aquí no se hace.
```

</details>

#### IAP-11: vias fictícias da Tabela 4.1, envolvente MC1 com área remanescente e diferença face à EN 1991-2

<details><summary>Saída real de <code>python examples/iap11_spain_lane_layout_table_4_1_and_mc1_mc2_envelope_vs_en1991_2_widths_4_5_to_12_m.py</code></summary>

```text
Tándem por carril (300.0, 200.0, 100.0) kN/eje, sobrecarga (9.0, 2.5, 2.5) kN/m², área remanente 2,5 kN/m²; γ_Q ELU = 1.35, ψ0 = 0.75

Carriles virtuales (IAP-11 Tabla 4.1):
  calzada w [m] carriles         anchos [m] remanente [m]
            4.5        1              [3.0]          1.50
            5.0        1              [3.0]          2.00
            5.4        2         [2.7, 2.7]          0.00
            5.7        2       [2.85, 2.85]          0.00
            6.0        2         [3.0, 3.0]          0.00
            7.0        2         [3.0, 3.0]          1.00
            9.5        3    [3.0, 3.0, 3.0]          0.50
           10.5        3    [3.0, 3.0, 3.0]          1.50
           12.0        4 [3.0, 3.0, 3.0, 3.0]          0.00

Envolvente MC1/MC2 para calzada de 10.5 m (3 carriles + 1,5 m remanente):
  L [m]    M_TS   M_UDL M_MC1 car. M_MC1 ELU V_MC1 car.   V ELU M_MC2 local EN 1991-2 M      Δ
     20    5645    2288       7933     10709       1622    2189        2000        7745  +2.4%
     30    8644    5147      13790     18617       1862    2514        3000       13369  +3.2%
     40   11643    9150      20793     28070       2097    2831        4000       20043  +3.7%

  La diferencia con evaluate_eurocode_lm1 es exactamente el área remanente: 2,5 kN/m² × 1,5 m = 3,75 kN/m → 422 kN·m en 30 m (M_UDL 5147 frente a 4725).

Tándem de Barré por carril en L = 30 m: 300 kN → M 4322 kN·m, V 588 kN, 200 kN → M 2881 kN·m, V 392 kN, 100 kN → M 1441 kN·m, V 196 kN
Luz corta: en L = 1,5 m (< 2,05 m) manda un solo eje centrado: M = 112.5 kN·m = 300·1,5/4

MC2 en el modelo (L local = luz del vano) es solo orientativo: la comprobación local real usa la luz entre vigas o nervios, no la del tablero. El módulo publica un solo ψ0 = 0.75 (el del tándem); la sobrecarga repartida tiene otro menor en IAP-11, así que para combinar por separado ponlo a mano. El valor de dimensionamiento longitudinal es el MC1.
```

</details>

#### EN 1990: 6.10, 6.10a e 6.10b com a ação de base escolhida por cálculo, serviço e sismo

<details><summary>Saída real de <code>python examples/en1990_combinations_6_10_6_10a_6_10b_leading_variable_selection_sls_frequent_and_seismic.py</code></summary>

```text
Permanentes (kN·m por tablero): {'tablero': 1800.0, 'pavimento+barreras': 320.0}; γ_G = 1.35 desfavorable, ξ = 0.85

1) Tabla de edificación (A1.1) tal como viene en el módulo, γ_Q = 1,50:
  ULS 6.10 :     6408 kN·m
  ULS 6.10a:     5463 kN·m
  ULS 6.10b:     5979 kN·m
  gobernante del set alternativo máx(6.10a, 6.10b): 5979 kN·m
  SLS characteristic  :     4484 kN·m
  SLS frequent        :     3170 kN·m
  SLS quasi_permanent :     2750 kN·m
  sísmica G + A_Ed + Σψ2·Q (A_Ed = 950): 3700 kN·m

2) Puente de carretera: ψ del Anexo A2 Tabla A2.1 añadidos al catálogo y γ_Q,tráfico = 1,35 (Tabla A2.4(B)):
  dominante            6.10    6.10a    6.10b
  tándem TS            5486     5014     5057
  sobrecarga UDL       5581     5014     5152
  viento               5154     5014     4725
  temperatura          5111     5014     4682
  función (máx. sobre dominantes): 6.10 5581, 6.10a 5014, 6.10b 5152 kN·m → en 6.10 gobierna «sobrecarga UDL» como dominante
  La sobrecarga repartida gana al tándem como dominante aunque valga la mitad: su ψ0 = 0,40 es el más bajo, así que es la que más sube al pasar de ψ0·Q a Q (0,60·700 = 420 frente a 0,25·1400 = 350 kN·m).
  SLS característica 4134, frecuente 3260, casi permanente 2210 kN·m (solo la térmica tiene ψ2 ≠ 0)

EN 1990 A2 trata el gr1a (TS + UDL) como un grupo con un solo ψ0 del grupo; aquí se separan para ver el efecto. El módulo no conoce el Anexo A2: γ_Q, γ_G de puentes (1,35 también) y ψ hay que ponerlos a mano, y GAMMA_Q es estado global del módulo (devuélvelo a 1,50 después, como arriba). 6.10a usa ψ0 también en la dominante; 6.10b reduce las permanentes con ξ = 0,85.
```

</details>

#### Incremento dinâmico por norma e as duas aproximações não normativas de `multi_code`

<details><summary>Saída real de <code>python examples/multi_code_as5100_cc40_dynamic_allowance_by_code_and_declared_non_normative_approximations.py</code></summary>

```text
Incremento dinámico IM (fracción) por código y componente:
  AASHTO other       → IM = 0.33
  AASHTO deck_joints → IM = 0.75
  AASHTO fatigue     → IM = 0.15
  NSR    other       → IM = 0.33
  AS     other       → IM = 0.30
  EU     other       → IM = 0.00
  SG     other       → IM = 0.00
  EU_RAIL φ2 − 1 (EN 1991-2 §6.4.5.2, vía con mantenimiento cuidadoso): LΦ 3 m → 0.670, LΦ 5 m → 0.527, LΦ 10 m → 0.306, LΦ 20 m → 0.157, LΦ 50 m → 0.030
  lm3_special.impact_factor (DAF): EUROCODE 1.00, AASHTO 1.33, INDIA 1.17, AS 1.30

Hasta 1.0 'EU' devolvía el φ2 ferroviario (0,16 en 20 m, 0,31 en 10 m) y lo multiplicaba sobre el LM1, que ya incluye la amplificación dinámica: doble conteo del 16–30 %.

multi_code.evaluate_as5100 — vehículo del módulo: ejes [60.0, 60.0, 80.0, 80.0, 80.0, 80.0] kN a [3.75, 1.2, 6.25, 1.2, 1.2] m (440 kN) + 6.0 kN/m, M_camión = IM·0,130·W·L:
  L [m] M AS5100 1 carril       V  HL-93 M
     20              1787     632     2127
     30              2906     662     3787
     40              4174     692     5681

multi_code.evaluate_cc40 — ejes [40.0, 160.0, 160.0] kN a [4.0, 1.2] m + 9.0 kN/m, M_camión = IM·W·L/5,5:
  L [m]  M_camión  M_carril  M_total       V
     20      1741       450     2191     569
     30      2612      1012     3624     614
     40      3482      1800     5282     659

Por qué no diseñar con estos dos módulos: ni el vehículo de 6 ejes y 440 kN con M = 0,130·W·L ni el camión de 360 kN con M = W·L/5,5 se han contrastado con AS 5100.2 (cargas M1600/S1600) ni con la CCP-14 colombiana (basada en AASHTO LRFD); ambos coeficientes son aproximaciones de envolvente sin barrido de posiciones. Se conservan por compatibilidad y están marcados como no normativos en el README. Para un tren de cargas concreto, barre sus ejes con influence_lines.critical_position o lm3_special.max_moment_simple_span.
```

</details>

### 3. Linhas de influência e vigas contínuas

#### Viga simples de 25 m: linhas de influência de momento e esforço transverso e posição crítica do camião

<details><summary>Saída real de <code>python examples/influence_lines_simple_beam_moment_and_shear_quarter_span_hl93_truck_critical_position_vs_envelope.py</code></summary>

```text
Viga biapoyada L = 25 m. LI de momento: ordenada máxima en el centro 6.250 m (= L/4), en el cuarto 4.6875 m (= 3L/16)
  Camión HL-93 (35.0, 145.0, 145.0) kN a (4.27, 4.27) m; carril 9.34 kN/m

  sección / tren                               x 1er eje [m] efecto [kN·m]
  M en L/2, camión, 35 kN delante                       8.23        1648.8
  M en L/2, camión, 35 kN detrás                        8.23        1648.8
  M en L/2, camión + carril en zona positiva            8.23        2378.4
  M en L/4, camión, 35 kN delante                       1.99        1256.0
  M en L/4, camión, 35 kN detrás                        6.28        1290.9
  M en L/4, camión + carril en zona positiva            1.99        1803.3

Momento del camión en la sección central por LI: 1648.8 kN·m; envolvente hl93_envelope (sección móvil, Barré): 1652.4 kN·m (+0.22 %): el máximo absoluto está bajo el eje central a 0,72 m del centro, no en el centro.
Tren en una posición dada (eje delantero en 8,0 m): M_centro = 1640.8 kN·m (envelope_from_il, sin barrido)

LI de cortante en x = L/4: salta de -0.248 a +0.748 al pasar la sección (−x/L a (L−x)/L)
  Camión con los ejes pesados justo a la derecha de la sección: x 1er eje = 6.28 m → V = 206.5 kN; con carril en la zona positiva: 272.4 kN
  Cortante en el apoyo (envolvente): 500.2 kN con IM y carril; sin IM el camión solo da 288.3 kN

critical_position suma el carril sobre toda la zona de ordenada positiva (correcto para máximos positivos); para efectos negativos invierte el signo de la LI antes de llamar. La malla manda: con 200 puntos el error de posición es L/200; aquí se usan 501.
```

</details>

#### Três momentos em dois e três vãos face à forma fechada e face ao método da rigidez direta

<details><summary>Saída real de <code>python examples/influence_line_continuous_three_moment_two_and_three_spans_support_moment_vs_closed_form_and_stiffness.py</code></summary>

```text
Dos vanos iguales de 30 m, LI del momento en el apoyo central (carga unidad en x):
   x [m] tres momentos forma cerrada  −a(L²−a²)/(4L²)
    5.00       -1.2153       -1.2153          -1.2153
   10.00       -2.2222       -2.2222          -2.2222
   17.32       -2.8867       -2.8867          -2.8868
   20.00       -2.7778       -2.7778          -2.7778
   25.00       -1.9097       -1.9097          -1.9097
   35.00       -1.9097       -1.9097          -1.9097
   40.00       -2.7778       -2.7778          -2.7778
   42.68       -2.8867       -2.8867          -2.8868
   50.00       -2.2222       -2.2222          -2.2222
  Mínimos: -2.8867 en x = 17.30 m y -2.8867 en x = 42.70 m → a* = L/√3 = 17.32 m desde cada extremo, η* = −L/(6√3) = -2.8868
  Diferencia máxima tres momentos − forma cerrada: 3.33e-15 m

Tres vanos desiguales [20.0, 30.0, 25.0] m: LI contra rigidez directa (EI = 1)
      M en carga en x tres momentos   rigidez versión 1.0
      20.0        8.0       -1.4638   -1.4638     -1.6729
      20.0       27.0       -2.5080   -2.5080     -1.3280
      20.0       44.0       -1.1121   -1.1121     -2.3097
      35.0        8.0       -0.5323   -0.5323            
      35.0       27.0        1.6854    1.6854     +1.7440
      35.0       44.0        1.4174    1.4174     +1.3747
      50.0        8.0        0.3992    0.3992            
      50.0       27.0       -1.1212   -1.1212     -2.2339
      50.0       44.0       -2.0531   -2.0531     -0.9410

LI de cortante en x = 15 m de la viga de 2 × 30 m: salto de -0.590 a +0.403; en el segundo vano es -0.0938 (pequeña y del signo del levantamiento)

La columna «versión 1.0» muestra el espejo: en el apoyo de 20 m, una carga a 27 m (7 m dentro del vano central) daba −1,33 cuando vale −2,51, y una a 44 m daba −2,31 cuando vale −1,11. El test dorado de la forma cerrada no lo detectaba porque solo comprobaba el valor del mínimo, idéntico en la LI reflejada. EI constante: no vale para cartelas ni cambios de sección.
```

</details>

#### Envolvente HL-93 em 2 × 30 e 3 × 30 m com a regra dos dois camiões, face ao método antigo de coeficientes

<details><summary>Saída real de <code>python examples/multispan_hl93_envelope_two_and_three_equal_spans_30_m_influence_lines_two_truck_rule_vs_old_coefficients.py</code></summary>

```text
Viga simple de 30 m como referencia: M = 3787 kN·m, V = 532 kN (un carril, IM 1,33)

2 × 30 m — método: líneas de influencia (tres momentos, EI constante) + barrido del tren de cargas
  M⁺ = 3013 kN·m en x = 46.89 m: truck 2208 (sin IM: camión 1660, tándem 1305) + carril 804; 1er eje en x = 42.69 m
  M⁻ = 3101 kN·m en el apoyo x = 30 m, regla «0.9·(2 camiones + carril)»: un vehículo 2250 (camión 902·1,33 + carril 1051) frente a 0,9·(2 camiones 1801·1,33 + carril) = 3101; separación entre camiones 18 m
  V = 579 kN en cara izquierda del apoyo x=30: camión 304·1,33 + carril 174
  sección                                signo  camión  tándem  carril  V [kN]
  apoyo extremo x=0+                         +   284.4   212.9   121.9   500.1
  apoyo extremo x=0+                         −    30.1    21.1    17.5    57.5
  cara izquierda del apoyo x=30              −   304.4   217.0   174.4   579.3
  cara derecha del apoyo x=30                +   304.4   217.0   174.4   579.3
  apoyo extremo x=60-                        +    30.1    21.1    17.5    57.5
  apoyo extremo x=60-                        −   284.4   212.9   121.9   500.1
  Versión 1.0 (coeficientes 0,080/0,100·w·L², 0,40·w·L con w = 1,33·325/L + 9,34): M⁺ 1710, M⁻ 2137, V 285 → +76 %, +45 %, +103 %
  Frente a la viga simple: M⁺ -20 %, V +9 %

3 × 30 m — método: líneas de influencia (tres momentos, EI constante) + barrido del tren de cargas
  M⁺ = 3023 kN·m en x = 76.89 m: truck 2172 (sin IM: camión 1633, tándem 1288) + carril 850; 1er eje en x = 72.76 m
  M⁻ = 2921 kN·m en el apoyo x = 60 m, regla «0.9·(2 camiones + carril)»: un vehículo 2260 (camión 962·1,33 + carril 981) frente a 0,9·(2 camiones 1703·1,33 + carril) = 2921; separación entre camiones 15 m
  V = 577 kN en cara derecha del apoyo x=60: camión 305·1,33 + carril 172
  sección                                signo  camión  tándem  carril  V [kN]
  apoyo extremo x=0+                         +   284.3   212.9   125.4   503.6
  apoyo extremo x=0+                         −    24.9    17.6    14.0    47.1
  cara izquierda del apoyo x=30              +     8.0     5.6     4.7    15.3
  cara izquierda del apoyo x=30              −   304.6   217.0   172.1   577.2
  cara derecha del apoyo x=30                +   297.7   215.5   162.7   558.7
  cara derecha del apoyo x=30                −    40.1    28.2    23.3    76.7
  cara izquierda del apoyo x=60              +    40.1    28.2    23.3    76.7
  cara izquierda del apoyo x=60              −   297.7   215.5   162.7   558.7
  cara derecha del apoyo x=60                +   304.6   217.0   172.1   577.2
  cara derecha del apoyo x=60                −     8.0     5.6     4.7    15.3
  apoyo extremo x=90-                        +    24.9    17.6    14.0    47.1
  apoyo extremo x=90-                        −   284.3   212.9   125.4   503.6
  Versión 1.0 (coeficientes 0,080/0,100·w·L², 0,40·w·L con w = 1,33·325/L + 9,34): M⁺ 1646, M⁻ 2287, V 306 → +84 %, +28 %, +88 %
  Frente a la viga simple: M⁺ -20 %, V +9 %

2 × 30 m sin IM: M⁺ 2461, M⁻ 2566, V 479 (el carril no cambia: 1051 kN·m = 9,34·30²/8 en el apoyo con los dos vanos cargados)

La continuidad baja el momento positivo un quinto respecto a la viga simple y sube el cortante en la cara del apoyo interior. El momento negativo lo gobierna el par de camiones al 90 %, no el tándem. Todo por carril y con EI constante: aplica factor de distribución y presencia múltiple fuera, y no lo uses con cartelas.
```

</details>

#### Vãos desiguais 30 + 40 + 30 m: secções críticas e carga de via só onde soma

<details><summary>Saída real de <code>python examples/multispan_unequal_spans_30_40_30_m_critical_sections_lane_only_where_it_adds_and_span_limits.py</code></summary>

```text
Viga continua (30.0, 40.0, 30.0) m, un carril HL-93, IM 1,33:
  M⁺ = 3436 kN·m en x = 50.84 m (vano 2): truck 2401 + carril 1034
  M⁻ = 3554 kN·m en x = 30 m, regla 0.9·(2 camiones + carril); carril 1321 kN·m, dos camiones 1976 kN·m a 21 m
  V = 608 kN en cara derecha del apoyo x=30

  sección de cortante                    signo  camión  tándem  carril  V [kN]
  apoyo extremo x=0+                         +   283.3   212.7   127.7   504.5
  apoyo extremo x=0+                         −    37.9    26.3    27.7    78.1
  cara izquierda del apoyo x=30              +     8.0     5.6     4.7    15.3
  cara izquierda del apoyo x=30              −   303.8   216.2   183.4   587.5
  cara derecha del apoyo x=30                +   305.6   216.7   201.6   608.0
  cara derecha del apoyo x=30                −    27.1    19.0    15.8    51.7
  cara izquierda del apoyo x=70              +    27.1    19.0    15.8    51.7
  cara izquierda del apoyo x=70              −   305.6   216.7   201.6   608.0
  cara derecha del apoyo x=70                +   303.8   216.2   183.4   587.5
  cara derecha del apoyo x=70                −     8.0     5.6     4.7    15.3
  apoyo extremo x=100-                       +    37.9    26.3    27.7    78.1
  apoyo extremo x=100-                       −   283.3   212.7   127.7   504.5

Carril para M⁺ en el centro del vano de 40 m: la LI es positiva solo entre x = 30.1 y 69.9 m (el vano central); los vanos laterales tienen ordenada negativa (hasta -0.962) y quedan sin carril: 9.34 kN/m × área positiva = 1034 kN·m frente a 9,34·40²/8 = 1868 de la viga simple.
Carril para M⁻ en el apoyo de 30 m: la LI es negativa en los vanos 1 y 2 y positiva en el 3 (máx +0.770); el carril carga solo los dos primeros.

Cuatro vanos de 25 m: M⁺ 2303 (x = 88.6 m), M⁻ 2272 (x = 75 m), V 544 kN; un vano extremo gobierna el positivo y un apoyo contiguo a los vanos extremos (x = 25 o 75 m, simétricos) el negativo
  Entrada inválida → ValueError: Se admiten de 2 a 6 vanos (recibidos 1)
  Entrada inválida → ValueError: Se admiten de 2 a 6 vanos (recibidos 7)
  Entrada inválida → ValueError: span_m debe ser > 0

Con vanos laterales más cortos (30/40/30 ≈ 0,75) los apoyos interiores son simétricos y el positivo máximo cae en el vano central. Luces muy distintas o relaciones < 0,6 piden revisar el levantamiento en los vanos cortos: la LI de reacción en el estribo se hace negativa y esta función no publica reacciones.
```

</details>

#### Número de vãos que minimiza o custo para pontes de 120 a 400 m

<details><summary>Saída real de <code>python examples/span_optimization_number_of_spans_pier_vs_deck_cost_model_120_to_400_m_and_governing_hl93_moment.py</code></summary>

```text
Coste pila 250 kUSD, tablero 8 kUSD/m a 30 m con exponente 1,5, luces admitidas 15–80 m:
  L total [m] n óptimo luz [m] coste [MUSD] M HL-93 [kN·m]  candidatos (n: luz → MUSD)
          120        2    60.0         1.61          10173  2: 60 → 1.61; 3: 40 → 1.61; 4: 30 → 1.71; 5: 24 → 1.86; 6: 20 → 2.03; 7: 17 → 2.23…
          200        4    50.0         2.82           7814  3: 67 → 2.89; 4: 50 → 2.82; 5: 40 → 2.85; 6: 33 → 2.94; 7: 29 → 3.06; 8: 25 → 3.21…
          300        6    50.0         4.35           7814  4: 75 → 4.54; 5: 60 → 4.39; 6: 50 → 4.35; 7: 43 → 4.37; 8: 38 → 4.43; 9: 33 → 4.53…
          400        8    50.0         5.88           7814  5: 80 → 6.23; 6: 67 → 6.02; 7: 57 → 5.92; 8: 50 → 5.88; 9: 44 → 5.89; 10: 40 → 5.95…

Sensibilidad al coste de pila (L total = 200 m):
  pila [kUSD]   n luz [m] coste [MUSD]
           50  12    16.7         1.74
          150   6    33.3         2.44
          250   4    50.0         2.82
          600   3    66.7         3.59
         2000   3    66.7         6.39

Exponente del tablero (L total = 200 m, pila 250 kUSD): exp 1.2: n = 3; exp 1.5: n = 4; exp 2.0: n = 7; exp 2.5: n = 8
Luces restringidas a 40–60 m: n = 4, luz 50.0 m, candidatos [(4, 50.0), (5, 40.0)]

El modelo de coste es ilustrativo: no incluye cimentaciones (que dependen de la altura de pila y el terreno), ni el salto de tipología al pasar de 40–50 m (losa → cajón → pretensado), ni el coste de los estribos; M_design es el de viga simple, no el del tablero continuo. Sirve para ordenar escenarios, no para presupuestar.
```

</details>

### 4. Sismo, ductilidade e fragilidade

#### Espectro de cálculo AASHTO §3.10 em rocha, solo rijo e solo mole

<details><summary>Saída real de <code>python examples/aashto_3_10_design_spectrum_site_coefficients_sds_sd1_ts_and_spectral_ordinates_three_sites.py</code></summary>

```text
Valores de roca: PGA = 0.4 g, S_s = 1.0 g, S_1 = 0.4 g. Coeficientes de sitio (F_pga, F_a, F_v) de las Tablas 3.10.3.2-1/2/3 para esos niveles:

  clase             F_pga  F_a  F_v    A_s   S_DS   S_D1 T_0 [s] T_s [s]
  B (roca)            1.0  1.0  1.0  0.400  1.000  0.400   0.080   0.400
  D (suelo rígido)    1.1  1.1  1.6  0.440  1.100  0.640   0.116   0.582
  E (suelo blando)    0.9  0.9  2.4  0.360  0.900  0.960   0.213   1.067

  T [s]          B (roca)  D (suelo rígido)  E (suelo blando)
   0.00             0.400             0.440             0.360
   0.10             1.000             1.007             0.613
   0.20             1.000             1.100             0.866
   0.40             1.000             1.100             0.900
   0.60             0.667             1.067             0.900
   0.80             0.500             0.800             0.900
   1.00             0.400             0.640             0.900
   1.50             0.267             0.427             0.640
   2.00             0.200             0.320             0.480
   3.00             0.133             0.213             0.320
   4.00             0.100             0.160             0.240

Lectura para pilas (Sa en g):
  T = 0.4 s: B 1.000, D 1.100, E 0.900
  T = 0.8 s: B 0.500, D 0.800, E 0.900
  T = 1.5 s: B 0.267, D 0.427, E 0.640

En suelo blando la meseta baja (F_a 0,9) pero F_v = 2,4 estira T_s hasta 1.07 s: una pila de 1,5 s ve 0.640 g frente a 0.267 g en roca, ×2.4.
La función no interpola los coeficientes de sitio entre niveles de aceleración ni fija la categoría SDC (A–D, Tabla 3.10.6-1); dale los F de la tabla y clasifica fuera. Sa(0) = A_s, sin rama de periodo largo T_L.
```

</details>

#### Encontro de 6 m: Coulomb ativo e passivo e Mononobe-Okabe com k_h de 0 a 0,30

<details><summary>Saída real de <code>python examples/abutment_coulomb_active_passive_and_mononobe_okabe_seismic_pressure_kh_0_to_0_3.py</code></summary>

```text
Estribo H = 6.0 m, relleno γ = 19.0 kN/m³, φ = 33.0°, δ = 22.0° (2/3 φ), trasdós vertical, talud horizontal:
  Coulomb K_a = 0.2645 (Rankine sin fricción 0.2948), K_p = 8.084; P_a = ½·γ·H²·K_a = 90.4 kN/m

Mononobe-Okabe (ψ = atan(k_h/(1 − k_v))):
    k_h   k_v  ψ [°]    K_ae P_ae [kN/m]   ΔP_ae K_ae/K_a
   0.00  0.00   0.00  0.2645        90.4     0.0    1.000
   0.05  0.00   2.86  0.2948       100.8    10.4    1.115
   0.10  0.00   5.71  0.3288       112.4    22.0    1.243
   0.15  0.00   8.53  0.3671       125.6    35.1    1.388
   0.20  0.00  11.31  0.4106       140.4    50.0    1.553
   0.25  0.00  14.04  0.4603       157.4    67.0    1.741
   0.30  0.00  16.70  0.5178       177.1    86.6    1.958
   0.20  0.10  12.53  0.4318       132.9    42.5    1.633
   0.20 -0.10  10.30  0.3941       148.3    57.8    1.490

Geometría: trasdós inclinado β y talud α (k_h = 0,15):
  β [°] α [°]     K_a    K_ae     P_a    P_ae
      0     0  0.2645  0.3671    90.4   125.6
     10     0  0.3439  0.4594   117.6   157.1
      0    10  0.2993  0.4374   102.4   149.6
      0    15  0.3234  0.4945   110.6   169.1
     10    10  0.3953  0.5575   135.2   190.7

Límite de M-O: con α = 15° y k_h = 0,35, φ − ψ − α = -1.3° < 0 → el radicando se trunca a 0 y K_ae = 1.331 ya no es fiable (Seed-Whitman o análisis de desplazamientos).

El punto de aplicación no se calcula: el estático va a H/3 y el incremento ΔP_ae suele colocarse a 0,6·H (Seed & Whitman). k_h de diseño en estribos = ½·A_s·… según AASHTO 11.6.5 si el estribo puede desplazarse; aquí k_h es un dato. Sin agua ni cohesión.
```

</details>

#### EN 1998-2: coeficiente q, taxa de confinamento, comprimento da rótula plástica e deslocamento-objetivo

<details><summary>Saída real de <code>python examples/ec8_ductility_behaviour_factor_q_confinement_omega_w_plastic_hinge_length_and_target_displacement.py</code></summary>

```text
Factor de comportamiento q (EN 1998-2 Tabla 4.1, forma simplificada del módulo):
  reinforced_concrete_ductile            q = 3.50
  reinforced_concrete_limited_ductility  q = 1.50
  steel_ductile                          q = 3.50
  non_ductile                            q = 1.00
  Reducción por esbeltez de cortante α_s = L_s/h en pila dúctil de hormigón: α_s 4.0 → q 3.50, α_s 3.0 → q 3.50, α_s 2.0 → q 2.86, α_s 1.5 → q 2.47, α_s 1.0 → q 2.02, α_s 0.8 → q 1.00

Confinamiento ω_w,req para una pila de 1,5 × 1,5 m, f_cd = 20 MPa (C30/37, γ_c 1,5), f_yd = 435 MPa:
  N_Ed [kN]    η_k ω_w,req (α_n·α_s = 1) ω_w,req (α = 0,8)
       3000  0.067                 0.120             0.120
       6000  0.133                 0.120             0.120
       9000  0.200                 0.120             0.120
      13500  0.300                 0.131             0.163
      18000  0.400                 0.174             0.217
  Con η_k ≤ 0.276 manda el mínimo ω_w,min = 0,12 (zonas dúctiles, rectangular); por encima crece lineal con el axil.

Longitud de rótula plástica L_p = 0,10·L_v + 0,015·f_y·d_b (Anexo E):
  L_v =  6.0 m, Ø20: L_p = 0.60 + 0.150 = 0.750 m (12.5 % de L_v)
  L_v =  8.0 m, Ø25: L_p = 0.80 + 0.188 = 0.988 m (12.3 % de L_v)
  L_v =  8.0 m, Ø32: L_p = 0.80 + 0.240 = 1.040 m (13.0 % de L_v)
  L_v = 12.0 m, Ø25: L_p = 1.20 + 0.188 = 1.388 m (11.6 % de L_v)

Desplazamiento objetivo (demanda espectral frente a capacidad):
  T_ef = 1.2 s, S_d = 180 mm, capacidad 250 mm → ratio 0.72 OK
  T_ef = 1.8 s, S_d = 270 mm, capacidad 250 mm → ratio 1.08 NO CUMPLE
  T_ef = 0.9 s, S_d = 120 mm, capacidad 150 mm → ratio 0.80 OK
  Tipo desconocido → ValueError: Unknown pier_type 'timber'

q de la tabla real depende también de la relación axil (η_k > 0,3 lo reduce con λ(η_k)) y del tipo de rótula (vertical/inclinada, en cabeza o pie); el módulo solo aplica la corrección por α_s. ω_w,req omite el término 0,13·(f_yd/f_cd)·(ρ_L − 0,01) de la fórmula completa de §6.2.1.4: es la forma básica por axil. Unidades SI estrictas (N, m², Pa).
```

</details>

#### Pushover de pilares retangulares e circulares com idealização bilinear e as simplificações declaradas

<details><summary>Saída real de <code>python examples/pier_pushover_sdof_rectangular_and_circular_piers_bilinear_equal_energy_ductility_and_declared_simplifications.py</code></summary>

```text
f'c 30 MPa, f_y 420 MPa, N = 6000 kN, ρ_l 1,5 % salvo indicación:
  pila                               M_y [kN·m]     M_u φ_y [1/km] L_p [m] V_y [kN] Δ_y [mm] Δ_u [mm]   μ_Δ K_e [kN/mm]
  rect. 1,5 × 1,5 m, H 8 m                18760   20637      3.150   0.871     2121     60.8    254.0  4.18        34.9
  rect. 1,5 × 1,5 m, H 12 m               18760   20637      3.150   1.191     1399    135.3    536.3  3.96        10.3
  rect. 1,5 × 2,0 m, H 8 m                33519   36871      2.362   0.871     3790     45.6    190.5  4.18        83.1
  circular Ø 1,8 m, H 8 m                 25608   28169      2.742   0.871     2895     52.9    221.1  4.18        54.7
  rect. 1,5 × 1,5 m, H 8 m, ρ 3 %         36621   40283      3.150   0.871     4140     60.8    254.0  4.18        68.1

Pila de referencia: 50 puntos; curva trilineal origen → (Δ_y, V_y) → (Δ_u, V_u): tramo elástico hasta 64.5 mm, luego endurecimiento del 10 % hasta 254.0 mm
  Δ_y = φ_y·H²/3 = 0.00315·8²/3 = 67.2 mm; Δ_p = (φ_u − φ_y)·L_p·(H − L_p/2) = 186.8 mm
  L_p Priestley 2007 (0,08·H + 0,022·f_y·d_b, d_b = 25 mm fijo) = 0.871 m frente a EN 1998-2 Anexo E (0,10·L_v + 0,015·f_y·d_b) = 0.958 m

Idealización bilineal de una curva exponencial V = 900·(1 − e^(−Δ/18)): V_y 765 kN, Δ_y 26.5 mm, K_e 28.9 kN/mm (secante al 70 %), μ 4.53; energía curva 91804 frente a bilineal 87919 kN·mm (-4.2 %)

Lo que NO hace: ni diagrama momento-curvatura por equilibrio de sección (el 0,9·A_s·f_y·d ignora el acero comprimido y la posición real del bloque de compresiones), ni φ_u del hormigón confinado (es 10·φ_y por decreto), ni P-Δ, ni cortante. El diámetro de barra para L_p está fijo en 25 mm. Úsalo para ordenar alternativas; para capacidades, sección por fibras.
```

</details>

#### Fragilidade de pilares: probabilidades por estado de dano, Park-Ang, ajuste por máxima verosimilhança e dados do sismo do Maule 2010

<details><summary>Saída real de <code>python examples/fragility_lognormal_rc_pier_damage_probabilities_park_ang_index_mle_fit_and_concepcion_2010_illustrative_dataset.py</code></summary>

```text
Parámetros por defecto (mediana [g], β): {'slight': (0.15, 0.55), 'moderate': (0.3, 0.55), 'extensive': (0.5, 0.55), 'complete': (0.8, 0.55)}

  IM [g] P(≥ligero) P(≥moderado) P(≥extenso) P(≥completo) | sin daño  ligero moderado extenso completo
    0.10      0.230        0.023       0.002        0.000 |    0.770   0.208    0.021   0.002    0.000  Σ = 1.000
    0.20      0.700        0.230       0.048        0.006 |    0.300   0.469    0.183   0.042    0.006  Σ = 1.000
    0.30      0.896        0.500       0.177        0.037 |    0.104   0.396    0.323   0.139    0.037  Σ = 1.000
    0.50      0.986        0.823       0.500        0.196 |    0.014   0.162    0.323   0.304    0.196  Σ = 1.000
    0.80      0.999        0.963       0.804        0.500 |    0.001   0.036    0.159   0.304    0.500  Σ = 1.000
    1.20      1.000        0.994       0.944        0.770 |    0.000   0.006    0.050   0.175    0.770  Σ = 1.000
  En la mediana de cada estado P = 0,5 exactamente: ligero 0,15 g, completo 0,80 g.

Índice de daño de Park-Ang (DI < 0,4 operacional, 0,4–0,7 reparable, > 1 colapso), δ_u = 180 mm, F_y = 900 kN, β = 0,10:
  δ_max    40 mm, E_h    20 kN·m → DI = 0.222 + 0.012 = 0.235 (operacional)
  δ_max    90 mm, E_h    80 kN·m → DI = 0.500 + 0.049 = 0.549 (reparable)
  δ_max   130 mm, E_h   150 kN·m → DI = 0.722 + 0.093 = 0.815 (daño severo)
  δ_max   170 mm, E_h   300 kN·m → DI = 0.944 + 0.185 = 1.130 (colapso)

Ajuste por máxima verosimilitud binomial a 60 observaciones sintéticas generadas con mediana 0,45 g y β 0,50 (43 con daño): mediana 0.420 g, β 0.386
  Con 2000 observaciones: mediana 0.461 g, β 0.480. Con 60 el error de muestreo es del orden del 10–20 %. Hasta 1.0 la función devolvía la media de ln(IM) de los casos con daño (0,88 g con estos mismos 60 datos), que describe dónde cayeron los daños, no la fragilidad.

Pilas del Maule 2010 (datasets.concepcion_2010), VALORES ILUSTRATIVOS sembrados a partir de las referencias, no medidos:
  pila               puente                   H [m]    M_y    M_u    θ_u daño observado
  LoRojas_P1         Lo Rojas                   7.5   2800   3600  0.035      extensive
  BioBio_P3          Puente Bío-Bío (antiguo)  12.0   4200   5300  0.040       complete
  LlacolenE_P2       Llacolén                  10.0   3500   4400  0.045       moderate
  Juan_Pablo_II_P5   Juan Pablo II             14.0   5000   6200  0.050         slight
  Raqui1_P2          Raqui 1                    6.5   2200   2900  0.030      extensive

  Curvas del conjunto (mediana, β) y P(≥ds | PGA = 0.65 g): slight (0.18, 0.55) → 0.99, moderate (0.35, 0.6) → 0.85, extensive (0.55, 0.65) → 0.60, complete (0.85, 0.7) → 0.35
  pier_by_name no distingue mayúsculas: BioBio_P3 — Colapso por desplazamiento de tablero.

Las medianas 0,15/0,30/0,50/0,80 g con β 0,55 son valores representativos del módulo, no una fila literal de la Tabla 7-9 de HAZUS (que usa β = 0,6 y medianas por clase HWB); pásalos explícitamente a hazus_rc_pier_fragility(params). Las pilas de Concepción llevan M_y, M_u y θ_u asignados «por juicio» en el código fuente: sirven para probar el flujo, no como evidencia del terremoto.
```

</details>

#### Amortecedor de Bouc-Wen-Baber-Noori: ciclos, energia dissipada e degradação

<details><summary>Saída real de <code>python examples/bwbn_hysteresis_damper_sinusoidal_history_force_displacement_loops_dissipated_energy_and_degradation.py</code></summary>

```text
Parámetros: α = 0.05, n = 1.0, β = γ = 0.5, F_y = 250.0 kN, K₀ = 20000.0 kN/m → u_y = F_y/K₀ = 12.5 mm

  ciclo amplitud [mm] μ = u/u_y F_máx [kN]  F/F_y E_h [kN·m]  E/(4·F_y·(u−u_y))
      1           6.2       0.5      100.1  0.401      0.231   — (sin fluencia)
      2          12.5       1.0      167.0  0.668      1.638   — (sin fluencia)
      3          25.0       2.0      238.1  0.952      8.993               0.72
      4          50.0       4.0      286.0  1.144     31.881               0.85
      5          75.0       6.0      312.5  1.250     56.330               0.90
  El lazo elastoplástico ideal disipa 4·F_y·(u_max − u_y) por ciclo; con n = 1 la transición es suave y la energía queda entre el 72 y el 90 % del ideal; con α = 0,05 la fuerza sigue creciendo tras F_y (1000 kN/m de rigidez posfluencia), y por debajo de u_y el lazo ya disipa algo (Bouc-Wen no tiene rama elástica pura).

Exponente n (transición elástica-plástica), ciclo a 4·u_y:
  n = 1.0: F_máx  283.3 kN, E_h 30.066 kN·m
  n = 2.0: F_máx  287.4 kN, E_h 32.472 kN·m
  n = 5.0: F_máx  287.5 kN, E_h 33.749 kN·m

Degradación (δ_ν rigidez, δ_η resistencia) en 5 ciclos iguales a 4·u_y:
  δ_ν = 0.00, δ_η = 0.00: F_máx ciclo 1 283.3 → ciclo 5 287.3 kN; E_h 30.066 → 32.720 kN·m
  δ_ν = 0.05, δ_η = 0.00: F_máx ciclo 1 262.6 → ciclo 5 145.0 kN; E_h 27.312 → 16.353 kN·m
  δ_ν = 0.00, δ_η = 0.05: F_máx ciclo 1 282.3 → ciclo 5 266.0 kN; E_h 26.803 → 14.586 kN·m
  δ_ν = 0.05, δ_η = 0.05: F_máx ciclo 1 262.5 → ciclo 5 152.0 kN; E_h 25.400 → 13.839 kN·m

bwbn_step subdivide cada incremento en subpasos de |du|/u_y ≤ 0,02 (Euler explícito), así que la historia puede ser gruesa. Hasta 1.0 la descarga seguía la misma ley que la carga (sin lazo: energía nula) y z no se normalizaba por u_y (la fuerza no pasaba de 0,37·F_y con μ = 6). No hay pinzamiento (los parámetros de pinching de BWBN no están implementados) ni dependencia de la velocidad: es un disipador histerético, no viscoso.
```

</details>

### 5. Superestrutura, memórias e estado de cálculo

#### Viga-caixão pré-esforçada: momento resistente, esforço transverso e tração principal na alma

<details><summary>Saída real de <code>python examples/box_girder_aashto_5_7_prestressed_flexural_strength_mcft_shear_and_principal_web_stress_service_iii.py</code></summary>

```text
Cajón de dos almas de 350 mm, canto 2,2 m, ala comprimida 6,0 m, f'c = 45.0 MPa; A_ps = 7000 mm² (50 cordones de 140 mm², f_pu 1860) en d_p = 2000 mm, A_s = 3000 mm² en d_s = 2100 mm
  Flexión: c por equilibrio → a = β₁·c = 62.6 mm, f_ps = f_pu·(1 − 0,28·c/d_p) = 1838 MPa, M_n = 28,427 kN·m; M_u = 25,000 kN·m → cumple (φ = 1,0 para pretensado adherente con control por tracción)

  A_ps [mm²]  a [mm] f_ps [MPa]  M_n [kN·m] M_n/M_u
        4000    38.7       1846      17,747    0.71
        5500    50.7       1842      23,116    0.92
        7000    62.6       1838      28,427    1.14
        8500    74.4       1833      33,682    1.35
       10000    86.2       1829      38,880    1.56
  f_ps baja al crecer A_ps (más c/d_p); el bloque comprimido a ≈ 0,1 m queda dentro del ala de 0,25 m, así que la hipótesis de sección rectangular vale.

Cortante V_u = 6,500 kN, b_v = 700 mm, d_v = 1900 mm, β = 2, θ = 36°, φ = 0,90:
  estribos               V_c [kN] V_s [kN] V_n [kN] V_r [kN] V_r/V_u
  4Ø16 a 300 (2 almas)       1481     3504     4985     4487    0.69
  4Ø16 a 200                 1481     5256     6737     6064    0.93
  4Ø20 a 200                 1481     8211     9693     8723    1.34
  4Ø20 a 150                 1481    10949    12430    11187    1.72
  Tope V_n,máx = 0,25·f'c·b_v·d_v = 14,962 kN, lejos de gobernar.
  Con el coeficiente en ksi aplicado en MPa (versión 1.0) V_c habría sido 564 kN en vez de 1481.

Tracción principal en el alma (Service III), límite −0,29·√f'c MPa (0,110·√f'c en ksi):
  f_pc [MPa] v [MPa]  σ₁ [MPa]  límite   estado
         4.0     1.5    -0.500  -1.945       OK
         4.0     2.5    -1.202  -1.945       OK
         2.5     2.5    -1.545  -1.945       OK
         6.0     3.0    -1.243  -1.945       OK
         1.0     2.0    -1.562  -1.945       OK
         2.0     4.0    -3.123  -1.945   excede

Límites del módulo: sección rectangular equivalente (si a supera el espesor del ala habría que pasar a sección en T y no avisa), f_ps por la fórmula aproximada sin compatibilidad de deformaciones, β y θ fijos (sin iterar ε_x), sin pérdidas de pretensado ni fase constructiva. φ no se deduce de la ductilidad de la sección (§5.5.4.2.1): lo pones tú.
```

</details>

#### Viga de betão de 30 m: da envolvente HL-93 às razões de flexão e esforço transverso para três armaduras

<details><summary>Saída real de <code>python examples/concrete_girder_superstructure_dcr_flexure_shear_from_hl93_strength_i_30_m_three_reinforcement_options.py</code></summary>

```text
Viga interior L = 30 m: DC 25 kN/m → M 2812 kN·m, DW 5 kN/m → M 562; HL-93 3787 kN·m/carril × g_M 0.65 = 2462 kN·m; V 532 × g_V 0.8 = 425 kN
  Strength I: M_u = 1,25·2812 + 1,50·562 + 1,75·2462 = 8667 kN·m; V_u = 1326 kN

Sección f'c = 35.0 MPa, b_w = 600 mm, d = 1750 mm, f_y = 500 MPa, φ = 0,90:
  armado                       A_s [mm²]  a [mm] φM_n [kN·m] DCR flexión
  16 Ø32                           12864   360.3        9087       0.954 cumple
  20 Ø32                           16080   450.4       11033       0.786 cumple
  24 Ø32                           19296   540.5       12849       0.675 cumple

  estribos                     A_v [mm²] s [mm] φV_n [kN] DCR cortante
  2 ramas Ø12 a 300                  226    300      1570        0.844 cumple
  2 ramas Ø12 a 200                  226    200      1938        0.684 cumple
  4 ramas Ø12 a 200                  452    200      3040        0.436 cumple
  sin estribos (solo V_c)              0      0       835        1.587 NO cumple

  Casos límite: A_s = 0 → DCR inf; a ≥ d (A_s = 90 000 mm²) → inf: el módulo devuelve infinito en vez de lanzar, así que hay que comprobar el valor.

Son chequeos de anteproyecto: brazo d − a/2 con un solo lecho de armadura, sin acero comprimido, β y θ fijos (sin ε_x), d_v = 0,9·d en vez de máx(0,9d, 0,72h), sin armadura mínima ni separación máxima de estribos. Usa box_girder_* para pretensado y una comprobación seccional completa para el proyecto.
```

</details>

#### Chave de corte por corte-atrito: armadura, compressão, coeficientes de interface e limites superiores

<details><summary>Saída real de <code>python examples/shear_key_capacity_aashto_5_7_4_friction_cohesion_axial_compression_and_upper_limits_sweep.py</code></summary>

```text
Llave de 600 × 400 mm, f'c = 30.0 MPa, 4 Ø16 (A_vf = 804 mm²) f_y = 420.0 MPa, c = 0,5 MPa, μ = 1,0, sin compresión:
  A_cv = 240,000 mm²; acero 338 kN; V_ni = 0,5·A_cv + 1,0·A_vf·f_y = 458 kN; topes 1800 (0,25·f'c·A_cv) y 2400 kN (10·A_cv); V_di = 0,9·458 = 412 kN

Barrido de armadura (μ = 1,0, P_c = 0):
          A_vf acero [kN]    V_ni gobierna V_di [kN]
         4 Ø16        338     458     V_ni       412
         6 Ø16        507     627     V_ni       564
         4 Ø20        528     648     V_ni       583
         6 Ø20        791     911     V_ni       820
         8 Ø25       1650    1770     V_ni      1593

Compresión en la junta P_c (4 Ø20):
  P_c [kN]    V_ni V_di [kN] + frente a P_c = 0
         0     648       583                +0 %
       200     848       763               +31 %
       500    1148      1033               +77 %
      1000    1648      1483              +154 %

Coeficientes de interfaz (4 Ø20, P_c = 0): por defecto del módulo: c 0.50 MPa, μ 1.0 → V_di 583 kN; intencionadamente rugosa, 0,24 ksi: c 1.65 MPa, μ 1.0 → V_di 831 kN; no rugosa, 0,075 ksi: c 0.52 MPa, μ 0.6 → V_di 397 kN

Con 8 Ø25, V_ni = 1770 kN queda a 2 % del tope 0,25·f'c·A_cv = 1800 kN; con 500 kN de compresión ya manda el tope (1800 kN): a partir de ahí añadir acero no sube la capacidad, hay que agrandar la llave o subir f'c.
Los pares (c, μ) de AASHTO LRFD §5.7.4.4 para hormigón contra hormigón endurecido son 0,24 ksi / 1,0 con superficie intencionadamente rugosa y 0,075 ksi / 0,6 sin rugosidad (ASPIRE, invierno 2025, Tabla 1); el módulo toma c = 0,5 MPa y μ = 1,0 por defecto, que no es ninguna fila de esa tabla: pásalos explícitamente. No comprueba A_vf mínimo ni la fuerza sísmica de la llave.
```

</details>

#### Memória Strength I passo a passo em LaTeX e Markdown

<details><summary>Saída real de <code>python examples/memo_hl93_handcalcs_strength_i_latex_markdown_saved_to_file_and_legacy_memo_now_exact.py</code></summary>

```text
Memoria handcalcs L = 30 m, DC 25 kN/m, DW 5 kN/m, IM 33 %, MPF 1,0:
  M_DC = 2812.5, M_DW = 562.5, M_camión = 2057.9, M_tándem = 1584.6 (gobierna truck), M_carril = 1050.8 kN·m
  M_LL+IM = (máx·1.33 + carril)·MPF = 3787.8; M_u = 1,25·2812 + 1,50·562 + 1,75·3788 = 10988.0 kN·m
  LaTeX renderizado por handcalcs; 1028 caracteres de LaTeX → memoria_hl93_30m.tex; 396 de Markdown → memoria_hl93_30m.md

LaTeX generado (primeras líneas):
  | \section*{Memoria LRFD HL-93 (handcalcs) -- Strength I}
  | 
  | \subsection*{Cargas muertas}
  | 
  | $$
  | \begin{aligned}
  | M_{DC} &= w_{DC} \cdot \frac{ \left( L \right) ^{ 2 } }{ 8 }  = 25.000 \cdot \frac{ \left( 30.000 \right) ^{ 2 } }{ 8 } &= 2812.500  
  | \\

Markdown generado:
  | # Memoria LRFD HL-93 -- Strength I
  | 
  | ## Datos
  | - L = 30.0 m, lanes = 2
  | - DC = 25.0 kN/m, DW = 5.0 kN/m
  | 
  | ## Cargas muertas
  | - M_DC = 2812.50 kN-m
  | - M_DW = 562.50 kN-m
  | 
  | ## Carga viva HL-93
  | - M_truck = 2057.92 kN-m
  | - M_tandem = 1584.59 kN-m
  | - Gobierna: truck
  | - M_lane = 1050.75 kN-m
  | - IM = 1.33
  | - M_LL+IM = 3787.78 kN-m
  | 
  | ## Strength I
  | - gamma_DC=1.25, gamma_DW=1.5, gamma_LL=1.75
  | - M_u = 10988.00 kN-m

Comprobación cruzada con hl93_envelope: camión 2057.6 (memoria 2057.9, barrido propio de 80 posiciones: +0.02 %), tándem 1584.6 frente a 1584.6

Memoria ligera generar_memoria_hl93: camión 2057.6, tándem 1584.6 (gobierna truck), carril 1050.75 (9,34 kN/m), M_u = 10987.3 kN·m
  Hasta 1.0 el camión salía de 145·L/4 − 145·4,3/2 = 775.75 kN·m, -62 % frente al barrido, con carril de 9,3 y sin tándem: M_u habría sido 7996 en vez de 10987 kN·m (-27 %).

Las dos memorias son por carril sin factor de distribución ni presencia múltiple (MPF = 1,0 por defecto): el M_u impreso es el de un carril entero, no el de una viga. Para una viga, multiplica M_LL+IM por g antes o pasa MPF = g.
```

</details>

#### Estado de uma verificação fechado por defeito e agregação dos estados de um tabuleiro

<details><summary>Saída real de <code>python examples/audit_status_closed_by_default_resolve_and_aggregate_for_bridge_checks.py</code></summary>

```text
Condiciones de evidencia (6): ('demand_present', 'capacity_present', 'analysis_executed', 'geometry_present', 'material_present', 'reinforcement_present')

  caso                                                                       estado
  DCR 0,85 con las seis evidencias                                 CALCULADO_CUMPLE
  DCR 1,20 con las seis evidencias                                  CALCULADO_FALLA
  DCR 0,85 sin declarar evidencias                                     NO_CALCULADO
  DCR 0,85, analysis_executed=False (SAP2000 no corrió)                NO_CALCULADO
  DCR 0,85, falta f'c en missing_inputs                                NO_CALCULADO
  DCR 0,85, método no soportado (hormigón con fórmulas de acero)  REQUIERE_REVISION
  sin número (None) con evidencias                                REQUIERE_REVISION
  DCR +inf (A_s = 0 en concrete_box_girder_flexure)               REQUIERE_REVISION
  DCR NaN                                                         REQUIERE_REVISION
  DCR −0,2 (signo invertido)                                      REQUIERE_REVISION
  DCR 1 + 6,66e-16 (tres ULP)                                      CALCULADO_CUMPLE
  DCR 1,001 (0,1 % de exceso)                                       CALCULADO_FALLA
  demanda cero con evidencias                                      CALCULADO_CUMPLE

Agregación de los estados de un tablero:
  [] (ninguna comprobación)                            → NO_CALCULADO
  [flexión CUMPLE, cortante CUMPLE, flecha CUMPLE]     → CALCULADO_CUMPLE
  [CUMPLE, NO_APLICA (LTB en hormigón)]                → CALCULADO_CUMPLE
  [NO_APLICA, NO_APLICA]                               → NO_APLICA
  [CUMPLE, REQUIERE_REVISION]                          → REQUIERE_REVISION
  [CUMPLE, NO_CALCULADO (sin SAP2000)]                 → NO_CALCULADO
  [CUMPLE, NO_CALCULADO, FALLA]                        → CALCULADO_FALLA
  [REQUIERE_REVISION, NO_CALCULADO]                    → NO_CALCULADO
  ['CALCULADO_CUMPLE', 'texto raro']                   → REQUIERE_REVISION

  all([]) en Python es True: por eso la lista vacía se trata aparte y da NO_CALCULADO; un tablero con cero comprobaciones no está aprobado, está sin comprobar.
Este contrato es el que usa verify_bridge_grillage_results para clasificar cada barra y el global, y el que convierte un DCR infinito (capacidad nula) en REQUIERE_REVISION en vez de en FALLA: la ausencia se propaga como ausencia.
```

</details>

### 6. Integrações e API REST

#### Vias EN e AASHTO, Courbon, propriedades de secção e estabilidade dos apoios sem SAP2000

<details><summary>Saída real de <code>python examples/grillage_lanes_en1991_2_vs_aashto_courbon_transverse_factors_section_props_and_kinematic_stability_without_sap2000.py</code></summary>

```text
Carriles por ancho de calzada:
  w [m]  EN 1991-2 n × ancho + remanente  AASHTO LRFD n × ancho + remanente
    5.0                  1 × 3.00 + 2.00                    1 × 5.00 + 0.00
    5.7                  2 × 2.85 + 0.00                    1 × 5.70 + 0.00
    6.5                  2 × 3.00 + 0.50                    2 × 3.25 + 0.00
    7.2                  2 × 3.00 + 1.20                    2 × 3.60 + 0.00
   10.5                  3 × 3.00 + 1.50                    2 × 3.60 + 3.30
   12.0                  4 × 3.00 + 0.00                    3 × 3.60 + 1.20
  EN: 3,0 m por carril desde 6 m; AASHTO: 3,6 m (12 ft) y dos carriles entre 6,0 y 7,2 m.

Courbon para 4 vigas en y = [0.0, 3.33, 6.67, 10.0] m (tablero rígido transversalmente):
  carga en y =  1.5 m → η = [0.565, 0.355, 0.145, -0.065]; Ση = 1.000, Ση·y = 1.50 m
  carga en y =  5.0 m → η = [0.25, 0.25, 0.25, 0.25]; Ση = 1.000, Ση·y = 5.00 m
  carga en y =  8.5 m → η = [-0.065, 0.145, 0.355, 0.565]; Ση = 1.000, Ση·y = 8.50 m
  carga en y = 10.0 m → η = [-0.2, 0.1, 0.4, 0.7]; Ση = 1.000, Ση·y = 10.00 m
  Con la carga en el borde la viga opuesta recibe η < 0 (levantamiento): la hipótesis de tablero rígido exagera el reparto en tableros flexibles.

  sección                A [m²]  I33 [m⁴]  I22 [m⁴]    J [m⁴] Av2 [m²] Wel33 [m³] Wpl33 [m³] masa [kg/m]
  PG_1500x500x40x16      0.0627   0.02514   0.00083   0.00002   0.0240    0.03352    0.03727       492.4
  VIGA_HA_1800x600       1.0800   0.29160   0.03240   0.10241   0.9000    0.32400    0.48600      2700.0
  Viga armada: A = 2·0,5·0,04 + 1,42·0,016 = 0.0627 m² ✓; Wpl/Wel = 1.112. Hormigón: J por la fórmula de Saint-Venant para rectángulo, Av = 5/6·A.

Emparrillado 2 vanos × 4 vigas × 3 diafragmas interiores: {'n_x': 9, 'divisions_per_span': 4, 'n_joints': 36, 'n_frames_long': 32, 'n_frames_trans': 27, 'n_frames': 59, 'n_supports': 12}
  Comprobación: n_x = 2·4 + 1 = 9, nudos 9·4 = 36, longitudinales 32, transversales 27, apoyos 3 líneas × 4 = 12

Esquema de apoyos correcto (fijo en x = 0, guía Uy en la viga 0, resto deslizante): estable_3d = True, GDL {'sum_Fx': True, 'sum_Fy': True, 'sum_Fz': True, 'sum_Mx': True, 'sum_My': True, 'sum_Mz': True}, Ux coaccionados 4, Uy 3, Uz 12
  sin ningún Ux (tablero libre longitudinalmente) → ValueError: Inestabilidad cinemática (sum_Fx): ningún apoyo restringe Ux
  sin ninguna coacción Uy → ValueError: Inestabilidad cinemática (sum_Fy): ningún apoyo restringe Uy
  Ux también en las pilas (coacción térmica) → ValueError: Coacción longitudinal espuria en apoyos móviles [8 nudos]

Todo esto corre sin SAP2000: lo que sí necesita fastsap es section_props_from_catalog (perfiles EN 10365), build_bridge_grillage y los bucles de análisis y rediseño. Los carriles EN con área remanente coinciden con iap11_lane_layout; AASHTO redondea a 3,6 m por carril y no usa área remanente.
```

</details>

#### Grelha de um tabuleiro metálico de 2 × 30 m: nós, barras, apoios e cargas de tráfego

<details><summary>Saída real de <code>python examples/grillage_generate_two_span_steel_deck_from_spec_joints_frames_supports_and_loads_summary_no_sap2000.py</code></summary>

```text
Material S355 (EN 1993-1-1 Tabla 3.1 / EN 10025-2 (S355)): E = 210 GPa, f_y = 355 MPa, γ = 78.5 kN/m³
Vigas PG_1500x500x40x16 (492 kg/m, I33 = 0.0251 m⁴), diafragmas PG_800x300x25x12 (188 kg/m)

Emparrillado: 52 nudos, 87 barras (Counter({'girder': 48, 'diaphragm': 39})); recuentos derivados {'n_x': 13, 'divisions_per_span': 6, 'n_joints': 52, 'n_frames_long': 48, 'n_frames_trans': 39, 'n_frames': 87, 'n_supports': 12}
  Apoyos: 12 nudos en x = [0.0, 30.0, 60.0]; coacciones [Ux,Uy,Uz,Rx,Ry,Rz]: N0_0 [True, True, True]; N0_1 [True, False, True]; N6_0 [False, True, True]; N6_1 [False, False, True]
  Estabilidad: {'sum_Fx': True, 'sum_Fy': True, 'sum_Fz': True, 'sum_Mx': True, 'sum_My': True, 'sum_Mz': True}, dilatación longitudinal libre en móviles = True

Cargas (EN_1991_2_LM1, IM = 1.0): losa 0,25 m → 15.625 kN/m por viga; DW (2 kPa + 5 kN/m de barreras) → 6.25 kN/m por viga
  LANE_1         y = 0.0–3.0 m, UDL 27.0 kN/m, tándem 300 kN/eje, Courbon [0.565, 0.355, 0.145, -0.065]
  LANE_2         y = 3.0–6.0 m, UDL 7.5 kN/m, tándem 200 kN/eje, Courbon [0.295, 0.265, 0.235, 0.205]
  LANE_3         y = 6.0–9.0 m, UDL 7.5 kN/m, tándem 100 kN/eje, Courbon [0.025, 0.175, 0.325, 0.475]
  REMAINING_AREA y = 9.0–10.0 m, UDL 2.5 kN/m, tándem 0 kN/eje, Courbon [-0.155, 0.115, 0.385, 0.655]
  Carril repartido por viga (Courbon, carriles desde el borde y = 0): {0: 17.2675, 1: 13.1725, 2: 9.0775, 3: 4.9825} kN/m (total 44.5 kN/m)
  Vehículo para M⁺: ejes [600.0, 600.0] kN en x = [14.7, 15.9] m (Barré en el vano 1); para V: en x = [0.05, 1.25] m (desfase 0.05 m para no caer en el nudo)
  Reparto del eje entre vigas: {0: 0.385, 1: 0.295, 2: 0.205, 3: 0.115}; viga exterior gobernante 0
  Envolvente analítica de viga simple (comprobación): M = 13369 kN·m, V = 1806 kN
  Cargas puntuales LIVE_VEHICLE_M: 8 sobre barras, p. ej. {'frame_id': 'L2_0', 'girder_index': 0, 'axle_index': 1, 'x_global_m': 14.7, 'dist_local_m': 4.7, 'load_kN': 230.999997, 'fz_global_kN': -230.999997}
  Combinaciones (3): 0: {'name': 'ULS_STR', 'norm_ref': 'EN 1990 §6.4.3.2 Ec. 6.10 + Anexo A2 Tabla A2.4(B)', 'factors': {'DEAD': 1.35, 'DW': 1.35, 'LIVE_LANE': 1.35, 'LIVE_VEHICLE_M': 1.35}}; 1: {'name': 'ULS_STR_SHEAR', 'norm_ref': 'EN 1990 §6.4.3.2 Ec. 6.10 + Anexo A2 Tabla A2.4(B)', 'factors': {'DEAD': 1.35, 'DW': 1.35, 'LIVE_LANE': 1.35, 'LIVE_VEHICLE_V': 1.35}}; 2: {'name': 'SLS_CHARACTERISTIC', 'norm_ref': 'EN 1990 §6.5.3 Ec. 6.14b (Combinación característica)', 'factors': {'DEAD': 1.0, 'DW': 1.0, 'LIVE_LANE': 1.0, 'LIVE_VEHICLE_M': 1.0}}

Modelo guardado: grillage_2x30_steel.json (30 kB)

Limitaciones declaradas en meta (3): El tren de cargas de tráfico (HL-93 / LM1) se introduce mediante casos estáticos en posici… | La losa superior de hormigón se introduce como masa/carga permanente tributaria sobre las … | Los aparatos de apoyo se modelan como vínculos puntuales ideales isostáticos en planta (fi…
Estados límite aplicables (10) y comprobaciones no implementadas (5): torsión/alabeo, abolladura, conectores, fatiga, aparatos de apoyo quedan fuera.

Sin spec, generate_grillage pide perfiles del catálogo EN 10365 de fastsap (HEM 1000 / HEB 400) y falla sin él; con spec y secciones calculadas aquí corre en puro Python. El tándem se aplica en posiciones discretas (M⁺ en el vano 1, V en x = 0+), no como carga móvil.
```

</details>

#### Script pyRevit para uma ponte de três vãos

<details><summary>Saída real de <code>python examples/revit_export_pyrevit_script_three_span_bridge_piers_deck_saved_and_inspected.py</code></summary>

```text
Script pyRevit generado: 87 líneas, 3690 caracteres → viaducto_demo_pyrevit.py
  Transacciones: 1; NewFamilyInstance: 5 (2 pilas + 3 tramos de tablero); familias: ['BridgeCalc_AdaptivePier', 'BridgeCalc_Deck']
  Parámetros fijados: ['Depth', 'Height', 'Thickness', 'Width']
  SPANS_M = [30.0, 40.0, 30.0]; cota del tablero = altura de la primera pila (12.0 m) en todos los tramos

Fragmento (pila 2 y tramo 2):
  | # Pier 2 @ x=70.000 m
  |     pier_pt_1 = XYZ(70.0, 0.0, 0.0)
  |     pier_sym_1 = next(s for s in DB.FilteredElementCollector(doc)
  |                        .OfClass(DB.FamilySymbol)
  |                        if s.Family.Name == "BridgeCalc_AdaptivePier")
  |     if not pier_sym_1.IsActive:
  |         pier_sym_1.Activate(); doc.Regenerate()
  |     pier_inst_1 = doc.Create.NewFamilyInstance(
  |         pier_pt_1, pier_sym_1, Structure.StructuralType.NonStructural)
  |     pier_inst_1.LookupParameter("Height").Set(14.0)
  |     pier_inst_1.LookupParameter("Width").Set(1.8)
  |     pier_inst_1.LookupParameter("Depth").Set(2.5)
  | # Deck span 2: 30.00 → 70.00 m
  |     deck_start_1 = XYZ(30.0, 0.0, 12.0)
  |     deck_end_1   = XYZ(70.0, 0.0, 12.0)
  |     deck_line_1 = Line.CreateBound(deck_start_1, deck_end_1)
  |     deck_sym_1 = next(s for s in DB.FilteredElementCollector(doc)
  |                        .OfClass(DB.FamilySymbol)
  |                        if s.Family.Name == "BridgeCalc_Deck")
  |     if not deck_sym_1.IsActive:

Sin pilas declaradas: se sintetizan 3 pilas de 10 m en x = ['25.000', '50.000', '75.000'] m

El script coloca el tablero a la cota de la primera pila en todos los tramos (sin pendiente ni peralte) y usa unidades de proyecto sin convertir a pies: en un proyecto en pies las coordenadas en metros salen mal. Es un arranque geométrico para pyRevit, no un modelo BIM: sin apoyos, estribos ni armado. Plantilla de botón en integration/pyrevit_scripts/bridgecalc_import.py.
```

</details>

#### Desenho de disposição geral em DXF através de um cliente CAD intercambiável

<details><summary>Saída real de <code>python examples/autocad_layout_general_arrangement_dxf_via_ezdxf_adapter_and_recorder_client_entity_counts.py</code></summary>

```text
Puente [30.0, 40.0, 30.0] m con pilas en x = [30.0, 70.0] m. draw_bridge_layout → {'lines': 6, 'texts': 6, 'piers': 2}
  Capas y color: {'BR-AXIS': 7, 'BR-PIER': 1, 'BR-DIMS': 3, 'BR-TITLE': 7}
  Primitivas por capa: {('BR-AXIS', 'polyline'): 1, ('BR-PIER', 'polyline'): 2, ('BR-PIER', 'text'): 2, ('BR-DIMS', 'polyline'): 3, ('BR-DIMS', 'text'): 3, ('BR-TITLE', 'text'): 1}
  Textos: ['P1', 'P2', 'L1=30.00 m', 'L2=40.00 m', 'L3=30.00 m', 'Viaducto demo 30+40+30']
  Puente de 2 luces sin pilas declaradas: se sintetiza 1 pila a 10 m de altura; textos ['P1', 'L1=20.00 m', 'L2=20.00 m', 'Sin pilas']

DXF viaducto_demo_disposicion_general.dxf: versión AC1032, $INSUNITS = 6 (6 = metros), entidades {'LWPOLYLINE': 7, 'TEXT': 6}, capas ['BR-AXIS', 'BR-PIER', 'BR-DIMS', 'BR-TITLE']
  Conteos del dibujo {'lines': 6, 'texts': 6, 'piers': 2}; segmentos AutoLISP acumulados: 10 líneas y 6 textos (para generar un .dwg nativo con accoreconsole cuando exista)
  Extensión en x: -2.0 a 102.0 m (eje de 100 m más el marco)

El plano es esquemático: eje en planta, pilas como segmentos verticales hacia −z, cotas como polilíneas y texto; sin bloques, estilos de texto ni acotación real. export_bridge_grillage_drawings añade planta, alzado, sección y cuadros a partir del resultado del bucle de diseño, pero requiere rebardxf y, para el .dwg, AutoCAD con accoreconsole.
```

</details>

#### API REST sem servidor: HL-93, vigas contínuas, LM1, LM2, Park-Ang e validação

<details><summary>Saída real de <code>python examples/rest_api_hl93_single_multispan_lm1_lm2_park_ang_testclient_json_and_422_on_invalid_input.py</code></summary>

```text
API «BridgeCalc API» v1.1.0; GET /health → {'status': 'ok'}
  Rutas: ['/api/bridge/fragility/park-ang', '/api/bridge/hl93/multispan', '/api/bridge/hl93/single', '/api/bridge/traffic/lm1', '/api/bridge/traffic/lm2']

POST hl93/single span 30 → 200: {'M_max_kNm': 3787.362276254152, 'V_max_kN': 531.6497833333333, 'governing_vehicle': 'truck'}
  sin IM: M = 3108 kN·m

POST hl93/multispan 2 × 30 → 200: M⁺ 3013 kN·m en x = 46.89 m, M⁻ 3101 en x = 30, V 579 kN
  método: líneas de influencia (tres momentos, EI constante) + barrido del tren de cargas; gobierna: M+: truck + carril en x = 46.89 m; M-: 0.9·(2 camiones + carril) en apoyo x = 30.00 m; V: truck + carril en cara izquierda del apoyo x=30
  componentes M⁻: regla «0.9·(2 camiones + carril)», carril 1051 kN·m, dos camiones a 18 m

POST traffic/lm1 L 20 m, 2 carriles → 200: M 6429.5 kN·m, V 1315.0 kN, EN 1991-2 §4.3.2 (LM1); carriles [{'lane': 1, 'Qik_kN': 300.0, 'qik_kPa': 9.0}, {'lane': 2, 'Qik_kN': 200.0, 'qik_kPa': 2.5}]
  con α_Q 0,9 y α_q 0,8 (anexo nacional): M 5614.1 kN·m
POST traffic/lm2 → {'Qak_kN': 400.0, 'beta_Q': 1.0, 'contact_surfaces_m': '2 x (0.35 x 0.60)', 'transverse_spacing_m': 2.0, 'code': 'EN 1991-2 §4.3.3 (LM2)'}
POST fragility/park-ang → {'damage_index': 0.7592592592592592, 'status': 'collapse_risk'}
  La API llama «collapse_risk» a todo DI ≥ 0,7; la escala de Park-Ang que cita el módulo reserva el colapso para DI > 1,0, así que 0,7–1,0 es daño severo, no colapso.

  hl93/single con luz 0 → 422: span_m: Input should be greater than 0
  hl93/single con luz negativa → 422: span_m: Input should be greater than 0
  hl93/multispan con 7 vanos → 422: n_spans: Input should be less than or equal to 6
  hl93/multispan con 1 vano → 422: n_spans: Input should be greater than or equal to 2
  traffic/lm1 con 9 carriles → 422: n_lanes: Input should be less than or equal to 5
  fragility/park-ang con δ_u = 0 → 422: delta_u: Input should be greater than 0

La validación de rango la hace Pydantic (422) antes de llegar al núcleo; los ValueError del núcleo que escapan a esa validación salen como 400. La API no expone el factor de distribución, IAP-11, la calificación de carga ni los módulos sísmicos: esos van por Python. Sin autenticación ni estado: pensada para montar detrás de un gateway.
```

</details>

## Verificação

- HL-93 em 30 m face ao cálculo manual da AASHTO (M ≈ 3789 kN·m, V ≈ 531,6 kN) e o camião face à posição de Barré dentro do exemplo (−0,06 %) (`test_hl93_envelope.py`).
- Tandem do LM1 por Barré face a uma pesquisa numérica sobre todas as posições e secções (2822,7 kN·m em 20 m), envolvente LM1 de 20 m derivada à mão (6429,5 kN·m e 1315 kN), e as três vias do LM1 (`eurocode_lm1`, `ec1_traffic`, `iap11`) coincidentes em momento e esforço transverso para vãos de 1 a 30 m (`test_ec1_tandem_barre.py`, `test_ec1_traffic_api.py`, `test_lm1_tandem_shear_and_short_spans.py`).
- Cargas da IAP-11 e da EN 1991-2 ancoradas na ficha W01630 do mestrado (300/200/100 kN, 9,0/2,5/2,5 kN/m², LM2 de 400 kN) com oráculos de forma fechada (`test_golden_fichas_bridge_loads.py`, `test_iap11_loads.py`).
- Linhas de influência de vigas contínuas face à forma fechada −a(L² − a²)/(4L²), ao pico −L/(6√3) em L/√3 e a um solver independente de rigidez direta em três vãos desiguais; envolvente multivão com a carga de via no apoio igual a w·L²/8 e no encontro igual a 7·w·L/16 (`test_influence_continuous.py`, `test_influence_continuous_three_moment_orientation.py`, `test_multispan_influence_envelope.py`).
- Combinações EN 1990 6.10/6.10a/6.10b e de serviço com valores calculados à mão, avaliação LRFR, coeficientes SI da AASHTO como conversão exata dos de ksi, ciclo de Bouc-Wen com energia positiva e força que tende para F_y, ajuste de fragilidade que recupera os parâmetros de dados sintéticos (`test_en1990_combinations.py`, `test_load_rating.py`, `test_aashto_si_coefficients.py`, `test_bwbn_hysteresis_loop.py`, `test_fragility_binomial_mle.py`).
- Correções da 1.1.0, cada uma com o seu teste: orientação da equação dos três momentos e espelho da forma fechada no segundo vão; envolvente multivão por linhas de influência em vez de coeficientes; tandem do LM1 antigo (antes metade); esforço transverso do tandem e vãos curtos em `eurocode_lm1`; camião exato na memória simplificada; IM da EN 1991-2 igual a zero para estradas; V_c e tração principal com coeficientes SI; ciclo de Bouc-Wen; ajuste de fragilidade por máxima verosimilhança; versão única. Detalhe em [CHANGELOG.md](CHANGELOG.md).
- `tests/test_examples.py` executa os 32 exemplos como subprocessos em ubuntu e windows × Python 3.11–3.13. Os testes da grelha que precisam do `fastsap` (cliente do SAP2000) ou do `jmworkbench` são omitidos sem eles.

## Limitações

- Todas as envolventes são por via de cálculo e sem fator de distribuição nem de presença múltipla, salvo indicação. `hl93_envelope` varre 60 posições e fica ≈ 0,1 % abaixo do máximo de Barré.
- `envelope_multispan` supõe EI constante, apoios rígidos e uma via; não publica reações nem levantamentos nos encontros. As linhas de influência contínuas também não admitem mudanças de secção.
- `loads.multi_code` (AS 5100.2 e camião colombiano) usa coeficientes de envolvente não contrastados com essas normas; os veículos «SV120», «SV196» e «AS 5100.2 SM1600 T44» de `lm3_special` são de exemplo, e o seu momento avalia-se a meio vão. O camião chileno de 44 t (62/185/185 kN, IM 25 %) toma-se tal como o módulo o define e não foi contrastado aqui com o Manual de Carreteras do MOP; os seus nomes no código (`hl93k_nch_envelope`, `NCH_*`) mantêm-se por compatibilidade, mas a NCh 3171 é a norma chilena de combinações de cargas, não a que define o camião.
- `evaluate_eurocode_lm1` atribui ⌊w/3⌋ vias com limite de 3 e sem área remanescente; para faixas de rodagem que não sejam múltiplo de 3 m ou entre 5,4 e 6 m use `iap11_lane_layout` ou `evaluate_iap11_traffic_loads`.
- `en1990_combinations` leva os ψ de edifícios e γ_Q = 1,50 como constante do módulo; para pontes é preciso acrescentar os ψ do Anexo A2 e mudar γ_Q, como faz o exemplo. `load_combinations` usa os γ_WS anteriores à 8.ª edição do LRFD (Strength III 1,40). `wind_pressure_bridge` é a pressão dinâmica sem rajada, altura nem exposição.
- `design`: secções retangulares equivalentes, f_ps aproximado, β = 2 e θ = 36° fixos, sem perdas nem fases; as razões devolvem `inf` com capacidade nula em vez de lançar um erro. `shear_key_capacity` usa por defeito c = 0,5 MPa e μ = 1,0, que não é nenhuma linha da tabela da AASHTO: passe os coeficientes da superfície real.
- `pier_pushover_sdof` estima M_y = 0,9·A_s·f_y·d + 0,1·N·D, M_u = 1,1·M_y e φ_u = 10·φ_y, com Ø 25 mm fixo para a rótula; `behavior_factor_q` só corrige pela esbelteza de corte e `confinement_required` omite o termo da taxa longitudinal.
- `HAZUS_RC_PIER_PARAMS` e as curvas de `datasets.concepcion_2010` são parâmetros representativos, e os cinco pilares do Maule 2010 têm momentos e rotações atribuídos no código, não medidos. O endpoint de Park-Ang chama `collapse_risk` a DI ≥ 0,7.
- O amortecedor de Bouc-Wen-Baber-Noori não tem estrangulamento (pinching) nem dependência da velocidade. `optimization` usa um modelo de custo ilustrativo.
- A grelha aplica o tandem em posições discretas, sem carga móvel, ação mista laje-viga nem rigidez dos aparelhos de apoio. Construí-la e analisá-la no SAP2000 requer o `fastsap` e o SAP2000. O script do Revit não converte unidades nem dá inclinação ao tabuleiro. O desenho DXF é esquemático, e o `.dwg` precisa do AutoCAD com accoreconsole.

## Normas e referências

- AASHTO LRFD Bridge Design Specifications, 9.ª ed. (2020): §3.4.1 (combinações), §3.6.1 (HL-93 e presença múltipla), §3.6.2 (incremento dinâmico), §3.8 (vento), §3.10 (sismo), §4.6.2.2 (fatores de distribuição), §5.6.3, §5.7.3, §5.7.4 e §5.9.2.3.3 (betão). AASHTO Manual for Bridge Evaluation, §6A.4.2 (LRFR).
- O. Bayrak, «Shear-Friction Design Provisions of the AASHTO LRFD Bridge Design Specifications», ASPIRE, inverno de 2025 (coeficientes c e μ do §5.7.4.4).
- EN 1990:2002 + A1:2005 Anexo A2 (combinações para pontes); EN 1991-2:2003 §4.2.3, §4.3.2, §4.3.3, Anexo A e §6.4.5.2; EN 1998-2:2005 §4.1, §6.2.1 e Anexo E.
- IAP-11, Instrução sobre as ações a considerar no projeto de pontes rodoviárias (Ministerio de Fomento, Espanha, 2011), Cap. 4.
- Teorema de Barré; H. Müller-Breslau (1886); equação dos três momentos de Clapeyron; J. Courbon (repartição transversal).
- M. J. N. Priestley, F. Seible e G. M. Calvi, *Seismic Design and Retrofit of Bridges* (1996); M. J. N. Priestley, G. M. Calvi e M. J. Kowalsky, *Displacement-Based Seismic Design of Structures* (2007).
- Y.-J. Park e A. H.-S. Ang, «Mechanistic seismic damage model for reinforced concrete», J. Struct. Eng. 111(4) (1985). T. T. Baber e M. N. Noori, «Random vibration of degrading, pinching systems», J. Eng. Mech. 111(8) (1985). Y.-K. Wen, «Method for random vibration of hysteretic systems», J. Eng. Mech. Div. 102 (1976).
- J. W. Baker, «Efficient analytical fragility function fitting using dynamic structural analysis», Earthquake Spectra 31(1) (2015). FEMA, HAZUS-MH Technical Manual. K. Kawashima et al., «Damage of bridges due to the 2010 Maule, Chile, earthquake», J. Earthquake Eng. 15(7) (2011).
- Mononobe-Okabe; S. Okabe (1926), N. Mononobe e H. Matsuo (1929); H. B. Seed e R. V. Whitman (1970) para o ponto de aplicação do incremento sísmico.

## Licença

MIT. Consulte [LICENSE](LICENSE).

---

Parte do **Loadpath**, a coleção de bibliotecas estruturais de código aberto de [Jesús Murgas](https://github.com/jmurgass99).
