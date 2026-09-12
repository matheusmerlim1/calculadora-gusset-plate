"""Gera tests/fixtures_whitmore.json a partir do motor Python.

Os valores servem de referencia para tests/test_whitmore_js.mjs, que
verifica se o porte em JavaScript usado na pagina (js/whitmore.js)
reproduz os mesmos numeros de src/gusset_calc.py.

Uso:
    python tools/gen_js_fixtures.py
"""
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "src"))

from gusset_calc import GussetInput, compute_geometry, strength_checks  # noqa: E402

# (L, s, tp, Fy, K, E, Lc, Pu) - Lc e o comprimento de pseudo-coluna, que na
# pagina o usuario informa direto, em vez de deduzir da geometria completa.
CASOS = [
    (13.0, 3.0, 0.500, 50.0, 0.50, 29000.0, 5.046325, 127.0),
    (8.0, 0.0, 0.375, 36.0, 1.00, 29000.0, 10.046325, 90.0),
    (20.0, 5.5, 0.750, 50.0, 0.65, 29000.0, 12.0, 400.0),
    (6.0, 2.0, 0.250, 36.0, 1.20, 29000.0, 18.0, 40.0),
    (13.0, 3.0, 0.500, 50.0, 0.50, 29000.0, 0.0, 127.0),  # pseudo-coluna nula
    (10.0, 1.5, 0.625, 65.0, 1.00, 29000.0, 30.0, 150.0),  # esbelta: ramo elastico
]


def valores(L, s, tp, Fy, K, E, Lc, Pu):
    """Aplica as mesmas formulas de strength_checks(), porem com Lc dado.

    strength_checks() deduz Lc da media de L1/L2/L3; aqui o comprimento e
    uma entrada, entao a geometria serve so para obter Lw pelo motor real.
    """
    import math

    gi = GussetInput(
        H=20.0, W=21.5, a=19.7, b=14.5, L=L, Le=2, s=s,
        theta_b_deg=15.0, theta_c_deg=30.0,
        theta_bb_deg=-10.0, theta_cc_deg=-8.0,
        tp=tp, Fy=Fy, Fu=65.0, Pu=Pu, phi_y=0.90, phi_c=0.90, K=K, E=E,
    )
    res = compute_geometry(gi)
    Lw = res.Lw
    Aw = Lw * tp

    phiPn_yield = 0.90 * Fy * Aw

    r = tp / math.sqrt(12.0)
    KL_r = (K * Lc) / r if r > 0 else 0.0
    Fe = (math.pi ** 2 * E) / (KL_r ** 2) if KL_r > 0 else float("inf")
    if KL_r <= 4.71 * math.sqrt(E / Fy):
        Fcr = (0.658 ** (Fy / Fe)) * Fy
    else:
        Fcr = 0.877 * Fe
    phiPn_buckling = 0.90 * Fcr * Aw

    return dict(
        entrada=dict(L=L, s=s, tp=tp, Fy=Fy, K=K, E=E, Lc=Lc, Pu=Pu),
        Lw=Lw, Aw=Aw, r=r, KL_r=KL_r, Fcr=Fcr,
        phiPn_yield=phiPn_yield, phiPn_buckling=phiPn_buckling,
        governing=min(phiPn_yield, phiPn_buckling),
        DCR_yield=Pu / phiPn_yield, DCR_buckling=Pu / phiPn_buckling,
    )


def main():
    dados = [valores(*c) for c in CASOS]
    destino = os.path.join(RAIZ, "tests", "fixtures_whitmore.json")
    with open(destino, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(dados, fh, indent=2)
        fh.write("\n")
    print("gerado:", destino, "-", len(dados), "casos")


if __name__ == "__main__":
    main()
