"""Tests del generador de emparrillado de puente (idea #12, MVP). Pura geometría.

Verifica conteos del grid (vigas longitudinales + diafragmas), apoyos en pilas y
que la carga de carril HL-93 viaja como metadato. Sin CSiBridge.
"""
from bridgejm.integration.grillage_model import generate_grillage


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
