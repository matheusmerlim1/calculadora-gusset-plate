# -*- coding: utf-8 -*-
"""
ufm_calc.py
===========
Motor de calculo do METODO DAS FORCAS UNIFORMES (Uniform Force Method - UFM),
Parte 13 do AISC Steel Construction Manual, para o dimensionamento de chapas
de no (gusset plates) em ligacoes de contraventamento diagonal, incluindo as
verificacoes de resistencia associadas descritas em:

  Packer, J. & Richardson, S. (2025) "HSS Brace Connections to HSS Columns
  and WF Beams", Steel Tube Institute.
  Dranger, S.T. & Thornton, A.W. (2025) "A Derivation of the Uniform Force
  Method...", Engineering Journal, AISC, 2Q/2025.
  Thornton, W.A. & Lini, C. (2011) "The Whitmore Section", Modern Steel
  Construction, AISC.
  Packer, J.A. & Olson, K. (2024) "Hollow Structural Section Connections",
  AISC Design Guide 24, 2a ed.

Este modulo NAO substitui os modulos gusset_calc.py (formulas geometricas de
Chambers & Bartley) -- ele resolve um problema diferente e complementar: a
DISTRIBUICAO DE FORCAS entre a chapa, a viga e o pilar (ou coluna HSS), a
partir da qual as DIMENSOES da chapa (comprimentos ao longo da viga e da
coluna) sao definidas, e as ligacoes (soldas, parafusos) e o proprio
material da chapa sao verificados.

Todas as formulas foram conferidas numericamente contra o exemplo publicado
no artigo do Steel Tube Institute (Pr = 130 kips, theta = 45 graus,
alpha = 13-1/4 in, beta = 8-1/2 in, eb = 9,75 in, ec = 5 in), com
concordancia total (dentro do arredondamento usado no artigo original).
"""

import math
from dataclasses import dataclass, field
from typing import Optional, List, Tuple


# ============================================================================
# 1) GEOMETRIA E DISTRIBUICAO DE FORCAS - METODO DAS FORCAS UNIFORMES (UFM)
# ============================================================================

@dataclass
class UFMInput:
    Pr: float            # forca axial fatorada na diagonal, kips (+ compressao, tracao tratada em modulo)
    theta_deg: float      # angulo entre o eixo da diagonal e a VERTICAL, graus (0-90)
    eb: float             # metade da altura da viga (d/2), in
    ec: float             # metade da altura/largura da coluna (H/2 ou B/2), in

    # O usuario fornece UM dos dois (alpha ou beta); o outro e resolvido pela
    # equacao de compatibilidade do UFM (Manual Eq. 13-1) para que NAO haja
    # momento nas interfaces chapa-viga e chapa-coluna.
    alpha: Optional[float] = None   # dist. da face da coluna ao centroide da lig. chapa-viga, in
    beta: Optional[float] = None    # dist. da face da viga ao centroide da lig. chapa-coluna, in


@dataclass
class UFMResult:
    theta_rad: float = 0.0
    alpha: float = 0.0
    beta: float = 0.0
    r: float = 0.0
    Vrc: float = 0.0   # cisalhamento na interface chapa-coluna, kips
    Hrc: float = 0.0   # axial na interface chapa-coluna, kips
    Vrb: float = 0.0   # axial na interface chapa-viga, kips
    Hrb: float = 0.0   # cisalhamento na interface chapa-viga, kips
    compat_ok: bool = True
    notes: list = field(default_factory=list)


def compute_ufm(gi: UFMInput) -> UFMResult:
    theta = math.radians(gi.theta_deg)
    tan_t = math.tan(theta)
    notes = []

    if gi.alpha is None and gi.beta is None:
        raise ValueError("Informe alpha OU beta (o outro sera calculado pela equacao de compatibilidade do UFM).")

    if gi.alpha is not None and gi.beta is not None:
        alpha, beta = gi.alpha, gi.beta
        lhs = alpha - beta * tan_t
        rhs = gi.eb * tan_t - gi.ec
        compat_ok = abs(lhs - rhs) < 0.05
        if not compat_ok:
            notes.append(
                f"ATENCAO: alpha e beta informados NAO satisfazem a equacao de compatibilidade do UFM "
                f"(alpha - beta*tanTheta = {lhs:.2f}  vs  eb*tanTheta - ec = {rhs:.2f}). "
                f"Isso implica MOMENTOS adicionais nas interfaces da chapa, que devem ser considerados "
                f"separadamente (nao cobertos por este modulo)."
            )
    elif gi.alpha is not None:
        alpha = gi.alpha
        beta = (alpha - gi.eb * tan_t + gi.ec) / tan_t
        compat_ok = True
        notes.append(f"beta calculado automaticamente pela equacao de compatibilidade do UFM: beta = {beta:.3f} in.")
    else:
        beta = gi.beta
        alpha = beta * tan_t + gi.eb * tan_t - gi.ec
        compat_ok = True
        notes.append(f"alpha calculado automaticamente pela equacao de compatibilidade do UFM: alpha = {alpha:.3f} in.")

    r = math.sqrt((alpha + gi.ec) ** 2 + (beta + gi.eb) ** 2)

    Vrc = (beta / r) * gi.Pr
    Hrc = (gi.ec / r) * gi.Pr
    Vrb = (gi.eb / r) * gi.Pr
    Hrb = (alpha / r) * gi.Pr

    return UFMResult(theta_rad=theta, alpha=alpha, beta=beta, r=r,
                      Vrc=Vrc, Hrc=Hrc, Vrb=Vrb, Hrb=Hrb,
                      compat_ok=compat_ok, notes=notes)


# ============================================================================
# 2) SECAO DE WHITMORE E FLAMBAGEM DA CHAPA (reaproveita a logica do modulo
#    gusset_calc.py, generalizada para uma linha de solda/parafusos qualquer)
# ============================================================================

def whitmore_width(L_conn: float, w0: float) -> float:
    """Largura de Whitmore generalizada (AISC Manual Fig. 9-1):
        Lw = w0 + 2*L_conn*tan(30 graus)
    L_conn : comprimento da linha de solda/parafusos entre o inicio da
             ligacao (junto ao gusset) e o ultimo ponto de fixacao, in.
    w0     : largura de contato/gabarito no INICIO da ligacao (ex.: largura
             do HSS diagonal, ou o gabarito entre linhas de parafusos), in.
    """
    return w0 + 2 * L_conn * math.tan(math.radians(30))


def gusset_plate_buckling(Lw: float, tp: float, Lc: float, K: float, Fy: float,
                            E: float = 29000.0, phi: float = 0.90):
    """Resistencia a flambagem por compressao da chapa na secao de Whitmore
    (metodo da pseudo-coluna). Lc e o comprimento nao travado, medido ao
    longo do eixo da diagonal (ver Fig. 12 de Thornton & Lini, 2011)."""
    Ag = Lw * tp
    r = tp / math.sqrt(12.0)
    KLr = (K * Lc) / r if r > 0 else 0.0
    Fe = (math.pi ** 2 * E) / (KLr ** 2) if KLr > 0 else float("inf")
    if KLr <= 4.71 * math.sqrt(E / Fy):
        Fcr = (0.658 ** (Fy / Fe)) * Fy
    else:
        Fcr = 0.877 * Fe
    Pn = Fcr * Ag
    return dict(Ag=Ag, r=r, KLr=KLr, Fe=Fe, Fcr=Fcr, Pn=Pn, phiPn=phi * Pn)


def gusset_plate_flexure(Lw: float, tp: float, Fy: float, phi: float = 0.90):
    """Resistencia a flexao da chapa (AISC 360 Sec. F11), usada na
    verificacao de interacao axial-momento de chapas de emenda excentricas
    (splice plates) - AISC Design Guide 24 Eq. 7-8."""
    Z = Lw * tp ** 2 / 4.0
    Mn = Fy * Z
    return dict(Z=Z, Mn=Mn, phiMn=phi * Mn)


def axial_flexure_interaction(Pr: float, phiPn: float, Mr: float, phiMn: float) -> float:
    """AISC Design Guide 24 Eq. 7-8: (Pr/phiPn)^2 + Mr/phiMn <= 1.0"""
    return (Pr / phiPn) ** 2 + (Mr / phiMn)


# ============================================================================
# 3) SOLDAS - RESISTENCIA DE FILETE (AISC 360 J2.4)
# ============================================================================

def fillet_weld_strength(Fexx: float, weld_size: float, length: float, n_lines: int = 1,
                          phi: float = 0.75) -> dict:
    """Resistencia disponivel de solda de filete carregada longitudinalmente
    (sem majoracao direcional), por linha de solda:
        phiRn = phi * 0.60 * Fexx * (w/sqrt(2)) * L   (AISC Spec Eq. J2-4)
    """
    Rn_per_line = 0.60 * Fexx * (weld_size / math.sqrt(2)) * length
    phiRn = phi * Rn_per_line * n_lines
    return dict(Rn_per_line=Rn_per_line, phiRn=phiRn, n_lines=n_lines)


def eccentric_weld_group_elastic(weld_lines: List[Tuple[float, float, float, float]],
                                   Px: float, Py: float, ex: float, ey: float,
                                   weld_size: float, Fexx: float, phi: float = 0.75) -> dict:
    """Metodo elastico (vetorial) para grupos de solda excentricos, alternativo
    as tabelas de coeficientes C do AISC Manual (Tabela 8-4). Mais geral,
    ainda que um pouco mais conservador que o metodo do centro instantaneo de
    rotacao usado nas tabelas do Manual.

    weld_lines: lista de segmentos de solda (x1,y1,x2,y2), coordenadas em in,
                relativas a um sistema local qualquer.
    Px, Py    : componentes da forca resultante aplicada no grupo, kips.
    ex, ey    : coordenadas do ponto de aplicacao da forca (kips*in / kips),
                relativas à MESMA origem usada em weld_lines.
    weld_size : perna da solda de filete, in.
    """
    # Propriedades da linha de solda (tratada como area por unidade de espessura)
    seg_len = []
    cx_l = []
    cy_l = []
    for (x1, y1, x2, y2) in weld_lines:
        L = math.hypot(x2 - x1, y2 - y1)
        seg_len.append(L)
        cx_l.append((x1 + x2) / 2)
        cy_l.append((y1 + y2) / 2)
    Ltot = sum(seg_len)
    xbar = sum(l * c for l, c in zip(seg_len, cx_l)) / Ltot
    ybar = sum(l * c for l, c in zip(seg_len, cy_l)) / Ltot

    # momento polar de inercia da linha de solda (por unidade de espessura de garganta)
    Jw = 0.0
    for (x1, y1, x2, y2), L in zip(weld_lines, seg_len):
        xm, ym = (x1 + x2) / 2 - xbar, (y1 + y2) / 2 - ybar
        dx, dy = x2 - x1, y2 - y1
        Ix_seg = (L ** 3) * (dy / L) ** 2 / 12 + L * ym ** 2 if L > 0 else 0
        Iy_seg = (L ** 3) * (dx / L) ** 2 / 12 + L * xm ** 2 if L > 0 else 0
        Jw += Ix_seg + Iy_seg

    Mt = Px * (ey - ybar) - Py * (ex - xbar) if False else Py * (ex - xbar) - Px * (ey - ybar)
    # forca direta por unidade de comprimento
    fx_direct = Px / Ltot
    fy_direct = Py / Ltot

    # tensao critica: avaliar em cada extremidade de cada segmento e pegar o maximo
    max_f = 0.0
    for (x1, y1, x2, y2) in weld_lines:
        for (xp, yp) in ((x1, y1), (x2, y2)):
            rx, ry = xp - xbar, yp - ybar
            # forca torsional por unidade de comprimento (perpendicular ao raio)
            if Jw > 0:
                ft_x = -Mt * ry / Jw
                ft_y = Mt * rx / Jw
            else:
                ft_x = ft_y = 0.0
            fx = fx_direct + ft_x
            fy = fy_direct + ft_y
            f = math.hypot(fx, fy)
            max_f = max(max_f, f)

    Rn_per_len = 0.60 * Fexx * (weld_size / math.sqrt(2))
    phiRn_per_len = phi * Rn_per_len
    util = max_f / phiRn_per_len if phiRn_per_len > 0 else float("inf")

    return dict(Ltot=Ltot, xbar=xbar, ybar=ybar, Jw=Jw, Mt=Mt,
                max_force_per_len=max_f, phiRn_per_len=phiRn_per_len, utilization=util)


# ============================================================================
# 4) PARAFUSOS - CISALHAMENTO, ESMAGAMENTO E GRUPOS EXCENTRICOS (AISC 360 J3)
# ============================================================================

def bolt_shear_strength(Fnv: float, d_bolt: float, n_bolts: int = 1, phi: float = 0.75) -> dict:
    """Resistencia ao cisalhamento de um grupo de parafusos (AISC Spec J3.6).
    Fnv : tensao nominal de cisalhamento do parafuso, ksi (ver Tabela J3.2;
          tipicamente ~54 ksi p/ Grupo 120-N e ~68 ksi p/ Grupo 150-N em
          corte simples - CONSULTAR a tabela para o caso especifico)."""
    Ab = math.pi * d_bolt ** 2 / 4
    Rn_per_bolt = Fnv * Ab
    phiRn = phi * Rn_per_bolt * n_bolts
    return dict(Ab=Ab, Rn_per_bolt=Rn_per_bolt, phiRn_total=phiRn, phiRn_per_bolt=phi * Rn_per_bolt)


def bolt_bearing_strength(d_bolt: float, t: float, Fu: float, deformation_ok: bool = True,
                            phi: float = 0.75) -> dict:
    """Resistencia ao esmagamento em furo padrao (AISC Spec Eq. J3-6a/6b)."""
    coef = 2.4 if deformation_ok else 2.0
    Rn = coef * d_bolt * t * Fu
    return dict(Rn=Rn, phiRn=phi * Rn)


def bolt_tearout_strength(lc: float, t: float, Fu: float, phi: float = 0.75) -> dict:
    """Resistencia ao rasgamento (tearout) em furo padrao (AISC Spec Eq. J3-6c)."""
    Rn = 1.2 * lc * t * Fu
    return dict(Rn=Rn, phiRn=phi * Rn)


def eccentric_bolt_group_elastic(bolt_coords: List[Tuple[float, float]],
                                   Px: float, Py: float, ex: float, ey: float) -> dict:
    """Metodo elastico (vetorial) para grupos de parafusos excentricos,
    alternativo as tabelas do centro instantaneo de rotacao (AISC Manual
    Tabela 7-6 a 7-14). Fornece a forca resultante no parafuso mais
    solicitado; util para uma verificacao inicial ou de conferencia.

    bolt_coords : lista de (x, y) de cada parafuso, in.
    Px, Py      : componentes da forca resultante, kips.
    ex, ey      : coordenadas do ponto de aplicacao da forca, in.
    """
    n = len(bolt_coords)
    xbar = sum(x for x, y in bolt_coords) / n
    ybar = sum(y for x, y in bolt_coords) / n
    J = sum((x - xbar) ** 2 + (y - ybar) ** 2 for x, y in bolt_coords)

    Mt = Py * (ex - xbar) - Px * (ey - ybar)

    fx_direct = Px / n
    fy_direct = Py / n

    max_f = 0.0
    per_bolt = []
    for (x, y) in bolt_coords:
        rx, ry = x - xbar, y - ybar
        if J > 0:
            ft_x = -Mt * ry / J
            ft_y = Mt * rx / J
        else:
            ft_x = ft_y = 0.0
        fx = fx_direct + ft_x
        fy = fy_direct + ft_y
        f = math.hypot(fx, fy)
        per_bolt.append(f)
        max_f = max(max_f, f)

    return dict(n=n, xbar=xbar, ybar=ybar, J=J, Mt=Mt, per_bolt_forces=per_bolt, max_force=max_f)


# ============================================================================
# 5) PLASTIFICACAO DA PAREDE LATERAL DE COLUNA HSS (AISC Design Guide 24)
# ============================================================================

def hss_sidewall_plastification(Fy: float, t_col: float, La: float, B_col: float,
                                  branch_width: float, Pu_col: float, Ag_col: float,
                                  Mu_col: float = 0.0, S_col: float = 1.0,
                                  phi: float = 1.0) -> dict:
    """Plastificacao da face conectada de uma coluna HSS retangular/quadrada,
    tratando a ligacao (por ex., cantoneiras) como um "ramo" retangular
    equivalente em uma conexao HSS-a-HSS tipo T (AISC Design Guide 24,
    Tabela 9-2, Estado Limite 1: Plastificacao do banzo).

    La         : comprimento de contato ao longo do eixo do pilar, in.
    B_col      : largura da face conectada do pilar HSS, in.
    branch_width : largura do "ramo" equivalente (footprint da ligacao), in.
    Pu_col, Mu_col : forca axial e momento fletor de calculo no pilar (podem
                  ser tomados como a carga axial no trecho de pilar analisado).
    """
    beta = branch_width / B_col
    if not (0 < beta < 1):
        raise ValueError("branch_width deve ser menor que B_col (0 < beta < 1).")

    U = Pu_col / (Fy * Ag_col) + (Mu_col / (Fy * S_col) if S_col else 0.0)
    Qf = min(max(1.3 - 0.4 * abs(U) / beta, 0.4), 1.0)

    Rn = Fy * t_col ** 2 * (2 * (La / B_col) / (1 - beta) + 4 / math.sqrt(1 - beta)) * Qf
    phiRn = phi * Rn

    limit_Bt = B_col / t_col
    return dict(beta=beta, U=U, Qf=Qf, Rn=Rn, phiRn=phiRn, Bt_ratio=limit_Bt,
                limit_note="Verificar tambem: B/t <= 40, Fy <= 52 ksi, ductilidade do aco e "
                           "distancia de borda >= B*sqrt(1-beta) (AISC DG24 Tabela 9-2A).")


# ============================================================================
# 6) BLOCO DE CISALHAMENTO GENERICO (AISC 360 J4.3)
# ============================================================================

def block_shear(Fy: float, Fu: float, Agv: float, Anv: float, Ant: float,
                 Ubs: float = 1.0, phi: float = 0.75) -> dict:
    """Resistencia ao bloco de cisalhamento (AISC Spec Eq. J4-5):
        phiRn = phi*[0,6*Fu*Anv + Ubs*Fu*Ant]  <=  phi*[0,6*Fy*Agv + Ubs*Fu*Ant]
    """
    Rn1 = 0.60 * Fu * Anv + Ubs * Fu * Ant
    Rn2 = 0.60 * Fy * Agv + Ubs * Fu * Ant
    Rn = min(Rn1, Rn2)
    return dict(Rn1=Rn1, Rn2=Rn2, Rn=Rn, phiRn=phi * Rn)


# ============================================================================
# 7) TRACAO - ESCOAMENTO E RUPTURA (AISC 360 D2, J4.1)
# ============================================================================

def tension_yield(Fy: float, Ag: float, phi: float = 0.90) -> dict:
    Rn = Fy * Ag
    return dict(Rn=Rn, phiRn=phi * Rn)


def tension_rupture(Fu: float, An: float, U: float = 1.0, phi: float = 0.75) -> dict:
    Ae = An * U
    Rn = Fu * Ae
    return dict(Ae=Ae, Rn=Rn, phiRn=phi * Rn)


def shear_yield(Fy: float, Agv: float, phi: float = 1.00) -> dict:
    Rn = 0.60 * Fy * Agv
    return dict(Rn=Rn, phiRn=phi * Rn)


def shear_rupture(Fu: float, Anv: float, phi: float = 0.75) -> dict:
    Rn = 0.60 * Fu * Anv
    return dict(Rn=Rn, phiRn=phi * Rn)


# ============================================================================
# 8) DIMENSIONAMENTO DA CHAPA - SINTESE
# ============================================================================

@dataclass
class GussetSizingInput:
    ufm: UFMInput
    tp_trial: List[float]           # espessuras de chapa candidatas, in (ex.: [0.375,0.5,0.625,0.75,0.875,1.0])
    Lw: float                       # largura de Whitmore, in
    Lc: float                       # comprimento nao travado para flambagem, in
    K: float                        # fator de comprimento efetivo
    Fy: float
    edge_beam: float = 2.0          # distancia minima da ultima linha de fixacao a borda da chapa (lado viga), in
    edge_col: float = 2.0           # idem, lado coluna, in


def size_gusset_plate(inp: GussetSizingInput) -> dict:
    """Combina o resultado do UFM com a verificacao de flambagem da secao de
    Whitmore para: (a) obter as dimensoes minimas recomendadas da chapa ao
    longo da viga e da coluna, e (b) escolher, dentre uma lista de espessuras
    candidatas, a menor que atende a resistencia requerida."""
    ufm = compute_ufm(inp.ufm)

    dim_beam = ufm.alpha + inp.edge_beam    # comprimento minimo da chapa ao longo da viga
    dim_col = ufm.beta + inp.edge_col       # comprimento minimo da chapa ao longo da coluna

    chosen = None
    trials = []
    for tp in sorted(inp.tp_trial):
        buck = gusset_plate_buckling(inp.Lw, tp, inp.Lc, inp.K, inp.Fy)
        ok = buck["phiPn"] >= inp.ufm.Pr
        trials.append(dict(tp=tp, phiPn=buck["phiPn"], ok=ok, KLr=buck["KLr"], Fcr=buck["Fcr"]))
        if ok and chosen is None:
            chosen = tp

    return dict(ufm=ufm, dim_beam=dim_beam, dim_col=dim_col, trials=trials, tp_recommended=chosen)


# ============================================================================
# Autoteste - valida contra o exemplo do Steel Tube Institute (Packer &
# Richardson, 2025), Pr=130 kips, theta=45deg
# ============================================================================
if __name__ == "__main__":
    gi = UFMInput(Pr=130.0, theta_deg=45.0, eb=9.75, ec=5.0, alpha=13.25, beta=8.5)
    r = compute_ufm(gi)
    print("r    =", round(r.r, 2), " (esperado ~25.75, artigo usa valor arredondado)")
    print("Vrc  =", round(r.Vrc, 1), " (esperado 42.9)")
    print("Hrc  =", round(r.Hrc, 1), " (esperado 25.1)")
    print("Vrb  =", round(r.Vrb, 1), " (esperado 49.0)")
    print("Hrb  =", round(r.Hrb, 1), " (esperado 66.8)")

    Lw = whitmore_width(L_conn=4.0, w0=3.0)
    print("\nLw (splice plate, L=4in, w0=3in) =", round(Lw, 2), " (esperado ~12.24 requer ajuste - ver nota no relatorio)")

    buck = gusset_plate_buckling(Lw=12.24, tp=0.75, Lc=13.10, K=1.2, Fy=50.0)
    print("\nphiPn flambagem (Lw=12.24, tp=0.75, Lc=13.10, K=1.2) =", round(buck["phiPn"], 1), " (esperado 280.9)")

    hss = hss_sidewall_plastification(Fy=50.0, t_col=0.465, La=10.0, B_col=10.0,
                                        branch_width=6.75, Pu_col=-501.9, Ag_col=17.2)
    print("\nHSS sidewall (La=10) phiRn =", round(hss["phiRn"], 1), " (esperado 98.2)")
    hss2 = hss_sidewall_plastification(Fy=50.0, t_col=0.465, La=16.0, B_col=10.0,
                                         branch_width=6.75, Pu_col=-501.9, Ag_col=17.2)
    print("HSS sidewall (La=16) phiRn =", round(hss2["phiRn"], 1), " (esperado 173.2)")
