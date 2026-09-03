# -*- coding: utf-8 -*-
"""
Calculadora de Chapa de No (Gusset Plate) - Whitmore / Pseudo-Coluna / HSS
============================================================================
Aplicativo grafico (Tkinter + Matplotlib) para:

  1) Calcular a largura e a area de Whitmore;
  2) Calcular y_b, y_bf, y_c, y_cf (verificar se a secao de Whitmore
     ultrapassa as bordas da chapa) segundo Chambers & Bartley (2007);
  3) Calcular os comprimentos de pseudo-coluna L1, L2 e L3 (metodo de
     Thornton) para a verificacao de flambagem;
  4) Verificar escoamento por tracao, flambagem por compressao e bloco de
     cisalhamento equivalente na secao de Whitmore (AISC 360 / AISC Manual);
  5) Calcular o fator de retardo de cisalhamento (shear lag) para conexoes
     de HSS circular fendido soldado a chapa de no (Cheng & Kulak, 2000);
  6) Desenhar a geometria da chapa, a secao de Whitmore e as pseudo-colunas
     em um diagrama que se atualiza automaticamente com os dados de entrada;
  7) Exportar um relatorio de calculo em PDF.

Autor: gerado com apoio do Claude (Anthropic) a partir dos artigos tecnicos:
  - Chambers, J.J. & Bartley, T.C. (2007) "Geometric Formulas for Gusset
    Plate Design", Engineering Journal, AISC, 3Q/2007 (+ errata 1Q/2008).
  - Thornton, W.A. & Lini, C. (2011) "The Whitmore Section", Modern Steel
    Construction, AISC, julho/2011.
  - Cheng, J.J.R. & Kulak, G.L. (2000) "Gusset Plate Connection to Round
    HSS Tension Members", Engineering Journal, AISC, 4Q/2000.

Este programa e uma ferramenta de apoio ao calculo. Os resultados devem
ser sempre conferidos por um engenheiro responsavel, conforme as normas
aplicaveis (AISC 360, NBR 8800, etc).
"""

import math
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Polygon, FancyArrowPatch
import numpy as np

from gusset_calc import GussetInput, compute_geometry, strength_checks, hss_round_shear_lag
import ufm_calc

APP_TITLE = "Calculadora de Chapa de No (Gusset Plate) v1.2"


# ============================================================================
# Sistema de unidades (imperial <-> metrico)
# ============================================================================
# O motor de calculo (gusset_calc.py / ufm_calc.py) trabalha SEMPRE em
# unidades imperiais (in, ksi, kips, in2), pois e nessas unidades que as
# formulas foram validadas contra os artigos originais. A conversao para
# milimetros/MPa/kN acontece apenas na camada de interface (entrada e saida).

MM_PER_IN = 25.4
MPA_PER_KSI = 6.894757293168361
KN_PER_KIP = 4.4482216152605

UNIT_LABELS = {
    "imperial": dict(length="in", stress="ksi", force="kips", area="in2"),
    "metric": dict(length="mm", stress="MPa", force="kN", area="mm2"),
}


def to_internal(value, kind, system):
    """Converte um valor do sistema de unidades ATUAL da interface para o
    sistema INTERNO (imperial), usado pelos modulos de calculo."""
    if kind is None or system == "imperial" or value is None:
        return value
    if kind == "length":
        return value / MM_PER_IN
    if kind == "stress":
        return value / MPA_PER_KSI
    if kind == "force":
        return value / KN_PER_KIP
    if kind == "area":
        return value / (MM_PER_IN ** 2)
    return value


def from_internal(value, kind, system):
    """Converte um valor do sistema INTERNO (imperial) para o sistema de
    unidades ATUAL da interface, para exibicao."""
    if kind is None or system == "imperial" or value is None:
        return value
    if kind == "length":
        return value * MM_PER_IN
    if kind == "stress":
        return value * MPA_PER_KSI
    if kind == "force":
        return value * KN_PER_KIP
    if kind == "area":
        return value * (MM_PER_IN ** 2)
    return value


# Tipo de grandeza de cada campo de entrada (None = sem conversao: angulos,
# fatores adimensionais, contagens)
FIELD_UNITS = {
    # ---- aba Geometria ----
    "H": "length", "W": "length", "a": "length", "b": "length",
    "n_bolts": None, "pitch": "length", "Le": "length", "s": "length",
    "theta_b_deg": None, "theta_c_deg": None, "theta_bb_deg": None, "theta_cc_deg": None,
    # ---- aba Material/Carga ----
    "tp": "length", "Fy": "stress", "Fu": "stress", "Pu": "force",
    "phi_y": None, "phi_c": None, "K": None, "E": "stress",
    # ---- aba HSS circular ----
    "hss_D": "length", "hss_t": "length", "hss_Lweld": "length",
    "hss_Fy": "stress", "hss_Fu": "stress",
    # ---- aba UFM ----
    "ufm_Pr": "force", "ufm_theta": None, "ufm_eb": "length", "ufm_ec": "length",
    "ufm_alpha": "length", "ufm_nbolts_brace": None, "ufm_pitch_brace": "length",
    "ufm_w0": "length", "ufm_Lc": "length", "ufm_K": None, "ufm_Fy_plate": "stress",
    "ufm_tp_list": "length_list", "ufm_edge_beam": "length", "ufm_edge_col": "length",
    "ufm_Fexx": "stress", "ufm_weld_size": "length", "ufm_weld_length": "length",
    "ufm_weld_nlines": None, "ufm_Fnv": "stress", "ufm_dbolt": "length",
    "ufm_nbolts": None, "ufm_tply": "length", "ufm_Fuply": "stress",
    "ufm_Fy_col": "stress", "ufm_t_col": "length", "ufm_La": "length",
    "ufm_B_col": "length", "ufm_branch_w": "length", "ufm_Pu_col": "force",
    "ufm_Ag_col": "area",
}


# ============================================================================
# Geometria auxiliar para o desenho (reconstrucao aproximada do contorno da
# chapa a partir dos parametros de entrada, apenas para fins ilustrativos)
# ============================================================================

def draw_gusset(ax, gi: GussetInput, res, unit_label="in", unit_scale=1.0, n_bolts_draw=None):
    """Desenha a chapa de no reproduzindo a geometria da Figura 4 de
    Chambers & Bartley (2007): H e W sao distancias de referencia ao
    longo das interfaces; a e b localizam a quina (corner edge); theta_b
    e theta_c moldam as bordas livres lado-coluna e lado-viga (a partir
    da horizontal e da vertical, respectivamente); theta_bb e theta_cc
    inclinam as proprias interfaces quando nao-ortogonais (Figura 8)."""
    ax.clear()
    H, W, a, b = gi.H * unit_scale, gi.W * unit_scale, gi.a * unit_scale, gi.b * unit_scale
    Le_s = gi.Le * unit_scale
    LLe_s = res.LLe * unit_scale
    Lw_s = res.Lw * unit_scale
    L1_s = res.L1 * unit_scale if res.L1 is not None else None
    L2_s = res.L2 * unit_scale if res.L2 is not None else None
    L3_s = res.L3 * unit_scale if res.L3 is not None else None
    theta_B = math.radians(res.theta_B_deg)
    dirx, diry = math.cos(theta_B), math.sin(theta_B)

    theta_b = math.radians(getattr(gi, "theta_b_deg", 0.0))
    theta_c = math.radians(getattr(gi, "theta_c_deg", 0.0))
    theta_cc = math.radians(getattr(gi, "theta_cc_deg", 0.0))
    theta_bb = math.radians(getattr(gi, "theta_bb_deg", 0.0))

    # --- direcoes das interfaces: nominalmente verticais/horizontais,
    #     inclinadas por theta_cc/theta_bb quando nao-ortogonais (Fig. 8) ---
    col_dir = (math.sin(theta_cc), math.cos(theta_cc))     # interface chapa-coluna
    beam_dir = (math.cos(theta_bb), math.sin(theta_bb))    # interface chapa-viga

    # --- vertices da chapa, EXATAMENTE como na Figura 4: a quina (corner
    #     edge) vai de corner_top a corner_bot; as bordas livres se abrem
    #     a partir dai ate as interfaces, nos angulos theta_b (coluna, da
    #     horizontal) e theta_c (viga, da vertical) ---
    corner_top = (a * beam_dir[0] + H * col_dir[0], a * beam_dir[1] + H * col_dir[1])
    corner_bot = (W * beam_dir[0] + b * col_dir[0], W * beam_dir[1] + b * col_dir[1])
    corner_mid = ((corner_top[0] + corner_bot[0]) / 2, (corner_top[1] + corner_bot[1]) / 2)
    top_left = ((H + a * math.tan(theta_b)) * col_dir[0], (H + a * math.tan(theta_b)) * col_dir[1])
    bot_right = ((W + b * math.tan(theta_c)) * beam_dir[0], (W + b * math.tan(theta_c)) * beam_dir[1])

    outline = [(0, 0), top_left, corner_top, corner_bot, bot_right]
    poly = Polygon(outline, closed=True, fill=True, facecolor="#eaf1fb",
                    edgecolor="#1c3d6e", linewidth=1.8, zorder=1)
    ax.add_patch(poly)

    # --- interfaces (linhas grossas, ao longo de col_dir / beam_dir) ---
    col_far = (-1.0 * col_dir[0], -1.0 * col_dir[1])
    col_near = ((H + 1.0) * col_dir[0], (H + 1.0) * col_dir[1])
    beam_far = (-1.0 * beam_dir[0], -1.0 * beam_dir[1])
    beam_near = ((W + 1.0) * beam_dir[0], (W + 1.0) * beam_dir[1])
    ax.plot([beam_far[0], beam_near[0]], [beam_far[1], beam_near[1]], color="#444444", linewidth=3, zorder=2)
    ax.plot([col_far[0], col_near[0]], [col_far[1], col_near[1]], color="#444444", linewidth=3, zorder=2)
    ax.text(W * beam_dir[0] * 0.5, W * beam_dir[1] * 0.5 - H * 0.08 - 1, "Interface chapa-viga (W)",
            ha="center", fontsize=8, color="#444444",
            rotation=math.degrees(math.atan2(beam_dir[1], beam_dir[0])))
    ax.text(H * col_dir[0] * 0.5 - W * 0.08 - 1, H * col_dir[1] * 0.5, "Interface\nchapa-coluna\n(H)",
            ha="center", fontsize=8, color="#444444", rotation=90 - math.degrees(theta_cc))

    # --- bordas livres (linhas do contorno da chapa, ja incluidas no
    #     poligono, mas realcadas e rotuladas) ---
    ax.plot([top_left[0], corner_top[0]], [top_left[1], corner_top[1]], color="#1c3d6e", linewidth=2.0, zorder=2)
    ax.plot([corner_bot[0], bot_right[0]], [corner_bot[1], bot_right[1]], color="#1c3d6e", linewidth=2.0, zorder=2)
    ax.plot([corner_top[0], corner_bot[0]], [corner_top[1], corner_bot[1]], color="#c0392b", linewidth=2.2, zorder=3)

    # --- linha de trabalho (C.L. diagonal), prolongando-se para FORA da
    #     chapa a partir do meio da quina ---
    Ltot = max(4.0, 0.15 * max(H, W))
    x_end = corner_mid[0] + Ltot * dirx
    y_end = corner_mid[1] + Ltot * diry

    # --- linha de parafusos/solda: comeca perto da quina (afastada por Le)
    #     e avanca PARA DENTRO da chapa (em direcao as interfaces viga/coluna),
    #     conforme Figs. 1, 3 e 4 de Chambers & Bartley (2007) ---
    x0 = corner_mid[0] - Le_s * dirx
    y0 = corner_mid[1] - Le_s * diry
    x1 = corner_mid[0] - LLe_s * dirx
    y1 = corner_mid[1] - LLe_s * diry

    # --- secao de Whitmore (linhas a 30 graus a partir do 1o furo, junto a
    #     quina, alargando-se para dentro da chapa ate o ultimo furo) ---
    half = Lw_s / 2
    perp = (-diry, dirx)
    end_center = (x1, y1)
    p_plus = (end_center[0] + half * perp[0], end_center[1] + half * perp[1])
    p_minus = (end_center[0] - half * perp[0], end_center[1] - half * perp[1])

    ax.plot([corner_mid[0], x_end], [corner_mid[1], y_end], color="#c0392b", linewidth=1.4,
             linestyle="--", zorder=3, label="Linha de trabalho (C.L. diagonal, alem da quina)")
    ax.plot(*corner_mid, marker="^", color="#c0392b", markersize=7, zorder=4, label="Quina da chapa (corner edge)")

    ax.plot([x0, x1], [y0, y1], color="#2c3e50", linewidth=2.2, zorder=5,
             solid_capstyle="round", label="Linha de parafusos/solda")
    n_dots = n_bolts_draw if n_bolts_draw is not None else max(2, int(gi.L / 3))
    for t in np.linspace(0, 1, max(2, int(n_dots))):
        xb = x0 + t * (x1 - x0)
        yb = y0 + t * (y1 - y0)
        ax.plot(xb, yb, marker="o", markerfacecolor="white",
                 markeredgecolor="#2c3e50", markersize=6, zorder=6)

    ax.plot([x0, p_plus[0]], [y0, p_plus[1]], color="#27ae60", linewidth=1.3, zorder=4)
    ax.plot([x0, p_minus[0]], [y0, p_minus[1]], color="#27ae60", linewidth=1.3, zorder=4)
    ax.plot([p_minus[0], p_plus[0]], [p_minus[1], p_plus[1]], color="#27ae60",
             linewidth=2.2, zorder=5, label=f"Largura de Whitmore Lw = {Lw_s:.2f} {unit_label}")

    # --- pseudo-colunas L1, L2, L3: continuam PARA DENTRO da chapa a partir
    #     do centro da secao de Whitmore, em direcao as interfaces ---
    labels_L = []
    colors_L = {"L1": "#8e44ad", "L2": "#e67e22", "L3": "#16a085"}
    for name, val in (("L1", L1_s), ("L2", L2_s), ("L3", L3_s)):
        if val is None:
            continue
        xe = end_center[0] - val * dirx
        ye = end_center[1] - val * diry
        ax.plot([end_center[0], xe], [end_center[1], ye], color=colors_L[name],
                 linewidth=2.0, linestyle=":", zorder=3)
        ax.plot(xe, ye, marker="s", color=colors_L[name], markersize=5, zorder=6)
        labels_L.append(f"{name} = {val:.2f} {unit_label}")

    # --- anotacoes ---
    nonortho_txt = ""
    if getattr(gi, "theta_bb_deg", 0.0) or getattr(gi, "theta_cc_deg", 0.0):
        nonortho_txt = f"\n$\\theta_{{bb}}$={gi.theta_bb_deg:.1f}°  $\\theta_{{cc}}$={gi.theta_cc_deg:.1f}°"
    info = (
        f"$\\theta_B$ = {res.theta_B_deg:.1f}$^\\circ$" + nonortho_txt + "\n"
        f"Lw = {Lw_s:.2f} {unit_label}\n" + "\n".join(labels_L)
    )
    ax.text(0.98, 0.03, info, transform=ax.transAxes, ha="right", va="bottom",
            fontsize=8.5, family="monospace",
            bbox=dict(boxstyle="round", facecolor="white", edgecolor="#999999", alpha=0.9))

    all_x = [0, top_left[0], corner_top[0], corner_bot[0], bot_right[0], x_end, x0, x1, p_plus[0], p_minus[0]]
    all_y = [0, top_left[1], corner_top[1], corner_bot[1], bot_right[1], y_end, y0, y1, p_plus[1], p_minus[1]]
    mrg = max(3.0, 0.1 * max(W, H))
    ax.set_xlim(min(all_x) - mrg, max(all_x) + mrg)
    ax.set_ylim(min(all_y) - mrg, max(all_y) + mrg)
    ax.set_aspect("equal")
    ax.set_title("Geometria da chapa de no (esquematico - fora de escala/proporcional aos dados de entrada)",
                 fontsize=9)
    ax.set_xlabel(unit_label)
    ax.set_ylabel(unit_label)
    ax.legend(loc="upper left", fontsize=7, framealpha=0.9)
    ax.grid(alpha=0.25)


# ============================================================================
# Interface grafica
# ============================================================================

# ============================================================================
# Diagrama de referencia (ajuda) - notacao geometrica completa, identifica
# cada uma das variaveis de entrada (H, W, a, b, L, Le, s, theta_b, theta_c,
# theta_B), analogo em finalidade a Figura 4 de Chambers & Bartley (2007)
# ============================================================================

def _unit(v):
    n = math.hypot(*v)
    return (v[0] / n, v[1] / n)


def _angle_arc(ax, center, v1, v2, radius, color, lw=1.5):
    a1 = math.atan2(v1[1], v1[0])
    a2 = math.atan2(v2[1], v2[0])
    d = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
    n = 30
    arc = [a1 + d * t / n for t in range(n + 1)]
    xs = [center[0] + radius * math.cos(t) for t in arc]
    ys = [center[1] + radius * math.sin(t) for t in arc]
    ax.plot(xs, ys, color=color, lw=lw)


def draw_reference_diagram(ax):
    """Desenha um diagrama esquematico ilustrativo (nao ligado aos campos
    preenchidos pelo usuario) mostrando onde cada variavel geometrica de
    entrada se localiza na chapa: H, W, a, b, L, Le, s, theta_b, theta_c e
    theta_B. Serve como referencia visual (ajuda), analoga em finalidade a
    Figura 4 de Chambers & Bartley (2007), porem com desenho proprio."""
    ax.clear()

    a, b = 15.0, 9.0
    H, W = 15.0, 21.0
    theta_b = math.radians(9.0)
    theta_c = math.radians(13.0)

    corner_top = (a, H)
    corner_bot = (W, b)
    corner_mid = ((corner_top[0] + corner_bot[0]) / 2, (corner_top[1] + corner_bot[1]) / 2)

    top_left = (0.0, corner_top[1] + a * math.tan(theta_b))
    bot_right = (corner_bot[0] + b * math.tan(theta_c), 0.0)

    outline = [(0, 0), top_left, corner_top, corner_bot, bot_right]
    poly = Polygon(outline, closed=True, facecolor="#eaf1fb", edgecolor="#1c3d6e", linewidth=2.0, zorder=1)
    ax.add_patch(poly)

    ax.plot([0, 0], [0, top_left[1]], color="#444", lw=4, zorder=2)
    ax.plot([0, bot_right[0]], [0, 0], color="#444", lw=4, zorder=2)
    ax.text(-2.0, top_left[1] * 0.14, "Interface\nchapa-coluna", rotation=90,
            ha="center", va="center", fontsize=9, color="#333", style="italic")
    ax.text(bot_right[0] * 0.42, -2.0, "Interface chapa-viga", ha="center",
            va="center", fontsize=9, color="#333", style="italic")

    ax.plot([top_left[0], corner_top[0]], [top_left[1], corner_top[1]], color="#1c3d6e", lw=2)
    ax.plot([corner_bot[0], bot_right[0]], [corner_bot[1], bot_right[1]], color="#1c3d6e", lw=2)
    ax.text(top_left[0] + 2.2, top_left[1] + 1.7, "borda livre lado-coluna",
            fontsize=8.5, color="#1c3d6e", style="italic",
            rotation=math.degrees(math.atan2(corner_top[1]-top_left[1], corner_top[0]-top_left[0])))
    ax.text((corner_bot[0] + bot_right[0]) / 2 + 3.4, (corner_bot[1] + bot_right[1]) / 2 - 0.6,
            "borda livre\nlado-viga", fontsize=8.5, color="#1c3d6e", style="italic",
            rotation=math.degrees(math.atan2(bot_right[1]-corner_bot[1], bot_right[0]-corner_bot[0])))

    ax.plot([corner_top[0], corner_bot[0]], [corner_top[1], corner_bot[1]], color="#c0392b", lw=2.8, zorder=3)
    ax.text(corner_top[0] - 0.3, corner_top[1] + 1.4, "quina\n(junto à diagonal)",
            fontsize=8.5, color="#c0392b", style="italic", ha="center")

    quina_dir = (corner_bot[0] - corner_top[0], corner_bot[1] - corner_top[1])
    quina_unit = _unit(quina_dir)
    perp_in = (-quina_unit[1], quina_unit[0])
    to_origin = (-corner_mid[0], -corner_mid[1])
    if perp_in[0]*to_origin[0] + perp_in[1]*to_origin[1] < 0:
        perp_in = (-perp_in[0], -perp_in[1])

    Le, Lb, s = 2.3, 7.2, 2.2
    p0 = (corner_mid[0] + Le * perp_in[0], corner_mid[1] + Le * perp_in[1])
    p1 = (corner_mid[0] + (Le + Lb) * perp_in[0], corner_mid[1] + (Le + Lb) * perp_in[1])
    ax.plot([corner_mid[0], p0[0]], [corner_mid[1], p0[1]], color="#7f8c8d", lw=1.0, ls=":")
    ax.plot([p0[0], p1[0]], [p0[1], p1[1]], color="#2c3e50", lw=2.2, zorder=5)
    bolt_pts = []
    for t in np.linspace(0, 1, 6):
        xb, yb = p0[0] + t*(p1[0]-p0[0]), p0[1] + t*(p1[1]-p0[1])
        bolt_pts.append((xb, yb))
        ax.plot(xb, yb, "o", markerfacecolor="white", markeredgecolor="#2c3e50", markersize=7, zorder=6)

    ax.annotate("", xy=p0, xytext=corner_mid, arrowprops=dict(arrowstyle="<->", color="#7f8c8d", lw=1.1))
    le_mid = ((corner_mid[0]+p0[0])/2, (corner_mid[1]+p0[1])/2)
    le_perp = (quina_unit[0], quina_unit[1])
    ax.text(le_mid[0] + 2.6*le_perp[0], le_mid[1] + 2.6*le_perp[1], r"$L_e$", color="#7f8c8d", fontsize=11,
            ha="center", va="center")

    mid_L = ((p0[0]+p1[0])/2, (p0[1]+p1[1])/2)
    ax.text(mid_L[0] - 3.6, mid_L[1] - 1.8, "$L$\n(calc. de n.parafusos x pitch)", color="#2c3e50",
            fontsize=9.5, ha="center")

    p0b = (bolt_pts[1][0] + s*quina_unit[0], bolt_pts[1][1] + s*quina_unit[1])
    ax.plot(p0b[0], p0b[1], "o", markerfacecolor="white", markeredgecolor="#2c3e50", markersize=7, zorder=6)
    ax.annotate("", xy=p0b, xytext=bolt_pts[1], arrowprops=dict(arrowstyle="<->", color="#16a085", lw=1.3))
    ax.text((bolt_pts[1][0]+p0b[0])/2 + 0.9, (bolt_pts[1][1]+p0b[1])/2 - 0.7, "$s$", color="#16a085", fontsize=12)

    _angle_arc(ax, p0, (1, 0), (p1[0]-p0[0], p1[1]-p0[1]), 1.0, "#e67e22", lw=1.5)
    ax.plot([p0[0], p0[0]+3.0], [p0[1], p0[1]], color="gray", lw=0.8, ls="--")
    ax.text(p0[0] + 3.6, p0[1] + 2.0, r"$\theta_B$" + "\n(calculado)", color="#e67e22", fontsize=9.5, ha="center")

    pt_b = (0.35*top_left[0] + 0.65*corner_top[0], 0.35*top_left[1] + 0.65*corner_top[1])
    edge_b_dir = (top_left[0]-corner_top[0], top_left[1]-corner_top[1])
    _angle_arc(ax, pt_b, (-1, 0), edge_b_dir, 2.3, "#8e44ad", lw=1.5)
    ax.plot([pt_b[0]-3.0, pt_b[0]], [pt_b[1], pt_b[1]], color="gray", lw=0.8, ls="--")
    ax.text(pt_b[0] - 2.6, pt_b[1] + 0.75, r"$\theta_b$", color="#8e44ad", fontsize=13)

    pt_c = (0.55*corner_bot[0] + 0.45*bot_right[0], 0.55*corner_bot[1] + 0.45*bot_right[1])
    edge_c_dir = (bot_right[0]-corner_bot[0], bot_right[1]-corner_bot[1])
    _angle_arc(ax, pt_c, (0, -1), edge_c_dir, 2.3, "#16a085", lw=1.5)
    ax.plot([pt_c[0], pt_c[0]], [pt_c[1]-3.0, pt_c[1]], color="gray", lw=0.8, ls="--")
    ax.text(pt_c[0] + 0.7, pt_c[1] - 2.6, r"$\theta_c$", color="#16a085", fontsize=13)

    ax.annotate("", xy=(corner_top[0], H + 3.4), xytext=(0, H + 3.4), arrowprops=dict(arrowstyle="<->", color="k", lw=1.1))
    ax.text(corner_top[0]/2, H + 3.9, "$a$", ha="center", fontsize=14)

    ax.annotate("", xy=(-2.6, H), xytext=(-2.6, 0), arrowprops=dict(arrowstyle="<->", color="k", lw=1.0))
    ax.text(-5.6, H*0.68, "$H$", fontsize=14)

    ax.annotate("", xy=(W + 6.6, b), xytext=(W + 6.6, 0), arrowprops=dict(arrowstyle="<->", color="k", lw=1.1))
    ax.text(W + 7.1, b/2, "$b$", fontsize=14, va="center")

    ax.annotate("", xy=(bot_right[0], -2.8), xytext=(0, -2.8), arrowprops=dict(arrowstyle="<->", color="k", lw=1.0))
    ax.text(bot_right[0]/2, -3.7, "$W$", ha="center", fontsize=14)

    ax.text(0.5, 0.5, "", transform=ax.transAxes)  # no-op, mantem estilo
    ax.set_xlim(-7, W + 7)
    ax.set_ylim(-7, H + 7)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(
        "Diagrama de referência - identificação dos ângulos e distâncias de entrada\n"
        "(esquemático, não ligado aos valores preenchidos)",
        fontsize=10
    )


def draw_nonortho_diagram(ax):
    """Desenha um diagrama esquematico ilustrativo identificando theta_bb,
    theta_cc, y_b e y_c - os parametros de nao-ortogonalidade das
    interfaces chapa-viga e chapa-coluna. Analogo em finalidade a
    Figura 8(a) de Chambers & Bartley (2007), porem com desenho proprio."""
    ax.clear()

    # --- contorno simplificado da chapa, no mesmo estilo do painel
    #     principal (quina + bordas livres), levemente girado para lembrar
    #     a apresentacao da Figura 8 do artigo original ---
    a, b = 8.0, 5.0
    H, W = 9.0, 12.0
    theta_b, theta_c = math.radians(6.0), math.radians(8.0)
    rot = math.radians(18.0)  # rotacao geral da figura, so estetica

    def R(p):
        x, y = p
        return (x * math.cos(rot) - y * math.sin(rot), x * math.sin(rot) + y * math.cos(rot))

    corner_top = R((a, H))
    corner_bot = R((W, b))
    top_left = R((0.0, H + a * math.tan(theta_b)))
    bot_right = R((W + b * math.tan(theta_c), 0.0))
    origin = R((0, 0))

    outline = [origin, top_left, corner_top, corner_bot, bot_right]
    poly = Polygon(outline, closed=True, facecolor="#eaf1fb", edgecolor="#1c3d6e", lw=1.8, zorder=1)
    ax.add_patch(poly)
    ax.plot([origin[0], top_left[0]], [origin[1], top_left[1]], color="#444", lw=2.6, zorder=2)
    ax.plot([origin[0], bot_right[0]], [origin[1], bot_right[1]], color="#444", lw=2.6, zorder=2)

    # --- linha de trabalho / parafusos, atravessando a chapa (estilo "CL") ---
    corner_mid = ((corner_top[0] + corner_bot[0]) / 2, (corner_top[1] + corner_bot[1]) / 2)
    theta_B_local = math.radians(34.0) + rot
    brace_dir = (math.cos(theta_B_local), math.sin(theta_B_local))
    p_far = (corner_mid[0] + 6.0 * brace_dir[0], corner_mid[1] + 6.0 * brace_dir[1])
    p_near = (corner_mid[0] - 5.0 * brace_dir[0], corner_mid[1] - 5.0 * brace_dir[1])
    ax.plot([p_near[0], p_far[0]], [p_near[1], p_far[1]], color="#2c3e50", lw=1.8, zorder=3)
    ax.text(p_far[0] + 0.2, p_far[1] + 0.2, r"$\mathbb{C}_L$", fontsize=12, color="#2c3e50")
    for t in np.linspace(0.15, 0.85, 7):
        xb = p_near[0] + t * (p_far[0] - p_near[0])
        yb = p_near[1] + t * (p_far[1] - p_near[1])
        ax.plot(xb, yb, "o", markerfacecolor="white", markeredgecolor="#2c3e50", markersize=6, zorder=4)

    # --- ponto P: onde y_b, y_c, theta_bb e theta_cc sao definidos (perto
    #     do centro da secao de Whitmore, ao longo da linha de parafusos) ---
    P = (corner_mid[0] - 1.0 * brace_dir[0], corner_mid[1] - 1.0 * brace_dir[1])
    ax.plot(*P, "s", color="#c0392b", markersize=7, zorder=6)
    # marca de angulo reto entre P e a linha de parafusos
    perp_mark = (-brace_dir[1], brace_dir[0])
    sq = 0.35
    sp1 = (P[0] + sq * perp_mark[0], P[1] + sq * perp_mark[1])
    sp2 = (sp1[0] + sq * brace_dir[0], sp1[1] + sq * brace_dir[1])
    sp3 = (P[0] + sq * brace_dir[0], P[1] + sq * brace_dir[1])
    ax.plot([sp1[0], sp2[0], sp3[0]], [sp1[1], sp2[1], sp3[1]], color="#555", lw=0.9, zorder=5)

    # --- interface chapa-coluna (nominal = vertical, rotacionada por theta_cc) ---
    theta_cc = math.radians(10.0)
    col_ref = (0, -1)  # referencia "para baixo" (como no desenho do artigo)
    col_dir = (math.sin(theta_cc), -math.cos(theta_cc))
    Lc = 6.5
    col_end = (P[0] + Lc * col_dir[0], P[1] + Lc * col_dir[1])
    ax.plot([P[0], P[0] + 2.6 * col_ref[0]], [P[1], P[1] + 2.6 * col_ref[1]], color="gray", lw=0.8, ls="--")
    ax.plot([P[0], col_end[0]], [P[1], col_end[1]], color="#8e44ad", lw=2.2, zorder=4,
             label="Interface chapa-coluna (θcc a partir da vertical)")
    _angle_arc(ax, P, col_ref, col_dir, 1.5, "#8e44ad", lw=1.4)
    mid_arc = ((col_ref[0]+col_dir[0])/2, (col_ref[1]+col_dir[1])/2)
    mid_arc_u = _unit(mid_arc)
    ax.text(P[0] + 2.3 * mid_arc_u[0], P[1] + 2.3 * mid_arc_u[1], r"$\theta_{cc}$",
            color="#8e44ad", fontsize=13, ha="center", va="center")

    # --- interface chapa-viga (nominal = horizontal, rotacionada por theta_bb) ---
    theta_bb = math.radians(14.0)
    beam_ref = (-1, 0)
    beam_dir = (-math.cos(theta_bb), -math.sin(theta_bb))
    Lb = 5.6
    beam_end = (P[0] + Lb * beam_dir[0], P[1] + Lb * beam_dir[1])
    ax.plot([P[0] + 2.6 * beam_ref[0], P[0]], [P[1] + 2.6 * beam_ref[1], P[1]], color="gray", lw=0.8, ls="--")
    ax.plot([P[0], beam_end[0]], [P[1], beam_end[1]], color="#16a085", lw=2.2, zorder=4,
             label="Interface chapa-viga (θbb a partir da horizontal)")
    _angle_arc(ax, P, beam_ref, beam_dir, 1.15, "#16a085", lw=1.4)
    mid_arc_b = _unit(((beam_ref[0]+beam_dir[0])/2, (beam_ref[1]+beam_dir[1])/2))
    ax.text(P[0] + 2.1 * mid_arc_b[0], P[1] + 2.1 * mid_arc_b[1], r"$\theta_{bb}$",
            color="#16a085", fontsize=13, ha="center", va="center")

    # --- y_c e y_b: distancias de P as interfaces ---
    off_c = (-3.0, 0.5)
    yc_len = 5.6
    yc_end = (P[0] + yc_len * col_dir[0], P[1] + yc_len * col_dir[1])
    ax.annotate("", xy=(yc_end[0] + off_c[0], yc_end[1] + off_c[1]), xytext=(P[0] + off_c[0], P[1] + off_c[1]),
                arrowprops=dict(arrowstyle="<->", color="#8e44ad", lw=1.3))
    ax.text(P[0] + off_c[0] - 1.0, (P[1] + yc_end[1]) / 2 + off_c[1], "$y_c$", color="#8e44ad", fontsize=13,
            ha="center", va="center")

    off_b = (0.3, -2.9)
    yb_len = 4.6
    yb_end = (P[0] + yb_len * beam_dir[0], P[1] + yb_len * beam_dir[1])
    ax.annotate("", xy=(yb_end[0] + off_b[0], yb_end[1] + off_b[1]), xytext=(P[0] + off_b[0], P[1] + off_b[1]),
                arrowprops=dict(arrowstyle="<->", color="#16a085", lw=1.3))
    ax.text((P[0] + yb_end[0]) / 2 + off_b[0], P[1] + off_b[1] - 0.75, "$y_b$", color="#16a085", fontsize=13,
            ha="center", va="center")

    all_pts = [origin, top_left, corner_top, corner_bot, bot_right, p_far, p_near,
               col_end, beam_end, (yc_end[0]+off_c[0], yc_end[1]+off_c[1]),
               (yb_end[0]+off_b[0], yb_end[1]+off_b[1])]
    xs = [p[0] for p in all_pts]; ys = [p[1] for p in all_pts]
    mrg = 1.6
    ax.set_xlim(min(xs) - mrg, max(xs) + mrg)
    ax.set_ylim(min(ys) - mrg, max(ys) + mrg)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.legend(loc="upper left", fontsize=7, framealpha=0.92)
    ax.set_title(
        "Ângulos de não-ortogonalidade θbb, θcc\ne distâncias yb, yc",
        fontsize=10
    )


class ReferenceDiagramWindow(tk.Toplevel):
    """Janela auxiliar (popup) que mostra os diagramas de referencia com
    todos os angulos e distancias de entrada identificados: painel
    esquerdo (H, W, a, b, L, Le, s, theta_b, theta_c, theta_B - Figura 4
    de Chambers & Bartley, 2007) e painel direito (theta_bb, theta_cc,
    y_b, y_c - Figura 8 de Chambers & Bartley, 2007)."""
    def __init__(self, master):
        super().__init__(master)
        self.title("Diagrama de referência - ângulos e distâncias")
        self.geometry("1180x760")
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.6, 7.4))
        draw_reference_diagram(ax1)
        draw_nonortho_diagram(ax2)
        canvas = FigureCanvasTkAgg(fig, master=self)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        canvas.draw()
        ttk.Button(self, text="Fechar", command=self.destroy).pack(pady=6)


def draw_ufm_reference_diagram(ax):
    """Diagrama esquematico ilustrativo (nao ligado aos valores preenchidos)
    identificando alpha, beta, eb, ec, theta, r e as 4 forcas de interface
    do Metodo das Forcas Uniformes (UFM)."""
    ax.clear()
    H_col, W_beam = 10, 16
    ax.plot([-1, W_beam + 3], [0, 0], color="#444", lw=4)
    ax.plot([0, 0], [-1, H_col + 8], color="#444", lw=4)

    alpha, beta = 6.5, 4.5
    ec, eb = 2.5, 4.0
    theta = math.radians(40)

    wp = (alpha + ec, beta + eb)
    ax.plot(*wp, "o", color="#c0392b", ms=6, zorder=5)

    outline = [(0, 0), (0, beta + eb + 3), (alpha + ec + 3, beta + eb + 3), (alpha + ec + 2, 0)]
    poly = Polygon(outline, closed=True, facecolor="#eaf1fb", edgecolor="#1c3d6e", lw=1.6, zorder=1)
    ax.add_patch(poly)

    cb = (alpha, 0)
    ax.plot(*cb, "s", color="#2c3e50", ms=7, zorder=5)
    ax.annotate("", xy=(alpha, 0), xytext=(0, 0), arrowprops=dict(arrowstyle="<->", color="k", lw=1))
    ax.text(alpha / 2, -0.9, r"$\alpha$", ha="center", fontsize=13)

    cc = (0, beta)
    ax.plot(*cc, "s", color="#2c3e50", ms=7, zorder=5)
    ax.annotate("", xy=(0, beta), xytext=(0, 0), arrowprops=dict(arrowstyle="<->", color="k", lw=1))
    ax.text(-0.9, beta / 2, r"$\beta$", va="center", ha="center", fontsize=13, rotation=90)

    ax.annotate("", xy=(alpha, eb + beta), xytext=(alpha, 0), arrowprops=dict(arrowstyle="<->", color="#16a085", lw=1.3))
    ax.text(alpha + 0.5, beta + eb / 2, r"$e_b$", color="#16a085", fontsize=12)
    ax.annotate("", xy=(ec + alpha, beta), xytext=(0, beta), arrowprops=dict(arrowstyle="<->", color="#8e44ad", lw=1.3))
    ax.text(alpha / 2 + ec / 2, beta + 0.6, r"$e_c$", color="#8e44ad", fontsize=12)

    ax.plot([alpha, wp[0]], [0, wp[1]], color="#c0392b", ls=":", lw=1)
    ax.plot([0, wp[0]], [beta, wp[1]], color="#c0392b", ls=":", lw=1)
    ax.plot([cb[0], wp[0]], [cb[1], wp[1]], color="#e67e22", lw=2, zorder=4)
    ax.text((cb[0] + wp[0]) / 2 + 0.6, (cb[1] + wp[1]) / 2, "r", color="#e67e22", fontsize=13)

    Lb = 7
    xe = wp[0] + Lb * math.sin(theta)
    ye = wp[1] + Lb * math.cos(theta)
    ax.plot([wp[0], xe], [wp[1], ye], color="#c0392b", lw=2, ls="--")
    ax.text(xe + 0.3, ye, r"$P_r$" + "\n(diagonal)", color="#c0392b", fontsize=10)
    ax.text(wp[0] + 0.6, wp[1] - 1.3, r"$\theta$", color="#c0392b", fontsize=13)

    ax.annotate("", xy=(alpha, -2.6), xytext=(alpha, 0), arrowprops=dict(arrowstyle="->", color="#2980b9", lw=2))
    ax.text(alpha + 0.3, -2.3, r"$V_{rb}$", color="#2980b9", fontsize=11)
    ax.annotate("", xy=(alpha - 2.6, 0.55), xytext=(alpha, 0.55), arrowprops=dict(arrowstyle="->", color="#2980b9", lw=2))
    ax.text(alpha - 3.3, 0.9, r"$H_{rb}$", color="#2980b9", fontsize=11)
    ax.annotate("", xy=(-2.6, beta), xytext=(0, beta), arrowprops=dict(arrowstyle="->", color="#c0392b", lw=2))
    ax.text(-3.6, beta + 0.4, r"$H_{rc}$", color="#c0392b", fontsize=11)
    ax.annotate("", xy=(0.55, beta - 2.6), xytext=(0.55, beta), arrowprops=dict(arrowstyle="->", color="#c0392b", lw=2))
    ax.text(0.7, beta - 3.0, r"$V_{rc}$", color="#c0392b", fontsize=11)

    ax.text(W_beam * 0.35, -1.9, "Interface chapa-viga", fontsize=8, color="#555")
    ax.text(-2.6, H_col * 0.55, "Interface\nchapa-coluna", fontsize=8, color="#555", rotation=90, ha="center")

    ax.set_xlim(-5, W_beam + 3)
    ax.set_ylim(-5, H_col + 3)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(
        "Diagrama de referência - Método das Forças Uniformes (UFM)\n"
        "(esquemático, não ligado aos valores preenchidos)",
        fontsize=10,
    )


class UFMReferenceDiagramWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Diagrama de referência - UFM (α, β, eb, ec)")
        self.geometry("720x760")
        fig, ax = plt.subplots(figsize=(6.8, 7.0))
        draw_ufm_reference_diagram(ax)
        canvas = FigureCanvasTkAgg(fig, master=self)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        canvas.draw()
        ttk.Button(self, text="Fechar", command=self.destroy).pack(pady=6)


class GussetApp:
    def __init__(self, root):
        self.root = root
        root.title(APP_TITLE)
        root.geometry("1280x800")

        self.last_gi = None
        self.last_res = None

        self._build_layout()
        self._set_defaults()
        self._set_ufm_defaults()
        self.calculate()
        self.calculate_ufm()

    # ------------------------------------------------------------------
    def _build_layout(self):
        outer = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        outer.pack(fill=tk.BOTH, expand=True)

        # ---- painel esquerdo: entradas ----
        left = ttk.Frame(outer, padding=10)
        outer.add(left, weight=1)

        self.vars = {}
        self.unit_aware_labels = []

        # ---- seletor global de unidades (fica no topo, acima das abas) ----
        unit_frame = ttk.LabelFrame(left, text="Sistema de unidades", padding=6)
        unit_frame.pack(fill=tk.X, pady=(0, 8))
        self.unit_system = tk.StringVar(value="imperial")
        ttk.Radiobutton(unit_frame, text="Imperial (in / ksi / kips)", variable=self.unit_system,
                         value="imperial", command=self._on_unit_change).pack(side=tk.LEFT, padx=6)
        ttk.Radiobutton(unit_frame, text="Métrico (mm / MPa / kN)", variable=self.unit_system,
                         value="metric", command=self._on_unit_change).pack(side=tk.LEFT, padx=6)

        nb = ttk.Notebook(left)
        nb.pack(fill=tk.BOTH, expand=True)

        self.tab_geo = ttk.Frame(nb, padding=8)
        self.tab_mat = ttk.Frame(nb, padding=8)
        self.tab_hss = ttk.Frame(nb, padding=8)
        self.tab_ufm = self._make_scrollable_tab(nb)
        nb.add(self.tab_geo, text="Geometria (Whitmore)")
        nb.add(self.tab_mat, text="Material / Carga")
        nb.add(self.tab_hss, text="HSS circular (shear lag)")
        nb.add(self.tab_ufm.outer, text="UFM - Diagonal HSS/WF")

        geo_fields = [
            ("H", "H - altura total da chapa ({U})"),
            ("W", "W - largura total da chapa ({U})"),
            ("a", "a - dist. face coluna -> centroide lig. viga ({U})"),
            ("b", "b - dist. face viga -> centroide lig. coluna ({U})"),
            ("n_bolts", "Numero de parafusos na linha de fixacao da diagonal"),
            ("pitch", "Espacamento entre parafusos - pitch ({U})"),
            ("Le", "Le - afastamento do 1o parafuso a quina ({U})"),
            ("s", "s - espacamento perpendicular entre linhas (gramp) ({U})"),
            ("theta_b_deg", "theta_b - angulo interface viga (graus)"),
            ("theta_c_deg", "theta_c - angulo interface coluna (graus)"),
            ("theta_bb_deg", "theta_bb - nao-ortog. viga (graus, 0=ortogonal)"),
            ("theta_cc_deg", "theta_cc - nao-ortog. coluna (graus, 0=ortogonal)"),
        ]
        self._add_fields(self.tab_geo, geo_fields)
        self.lbl_L_computed = ttk.Label(self.tab_geo, text="L (calculado) = -- in",
                                         font=("TkDefaultFont", 9, "italic"), foreground="#1c3d6e")
        self.lbl_L_computed.grid(row=len(geo_fields), column=0, columnspan=2, sticky="w", pady=(4, 0))

        mat_fields = [
            ("tp", "tp - espessura da chapa ({U})"),
            ("Fy", "Fy - tensao de escoamento ({U})"),
            ("Fu", "Fu - tensao de ruptura ({U})"),
            ("Pu", "Pu - carga fatorada na diagonal ({U})"),
            ("phi_y", "phi (escoamento a tracao)"),
            ("phi_c", "phi (flambagem / compressao)"),
            ("K", "K - fator de comp. efetivo (pseudo-coluna)"),
            ("E", "E - modulo de elasticidade ({U})"),
        ]
        self._add_fields(self.tab_mat, mat_fields)

        self._build_ufm_tab()

        hss_fields = [
            ("hss_D", "D - diametro externo do HSS ({U})"),
            ("hss_t", "t - espessura de parede do HSS ({U})"),
            ("hss_Lweld", "L - comprimento da solda longitudinal ({U})"),
            ("hss_Fy", "Fy do tubo ({U})"),
            ("hss_Fu", "Fu do tubo ({U})"),
        ]
        self._add_fields(self.tab_hss, hss_fields)
        self.hss_transverse = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.tab_hss, text="Ha solda transversal na extremidade da fenda",
                         variable=self.hss_transverse).grid(row=len(hss_fields), column=0,
                                                              columnspan=2, sticky="w", pady=6)

        btn_frame = ttk.Frame(left, padding=(0, 10))
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Calcular", command=self.calculate).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="Exportar relatorio (PDF)", command=self.export_pdf).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="Carregar Exemplo 1 (artigo)", command=self.load_example).pack(side=tk.LEFT, padx=4)
        btn_frame2 = ttk.Frame(left, padding=(0, 0))
        btn_frame2.pack(fill=tk.X)
        ttk.Button(btn_frame2, text="📐 Ver diagrama de referência (ângulos e distâncias)",
                   command=self.show_reference_diagram).pack(side=tk.LEFT, padx=4, pady=(0, 6))

        # ---- painel direito: desenho + resultados ----
        right = ttk.Frame(outer, padding=10)
        outer.add(right, weight=2)

        self.fig, self.ax = plt.subplots(figsize=(6.5, 6.0))
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.txt = tk.Text(right, height=16, font=("Consolas", 9))
        self.txt.pack(fill=tk.BOTH, expand=False, pady=(8, 0))

    def _label_text_for(self, key, template):
        """Substitui o placeholder {U} pela abreviacao de unidade correta
        para o tipo de grandeza do campo (comprimento/tensao/forca/area),
        de acordo com o sistema de unidades atualmente selecionado."""
        if "{U}" not in template:
            return template
        kind = FIELD_UNITS.get(key)
        system = self.unit_system.get() if hasattr(self, "unit_system") else "imperial"
        unit_str = UNIT_LABELS[system].get(kind, "") if kind else ""
        return template.format(U=unit_str)

    def _add_fields(self, parent, fields):
        if not hasattr(self, "unit_aware_labels"):
            self.unit_aware_labels = []
        for i, (key, template) in enumerate(fields):
            lbl = ttk.Label(parent, text=self._label_text_for(key, template), wraplength=260, justify="left")
            lbl.grid(row=i, column=0, sticky="w", pady=3, padx=(0, 6))
            var = tk.StringVar()
            ttk.Entry(parent, textvariable=var, width=12).grid(row=i, column=1, pady=3)
            self.vars[key] = var
            self.unit_aware_labels.append((lbl, key, template))

    def _make_scrollable_tab(self, nb):
        """Cria um Frame rolavel (canvas + scrollbar) para abas com muitos campos."""
        outer = ttk.Frame(nb)
        canvas = tk.Canvas(outer, borderwidth=0, highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas, padding=8)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel, add="+")

        ns = type("ScrollTab", (), {})()
        ns.outer = outer
        ns.inner = inner
        return ns

    def _add_labelframe_fields(self, parent, title, fields, row):
        if not hasattr(self, "unit_aware_labels"):
            self.unit_aware_labels = []
        lf = ttk.LabelFrame(parent, text=title, padding=8)
        lf.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        for i, (key, template) in enumerate(fields):
            lbl = ttk.Label(lf, text=self._label_text_for(key, template), wraplength=340, justify="left")
            lbl.grid(row=i, column=0, sticky="w", pady=3, padx=(0, 6))
            var = tk.StringVar()
            ttk.Entry(lf, textvariable=var, width=14).grid(row=i, column=1, pady=3)
            self.vars[key] = var
            self.unit_aware_labels.append((lbl, key, template))
        return lf

    def _build_ufm_tab(self):
        parent = self.tab_ufm.inner
        r = 0

        ttk.Label(parent, text="Metodo das Forcas Uniformes (UFM) - AISC Manual Parte 13\n"
                  "Distribui a forca da diagonal entre a chapa, a viga e a coluna, e "
                  "dimensiona a chapa de no.\nBaseado em: Packer & Richardson (2025), "
                  "Steel Tube Institute.", wraplength=380, justify="left",
                  font=("TkDefaultFont", 9, "italic")).grid(row=r, column=0, sticky="w", pady=(0, 10))
        r += 1

        self._add_labelframe_fields(parent, "A) Geometria e forca da diagonal", [
            ("ufm_Pr", "Pr - forca axial fatorada na diagonal ({U})"),
            ("ufm_theta", "theta - angulo entre o eixo da diagonal e a VERTICAL (graus)"),
            ("ufm_eb", "eb - metade da altura da viga, d/2 ({U})"),
            ("ufm_ec", "ec - metade da altura/largura da coluna, H/2 ou B/2 ({U})"),
            ("ufm_alpha", "alpha - dist. face da coluna ao centroide da lig. chapa-viga ({U})"),
        ], r); r += 1

        self._add_labelframe_fields(parent, "B) Secao de Whitmore e flambagem da chapa", [
            ("ufm_nbolts_brace", "Numero de parafusos (ou pontos de solda) na linha da diagonal"),
            ("ufm_pitch_brace", "Espacamento entre eles - pitch ({U}). L = (n-1) x pitch. "
             "Para solda simetrica ao ponto de trabalho, informe n=2 e pitch = comprimento TOTAL."),
            ("ufm_w0", "w0 - largura de contato no inicio da ligacao ({U})"),
            ("ufm_Lc", "Lc - comprimento nao travado p/ flambagem, ao longo da diagonal ({U})"),
            ("ufm_K", "K - fator de comprimento efetivo (1,0 tipico; 1,2 p/ chapa de emenda excentrica)"),
            ("ufm_Fy_plate", "Fy da chapa de no ({U})"),
            ("ufm_tp_list", "Espessuras candidatas da chapa, separadas por virgula ({U})"),
            ("ufm_edge_beam", "Distancia minima da ligacao a borda da chapa, lado viga ({U})"),
            ("ufm_edge_col", "Distancia minima da ligacao a borda da chapa, lado coluna ({U})"),
        ], r); r += 1

        self._add_labelframe_fields(parent, "C) Verificacao rapida de solda de filete", [
            ("ufm_Fexx", "Fexx - resistencia do eletrodo ({U})"),
            ("ufm_weld_size", "Perna da solda de filete ({U})"),
            ("ufm_weld_length", "Comprimento de cada linha de solda ({U})"),
            ("ufm_weld_nlines", "Numero de linhas de solda"),
        ], r); r += 1

        self._add_labelframe_fields(parent, "D) Verificacao rapida de parafusos", [
            ("ufm_Fnv", "Fnv - tensao nominal de cisalhamento do parafuso ({U})"),
            ("ufm_dbolt", "Diametro do parafuso ({U})"),
            ("ufm_nbolts", "Numero de parafusos no grupo"),
            ("ufm_tply", "Espessura da parte ligada mais fina ({U})"),
            ("ufm_Fuply", "Fu da parte ligada ({U})"),
        ], r); r += 1

        self._add_labelframe_fields(parent, "E) Plastificacao da parede de coluna HSS (AISC DG24)", [
            ("ufm_Fy_col", "Fy da coluna HSS ({U})"),
            ("ufm_t_col", "Espessura de parede da coluna HSS ({U})"),
            ("ufm_La", "La - comprimento de contato ao longo da coluna ({U})"),
            ("ufm_B_col", "B - largura da face conectada da coluna HSS ({U})"),
            ("ufm_branch_w", "Largura do 'ramo' equivalente (footprint da ligacao) ({U})"),
            ("ufm_Pu_col", "Pu na coluna ({U}; negativo = compressao)"),
            ("ufm_Ag_col", "Area bruta da coluna HSS ({U})"),
        ], r); r += 1

        btnf = ttk.Frame(parent)
        btnf.grid(row=r, column=0, sticky="w", pady=6)
        ttk.Button(btnf, text="Calcular UFM", command=self.calculate_ufm).pack(side=tk.LEFT, padx=4)
        ttk.Button(btnf, text="Carregar exemplo (Steel Tube Institute)", command=self.load_ufm_example).pack(side=tk.LEFT, padx=4)
        ttk.Button(btnf, text="📐 Ver diagrama de referência (α, β, eb, ec)",
                   command=self.show_ufm_reference_diagram).pack(side=tk.LEFT, padx=4)
        r += 1

        self.txt_ufm = tk.Text(parent, height=28, width=62, font=("Consolas", 9))
        self.txt_ufm.grid(row=r, column=0, sticky="ew", pady=(6, 0))

    # ------------------------------------------------------------------
    def _set_defaults(self):
        defaults = dict(
            H=20.0, W=21.5, a=19.7, b=14.5, n_bolts=6, pitch=2.6, Le=2, s=3,
            theta_b_deg=15.0, theta_c_deg=30.0, theta_bb_deg=-10.0, theta_cc_deg=-8.0,
            tp=0.5, Fy=50.0, Fu=65.0, Pu=127.0, phi_y=0.90, phi_c=0.90, K=0.5, E=29000.0,
            hss_D=8.625, hss_t=0.322, hss_Lweld=13.0, hss_Fy=42.0, hss_Fu=58.0,
        )
        for k, v in defaults.items():
            self.vars[k].set(str(v))

    def load_example(self):
        self._set_defaults()
        self.calculate()

    def show_reference_diagram(self):
        ReferenceDiagramWindow(self.root)

    def show_ufm_reference_diagram(self):
        UFMReferenceDiagramWindow(self.root)

    def _on_unit_change(self):
        """Chamado quando o usuario alterna entre unidades imperiais e
        metricas: (1) converte os valores JA DIGITADOS nos campos para o
        novo sistema (sem precisar redigitar), e (2) atualiza os rotulos
        dos campos para mostrar a unidade correta."""
        new_system = self.unit_system.get()
        old_system = getattr(self, "_last_unit_system", "imperial")
        if new_system != old_system:
            for key, var in self.vars.items():
                kind = FIELD_UNITS.get(key)
                raw = var.get().strip()
                if not raw:
                    continue
                try:
                    if kind == "length_list":
                        vals = [float(x) for x in raw.split(",") if x.strip()]
                        conv = [from_internal(to_internal(v, "length", old_system), "length", new_system)
                                for v in vals]
                        var.set(",".join(f"{v:.4g}" for v in conv))
                    elif kind is None:
                        continue
                    else:
                        v = float(raw)
                        conv = from_internal(to_internal(v, kind, old_system), kind, new_system)
                        var.set(f"{conv:.5g}")
                except ValueError:
                    continue
        self._last_unit_system = new_system

        for lbl, key, template in getattr(self, "unit_aware_labels", []):
            lbl.config(text=self._label_text_for(key, template))

        # recalcula com os novos valores/unidades, se possivel
        try:
            self.calculate()
        except Exception:
            pass
        try:
            self.calculate_ufm()
        except Exception:
            pass

    def _set_ufm_defaults(self):
        defaults = dict(
            ufm_Pr=130.0, ufm_theta=45.0, ufm_eb=9.75, ufm_ec=5.0, ufm_alpha=13.25,
            ufm_nbolts_brace=2, ufm_pitch_brace=8.0, ufm_w0=3.0, ufm_Lc=13.10, ufm_K=1.2, ufm_Fy_plate=50.0,
            ufm_tp_list="0.375,0.5,0.625,0.75,0.875,1.0", ufm_edge_beam=2.0, ufm_edge_col=2.0,
            ufm_Fexx=70.0, ufm_weld_size=0.25, ufm_weld_length=6.0, ufm_weld_nlines=4,
            ufm_Fnv=68.0, ufm_dbolt=0.875, ufm_nbolts=6, ufm_tply=0.75, ufm_Fuply=65.0,
            ufm_Fy_col=50.0, ufm_t_col=0.465, ufm_La=16.0, ufm_B_col=10.0, ufm_branch_w=6.75,
            ufm_Pu_col=-501.9, ufm_Ag_col=17.2,
        )
        for k, v in defaults.items():
            self.vars[k].set(str(v))

    def load_ufm_example(self):
        self._set_ufm_defaults()
        self.calculate_ufm()

    def calculate_ufm(self):
        try:
            Pr = self._read_conv("ufm_Pr")
            theta = self._read_float("ufm_theta")
            eb = self._read_conv("ufm_eb")
            ec = self._read_conv("ufm_ec")
            alpha = self._read_conv("ufm_alpha")

            Lconn_nbolts = self._read_float("ufm_nbolts_brace")
            Lconn_pitch = self._read_conv("ufm_pitch_brace")
            w0 = self._read_conv("ufm_w0")
            Lc = self._read_conv("ufm_Lc")
            K = self._read_float("ufm_K")
            Fy_plate = self._read_conv("ufm_Fy_plate")
            system = self.unit_system.get()
            tp_list = [to_internal(float(x), "length", system)
                       for x in self.vars["ufm_tp_list"].get().split(",") if x.strip()]
            edge_beam = self._read_conv("ufm_edge_beam")
            edge_col = self._read_conv("ufm_edge_col")

            Fexx = self._read_conv("ufm_Fexx")
            weld_size = self._read_conv("ufm_weld_size")
            weld_length = self._read_conv("ufm_weld_length")
            weld_nlines = int(self._read_float("ufm_weld_nlines"))

            Fnv = self._read_conv("ufm_Fnv")
            dbolt = self._read_conv("ufm_dbolt")
            nbolts = int(self._read_float("ufm_nbolts"))
            tply = self._read_conv("ufm_tply")
            Fuply = self._read_conv("ufm_Fuply")

            Fy_col = self._read_conv("ufm_Fy_col")
            t_col = self._read_conv("ufm_t_col")
            La = self._read_conv("ufm_La")
            B_col = self._read_conv("ufm_B_col")
            branch_w = self._read_conv("ufm_branch_w")
            Pu_col = self._read_conv("ufm_Pu_col")
            Ag_col = self._read_conv("ufm_Ag_col")
        except Exception as exc:
            messagebox.showerror("Erro de entrada", str(exc))
            return

        try:
            if Lconn_nbolts < 2:
                raise ValueError("O numero de parafusos/pontos na linha da diagonal deve ser >= 2.")
            Lconn = (Lconn_nbolts - 1) * Lconn_pitch

            ufm_in = ufm_calc.UFMInput(Pr=Pr, theta_deg=theta, eb=eb, ec=ec, alpha=alpha)
            Lw = ufm_calc.whitmore_width(Lconn, w0)
            sizing_in = ufm_calc.GussetSizingInput(ufm=ufm_in, tp_trial=tp_list, Lw=Lw,
                                                     Lc=Lc, K=K, Fy=Fy_plate,
                                                     edge_beam=edge_beam, edge_col=edge_col)
            sizing = ufm_calc.size_gusset_plate(sizing_in)
            res = sizing["ufm"]

            weld_chk = ufm_calc.fillet_weld_strength(Fexx, weld_size, weld_length, weld_nlines)
            bolt_shear = ufm_calc.bolt_shear_strength(Fnv, dbolt, nbolts)
            bolt_bearing = ufm_calc.bolt_bearing_strength(dbolt, tply, Fuply)

            hss_chk = ufm_calc.hss_sidewall_plastification(Fy_col, t_col, La, B_col, branch_w,
                                                              Pu_col, Ag_col)
        except Exception as exc:
            messagebox.showerror("Erro de calculo", str(exc))
            return

        self._last_ufm = dict(res=res, Lw=Lw, sizing=sizing, weld_chk=weld_chk,
                               bolt_shear=bolt_shear, bolt_bearing=bolt_bearing, hss_chk=hss_chk,
                               Pr=Pr, nbolts=nbolts, weld_nlines=weld_nlines)

        uL, uS, uF = self._u("length"), self._u("stress"), self._u("force")
        f = self._fmt
        L = []
        L.append("=" * 62)
        L.append("METODO DAS FORCAS UNIFORMES (UFM) - AISC Manual Parte 13")
        L.append("=" * 62)
        for n in res.notes:
            if n.startswith("beta calculado automaticamente") or n.startswith("alpha calculado automaticamente"):
                continue  # ja exibido abaixo, com a unidade correta
            L.append(f"  * {n}")
        if not res.compat_ok:
            L.append("  !! VERIFICAR: geometria nao satisfaz a equacao de compatibilidade !!")
        L.append(f"alpha = {f(res.alpha,'length'):.3f} {uL}    beta = {f(res.beta,'length'):.3f} {uL}")
        L.append(f"r     = {f(res.r,'length'):.3f} {uL}")
        L.append(f"L (linha da diagonal, calculado) = ({Lconn_nbolts:g}-1) x {f(Lconn_pitch,'length'):g} {uL} = {f(Lconn,'length'):.3f} {uL}")
        L.append("")
        L.append(f"Forcas nas interfaces ({uF}):")
        L.append(f"  Vrc (cisalhamento chapa-coluna) = {f(res.Vrc,'force'):8.2f}")
        L.append(f"  Hrc (axial chapa-coluna)        = {f(res.Hrc,'force'):8.2f}")
        L.append(f"  Vrb (axial chapa-viga)          = {f(res.Vrb,'force'):8.2f}")
        L.append(f"  Hrb (cisalhamento chapa-viga)   = {f(res.Hrb,'force'):8.2f}")
        L.append("")
        L.append("-" * 62)
        L.append("DIMENSOES RECOMENDADAS DA CHAPA")
        L.append("-" * 62)
        L.append(f"Comprimento minimo ao longo da viga   ~= {f(sizing['dim_beam'],'length'):.2f} {uL}  (alpha + margem)")
        L.append(f"Comprimento minimo ao longo da coluna ~= {f(sizing['dim_col'],'length'):.2f} {uL}  (beta + margem)")
        L.append(f"Largura de Whitmore, Lw = {f(Lw,'length'):.2f} {uL}")
        L.append("")
        L.append("Verificacao de flambagem por espessura candidata (Pr = {:.1f} {}):".format(f(Pr,'force'), uF))
        for t in sizing["trials"]:
            flag = "OK " if t["ok"] else "não passa"
            L.append(f"  tp = {f(t['tp'],'length'):.3f} {uL}  ->  phiPn = {f(t['phiPn'],'force'):7.1f} {uF}  (KL/r={t['KLr']:5.1f})  [{flag}]")
        if sizing["tp_recommended"]:
            L.append(f"\n  >> Espessura minima recomendada (flambagem): tp = {f(sizing['tp_recommended'],'length'):.3f} {uL}")
        else:
            L.append("\n  >> NENHUMA espessura candidata atende a flambagem - aumente Lw, reduza Lc/K ou Fy.")
        L.append("")
        L.append("-" * 62)
        L.append("VERIFICACAO RAPIDA DE SOLDA DE FILETE (Spec. Eq. J2-4)")
        L.append("-" * 62)
        L.append(f"phiRn = {f(weld_chk['phiRn'],'force'):.1f} {uF}  ({weld_nlines} linha(s) de {f(weld_length,'length'):.2f} {uL}, perna {f(weld_size,'length'):.3f} {uL})")
        L.append(f"  Utilizacao vs Pr: {Pr/weld_chk['phiRn']:.2f}" if weld_chk['phiRn'] > 0 else "")
        L.append("")
        L.append("-" * 62)
        L.append("VERIFICACAO RAPIDA DE PARAFUSOS (grupo concentrico)")
        L.append("-" * 62)
        L.append(f"Cisalhamento: phiRn = {f(bolt_shear['phiRn_total'],'force'):.1f} {uF} ({nbolts} parafusos)")
        L.append(f"Esmagamento (por parafuso): phiRn = {f(bolt_bearing['phiRn'],'force'):.1f} {uF}/parafuso")
        L.append(f"  Esmagamento total (grupo): phiRn = {f(bolt_bearing['phiRn']*nbolts,'force'):.1f} {uF}")
        L.append("  (Nota: para grupos EXCENTRICOS, use eccentric_bolt_group_elastic() no")
        L.append("   modulo ufm_calc.py, informando as coordenadas de cada parafuso.)")
        L.append("")
        L.append("-" * 62)
        L.append("PLASTIFICACAO DA PAREDE DE COLUNA HSS (AISC Design Guide 24)")
        L.append("-" * 62)
        L.append(f"beta (largura ramo/coluna) = {hss_chk['beta']:.3f}")
        L.append(f"Qf = {hss_chk['Qf']:.3f}   (U = {hss_chk['U']:.3f})")
        L.append(f"phiRn = {f(hss_chk['phiRn'],'force'):.1f} {uF}")
        L.append(f"  {hss_chk['limit_note']}")

        self.txt_ufm.delete("1.0", tk.END)
        self.txt_ufm.insert(tk.END, "\n".join(L))

    def _read_float(self, key):
        try:
            return float(self.vars[key].get())
        except ValueError:
            raise ValueError(f"Valor invalido no campo '{key}': {self.vars[key].get()!r}")

    def _read_conv(self, key):
        """Le um campo e converte para unidades internas (imperial: in,
        ksi, kips, in2), de acordo com o tipo de grandeza do campo e o
        sistema de unidades atualmente selecionado na interface."""
        raw = self._read_float(key)
        kind = FIELD_UNITS.get(key)
        return to_internal(raw, kind, self.unit_system.get())

    def _u(self, kind):
        """Abreviacao da unidade atual para o tipo de grandeza informado
        ('length', 'stress', 'force', 'area')."""
        return UNIT_LABELS[self.unit_system.get()][kind]

    def _fmt(self, value, kind):
        """Converte um valor calculado (sempre em unidades internas /
        imperiais) para o sistema de unidades atual, para exibicao."""
        if value is None:
            return None
        return from_internal(value, kind, self.unit_system.get())

    # ------------------------------------------------------------------
    def calculate(self):
        try:
            n_bolts = self._read_float("n_bolts")
            pitch = self._read_conv("pitch")
            if n_bolts < 2:
                raise ValueError("O numero de parafusos deve ser >= 2 (e necessario ao menos "
                                  "um espacamento para definir o comprimento da linha, L).")
            L = (n_bolts - 1) * pitch  # em unidades internas (in)
            L_disp = self._fmt(L, "length")
            pitch_disp = self._fmt(pitch, "length")
            self.lbl_L_computed.config(
                text=f"L (calculado) = ({n_bolts:g} - 1) x {pitch_disp:g} {self._u('length')} "
                     f"= {L_disp:.3f} {self._u('length')}")

            gi = GussetInput(
                H=self._read_conv("H"), W=self._read_conv("W"),
                a=self._read_conv("a"), b=self._read_conv("b"),
                L=L, Le=self._read_conv("Le"), s=self._read_conv("s"),
                theta_b_deg=self._read_float("theta_b_deg"),
                theta_c_deg=self._read_float("theta_c_deg"),
                theta_bb_deg=self._read_float("theta_bb_deg"),
                theta_cc_deg=self._read_float("theta_cc_deg"),
                tp=self._read_conv("tp"), Fy=self._read_conv("Fy"), Fu=self._read_conv("Fu"),
                Pu=self._read_conv("Pu"), phi_y=self._read_float("phi_y"),
                phi_c=self._read_float("phi_c"), K=self._read_float("K"), E=self._read_conv("E"),
            )
            res = compute_geometry(gi)
            res = strength_checks(gi, res)
        except Exception as exc:
            messagebox.showerror("Erro de entrada", str(exc))
            return

        self.last_gi, self.last_res = gi, res

        draw_gusset(self.ax, gi, res, unit_label=self._u("length"),
                    unit_scale=(MM_PER_IN if self.unit_system.get() == "metric" else 1.0),
                    n_bolts_draw=int(n_bolts))
        self.canvas.draw()

        self.txt.delete("1.0", tk.END)
        self.txt.insert(tk.END, self._format_report(gi, res))

    # ------------------------------------------------------------------
    def _format_report(self, gi, res):
        uL, uS, uF, uA = self._u("length"), self._u("stress"), self._u("force"), self._u("area")
        f = self._fmt
        L = []
        L.append("=" * 70)
        L.append("RESULTADOS - GEOMETRIA DA CHAPA DE NO")
        L.append("=" * 70)
        L.append(f"theta_B (calculado)      = {res.theta_B_deg:8.3f} graus")
        L.append(f"L (linha de parafusos, calculado = (n-1) x pitch) = {f(gi.L,'length'):8.3f} {uL}")
        L.append(f"Largura de Whitmore, Lw  = {f(res.Lw,'length'):8.3f} {uL}")
        L.append(f"c, d, phi                = {f(res.c,'length'):.3f}, {f(res.d,'length'):.3f} {uL}, {res.phi_deg:.3f} graus")
        L.append("")
        if res.yb is not None:
            L.append(f"y_b  = {f(res.yb,'length'):8.3f} {uL}   -> Whitmore ENTRA na viga")
        if res.ybf is not None:
            L.append(f"y_bf = {f(res.ybf,'length'):8.3f} {uL}   -> Whitmore contida (borda livre da viga)")
        if res.yc is not None:
            L.append(f"y_c  = {f(res.yc,'length'):8.3f} {uL}   -> Whitmore ENTRA na coluna")
        if res.ycf is not None:
            L.append(f"y_cf = {f(res.ycf,'length'):8.3f} {uL}   -> Whitmore contida (borda livre da coluna)")
        L.append("")
        L.append(f"L1 = {f(res.L1,'length'):.3f} {uL}" if res.L1 is not None else "L1 = nao existe (y < Lw/2)")
        L.append(f"L2 = {f(res.L2,'length'):.3f} {uL}" if res.L2 is not None else "L2 = nao existe")
        L.append(f"L3 = {f(res.L3,'length'):.3f} {uL}" if res.L3 is not None else "L3 = nao existe (y < Lw/2)")
        L.append(f"    ramo W vs w: {res.branch_W_vs_w}")
        if res.branch_H_vs_j:
            L.append(f"    ramo H vs j: {res.branch_H_vs_j}")
        if res.branch_W_vs_m:
            L.append(f"    ramo W vs m: {res.branch_W_vs_m}")
        L.append("")
        L.append("-" * 70)
        L.append("VERIFICACOES DE RESISTENCIA (secao de Whitmore, LRFD)")
        L.append("-" * 70)
        L.append(f"Area de Whitmore, Aw = Lw x tp        = {f(res.Aw,'area'):8.3f} {uA}")
        L.append(f"Escoamento a tracao: phi*Pn           = {f(res.phiPn_yield,'force'):8.1f} {uF}   (phi={gi.phi_y})")
        Lc_used = getattr(res, "Lc_avg", 0.0)
        KLr = getattr(res, "_KL_r", 0.0)
        L.append(f"Comprimento pseudo-coluna (media)     = {f(Lc_used,'length'):8.3f} {uL}   (K*L/r = {KLr:.1f})")
        L.append(f"Flambagem por compressao: phi*Pn      = {f(res.phiPn_buckling,'force'):8.1f} {uF}   (phi={gi.phi_c}, Fcr={f(res.Fcr,'stress'):.1f} {uS})")
        L.append(f"Bloco de cisalhamento equiv. (W&R)    = {f(res.phiPn_blockshear_equiv,'force'):8.1f} {uF}   (phi=0.75)")
        if gi.Pu > 0:
            L.append("")
            L.append(f"Carga fatorada Pu = {f(gi.Pu,'force'):.1f} {uF}")
            ok_y = "OK" if res.DCR_yield <= 1.0 else "NAO PASSA"
            ok_b = "OK" if res.DCR_buckling <= 1.0 else "NAO PASSA"
            L.append(f"  Pu / phiPn (escoamento) = {res.DCR_yield:.3f}  -> {ok_y}")
            L.append(f"  Pu / phiPn (flambagem)  = {res.DCR_buckling:.3f}  -> {ok_b}")
        L.append("")
        L.append("-" * 70)
        L.append("OBSERVACOES")
        L.append("-" * 70)
        for n in res.notes:
            L.append(f"  - {n}")
        return "\n".join(L)

    # ------------------------------------------------------------------
    def export_pdf(self):
        if self.last_res is None:
            messagebox.showwarning("Aviso", "Calcule antes de exportar.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".pdf",
                                             filetypes=[("PDF", "*.pdf")],
                                             initialfile="relatorio_gusset.pdf")
        if not path:
            return
        try:
            self._export_pdf_impl(path)
            messagebox.showinfo("Sucesso", f"Relatorio salvo em:\n{path}")
        except Exception as exc:
            messagebox.showerror("Erro ao exportar", str(exc))

    def _export_pdf_impl(self, path):
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Preformatted
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        import io

        gi, res = self.last_gi, self.last_res

        # salvar figura atual em PNG temporario
        img_buf = io.BytesIO()
        self.fig.savefig(img_buf, format="png", dpi=200, bbox_inches="tight")
        img_buf.seek(0)

        styles = getSampleStyleSheet()
        doc = SimpleDocTemplate(path, pagesize=letter)
        story = []
        story.append(Paragraph("Relatorio de Calculo - Chapa de No (Gusset Plate)", styles["Title"]))
        story.append(Paragraph(datetime.now().strftime("Gerado em %d/%m/%Y %H:%M"), styles["Normal"]))
        story.append(Spacer(1, 12))
        story.append(Image(img_buf, width=5.5 * inch, height=5.0 * inch))
        story.append(Spacer(1, 12))
        story.append(Preformatted(self._format_report(gi, res), styles["Code"]))
        doc.build(story)


def main():
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass
    app = GussetApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
