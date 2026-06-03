"""Tests del generador de emparrillado de puente (idea #12, MVP). Pura geometría.

Verifica conteos del grid (vigas longitudinales + diafragmas), apoyos en pilas y
que la carga de carril HL-93 viaja como metadato. Sin CSiBridge.
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
    assert all(j["restraint"] == [True, True, True, False, False, False] for j in apoyados)


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
    # divisions_per_span = n_diaphragms+1 = 4 → n_x = 5 lineas transversales.
    # joints = 5 * 4 = 20
    assert len(g["joints"]) == 20
    # longitudinales = (n_x-1)*n_girders = 4*4 = 16
    assert sum(1 for f in g["frames"] if f["id"].startswith("L")) == 16
    # transversales = n_x*(n_girders-1) = 5*3 = 15
    assert sum(1 for f in g["frames"] if f["id"].startswith("T")) == 15
    # ancho total 10 m sobre 4 vigas → separacion 10/3
    assert g["meta"]["girder_spacing"] == pytest.approx(10.0 / 3.0)
    # la viga de borde cae en y = W
    assert any(j["y"] == pytest.approx(10.0) for j in g["joints"])


def test_grillage_model_coords_extremos():
    g = grillage_model(L=30.0, W=12.0, n_girders=3, n_diaphragms=2)
    # extremo en x=30 sobre la viga central (y=6)
    assert any(j["x"] == pytest.approx(30.0) and j["y"] == pytest.approx(6.0)
               for j in g["joints"])
    # apoyos solo en x=0 y x=30 → 2 lineas * 3 vigas = 6
    apoyados = [j for j in g["joints"] if j["restraint"] is not None]
    assert len(apoyados) == 6


def test_grillage_model_validaciones():
    with pytest.raises(ValueError):
        grillage_model(L=30.0, W=0.0, n_girders=4, n_diaphragms=3)
    with pytest.raises(ValueError):
        grillage_model(L=30.0, W=10.0, n_girders=1, n_diaphragms=3)


# --------------------------------------------------------------------------- #
# build_bridge_grillage — OAPI (mock, sin CSiBridge vivo)
# --------------------------------------------------------------------------- #
class _RecordingSapModel:
    """Mock minimal de SapModel: registra las llamadas OAPI."""
    def __init__(self):
        self.points = []
        self.restraints = []
        self.frames = []

        builder = self

        class _PointObj:
            def AddCartesian(self, x, y, z, name, uname):
                builder.points.append((x, y, z, name, uname))
                return 0
            def SetRestraint(self, name, vals):
                builder.restraints.append((name, list(vals)))
                return 0

        class _FrameObj:
            def AddByPoint(self, ji, jj, prop, section, name):
                builder.frames.append((ji, jj, section, name))
                return 0

        self.PointObj = _PointObj()
        self.FrameObj = _FrameObj()


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
    assert all(r[1] == [True, True, True, False, False, False]
               for r in sap.restraints)
    # las secciones se asignan (vigas + diafragmas)
    secciones = {f[2] for f in sap.frames}
    assert secciones == {"GIRDER", "DIAPHRAGM"}


def test_build_acepta_sapmodel_directo():
    sap = _RecordingSapModel()
    # pasar el SapModel directamente (sin wrapper) tambien funciona
    build_bridge_grillage(sap, L=20.0, W=8.0, n_girders=3, n_diaphragms=1)
    # n_x = div+1 = 2+1... div = n_diaphragms+1 = 2 → n_x=3; joints=3*3=9
    assert len(sap.points) == 9
