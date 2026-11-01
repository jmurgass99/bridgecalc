"""Tests del generador de emparrillado de puente (idea #12 + Tarea 2 Argos).

Verifica:
1. Conteos derivados matematicamente de la especificacion (n_spans, n_girders, n_diaphragms).
2. Esquema de apoyos cinematica y estaticamente estable en 3D (6 GDL globales:
   Fx, Fy, Fz, Mx, My, Mz) con libre dilatacion longitudinal en el estribo movil.
3. Verificacion estricta de codigos de retorno OAPI (ret != 0 lanza OAPICallError).
4. Conexion desde Encargo ejecutable -> BridgeDesignSpec -> materiales y secciones
   reales verificadas de catalogo con propiedades mecanicas completas (> 0).
5. Cargas de puente reales (DEAD, DW, carril + tren de cargas HL-93 / LM1 en
   posiciones pesimas de M+ y Vmax), combinaciones normativas y declaracion
   explicita de limitaciones del modelo y estados limite no implementados.
"""
import pytest as _pytest_skip
_pytest_skip.importorskip("fastsap")  # dependencia externa opcional: sin ella estos tests se omiten
import pytest

from bridgecalc.integration.grillage_model import (
    build_bridge_grillage,
    generate_grillage,
    grillage_model,
)


def test_conteos_del_grid_2vanos():
    g = generate_grillage(n_spans=2, span_length=20.0, n_girders=4,
                          girder_spacing=2.5, divisions_per_span=4)
    # n_x = n_spans*div+1 = 9 lineas transversales; joints = 9*4
    assert len(g["joints"]) == 36
    # longitudinales = (n_x-1)*n_girders = 8*4 = 32 ; transversales = n_x*(n_g-1) = 9*3 = 27
    assert sum(1 for f in g["frames"] if f["id"].startswith("L")) == 32
    assert sum(1 for f in g["frames"] if f["id"].startswith("T")) == 27
    assert len(g["frames"]) == 59


def test_apoyos_en_lineas_de_pila():
    g = generate_grillage(n_spans=2, span_length=20.0, n_girders=4, divisions_per_span=4)
    apoyados = [j for j in g["joints"] if j["restraint"] is not None]
    # apoyos en x = 0, 20, 40 -> 3 lineas * 4 vigas = 12
    assert len(apoyados) == 12
    # Todos los apoyos restringen Uz=True y liberan giros Rx=Ry=Rz=False
    assert all(
        j["restraint"][2] is True and j["restraint"][3:] == [False, False, False]
        for j in apoyados
    )
    # Estribo fijo (x=0): Ux=True; pilas/estribo movil (x>0): Ux=False
    fijos_x0 = [j for j in apoyados if j["x"] == pytest.approx(0.0)]
    moviles = [j for j in apoyados if j["x"] > 0.0]
    assert all(j["restraint"][0] is True for j in fijos_x0)
    assert all(j["restraint"][0] is False for j in moviles)


def test_geometria_coords():
    g = generate_grillage(n_spans=1, span_length=24.0, n_girders=3,
                          girder_spacing=3.0, divisions_per_span=6)
    # viga del medio (ig=1) en y=3.0; extremo en x=24
    assert any(j["x"] == 24.0 and j["y"] == 3.0 for j in g["joints"])


def test_carga_carril_hl93_en_meta():
    g = generate_grillage(n_spans=1, span_length=20.0, n_girders=4)
    assert g["meta"]["lane_load_kN_m"] > 0  # carga de carril HL-93 (9.3 kN/m)
    assert g["meta"]["n_spans"] == 1


def test_salida_valida_como_structural_job_input():
    from fastsap.worker_sap2000 import StructuralJobInput
    g = generate_grillage(n_spans=1, span_length=20.0, n_girders=3, divisions_per_span=4)
    job = StructuralJobInput(joints=g["joints"], frames=g["frames"])
    assert len(job.joints) == len(g["joints"])


# --------------------------------------------------------------------------- #
# grillage_model(L, W, n_girders, n_diaphragms) — firma de la idea #12
# --------------------------------------------------------------------------- #
def test_grillage_model_conteos_y_ancho():
    # L=30, W=10, 4 vigas, 3 diafragmas interiores.
    g = grillage_model(L=30.0, W=10.0, n_girders=4, n_diaphragms=3)
    # divisions_per_span = n_diaphragms+1 = 4 -> n_x = 5 lineas transversales.
    # joints = 5 * 4 = 20
    assert len(g["joints"]) == 20
    # longitudinales = (n_x-1)*n_girders = 4*4 = 16
    assert sum(1 for f in g["frames"] if f["id"].startswith("L")) == 16
    # transversales = n_x*(n_girders-1) = 5*3 = 15
    assert sum(1 for f in g["frames"] if f["id"].startswith("T")) == 15
    # ancho total 10 m sobre 4 vigas -> separacion 10/3
    assert g["meta"]["girder_spacing"] == pytest.approx(10.0 / 3.0)
    # la viga de borde cae en y = W
    assert any(j["y"] == pytest.approx(10.0) for j in g["joints"])


def test_grillage_model_coords_extremos():
    g = grillage_model(L=30.0, W=12.0, n_girders=3, n_diaphragms=2)
    # extremo en x=30 sobre la viga central (y=6)
    assert any(j["x"] == pytest.approx(30.0) and j["y"] == pytest.approx(6.0)
               for j in g["joints"])
    # apoyos solo en x=0 y x=30 -> 2 lineas * 3 vigas = 6
    apoyados = [j for j in g["joints"] if j["restraint"] is not None]
    assert len(apoyados) == 6


def test_grillage_model_validaciones():
    with pytest.raises(ValueError):
        grillage_model(L=30.0, W=0.0, n_girders=4, n_diaphragms=3)
    with pytest.raises(ValueError):
        grillage_model(L=30.0, W=10.0, n_girders=1, n_diaphragms=3)


# --------------------------------------------------------------------------- #
# build_bridge_grillage — OAPI (mock/contract, sin CSiBridge vivo)
# --------------------------------------------------------------------------- #
class _RecordingSapModel:
    """Mock de contrato de SapModel: registra las llamadas OAPI y devuelve ret=0."""
    def __init__(self, fail_on: str | None = None):
        self.fail_on = fail_on
        self.materials = []
        self.isotropic = []
        self.weights = []
        self.i_sections = []
        self.rect_sections = []
        self.points = []
        self.restraints = []
        self.frames = []
        self.load_patterns = []
        self.dist_loads = []
        self.point_loads = []
        self.frame_point_loads = []
        self.combos = []
        self.combo_cases = []

        builder = self

        def _ret(op_name: str) -> int:
            return 1 if builder.fail_on == op_name else 0

        class _PropMaterial:
            def SetMaterial(self, name, mat_type):
                builder.materials.append((name, mat_type))
                return _ret("SetMaterial")

            def SetMPIsotropic(self, name, e, nu, alpha):
                builder.isotropic.append((name, e, nu, alpha))
                return _ret("SetMPIsotropic")

            def SetWeightAndMass(self, name, opt, val):
                builder.weights.append((name, opt, val))
                return _ret("SetWeightAndMass")

        class _PropFrame:
            def SetISection(self, name, mat, t3, t2, tf, tw, t2b, tfb):
                builder.i_sections.append((name, mat, t3, t2, tf, tw, t2b, tfb))
                return _ret("SetISection")

            def SetRectangle(self, name, mat, t3, t2):
                builder.rect_sections.append((name, mat, t3, t2))
                return _ret("SetRectangle")

        class _PointObj:
            def AddCartesian(self, x, y, z, name, uname):
                builder.points.append((x, y, z, name, uname))
                return (_ret("AddCartesian"), uname)

            def SetRestraint(self, name, vals):
                builder.restraints.append((name, list(vals)))
                return _ret("SetRestraint")

            def SetLoadForce(self, name, pat, vals, replace=False, csys="Global", item_type=0):
                builder.point_loads.append((name, pat, list(vals)))
                return _ret("SetLoadForce")

        class _FrameObj:
            def AddByPoint(self, ji, jj, prop, section, name):
                builder.frames.append((ji, jj, section, name))
                return (_ret("AddByPoint"), name)

            def SetLoadDistributed(self, name, pat, my_type, dir_, dist1, dist2, val1, val2, csys="Global", rel=True, replace=True, item_type=0):
                builder.dist_loads.append((name, pat, my_type, dir_, dist1, dist2, val1, val2))
                return _ret("SetLoadDistributed")

            def SetLoadPoint(self, name, pat, my_type, dir_, dist, val, csys="Global", rel=False, replace=False, item_type=0):
                builder.frame_point_loads.append((name, pat, my_type, dir_, dist, val, csys, rel, replace))
                return _ret("SetLoadPoint")

        class _LoadPatterns:
            def Add(self, name, my_type, sw_mult=0.0, add_case=True):
                builder.load_patterns.append((name, my_type, sw_mult, add_case))
                return _ret("LoadPatterns.Add")

        class _RespCombo:
            def Add(self, name, combo_type):
                builder.combos.append((name, combo_type))
                return _ret("RespCombo.Add")

            def SetCaseList(self, name, cname_type, cname, sf):
                builder.combo_cases.append((name, cname_type, cname, sf))
                return _ret("RespCombo.SetCaseList")

        self.PropMaterial = _PropMaterial()
        self.PropFrame = _PropFrame()
        self.PointObj = _PointObj()
        self.FrameObj = _FrameObj()
        self.LoadPatterns = _LoadPatterns()
        self.RespCombo = _RespCombo()


class _ClientWrapper:
    def __init__(self, sap_model):
        self.SapModel = sap_model


def test_build_preview_no_toca_modelo():
    summary = build_bridge_grillage(None, L=30.0, W=10.0, n_girders=4,
                                    n_diaphragms=3, preview_only=True)
    assert summary["n_joints"] == 20
    assert summary["n_frames_long"] == 16
    assert summary["n_frames_trans"] == 15
    assert summary["n_supports"] == 8  # 2 lineas de apoyo * 4 vigas


def test_build_llama_ops_oapi_con_mock():
    sap = _RecordingSapModel()
    summary = build_bridge_grillage(_ClientWrapper(sap), L=30.0, W=10.0,
                                    n_girders=4, n_diaphragms=3)
    # un AddCartesian por nodo
    assert len(sap.points) == summary["n_joints"] == 20
    # un AddByPoint por barra (16 long + 15 trans)
    assert len(sap.frames) == summary["n_frames"] == 31
    # SetRestraint solo en los nodos de apoyo
    assert len(sap.restraints) == summary["n_supports"] == 8
    # Material y secciones reales definidas previamente en SapModel (no "GIRDER"/"DIAPHRAGM" huerfanos)
    assert len(sap.materials) >= 1
    assert len(sap.i_sections) + len(sap.rect_sections) >= 2
    secciones_definidas = {s[0] for s in sap.i_sections} | {s[0] for s in sap.rect_sections}
    secciones_asignadas = {f[2] for f in sap.frames}
    assert secciones_asignadas.issubset(secciones_definidas)
    assert "GIRDER" not in secciones_asignadas
    assert "DIAPHRAGM" not in secciones_asignadas


def test_build_acepta_sapmodel_directo():
    sap = _RecordingSapModel()
    # pasar el SapModel directamente (sin wrapper) tambien funciona
    build_bridge_grillage(sap, L=20.0, W=8.0, n_girders=3, n_diaphragms=1)
    # div = n_diaphragms+1 = 2 -> n_x=3; joints=3*3=9
    assert len(sap.points) == 9


# --------------------------------------------------------------------------- #
# TAREA 2 — Tests de verificacion estricta OAPI, recuentos derivados,
# estabilidad cinematica 3D, conexion Encargo->BridgeDesignSpec y cargas reales
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "fail_op",
    [
        "SetMaterial",
        "SetMPIsotropic",
        "SetWeightAndMass",
        "SetISection",
        "AddCartesian",
        "SetRestraint",
        "AddByPoint",
        "LoadPatterns.Add",
        "SetLoadDistributed",
        "SetLoadPoint",
        "RespCombo.Add",
        "RespCombo.SetCaseList",
    ],
)
def test_oapi_ret_nonzero_lanza_excepcion(fail_op: str):
    from bridgecalc.integration.grillage_model import OAPICallError

    sap = _RecordingSapModel(fail_on=fail_op)
    with pytest.raises(OAPICallError, match=fail_op):
        build_bridge_grillage(sap, L=30.0, W=10.0, n_girders=4, n_diaphragms=3)


@pytest.mark.parametrize(
    "n_spans,n_girders,n_diaphragms,exp_joints,exp_long,exp_trans,exp_supports",
    [
        (1, 4, 3, 20, 16, 15, 8),
        (1, 5, 4, 30, 25, 24, 10),
        (2, 3, 2, 21, 18, 14, 9),
        (3, 6, 2, 60, 54, 50, 24),
    ],
)
def test_recuentos_derivados_de_especificacion_parametrica(
    n_spans, n_girders, n_diaphragms, exp_joints, exp_long, exp_trans, exp_supports
):
    from bridgecalc.integration.grillage_model import expected_grillage_counts

    counts = expected_grillage_counts(
        n_spans=n_spans, n_girders=n_girders, n_diaphragms=n_diaphragms
    )
    assert counts["n_joints"] == exp_joints
    assert counts["n_frames_long"] == exp_long
    assert counts["n_frames_trans"] == exp_trans
    assert counts["n_frames"] == exp_long + exp_trans
    assert counts["n_supports"] == exp_supports

    sap = _RecordingSapModel()
    summary = build_bridge_grillage(
        sap, L=25.0, W=11.0,
        n_spans=n_spans, n_girders=n_girders, n_diaphragms=n_diaphragms,
    )
    assert summary["n_joints"] == exp_joints == len(sap.points)
    assert summary["n_frames_long"] == exp_long
    assert summary["n_frames_trans"] == exp_trans
    assert summary["n_frames"] == exp_long + exp_trans == len(sap.frames)
    assert summary["n_supports"] == exp_supports == len(sap.restraints)


def test_estabilidad_cinematica_3d_apoyos_y_dilatacion_libre():
    from bridgecalc.integration.grillage_model import verify_kinematic_stability

    g = grillage_model(L=30.0, W=10.0, n_girders=4, n_diaphragms=3)
    report = verify_kinematic_stability(g["joints"])
    assert report["stable_3d"] is True
    assert report["global_dofs"] == {
        "sum_Fx": True,
        "sum_Fy": True,
        "sum_Fz": True,
        "sum_Mx": True,
        "sum_My": True,
        "sum_Mz": True,
    }
    assert report["longitudinal_expansion_free_at_movable"] is True
    assert report["transverse_expansion_free_on_non_guide"] is True

    # Verificar que si se bloquea Ux en x=L (hiperestatico longitudinal espurio), falla la validacion
    corrupt_locked = [
        {**j, "restraint": [True, True, True, False, False, False] if j["restraint"] else None}
        for j in g["joints"]
    ]
    with pytest.raises(ValueError, match="coacci[oó]n longitudinal|dilataci[oó]n"):
        verify_kinematic_stability(corrupt_locked)

    # Verificar que si se elimina Uy en x=L (inestable al giro en planta Mz), falla la validacion
    corrupt_unstable_mz = [
        {
            **j,
            "restraint": [False, False, True, False, False, False]
            if (j["restraint"] and j["x"] > 0)
            else j["restraint"],
        }
        for j in g["joints"]
    ]
    with pytest.raises(ValueError, match="sum_Mz|planta"):
        verify_kinematic_stability(corrupt_unstable_mz)


def test_encargo_puente_30m_genera_especificacion_material_secciones_cargas_y_limitaciones():
    from jmworkbench.encargo import interpretar_encargo
    from bridgecalc.integration.grillage_model import (
        bridge_spec_from_encargo,
        build_bridge_grillage,
    )

    orden = (
        "Diseña un puente de 30 m de luz que cumpla la normativa aplicable. "
        "Selecciona una tipología estructural adecuada, define la geometría, "
        "predimensiona y selecciona las secciones, establece materiales, apoyos, "
        "cargas y combinaciones, genera el modelo en SAP2000, ejecuta el análisis, "
        "verifica los estados límite, corrige las secciones si es necesario y "
        "entrega el modelo en SAP2000 con sus resultados y sus planos en AutoCAD."
    )
    supuestos = {
        "norma": "EN 1991-2",
        "uso": "carretera",
        "ancho_tablero_o_carriles": "ancho de tablero 10 m",
        "material": "acero",
        "apoyos": "simplemente apoyado",
        "galibo": "gálibo de 5,5 m",
        "acciones": "LM1",
    }
    enc = interpretar_encargo(orden, supuestos=supuestos)
    assert enc.ejecutable is True

    spec = bridge_spec_from_encargo(enc)
    assert spec.span_m == pytest.approx(30.0)
    assert spec.width_m == pytest.approx(10.0)
    assert spec.n_girders == 4
    assert spec.n_diaphragms == 3

    # Material trazable con propiedades completas > 0
    mat = spec.material
    assert mat.E_kPa > 0
    assert mat.nu > 0
    assert mat.gamma_kN_m3 > 0
    assert mat.fy_MPa > 0

    # Secciones reales de catalogo con todas las propiedades mecanicas > 0
    for sec in (spec.girder_section, spec.diaphragm_section):
        assert sec.name not in ("GIRDER", "DIAPHRAGM")
        assert sec.h_m > 0 and sec.b_m > 0 and sec.tf_m > 0 and sec.tw_m > 0
        assert sec.A_m2 > 0
        assert sec.I33_m4 > 0
        assert sec.I22_m4 > 0
        assert sec.J_m4 > 0
        assert sec.Av2_m2 > 0
        assert sec.Av3_m2 > 0
        assert sec.Wel33_m3 > 0
        assert sec.Wpl33_m3 > 0

    sap = _RecordingSapModel()
    summary = build_bridge_grillage(sap, spec=spec)

    # Cargas de puente aplicadas (DEAD, DW, LIVE_LANE, LIVE_VEHICLE_M, LIVE_VEHICLE_V)
    pats = {p[0] for p in sap.load_patterns}
    assert {"DEAD", "DW", "LIVE_LANE", "LIVE_VEHICLE_M", "LIVE_VEHICLE_V"}.issubset(pats)
    assert len(sap.dist_loads) > 0
    assert len(sap.frame_point_loads) > 0
    # Todas las cargas verticales gravitatorias usan Dir=10 (Gravity, -Z global con valor > 0)
    assert all(dl[3] == 10 and dl[6] > 0 for dl in sap.dist_loads)
    assert all(pl[3] == 10 and pl[5] > 0 for pl in sap.frame_point_loads)

    # Combinaciones ELU y ELS creadas
    combos = {c[0] for c in sap.combos}
    assert len(combos) >= 2

    # Honestidad de limitaciones y estados limite no implementados en meta
    meta = summary["meta"]
    assert len(meta["limitaciones_modelo"]) >= 2
    assert len(meta["estados_limite_aplicables"]) >= 5
    assert len(meta["comprobaciones_no_implementadas"]) >= 4


def test_encargo_puente_30m_aashto_hl93():
    from jmworkbench.encargo import interpretar_encargo
    from bridgecalc.integration.grillage_model import (
        bridge_spec_from_encargo,
        build_bridge_grillage,
    )

    enc = interpretar_encargo(
        "Diseña un puente vehicular de 30 m de luz con ancho de tablero 10 m en acero, "
        "simplemente apoyado, con gálibo de 5 m y tren de cargas HL-93 según AASHTO LRFD."
    )
    assert enc.ejecutable is True
    spec = bridge_spec_from_encargo(enc)
    assert "AASHTO" in spec.norma.upper()
    sap = _RecordingSapModel()
    summary = build_bridge_grillage(sap, spec=spec)
    assert summary["meta"]["loads_summary"]["traffic_code"] == "AASHTO_LRFD_HL93"
    assert summary["meta"]["loads_summary"]["impact_factor_IM"] == pytest.approx(1.33)
    combos = {c[0] for c in sap.combos}
    assert "ULS_STRENGTH_I" in combos
    assert "SLS_SERVICE_II" in combos


# --------------------------------------------------------------------------- #
# Correcciones previas Tarea 3 (Autorizacion Condicionada):
# 1. Carriles nocionales LM1 EN 1991-2 Tabla 4.1 (3 carriles de 3 m + 1 m rem).
# 2. Distribucion transversal excentrica (Courbon) hacia la viga exterior.
# 3. Cargas puntuales en barras (SetLoadPoint) proximas al apoyo sin condensar
#    sobre el nudo coaccionado N0_*.
# --------------------------------------------------------------------------- #
def test_lm1_10m_tres_carriles_nocionales_y_area_remanente():
    from jmworkbench.encargo import interpretar_encargo
    from bridgecalc.integration.grillage_model import (
        bridge_spec_from_encargo,
        build_bridge_grillage,
        notional_lanes_en1991_2,
    )

    nl = notional_lanes_en1991_2(10.0)
    assert nl["n_notional_lanes"] == 3
    assert nl["notional_lane_width_m"] == pytest.approx(3.0)
    assert nl["remaining_width_m"] == pytest.approx(1.0)

    enc = interpretar_encargo(
        "Diseña un puente de 30 m de luz que cumpla la normativa aplicable.",
        supuestos={
            "norma": "EN 1991-2",
            "uso": "carretera",
            "ancho_tablero_o_carriles": "ancho de tablero 10 m",
            "material": "acero",
            "apoyos": "simplemente apoyado",
            "galibo": "gálibo de 5,5 m",
            "acciones": "LM1",
        },
    )
    spec = bridge_spec_from_encargo(enc)
    assert spec.n_lanes == 3

    summary = build_bridge_grillage(None, spec=spec, preview_only=True)
    loads = summary["meta"]["loads_summary"]
    detail = loads["notional_lanes_detail"]
    assert detail["n_notional_lanes"] == 3
    assert detail["notional_lane_width_m"] == pytest.approx(3.0)
    assert detail["remaining_width_m"] == pytest.approx(1.0)
    strips = detail["strips"]
    assert len(strips) == 4  # 3 carriles nocionales + 1 area remanente
    assert [s["strip_id"] for s in strips] == ["LANE_1", "LANE_2", "LANE_3", "REMAINING_AREA"]
    # Suma de UDL = 27.0 + 7.5 + 7.5 + 2.5 = 44.5 kN/m
    assert sum(s["udl_kN_m"] for s in strips) == pytest.approx(44.5)
    # Suma de TS por eje = 300 + 200 + 100 = 600 kN/eje (2 ejes -> 1200 kN total)
    assert loads["vehicle_axles_M_kN"] == [pytest.approx(600.0), pytest.approx(600.0)]


def test_distribucion_transversal_excentrica_courbon():
    from bridgecalc.integration.grillage_model import (
        build_bridge_grillage,
        courbon_transverse_factors,
    )

    y_girders = [0.0, 10.0 / 3.0, 20.0 / 3.0, 10.0]
    for y_load in (1.5, 4.5, 7.5, 9.5):
        etas = courbon_transverse_factors(y_girders, y_load)
        # Conservacion de fuerza vertical y de momento respecto a y=0
        assert sum(etas) == pytest.approx(1.0)
        assert sum(e * y for e, y in zip(etas, y_girders)) == pytest.approx(y_load)

    summary = build_bridge_grillage(
        None, L=30.0, W=10.0, n_girders=4, n_diaphragms=3, preview_only=True
    )
    td = summary["meta"]["loads_summary"]["transverse_distribution"]
    q_by_g = td["q_lane_by_girder_kN_m"]
    sh_by_g = td["vehicle_axle_share_by_girder"]
    # La viga exterior ig=0 recibe estrictamente mas carga que las interiores y opuesta
    assert q_by_g[0] > q_by_g[1] > q_by_g[2] > q_by_g[3]
    assert sh_by_g[0] > sh_by_g[1] > sh_by_g[2] > sh_by_g[3]
    assert sum(sh_by_g.values()) == pytest.approx(1.0)


def test_cargas_puntuales_en_barras_proximas_al_apoyo_sin_condensacion_nodal():
    from jmworkbench.encargo import interpretar_encargo
    from bridgecalc.integration.grillage_model import (
        bridge_spec_from_encargo,
        build_bridge_grillage,
    )

    enc = interpretar_encargo(
        "Diseña un puente de 30 m de luz.",
        supuestos={
            "norma": "EN 1991-2",
            "uso": "carretera",
            "ancho_tablero_o_carriles": "ancho de tablero 10 m",
            "material": "acero",
            "apoyos": "simplemente apoyado",
            "galibo": "gálibo de 5,5 m",
            "acciones": "LM1",
        },
    )
    spec = bridge_spec_from_encargo(enc)
    sap = _RecordingSapModel()
    summary = build_bridge_grillage(sap, spec=spec)
    loads = summary["meta"]["loads_summary"]

    # Ninguna carga puntual se condensa mediante PointObj.SetLoadForce sobre nudos de apoyo
    assert len(sap.point_loads) == 0
    # Se aplican 2 ejes * 4 vigas = 8 cargas puntuales en barra para M y 8 para V
    pts_M = [p for p in sap.frame_point_loads if p[1] == "LIVE_VEHICLE_M"]
    pts_V = [p for p in sap.frame_point_loads if p[1] == "LIVE_VEHICLE_V"]
    assert len(pts_M) == 8
    assert len(pts_V) == 8
    # En LIVE_VEHICLE_V los dos ejes caen dentro del primer tramo L0_* con distancia local > 0
    # (primer eje en x = 0.05 m > 0, segundo en x = 1.25 m) y Replace=False para acumular ambos ejes
    assert all(p[0].startswith("L0_") for p in pts_V)
    assert all(p[4] > 0.0 for p in pts_V)
    assert all(p[8] is False for p in pts_V)  # Replace=False
    assert sum(p[5] for p in pts_V) == pytest.approx(sum(loads["vehicle_axles_V_kN"]))
    assert sum(p[5] for p in pts_M) == pytest.approx(sum(loads["vehicle_axles_M_kN"]))


# --------------------------------------------------------------------------- #
# TAREA 3 — Ciclo de analisis, extraccion concurrente, equilibrio y reapertura
# --------------------------------------------------------------------------- #
def test_compute_expected_vertical_loads_y_equilibrio_analitico():
    from jmworkbench.encargo import interpretar_encargo
    from bridgecalc.integration.grillage_model import (
        bridge_spec_from_encargo,
        build_bridge_grillage,
        compute_expected_vertical_loads_kN,
    )

    enc = interpretar_encargo(
        "Diseña un puente de 30 m de luz.",
        supuestos={
            "norma": "EN 1991-2",
            "uso": "carretera",
            "ancho_tablero_o_carriles": "ancho de tablero 10 m",
            "material": "acero",
            "apoyos": "simplemente apoyado",
            "galibo": "gálibo de 5,5 m",
            "acciones": "LM1",
        },
    )
    spec = bridge_spec_from_encargo(enc)
    summary = build_bridge_grillage(None, spec=spec, preview_only=True)
    fz = compute_expected_vertical_loads_kN(summary["meta"])

    # DEAD = peso propio 4 vigas HEM 1000 (30 m) + 5 lineas diafragma HEB 400 (10 m) + losa 0.25 m
    assert fz["DEAD"] == pytest.approx(
        fz["DEAD_self_weight_girders_kN"] + fz["DEAD_self_weight_diaphragms_kN"] + fz["DEAD_slab_kN"]
    )
    assert fz["DEAD_slab_kN"] == pytest.approx(4 * 30.0 * 15.625)  # 1875.0 kN
    assert fz["DW"] == pytest.approx(4 * 30.0 * 6.25)  # 750.0 kN
    assert fz["LIVE_LANE"] == pytest.approx(44.5 * 30.0)  # 1335.0 kN
    assert fz["LIVE_VEHICLE_M"] == pytest.approx(1200.0)
    assert fz["LIVE_VEHICLE_V"] == pytest.approx(1200.0)
    assert fz["ULS_STR"] == pytest.approx(
        1.35 * (fz["DEAD"] + fz["DW"] + fz["LIVE_LANE"] + fz["LIVE_VEHICLE_M"]), rel=1e-4
    )


@pytest.mark.compat
@pytest.mark.live
def test_bridge_grillage_30m_live_sap2000(tmp_path):
    """Test LIVE real contra SAP2000 v26: construye el emparrillado de 30 m x 10 m,
    guarda .sdb, ejecuta analisis estatico, verifica equilibrio global de reacciones,
    extrae desplazamientos y esfuerzos concurrentes (P, V2, V3, T, M2, M3),
    cierra y reabre el archivo .sdb verificando recuentos y veredicto OK.
    """
    from pathlib import Path
    from jmworkbench.encargo import interpretar_encargo
    from bridgecalc.integration.grillage_model import (
        bridge_spec_from_encargo,
        run_bridge_grillage_sap2000,
    )

    sap_exe = Path(r"C:\Program Files\Computers and Structures\SAP2000 26\SAP2000.exe")
    if not sap_exe.exists():
        pytest.skip(f"SAP2000 v26 no instalado en {sap_exe}")

    enc = interpretar_encargo(
        "Diseña un puente de 30 m de luz que cumpla la normativa aplicable. "
        "Selecciona una tipología estructural adecuada, define la geometría, "
        "predimensiona y selecciona las secciones, establece materiales, apoyos, "
        "cargas y combinaciones, genera el modelo en SAP2000, ejecuta el análisis, "
        "verifica los estados límite, corrige las secciones si es necesario y "
        "entrega el modelo en SAP2000 con sus resultados y sus planos en AutoCAD.",
        supuestos={
            "norma": "EN 1991-2",
            "uso": "carretera",
            "ancho_tablero_o_carriles": "ancho de tablero 10 m",
            "material": "acero",
            "apoyos": "simplemente apoyado",
            "galibo": "gálibo de 5,5 m",
            "acciones": "LM1",
        },
    )
    spec = bridge_spec_from_encargo(enc)
    sdb_file = tmp_path / "puente_30m_emparrillado_live.sdb"

    res = run_bridge_grillage_sap2000(str(sdb_file), spec=spec, visible=False, keep_open=False)

    assert Path(res["sdb_path"]).exists()
    assert res["sdb_size_bytes"] > 1000
    assert res["RunAnalysis_ret"] == 0
    assert res["persistence_verdict"] == {"veredicto": "OK", "motivos": []}
    assert res["counts"]["created"]["n_joints"] == 20
    assert res["counts"]["reopened"]["n_joints"] == 20
    assert res["counts"]["created"]["n_frames"] == 31
    assert res["counts"]["reopened"]["n_frames"] == 31
    assert res["counts"]["reopened"]["n_supports"] == 8

    # Equilibrio global exacto verificado en todos los casos y combinaciones
    for case_name, eq in res["equilibrium_by_case"].items():
        assert eq["equilibrium_ok"] is True, f"Equilibrio fallo en {case_name}: {eq}"
        assert eq["rel_error"] < 1e-4

    # Persistir el .sdb y el reporte JSON de evidencias para inspeccion auditable
    import json
    import shutil
    import tempfile
    artifact_dir = Path(tempfile.gettempdir()) / "bridgecalc_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(res["sdb_path"], artifact_dir / "puente_30m_emparrillado_sap2000_v26.sdb")
    (artifact_dir / "puente_30m_emparrillado_sap2000_v26_report.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # La viga exterior ig=0 recibe mayor momento y cortante que la viga opuesta ig=3 bajo trafico excentrico
    uls = res["summary_by_case"]["ULS_STR"]
    assert uls["girder_peaks_by_index"][0]["M3_max_kNm"] > uls["girder_peaks_by_index"][3]["M3_max_kNm"]
    assert uls["diaphragm_M3_max_kNm"] > 0.0
    assert uls["diaphragm_V2_max_kN"] > 0.0
    assert uls["min_Uz_mm"] < -10.0  # flecha hacia abajo (-Z)

    uls_v = res["summary_by_case"]["ULS_STR_SHEAR"]
    assert uls_v["girder_peaks_by_index"][0]["V2_max_kN"] > uls_v["girder_peaks_by_index"][3]["V2_max_kN"]


# --------------------------------------------------------------------------- #
# TAREA 4 — Verificacion normativa concurrente ULS/SLS y bucle cerrado de
# redimensionamiento con catalogo extendido de vigas armadas PG_*
# --------------------------------------------------------------------------- #
def _make_synthetic_analysis_report(
    *,
    girder_section: str = "HEM 1000",
    diaphragm_section: str = "HEB 400",
    midspan_M3_kNm: float = 11014.12,
    midspan_concurrent_V2_kN: float = 4.19,
    support_V2_kN: float = 1478.68,
    support_concurrent_M3_kNm: float = 0.0,
    diaph_M3_kNm: float = 551.83,
    diaph_V2_kN: float = 365.47,
    live_defl_mm: float = 300.04,
    total_defl_mm: float = 484.84,
    run_ret: int = 0,
    units: str = "kN_m_C",
    equilibrium_ok: bool = True,
) -> dict:
    from jmworkbench.encargo import interpretar_encargo
    from bridgecalc.integration.grillage_model import (
        bridge_spec_from_encargo,
        build_bridge_grillage,
        compute_expected_vertical_loads_kN,
        section_props_from_catalog,
    )

    enc = interpretar_encargo(
        "Diseña un puente de 30 m de luz.",
        supuestos={
            "norma": "EN 1991-2",
            "uso": "carretera",
            "ancho_tablero_o_carriles": "ancho de tablero 10 m",
            "material": "acero",
            "apoyos": "simplemente apoyado",
            "galibo": "gálibo de 5,5 m",
            "acciones": "LM1",
        },
    )
    spec_base = bridge_spec_from_encargo(enc)
    from dataclasses import replace
    spec = replace(
        spec_base,
        girder_section=section_props_from_catalog(girder_section, material_name=spec_base.material.name),
        diaphragm_section=section_props_from_catalog(diaphragm_section, material_name=spec_base.material.name),
    )

    summary = build_bridge_grillage(
        None,
        spec=spec,
        preview_only=True,
    )
    meta = summary["meta"]
    fz_map = compute_expected_vertical_loads_kN(meta)
    eq_by_case = {
        k: {
            "applied_vertical_load_kN": v,
            "sum_Rz_reactions_kN": v if equilibrium_ok else v * 0.5,
            "abs_diff_kN": 0.0 if equilibrium_ok else v * 0.5,
            "rel_error": 0.0 if equilibrium_ok else 0.5,
            "sum_Rx_kN": 0.0,
            "sum_Ry_kN": 0.0,
            "sum_Rx_movable_abutment_kN": 0.0,
            "equilibrium_ok": equilibrium_ok,
        }
        for k, v in fz_map.items()
        if not k.startswith("DEAD_")
    }
    frame_forces = [
        # Estacion en centro de vano (x = 15 m, L1_0 station 7.5 m)
        {
            "frame": "L1_0",
            "role": "girder",
            "station_m": 7.5,
            "case": "ULS_STR",
            "P_kN": 0.0,
            "V2_kN": midspan_concurrent_V2_kN,
            "V3_kN": 0.0,
            "T_kNm": 3.07,
            "M2_kNm": 0.0,
            "M3_kNm": midspan_M3_kNm,
        },
        # Estacion en apoyo (x = 0 m, L0_0 station 0.0 m)
        {
            "frame": "L0_0",
            "role": "girder",
            "station_m": 0.0,
            "case": "ULS_STR_SHEAR",
            "P_kN": 0.0,
            "V2_kN": -support_V2_kN,
            "V3_kN": 0.0,
            "T_kNm": 25.0,
            "M2_kNm": 0.0,
            "M3_kNm": support_concurrent_M3_kNm,
        },
        # Diafragma interior T2_0
        {
            "frame": "T2_0",
            "role": "diaphragm",
            "station_m": 1.6667,
            "case": "ULS_STR",
            "P_kN": 0.0,
            "V2_kN": diaph_V2_kN,
            "V3_kN": 0.0,
            "T_kNm": 8.0,
            "M2_kNm": 0.0,
            "M3_kNm": diaph_M3_kNm,
        },
    ]
    displacements = [
        {
            "joint": "N2_0",
            "case": "LIVE_LANE",
            "Ux_m": 0.0,
            "Uy_m": 0.0,
            "Uz_m": -0.4 * (live_defl_mm / 1000.0),
            "Rx_rad": 0.0,
            "Ry_rad": 0.0,
            "Rz_rad": 0.0,
        },
        {
            "joint": "N2_0",
            "case": "LIVE_VEHICLE_M",
            "Ux_m": 0.0,
            "Uy_m": 0.0,
            "Uz_m": -0.6 * (live_defl_mm / 1000.0),
            "Rx_rad": 0.0,
            "Ry_rad": 0.0,
            "Rz_rad": 0.0,
        },
        {
            "joint": "N2_0",
            "case": "SLS_CHARACTERISTIC",
            "Ux_m": 0.0,
            "Uy_m": 0.0,
            "Uz_m": -(total_defl_mm / 1000.0),
            "Rx_rad": 0.0,
            "Ry_rad": 0.0,
            "Rz_rad": 0.0,
        },
    ]
    reactions = [
        {
            "joint": "N0_0",
            "case": "ULS_STR",
            "Fx_kN": 0.0,
            "Fy_kN": 0.0,
            "Fz_kN": 1500.0,
            "Mx_kNm": 0.0,
            "My_kNm": 0.0,
            "Mz_kNm": 0.0,
        },
        {
            "joint": "N0_0",
            "case": "ULS_STR_SHEAR",
            "Fx_kN": 0.0,
            "Fy_kN": 0.0,
            "Fz_kN": 1700.0,
            "Mx_kNm": 0.0,
            "My_kNm": 0.0,
            "Mz_kNm": 0.0,
        },
    ]
    return {
        "RunAnalysis_ret": run_ret,
        "units": units,
        "frames": summary["frames"],
        "meta": meta,
        "equilibrium_by_case": eq_by_case,
        "frame_forces": frame_forces,
        "displacements": displacements,
        "reactions": reactions,
    }


def test_verificador_falla_seccion_insuficiente_hem1000():
    """1. Fallo de sección insuficiente: HEM 1000 bajo las demandas reales del vano de 30 m
    incumple tanto ULS (flexión y LTB) como SLS (flecha activa y total), devolviendo
    CalculationStatus.CALCULADO_FALLA.
    """
    from bridgecalc._common.audit_status import CalculationStatus
    from bridgecalc.integration.grillage_model import verify_bridge_grillage_results

    rep = _make_synthetic_analysis_report(girder_section="HEM 1000")
    verif = verify_bridge_grillage_results(rep)

    assert verif["calculation_status"] == CalculationStatus.CALCULADO_FALLA
    assert verif["implemented_checks_status"] == "FALLA"
    assert verif["max_dcr_uls"] > 2.0
    assert verif["max_dcr_sls"] > 5.0
    checks_by_id = {c["check_id"]: c for c in verif["checks"]}
    assert checks_by_id["ELU_FLEXION_SECCION_VIGA"]["status"] == "CALCULADO_FALLA"
    assert checks_by_id["ELU_PANDEO_LATERAL_TORSIONAL_LTB_VIGA"]["status"] == "CALCULADO_FALLA"
    assert checks_by_id["ELS_FLECHA_ACTIVA_TRAFICO"]["status"] == "CALCULADO_FALLA"


def test_verificador_interaccion_concurrente_m_v_n_misma_estacion():
    """2. Interacción concurrente en la misma estación y combinación:
    - Cuando V2 <= 0.5 * Vc,Rd en la estación de máximo momento (x=15 m), rho=0 y no se penaliza
      artificialmente Mc,Rd con el cortante máximo del apoyo (x=0 m).
    - Cuando en la MISMA estación concurren M3 elevado y V2 > 0.5 * Vc,Rd, rho > 0 reduce Mc,Rd y Mb,Rd
      incrementando el DCR de interacción concurrente M-V-N.
    """
    from bridgecalc.integration.grillage_model import verify_bridge_grillage_results

    # Caso A: M3=3500 kN*m en centro de vano con V2 concurrente bajo (10 kN), aunque en el apoyo V2=1800 kN
    rep_low_v_concurrent = _make_synthetic_analysis_report(
        girder_section="HEM 1000",
        midspan_M3_kNm=3500.0,
        midspan_concurrent_V2_kN=10.0,
        support_V2_kN=1800.0,
        support_concurrent_M3_kNm=50.0,
        live_defl_mm=20.0,
        total_defl_mm=30.0,
    )
    verif_a = verify_bridge_grillage_results(rep_low_v_concurrent)
    mvn_a = next(c for c in verif_a["checks"] if c["check_id"] == "ELU_INTERACCION_CONCURRENTE_M_V_N_VIGA")
    assert mvn_a["rho_shear_reduction"] == pytest.approx(0.0)

    # Caso B: en la MISMA estacion concurren M3=3500 kN*m y V2=3200 kN (> 0.5 * Vc,Rd de HEM 1000)
    rep_high_v_concurrent = _make_synthetic_analysis_report(
        girder_section="HEM 1000",
        midspan_M3_kNm=3500.0,
        midspan_concurrent_V2_kN=3200.0,
        support_V2_kN=1800.0,
        support_concurrent_M3_kNm=50.0,
        live_defl_mm=20.0,
        total_defl_mm=30.0,
    )
    verif_b = verify_bridge_grillage_results(rep_high_v_concurrent)
    mvn_b = next(c for c in verif_b["checks"] if c["check_id"] == "ELU_INTERACCION_CONCURRENTE_M_V_N_VIGA")
    assert mvn_b["rho_shear_reduction"] > 0.20
    assert mvn_b["dcr"] > mvn_a["dcr"]


def test_verificador_analisis_invalido_o_resultados_incompletos_no_calculado():
    """5. Análisis inválido o resultados incompletos producen CalculationStatus.NO_CALCULADO."""
    from bridgecalc._common.audit_status import CalculationStatus
    from bridgecalc.integration.grillage_model import verify_bridge_grillage_results

    # RunAnalysis_ret != 0
    rep_bad_rc = _make_synthetic_analysis_report(run_ret=1)
    res_bad_rc = verify_bridge_grillage_results(rep_bad_rc)
    assert res_bad_rc["calculation_status"] == CalculationStatus.NO_CALCULADO
    assert res_bad_rc["implemented_checks_status"] == "NO_CALCULADO"

    # Esfuerzos vacios
    rep_empty = _make_synthetic_analysis_report()
    rep_empty["frame_forces"] = []
    res_empty = verify_bridge_grillage_results(rep_empty)
    assert res_empty["calculation_status"] == CalculationStatus.NO_CALCULADO

    # Equilibrio roto
    rep_bad_eq = _make_synthetic_analysis_report(equilibrium_ok=False)
    res_bad_eq = verify_bridge_grillage_results(rep_bad_eq)
    assert res_bad_eq["calculation_status"] == CalculationStatus.NO_CALCULADO


def test_conservacion_salvedades_y_estado_requiere_revision_cuando_implementados_cumplen():
    """6. Conservación de salvedades y estados límite no implementados:
    Cuando una viga armada PG_2100x700x55x30 cumple todos los estados límite implementados
    (DCR_ULS <= 1.0 y DCR_SLS <= 1.0), implemented_checks_status == 'CALCULADO_CUMPLE',
    pero calculation_status global es CalculationStatus.REQUIERE_REVISION porque persisten
    comprobaciones obligatorias de puente en unimplemented_checks.
    """
    from bridgecalc._common.audit_status import CalculationStatus
    from bridgecalc.integration.grillage_model import verify_bridge_grillage_results

    rep_ok = _make_synthetic_analysis_report(
        girder_section="PG_2100x700x55x30",
        diaphragm_section="HEB 400",
        midspan_M3_kNm=12200.0,
        midspan_concurrent_V2_kN=15.0,
        support_V2_kN=1580.0,
        diaph_M3_kNm=550.0,
        diaph_V2_kN=365.0,
        live_defl_mm=18.5,
        total_defl_mm=33.0,
    )
    verif = verify_bridge_grillage_results(rep_ok)
    assert verif["max_dcr_uls"] <= 1.0
    assert verif["max_dcr_sls"] <= 1.0
    assert verif["implemented_checks_status"] == "CUMPLE"
    assert len(verif["unimplemented_checks"]) >= 4
    assert verif["calculation_status"] == CalculationStatus.REQUIERE_REVISION


def test_ltb_viga_armada_pg_referencia_independiente_ec3():
    """Auditoria Punto 1: Prueba de referencia independiente en forma cerrada para el pandeo
    lateral-torsional (LTB) y cortante de dos secciones armadas soldadas (PG_1900x650x50x28 y
    PG_1500x550x40x24) segun EN 1993-1-1:2005+A1:2014 §6.3.2.2 (Caso General de vigas soldadas),
    EN 10025-2 Tabla 7 y EN 1993-1-5 §5.1-5.3.
    """
    import math
    from bridgecalc.integration.grillage_model import (
        _compute_member_capacities_ec3,
        default_bridge_material,
        section_props_from_catalog,
    )

    mat = default_bridge_material("acero", "EN_1991_2").to_dict()
    E_MPa = 210000.0
    nu = 0.30
    G_MPa = E_MPa / (2.0 * (1.0 + nu))  # 80769.230769 MPa
    L_LT_m = 7.50  # 30.0 m / 4 divisiones entre diafragmas T0..T4

    for sec_name, h_m, b_m, tf_m, tw_m, fy_eff_expected in [
        ("PG_1900x650x50x28", 1.900, 0.650, 0.050, 0.028, 335.0),
        ("PG_1500x550x40x24", 1.500, 0.550, 0.040, 0.024, 345.0),
    ]:
        sec = section_props_from_catalog(sec_name, material_name="S355").to_dict()
        cap = _compute_member_capacities_ec3(sec, mat, L_ltb_m=L_LT_m, gamma_M0=1.00, gamma_M1=1.10)

        # 1) Reduccion de limite elastico por espesor EN 10025-2 Tabla 7
        assert cap["fy_effective_MPa"] == pytest.approx(fy_eff_expected)
        eps_ref = math.sqrt(235.0 / fy_eff_expected)
        assert cap["classification"]["epsilon"] == pytest.approx(eps_ref, abs=1e-5)

        # 2) Propiedades geometricas exactas de seccion doble T doblemente simetrica sin acuerdo r=0
        hw_m = h_m - 2.0 * tf_m
        i22_ref = (2.0 * tf_m * (b_m ** 3) + hw_m * (tw_m ** 3)) / 12.0
        j_ref = (2.0 * b_m * (tf_m ** 3) + hw_m * (tw_m ** 3)) / 3.0
        iw_ref = i22_ref * ((h_m - tf_m) ** 2) / 4.0
        wpl33_ref = b_m * tf_m * (h_m - tf_m) + 0.25 * tw_m * (hw_m ** 2)

        assert sec["I22_m4"] == pytest.approx(i22_ref, rel=1e-4)
        assert sec["J_m4"] == pytest.approx(j_ref, rel=1e-4)
        assert cap["Iw_m6"] == pytest.approx(iw_ref, rel=1e-4)
        assert cap["Wy_m3"] == pytest.approx(wpl33_ref, rel=1e-4)

        # 3) Clasificacion de seccion EN 1993-1-1 Tabla 5.2 (Clase 1/2 -> usa Wpl,y)
        cf_over_tf_ref = (0.5 * (b_m - tw_m)) / tf_m
        cw_over_tw_ref = hw_m / tw_m
        assert cf_over_tf_ref <= 9.0 * eps_ref  # Ala Clase 1
        assert cw_over_tw_ref <= 83.0 * eps_ref  # Alma Clase 1 o 2
        assert cap["classification"]["section_class"] in (1, 2)

        # 4) Momento critico elastico de Timoshenko Mcr (C1 = 1.0, apoyo en horquilla en diafragmas)
        E_Pa = E_MPa * 1e6
        G_Pa = G_MPa * 1e6
        k_pi_L = math.pi / L_LT_m
        Mcr_Nm_ref = k_pi_L * math.sqrt((E_Pa * i22_ref) * (G_Pa * j_ref + (k_pi_L ** 2) * E_Pa * iw_ref))
        Mcr_kNm_ref = Mcr_Nm_ref / 1000.0
        assert cap["Mcr_kNm"] == pytest.approx(Mcr_kNm_ref, rel=1e-5)

        # 5) Esbeltez adimensional y factor de reduccion chi_LT (§6.3.2.2 Caso General, Tabla 6.3 y 6.4)
        #    Para seccion armada soldada con h/b > 2.0 -> curva 'd' (alpha_LT = 0.76)
        assert (h_m / b_m) > 2.0
        assert cap["ltb_curve"] == "d"
        alpha_LT = 0.76
        lam_bar_ref = math.sqrt((wpl33_ref * fy_eff_expected * 1e6) / Mcr_Nm_ref)
        phi_lt_ref = 0.5 * (1.0 + alpha_LT * (lam_bar_ref - 0.2) + (lam_bar_ref ** 2))
        chi_lt_ref = 1.0 / (phi_lt_ref + math.sqrt(phi_lt_ref ** 2 - lam_bar_ref ** 2))
        Mb_Rd_kNm_ref = (chi_lt_ref * wpl33_ref * fy_eff_expected * 1000.0) / 1.10
        Mc_Rd_kNm_ref = (wpl33_ref * fy_eff_expected * 1000.0) / 1.00

        assert cap["lambda_bar_LT"] == pytest.approx(lam_bar_ref, abs=1e-4)
        assert cap["chi_LT"] == pytest.approx(chi_lt_ref, abs=1e-4)
        assert cap["Mb_Rd_kNm"] == pytest.approx(Mb_Rd_kNm_ref, rel=1e-4)
        assert cap["Mc_Rd_kNm"] == pytest.approx(Mc_Rd_kNm_ref, rel=1e-4)

        # 6) Cortante y abolladura del alma EN 1993-1-5 §5.1-5.3
        eta_w = 1.20
        hw_lim_ref = (72.0 / eta_w) * eps_ref
        assert cap["hw_over_tw"] == pytest.approx(cw_over_tw_ref, abs=1e-3)
        assert cap["hw_over_tw_unstiffened_limit"] == pytest.approx(hw_lim_ref, abs=1e-3)


class _StatefulBridgeSapMock:
    """Mock con estado físico simplificado de SAP2000 para probar en tests unitarios rápidos
    el bucle cerrado de redimensionamiento, desbloqueo del modelo, actualización de secciones,
    verificación GetSectProps, recálculo de peso propio y flecha inversamente proporcional a I33.
    """
    def __init__(self):
        from pathlib import Path
        self.locked = False
        self.materials = {}
        self.sections = {}
        self.points = {}
        self.restraints = {}
        self.frames = {}
        self.patterns = {}
        self.combos = {}
        self.saved_paths = []
        self.run_count = 0
        self.unlock_count = 0
        mock = self

        class cPropMaterial:
            def SetMaterial(self, name, mat_type):
                mock.materials[name] = {"type": mat_type}
                return 0

            def SetMPIsotropic(self, name, e, nu, alpha):
                mock.materials.setdefault(name, {}).update({"E": e, "nu": nu, "alpha": alpha})
                return 0

            def SetWeightAndMass(self, name, opt, val):
                mock.materials.setdefault(name, {})["gamma"] = val
                return 0

            def GetNameList(self, num, names):
                ks = list(mock.materials.keys())
                return (0, len(ks), ks)

        class cPropFrame:
            def SetISection(self, name, mat, t3, t2, tf, tw, t2b, tfb):
                hw = max(0.0, t3 - 2.0 * tf)
                area = 2.0 * t2 * tf + hw * tw
                i33 = (t2 * (t3 ** 3) - (t2 - tw) * (hw ** 3)) / 12.0
                i22 = (2.0 * tf * (t2 ** 3) + hw * (tw ** 3)) / 12.0
                j = (2.0 * t2 * (tf ** 3) + hw * (tw ** 3)) / 3.0
                s33 = i33 / (0.5 * t3)
                z33 = t2 * tf * (t3 - tf) + 0.25 * tw * (hw ** 2)
                s22 = i22 / (0.5 * t2)
                z22 = 0.5 * tf * (t2 ** 2) + 0.25 * hw * (tw ** 2)
                as2 = t3 * tw
                as3 = (5.0 / 6.0) * 2.0 * t2 * tf
                r22 = (i22 / area) ** 0.5
                r33 = (i33 / area) ** 0.5
                mock.sections[name] = {
                    "mat": mat, "t3": t3, "t2": t2, "tf": tf, "tw": tw,
                    "props": (area, as2, as3, j, i22, i33, s22, s33, z22, z33, r22, r33),
                }
                return 0

            def GetSectProps(self, name, *args):
                p = mock.sections[name]["props"]
                return (0, *p)

            def GetNameList(self, num, names):
                ks = list(mock.sections.keys())
                return (0, len(ks), ks)

        class cPointObj:
            def AddCartesian(self, x, y, z, name, uname):
                mock.points[uname] = (float(x), float(y), float(z))
                return (0, uname)

            def SetRestraint(self, name, vals):
                mock.restraints[name] = list(vals)
                return 0

            def GetRestraint(self, name, vals):
                return (0, mock.restraints.get(name, [False] * 6))

            def GetCoordCartesian(self, name, x=0.0, y=0.0, z=0.0):
                pt = mock.points[name]
                return (0, pt[0], pt[1], pt[2])

            def Count(self):
                return len(mock.points)

        class cFrameObj:
            def AddByPoint(self, ji, jj, prop, section, name):
                mock.frames[name] = {"ji": ji, "jj": jj, "section": section}
                return (0, name)

            def SetSection(self, name, sec_name):
                if mock.locked:
                    return 1  # SAP2000 falla si el modelo sigue bloqueado
                mock.frames[name]["section"] = sec_name
                return 0

            def GetSection(self, name, prop="", auto=""):
                return (0, mock.frames[name]["section"], "")

            def GetPoints(self, name, pi="", pj=""):
                f = mock.frames[name]
                return (0, f["ji"], f["jj"])

            def SetOutputStations(self, *args):
                return 0

            def SetLoadDistributed(self, *args):
                return 0

            def SetLoadPoint(self, *args):
                return 0

            def Count(self):
                return len(mock.frames)

        class _LoadPatterns:
            def Add(self, name, my_type, sw_mult=0.0, add_case=True):
                mock.patterns[name] = (my_type, sw_mult)
                return 0

            def GetNameList(self, num, names):
                ks = list(mock.patterns.keys())
                return (0, len(ks), ks)

        class _RespCombo:
            def Add(self, name, combo_type):
                mock.combos[name] = {}
                return 0

            def SetCaseList(self, name, cname_type, cname, sf):
                mock.combos.setdefault(name, {})[cname] = float(sf)
                return 0

            def GetNameList(self, num, names):
                ks = list(mock.combos.keys())
                return (0, len(ks), ks)

        class _File:
            def Save(self, path):
                import os
                p = Path(str(path).replace("\\", "/")) if os.name != "nt" else Path(path)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b"SAP2000_MOCK_SDB_BINARY_HEADER" * 40)
                mock.saved_paths.append(str(p))
                return 0

            def NewBlank(self):
                return 0

            def OpenFile(self, path):
                import os
                p = Path(str(path).replace("\\", "/")) if os.name != "nt" else Path(path)
                return 0 if p.exists() else 1

        class _Analyze:
            def SetRunCaseFlag(self, name, flag, all_flag=True):
                return 0

            def RunAnalysis(self):
                mock.locked = True
                mock.run_count += 1
                return 0

        class _Setup:
            def DeselectAllCasesAndCombosForOutput(self):
                return 0

            def SetCaseSelectedForOutput(self, name):
                return 0

            def SetComboSelectedForOutput(self, name):
                return 0

        class _Results:
            def __init__(self):
                self.Setup = _Setup()

            def JointReact(self, name, item_type, *args):
                # Devolver 1/8 de la carga vertical esperada en cada uno de los 8 apoyos
                from bridgecalc.integration.grillage_model import (
                    compute_expected_vertical_loads_kN,
                    section_props_from_catalog,
                )
                g_sec = mock.frames["L0_0"]["section"]
                d_sec = mock.frames["T0_0"]["section"]
                g_p = section_props_from_catalog(g_sec).to_dict()
                d_p = section_props_from_catalog(d_sec).to_dict()
                meta_tmp = {
                    "material": {"gamma_kN_m3": 78.5},
                    "sections": {g_sec: g_p, d_sec: d_p},
                    "total_length": 30.0,
                    "width_m": 10.0,
                    "n_girders": 4,
                    "derived_counts": {"n_x": 5},
                    "loads_summary": {
                        "q_slab_per_girder_kN_m": 15.625,
                        "q_dw_per_girder_kN_m": 6.25,
                        "q_lane_per_girder_kN_m": 11.125,
                        "q_lane_by_girder_kN_m": {0: 17.225, 1: 13.158333, 2: 9.091667, 3: 5.025},
                        "frame_point_loads_LIVE_VEHICLE_M": [{"load_kN": 1200.0}],
                        "frame_point_loads_LIVE_VEHICLE_V": [{"load_kN": 1200.0}],
                        "combinations": [
                            {"name": "ULS_STR", "factors": {"DEAD": 1.35, "DW": 1.35, "LIVE_LANE": 1.35, "LIVE_VEHICLE_M": 1.35}},
                            {"name": "ULS_STR_SHEAR", "factors": {"DEAD": 1.35, "DW": 1.35, "LIVE_LANE": 1.35, "LIVE_VEHICLE_V": 1.35}},
                            {"name": "SLS_CHARACTERISTIC", "factors": {"DEAD": 1.0, "DW": 1.0, "LIVE_LANE": 1.0, "LIVE_VEHICLE_M": 1.0}},
                        ],
                    },
                }
                fz = compute_expected_vertical_loads_kN(meta_tmp)
                cases = ["DEAD", "DW", "LIVE_LANE", "LIVE_VEHICLE_M", "LIVE_VEHICLE_V", "ULS_STR", "ULS_STR_SHEAR", "SLS_CHARACTERISTIC"]
                n = len(cases)
                return (
                    0, n, [name] * n, [""] * n, cases, ["LinStatic"] * n, [0.0] * n,
                    [0.0] * n, [0.0] * n, [fz[c] / 8.0 for c in cases],
                    [0.0] * n, [0.0] * n, [0.0] * n,
                )

            def JointDispl(self, name, item_type, *args):
                # Flecha inversamente proporcional a I33 de la viga principal
                g_sec = mock.frames["L0_0"]["section"]
                i33 = mock.sections[g_sec]["props"][5]
                i33_ref = 0.005926  # HEM 1000
                ratio = i33_ref / max(1e-9, i33)
                cases = ["DEAD", "DW", "LIVE_LANE", "LIVE_VEHICLE_M", "LIVE_VEHICLE_V", "ULS_STR", "ULS_STR_SHEAR", "SLS_CHARACTERISTIC"]
                uz_ref = {
                    "DEAD": -0.130,
                    "DW": -0.054,
                    "LIVE_LANE": -0.1237,
                    "LIVE_VEHICLE_M": -0.1763,
                    "LIVE_VEHICLE_V": -0.015,
                    "ULS_STR": -0.654,
                    "ULS_STR_SHEAR": -0.435,
                    "SLS_CHARACTERISTIC": -0.4848,
                }
                n = len(cases)
                return (
                    0, n, [name] * n, [""] * n, cases, ["LinStatic"] * n, [0.0] * n,
                    [0.0] * n, [0.0] * n, [uz_ref[c] * ratio if name.startswith("N2_") else 0.0 for c in cases],
                    [0.0] * n, [0.0] * n, [0.0] * n,
                )

            def FrameForce(self, name, item_type, *args):
                g_sec = mock.frames["L0_0"]["section"]
                area = mock.sections[g_sec]["props"][0]
                area_ref = 0.031536  # HEM 1000
                # El momento por peso propio crece ligeramente con el area de la viga
                m3_uls = 11014.12 + (area - area_ref) * 78.5 * (30.0 ** 2 / 8.0) * 1.35
                v2_uls = 1478.68 + (area - area_ref) * 78.5 * (30.0 / 2.0) * 1.35
                is_girder = name.startswith("L")
                cases = ["ULS_STR", "ULS_STR_SHEAR"]
                n = len(cases)
                m3_vals = [m3_uls if is_girder else 551.8, 200.0 if is_girder else 300.0]
                v2_vals = [10.0 if is_girder else 365.5, -v2_uls if is_girder else 250.0]
                return (
                    0, n, [name] * n, [3.75] * n, [name] * n, [3.75] * n,
                    cases, ["Combo"] * n, [0.0] * n,
                    [0.0] * n, v2_vals, [0.0] * n, [3.0] * n, [0.0] * n, m3_vals,
                )

        self.PropMaterial = cPropMaterial()
        self.PropFrame = cPropFrame()
        self.PointObj = cPointObj()
        self.FrameObj = cFrameObj()
        self.LoadPatterns = _LoadPatterns()
        self.RespCombo = _RespCombo()
        self.File = _File()
        self.Analyze = _Analyze()
        self.Results = _Results()

    def SetModelIsLocked(self, flag: bool):
        self.locked = bool(flag)
        if not self.locked:
            self.unlock_count += 1
        return 0


def test_bucle_redimensionamiento_actualiza_propiedades_reanaliza_y_converge(tmp_path):
    """3. Actualización del modelo y reanálisis cuando se cambia la sección en el bucle:
    Verifica que el bucle detecta el fallo de HEM 1000, desbloquea el modelo (SetModelIsLocked(False)),
    registra y verifica con GetSectProps cada nueva sección candidata PG_*, actualiza todas las barras L*,
    re-ejecuta RunAnalysis() y converge en una sección armada PG_* con DCR_ULS <= 1.0 y DCR_SLS <= 1.0.
    """
    from jmworkbench.encargo import interpretar_encargo
    from bridgecalc.integration.grillage_model import (
        bridge_spec_from_encargo,
        execute_bridge_grillage_design_loop,
    )

    enc = interpretar_encargo(
        "Diseña un puente de 30 m de luz.",
        supuestos={
            "norma": "EN 1991-2",
            "uso": "carretera",
            "ancho_tablero_o_carriles": "ancho de tablero 10 m",
            "material": "acero",
            "apoyos": "simplemente apoyado",
            "galibo": "gálibo de 5,5 m",
            "acciones": "LM1",
        },
    )
    spec = bridge_spec_from_encargo(enc)
    mock_sap = _StatefulBridgeSapMock()
    sdb_file = tmp_path / "bucle_convergencia.sdb"
    ladder = ("HEM 1000", "PG_1500x550x40x24", "PG_1900x650x50x28", "PG_2100x700x55x30")

    res = execute_bridge_grillage_design_loop(
        mock_sap,
        str(sdb_file),
        spec=spec,
        candidate_girder_ladder=ladder,
    )

    assert res["initial_girder_section"] == "HEM 1000"
    assert res["final_girder_section"] == "PG_1900x650x50x28"
    assert res["n_iterations"] == 3
    assert mock_sap.run_count == 3
    assert mock_sap.unlock_count == 2
    assert res["termination_reason"] == "CONVERGED_ALL_IMPLEMENTED_CHECKS_PASS"
    assert res["implemented_checks_status"] == "CUMPLE"
    assert res["calculation_status"] == "REQUIERE_REVISION"
    assert res["persistence_verdict"] == {"veredicto": "OK", "motivos": []}

    # Verificar que el peso propio DEAD y la inercia I33 crecen en cada iteracion y el DCR baja
    hist = res["iterations_history"]
    assert hist[0]["girder_section"] == "HEM 1000"
    assert hist[0]["implemented_checks_status"] == "FALLA"
    assert hist[-1]["girder_section"] == "PG_1900x650x50x28"
    assert hist[-1]["implemented_checks_status"] == "CUMPLE"
    assert hist[-1]["DEAD_total_kN"] > hist[0]["DEAD_total_kN"]
    assert hist[-1]["active_traffic_deflection_mm"] < hist[0]["active_traffic_deflection_mm"]
    assert hist[-1]["max_dcr_overall"] <= 1.0
    reopened_f_secs = res["counts"]["reopened"]["frame_sections"]
    assert all(reopened_f_secs[fid] == "PG_1900x650x50x28" for fid in reopened_f_secs if fid.startswith("L"))
    assert all(reopened_f_secs[fid] == "HEB 400" for fid in reopened_f_secs if fid.startswith("T"))


def test_bucle_redimensionamiento_agotamiento_catalogo_calculado_falla(tmp_path):
    """4. Agotamiento de catálogo sin convergencia:
    Si la escalera permitida solo contiene perfiles laminados hasta HEM 1000, el bucle
    agota el catálogo y termina limpiamente con CalculationStatus.CALCULADO_FALLA y
    termination_reason == 'CATALOG_EXHAUSTED'.
    """
    from dataclasses import replace
    from jmworkbench.encargo import interpretar_encargo
    from bridgecalc.integration.grillage_model import (
        bridge_spec_from_encargo,
        execute_bridge_grillage_design_loop,
        section_props_from_catalog,
    )

    enc = interpretar_encargo(
        "Diseña un puente de 30 m de luz.",
        supuestos={
            "norma": "EN 1991-2",
            "uso": "carretera",
            "ancho_tablero_o_carriles": "ancho de tablero 10 m",
            "material": "acero",
            "apoyos": "simplemente apoyado",
            "galibo": "gálibo de 5,5 m",
            "acciones": "LM1",
        },
    )
    spec_base = bridge_spec_from_encargo(enc)
    spec_heb900 = replace(
        spec_base,
        girder_section=section_props_from_catalog("HEB 900", material_name=spec_base.material.name),
    )
    mock_sap = _StatefulBridgeSapMock()
    sdb_file = tmp_path / "bucle_agotado.sdb"
    short_ladder = ("HEB 900", "HEM 1000")

    res = execute_bridge_grillage_design_loop(
        mock_sap,
        str(sdb_file),
        spec=spec_heb900,
        candidate_girder_ladder=short_ladder,
    )

    assert res["termination_reason"] == "CATALOG_EXHAUSTED"
    assert res["implemented_checks_status"] == "FALLA"
    assert res["calculation_status"] == "CALCULADO_FALLA"
    assert res["n_iterations"] == 2
    assert res["final_girder_section"] == "HEM 1000"


@pytest.mark.compat
@pytest.mark.live
def test_bridge_grillage_30m_closed_loop_resize_live_sap2000(tmp_path):
    """Test LIVE en SAP2000 v26 del bucle completo de verificación ULS/SLS y redimensionamiento
    iterativo del puente de 30 m x 10 m desde HEM 1000 hasta convergencia en viga armada PG_*.
    """
    from pathlib import Path
    import json
    import shutil
    from jmworkbench.encargo import interpretar_encargo
    from bridgecalc.integration.grillage_model import (
        bridge_spec_from_encargo,
        run_bridge_grillage_design_loop_sap2000,
    )

    sap_exe = Path(r"C:\Program Files\Computers and Structures\SAP2000 26\SAP2000.exe")
    if not sap_exe.exists():
        pytest.skip(f"SAP2000 v26 no instalado en {sap_exe}")

    enc = interpretar_encargo(
        "Diseña un puente de 30 m de luz que cumpla la normativa aplicable. "
        "Selecciona una tipología estructural adecuada, define la geometría, "
        "predimensiona y selecciona las secciones, establece materiales, apoyos, "
        "cargas y combinaciones, genera el modelo en SAP2000, ejecuta el análisis, "
        "verifica los estados límite, corrige las secciones si es necesario y "
        "entrega el modelo en SAP2000 con sus resultados y sus planos en AutoCAD.",
        supuestos={
            "norma": "EN 1991-2",
            "uso": "carretera",
            "ancho_tablero_o_carriles": "ancho de tablero 10 m",
            "material": "acero",
            "apoyos": "simplemente apoyado",
            "galibo": "gálibo de 5,5 m",
            "acciones": "LM1",
        },
    )
    spec = bridge_spec_from_encargo(enc)
    sdb_file = tmp_path / "puente_30m_emparrillado_redimensionado_live.sdb"

    res = run_bridge_grillage_design_loop_sap2000(
        str(sdb_file),
        spec=spec,
        visible=False,
        keep_open=False,
    )

    assert Path(res["sdb_path"]).exists()
    assert res["sdb_size_bytes"] > 1000
    assert res["RunAnalysis_ret"] == 0
    assert res["initial_girder_section"] == "HEM 1000"
    assert res["final_girder_section"].startswith("PG_")
    assert res["n_iterations"] >= 2
    assert res["termination_reason"] == "CONVERGED_ALL_IMPLEMENTED_CHECKS_PASS"
    assert res["implemented_checks_status"] == "CUMPLE"
    assert res["calculation_status"] == "REQUIERE_REVISION"
    assert res["persistence_verdict"] == {"veredicto": "OK", "motivos": []}

    # Iteracion 0 (HEM 1000) debe fallar con DCR > 1.0; iteracion final debe cumplir con DCR <= 1.0
    hist = res["iterations_history"]
    assert hist[0]["girder_section"] == "HEM 1000"
    assert hist[0]["implemented_checks_status"] == "FALLA"
    assert hist[0]["max_dcr_uls"] > 1.0
    assert hist[0]["max_dcr_sls"] > 1.0

    assert hist[-1]["girder_section"] == res["final_girder_section"]
    assert hist[-1]["implemented_checks_status"] == "CUMPLE"
    assert hist[-1]["max_dcr_uls"] <= 1.0
    assert hist[-1]["max_dcr_sls"] <= 1.0
    assert hist[-1]["sap_section_verification"]["girder"]["verified_via_oapi"] is True
    assert hist[-1]["sap_section_verification"]["girder"]["max_rel_diff"] < 0.01
    reopened_f_secs = res["counts"]["reopened"]["frame_sections"]
    assert len(reopened_f_secs) == 31
    assert all(reopened_f_secs[fid] == res["final_girder_section"] for fid in reopened_f_secs if fid.startswith("L"))
    assert all(reopened_f_secs[fid] == "HEB 400" for fid in reopened_f_secs if fid.startswith("T"))

    # Equilibrio global exacto en todas las combinaciones del modelo final
    for case_name, eq in res["equilibrium_by_case"].items():
        assert eq["equilibrium_ok"] is True, f"Equilibrio fallo en {case_name}: {eq}"
        assert eq["rel_error"] < 1e-4

    # Persistir artefactos finales auditables
    import tempfile
    artifact_dir = Path(tempfile.gettempdir()) / "bridgecalc_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(res["sdb_path"], artifact_dir / "puente_30m_emparrillado_redimensionado_sap2000_v26.sdb")
    (artifact_dir / "puente_30m_emparrillado_redimensionado_sap2000_v26_report.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8"
    )
