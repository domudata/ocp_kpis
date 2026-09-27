# -*- coding: utf-8 -*-
"""
Rapport KPI professionnel (paysage A4) par poste de travail OU par
division (SF01 / SF02), généré directement en PDF via reportlab.

STRUCTURE (refonte du 27/09) — une page = un thème :
  P1  Vue d'ensemble   · en-tête + scores · tableaux KPI Perf / Qualité
                       · chart Anomalies
                       · (division) postes ayant dégradé chaque indicateur,
                         directement sous le chart
  P2  Évolution S-1→S  · tuiles scores / anomalies avec écart
                       · charts butterfly Performance | Qualité
  P3  Backlog caract.  · camemberts Préparation | Planification + clé des codes
                       · nombre total traité (tuiles + chart par code)
  P4  Tendance         · évolution des scores sur les dernières extractions
                       · (division) petits multiples par poste
  P5  Plan d'action

Toutes les données sont préparées par core/report_data.py ; ce module ne
fait que la mise en page. Tous les nouveaux paramètres sont optionnels :
un appel avec l'ancienne signature produit toujours un PDF valide.

RÉSILIENCE : matplotlib est optionnel. S'il est absent, le chart
anomalies passe par Pillow et les autres graphiques sont remplacés par
des tableaux de données équivalents.
"""
import io
import math
import os

import numpy as np
import pandas as pd
from PIL import Image as PILImage, ImageDraw, ImageFont

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    HAS_MATPLOTLIB = True
except Exception:
    HAS_MATPLOTLIB = False
    plt = None
    mpatches = None

from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, HRFlowable, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from core.constants import LOWER_BETTER

# ── Jetons de couleur ────────────────────────────────────────────────────────
# Marque OCP (bandeaux) + palette data-viz validée (séries, statuts, encre).
NAVY_HEX = "#1E3A5F"
ACCENT_HEX = "#F59E0B"          # filet orange sous les bandeaux
INK_HEX = "#0b0b0b"
INK2_HEX = "#52514e"
MUTED_HEX = "#898781"
GRID_HEX = "#e1e0d9"
AXIS_HEX = "#c3c2b7"
SURFACE_HEX = "#ffffff"
PERF_HEX, PERF_PREC_HEX = "#2a78d6", "#b7d2f2"   # série Performance (S / S-1)
QUAL_HEX, QUAL_PREC_HEX = "#4a3aa7", "#c9c3ec"   # série Qualité (S / S-1)
GOOD_HEX, WARN_HEX = "#0ca30c", "#fab219"
SERIOUS_HEX, CRIT_HEX = "#ec835a", "#d03b3b"
UP_TEXT_HEX, DOWN_TEXT_HEX = "#006300", "#d03b3b"
RESTANT_HEX = "#d6d5cf"
# Ordre catégoriel fixe pour les codes de caractérisation (5 codes / catégorie)
CODE_PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]

NAVY = colors.HexColor(NAVY_HEX)
ACCENT = colors.HexColor(ACCENT_HEX)
INK = colors.HexColor(INK_HEX)
INK2 = colors.HexColor(INK2_HEX)
MUTED = colors.HexColor(MUTED_HEX)
GRID = colors.HexColor(GRID_HEX)
LGREY = colors.HexColor("#F4F4F1")
WHITE = colors.white
GOOD = colors.HexColor(GOOD_HEX)
WARN = colors.HexColor(WARN_HEX)
CRIT = colors.HexColor(CRIT_HEX)
PERF_C = colors.HexColor(PERF_HEX)
QUAL_C = colors.HexColor(QUAL_HEX)
# alias conservés pour compatibilité (anciens imports)
GREEN, ORANGE, RED, BLUE, GREY, MGREY, DARK = GOOD, WARN, CRIT, PERF_C, INK2, GRID, INK

PAGE_W, PAGE_H = landscape(A4)
MARGIN_X = 1.0 * cm
MARGIN_TOP = 0.9 * cm
MARGIN_BOTTOM = 1.3 * cm
CONTENT_W = PAGE_W - 2 * MARGIN_X          # 27.7 cm
FRAME_H = PAGE_H - MARGIN_TOP - MARGIN_BOTTOM - 12  # hauteur utile réelle


# ── Polices ──────────────────────────────────────────────────────────────────
def _register_unicode_font():
    """DejaVu Sans (livrée avec matplotlib) pour les flèches ▲▼ dans le PDF."""
    try:
        if not HAS_MATPLOTLIB:
            return False
        base = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
        pdfmetrics.registerFont(TTFont("DejaVu", os.path.join(base, "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", os.path.join(base, "DejaVuSans-Bold.ttf")))
        return True
    except Exception:
        return False


HAS_DEJAVU = _register_unicode_font()
F_REG = "DejaVu" if HAS_DEJAVU else "Helvetica"
F_BOLD = "DejaVu-Bold" if HAS_DEJAVU else "Helvetica-Bold"
UP, DOWN = ("▲", "▼") if HAS_DEJAVU else ("+", "-")

RC = {
    "font.family": "DejaVu Sans",
    "font.size": 7,
    "axes.edgecolor": AXIS_HEX,
    "axes.labelcolor": INK2_HEX,
    "axes.titlesize": 8.5,
    "axes.titleweight": "bold",
    "axes.titlecolor": INK_HEX,
    "xtick.color": MUTED_HEX,
    "ytick.color": INK2_HEX,
    "xtick.labelsize": 6.5,
    "ytick.labelsize": 6.5,
    "figure.facecolor": SURFACE_HEX,
    "axes.facecolor": SURFACE_HEX,
}


# ── Helpers génériques ───────────────────────────────────────────────────────
def _get_pillow_font(size=12, bold=False):
    candidates = [
        "arialbd.ttf" if bold else "arial.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "LiberationSans-Bold.ttf" if bold else "LiberationSans.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def _fig_buf(fig, dpi=200):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                facecolor=SURFACE_HEX, pad_inches=0.05)
    plt.close(fig)
    buf.seek(0)
    return buf


def _img(buf, max_w, max_h):
    """Image reportlab mise à l'échelle SANS déformation (ratio conservé)."""
    iw, ih = PILImage.open(buf).size
    buf.seek(0)
    s = min(max_w / iw, max_h / ih)
    return Image(buf, width=iw * s, height=ih * s)


def _style(name, **kw):
    base = dict(fontName=F_REG, fontSize=8, leading=10, textColor=INK)
    base.update(kw)
    return ParagraphStyle(name=name, **base)


def _p(text, **kw):
    return Paragraph(text, _style(f"p{hash((text, tuple(sorted(kw.items()))))}", **kw))


def _no_data_box(msg):
    t = Table([[_p(msg, fontSize=8, textColor=INK2, leading=11)]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LGREY),
        ("BOX", (0, 0), (-1, -1), 0.4, GRID),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def _section_title(text, accent=NAVY, width=None):
    t = Table([[_p(text, fontName=F_BOLD, fontSize=9.5, textColor=INK, leading=12)]],
              colWidths=[width or CONTENT_W])
    t.setStyle(TableStyle([
        ("LINEBEFORE", (0, 0), (0, 0), 3, accent),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    return t


def _bandeau(titre, date_str):
    t = Table([[_p(titre, fontName=F_BOLD, fontSize=13, textColor=WHITE, leading=16),
                _p(f"Période : {date_str}", fontSize=8, textColor=colors.HexColor("#CBD5E1"),
                   alignment=TA_RIGHT)]],
              colWidths=[CONTENT_W - 6 * cm, 6 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return [t, HRFlowable(width="100%", thickness=2.5, color=ACCENT, spaceAfter=7)]


def _fmt_delta(prec, act, lower_better=False, unite=" pt", decimals=1):
    """Texte coloré de l'écart S-1 → S (vert = amélioration, rouge = dégradation)."""
    if prec is None or act is None:
        return f'<font color="{MUTED_HEX}">—</font>'
    d = act - prec
    if abs(d) < 0.05:
        return f'<font color="{MUTED_HEX}">= stable</font>'
    better = (d < 0) if lower_better else (d > 0)
    col = UP_TEXT_HEX if better else DOWN_TEXT_HEX
    arrow = UP if d > 0 else DOWN
    return f'<font color="{col}"><b>{arrow} {d:+.{decimals}f}{unite}</b></font>'


def _tiles(items, width=CONTENT_W, height=1.75 * cm, value_size=15):
    """
    Rangée de tuiles KPI. items : liste de dict
      {"label", "value", "sub" (html), "accent" (hex), "highlight" (bool)}
    """
    n = len(items)
    gap = 0.25 * cm
    w = (width - gap * (n - 1)) / n
    cells, col_w = [], []
    for i, it in enumerate(items):
        inner = Table([
            [_p(it["label"].upper(), fontName=F_BOLD, fontSize=6.2, textColor=INK2, leading=7.5)],
            [_p(it["value"], fontName=F_BOLD, fontSize=value_size, textColor=INK,
                leading=value_size + 2)],
            [_p(it.get("sub", ""), fontSize=6.5, textColor=INK2, leading=8)],
        ], colWidths=[w - 0.1 * cm])
        bg = colors.HexColor("#EAF6EA") if it.get("highlight") else WHITE
        inner.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), bg),
            ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor(it.get("accent", NAVY_HEX))),
            ("BOX", (0, 0), (-1, -1), 0.4, GRID),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ]))
        cells.append(inner)
        col_w.append(w)
        if i < n - 1:
            cells.append("")
            col_w.append(gap)
    t = Table([cells], colWidths=col_w)
    t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


def _color_for(val, cible, lower, mode_conformite=False):
    """Couleur de statut (vert/orange/rouge) du verdict KPI."""
    val = round(val)
    if mode_conformite:
        return GOOD if val >= 90 else (WARN if val >= 70 else CRIT)
    if lower:
        return GOOD if val <= cible else (WARN if val <= cible + 5 else CRIT)
    return GOOD if val >= cible else (WARN if val >= cible - 5 else CRIT)


# ── Tableau KPI ──────────────────────────────────────────────────────────────
def _kpi_table_flowable(title, kpi_dict, cibles, accent_hex, styles=None,
                        mode_conformite=False, width=8.6 * cm):
    accent = colors.HexColor(accent_hex)
    head = "% postes conf." if mode_conformite else "Val."
    rows = [["Indicateur", head, "Cible"]]
    cell_colors = []
    for k, v in kpi_dict.items():
        cible = cibles.get(k, 100)
        lower = k in LOWER_BETTER
        c = _color_for(v, cible, lower, mode_conformite)
        rows.append([k, f"{v:.0f}%", f"{'≤' if lower else '≥'}{cible:.0f}"])
        cell_colors.append(c)
    t = Table(rows, colWidths=[width - 3.3 * cm, 1.9 * cm, 1.4 * cm], repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), accent),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, -1), F_REG),
        ("FONTNAME", (0, 0), (-1, 0), F_BOLD),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("TEXTCOLOR", (0, 1), (-1, -1), INK),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, GRID),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LGREY]),
    ]
    for i, c in enumerate(cell_colors, start=1):
        style += [
            ("BACKGROUND", (1, i), (1, i), c),
            ("TEXTCOLOR", (1, i), (1, i), INK if c is WARN else WHITE),
            ("FONTNAME", (1, i), (1, i), F_BOLD),
        ]
    t.setStyle(TableStyle(style))
    return t


# ═════════════════════════════════════════════════════════════════════════════
# GRAPHIQUES — tous dessinés à leur taille d'impression exacte (w_cm × h_cm),
# pour que les textes gardent leur taille réelle dans le PDF (pas de
# réduction). Seuils de sévérité partagés avec core/report_data.py.
# ═════════════════════════════════════════════════════════════════════════════
SEUIL_CRITIQUE, SEUIL_MODERE = 0.66, 0.33


def _severite_hex(v, max_v):
    r = v / max_v if max_v else 0
    return CRIT_HEX if r >= SEUIL_CRITIQUE else (SERIOUS_HEX if r >= SEUIL_MODERE else PERF_HEX)


def _figure(w_cm, h_cm, dpi=220):
    return plt.figure(figsize=(w_cm / 2.54, h_cm / 2.54), dpi=dpi)


def _save(fig, dpi=220):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor=SURFACE_HEX)
    plt.close(fig)
    buf.seek(0)
    return buf


def _clean(ax, keep=("left",)):
    for sp in ("top", "right", "bottom", "left"):
        ax.spines[sp].set_visible(sp in keep)
    ax.tick_params(length=0)


# ── Anomalies par indicateur ────────────────────────────────────────────────
def _anomalies_entries(anomalies, short_labels):
    entries = sorted([(k, v) for k, v in anomalies.items() if v > 0], key=lambda x: x[1])
    return [(short_labels.get(k, k), v) for k, v in entries]


def _chart_anomalies_mpl(anomalies, short_labels, w_cm, h_cm):
    entries = _anomalies_entries(anomalies, short_labels)
    if not entries:
        return None
    labels = [e[0] for e in entries]
    valeurs = [e[1] for e in entries]
    max_v = max(valeurs)
    with plt.rc_context(RC):
        fig = _figure(w_cm, h_cm)
        ax = fig.add_axes([2.55 / w_cm, 0.55 / h_cm, 1 - 3.25 / w_cm, 1 - 0.65 / h_cm])
        ax.barh(labels, valeurs, color=[_severite_hex(v, max_v) for v in valeurs],
                height=0.68, edgecolor="white", linewidth=0.8)
        for i, v in enumerate(valeurs):
            ax.text(v + max_v * 0.015, i, str(v), va="center", fontsize=6,
                    color=INK_HEX, fontweight="bold")
        ax.set_xticks([])
        ax.set_xlim(0, max_v * 1.12)
        ax.set_ylim(-0.6, len(labels) - 0.4)
        ax.tick_params(axis="y", labelsize=6, labelcolor=INK_HEX)
        _clean(ax)
        handles = [mpatches.Patch(color=CRIT_HEX, label="Critique (≥ 66 % du max)"),
                   mpatches.Patch(color=SERIOUS_HEX, label="Modéré (33–66 %)"),
                   mpatches.Patch(color=PERF_HEX, label="Faible")]
        fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, fontsize=5.3,
                   labelcolor=INK2_HEX, handlelength=1, columnspacing=1, bbox_to_anchor=(0.5, 0.0))
        return _save(fig)


def _chart_anomalies_pillow(anomalies, short_labels, w_cm, h_cm):
    entries = _anomalies_entries(anomalies, short_labels)
    if not entries:
        return None
    labels = [e[0] for e in entries][::-1]
    valeurs = [e[1] for e in entries][::-1]
    max_v = max(valeurs)
    W, row_gap = 850, 42
    img = PILImage.new("RGB", (W, max(200, len(entries) * row_gap + 30)), SURFACE_HEX)
    draw = ImageDraw.Draw(img)
    f_label, f_val = _get_pillow_font(12), _get_pillow_font(12, bold=True)
    left_x = 240
    for i, (lab, val) in enumerate(zip(labels, valeurs)):
        y = 15 + i * row_gap
        draw.text((left_x - 12, y + 4), lab, fill=INK_HEX, font=f_label, anchor="ra")
        bw = max(6, int((W - left_x - 90) * val / max_v))
        draw.rounded_rectangle([left_x + 2, y, left_x + 2 + bw, y + 24], radius=4,
                               fill=_severite_hex(val, max_v))
        draw.text((left_x + 10 + bw, y + 4), str(val), fill=INK_HEX, font=f_val)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _chart_anomalies(anomalies, short_labels, w_cm=9.9, h_cm=4.4):
    if HAS_MATPLOTLIB:
        try:
            buf = _chart_anomalies_mpl(anomalies, short_labels, w_cm, h_cm)
            if buf:
                return buf
        except Exception:
            pass
    try:
        return _chart_anomalies_pillow(anomalies, short_labels, w_cm, h_cm)
    except Exception:
        return None


# ── Postes impactants (% d'impact) — divisions uniquement ───────────────────
def _chart_impact(impact, short_labels, w_cm, h_cm):
    """
    Un panneau par indicateur critique : postes de travail qui génèrent ses
    anomalies, avec nombre et % d'impact (part des anomalies de l'indicateur).
    """
    if not impact or not HAS_MATPLOTLIB:
        return None
    n_pan = 3
    pan_w = w_cm / n_pan
    lab_w, val_w, top_h = 1.75, 1.55, 0.5
    with plt.rc_context(RC):
        fig = _figure(w_cm, h_cm)
        for i, pan in enumerate(impact[:n_pan]):
            rows = [(d["poste"], d["nb"], d["pct"]) for d in pan["postes"]]
            if pan.get("autres_nb"):
                rows.append((f"Autres ({pan['autres_postes']})", pan["autres_nb"], pan["autres_pct"]))
            x0 = i * pan_w
            ax = fig.add_axes([(x0 + lab_w) / w_cm, 0.08 / h_cm,
                               (pan_w - lab_w - val_w) / w_cm, (h_cm - top_h - 0.12) / h_cm])
            y = np.arange(len(rows))
            vmax = max(r[1] for r in rows) or 1
            col = CRIT_HEX if pan["severite"] == "Critique" else SERIOUS_HEX
            ax.barh(y, [r[1] for r in rows], height=0.66, edgecolor="white", linewidth=0.8,
                    color=[RESTANT_HEX if r[0].startswith("Autres") else col for r in rows])
            for j, (nm, nb, pct) in enumerate(rows):
                ax.text(nb + vmax * 0.03, j, f"{nb} · {pct:.0f}%", va="center", fontsize=5.9,
                        color=INK_HEX, fontweight="bold" if j == 0 else "normal")
            ax.set_yticks(y)
            ax.set_yticklabels([r[0] for r in rows], fontsize=5.9, color=INK_HEX)
            ax.set_ylim(len(rows) - 0.45, -0.55)
            ax.set_xlim(0, vmax)
            ax.set_xticks([])
            _clean(ax)
            fig.text((x0 + 0.1) / w_cm, 1 - 0.08 / h_cm,
                     f"{short_labels.get(pan['kpi'], pan['kpi'])} — {pan['total']} anomalies",
                     ha="left", va="top", fontsize=6.6, fontweight="bold", color=INK_HEX)
            fig.text((x0 + pan_w - 0.25) / w_cm, 1 - 0.08 / h_cm, pan["severite"].upper(),
                     ha="right", va="top", fontsize=5.6, fontweight="bold", color=col)
        return _save(fig)


# ── Butterfly S-1 vs S ──────────────────────────────────────────────────────
BF_ROW_CM, BF_HEAD_CM = 0.37, 0.85


def _chart_butterfly(rows, label_prec, label_act, titre, c_prec, c_act,
                     short_labels, cibles, mode_division, w_cm):
    rows = [r for r in rows if r.get("prec") is not None or r.get("act") is not None]
    if not rows or not HAS_MATPLOTLIB:
        return None
    n = len(rows)
    h_cm = BF_HEAD_CM + n * BF_ROW_CM
    vals = [v for r in rows for v in (r["prec"], r["act"]) if v is not None]
    vmax = max(100.0, max(vals) if vals else 100.0)
    y = np.arange(n)
    xl, xm, xr = 0.30, 0.60, 1.0            # bornes des 3 colonnes (fractions)
    body_top = 1 - BF_HEAD_CM / h_cm
    with plt.rc_context(RC):
        fig = _figure(w_cm, h_cm)
        axL = fig.add_axes([0.0, 0.02, xl, body_top - 0.02])
        axR = fig.add_axes([xm, 0.02, xr - xm, body_top - 0.02])
        for ax in (axL, axR):
            ax.set_ylim(n - 0.5, -0.5)
            ax.set_xticks([])
            ax.set_yticks([])
            for g in (50, 100):
                ax.axvline(g, color=GRID_HEX, linewidth=0.5, zorder=0)
        axL.barh(y, [r["prec"] or 0 for r in rows], height=0.66, color=c_prec,
                 edgecolor="white", linewidth=0.6)
        axR.barh(y, [r["act"] or 0 for r in rows], height=0.66, color=c_act,
                 edgecolor="white", linewidth=0.6)
        axL.set_xlim(vmax * 1.2, 0)
        axR.set_xlim(0, vmax * 1.62)
        _clean(axL, keep=("right",))
        _clean(axR, keep=("left",))
        for i, r in enumerate(rows):
            if r["prec"] is not None:
                axL.text(r["prec"] + vmax * 0.02, i, f"{r['prec']:.0f}%", ha="right",
                         va="center", fontsize=5.5, color=INK2_HEX)
            if r["act"] is not None:
                axR.text(r["act"] + vmax * 0.02, i, f"{r['act']:.0f}%", ha="left",
                         va="center", fontsize=5.5, color=INK_HEX, fontweight="bold")
            lab = short_labels.get(r["kpi"], r["kpi"])
            if not mode_division and cibles.get(r["kpi"]) is not None:
                lab += f" ({'≤' if r['kpi'] in LOWER_BETTER else '≥'}{cibles[r['kpi']]:.0f})"
            y_fig = 0.02 + (body_top - 0.02) * (1 - (i + 0.5) / n)
            fig.text((xl + xm) / 2, y_fig, lab, ha="center", va="center", fontsize=5.7,
                     color=INK_HEX)
            if r["prec"] is not None and r["act"] is not None:
                d = r["act"] - r["prec"]
                if abs(d) < 0.05:
                    txt, col = "=", MUTED_HEX
                else:
                    better = (d < 0) if r.get("lower") else (d > 0)
                    txt = f"{'▲' if d > 0 else '▼'} {d:+.1f}"
                    col = UP_TEXT_HEX if better else DOWN_TEXT_HEX
                axR.text(vmax * 1.6, i, txt, ha="right", va="center", fontsize=5.5,
                         color=col, fontweight="bold")
        top1 = 1 - 0.1 / h_cm
        top2 = 1 - 0.5 / h_cm
        fig.text(0.0, top1, titre, ha="left", va="top", fontsize=6.8, fontweight="bold", color=INK_HEX)
        fig.text(xl - 0.005, top2, label_prec, ha="right", va="top", fontsize=6, color=INK2_HEX,
                 fontweight="bold")
        fig.text(xm + 0.005, top2, label_act, ha="left", va="top", fontsize=6, color=INK_HEX,
                 fontweight="bold")
        fig.text(0.995, top2, "Écart", ha="right", va="top", fontsize=6, color=INK2_HEX,
                 fontweight="bold")
        return _save(fig), h_cm


def _table_comparaison(rows, label_prec, label_act, short_labels, width):
    """Repli sans matplotlib : même information en tableau."""
    data = [["Indicateur", label_prec, label_act, "Écart"]]
    for r in rows:
        p = "—" if r["prec"] is None else f"{r['prec']:.0f}%"
        a = "—" if r["act"] is None else f"{r['act']:.0f}%"
        data.append([short_labels.get(r["kpi"], r["kpi"]), p, a,
                     _p(_fmt_delta(r["prec"], r["act"], r.get("lower")), fontSize=6.5)])
    t = Table(data, colWidths=[width * 0.46, width * 0.18, width * 0.18, width * 0.18])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, -1), F_REG), ("FONTSIZE", (0, 0), (-1, -1), 6.5),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"), ("LINEBELOW", (0, 0), (-1, -1), 0.3, GRID),
        ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    return t


# ── Tendance des scores ─────────────────────────────────────────────────────
def _chart_tendance(evol_df, w_cm, h_cm, titre):
    if evol_df is None or len(evol_df) < 2 or not HAS_MATPLOTLIB:
        return None
    df = evol_df.reset_index(drop=True)
    x = np.arange(len(df))
    labels = [f"S{pd.Timestamp(d).isocalendar().week} {pd.Timestamp(d).strftime('%d/%m')}"
              for d in df["Date"]]
    allv = [v for v in list(df["Perf"]) + list(df["Qual"]) if v is not None and not pd.isna(v)]
    lo = max(0, math.floor((min(allv) - 6) / 10) * 10) if allv else 0
    with plt.rc_context(RC):
        fig = _figure(w_cm, h_cm)
        ax = fig.add_axes([0.9 / w_cm, 0.5 / h_cm, 1 - 2.3 / w_cm, 1 - 1.0 / h_cm])
        for col, nom, c in (("Perf", "Performance", PERF_HEX), ("Qual", "Qualité", QUAL_HEX)):
            yv = pd.to_numeric(df[col], errors="coerce")
            ax.plot(x, yv, color=c, linewidth=1.8, marker="o", markersize=3.8,
                    markerfacecolor="white", markeredgewidth=1.3, label=nom)
            last = yv.dropna()
            if not last.empty:
                ax.annotate(f"{last.iloc[-1]:.1f}%", (last.index[-1], last.iloc[-1]),
                            xytext=(5, 0), textcoords="offset points", va="center",
                            fontsize=6, fontweight="bold", color=INK_HEX)
        ax.axhline(90, color=MUTED_HEX, linewidth=0.7, linestyle="--", zorder=0)
        ax.set_ylim(lo, 104)
        ax.set_xlim(-0.3, len(df) - 0.7)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=5.5)
        ax.tick_params(axis="y", labelsize=5.5)
        ax.yaxis.grid(True, color=GRID_HEX, linewidth=0.5)
        ax.set_axisbelow(True)
        _clean(ax, keep=("bottom",))
        fig.text(0.9 / w_cm, 1 - 0.08 / h_cm, titre, ha="left", va="top", fontsize=6.6,
                 fontweight="bold", color=INK_HEX)
        ax.legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=3, frameon=False,
                  fontsize=5.6, labelcolor=INK2_HEX, handlelength=1.6, borderaxespad=0.1,
                  handles=ax.get_lines()[:2] + [plt.Line2D([], [], color=MUTED_HEX, linewidth=0.7,
                                                             linestyle="--", label="seuil 90 %")])
        return _save(fig)


# ── Camembert (donut) des codes de caractérisation ─────────────────────────
def _chart_donut(counts, codes, d_cm):
    vals = [int(counts.get(c, 0) or 0) for c in codes]
    total = sum(vals)
    if total == 0 or not HAS_MATPLOTLIB:
        return None
    nz = [(v, CODE_PALETTE[i % len(CODE_PALETTE)]) for i, v in enumerate(vals) if v > 0]
    with plt.rc_context(RC):
        fig = _figure(d_cm, d_cm)
        ax = fig.add_axes([0.02, 0.02, 0.96, 0.96])
        ax.pie([v for v, _ in nz], colors=[c for _, c in nz], startangle=90, counterclock=False,
               wedgeprops=dict(width=0.34, edgecolor="white", linewidth=1.2))
        ax.text(0, 0.1, f"{total}", ha="center", va="center", fontsize=10.5,
                fontweight="bold", color=INK_HEX)
        ax.text(0, -0.22, "OT", ha="center", va="center", fontsize=5.8, color=INK2_HEX)
        ax.set_aspect("equal")
        return _save(fig)


def _table_cle_codes(counts, codes, desc_map, width):
    """Clé des codes : pastille couleur · code · signification · nb · %."""
    total = sum(int(counts.get(c, 0) or 0) for c in codes)
    data = [["", "Code", "Signification", "Nb OT", "%"]]
    for c in codes:
        n = int(counts.get(c, 0) or 0)
        data.append(["", c, _p(desc_map.get(c, ""), fontSize=6.2, leading=7.4),
                     str(n), f"{(n / total * 100) if total else 0:.0f}%"])
    data.append(["", "Total", "", str(total), "100%" if total else "0%"])
    w_desc = width - (0.3 + 1.0 + 1.1 + 0.9) * cm
    t = Table(data, colWidths=[0.3 * cm, 1.0 * cm, w_desc, 1.1 * cm, 0.9 * cm])
    st = [
        ("FONTNAME", (0, 0), (-1, -1), F_REG), ("FONTSIZE", (0, 0), (-1, -1), 6.2),
        ("FONTNAME", (0, 0), (-1, 0), F_BOLD), ("TEXTCOLOR", (0, 0), (-1, 0), INK2),
        ("FONTNAME", (1, 1), (1, -1), F_BOLD), ("FONTNAME", (0, -1), (-1, -1), F_BOLD),
        ("LINEABOVE", (0, -1), (-1, -1), 0.6, INK2),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, GRID),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.1),
        ("LEFTPADDING", (0, 0), (0, -1), 0), ("RIGHTPADDING", (0, 0), (0, -1), 0),
    ]
    for i in range(len(codes)):
        st.append(("BACKGROUND", (0, i + 1), (0, i + 1),
                   colors.HexColor(CODE_PALETTE[i % len(CODE_PALETTE)])))
    t.setStyle(TableStyle(st))
    return t


# ── Nombre traité (backlog caractérisation) ────────────────────────────────
def _chart_traitement(traitement, codes_prep, codes_plan, w_cm, h_cm):
    if not traitement or not HAS_MATPLOTLIB:
        return None
    panels = [("prep", codes_prep, "Préparation"), ("planif", codes_plan, "Planification")]
    pan_w, lab_w, val_w, top_h = w_cm / 2, 1.2, 2.5, 0.45
    with plt.rc_context(RC):
        fig = _figure(w_cm, h_cm)
        for i, (cle, codes, nom) in enumerate(panels):
            data = traitement.get(cle) or {}
            labels = ["TOTAL"] + list(codes)
            prec = [traitement.get(f"{cle}_total_prec", 0)] + \
                   [data.get(c, {}).get("precedent", 0) or 0 for c in codes]
            trt = [traitement.get(f"{cle}_total_traite", 0)] + \
                  [data.get(c, {}).get("traite", 0) for c in codes]
            rest = [max(0, p - t) for p, t in zip(prec, trt)]
            x0 = i * pan_w
            ax = fig.add_axes([(x0 + lab_w) / w_cm, 0.05 / h_cm,
                               (pan_w - lab_w - val_w) / w_cm, (h_cm - top_h - 0.08) / h_cm])
            yy = np.arange(len(labels))
            ax.barh(yy, trt, height=0.66, color=GOOD_HEX, edgecolor="white", linewidth=0.8)
            ax.barh(yy, rest, left=trt, height=0.66, color=RESTANT_HEX, edgecolor="white", linewidth=0.8)
            vmax = max(prec) if max(prec) > 0 else 1
            for j, (p, t) in enumerate(zip(prec, trt)):
                ax.text(p + vmax * 0.02, j, f"{t} / {p}  ({(t / p * 100) if p else 0:.0f}%)",
                        va="center", fontsize=5.8, color=INK_HEX,
                        fontweight="bold" if j == 0 else "normal")
            ax.set_yticks(yy)
            ax.set_yticklabels(labels, fontsize=5.8, color=INK_HEX)
            ax.get_yticklabels()[0].set_fontweight("bold")
            ax.set_ylim(len(labels) - 0.45, -0.55)
            ax.axhline(0.5, color=AXIS_HEX, linewidth=0.6)
            ax.set_xlim(0, vmax)
            ax.set_xticks([])
            _clean(ax)
            fig.text((x0 + 0.1) / w_cm, 1 - 0.06 / h_cm, nom, ha="left", va="top",
                     fontsize=6.6, fontweight="bold", color=INK_HEX)
        handles = [mpatches.Patch(color=GOOD_HEX, label="Traité"),
                   mpatches.Patch(color=RESTANT_HEX, label="Restant")]
        fig.legend(handles=handles, loc="upper right", ncol=2, frameon=False, fontsize=5.6,
                   labelcolor=INK2_HEX, handlelength=1, bbox_to_anchor=(1.0, 1.02))
        return _save(fig)


# ── Pied de page ────────────────────────────────────────────────────────────
def _footer_factory(poste, date_str):
    def _draw(canvas, doc):
        canvas.saveState()
        y = MARGIN_BOTTOM - 0.55 * cm
        canvas.setStrokeColor(GRID)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN_X, y + 0.3 * cm, PAGE_W - MARGIN_X, y + 0.3 * cm)
        canvas.setFont(F_REG, 6.5)
        canvas.setFillColor(INK2)
        canvas.drawString(MARGIN_X, y, f"OCP — Rapport KPI SAP PM · {poste} · {date_str}")
        canvas.drawRightString(PAGE_W - MARGIN_X, y, f"Page {doc.page} / 2")
        canvas.restoreState()
    return _draw


def _hauteur(flowables, width):
    h = 0
    for f in flowables:
        _, fh = f.wrap(width, FRAME_H)
        h += fh + f.getSpaceBefore() + f.getSpaceAfter()
    return h


def _no_pad(t):
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 0),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return t


def _plan_table(plan_sorted, est_division, n_max=None):
    cs = dict(fontSize=6.4, leading=7.8)
    head_val = "% conf." if est_division else "Valeur"
    rows = [["Indicateur", head_val, "Cible", "Anom.", "Responsable", "Action corrective"]]
    lignes = plan_sorted if n_max is None else plan_sorted[:n_max]
    for p in lignes:
        rows.append([_p(str(p["kpi"]), **cs), f"{p['actual']:.0f}%", f"{p['target']:.0f}%",
                     str(p["nb_anom"]), _p(str(p["responsable"]), **cs), _p(str(p["action"]), **cs)])
    reste = len(plan_sorted) - len(lignes)
    if reste > 0:
        rows.append([_p(f"<i>+ {reste} autre(s) indicateur(s) à faible volume d'anomalies</i>",
                        textColor=INK2, **cs), "", "", str(sum(p["nb_anom"] for p in plan_sorted[len(lignes):])),
                     "", ""])
    t = Table(rows, colWidths=[4.4 * cm, 1.3 * cm, 1.2 * cm, 1.2 * cm, 3.0 * cm,
                               CONTENT_W - 11.1 * cm], repeatRows=1)
    st = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), F_BOLD), ("FONTNAME", (0, 1), (-1, -1), F_REG),
        ("FONTSIZE", (0, 0), (-1, -1), 6.4),
        ("ALIGN", (1, 0), (3, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (3, 1), (3, -1), F_BOLD), ("TEXTCOLOR", (3, 1), (3, -1), CRIT),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, GRID),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LGREY]),
        ("TOPPADDING", (0, 0), (-1, -1), 1.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
    ]
    if reste > 0:
        st.append(("SPAN", (0, len(rows) - 1), (2, len(rows) - 1)))
    t.setStyle(TableStyle(st))
    return t


# ═════════════════════════════════════════════════════════════════════════════
# FONCTION PRINCIPALE — rapport en 2 pages
#   Page 1 · Situation : en-tête, KPI, anomalies, (division) postes impactants,
#                        plan d'action
#   Page 2 · Évolution & Backlog : tuiles + tendance, butterfly S-1/S,
#                        camemberts caractérisation + clé, nombre traité
# ═════════════════════════════════════════════════════════════════════════════
def build_poste_report_pdf(
    poste, pscore, qscore, kpi_perf, kpi_qual, cibles,
    anomalies, total_anomalies, plan_action, date_str,
    short_labels=None, mode_conformite=False,
    hist_df=None, vp=None, periode_label="",
    comparaison=None, evolution=None, backlog_counts=None, traitement=None,
    impact_postes=None, codes_prep=None, codes_plan=None,
    desc_prep=None, desc_plan=None, **_ignored,
):
    """
    Construit et retourne les bytes PDF (2 pages, paysage A4) pour un poste
    ou une division (mode_conformite=True). Les données optionnelles
    (comparaison, evolution, backlog_counts, traitement, impact_postes)
    viennent de core/report_data.py ; absentes, la zone concernée affiche
    un message explicite.
    """
    short_labels = short_labels or {}
    est_division = bool(mode_conformite)
    codes_prep = codes_prep or ['ATPD', 'ATMR', 'ATRS', 'ATMO', 'ATER']
    codes_plan = codes_plan or ['ATEI', 'ATAL', 'ATAS', 'AGAR', 'ATHS']
    desc_prep = desc_prep or {}
    desc_plan = desc_plan or {}
    gap = 0.5 * cm
    half_w = (CONTENT_W - gap) / 2
    nom = str(poste).split(" — ")[0]
    p1 = []

    # ═══════════════════════════ PAGE 1 — SITUATION ═════════════════════════
    p_color = GOOD if pscore >= 90 else (WARN if pscore >= 80 else CRIT)
    q_color = GOOD if qscore >= 90 else (WARN if qscore >= 80 else CRIT)

    def badge(label, valeur, couleur):
        return [_p(label, fontName=F_BOLD, fontSize=6.5, textColor=INK2, alignment=TA_CENTER),
                _p(valeur, fontName=F_BOLD, fontSize=14, leading=17, textColor=couleur,
                   alignment=TA_CENTER)]

    badges = Table([[badge("SCORE PERFORMANCE", f"{pscore:.1f}%", p_color),
                     badge("SCORE QUALITÉ", f"{qscore:.1f}%", q_color),
                     badge("ANOMALIES", str(total_anomalies), CRIT)]],
                   colWidths=[3.6 * cm, 3.6 * cm, 3.0 * cm])
    badges.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), WHITE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEAFTER", (0, 0), (1, 0), 0.4, GRID),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    sous = "Synthèse division — taux de conformité des postes" if est_division \
        else "Rapport KPI Performance &amp; Qualité — SAP PM"
    entete = Table([[
        [_p("OCP", fontName=F_BOLD, fontSize=18, leading=20, textColor=WHITE, alignment=TA_CENTER),
         _p("Group", fontSize=6.5, textColor=colors.HexColor("#93C5FD"), alignment=TA_CENTER)],
        [_p(str(poste), fontName=F_BOLD, fontSize=13.5 if len(str(poste)) > 34 else 15,
            leading=17, textColor=WHITE),
         _p(f"{sous} · Période : {date_str}", fontSize=7.5, textColor=colors.HexColor("#CBD5E1"))],
        badges,
    ]], colWidths=[2.2 * cm, CONTENT_W - 2.2 * cm - 10.6 * cm, 10.6 * cm])
    entete.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (1, 0), (1, 0), 8), ("RIGHTPADDING", (2, 0), (2, 0), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    p1 += [entete, HRFlowable(width="100%", thickness=2.5, color=ACCENT, spaceAfter=5)]

    col_w = 8.4 * cm
    t_perf = _kpi_table_flowable("Performance", kpi_perf, cibles, PERF_HEX,
                                 mode_conformite=mode_conformite, width=col_w)
    t_qual = _kpi_table_flowable("Qualité", kpi_qual, cibles, QUAL_HEX,
                                 mode_conformite=mode_conformite, width=col_w)
    perf_block = [_section_title("INDICATEURS DE PERFORMANCE", PERF_C, col_w), Spacer(1, 2), t_perf]
    qual_block = [_section_title("INDICATEURS DE QUALITÉ", QUAL_C, col_w), Spacer(1, 2), t_qual]
    right_w = CONTENT_W - col_w - 0.4 * cm
    ano_w = right_w - col_w - 0.4 * cm
    h_perf = _hauteur(perf_block, col_w)
    h_qual = _hauteur(qual_block, col_w)
    n_ano = sum(1 for v in anomalies.values() if v > 0)
    avec_impact = bool(est_division and impact_postes)
    titre_h = 0.55 * cm
    if avec_impact:
        h_ano = max(3.0 * cm, h_qual - titre_h)
    else:
        h_ano = max(3.0 * cm, min(h_perf - titre_h, (0.75 + n_ano * 0.38) * cm))
    ano_buf = None
    try:
        ano_buf = _chart_anomalies(anomalies, short_labels, ano_w / cm, h_ano / cm)
    except Exception:
        ano_buf = None
    ano_block = [_section_title("ANOMALIES PAR INDICATEUR", CRIT, ano_w), Spacer(1, 2),
                 _img(ano_buf, ano_w, h_ano) if ano_buf
                 else _p("Aucune anomalie détectée.", textColor=INK2)]
    right = [_no_pad(Table([[qual_block, "", ano_block]], colWidths=[col_w, 0.4 * cm, ano_w]))]
    if avec_impact:
        imp_h = 3.35
        imp_buf = _chart_impact(impact_postes, short_labels, right_w / cm, imp_h)
        if imp_buf:
            right += [Spacer(1, 5),
                      _section_title("POSTES IMPACTANTS — ANOMALIES CRITIQUES "
                                     "(nb · % d'impact sur l'indicateur)", CRIT, right_w),
                      Spacer(1, 2), _img(imp_buf, right_w, imp_h * cm)]
    main = _no_pad(Table([[perf_block, "", right]], colWidths=[col_w, 0.4 * cm, right_w]))
    p1 += [main, Spacer(1, 6)]

    plan_sorted = sorted(plan_action, key=lambda p: -p["nb_anom"])
    plan_titre = _section_title(f"PLAN D'ACTION — {len(plan_sorted)} INDICATEUR(S) EN ANOMALIE", NAVY)
    if plan_sorted:
        dispo = FRAME_H - _hauteur(p1, CONTENT_W) - _hauteur([plan_titre, Spacer(1, 2)], CONTENT_W) - 0.3 * cm
        n = len(plan_sorted)
        t_plan = _plan_table(plan_sorted, est_division)
        while n > 1 and _hauteur([t_plan], CONTENT_W) > dispo:
            n -= 1
            t_plan = _plan_table(plan_sorted, est_division, n_max=n)
        p1 += [plan_titre, Spacer(1, 2), t_plan]
    else:
        p1 += [plan_titre, Spacer(1, 2),
               _no_data_box("Aucune anomalie — tous les indicateurs sont conformes.")]

    # ══════════════════════ PAGE 2 — ÉVOLUTION & BACKLOG ════════════════════
    p2 = [PageBreak()]
    if comparaison:
        lp, la = comparaison["label_prec"], comparaison["label_act"]
        p2 += [_section_title(f"ÉVOLUTION {lp} → {la} — {nom}", NAVY), Spacer(1, 3)]
        sp, sq, an = comparaison["score_perf"], comparaison["score_qual"], comparaison["anomalies"]

        def tile(label, pair, accent, lower=False, pct=True):
            prec, act = pair
            u = "%" if pct else ""
            val = "—" if act is None else (f"{act:.1f}{u}" if pct else f"{int(act)}")
            ref = "—" if prec is None else (f"{prec:.1f}{u}" if pct else f"{int(prec)}")
            return {"label": label, "value": val, "accent": accent,
                    "sub": f"{lp} : {ref} &nbsp; "
                           f"{_fmt_delta(prec, act, lower, ' pt' if pct else '', 1 if pct else 0)}"}

        tiles_w = 12.2 * cm
        tuiles = _tiles([tile("Score Performance", sp, PERF_HEX), tile("Score Qualité", sq, QUAL_HEX)],
                        width=tiles_w, value_size=12)
        tuiles2 = _tiles([tile("Total anomalies", an, CRIT_HEX, lower=True, pct=False),
                          {"label": "Indicateurs en anomalie", "accent": NAVY_HEX,
                           "value": str(sum(1 for v in anomalies.values() if v > 0)),
                           "sub": f"sur {len(kpi_perf) + len(kpi_qual)} suivis"}],
                         width=tiles_w, value_size=12)
        tend_w = CONTENT_W - tiles_w - gap
        h_tiles = _hauteur([tuiles, Spacer(1, 3), tuiles2], tiles_w)
        titre_t = "Tendance des scores (division)" if est_division else "Tendance des scores"
        tend = _chart_tendance(evolution, tend_w / cm, h_tiles / cm, titre_t)
        rowA = _no_pad(Table([[[tuiles, Spacer(1, 3), tuiles2], "",
                                _img(tend, tend_w, h_tiles) if tend else ""]],
                             colWidths=[tiles_w, gap, tend_w]))
        p2 += [rowA, Spacer(1, 5)]
        mode_t = "% de postes conformes" if est_division else "valeur de l'indicateur"
        cells = []
        for rows, titre, c_prec, c_act in ((comparaison["perf"], "Performance", PERF_PREC_HEX, PERF_HEX),
                                           (comparaison["qual"], "Qualité", QUAL_PREC_HEX, QUAL_HEX)):
            res = _chart_butterfly(rows, lp, la, f"{titre} — {mode_t}", c_prec, c_act,
                                   short_labels, cibles, est_division, half_w / cm)
            if res:
                buf, h_cm = res
                cells.append(Image(buf, width=half_w, height=h_cm * cm))
            else:
                cells.append(_table_comparaison(rows, lp, la, short_labels, half_w))
        p2 += [_no_pad(Table([[cells[0], "", cells[1]]], colWidths=[half_w, gap, half_w]))]
        note = ("Barre = % des postes conformes à l'indicateur (verdict vert ou orange). "
                if est_division else "Cible entre parenthèses ; pour « ≤ » une baisse est une amélioration. ")
        p2.append(_p(note + f"{UP} amélioration · {DOWN} dégradation. S = dernière extraction, "
                     "S-1 = dernière extraction de la semaine précédente.",
                     fontSize=5.8, textColor=MUTED, leading=7))
    else:
        p2 += [_section_title(f"ÉVOLUTION S-1 → S — {nom}", NAVY), Spacer(1, 3),
               _no_data_box("Comparaison S-1 → S indisponible : l'historique ne contient pas encore "
                            "deux extractions pour ce périmètre. Elle apparaîtra dès la prochaine "
                            "extraction enregistrée.")]
    p2.append(Spacer(1, 6))

    # ── Backlog caractérisation : camemberts + clé des codes ────────────────
    d_bc = backlog_counts.get("date") if backlog_counts else None
    sfx = f" — extraction du {pd.Timestamp(d_bc).strftime('%d/%m/%Y')}" if d_bc is not None else ""
    p2 += [_section_title(f"BACKLOG CARACTÉRISATION{sfx}", GOOD), Spacer(1, 3)]
    if backlog_counts:
        blocs = []
        d_cm = 2.9
        for cle, codes, desc, nom_cat in (("prep", codes_prep, desc_prep, "Préparation"),
                                          ("planif", codes_plan, desc_plan, "Planification")):
            counts = backlog_counts.get(cle) or {}
            donut = _chart_donut(counts, codes, d_cm)
            leg_w = half_w - (d_cm + 0.4) * cm
            gauche = [_p(f"<b>{nom_cat}</b>", fontSize=7, leading=9)]
            gauche.append(Image(donut, width=d_cm * cm, height=d_cm * cm) if donut
                          else _p("Aucun OT caractérisé.", fontSize=6.5, textColor=INK2))
            inner = Table([[gauche, _table_cle_codes(counts, codes, desc, leg_w)]],
                          colWidths=[(d_cm + 0.4) * cm, leg_w])
            inner.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                       ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                       ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                       ("TOPPADDING", (0, 0), (-1, -1), 0),
                                       ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
            blocs.append(inner)
        p2 += [_no_pad(Table([[blocs[0], "", blocs[1]]], colWidths=[half_w, gap, half_w])),
               Spacer(1, 5)]
    else:
        p2 += [_no_data_box("Aucune donnée de backlog caractérisation pour ce périmètre."), Spacer(1, 4)]

    # ── Nombre total traité ─────────────────────────────────────────────────
    if traitement:
        dp, da = traitement.get("date_prec"), traitement.get("date_act")
        tp, tpp = traitement.get("total_traite", 0), traitement.get("total_prec", 0)
        pr, pl = traitement.get("prep_total_traite", 0), traitement.get("planif_total_traite", 0)
        per = f"{pd.Timestamp(dp).strftime('%d/%m')} → {pd.Timestamp(da).strftime('%d/%m')}" if dp is not None else ""
        tile_w = 6.0 * cm
        tuile = _tiles([{"label": f"Nombre total traité ({per})", "value": f"{tp} OT",
                         "accent": GOOD_HEX, "highlight": True,
                         "sub": f"<b>{(tp / tpp * 100) if tpp else 0:.0f}%</b> des {tpp} OT caractérisés "
                                f"au {pd.Timestamp(dp).strftime('%d/%m') if dp is not None else '—'}<br/>"
                                f"Préparation : {pr} · Planification : {pl}"}],
                       width=tile_w, value_size=17)
        h_tr = max(_hauteur([tuile], tile_w), 2.5 * cm)
        chart_w = CONTENT_W - tile_w - gap
        trt = _chart_traitement(traitement, codes_prep, codes_plan, chart_w / cm, h_tr / cm)
        p2.append(_no_pad(Table([[tuile, "", _img(trt, chart_w, h_tr) if trt else ""]],
                                colWidths=[tile_w, gap, chart_w])))
    else:
        p2.append(_no_data_box(
            "<b>Nombre total traité</b> : il compare deux extractions enregistrées du backlog "
            "caractérisation ; une seule est disponible pour l'instant — il sera calculé "
            "automatiquement à la prochaine extraction."))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM,
                            leftMargin=MARGIN_X, rightMargin=MARGIN_X,
                            title=f"Rapport KPI — {poste}", author="OCP — KPI SAP PM")
    footer = _footer_factory(nom, date_str)
    doc.build(p1 + p2, onFirstPage=footer, onLaterPages=footer)
    buf.seek(0)
    return buf.getvalue()
