# -*- coding: utf-8 -*-
"""
Génère un rapport KPI professionnel (2 pages, paysage A4) par poste de
travail, DIRECTEMENT en PDF via reportlab (Python pur).

PAGE 1 — Vue d'ensemble :
  · En-tête avec nom du poste / division + badges de scores
  · Tableaux KPI Performance & Qualité
  · Chart « Anomalies (période sélectionnée) »
  · Chart comparaison 2 semaines (si données historiques disponibles)

PAGE 2 — Suivi & Action :
  · Suivi Sparklines par Poste de Travail (évolution historique)
  · Plan d'action détaillé (tous indicateurs en anomalie)

RÉSILIENCE :
  matplotlib est optionnel. Si matplotlib n'est pas installé dans
  l'environnement (ex: blocage réseau/proxy en local), les graphiques
  sont générés de façon équivalente et nette via Pillow (PIL).
"""
import io
import math
import numpy as np
import pandas as pd
from PIL import Image as PILImage, ImageDraw, ImageFont

# matplotlib est OPTIONNEL : si absent, fallback automatique sur Pillow
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
    Image, PageBreak, HRFlowable,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus.flowables import KeepTogether

from core.constants import LOWER_BETTER

# ── Palette de couleurs ─────────────────────────────────────────────────────
NAVY    = colors.HexColor("#1E3A5F")
NAVY2   = colors.HexColor("#1a3050")
GREEN   = colors.HexColor("#10B981")
ORANGE  = colors.HexColor("#F59E0B")
RED     = colors.HexColor("#EF4444")
BLUE    = colors.HexColor("#2563EB")
LBLUE   = colors.HexColor("#DBEAFE")
GREY    = colors.HexColor("#64748B")
LGREY   = colors.HexColor("#F1F5F9")
MGREY   = colors.HexColor("#E2E8F0")
WHITE   = colors.white
DARK    = colors.HexColor("#1E293B")
TEAL    = colors.HexColor("#0D9488")
PURPLE  = colors.HexColor("#7C3AED")

PAGE_W, PAGE_H = landscape(A4)
CONTENT_W = PAGE_W - 2 * cm  # 27.7 cm utilisable


# ── Helpers police Pillow ───────────────────────────────────────────────────
def _get_pillow_font(size=12, bold=False):
    candidates = [
        "arialbd.ttf" if bold else "arial.ttf",
        "calibrib.ttf" if bold else "calibri.ttf",
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


# ── Helpers couleur ─────────────────────────────────────────────────────────
def _color_for(val, cible, lower, mode_conformite=False):
    """Retourne la couleur (vert/orange/rouge) selon le verdict KPI."""
    val = round(val)
    if mode_conformite:
        return GREEN if val >= 90 else (ORANGE if val >= 70 else RED)
    if lower:
        return GREEN if val <= cible else (ORANGE if val <= cible * 1.5 else RED)
    return GREEN if val >= cible else (ORANGE if val >= cible * 0.9 else RED)


# ── Tableau KPI ─────────────────────────────────────────────────────────────
def _kpi_table_flowable(title, kpi_dict, cibles, accent_hex, styles,
                         mode_conformite=False):
    accent = colors.HexColor(accent_hex)
    rows = [["Indicateur", "Val.", "Cible"]]
    cell_colors = []
    for k, v in kpi_dict.items():
        cible = cibles.get(k, 100)
        lower = k in LOWER_BETTER
        c = _color_for(v, cible, lower, mode_conformite)
        rows.append([k, f"{v:.0f}%", f"{'≤' if lower else '≥'}{cible:.0f}"])
        cell_colors.append(c)

    t = Table(rows, colWidths=[5.4 * cm, 1.6 * cm, 1.6 * cm])
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), accent),
        ("TEXTCOLOR",  (0, 0), (-1, 0), WHITE),
        ("FONTSIZE",   (0, 0), (-1, -1), 7.5),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN",      (1, 0), (-1, -1), "CENTER"),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",       (0, 0), (-1, -1), 0.4, MGREY),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LGREY]),
    ]
    for i, c in enumerate(cell_colors, start=1):
        style += [
            ("BACKGROUND", (1, i), (1, i), c),
            ("TEXTCOLOR",  (1, i), (1, i), WHITE),
            ("FONTNAME",   (1, i), (1, i), "Helvetica-Bold"),
        ]
    t.setStyle(TableStyle(style))
    return t


# ── Chart anomalies horizontal ──────────────────────────────────────────────
def _chart_anomalies_mpl(anomalies, short_labels, periode_label=""):
    """Chart barres horizontales via matplotlib."""
    entries = sorted([(k, v) for k, v in anomalies.items() if v > 0],
                     key=lambda x: x[1])
    if not entries:
        return None

    labels  = [short_labels.get(k, k) for k, _ in entries]
    valeurs = [v for _, v in entries]
    max_v   = max(valeurs)

    bar_colors = []
    for v in valeurs:
        ratio = v / max_v if max_v > 0 else 0
        if ratio >= 0.66:
            bar_colors.append("#EF4444")
        elif ratio >= 0.33:
            bar_colors.append("#F59E0B")
        else:
            bar_colors.append("#3B82F6")

    fig, ax = plt.subplots(figsize=(5.0, max(2.5, len(entries) * 0.55 + 0.6)),
                           dpi=150)
    fig.patch.set_facecolor("#F8FAFC")
    ax.set_facecolor("#F8FAFC")

    bars = ax.barh(labels, valeurs, color=bar_colors, height=0.65,
                   edgecolor="white", linewidth=0.5)
    for bar, v in zip(bars, valeurs):
        ax.text(bar.get_width() + max_v * 0.02,
                bar.get_y() + bar.get_height() / 2,
                str(v), va="center", fontsize=7.5, color="#1E293B",
                fontweight="bold")

    titre = f"Anomalies (période sélectionnée){(' — ' + periode_label) if periode_label else ''}"
    ax.set_title(titre, fontsize=8.5, fontweight="bold", color="#1E3A5F", pad=6)
    ax.set_xticks([])
    ax.tick_params(axis="y", labelsize=7)
    ax.set_xlim(0, max_v * 1.15)
    for spine in ["top", "right", "bottom"]:
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color("#CBD5E1")

    patches = [
        mpatches.Patch(color="#EF4444", label="Critique"),
        mpatches.Patch(color="#F59E0B", label="Modéré"),
        mpatches.Patch(color="#3B82F6", label="Faible"),
    ]
    ax.legend(handles=patches, fontsize=6, loc="lower right",
              framealpha=0.7, edgecolor="#CBD5E1")

    plt.tight_layout(pad=0.4)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor="#F8FAFC")
    plt.close(fig)
    buf.seek(0)
    return buf


def _chart_anomalies_pillow(anomalies, short_labels, periode_label=""):
    """Chart barres horizontales pur Python via Pillow (aucun matplotlib requis)."""
    entries = sorted([(k, v) for k, v in anomalies.items() if v > 0],
                     key=lambda x: x[1])
    if not entries:
        return None

    labels  = [short_labels.get(k, k) for k, _ in entries]
    valeurs = [v for _, v in entries]
    max_v   = max(valeurs) if valeurs else 1

    W = 850
    row_gap = 42
    H = max(260, len(entries) * row_gap + 90)
    img = PILImage.new("RGB", (W, H), "#F8FAFC")
    draw = ImageDraw.Draw(img)

    f_title = _get_pillow_font(15, bold=True)
    f_label = _get_pillow_font(12, bold=False)
    f_val   = _get_pillow_font(12, bold=True)
    f_leg   = _get_pillow_font(10, bold=False)

    titre = f"Anomalies (période sélectionnée){(' — ' + periode_label) if periode_label else ''}"
    draw.text((20, 12), titre, fill="#1E3A5F", font=f_title)

    left_x = 240
    bar_max_w = W - left_x - 90
    y_start = 50

    draw.line([(left_x, y_start - 6), (left_x, y_start + len(entries) * row_gap + 4)],
              fill="#CBD5E1", width=2)

    for i, (lab, val) in enumerate(zip(labels, valeurs)):
        y = y_start + i * row_gap
        draw.text((left_x - 12, y + 4), lab, fill="#1E293B", font=f_label, anchor="ra")
        ratio = val / max_v if max_v > 0 else 0
        c = "#EF4444" if ratio >= 0.66 else ("#F59E0B" if ratio >= 0.33 else "#3B82F6")
        bw = max(6, int(bar_max_w * ratio))
        draw.rounded_rectangle([left_x + 2, y, left_x + 2 + bw, y + 24], radius=4, fill=c)
        draw.text((left_x + 10 + bw, y + 4), str(val), fill="#1E293B", font=f_val)

    # Légende
    leg_y = H - 26
    draw.rounded_rectangle([W - 280, leg_y + 2, W - 266, leg_y + 12], radius=2, fill="#EF4444")
    draw.text((W - 260, leg_y), "Critique", fill="#475569", font=f_leg)
    draw.rounded_rectangle([W - 200, leg_y + 2, W - 186, leg_y + 12], radius=2, fill="#F59E0B")
    draw.text((W - 180, leg_y), "Modéré", fill="#475569", font=f_leg)
    draw.rounded_rectangle([W - 120, leg_y + 2, W - 106, leg_y + 12], radius=2, fill="#3B82F6")
    draw.text((W - 100, leg_y), "Faible", fill="#475569", font=f_leg)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _chart_anomalies(anomalies, short_labels, periode_label=""):
    """Génère le chart des anomalies en utilisant matplotlib ou Pillow."""
    if HAS_MATPLOTLIB:
        try:
            buf = _chart_anomalies_mpl(anomalies, short_labels, periode_label)
            if buf:
                return buf
        except Exception:
            pass
    try:
        return _chart_anomalies_pillow(anomalies, short_labels, periode_label)
    except Exception:
        return None


# ── Chart comparaison 2 semaines ─────────────────────────────────────────────
def _chart_comparaison_semaines_mpl(hist_df, vp, now_ts=None):
    """Chart comparaison via matplotlib."""
    if hist_df is None or hist_df.empty:
        return None
    required_cols = {"Poste de travail", "Date_parsed", "_section"}
    if not required_cols.issubset(hist_df.columns):
        return None

    _now = pd.Timestamp(now_ts) if now_ts is not None else pd.Timestamp.today()
    lundi_act  = _now.normalize() - pd.Timedelta(days=_now.weekday())
    lundi_prec = lundi_act - pd.Timedelta(days=7)
    dim_prec   = lundi_act - pd.Timedelta(days=1)
    dim_act    = lundi_act + pd.Timedelta(days=6)

    dates_all  = hist_df["Date_parsed"].dropna()
    d_act_pool = dates_all[(dates_all >= lundi_act)  & (dates_all <= dim_act)]
    d_prec_pool= dates_all[(dates_all >= lundi_prec) & (dates_all <= dim_prec)]

    if d_act_pool.empty or d_prec_pool.empty:
        return None

    d_act  = d_act_pool.max()
    d_prec = d_prec_pool.max()
    s_act  = d_act.isocalendar().week
    s_prec = d_prec.isocalendar().week

    vp_set = set(vp) if vp else set()
    postes = sorted([p for p in vp_set
                     if p in hist_df["Poste de travail"].unique()])
    if not postes:
        return None

    perf_h = hist_df[hist_df["_section"] == "perf"]
    qual_h = hist_df[hist_df["_section"] == "qual"]

    pp, pa, qp, qa = [], [], [], []
    poste_ok = []
    for p in postes:
        def _get(df, date_ts, col):
            row = df[(df["Poste de travail"] == p) &
                     (df["Date_parsed"] == date_ts)]
            if row.empty or col not in row.columns:
                return 0.0
            try:
                return float(row[col].iloc[0])
            except (TypeError, ValueError):
                return 0.0

        vpa = _get(perf_h, d_act,  "Score Performance")
        vpp = _get(perf_h, d_prec, "Score Performance")
        vqa = _get(qual_h, d_act,  "Score Qualite")
        vqp = _get(qual_h, d_prec, "Score Qualite")

        if vpa == 0 and vpp == 0 and vqa == 0 and vqp == 0:
            continue
        poste_ok.append(p)
        pp.append(vpp); pa.append(vpa)
        qp.append(vqp); qa.append(vqa)

    if not poste_ok:
        return None

    n = len(poste_ok)
    x = np.arange(n)
    w = 0.20

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, max(2.8, n * 0.38 + 1.2)),
                                    dpi=150)
    fig.patch.set_facecolor("#F8FAFC")

    def _plot_half(ax, vals_prec, vals_act, title, c_prec, c_act):
        ax.set_facecolor("#F8FAFC")
        b1 = ax.barh(x - w/2, vals_prec, w, color=c_prec, label=f"S{s_prec}",
                     edgecolor="white", linewidth=0.4)
        b2 = ax.barh(x + w/2, vals_act,  w, color=c_act,  label=f"S{s_act}",
                     edgecolor="white", linewidth=0.4)
        for bar, v in zip(list(b1) + list(b2),
                          list(vals_prec) + list(vals_act)):
            if v > 0:
                ax.text(v + 0.5, bar.get_y() + bar.get_height() / 2,
                        f"{v:.0f}%", va="center", ha="left",
                        fontsize=5.5, color="#374151")
        ax.set_yticks(x)
        ax.set_yticklabels(poste_ok, fontsize=6)
        ax.set_xlim(0, 115)
        ax.axvline(100, color="#94A3B8", linewidth=0.6, linestyle="--")
        ax.set_xticks([0, 25, 50, 75, 100])
        ax.tick_params(axis="x", labelsize=6)
        ax.set_title(title, fontsize=8, fontweight="bold",
                     color="#1E3A5F", pad=5)
        ax.legend(fontsize=6, loc="lower right", framealpha=0.7)
        for sp in ["top", "right"]:
            ax.spines[sp].set_visible(False)
        ax.spines["left"].set_color("#CBD5E1")
        ax.spines["bottom"].set_color("#CBD5E1")

    _plot_half(ax1, pp, pa, f"Performance — S{s_prec} vs S{s_act}",
               "#93C5FD", "#1D4ED8")
    _plot_half(ax2, qp, qa, f"Qualité — S{s_prec} vs S{s_act}",
               "#86EFAC", "#15803D")

    fig.suptitle(f"Comparaison semaines S{s_prec} ({d_prec.strftime('%d/%m')}) "
                 f"→ S{s_act} ({d_act.strftime('%d/%m')})",
                 fontsize=8.5, fontweight="bold", color="#475569", y=1.01)
    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor="#F8FAFC")
    plt.close(fig)
    buf.seek(0)
    return buf


def _chart_comparaison_semaines_pillow(hist_df, vp, now_ts=None):
    """Chart comparaison via Pillow."""
    if hist_df is None or hist_df.empty:
        return None
    required_cols = {"Poste de travail", "Date_parsed", "_section"}
    if not required_cols.issubset(hist_df.columns):
        return None

    _now = pd.Timestamp(now_ts) if now_ts is not None else pd.Timestamp.today()
    lundi_act  = _now.normalize() - pd.Timedelta(days=_now.weekday())
    lundi_prec = lundi_act - pd.Timedelta(days=7)
    dim_prec   = lundi_act - pd.Timedelta(days=1)
    dim_act    = lundi_act + pd.Timedelta(days=6)

    dates_all  = hist_df["Date_parsed"].dropna()
    d_act_pool = dates_all[(dates_all >= lundi_act)  & (dates_all <= dim_act)]
    d_prec_pool= dates_all[(dates_all >= lundi_prec) & (dates_all <= dim_prec)]

    if d_act_pool.empty or d_prec_pool.empty:
        return None

    d_act  = d_act_pool.max()
    d_prec = d_prec_pool.max()
    s_act  = d_act.isocalendar().week
    s_prec = d_prec.isocalendar().week

    vp_set = set(vp) if vp else set()
    postes = sorted([p for p in vp_set
                     if p in hist_df["Poste de travail"].unique()])
    if not postes:
        return None

    perf_h = hist_df[hist_df["_section"] == "perf"]
    qual_h = hist_df[hist_df["_section"] == "qual"]

    def _get(df, date_ts, col, p):
        row = df[(df["Poste de travail"] == p) & (df["Date_parsed"] == date_ts)]
        if row.empty or col not in row.columns:
            return 0.0
        try:
            return float(row[col].iloc[0])
        except (TypeError, ValueError):
            return 0.0

    poste_ok, pp, pa, qp, qa = [], [], [], [], []
    for p in postes:
        vpa = _get(perf_h, d_act,  "Score Performance", p)
        vpp = _get(perf_h, d_prec, "Score Performance", p)
        vqa = _get(qual_h, d_act,  "Score Qualite", p)
        vqp = _get(qual_h, d_prec, "Score Qualite", p)
        if vpa == 0 and vpp == 0 and vqa == 0 and vqp == 0:
            continue
        poste_ok.append(p)
        pp.append(vpp); pa.append(vpa)
        qp.append(vqp); qa.append(vqa)

    if not poste_ok:
        return None

    n = len(poste_ok)
    row_h = 46
    W = 1200
    H = max(260, n * row_h + 110)
    img = PILImage.new("RGB", (W, H), "#F8FAFC")
    draw = ImageDraw.Draw(img)

    f_title = _get_pillow_font(14, bold=True)
    f_sub   = _get_pillow_font(12, bold=True)
    f_label = _get_pillow_font(11, bold=False)
    f_val   = _get_pillow_font(10, bold=True)
    f_leg   = _get_pillow_font(10, bold=False)

    dp_str = d_prec.strftime("%d/%m")
    da_str = d_act.strftime("%d/%m")
    title = f"Comparaison semaines S{s_prec} ({dp_str}) → S{s_act} ({da_str})"
    draw.text((20, 10), title, fill="#1E3A5F", font=f_title)

    half_w = (W - 60) // 2
    panels = [
        (f"Performance — S{s_prec} vs S{s_act}", 20, pp, pa, "#93C5FD", "#1D4ED8"),
        (f"Qualité — S{s_prec} vs S{s_act}", 40 + half_w, qp, qa, "#86EFAC", "#15803D"),
    ]

    for p_title, x_off, vals_p, vals_a, c_prec, c_act in panels:
        draw.text((x_off, 42), p_title, fill="#1E3A5F", font=f_sub)
        p_left = x_off + 150
        bar_area_w = half_w - 200
        y_top = 70
        draw.line([(p_left, y_top), (p_left, y_top + n * row_h)], fill="#CBD5E1", width=1)
        x_100 = p_left + int(bar_area_w * (100 / 115))
        for y_dash in range(y_top, y_top + n * row_h, 8):
            draw.line([(x_100, y_dash), (x_100, y_dash + 4)], fill="#94A3B8", width=1)

        for i, (p_name, vp_val, va_val) in enumerate(zip(poste_ok, vals_p, vals_a)):
            y = y_top + i * row_h
            draw.text((p_left - 10, y + 12), p_name, fill="#374151", font=f_label, anchor="ra")
            bw1 = max(2, int(bar_area_w * (vp_val / 115))) if vp_val > 0 else 0
            if bw1 > 0:
                draw.rectangle([p_left + 1, y + 2, p_left + 1 + bw1, y + 16], fill=c_prec)
                draw.text((p_left + 6 + bw1, y + 2), f"{vp_val:.0f}%", fill="#475569", font=f_val)
            bw2 = max(2, int(bar_area_w * (va_val / 115))) if va_val > 0 else 0
            if bw2 > 0:
                draw.rectangle([p_left + 1, y + 18, p_left + 1 + bw2, y + 32], fill=c_act)
                draw.text((p_left + 6 + bw2, y + 18), f"{va_val:.0f}%", fill="#1E293B", font=f_val)

        leg_y = y_top + n * row_h + 8
        draw.rectangle([p_left, leg_y + 2, p_left + 14, leg_y + 12], fill=c_prec)
        draw.text((p_left + 18, leg_y), f"S{s_prec}", fill="#475569", font=f_leg)
        draw.rectangle([p_left + 65, leg_y + 2, p_left + 79, leg_y + 12], fill=c_act)
        draw.text((p_left + 83, leg_y), f"S{s_act}", fill="#475569", font=f_leg)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _chart_comparaison_semaines(hist_df, vp, now_ts=None):
    """Génère le chart de comparaison des semaines via matplotlib ou Pillow."""
    if HAS_MATPLOTLIB:
        try:
            buf = _chart_comparaison_semaines_mpl(hist_df, vp, now_ts)
            if buf:
                return buf
        except Exception:
            pass
    try:
        return _chart_comparaison_semaines_pillow(hist_df, vp, now_ts)
    except Exception:
        return None


# ── Sparklines par poste ─────────────────────────────────────────────────────
def _chart_sparklines_mpl(hist_df, vp, short_labels=None):
    """Tableau sparklines via matplotlib."""
    if hist_df is None or hist_df.empty:
        return None
    if "Date_parsed" not in hist_df.columns or "Poste de travail" not in hist_df.columns:
        return None

    dates = sorted(hist_df["Date_parsed"].dropna().unique())
    if len(dates) < 2:
        return None

    vp_set = set(vp) if vp else set()
    perf_h = hist_df[hist_df["_section"] == "perf"]
    qual_h = hist_df[hist_df["_section"] == "qual"]
    postes = [p for p in vp_set if p in hist_df["Poste de travail"].unique()]
    if not postes:
        return None
    postes = sorted(postes)

    dates = dates[-6:]
    d_labels = [pd.Timestamp(d).strftime("%d/%m") for d in dates]
    n_postes = len(postes)
    n_dates  = len(dates)

    fig, axes = plt.subplots(n_postes, 2,
                              figsize=(11, max(3, n_postes * 0.9 + 1.0)),
                              dpi=130)
    fig.patch.set_facecolor("#F8FAFC")

    if n_postes == 1:
        axes = [axes]

    fig.suptitle("Suivi Sparklines par Poste de Travail",
                 fontsize=10, fontweight="bold", color="#1E3A5F", y=1.0)

    for col_idx, (label, color_line) in enumerate([
            ("Score Performance (%)", "#1D4ED8"),
            ("Score Qualité (%)",     "#15803D")]):
        axes[0][col_idx].set_title(label, fontsize=8, fontweight="bold",
                                   color=color_line, pad=4)

    for row_idx, poste in enumerate(postes):
        for col_idx, (section, score_col, c_line, c_fill) in enumerate([
                ("perf", "Score Performance", "#2563EB", "#DBEAFE"),
                ("qual", "Score Qualite",     "#059669", "#D1FAE5")]):
            ax = axes[row_idx][col_idx]
            ax.set_facecolor("#FAFAFA")

            df_sec = perf_h if section == "perf" else qual_h
            vals = []
            for d in dates:
                row = df_sec[(df_sec["Poste de travail"] == poste) &
                             (df_sec["Date_parsed"] == d)]
                if row.empty or score_col not in row.columns:
                    vals.append(None)
                else:
                    try:
                        vals.append(float(row[score_col].iloc[0]))
                    except (TypeError, ValueError):
                        vals.append(None)

            clean = [(i, v) for i, v in enumerate(vals) if v is not None]
            if len(clean) >= 2:
                xi = [c[0] for c in clean]
                yi = [c[1] for c in clean]
                ax.fill_between(xi, yi, alpha=0.18, color=c_line)
                ax.plot(xi, yi, color=c_line, linewidth=1.5,
                        marker="o", markersize=3, markerfacecolor="white",
                        markeredgecolor=c_line, markeredgewidth=0.8)
                ax.annotate(f"{yi[-1]:.0f}%",
                            (xi[-1], yi[-1]),
                            xytext=(3, 0), textcoords="offset points",
                            fontsize=6, color=c_line, fontweight="bold",
                            va="center")
            elif len(clean) == 1:
                ax.scatter(clean[0][0], clean[0][1], color=c_line, s=20, zorder=5)

            ax.axhline(90, color="#94A3B8", linewidth=0.5, linestyle="--", alpha=0.6)
            ax.set_ylim(0, 110)
            ax.set_xlim(-0.3, n_dates - 0.7)
            ax.set_xticks(range(n_dates))
            ax.set_xticklabels(d_labels, fontsize=5.5, rotation=30, ha="right")
            ax.set_yticks([0, 50, 90, 100])
            ax.tick_params(axis="y", labelsize=5.5)
            for sp in ["top", "right"]:
                ax.spines[sp].set_visible(False)
            ax.spines["left"].set_color("#CBD5E1")
            ax.spines["bottom"].set_color("#CBD5E1")

            if col_idx == 0:
                ax.set_ylabel(poste, fontsize=6.5, fontweight="bold",
                              color="#374151", rotation=0,
                              labelpad=48, va="center")

    plt.tight_layout(rect=[0.12, 0, 1, 0.97], pad=0.5, h_pad=0.6, w_pad=0.8)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                facecolor="#F8FAFC")
    plt.close(fig)
    buf.seek(0)
    return buf


def _chart_sparklines_pillow(hist_df, vp, short_labels=None):
    """Tableau sparklines via Pillow."""
    if hist_df is None or hist_df.empty:
        return None
    if "Date_parsed" not in hist_df.columns or "Poste de travail" not in hist_df.columns:
        return None
    dates = sorted(hist_df["Date_parsed"].dropna().unique())
    if len(dates) < 2:
        return None
    vp_set = set(vp) if vp else set()
    perf_h = hist_df[hist_df["_section"] == "perf"] if "_section" in hist_df.columns else pd.DataFrame()
    qual_h = hist_df[hist_df["_section"] == "qual"] if "_section" in hist_df.columns else pd.DataFrame()
    postes = sorted([p for p in vp_set if p in hist_df["Poste de travail"].unique()])
    if not postes:
        return None
    dates = dates[-6:]
    d_labels = [pd.Timestamp(d).strftime("%d/%m") for d in dates]
    n_postes = len(postes)
    n_dates = len(dates)

    W = 1200
    row_h = 75
    H = max(240, n_postes * row_h + 80)
    img = PILImage.new("RGB", (W, H), "#F8FAFC")
    draw = ImageDraw.Draw(img)

    f_title = _get_pillow_font(14, bold=True)
    f_sub   = _get_pillow_font(12, bold=True)
    f_label = _get_pillow_font(11, bold=True)
    f_tick  = _get_pillow_font(9, bold=False)
    f_val   = _get_pillow_font(10, bold=True)

    draw.text((20, 10), "Suivi Sparklines par Poste de Travail", fill="#1E3A5F", font=f_title)

    col_w = 460
    p1_x = 220
    p2_x = p1_x + col_w + 30
    draw.text((p1_x, 42), "Score Performance (%)", fill="#1D4ED8", font=f_sub)
    draw.text((p2_x, 42), "Score Qualité (%)", fill="#15803D", font=f_sub)

    y_top = 68
    for row_idx, poste in enumerate(postes):
        y_box = y_top + row_idx * row_h
        draw.text((p1_x - 15, y_box + row_h // 2 - 6), poste, fill="#1E293B", font=f_label, anchor="ra")
        for col_idx, (section_df, col_name, c_line, c_fill, box_x) in enumerate([
            (perf_h, "Score Performance", "#2563EB", "#DBEAFE", p1_x),
            (qual_h, "Score Qualite",     "#059669", "#D1FAE5", p2_x)
        ]):
            box_y = y_box + 2
            box_h = row_h - 18
            draw.rectangle([box_x, box_y, box_x + col_w, box_y + box_h], fill="#FFFFFF", outline="#E2E8F0")
            y_90 = box_y + int(box_h * (1.0 - 0.90))
            for x_dash in range(box_x, box_x + col_w, 8):
                draw.line([(x_dash, y_90), (x_dash + 4, y_90)], fill="#CBD5E1", width=1)
            pts = []
            for d_idx, d in enumerate(dates):
                row = section_df[(section_df["Poste de travail"] == poste) & (section_df["Date_parsed"] == d)]
                if not row.empty and col_name in row.columns and pd.notna(row[col_name].iloc[0]):
                    val = float(row[col_name].iloc[0])
                    px = box_x + 30 + int((col_w - 70) * (d_idx / max(1, n_dates - 1)))
                    clamped = max(0.0, min(105.0, val))
                    py = box_y + int(box_h * (1.0 - (clamped / 105.0)))
                    pts.append((px, py, val))
            if len(pts) >= 2:
                poly = [(pts[0][0], box_y + box_h)] + [(p[0], p[1]) for p in pts] + [(pts[-1][0], box_y + box_h)]
                draw.polygon(poly, fill=c_fill)
                line_pts = [(p[0], p[1]) for p in pts]
                draw.line(line_pts, fill=c_line, width=2)
                for px, py, val in pts:
                    draw.ellipse([px - 3, py - 3, px + 3, py + 3], fill="#FFFFFF", outline=c_line, width=2)
                last_px, last_py, last_val = pts[-1]
                draw.text((last_px + 6, last_py - 6), f"{last_val:.0f}%", fill=c_line, font=f_val)
            elif len(pts) == 1:
                draw.ellipse([pts[0][0] - 4, pts[0][1] - 4, pts[0][0] + 4, pts[0][1] + 4], fill=c_line)
                draw.text((pts[0][0] + 6, pts[0][1] - 6), f"{pts[0][2]:.0f}%", fill=c_line, font=f_val)
            if row_idx == n_postes - 1:
                for d_idx, d_lab in enumerate(d_labels):
                    px = box_x + 30 + int((col_w - 70) * (d_idx / max(1, n_dates - 1)))
                    draw.text((px, box_y + box_h + 3), d_lab, fill="#64748B", font=f_tick, anchor="ma")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _chart_sparklines(hist_df, vp, short_labels=None):
    """Génère le chart sparklines via matplotlib ou Pillow."""
    if HAS_MATPLOTLIB:
        try:
            buf = _chart_sparklines_mpl(hist_df, vp, short_labels)
            if buf:
                return buf
        except Exception:
            pass
    try:
        return _chart_sparklines_pillow(hist_df, vp, short_labels)
    except Exception:
        return None


# ── Titre de section stylisé ─────────────────────────────────────────────────
def _section_title(text, color=NAVY, fs=9.5):
    return Paragraph(
        text,
        ParagraphStyle(name=f"ST_{hash(text)}", fontSize=fs,
                       textColor=color, fontName="Helvetica-Bold",
                       spaceBefore=6, spaceAfter=3),
    )


# ── Fonction principale ───────────────────────────────────────────────────────
def build_poste_report_pdf(
    poste, pscore, qscore, kpi_perf, kpi_qual, cibles,
    anomalies, total_anomalies, plan_action, date_str,
    short_labels=None, mode_conformite=False,
    hist_df=None, vp=None, periode_label="",
):
    """
    Construit et retourne les bytes PDF (2 pages, paysage A4) pour un
    poste ou une division.
    """
    short_labels = short_labels or {}
    vp = vp or ([poste] if poste else [])

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitrePoste",   fontSize=18, textColor=WHITE,
                               fontName="Helvetica-Bold", leading=22))
    styles.add(ParagraphStyle(name="TitreSous",    fontSize=10, textColor=WHITE,
                               fontName="Helvetica-Bold", leading=13))
    styles.add(ParagraphStyle(name="SousTitre",    fontSize=8.5,
                               textColor=colors.HexColor("#CBD5E1")))
    styles.add(ParagraphStyle(name="SectionTitre", fontSize=10.5, textColor=NAVY,
                               fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=4))
    styles.add(ParagraphStyle(name="Corps",        fontSize=8, fontName="Helvetica",
                               leading=10))
    styles.add(ParagraphStyle(name="CorpsBlanc",   fontSize=8, fontName="Helvetica",
                               leading=10, textColor=WHITE))

    story = []

    # ════════════════════════════════════════════════════════════════════════
    # PAGE 1 — Vue d'ensemble
    # ════════════════════════════════════════════════════════════════════════

    # ── En-tête ─────────────────────────────────────────────────────────────
    p_color = GREEN if pscore >= 90 else (ORANGE if pscore >= 80 else RED)
    q_color = GREEN if qscore >= 90 else (ORANGE if qscore >= 80 else RED)

    entete_gauche = [
        Paragraph(str(poste), styles["TitrePoste"]),
        Spacer(1, 4),
        Paragraph("Rapport KPI Performance &amp; Qualité — SAP PM OCP", styles["SousTitre"]),
        Paragraph(f"Période : {date_str}", styles["SousTitre"]),
    ]

    badge_style = ParagraphStyle(name="Badge", fontSize=7.5,
                                  fontName="Helvetica-Bold", textColor=GREY,
                                  alignment=TA_CENTER)

    def badge_cell(label, valeur, couleur):
        vs = ParagraphStyle(name=f"BadgeVal_{label[:4]}", fontSize=15,
                             fontName="Helvetica-Bold",
                             textColor=couleur, alignment=TA_CENTER)
        return [Paragraph(label, badge_style), Paragraph(valeur, vs)]

    logo_cell = [
        Paragraph("OCP", ParagraphStyle(name="LogoTxt", fontSize=22,
                                         fontName="Helvetica-Bold",
                                         textColor=WHITE, alignment=TA_CENTER)),
        Paragraph("Group", ParagraphStyle(name="LogoSub", fontSize=7,
                                           textColor=colors.HexColor("#93C5FD"),
                                           alignment=TA_CENTER)),
    ]

    badges_table = Table([[
        badge_cell("SCORE PERFORMANCE", f"{pscore:.1f}%", p_color),
        badge_cell("SCORE QUALITÉ",     f"{qscore:.1f}%", q_color),
        badge_cell("ANOMALIES",          str(total_anomalies), RED),
    ]], colWidths=[3.7 * cm, 3.7 * cm, 3.1 * cm])
    badges_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), WHITE),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (0, 0), 0.5, MGREY),
        ("BOX", (1, 0), (1, 0), 0.5, MGREY),
        ("BOX", (2, 0), (2, 0), 0.5, MGREY),
        ("ROUNDEDCORNERS", [4]),
    ]))

    entete_table = Table(
        [[logo_cell, entete_gauche, badges_table]],
        colWidths=[2.5 * cm, 14.5 * cm, 10.7 * cm]
    )
    entete_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), NAVY),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (0, 0),  8),
        ("LEFTPADDING",   (1, 0), (1, 0), 10),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(entete_table)
    story.append(HRFlowable(width="100%", thickness=3,
                              color=colors.HexColor("#F59E0B"), spaceAfter=8))

    # ── Tableaux KPI + Chart anomalies (3 colonnes) ─────────────────────────
    perf_flow = [
        _section_title("📊 INDICATEURS DE PERFORMANCE",
                        color=colors.HexColor("#059669")),
        Spacer(1, 3),
        _kpi_table_flowable("Performance", kpi_perf, cibles,
                             "#059669", styles, mode_conformite),
    ]
    qual_flow = [
        _section_title("📊 INDICATEURS DE QUALITÉ", color=BLUE),
        Spacer(1, 3),
        _kpi_table_flowable("Qualité", kpi_qual, cibles,
                             "#2563EB", styles, mode_conformite),
    ]

    img_buf = None
    try:
        img_buf = _chart_anomalies(anomalies, short_labels, periode_label)
    except Exception:
        img_buf = None

    if img_buf:
        chart_flow = [
            _section_title("🔺 ANOMALIES (PÉRIODE SÉLECTIONNÉE)", color=RED),
            Spacer(1, 3),
            Image(img_buf, width=9.5 * cm,
                  height=min(7.5 * cm,
                             max(3 * cm,
                                 sum(1 for v in anomalies.values() if v > 0) * 0.55 * cm + 1.2 * cm))),
        ]
    else:
        chart_flow = [
            _section_title("🔺 ANOMALIES (PÉRIODE SÉLECTIONNÉE)", color=RED),
            Spacer(1, 3),
            _no_data_box("Aucune anomalie détectée sur ce poste."),
        ]

    trois_colonnes = Table(
        [[perf_flow, qual_flow, chart_flow]],
        colWidths=[8.6 * cm, 8.6 * cm, 10.5 * cm]
    )
    trois_colonnes.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(trois_colonnes)
    story.append(Spacer(1, 6))

    # ── Comparaison 2 semaines ───────────────────────────────────────────────
    comp_buf = None
    try:
        comp_buf = _chart_comparaison_semaines(hist_df, vp)
    except Exception:
        comp_buf = None

    if comp_buf:
        story.append(HRFlowable(width="100%", thickness=1,
                                  color=MGREY, spaceBefore=2, spaceAfter=4))
        story.append(
            _section_title("📅 COMPARAISON SEMAINE PRÉCÉDENTE vs SEMAINE ACTUELLE",
                            color=NAVY, fs=9.5)
        )
        story.append(Spacer(1, 3))
        story.append(Image(comp_buf, width=CONTENT_W, height=7 * cm))

    # ════════════════════════════════════════════════════════════════════════
    # PAGE 2 — Suivi & Plan d'action
    # ════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())

    # En-tête page 2 (bandeau compact)
    entete2 = Table(
        [[Paragraph(f"{poste} — Suivi &amp; Plan d'action", styles["TitrePoste"]),
          Paragraph(f"Période : {date_str}", styles["SousTitre"])]],
        colWidths=[19.7 * cm, 8.0 * cm]
    )
    entete2.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), NAVY),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(entete2)
    story.append(HRFlowable(width="100%", thickness=3,
                              color=colors.HexColor("#F59E0B"), spaceAfter=8))

    # ── Suivi Sparklines par Poste de Travail ───────────────────────────────
    story.append(_section_title("📈 SUIVI SPARKLINES PAR POSTE DE TRAVAIL",
                                 color=NAVY, fs=10))
    story.append(Spacer(1, 4))

    spark_buf = None
    try:
        spark_buf = _chart_sparklines(hist_df, vp, short_labels)
    except Exception:
        spark_buf = None

    if spark_buf:
        story.append(Image(spark_buf, width=CONTENT_W, height=_spark_height(vp)))
    else:
        story.append(_no_data_box(
            "Données historiques insuffisantes. "
            "Au moins 2 périodes enregistrées sont nécessaires."
        ))

    story.append(Spacer(1, 10))

    # ── Plan d'action ────────────────────────────────────────────────────────
    plan_sorted = sorted(plan_action, key=lambda p: -p["nb_anom"])
    story.append(HRFlowable(width="100%", thickness=1,
                              color=MGREY, spaceBefore=2, spaceAfter=4))
    story.append(
        _section_title(f"⚡ PLAN D'ACTION — INDICATEURS EN ANOMALIE ({len(plan_sorted)})",
                        color=NAVY, fs=10)
    )
    story.append(Spacer(1, 4))

    if plan_sorted:
        cell_style = ParagraphStyle(name="cell", fontSize=7, fontName="Helvetica",
                                     leading=9)
        rows = [["Indicateur", "Valeur", "Cible", "Écart",
                 "Nécessité action", "Responsable", "Action corrective"]]
        necessite_colors = []
        for p in plan_sorted:
            necessite = "✓ Oui" if p["nb_anom"] > 0 else "Non"
            necessite_colors.append(RED if p["nb_anom"] > 0 else GREEN)
            rows.append([
                Paragraph(str(p["kpi"]), cell_style),
                f"{p['actual']:.0f}%",
                f"{p['target']:.0f}%",
                f"{p['ecart']:+.1f}%",
                necessite,
                Paragraph(str(p["responsable"]), cell_style),
                Paragraph(str(p["action"]), cell_style),
            ])
        t = Table(rows,
                  colWidths=[4.2 * cm, 1.5 * cm, 1.5 * cm, 1.5 * cm,
                              2.4 * cm, 3.0 * cm, 13.6 * cm])
        ts = [
            ("BACKGROUND",    (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 7),
            ("ALIGN",         (1, 0), (4, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("GRID",          (0, 0), (-1, -1), 0.4, MGREY),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LGREY]),
        ]
        for i, c in enumerate(necessite_colors, start=1):
            ts += [
                ("BACKGROUND", (4, i), (4, i), c),
                ("TEXTCOLOR",  (4, i), (4, i), WHITE),
                ("FONTNAME",   (4, i), (4, i), "Helvetica-Bold"),
            ]
        t.setStyle(TableStyle(ts))
        story.append(t)
    else:
        story.append(_no_data_box("Aucune anomalie — tous les KPI sont conformes. ✅"))

    # ── Pied de page ─────────────────────────────────────────────────────────
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.5,
                              color=MGREY, spaceAfter=4))
    story.append(
        Paragraph(
            f"Rapport généré automatiquement par le système KPI SAP PM OCP — {date_str}  |  "
            "Toute reproduction est soumise à autorisation.",
            ParagraphStyle(name="footer", fontSize=6, textColor=GREY,
                           alignment=TA_CENTER),
        )
    )

    # ── Build PDF ────────────────────────────────────────────────────
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        topMargin=1 * cm, bottomMargin=1 * cm,
        leftMargin=1 * cm, rightMargin=1 * cm,
    )
    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


# ── Helpers internes ─────────────────────────────────────────────────────────
def _no_data_box(msg):
    return Paragraph(
        msg,
        ParagraphStyle(name=f"nd_{hash(msg)}", fontSize=8, textColor=GREY,
                       fontName="Helvetica", leading=10),
    )


def _spark_height(vp):
    """Hauteur du chart sparklines selon le nombre de postes."""
    n = len(vp) if vp else 1
    return min(18 * cm, max(4 * cm, n * 0.9 * cm + 1.5 * cm))
