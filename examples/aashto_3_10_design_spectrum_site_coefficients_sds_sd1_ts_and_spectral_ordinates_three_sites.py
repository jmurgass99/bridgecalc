"""Espectro de diseño sísmico AASHTO LRFD §3.10.4 para tres emplazamientos: A_s = F_pga·PGA, S_DS = F_a·S_s, S_D1 = F_v·S_1, periodos T_0 y T_s y ordenadas Sa(T) en los periodos típicos de pilas.

`aashto_design_spectrum` construye el espectro de tres ramas (lineal hasta T_0, meseta hasta T_s,
S_D1/T después) a partir de PGA, S_s, S_1 y los coeficientes de sitio F_pga, F_a, F_v (Tablas
3.10.3.2-1 a -3). Se comparan clase B (roca), D (suelo rígido) y E (suelo blando) para los mismos
valores de roca y se lee la aceleración espectral de pilas con T = 0,4, 0,8 y 1,5 s.

Ejecutar:  python examples/aashto_3_10_design_spectrum_site_coefficients_sds_sd1_ts_and_spectral_ordinates_three_sites.py
"""
import numpy as np

from bridgecalc.seismic import AASHTOSeismicInput, aashto_design_spectrum


def main() -> None:
    PGA, Ss, S1 = 0.40, 1.00, 0.40
    sitios = {"B (roca)": (1.0, 1.0, 1.0), "D (suelo rígido)": (1.1, 1.1, 1.6), "E (suelo blando)": (0.9, 0.9, 2.4)}
    print(f"Valores de roca: PGA = {PGA} g, S_s = {Ss} g, S_1 = {S1} g. Coeficientes de sitio (F_pga, F_a, F_v) de las Tablas 3.10.3.2-1/2/3 para esos niveles:\n")
    print(f"  {'clase':17} {'F_pga':>5} {'F_a':>4} {'F_v':>4} {'A_s':>6} {'S_DS':>6} {'S_D1':>6} {'T_0 [s]':>7} {'T_s [s]':>7}")
    res = {}
    for nombre, (fpga, fa, fv) in sitios.items():
        r = aashto_design_spectrum(AASHTOSeismicInput(PGA_g=PGA, Ss_g=Ss, S1_g=S1, Fpga=fpga, Fa=fa, Fv=fv), periods=[0.0, 0.1, 0.2, 0.4, 0.6, 0.8, 1.0, 1.5, 2.0, 3.0, 4.0])
        res[nombre] = r
        print(f"  {nombre:17} {fpga:5.1f} {fa:4.1f} {fv:4.1f} {fpga * PGA:6.3f} {r.SDS:6.3f} {r.SD1:6.3f} {r.T0:7.3f} {r.Ts:7.3f}")
    print(f"\n  {'T [s]':>5} " + " ".join(f"{n:>17}" for n in sitios))
    for i, (T, _) in enumerate(res["B (roca)"].Sa_T_g):
        print(f"  {T:5.2f} " + " ".join(f"{res[n].Sa_T_g[i][1]:17.3f}" for n in sitios))
    print("\nLectura para pilas (Sa en g):")
    for T in (0.4, 0.8, 1.5):
        vals = []
        for n, r in res.items():
            Ts, SD1, SDS = r.Ts, r.SD1, r.SDS
            Sa = SDS if T <= Ts else SD1 / T
            vals.append(f"{n.split()[0]} {Sa:.3f}")
        print(f"  T = {T} s: " + ", ".join(vals))
    r_e = res["E (suelo blando)"]
    print(f"\nEn suelo blando la meseta baja (F_a 0,9) pero F_v = 2,4 estira T_s hasta {r_e.Ts:.2f} s: una pila de 1,5 s ve {r_e.SD1 / 1.5:.3f} g frente a {res['B (roca)'].SD1 / 1.5:.3f} g en roca, ×{(r_e.SD1 / 1.5) / (res['B (roca)'].SD1 / 1.5):.1f}.")
    print("La función no interpola los coeficientes de sitio entre niveles de aceleración ni fija la categoría SDC (A–D, Tabla 3.10.6-1); dale los F de la tabla y clasifica fuera. Sa(0) = A_s, sin rama de periodo largo T_L.")


if __name__ == "__main__":
    main()
