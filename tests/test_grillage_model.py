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
import pytest

from bridgejm.integration.grillage_model import (
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
                return _ret("AddCartesian")

            def SetRestraint(self, name, vals):
                builder.restraints.append((name, list(vals)))
                return _ret("SetRestraint")

            def SetLoadForce(self, name, pat, vals, replace=False, csys="Global", item_type=0):
                builder.point_loads.append((name, pat, list(vals)))
                return _ret("SetLoadForce")

        class _FrameObj:
            def AddByPoint(self, ji, jj, prop, section, name):
                builder.frames.append((ji, jj, section, name))
                return _ret("AddByPoint")

            def SetLoadDistributed(self, name, pat, my_type, dir_, dist1, dist2, val1, val2, csys="Global", rel=True, replace=True, item_type=0):
                builder.dist_loads.append((name, pat, my_type, dir_, dist1, dist2, val1, val2))
                return _ret("SetLoadDistributed")

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
        "SetLoadForce",
        "RespCombo.Add",
        "RespCombo.SetCaseList",
    ],
)
def test_oapi_ret_nonzero_lanza_excepcion(fail_op: str):
    from bridgejm.integration.grillage_model import OAPICallError

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
    from bridgejm.integration.grillage_model import expected_grillage_counts

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
    from bridgejm.integration.grillage_model import verify_kinematic_stability

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
    from bridgejm.integration.grillage_model import (
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
    assert len(sap.point_loads) > 0
    # Todas las cargas verticales gravitatorias deben ser negativas en Z global (< 0)
    assert all(pl[2][2] < 0 for pl in sap.point_loads)

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
    from bridgejm.integration.grillage_model import (
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
