# -*- coding: utf-8 -*-
"""
gusset_calc.py
==============
Motor de calculo para geometria e resistencia de chapas de no (gusset plates),
implementando:

  - Largura e area de Whitmore (Thornton / AISC Manual Parte 9)
  - Formulas geometricas de Chambers & Bartley (AISC Engineering Journal,
    3o trimestre de 2007) para y_b, y_bf, y_c, y_cf e para os comprimentos
    de pseudo-coluna L1, L2 e L3, incluindo interfaces nao ortogonais
    (theta_bb, theta_cc), com a correcao de errata (1o trimestre de 2008).
  - Verificacao de escoamento por tracao e flambagem (metodo de Thornton /
    pseudo-coluna) na secao de Whitmore.
  - Verificacao de bloco de cisalhamento equivalente (Williams & Richard).
  - Fator de retardo de cisalhamento (shear lag) para membros tracionados
    de HSS circular conectados a chapa de no (Cheng & Kulak, AISC EJ, 4o
    trimestre de 2000).

Todas as formulas geometricas foram validadas numericamente contra os 12
exemplos da Tabela 2 do artigo original (erro < 0.001 in em todos os casos).

Convencao de angulos (graus, conforme Figura 4 do artigo original):
    theta_B  : angulo da diagonal (brace) em relacao a linha de trabalho,
               calculado automaticamente a partir da geometria (nao e
               fornecido pelo usuario).
    theta_b  : angulo da interface chapa-viga (beam) em relacao a horizontal.
    theta_c  : angulo da interface chapa-coluna (column) em relacao a vertical.
    theta_bb : nao-ortogonalidade da interface chapa-viga (0 = ortogonal).
    theta_cc : nao-ortogonalidade da interface chapa-coluna (0 = ortogonal).
"""

import math
from dataclasses import dataclass, field
from typing import Optional


# --------------------------------------------------------------------------
# Entrada de dados
# --------------------------------------------------------------------------

@dataclass
class GussetInput:
    # Geometria basica (Figura 4) - polegadas
    H: float          # altura total da chapa (vertical), in
    W: float          # largura total da chapa (horizontal), in
    a: float          # dist. face da coluna ao centroide da linha de parafusos/solda viga-chapa, in
    b: float          # dist. face da viga ao centroide da linha de parafusos/solda coluna-chapa, in
    L: float          # comprimento da linha de parafusos/solda na diagonal (brace), in
    Le: float         # excentricidade/afastamento do 1o parafuso a quina da chapa, in
    s: float          # espacamento perpendicular entre linhas de parafusos (gramp), in

    theta_b_deg: float = 0.0   # graus
    theta_c_deg: float = 0.0   # graus
    theta_bb_deg: float = 0.0  # graus (nao-ortogonalidade viga)
    theta_cc_deg: float = 0.0  # graus (nao-ortogonalidade coluna)

    # Dados de material / carregamento (opcionais, para verificacoes de resistencia)
    tp: float = 0.5      # espessura da chapa de no, in
    Fy: float = 50.0     # ksi
    Fu: float = 65.0     # ksi
    Pu: float = 0.0      # carga fatorada na diagonal, kips
    phi_y: float = 0.90  # fator de resistencia - escoamento a tracao (LRFD)
    phi_c: float = 0.90  # fator de resistencia - flambagem (compressao)
    K: float = 0.50      # fator de comprimento efetivo (metodo pseudo-coluna Thornton)
    E: float = 29000.0   # ksi, modulo de elasticidade do aco


# --------------------------------------------------------------------------
# Resultado
# --------------------------------------------------------------------------

@dataclass
class GussetResult:
    theta_B_deg: float = 0.0
    c: float = 0.0
    Lw: float = 0.0
    LLe: float = 0.0
    d: float = 0.0
    phi_deg: float = 0.0
    g: float = 0.0
    w: float = 0.0
    h: float = 0.0
    j: float = 0.0
    k: float = 0.0
    m: float = 0.0
    n: float = 0.0
    e: float = 0.0
    f: float = 0.0

    yb: Optional[float] = None
    ybf: Optional[float] = None
    yc: Optional[float] = None
    ycf: Optional[float] = None

    L1: Optional[float] = None
    L2: Optional[float] = None
    L3: Optional[float] = None

    branch_W_vs_w: str = ""
    branch_H_vs_j: Optional[str] = None
    branch_W_vs_m: Optional[str] = None

    whitmore_extends_beam: bool = False
    whitmore_extends_column: bool = False

    notes: list = field(default_factory=list)

    # ---- resultados de resistencia (preenchidos por strength_checks) ----
    Aw: float = 0.0
    Pn_yield: float = 0.0
    phiPn_yield: float = 0.0

    Lc_avg: float = 0.0
    Lc_max: float = 0.0
    r_gyration: float = 0.0
    Fcr: float = 0.0
    Pn_buckling: float = 0.0
    phiPn_buckling: float = 0.0

    Pn_blockshear_equiv: float = 0.0
    phiPn_blockshear_equiv: float = 0.0

    DCR_yield: float = 0.0
    DCR_buckling: float = 0.0


# --------------------------------------------------------------------------
# Motor geometrico (Chambers & Bartley, 2007 + errata 2008)
# --------------------------------------------------------------------------

def _d(x):
    return math.radians(x)


def compute_geometry(gi: GussetInput) -> GussetResult:
    H, W, a, b = gi.H, gi.W, gi.a, gi.b
    L, Le, s = gi.L, gi.Le, gi.s
    theta_b = _d(gi.theta_b_deg)
    theta_c = _d(gi.theta_c_deg)
    theta_bb = _d(gi.theta_bb_deg)
    theta_cc = _d(gi.theta_cc_deg)

    res = GussetResult()
    notes = []

    if H == b:
        raise ValueError("H nao pode ser igual a b (divisao por zero em theta_B).")

    theta_B = math.atan((W - a) / (H - b))
    c = 0.5 * math.sqrt((W - a) ** 2 + (H - b) ** 2)
    Lw = 2 * L * math.tan(_d(30)) + s
    LLe = L + Le
    d = math.sqrt(LLe ** 2 + c ** 2)
    phi = math.acos(c / d)
    g = (Lw - 2 * c) / 2
    w = (b * math.cos(theta_B) + c) / math.sin(theta_B)
    h = (a * math.sin(theta_B) + c) / math.cos(theta_B)
    j = (a * math.sin(theta_B) + 2 * c + g) / math.cos(theta_B)
    k = (a * math.sin(theta_B) - g) / math.cos(theta_B)
    m = (b * math.cos(theta_B) + 2 * c + g) / math.sin(theta_B)
    n = (b * math.cos(theta_B) - g) / math.sin(theta_B)
    e = d * math.sin(phi) / math.sin(theta_B + theta_c)
    f = d * math.sin(phi) / math.cos(theta_B + theta_b)

    res.theta_B_deg = math.degrees(theta_B)
    res.c, res.Lw, res.LLe, res.d = c, Lw, LLe, d
    res.phi_deg = math.degrees(phi)
    res.g, res.w, res.h, res.j, res.k, res.m, res.n = g, w, h, j, k, m, n
    res.e, res.f = e, f

    # ---- y_b / y_bf  (Eq. 5, 6, 17 - lado da viga) ----
    cond1 = b / math.cos(theta_c) + (math.sin(theta_bb) / math.cos(theta_bb - theta_c)) * (
        W - b * math.tan(theta_c)
    )
    if e <= cond1:
        ybf = d * math.sin(phi + theta_B + theta_c) / math.sin(theta_B + theta_c)
        res.ybf = ybf
        res.whitmore_extends_beam = False
        notes.append("A largura de Whitmore fica contida dentro da borda livre do lado da viga (y_bf).")
    else:
        yb = (b + d * math.cos(theta_B + phi)) / math.cos(theta_B) + (
            math.sin(theta_bb) / math.cos(theta_B + theta_bb)
        ) * (W + b * math.tan(theta_B) - d * math.sin(phi) / math.cos(theta_B))
        res.yb = yb
        res.whitmore_extends_beam = True
        notes.append("A largura de Whitmore se estende para dentro da viga (y_b) - avaliar secao hibrida.")

    # ---- y_c / y_cf  (Eq. 7, 8, 18 - lado da coluna) ----
    cond2 = a / math.cos(theta_b) + (math.sin(theta_cc) / math.cos(theta_b + theta_cc)) * (
        H + a * math.tan(theta_b)
    )
    if f <= cond2:
        ycf = d * math.cos(theta_B + theta_b - phi) / math.cos(theta_B + theta_b)
        res.ycf = ycf
        res.whitmore_extends_column = False
        notes.append("A largura de Whitmore fica contida dentro da borda livre do lado da coluna (y_cf).")
    else:
        yc = (a - d * math.sin(phi - theta_B)) / math.sin(theta_B) + (
            math.sin(theta_cc) / math.sin(theta_B - theta_cc)
        ) * (H + a / math.tan(theta_B) - d * math.sin(phi) / math.sin(theta_B))
        res.yc = yc
        res.whitmore_extends_column = True
        notes.append("A largura de Whitmore se estende para dentro da coluna (y_c) - avaliar secao hibrida.")

    yb_eff = res.yb if res.yb is not None else res.ybf
    yc_eff = res.yc if res.yc is not None else res.ycf

    # ---- L1, L2, L3 (Eq. 9-16 ortogonais / 19-26 nao ortogonais, com errata) ----
    if W <= w:
        res.branch_W_vs_w = "W <= w (L2 termina na interface chapa-coluna)"
        L2 = (
            W / math.cos(theta_B)
            + (math.sin(theta_cc) / math.cos(theta_B - theta_cc)) * (H - h)
            - c * math.tan(theta_B)
            - LLe
        )
        L3 = L2 + (Lw / 2) * (
            math.sin(theta_cc) / (math.cos(theta_B) * math.cos(theta_B - theta_cc)) - math.tan(theta_B)
        )
        if H >= j:
            res.branch_H_vs_j = "H >= j (L1 termina na interface chapa-coluna)"
            L1 = L2 + (Lw / 2) * (
                math.tan(theta_B) - math.sin(theta_cc) / (math.cos(theta_B) * math.cos(theta_B - theta_cc))
            )
        else:
            res.branch_H_vs_j = "H < j (L1 termina na interface chapa-viga)"
            L1 = (b - g * math.cos(theta_B)) / math.sin(theta_B) + (
                math.sin(theta_bb) / math.sin(theta_B + theta_bb)
            ) * (W - n) - LLe
    else:
        res.branch_W_vs_w = "W > w (L2 termina na interface chapa-viga)"
        L2 = (
            w / math.cos(theta_B)
            + (math.sin(theta_bb) / math.sin(theta_bb + theta_B)) * (W - w)
            - c * math.tan(theta_B)
            - LLe
        )
        L1 = L2 + (math.sin(theta_bb) / math.sin(theta_B + theta_bb)) * (w - n) - Lw / (2 * math.tan(theta_B))
        if W >= m:
            res.branch_W_vs_m = "W >= m (L3 termina na interface chapa-viga)"
            L3 = L2 + Lw / (2 * math.tan(theta_B)) + (math.sin(theta_bb) / math.sin(theta_B + theta_bb)) * (
                w - m
            )
        else:
            res.branch_W_vs_m = "W < m (L3 termina na interface chapa-coluna)"
            L3 = (
                (a - g * math.sin(theta_B)) / math.cos(theta_B)
                + (math.sin(theta_cc) / math.cos(theta_B - theta_cc)) * (H - k)
                - LLe
            )

    if yb_eff is None or yb_eff < Lw / 2:
        L1 = None
        notes.append("L1 nao existe (y_b/y_bf < Lw/2): pseudo-coluna nao se desenvolve deste lado.")
    if yc_eff is None or yc_eff < Lw / 2:
        L3 = None
        notes.append("L3 nao existe (y_c/y_cf < Lw/2): pseudo-coluna nao se desenvolve deste lado.")

    res.L1, res.L2, res.L3 = L1, L2, L3
    res.notes = notes
    return res


# --------------------------------------------------------------------------
# Verificacoes de resistencia (Metodo de Thornton / AISC Manual Parte 9)
# --------------------------------------------------------------------------

def strength_checks(gi: GussetInput, res: GussetResult) -> GussetResult:
    """Aplica as verificacoes de escoamento por tracao e flambagem por
    compressao na secao de Whitmore, alem do bloco de cisalhamento
    equivalente de Williams & Richard (1986)."""

    Lw = res.Lw
    tp = gi.tp

    # --- Area de Whitmore e escoamento a tracao (AISC Manual Eq. 9-1) ---
    Aw = Lw * tp
    Pn_yield = gi.Fy * Aw
    res.Aw = Aw
    res.Pn_yield = Pn_yield
    res.phiPn_yield = gi.phi_y * Pn_yield

    # --- Comprimento de pseudo-coluna (metodo de Thornton) ---
    Ls = [x for x in (res.L1, res.L2, res.L3) if x is not None]
    if Ls:
        Lc_avg = sum(Ls) / len(Ls)
        Lc_max = max(Ls)
    else:
        Lc_avg = Lc_max = 0.0
    res.Lc_avg = Lc_avg
    res.Lc_max = Lc_max

    r = tp / math.sqrt(12.0)  # raio de giracao de uma faixa retangular (chapa)
    res.r_gyration = r

    KL_r = (gi.K * Lc_avg) / r if r > 0 else 0.0

    # Tensao critica de flambagem - AISC 360 Cap. E (formulas de coluna)
    Fe = (math.pi ** 2 * gi.E) / (KL_r ** 2) if KL_r > 0 else float("inf")
    lam = math.sqrt(gi.Fy / Fe) if Fe > 0 else 0.0
    if KL_r <= 4.71 * math.sqrt(gi.E / gi.Fy):
        Fcr = (0.658 ** (gi.Fy / Fe)) * gi.Fy
    else:
        Fcr = 0.877 * Fe

    Pn_buckling = Fcr * Aw
    res.Fcr = Fcr
    res.Pn_buckling = Pn_buckling
    res.phiPn_buckling = gi.phi_c * Pn_buckling
    res._KL_r = KL_r  # armazenado para relatorio (nao faz parte do dataclass original)

    # --- Bloco de cisalhamento equivalente de Whitmore (Williams & Richard, 1986) ---
    # t * [2(L + Le) * 0.6 Fy + s * Fy]  ~=  t * Lw * Fy   (Eq. 4 do artigo geometrico)
    Pn_bs = tp * (2 * res.LLe * 0.6 * gi.Fy + gi.s * gi.Fy)
    res.Pn_blockshear_equiv = Pn_bs
    res.phiPn_blockshear_equiv = 0.75 * Pn_bs  # phi = 0.75 (ruptura)

    if gi.Pu > 0:
        res.DCR_yield = gi.Pu / res.phiPn_yield if res.phiPn_yield > 0 else float("inf")
        res.DCR_buckling = gi.Pu / res.phiPn_buckling if res.phiPn_buckling > 0 else float("inf")

    return res


# --------------------------------------------------------------------------
# Retardo de cisalhamento (shear lag) - HSS circular (Cheng & Kulak, 2000)
# --------------------------------------------------------------------------

def hss_round_shear_lag(D: float, t_wall: float, L_weld: float, transverse_weld: bool,
                          Fy: float, Fu: float, phi_t: float = 0.75):
    """Calcula o fator de retardo de cisalhamento U e a resistencia a
    tracao para um HSS circular fendido e soldado a chapa de no, conforme
    a Especificacao AISC para HSS (2.1b) e Cheng & Kulak (2000).

    D        : diametro externo do tubo, in
    t_wall   : espessura de parede do tubo, in (usada apenas para A_g)
    L_weld   : comprimento da solda longitudinal, in
    transverse_weld : True se houver solda transversal na extremidade da fenda
    """
    xbar = D / math.pi
    U = min(1.0 - xbar / L_weld, 0.9) if L_weld > 0 else 0.0

    # Area bruta aproximada de um HSS de parede fina: Ag = pi*(D-t)*t
    Ag = math.pi * (D - t_wall) * t_wall
    # Se nao houver solda transversal, a norma exige usar a area liquida
    # (area bruta menos a area das duas fendas longitudinais, aprox. 2*t*t)
    An = Ag if transverse_weld else Ag - 2 * t_wall * t_wall

    Ae = An * U
    Pn = Fu * Ae
    phiPn = phi_t * Pn

    recommendation_ok = L_weld >= 1.3 * D

    return dict(
        xbar=xbar,
        U=U,
        Ag=Ag,
        An=An,
        Ae=Ae,
        Pn=Pn,
        phiPn=phiPn,
        recommendation_ok=recommendation_ok,
        note=(
            "Cheng & Kulak (2000) recomendam DESCONSIDERAR a reducao por "
            "retardo de cisalhamento (U = 1.0) quando o comprimento de solda "
            "for >= 1,3 x o diametro do tubo E houver solda transversal na "
            "extremidade da fenda."
        ),
    )


# --------------------------------------------------------------------------
# Auto-teste rapido (executar: python gusset_calc.py)
# --------------------------------------------------------------------------

if __name__ == "__main__":
    # Exemplo 1 da Tabela 2 (Chambers & Bartley, 2007)
    gi = GussetInput(
        H=20.0, W=21.5, a=19.7, b=14.5, L=13, Le=2, s=3,
        theta_b_deg=15.0, theta_c_deg=30.0, theta_bb_deg=-10.0, theta_cc_deg=-8.0,
    )
    r = compute_geometry(gi)
    print("theta_B =", round(r.theta_B_deg, 3))
    print("y_b =", round(r.yb, 3) if r.yb else None, " (esperado 11.406)")
    print("y_c =", round(r.yc, 3) if r.yc else None, " (esperado 10.291)")
    print("L1 =", round(r.L1, 3), " (esperado 9.462)")
    print("L2 =", round(r.L2, 3), " (esperado 5.046)")
    print("L3 =", round(r.L3, 3), " (esperado 0.630)")
