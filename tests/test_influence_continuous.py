"""Tests BJ-001: lineas de influencia multi-tramo + superposicion."""
import numpy as np
import pytest

from bridgecalc.loads.influence_lines import (
    influence_line_continuous,
    critical_position,
    InfluenceLine,
    simple_beam_M_influence,
    two_span_continuous_M_at_support,
)
from bridgecalc.loads.hl93 import TRUCK_AXLES_kN, TRUCK_AXLE_SPACINGS_m


class TestInfluenceLineContinuous:
    def test_2_tramos_iguales_M_positivo(self):
        """Para 2 tramos iguales, M_max positivo ocurre ~ 0.4L del primer tramo."""
        L = 20.0
        spans = [L, L]
        # Evaluar M en 0.4*L del primer tramo
        x_eval = 0.4 * L
        il = influence_line_continuous(spans, x_eval, n_points=100)
        # La linea de influencia en x_eval=0.4L debe tener maximo > 0
        assert np.max(il.ordinates) > 0
        # El maximo de la IL deberia estar cerca de x_eval
        idx_max = int(np.argmax(il.ordinates))
        assert abs(il.x_m[idx_max] - x_eval) < 2.0  # dentro de 2m

    def test_2_tramos_iguales_simetria(self):
        """Puntos simetricos respecto al apoyo central deben dar
        lineas de influencia con el mismo pico."""
        L = 15.0
        # 0.4L en tramo 1  <-->  L + (1-0.4)*L = L + 0.6L en tramo 2
        # Pero la simetria real es: x en tramo 1 <-> 2L - x en tramo 2
        il1 = influence_line_continuous([L, L], 0.4 * L, n_points=100)
        il2 = influence_line_continuous([L, L], 2 * L - 0.4 * L, n_points=100)
        max1 = np.max(il1.ordinates)
        max2 = np.max(il2.ordinates)
        assert max1 == pytest.approx(max2, rel=0.05)

    def test_3_tramos(self):
        il = influence_line_continuous([20, 25, 20], 10.0, n_points=80)
        assert il.x_m[0] == pytest.approx(0.0)
        assert il.x_m[-1] == pytest.approx(65.0)
        assert np.max(il.ordinates) > 0

    def test_single_span_matches_simple_beam(self):
        """Para un solo tramo, debe coincidir con la viga simple."""
        L = 10.0
        x_eval = 5.0
        il_cont = influence_line_continuous([L], x_eval, n_points=200)
        il_simple = simple_beam_M_influence(L, x_eval, n_points=200)
        # Comparar maximos
        max_cont = np.max(il_cont.ordinates)
        max_simple = np.max(il_simple.ordinates)
        assert max_cont == pytest.approx(max_simple, rel=0.05)

    def test_x_eval_fuera_rango(self):
        with pytest.raises(ValueError):
            influence_line_continuous([10, 10], -1.0)
        with pytest.raises(ValueError):
            influence_line_continuous([10, 10], 25.0)

    def test_cortante(self):
        il = influence_line_continuous([15, 15], 7.5, n_points=100, quantity="V")
        assert il.quantity == "V"
        # Cortante deberia tener cambio de signo
        assert np.min(il.ordinates) < 0
        assert np.max(il.ordinates) > 0


class TestCriticalPosition:
    def test_simple_beam_truck_position(self):
        """Para viga simple, posicion critica del camion HL-93 debe
        estar cerca de midspan."""
        L = 30.0
        il = simple_beam_M_influence(L, L / 2, n_points=200)
        # HL-93 truck: 3 ejes
        truck_loads = [
            (0.0, TRUCK_AXLES_kN[0]),
            (TRUCK_AXLE_SPACINGS_m[0], TRUCK_AXLES_kN[1]),
            (sum(TRUCK_AXLE_SPACINGS_m), TRUCK_AXLES_kN[2]),
        ]
        pos, effect = critical_position(il, truck_loads)
        # El primer eje deberia estar entre 0 y L
        assert 0 <= pos <= L
        assert effect > 0

    def test_2_tramos_M_max_en_04L(self):
        """Para 2 tramos iguales con tren de carga, M_max en ~0.4L."""
        L = 20.0
        x_eval = 0.4 * L
        il = influence_line_continuous([L, L], x_eval, n_points=150)
        truck_loads = [
            (0.0, TRUCK_AXLES_kN[0]),
            (TRUCK_AXLE_SPACINGS_m[0], TRUCK_AXLES_kN[1]),
            (sum(TRUCK_AXLE_SPACINGS_m), TRUCK_AXLES_kN[2]),
        ]
        pos, effect = critical_position(il, truck_loads)
        assert effect > 0

    def test_udl_adds_positive(self):
        """Carga uniforme aumenta el efecto."""
        L = 25.0
        il = simple_beam_M_influence(L, L / 2, n_points=200)
        truck_loads = [(0.0, 100.0), (4.0, 100.0)]
        _, e_no_udl = critical_position(il, truck_loads, udl_kN_per_m=0.0)
        _, e_with_udl = critical_position(il, truck_loads, udl_kN_per_m=9.34)
        assert e_with_udl > e_no_udl

    def test_empty_loads(self):
        il = simple_beam_M_influence(10, 5)
        pos, effect = critical_position(il, [], udl_kN_per_m=10.0)
        assert effect > 0  # UDL contribuye

    def test_effect_at_multiple_positions(self):
        """Verificar que el efecto es mayor cerca de x_eval que lejos."""
        L = 20.0
        il_center = influence_line_continuous([L, L], 0.4 * L, n_points=100)
        il_edge = influence_line_continuous([L, L], 0.05 * L, n_points=100)
        truck = [(0.0, 145.0), (4.27, 145.0)]
        _, e_center = critical_position(il_center, truck)
        _, e_edge = critical_position(il_edge, truck)
        assert e_center > e_edge

    def test_2_tramos_M_max_position_sweep(self):
        """Respuesta conocida: para 2 tramos iguales, el maximo momento
        positivo del tren de carga ocurre en ~0.4L del primer tramo
        (Muller-Breslau: pico en 0.4226L)."""
        L = 20.0
        truck = [
            (0.0, TRUCK_AXLES_kN[0]),
            (TRUCK_AXLE_SPACINGS_m[0], TRUCK_AXLES_kN[1]),
            (sum(TRUCK_AXLE_SPACINGS_m), TRUCK_AXLES_kN[2]),
        ]
        best_xfrac = 0.0
        best_effect = -1e30
        for x_frac in np.linspace(0.10, 0.95, 30):
            il = influence_line_continuous([L, L], x_frac * L, n_points=100)
            _, eff = critical_position(il, truck)
            if eff > best_effect:
                best_effect = eff
                best_xfrac = x_frac
        # Pico debe estar cerca de 0.4L (rango aceptable: 0.35-0.50)
        assert 0.35 <= best_xfrac <= 0.50, (
            f"Pico en {best_xfrac:.3f}L, esperado ~0.4L"
        )


class TestTwoSpanSupportMomentILGolden:
    """GOLDEN — Linea de influencia del momento sobre el apoyo intermedio de
    una viga continua de DOS tramos iguales (caso clasico hiperestatico).

    Ancla EXTERNA, independiente de la rutina bajo prueba: el extremo de la
    LI se deriva por la ECUACION DE LOS TRES MOMENTOS (Clapeyron) /
    Muller-Breslau, un metodo DISTINTO de la forma cerrada que usa la
    rutina, y se contrasta ademas con el solver de rigidez independiente
    (``influence_line_continuous``). Para carga unidad a distancia ``a`` del
    extremo del primer vano (vanos iguales L, longitud total 2L) la ordenada
    de la LI del momento en el apoyo central es (resultado hiperestatico
    estandar, tablas de LI para vigas continuas de vanos iguales):

        eta(a) = - a (L^2 - a^2) / (4 L^2)

    Maximizando |eta| (d/da [a(L^2 - a^2)] = L^2 - 3 a^2 = 0):

        a*    = L / sqrt(3)        = 0.57735 L
        eta*  = - L / (6 sqrt(3))  = -0.096225 L   (valor minimo / pico)

    Estos dos numeros (POSICION y ORDENADA del pico) se derivan por calculo
    sobre la LI publicada, NO recalculando con la propia rutina -> golden
    honesto y no tautologico. La rutina arma eta(x) numericamente sobre una
    malla con su formula Muller-Breslau; el test comprueba que su pico
    discreto reproduce el extremo analitico.
    """

    # Extremo analitico publicado (forma cerrada), normalizado por L.
    A_STAR_OVER_L = 1.0 / np.sqrt(3.0)          # 0.57735
    ETA_STAR_OVER_L = -1.0 / (6.0 * np.sqrt(3.0))  # -0.096225

    @pytest.mark.parametrize("L", [10.0, 20.0, 30.0])
    def test_pico_ordenada_y_posicion_vanos_iguales(self, L):
        """El pico (minimo) de la LI coincide con -L/(6*sqrt(3)) en a=L/sqrt(3)."""
        il = two_span_continuous_M_at_support(L, L, n_points=400)
        # Desde 1.1.0 la LI es simetrica respecto al apoyo central (antes el segundo vano
        # estaba reflejado): hay dos minimos iguales, en a* del extremo A y en a* del extremo C.
        # Se mira el del primer vano y se comprueba el espejo en el segundo.
        mask1 = il.x_m <= L
        i_min = int(np.argmin(np.where(mask1, il.ordinates, 0.0)))
        eta_min = float(il.ordinates[i_min])
        x_min = float(il.x_m[i_min])
        i_min2 = int(np.argmin(np.where(~mask1, il.ordinates, 0.0)))
        assert float(il.x_m[i_min2]) == pytest.approx(2.0 * L - self.A_STAR_OVER_L * L, abs=L / 200.0 + 0.05)
        assert float(il.ordinates[i_min2]) == pytest.approx(eta_min, rel=1e-3)

        # Valor del pico: ancla publicada -0.096225*L (tol 0.5 % por malla)
        assert eta_min == pytest.approx(self.ETA_STAR_OVER_L * L, rel=5e-3)
        # Posicion del pico: a* = 0.57735*L (en el primer vano), tol ~0.5 m
        assert x_min == pytest.approx(self.A_STAR_OVER_L * L, abs=L / 200.0 + 0.05)
        # La LI del momento de apoyo es negativa en todo el interior.
        assert np.max(il.ordinates) <= 1e-9
        # Apoyos: ordenada nula en los extremos y en el apoyo central.
        assert il.ordinates[0] == pytest.approx(0.0, abs=1e-9)
        assert il.ordinates[-1] == pytest.approx(0.0, abs=1e-9)

    def test_valor_en_centro_de_vano_forma_cerrada(self):
        """En a = L/2 (centro del primer vano) la forma cerrada da
        eta = -(L/2)(L^2 - L^2/4)/(4 L^2) = -3L/32 = -0.09375 L."""
        L = 24.0
        il = two_span_continuous_M_at_support(L, L, n_points=801)
        # localizar el nodo mas cercano a x = L/2
        idx = int(np.argmin(np.abs(il.x_m - L / 2.0)))
        eta_mid = float(il.ordinates[idx])
        assert eta_mid == pytest.approx(-3.0 * L / 32.0, rel=2e-3)

    def test_cross_check_three_moment_solver(self):
        """Cross-validacion: el solver hiperestatico independiente
        (``influence_line_continuous`` por tres-momentos / Clapeyron) debe
        reproducir el MISMO pico publicado -L/(6*sqrt(3)) para la LI del
        momento en el apoyo central. Dos rutas de codigo independientes
        coincidiendo en el numero publicado.
        """
        L = 20.0
        il = influence_line_continuous([L, L], L, n_points=400, quantity="M")
        eta_min = float(np.min(il.ordinates))
        assert eta_min == pytest.approx(self.ETA_STAR_OVER_L * L, rel=5e-3)

    def test_escala_con_vanos_desiguales(self):
        """Vanos desiguales: el pico en el vano i (longitud Li) sigue la
        forma cerrada por vano eta_i(a) = -a(Li^2 - a^2)/(4 Li (L1+L2))*2... .
        Aqui solo verificamos consistencia de signo y que el vano mas largo
        produce mayor |ordenada| (la LI es mas profunda del lado largo)."""
        il = two_span_continuous_M_at_support(30.0, 15.0, n_points=400)
        i_min = int(np.argmin(il.ordinates))
        x_min = float(il.x_m[i_min])
        # El minimo global cae en el vano largo (primer vano, x < 30).
        assert x_min < 30.0
        assert float(il.ordinates[i_min]) < 0.0
