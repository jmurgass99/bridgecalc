"""Golden tests de cargas de puentes anclados a fichas del master
(``_EXTRACCION_DOCUMENTOS/fichas``).

Fuente principal: **W01630 — IAP-11** (Instruccion sobre las acciones a
considerar en el proyecto de puentes de carretera, RD 1359/2011), Cap. 4
"Acciones variables - Trafico". El Modelo de Carga 1 (MC1) de IAP-11 es la
adaptacion espanola literal del Load Model 1 (LM1) de EN 1991-2:2003 Tabla
4.2 -- mismos valores caracteristicos (300/200/100 kN por carril, 9.0/2.5/2.5
kN/m2, carril virtual de 3.0 m) -- por lo que ancla igualmente
``bridgejm.loads.eurocode_lm1``. El Modelo de Carga 2 (MC2) de IAP-11 == LM2
de EN 1991-2 Sec 4.3.3 (eje aislado de 400 kN).

Fuente secundaria: **W00736 — Puente Viga-Losa.xlsx** (evaluacion real de un
puente viga-losa AASHTO LRFD / HL-93), para el factor de impacto IM.

REGLA DE ORO de esta campana: no fiarse de los numeros impresos en las
fichas. Cada oraculo de este fichero se recalcula a mano (formulas de
mecanica de vigas cerradas, sin reimportar ni llamar a las funciones de
``bridgejm`` para generar el propio oraculo) antes de anclarlo contra el
resultado de la funcion de produccion.

Un tren de cargas del propio modulo tiene un error de formula descubierto
durante esta auditoria (``evaluate_eurocode_lm1`` / termino M_TS, tandem) --
ver docstring de ``TestErrataDocumentadaNoAnclada`` mas abajo. Por esa razon
NINGUN golden de este fichero ancla ``M_TS_kNm`` / ``M_total_kNm`` /
``V_TS_kN`` / ``V_total_kN``; solo se anclan los componentes UDL (formula
cerrada w*L^2/8, w*L/2, verificada correcta) y LM2 (eje unico, M=Q*L/4,
V=Q, verificada correcta).
"""
import pytest

from bridgejm.loads.eurocode_lm1 import (
    EurocodeLM1Input,
    EurocodeLM2Input,
    evaluate_eurocode_lm1,
    evaluate_eurocode_lm2,
    LM1_TS_AXLE_kN_PER_LANE,
    LM1_UDL_kN_per_m2_PER_LANE,
    LM1_NOTIONAL_LANE_WIDTH_m,
    LM2_AXLE_LOAD_kN,
    LM2_WHEEL_LOAD_kN,
    LM2_WHEEL_CONTACT_m,
    LM2_WHEEL_SPACING_m,
)
from bridgejm.loads.hl93 import HL93Configuration


class TestIAP11LM1CargasCaracteristicas:
    """Ancla W01630 (IAP-11 Cap.4, Tabla 4.2 / EN 1991-2:2003 Tabla 4.2).

    Ficha W01630, seccion "Modelos de carga de trafico (Cap.4)":
      Carril 1 (mas cargado): Q1k=300 kN (eje tandem 2x150kN) + q1k=9.0 kN/m2
      Carril 2: Q2k=200 kN + q2k=2.5 kN/m2
      Carril virtual: 3.0 m
    """

    def test_axle_loads_carril1_carril2_ancla_ficha(self):
        # Oraculo: valores citados literalmente en la ficha W01630 (Tabla
        # 4.2 IAP-11 / EN1991-2), transcritos a mano, no derivados del
        # modulo.
        assert LM1_TS_AXLE_kN_PER_LANE[0] == pytest.approx(300.0)
        assert LM1_TS_AXLE_kN_PER_LANE[1] == pytest.approx(200.0)
        assert LM1_TS_AXLE_kN_PER_LANE[2] == pytest.approx(100.0)

    def test_udl_carril1_carril2_ancla_ficha(self):
        assert LM1_UDL_kN_per_m2_PER_LANE[0] == pytest.approx(9.0)
        assert LM1_UDL_kN_per_m2_PER_LANE[1] == pytest.approx(2.5)
        assert LM1_NOTIONAL_LANE_WIDTH_m == pytest.approx(3.0)

    def test_total_TS_load_2carriles_ancla_ficha(self):
        """Suma de cargas de tandem (2 ejes x 2 carriles), IAP-11 W01630.

        Oraculo a mano: 2*300 (carril1) + 2*200 (carril2) = 1000 kN.
        Es una suma directa (sin geometria de posicionamiento), por lo que
        no esta afectada por el error de formula de M_TS documentado en
        ``TestErrataDocumentadaNoAnclada``.
        """
        oraculo_kN = 2.0 * 300.0 + 2.0 * 200.0
        assert oraculo_kN == pytest.approx(1000.0)

        r = evaluate_eurocode_lm1(EurocodeLM1Input(
            carriageway_width_m=7.0, span_m=30.0, n_lanes=2,
        ))
        assert r.total_TS_load_kN == pytest.approx(oraculo_kN)


class TestIAP11LM1UDLMomentoCortante:
    """Ancla M_UDL / V_UDL de LM1 (IAP-11 MC1) — viga simple, W01630.

    Puente 2 carriles, vano L=30 m, ancho >= 7 m (2 carriles virtuales de
    3.0 m, IAP-11 Cap.4). Oraculo independiente por formula cerrada de
    viga simplemente apoyada bajo carga uniforme:
        M_max = w*L^2/8 (centro de vano)   V_max = w*L/2 (apoyo)
    aplicada carril a carril con los valores caracteristicos de W01630
    (q1k=9.0 kN/m2, q2k=2.5 kN/m2, carril virtual b=3.0 m => w1=27.0 kN/m,
    w2=7.5 kN/m).
    """

    L = 30.0
    W1_kN_m = 9.0 * 3.0   # 27.0
    W2_kN_m = 2.5 * 3.0   # 7.5

    def test_M_UDL_2carriles_L30m_ancla_ficha(self):
        M1 = self.W1_kN_m * self.L ** 2 / 8.0
        M2 = self.W2_kN_m * self.L ** 2 / 8.0
        oraculo_kNm = M1 + M2
        assert oraculo_kNm == pytest.approx(3881.25)

        r = evaluate_eurocode_lm1(EurocodeLM1Input(
            carriageway_width_m=7.0, span_m=self.L, n_lanes=2,
        ))
        assert r.M_UDL_kNm == pytest.approx(oraculo_kNm, rel=1e-9)

    def test_V_UDL_2carriles_L30m_ancla_ficha(self):
        V1 = self.W1_kN_m * self.L / 2.0
        V2 = self.W2_kN_m * self.L / 2.0
        oraculo_kN = V1 + V2
        assert oraculo_kN == pytest.approx(517.5)

        r = evaluate_eurocode_lm1(EurocodeLM1Input(
            carriageway_width_m=7.0, span_m=self.L, n_lanes=2,
        ))
        assert r.V_UDL_kN == pytest.approx(oraculo_kN, rel=1e-9)

    def test_total_UDL_load_per_m_ancla_ficha(self):
        oraculo = self.W1_kN_m + self.W2_kN_m
        assert oraculo == pytest.approx(34.5)
        r = evaluate_eurocode_lm1(EurocodeLM1Input(
            carriageway_width_m=7.0, span_m=self.L, n_lanes=2,
        ))
        assert r.total_UDL_load_kN_per_m == pytest.approx(oraculo)


class TestIAP11LM2EjeUnico:
    """Ancla LM2 / MC2 (W01630): "Eje unico de 400 kN (2x200kN separados
    2.0m). Area de contacto de rueda: 0.35m x 0.60m".

    Oraculo independiente para viga simple con el eje aislado en el punto
    critico (centro de vano para M, apoyo para V):
        M_max = Q*L/4      V_max = Q
    Vano de aplicacion L=24 m (dato de ingenieria, la ficha no fija un
    vano para MC2; la magnitud de carga 400 kN si esta anclada a la
    ficha).
    """

    def test_axle_and_wheel_config_ancla_ficha(self):
        assert LM2_AXLE_LOAD_kN == pytest.approx(400.0)
        assert LM2_WHEEL_LOAD_kN == pytest.approx(200.0)
        assert LM2_WHEEL_CONTACT_m == pytest.approx((0.35, 0.60))
        assert LM2_WHEEL_SPACING_m == pytest.approx(2.0)
        # Consistencia interna citada en la ficha: eje = 2 ruedas.
        assert LM2_AXLE_LOAD_kN == pytest.approx(2.0 * LM2_WHEEL_LOAD_kN)

    def test_M_max_V_max_L24m_ancla_ficha(self):
        Q = 400.0
        L = 24.0
        M_oraculo = Q * L / 4.0   # 2400.0
        V_oraculo = Q             # 400.0
        assert M_oraculo == pytest.approx(2400.0)

        r = evaluate_eurocode_lm2(EurocodeLM2Input(span_m=L))
        assert r.M_max_kNm == pytest.approx(M_oraculo, rel=1e-9)
        assert r.V_max_kN == pytest.approx(V_oraculo, rel=1e-9)


class TestHL93FactorImpactoFichaW00736:
    """Ancla IM (factor de impacto) HL-93 a la evaluacion real de puente
    W00736 (Puente Viga-Losa.xlsx, hoja "BARET SERVICIO"):
        "Coeficiente de impacto IM=0,33 (estados servicio y resistencia)"

    AASHTO LRFD 3.6.2.1: factor de mayoracion dinamica = 1 + IM/100.
    """

    def test_impact_factor_default_coincide_con_evaluacion_real(self):
        IM_ficha = 0.33
        oraculo = 1.0 + IM_ficha
        assert oraculo == pytest.approx(1.33)
        cfg = HL93Configuration(span_m=30.0)
        assert cfg.impact_factor == pytest.approx(oraculo)


class TestBugM_TS_CorregidoYAnclado:
    """BUG DE PRODUCCION real, corregido por el controlador (no por el agente
    que detecto y documento este hallazgo -- ver commit de correccion).

    ``bridgejm/loads/eurocode_lm1.py`` calculaba el momento del tandem
    tratando los DOS ejes como si fueran una unica carga puntual equivalente
    2*Q_eff aplicada en la posicion del primer eje, usando la formula de viga
    simple para UNA carga puntual M(a) = P*a*(L-a)/L. Para L=30, spacing=1.2,
    Q_eff=1 daba 14.976 -- por ENCIMA del maximo fisico exacto alcanzable con
    esas dos cargas (14.406, teorema de la equidistancia carga-resultante),
    lo que confirmaba un error de FORMULA, no solo de posicion barrida.

    Corregido a la forma cerrada exacta:
        M_TS_lane = Q_eff * (2*L - spacing)**2 / (8*L)
                  = Q_eff * ((L-spacing)/2 + spacing**2/(8*L))
    Este test ancla el valor CORRECTO llamando a la funcion real (ya no es
    solo aritmetica aislada, como en el borrador original del hallazgo).
    """

    def test_M_TS_matches_the_exact_equidistant_theorem_value(self):
        from bridgejm.loads.eurocode_lm1 import (
            LM1_TS_AXLE_kN_PER_LANE,
            EurocodeLM1Input,
            evaluate_eurocode_lm1,
        )

        L, spacing = 30.0, 1.2
        formula_exacta_por_kN = (2.0 * L - spacing) ** 2 / (8.0 * L)
        assert formula_exacta_por_kN == pytest.approx(14.406, rel=1e-4)

        res = evaluate_eurocode_lm1(EurocodeLM1Input(
            span_m=L, carriageway_width_m=3.0, n_lanes=1,
            alpha_Q1=1.0, alpha_Qr=1.0,
        ))
        Q_carril1 = LM1_TS_AXLE_kN_PER_LANE[0]      # 300 kN
        M_TS_esperado = Q_carril1 * formula_exacta_por_kN
        assert res.M_TS_kNm == pytest.approx(M_TS_esperado, rel=1e-9)

        # y ya NO supera el maximo fisico (antes del fix, si lo hacia)
        assert res.M_TS_kNm <= M_TS_esperado + 1e-6
