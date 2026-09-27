# -*- coding: utf-8 -*-
"""
Présentation PowerPoint KPI (16:9) — même contenu que le rapport PDF
(core/generate_report_pdf.py), réparti sur plusieurs diapositives.

Périmètre = sélection « Poste de travail » de l'application :
  SF1 → Maroc Chimie · SF2 → FEEDS · mixte → OCP · 1 seul poste → ce poste.
Avec plusieurs postes, chaque indicateur est exprimé en % de postes
conformes (même règle que les rapports de division SF01 / SF02).

Diapositives :
   1  Titre + scores
   2  Indicateurs Performance & Qualité (tableaux)
   3  Anomalies par indicateur
   4  Postes impactants — anomalies critiques, % d'impact (plusieurs postes)
   5  Évolution S-1 → S (tuiles + tendance des scores)
   6  Comparaison S-1 vs S — Performance (butterfly)
   7  Comparaison S-1 vs S — Qualité (butterfly)
   8  Backlog caractérisation (camemberts + clé des codes)
   9  Nombre total traité (si 2 extractions du backlog disponibles)
  10+ Plan d'action (réparti sur plusieurs diapositives si nécessaire)

Tous les graphiques sont des graphiques PowerPoint NATIFS (modifiables).
Données : core/report_data.py (identiques au PDF).

Usage dans app.py (inchangé) :
    pptx_bytes = build_presentation(vp, ckdf, ano_map, pa, qa, pscores,
                                    qscores, hist_df, fichier_date)
"""
import io
import os

import pandas as pd
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import (XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION,
                             XL_MARKER_STYLE, XL_TICK_LABEL_POSITION, XL_TICK_MARK)
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

from core.constants import QK, PK, CIBLE, LOWER_BETTER
from core import report_data as rd

# ── Jetons (identiques au rapport PDF) ───────────────────────────────────────
def _rgb(h):
    return RGBColor.from_string(h.lstrip("#").upper())


NAVY, NAVY2 = _rgb("1E3A5F"), _rgb("2A4B74")
ACCENT = _rgb("F59E0B")
INK, INK2, MUTED = _rgb("0B0B0B"), _rgb("52514E"), _rgb("898781")
GRID, AXIS = _rgb("E1E0D9"), _rgb("C3C2B7")
CARD, ROW_ALT = _rgb("F4F6F9"), _rgb("F4F4F1")
WHITE = _rgb("FFFFFF")
PERF, PERF_PREC = _rgb("2A78D6"), _rgb("B7D2F2")
QUAL, QUAL_PREC = _rgb("4A3AA7"), _rgb("C9C3EC")
GOOD, WARN, SERIOUS, CRIT = _rgb("0CA30C"), _rgb("FAB219"), _rgb("EC835A"), _rgb("D03B3B")
UP_TXT, DOWN_TXT = _rgb("006300"), _rgb("D03B3B")
RESTANT = _rgb("D6D5CF")
CODE_PALETTE = [_rgb(h) for h in ("2A78D6", "EB6834", "1BAF7A", "EDA100", "E87BA4")]

FONT = "Calibri"
SW, SH = Inches(13.333), Inches(7.5)
MX = Inches(0.5)                     # marge latérale
CW = SW - 2 * MX                     # largeur utile
TOP = Inches(1.45)                   # début de la zone de contenu
BOTTOM = Inches(6.85)                # fin de la zone de contenu
SEUIL_CRITIQUE, SEUIL_MODERE = rd.SEUIL_CRITIQUE, rd.SEUIL_MODERE


def _short_labels():
    try:
        from core.publish_reports import SHORT_LABELS
        return SHORT_LABELS
    except Exception:
        return {}


def _entity_name(vp):
    """SF1 → Maroc Chimie, SF2 → FEEDS, mixte → OCP, 1 poste → ce poste."""
    vp = list(vp or [])
    if len(vp) == 1:
        return str(vp[0])
    has_sf1 = any(str(p).startswith("SF1") for p in vp)
    has_sf2 = any(str(p).startswith("SF2") for p in vp)
    if has_sf1 and not has_sf2:
        return "Maroc Chimie"
    if has_sf2 and not has_sf1:
        return "FEEDS"
    return "OCP — Maroc Chimie & FEEDS"


# ── Primitives de mise en page ───────────────────────────────────────────────
def _blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def _text(slide, x, y, w, h, runs, size=14, color=INK, bold=False, align=PP_ALIGN.LEFT,
          anchor=MSO_ANCHOR.TOP, font=FONT):
    """runs : str, ou liste de (texte, {size, color, bold, font}) ; "\\n" = nouveau paragraphe."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    if isinstance(runs, str):
        runs = [(runs, {})]
    p = tf.paragraphs[0]
    p.alignment = align
    for txt, st in runs:
        parts = txt.split("\n")
        for i, part in enumerate(parts):
            if i > 0:
                p = tf.add_paragraph()
                p.alignment = align
            if not part:
                continue
            r = p.add_run()
            r.text = part
            f = r.font
            f.name = st.get("font", font)
            f.size = Pt(st.get("size", size))
            f.bold = st.get("bold", bold)
            f.color.rgb = st.get("color", color)
    return tb


def _box(slide, x, y, w, h, fill=CARD, radius=True):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
                                 x, y, w, h)
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    shp.line.fill.background()
    shp.shadow.inherit = False
    if radius:
        shp.adjustments[0] = 0.08
    return shp


def _title(slide, titre, sous_titre=None):
    _text(slide, MX, Inches(0.38), CW, Inches(0.6), titre, size=28, bold=True, color=NAVY)
    if sous_titre:
        _text(slide, MX, Inches(0.98), CW, Inches(0.35), sous_titre, size=13, color=INK2)


def _delta_runs(prec, act, lower=False, unite=" pt", dec=1, size=12):
    if prec is None or act is None:
        return [("—", {"color": MUTED, "size": size})]
    d = act - prec
    if abs(d) < 0.05:
        return [("= stable", {"color": MUTED, "size": size})]
    better = (d < 0) if lower else (d > 0)
    col = UP_TXT if better else DOWN_TXT
    return [("▲ " if d > 0 else "▼ ", {"color": col, "size": size, "font": "Arial", "bold": True}),
            (f"{d:+.{dec}f}{unite}", {"color": col, "size": size, "bold": True})]


def _stat_card(slide, x, y, w, h, label, value, sub_runs=None, value_color=INK, fill=CARD,
               label_color=INK2, value_size=30):
    _box(slide, x, y, w, h, fill=fill)
    pad = Inches(0.22)
    _text(slide, x + pad, y + Inches(0.16), w - 2 * pad, Inches(0.3), label.upper(),
          size=10.5, bold=True, color=label_color)
    _text(slide, x + pad, y + Inches(0.44), w - 2 * pad, Inches(0.62), value,
          size=value_size, bold=True, color=value_color)
    if sub_runs:
        _text(slide, x + pad, y + h - Inches(0.44), w - 2 * pad, Inches(0.32), sub_runs,
              size=11.5, color=INK2)


def _table(slide, x, y, w, headers, rows, col_w, font_size=11, row_h=Inches(0.31),
           header_fill=NAVY, cell_fmt=None, align=None):
    """
    Tableau natif. cell_fmt(r, c) → dict optionnel {fill, color, bold} pour
    la cellule de données (r, c). align : liste d'alignements par colonne.
    """
    n_r, n_c = len(rows) + 1, len(headers)
    gf = slide.shapes.add_table(n_r, n_c, x, y, w, row_h * n_r)
    tbl = gf.table
    tbl.first_row = True
    tbl.horz_banding = False
    tot = sum(col_w)
    for i, cw in enumerate(col_w):
        tbl.columns[i].width = Emu(int(w * cw / tot))
    for r in range(n_r):
        tbl.rows[r].height = row_h
        for c in range(n_c):
            cell = tbl.cell(r, c)
            cell.margin_left = cell.margin_right = Inches(0.07)
            cell.margin_top = cell.margin_bottom = Inches(0.03)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            txt = headers[c] if r == 0 else rows[r - 1][c]
            fmt = {} if r == 0 or cell_fmt is None else (cell_fmt(r - 1, c) or {})
            cell.fill.solid()
            if r == 0:
                cell.fill.fore_color.rgb = header_fill
            else:
                cell.fill.fore_color.rgb = fmt.get("fill", WHITE if r % 2 else ROW_ALT)
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = (align[c] if align else PP_ALIGN.LEFT)
            run = p.add_run()
            run.text = str(txt)
            f = run.font
            f.name = FONT
            f.size = Pt(font_size)
            f.bold = True if r == 0 else fmt.get("bold", False)
            f.color.rgb = WHITE if r == 0 else fmt.get("color", INK)
    return gf


def _style_chart(chart, size=11):
    chart.has_title = False
    chart.font.name = FONT
    chart.font.size = Pt(size)
    chart.font.color.rgb = INK2


def _no_axis_line(axis):
    axis.format.line.fill.background()


def _color_for(val, cible, lower, mode_conformite):
    val = round(val)
    if mode_conformite:
        return GOOD if val >= 90 else (WARN if val >= 70 else CRIT)
    if lower:
        return GOOD if val <= cible else (WARN if val <= cible + 5 else CRIT)
    return GOOD if val >= cible else (WARN if val >= cible - 5 else CRIT)


def _sev_color(v, mx):
    r = v / mx if mx else 0
    return CRIT if r >= SEUIL_CRITIQUE else (SERIOUS if r >= SEUIL_MODERE else PERF)


def _message(slide, x, y, w, h, texte):
    _box(slide, x, y, w, h, fill=CARD)
    _text(slide, x + Inches(0.3), y, w - Inches(0.6), h, texte, size=13, color=INK2,
          anchor=MSO_ANCHOR.MIDDLE)


# ═════════════════════════════════════════════════════════════════════════════
# DIAPOSITIVES
# ═════════════════════════════════════════════════════════════════════════════
def _slide_titre(prs, entity, date_str, syn):
    s = _blank(prs)
    bg = s.background.fill
    bg.solid()
    bg.fore_color.rgb = NAVY
    logo = next((p for p in ("logo.png", "assets/logo.png", "images/logo.png") if os.path.exists(p)), None)
    x_txt = MX
    if logo:
        s.shapes.add_picture(logo, MX, Inches(0.55), height=Inches(1.35))
        x_txt = MX
    _text(s, x_txt, Inches(2.35), Inches(7.2), Inches(0.4), "RAPPORT KPI · SAP PM",
          size=14, bold=True, color=ACCENT)
    _text(s, x_txt, Inches(2.8), Inches(7.4), Inches(1.9), entity, size=44, bold=True, color=WHITE)
    n = len(syn["postes"])
    detail = f"{n} postes de travail" if n > 1 else "Poste de travail"
    _text(s, x_txt, Inches(4.75), Inches(7.2), Inches(0.9),
          f"Indicateurs de Performance & Qualité\n{detail} · extraction du {date_str}",
          size=16, color=_rgb("CBD5E1"))

    cards = [
        ("Score Performance", f"{syn['pscore']:.1f}%"),
        ("Score Qualité", f"{syn['qscore']:.1f}%"),
        ("Anomalies", f"{syn['total_anomalies']}"),
    ]
    cx, cw, ch, gap = Inches(8.55), Inches(4.28), Inches(1.45), Inches(0.28)
    y0 = Inches(1.35)
    for i, (lab, val) in enumerate(cards):
        y = y0 + i * (ch + gap)
        _box(s, cx, y, cw, ch, fill=NAVY2)
        _text(s, cx + Inches(0.3), y + Inches(0.2), cw, Inches(0.3), lab.upper(),
              size=11, bold=True, color=_rgb("CBD5E1"))
        _text(s, cx + Inches(0.3), y + Inches(0.5), cw, Inches(0.8), val, size=40,
              bold=True, color=WHITE)
    return s


def _slide_kpi(prs, entity, syn, sl):
    s = _blank(prs)
    mode = syn["mode_division"]
    _title(s, "Indicateurs de Performance & Qualité",
           f"{entity} — " + ("% de postes conformes par indicateur" if mode else "valeur de chaque indicateur"))
    col2 = "% postes conf." if mode else "Valeur"
    for (kpis, titre, head_fill, x, w) in (
        (syn["kpi_perf"], "Performance", PERF, MX, Inches(6.05)),
        (syn["kpi_qual"], "Qualité", QUAL, MX + Inches(6.3), Inches(6.03)),
    ):
        items = list(kpis.items())
        rows = [[k, f"{v:.0f}%", f"{'≤' if k in LOWER_BETTER else '≥'}{CIBLE.get(k, 100):.0f}"]
                for k, v in items]
        cols = [_color_for(v, CIBLE.get(k, 100), k in LOWER_BETTER, mode) for k, v in items]

        def fmt(r, c, cols=cols):
            if c == 1:
                return {"fill": cols[r], "color": INK if cols[r] == WARN else WHITE, "bold": True}
            return None

        _table(s, x, TOP, w, [f"Indicateurs de {titre.lower()}", col2, "Cible"], rows,
               [3.9, 1.3, 0.85], font_size=11, row_h=Inches(0.345), header_fill=head_fill,
               cell_fmt=fmt, align=[PP_ALIGN.LEFT, PP_ALIGN.CENTER, PP_ALIGN.CENTER])
    # légende des couleurs, sous le tableau Qualité (plus court)
    y_leg = TOP + Inches(0.345) * (len(syn["kpi_qual"]) + 1) + Inches(0.3)
    x_leg = MX + Inches(6.3)
    regle = ("≥ 90 % des postes conformes" if mode else "conforme à la cible",
             "70–90 %" if mode else "dans la tolérance de 5 pts",
             "< 70 %" if mode else "hors tolérance")
    for i, (c, lab) in enumerate(zip((GOOD, WARN, CRIT), regle)):
        yy = y_leg + i * Inches(0.36)
        _box(s, x_leg, yy + Inches(0.04), Inches(0.22), Inches(0.22), fill=c, radius=False)
        _text(s, x_leg + Inches(0.35), yy, Inches(5), Inches(0.3),
              ["Vert — ", "Orange — ", "Rouge — "][i] + lab, size=12, color=INK2)
    return s


def _slide_anomalies(prs, entity, syn, sl):
    s = _blank(prs)
    _title(s, "Anomalies par indicateur",
           f"{entity} — {syn['total_anomalies']} anomalies sur la période")
    entries = sorted([(k, v) for k, v in syn["anomalies"].items() if v > 0], key=lambda x: -x[1])
    if not entries:
        _message(s, MX, TOP, CW, Inches(1.2), "Aucune anomalie détectée — tous les indicateurs sont conformes.")
        return s
    mx = entries[0][1]
    cd = CategoryChartData()
    cd.categories = [sl.get(k, k) for k, _ in entries]
    cd.add_series("Anomalies", [v for _, v in entries])
    ch_w = Inches(8.4)
    gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, MX, TOP, ch_w, BOTTOM - TOP - Inches(0.35), cd)
    ch = gf.chart
    _style_chart(ch, 12)
    ch.has_legend = False
    plot = ch.plots[0]
    plot.gap_width = 45
    ser = plot.series[0]
    ser.invert_if_negative = False
    for i, (_, v) in enumerate(entries):
        pt = ser.points[i]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = _sev_color(v, mx)
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size = Pt(12)
    dl.font.bold = True
    dl.font.color.rgb = INK
    ca = ch.category_axis
    ca.reverse_order = True
    ca.major_tick_mark = XL_TICK_MARK.NONE
    ca.tick_labels.font.size = Pt(12)
    ca.tick_labels.font.color.rgb = INK
    ca.format.line.color.rgb = AXIS
    va = ch.value_axis
    va.visible = False
    va.has_major_gridlines = False
    va.maximum_scale = mx * 1.15
    va.minimum_scale = 0
    # légende des sévérités (texte + pastille : la couleur n'est jamais seule)
    y_leg = BOTTOM - Inches(0.3)
    for i, (c, lab) in enumerate(((CRIT, "Critique (≥ 66 % du max)"), (SERIOUS, "Modéré (33–66 %)"),
                                  (PERF, "Faible (< 33 %)"))):
        xx = MX + Inches(0.2) + i * Inches(2.6)
        _box(s, xx, y_leg + Inches(0.05), Inches(0.18), Inches(0.18), fill=c, radius=False)
        _text(s, xx + Inches(0.28), y_leg, Inches(2.3), Inches(0.3), lab, size=11, color=INK2)
    # tuiles de synthèse à droite
    x_c, w_c, h_c = MX + ch_w + Inches(0.35), CW - ch_w - Inches(0.35), Inches(1.5)
    top_k, top_v = entries[0]
    n_crit = sum(1 for _, v in entries if v / mx >= SEUIL_CRITIQUE)
    cartes = [
        ("Total anomalies", f"{syn['total_anomalies']}",
         [(f"sur {len(entries)} indicateur(s) en anomalie", {})]),
        ("Indicateur le plus touché", sl.get(top_k, top_k),
         [(f"{top_v} anomalies · {top_v / syn['total_anomalies'] * 100:.0f} % du total", {})]),
        ("Indicateurs critiques", f"{n_crit}",
         [("≥ 66 % du volume de l'indicateur le plus touché", {})]),
    ]
    for i, (lab, val, sub) in enumerate(cartes):
        y = TOP + i * (h_c + Inches(0.25))
        _stat_card(s, x_c, y, w_c, h_c, lab, val, sub,
                   value_color=CRIT if i != 1 else INK, value_size=30 if i != 1 else 22)
    return s


def _slide_impact(prs, entity, impact, sl):
    s = _blank(prs)
    _title(s, "Postes de travail impactants — anomalies critiques",
           f"{entity} — nombre d'anomalies et % d'impact de chaque poste sur l'indicateur")
    n = min(3, len(impact))
    gap = Inches(0.35)
    w = int((CW - gap * (n - 1)) / n)          # les panneaux se partagent la largeur
    for i, pan in enumerate(impact[:3]):
        x = MX + i * (w + gap)
        col = CRIT if pan["severite"] == "Critique" else SERIOUS
        _box(s, x, TOP, w, BOTTOM - TOP, fill=CARD)
        _text(s, x + Inches(0.25), TOP + Inches(0.18), w - Inches(0.5), Inches(0.35),
              pan["severite"].upper(), size=11, bold=True, color=col)
        _text(s, x + Inches(0.25), TOP + Inches(0.45), w - Inches(0.5), Inches(0.75),
              [(sl.get(pan["kpi"], pan["kpi"]), {"size": 18, "bold": True, "color": INK}),
               (f"\n{pan['total']} anomalies", {"size": 12, "color": INK2})], size=18)
        rows = [(d["poste"], d["nb"], d["pct"]) for d in pan["postes"]]
        if pan.get("autres_nb"):
            rows.append((f"Autres ({pan['autres_postes']})", pan["autres_nb"], pan["autres_pct"]))
        cd = CategoryChartData()
        cd.categories = [r[0] for r in rows]
        cd.add_series("Anomalies", [r[1] for r in rows])
        gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, x + Inches(0.1), TOP + Inches(1.3),
                                w - Inches(0.2), BOTTOM - TOP - Inches(1.45), cd)
        ch = gf.chart
        _style_chart(ch, 11)
        ch.has_legend = False
        plot = ch.plots[0]
        plot.gap_width = 45
        ser = plot.series[0]
        ser.invert_if_negative = False
        vmax = max(r[1] for r in rows) or 1
        for j, (nm, nb, pct) in enumerate(rows):
            pt = ser.points[j]
            pt.format.fill.solid()
            pt.format.fill.fore_color.rgb = RESTANT if nm.startswith("Autres") else col
            lab = pt.data_label
            lab.position = XL_LABEL_POSITION.OUTSIDE_END
            tf = lab.text_frame
            r1 = tf.paragraphs[0].add_run()
            r1.text = f"{nb} · {pct:.0f}%"
            r1.font.size = Pt(11)
            r1.font.bold = j == 0
            r1.font.color.rgb = INK
        ca = ch.category_axis
        ca.reverse_order = True
        ca.major_tick_mark = XL_TICK_MARK.NONE
        ca.tick_labels.font.size = Pt(11)
        ca.tick_labels.font.color.rgb = INK
        ca.format.line.color.rgb = AXIS
        va = ch.value_axis
        va.visible = False
        va.has_major_gridlines = False
        va.minimum_scale = 0
        va.maximum_scale = vmax * 1.55
    return s


def _slide_evolution(prs, entity, syn, comp, evol):
    s = _blank(prs)
    if not comp:
        _title(s, "Évolution S-1 → S", entity)
        _message(s, MX, TOP, CW, Inches(1.3),
                 "Comparaison S-1 → S indisponible : l'historique ne contient pas encore deux "
                 "extractions pour ce périmètre. Elle apparaîtra dès la prochaine extraction enregistrée.")
        return s
    lp, la = comp["label_prec"], comp["label_act"]
    _title(s, f"Évolution {lp} → {la}", f"{entity} — scores, anomalies et tendance des dernières extractions")
    sp, sq, an = comp["score_perf"], comp["score_qual"], comp["anomalies"]
    n_ano = sum(1 for v in syn["anomalies"].values() if v > 0)
    cards = [
        ("Score Performance", f"{sp[1]:.1f}%" if sp[1] is not None else "—",
         [(f"{lp} : {sp[0]:.1f}%   " if sp[0] is not None else f"{lp} : —   ", {})] + _delta_runs(*sp)),
        ("Score Qualité", f"{sq[1]:.1f}%" if sq[1] is not None else "—",
         [(f"{lp} : {sq[0]:.1f}%   " if sq[0] is not None else f"{lp} : —   ", {})] + _delta_runs(*sq)),
        ("Total anomalies", f"{int(an[1])}",
         [(f"{lp} : {int(an[0])}   ", {})] + _delta_runs(an[0], an[1], lower=True, unite="", dec=0)),
        ("Indicateurs en anomalie", f"{n_ano}",
         [(f"sur {len(syn['kpi_perf']) + len(syn['kpi_qual'])} suivis", {})]),
    ]
    cw, chh, g = Inches(2.85), Inches(1.95), Inches(0.25)
    for i, (lab, val, sub) in enumerate(cards):
        x = MX + (i % 2) * (cw + g)
        y = TOP + (i // 2) * (chh + g)
        _stat_card(s, x, y, cw, chh, lab, val, sub, value_size=30)
    # tendance des scores
    x_ch = MX + 2 * cw + g + Inches(0.45)
    w_ch = SW - MX - x_ch
    _text(s, x_ch, TOP, w_ch, Inches(0.35),
          "Tendance des scores" + (" (conformité des postes)" if syn["mode_division"] else ""),
          size=14, bold=True, color=INK)
    if evol is None or len(evol) < 2:
        _message(s, x_ch, TOP + Inches(0.5), w_ch, Inches(1.2), "Au moins 2 extractions nécessaires.")
        return s
    df = evol.reset_index(drop=True)
    cd = CategoryChartData()
    cd.categories = [f"S{pd.Timestamp(d).isocalendar().week} · {pd.Timestamp(d).strftime('%d/%m')}"
                     for d in df["Date"]]
    perf = [None if pd.isna(v) else float(v) for v in df["Perf"]]
    qual = [None if pd.isna(v) else float(v) for v in df["Qual"]]
    cd.add_series("Score Performance", perf)
    cd.add_series("Score Qualité", qual)
    cd.add_series("Seuil 90 %", [90.0] * len(df))
    gf = s.shapes.add_chart(XL_CHART_TYPE.LINE_MARKERS, x_ch, TOP + Inches(0.4), w_ch,
                            TOP + 2 * chh + g - (TOP + Inches(0.4)), cd)
    ch = gf.chart
    _style_chart(ch, 11)
    ch.has_legend = True
    ch.legend.position = XL_LEGEND_POSITION.BOTTOM
    ch.legend.include_in_layout = False
    ch.legend.font.size = Pt(11)
    for ser, col, dash in zip(ch.plots[0].series, (PERF, QUAL, MUTED), (False, False, True)):
        ser.smooth = False
        ser.format.line.color.rgb = col
        ser.format.line.width = Pt(1 if dash else 2.5)
        if dash:
            ser.format.line.dash_style = MSO_LINE_DASH_STYLE.DASH
            ser.marker.style = XL_MARKER_STYLE.NONE
        else:
            ser.marker.style = XL_MARKER_STYLE.CIRCLE
            ser.marker.size = 8
            ser.marker.format.fill.solid()
            ser.marker.format.fill.fore_color.rgb = WHITE
            ser.marker.format.line.color.rgb = col
            ser.marker.format.line.width = Pt(2)
            last = max(i for i, v in enumerate(perf if col == PERF else qual) if v is not None)
            dl = ser.points[last].data_label
            dl.position = XL_LABEL_POSITION.RIGHT if last == len(df) - 1 else XL_LABEL_POSITION.ABOVE
            r = dl.text_frame.paragraphs[0].add_run()
            r.text = f"{(perf if col == PERF else qual)[last]:.1f}%"
            r.font.size = Pt(12)
            r.font.bold = True
            r.font.color.rgb = INK
    vals = [v for v in perf + qual if v is not None]
    va = ch.value_axis
    va.minimum_scale = max(0, (min(vals) - 6) // 10 * 10)
    va.maximum_scale = 102
    va.major_unit = 10 if va.minimum_scale >= 50 else 20
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = GRID
    va.major_gridlines.format.line.width = Pt(0.75)
    va.tick_labels.number_format = '0'
    va.tick_labels.number_format_is_linked = False
    va.tick_labels.font.size = Pt(10)
    _no_axis_line(va)
    va.major_tick_mark = XL_TICK_MARK.NONE
    ca = ch.category_axis
    ca.tick_labels.font.size = Pt(10.5)
    ca.major_tick_mark = XL_TICK_MARK.NONE
    ca.format.line.color.rgb = AXIS
    return s


def _slide_butterfly(prs, entity, comp, cle, titre, c_prec, c_act, sl, mode_division):
    s = _blank(prs)
    lp, la = comp["label_prec"], comp["label_act"]
    rows = [r for r in comp[cle] if r.get("prec") is not None or r.get("act") is not None]
    mesure = "% de postes conformes" if mode_division else "valeur de l'indicateur"
    _title(s, f"Comparaison {lp} vs {la} — {titre}", f"{entity} — {mesure} par indicateur")
    labels = []
    for r in rows:
        lab = sl.get(r["kpi"], r["kpi"])
        if not mode_division:
            lab += f"  ({'≤' if r['kpi'] in LOWER_BETTER else '≥'}{CIBLE.get(r['kpi'], 100):.0f})"
        labels.append(lab)
    cd = CategoryChartData()
    cd.categories = labels
    cd.add_series(lp, [-(r["prec"] or 0) for r in rows])
    cd.add_series(la, [(r["act"] or 0) for r in rows])
    h = min(BOTTOM - TOP - Inches(0.45), Inches(0.36) * len(rows) + Inches(0.9))
    gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, MX, TOP, CW, h, cd)
    ch = gf.chart
    _style_chart(ch, 12)
    ch.has_legend = True
    ch.legend.position = XL_LEGEND_POSITION.TOP
    ch.legend.include_in_layout = False
    ch.legend.font.size = Pt(12)
    plot = ch.plots[0]
    plot.gap_width = 35
    plot.overlap = 100
    s_prec, s_act = plot.series
    for ser, col in ((s_prec, c_prec), (s_act, c_act)):
        ser.invert_if_negative = False
        ser.format.fill.solid()
        ser.format.fill.fore_color.rgb = col
    for i, r in enumerate(rows):
        if r["prec"] is not None:
            dl = s_prec.points[i].data_label
            dl.position = XL_LABEL_POSITION.OUTSIDE_END
            run = dl.text_frame.paragraphs[0].add_run()
            run.text = f"{r['prec']:.0f}%"
            run.font.size = Pt(11)
            run.font.color.rgb = INK2
        dl = s_act.points[i].data_label
        dl.position = XL_LABEL_POSITION.OUTSIDE_END
        p = dl.text_frame.paragraphs[0]
        run = p.add_run()
        run.text = "—" if r["act"] is None else f"{r['act']:.0f}%"
        run.font.size = Pt(11)
        run.font.bold = True
        run.font.color.rgb = INK
        if r["prec"] is not None and r["act"] is not None:
            d = r["act"] - r["prec"]
            if abs(d) >= 0.05:
                better = (d < 0) if r.get("lower") else (d > 0)
                col = UP_TXT if better else DOWN_TXT
                for txt, font in (("   ▲ " if d > 0 else "   ▼ ", "Arial"), (f"{d:+.1f}", FONT)):
                    rr = p.add_run()
                    rr.text = txt
                    rr.font.size = Pt(11)
                    rr.font.bold = True
                    rr.font.name = font
                    rr.font.color.rgb = col
    ca = ch.category_axis
    ca.reverse_order = True
    ca.tick_label_position = XL_TICK_LABEL_POSITION.LOW
    ca.major_tick_mark = XL_TICK_MARK.NONE
    ca.tick_labels.font.size = Pt(12)
    ca.tick_labels.font.color.rgb = INK
    ca.format.line.color.rgb = AXIS
    va = ch.value_axis
    vmax = max([100.0] + [v for r in rows for v in (r["prec"], r["act"]) if v is not None])
    va.minimum_scale = -vmax * 1.2
    va.maximum_scale = vmax * 1.45
    va.visible = False
    va.has_major_gridlines = False
    note = ("Barre = % des postes conformes à l'indicateur (verdict vert ou orange). " if mode_division
            else "Cible entre parenthèses ; pour les indicateurs « ≤ », une baisse est une amélioration. ")
    _text(s, MX, TOP + h + Inches(0.12), CW, Inches(0.3),
          [(note, {}), ("▲", {"font": "Arial", "color": UP_TXT}), (" amélioration   ", {}),
           ("▼", {"font": "Arial", "color": DOWN_TXT}),
           (f" dégradation.   S-1 = {lp}, S = {la} (dernière extraction).", {})],
          size=11, color=INK2)
    return s


def _set_hole(chart, pct=58):
    el = chart.plots[0]._element
    hs = el.find(qn("c:holeSize"))
    if hs is None:
        hs = el.makeelement(qn("c:holeSize"), {})
        el.append(hs)
    hs.set("val", str(pct))


def _slide_backlog(prs, entity, bc, traitement):
    s = _blank(prs)
    d = bc.get("date") if bc else None
    _title(s, "Backlog caractérisation",
           f"{entity} — OT en attente par code de caractérisation"
           + (f" · extraction du {pd.Timestamp(d).strftime('%d/%m/%Y')}" if d is not None else ""))
    if not bc:
        _message(s, MX, TOP, CW, Inches(1.2), "Aucune donnée de backlog caractérisation pour ce périmètre.")
        return s
    half = int((CW - Inches(0.4)) / 2)
    h_bloc = Inches(3.45)
    for i, (cle, codes, desc, nom) in enumerate((("prep", rd.CRPR_KW, rd.DESC_PREP, "Préparation"),
                                                 ("planif", rd.ATPL_KW, rd.DESC_PLAN, "Planification"))):
        x = MX + i * (half + Inches(0.4))
        counts = bc.get(cle) or {}
        total = sum(int(counts.get(c, 0) or 0) for c in codes)
        _box(s, x, TOP, half, h_bloc, fill=CARD)
        _text(s, x + Inches(0.25), TOP + Inches(0.15), half, Inches(0.35), nom, size=16,
              bold=True, color=INK)
        d_sz = Inches(2.3)
        y_ch = TOP + Inches(0.75)
        if total:
            cd = CategoryChartData()
            cd.categories = list(codes)
            cd.add_series("OT", [int(counts.get(c, 0) or 0) for c in codes])
            gf = s.shapes.add_chart(XL_CHART_TYPE.DOUGHNUT, x + Inches(0.15), y_ch, d_sz, d_sz, cd)
            ch = gf.chart
            _style_chart(ch, 10)
            ch.has_legend = False
            _set_hole(ch, 58)
            ser = ch.plots[0].series[0]
            for j in range(len(codes)):
                pt = ser.points[j]
                pt.format.fill.solid()
                pt.format.fill.fore_color.rgb = CODE_PALETTE[j % len(CODE_PALETTE)]
                pt.format.line.color.rgb = CARD
                pt.format.line.width = Pt(1.5)
            _text(s, x + Inches(0.15), y_ch + d_sz / 2 - Inches(0.36), d_sz, Inches(0.5), f"{total}",
                  size=26, bold=True, color=INK, align=PP_ALIGN.CENTER)
            _text(s, x + Inches(0.15), y_ch + d_sz / 2 + Inches(0.1), d_sz, Inches(0.3), "OT",
                  size=11, color=INK2, align=PP_ALIGN.CENTER)
        else:
            _text(s, x + Inches(0.25), y_ch + Inches(1.0), d_sz, Inches(0.4), "Aucun OT caractérisé.",
                  size=12, color=INK2)
        # clé des codes (tableau natif, pastille colorée en 1re colonne)
        rows = [["", c, desc.get(c, ""), str(int(counts.get(c, 0) or 0)),
                 f"{(int(counts.get(c, 0) or 0) / total * 100) if total else 0:.0f}%"] for c in codes]
        rows.append(["", "Total", "", str(total), "100%" if total else "0%"])

        def fmt(r, c, n=len(codes)):
            if c == 0 and r < n:
                return {"fill": CODE_PALETTE[r % len(CODE_PALETTE)]}
            if r == n:
                return {"bold": True, "fill": WHITE}
            return {"fill": WHITE, "bold": c == 1}

        x_t = x + d_sz + Inches(0.35)
        _table(s, x_t, TOP + Inches(0.6), x + half - Inches(0.2) - x_t,
               ["", "Code", "Signification", "Nb", "%"], rows,
               [0.14, 0.58, 1.72, 0.5, 0.5], font_size=10, row_h=Inches(0.34), header_fill=INK2,
               cell_fmt=fmt,
               align=[PP_ALIGN.LEFT, PP_ALIGN.LEFT, PP_ALIGN.LEFT, PP_ALIGN.RIGHT, PP_ALIGN.RIGHT])
    # synthèse sous les cartes
    tot_p = sum(int((bc.get("prep") or {}).get(c, 0) or 0) for c in rd.CRPR_KW)
    tot_l = sum(int((bc.get("planif") or {}).get(c, 0) or 0) for c in rd.ATPL_KW)
    tot = tot_p + tot_l
    y_s = TOP + h_bloc + Inches(0.3)
    if traitement:
        w3 = int((CW - Inches(0.5)) / 3)
        cartes = [("Backlog caractérisé total", f"{tot} OT", "Préparation + Planification"),
                  ("Préparation", f"{tot_p} OT", f"{(tot_p / tot * 100) if tot else 0:.0f} % du backlog caractérisé"),
                  ("Planification", f"{tot_l} OT", f"{(tot_l / tot * 100) if tot else 0:.0f} % du backlog caractérisé")]
        for i, (lab, val, sub) in enumerate(cartes):
            _stat_card(s, MX + i * (w3 + Inches(0.25)), y_s, w3, BOTTOM - y_s, lab, val,
                       [(sub, {})], value_size=24)
    else:
        _message(s, MX, y_s, CW, Inches(1.0),
                 "Nombre total traité : il compare deux extractions enregistrées du backlog "
                 "caractérisation ; une seule est disponible pour l'instant — il sera calculé "
                 "automatiquement à la prochaine extraction.")
    return s


def _slide_traitement(prs, entity, tr):
    s = _blank(prs)
    dp, da = tr.get("date_prec"), tr.get("date_act")
    per = f"{pd.Timestamp(dp).strftime('%d/%m')} → {pd.Timestamp(da).strftime('%d/%m')}"
    _title(s, "Nombre total traité — backlog caractérisation",
           f"{entity} — OT sortis du backlog entre les extractions du {per}")
    tp, tpp = tr.get("total_traite", 0), tr.get("total_prec", 0)
    w_c = Inches(3.6)
    _box(s, MX, TOP, w_c, BOTTOM - TOP, fill=_rgb("EAF6EA"))
    _text(s, MX + Inches(0.3), TOP + Inches(0.3), w_c - Inches(0.6), Inches(0.35),
          "TOTAL TRAITÉ", size=12, bold=True, color=_rgb("006300"))
    _text(s, MX + Inches(0.3), TOP + Inches(0.7), w_c - Inches(0.6), Inches(1.1), f"{tp}",
          size=66, bold=True, color=INK)
    _text(s, MX + Inches(0.3), TOP + Inches(1.8), w_c - Inches(0.6), Inches(0.9),
          [(f"{(tp / tpp * 100) if tpp else 0:.0f} %", {"bold": True, "size": 20, "color": _rgb("006300")}),
           (f" des {tpp} OT caractérisés au {pd.Timestamp(dp).strftime('%d/%m')}", {"size": 13})],
          size=13, color=INK2)
    for i, (cle, nom) in enumerate((("prep", "Préparation"), ("planif", "Planification"))):
        t, p = tr.get(f"{cle}_total_traite", 0), tr.get(f"{cle}_total_prec", 0)
        y = TOP + Inches(3.1) + i * Inches(1.05)
        _text(s, MX + Inches(0.3), y, w_c - Inches(0.6), Inches(0.9),
              [(nom.upper(), {"size": 11, "bold": True, "color": INK2}),
               (f"\n{t}", {"size": 26, "bold": True, "color": INK}),
               (f"  / {p}  ({(t / p * 100) if p else 0:.0f} %)", {"size": 13, "color": INK2})])
    # un graphique empilé Traité / Restant par catégorie
    x0 = MX + w_c + Inches(0.4)
    w_all = SW - MX - x0
    half = int((w_all - Inches(0.3)) / 2)
    for i, (cle, codes, nom) in enumerate((("prep", rd.CRPR_KW, "Préparation"),
                                           ("planif", rd.ATPL_KW, "Planification"))):
        data = tr.get(cle) or {}
        prec = [tr.get(f"{cle}_total_prec", 0)] + [(data.get(c) or {}).get("precedent", 0) or 0 for c in codes]
        trt = [tr.get(f"{cle}_total_traite", 0)] + [(data.get(c) or {}).get("traite", 0) for c in codes]
        cats = [f"{lab}  {t}/{p} ({(t / p * 100) if p else 0:.0f}%)"
                for lab, t, p in zip(["TOTAL"] + list(codes), trt, prec)]
        cd = CategoryChartData()
        cd.categories = cats
        cd.add_series("Traité", trt)
        cd.add_series("Restant", [max(0, p - t) for p, t in zip(prec, trt)])
        x = x0 + i * (half + Inches(0.3))
        _text(s, x, TOP, half, Inches(0.35), nom, size=16, bold=True, color=INK)
        gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_STACKED, x, TOP + Inches(0.4), half,
                                BOTTOM - TOP - Inches(0.4), cd)
        ch = gf.chart
        _style_chart(ch, 11)
        ch.has_legend = True
        ch.legend.position = XL_LEGEND_POSITION.BOTTOM
        ch.legend.include_in_layout = False
        ch.legend.font.size = Pt(11)
        plot = ch.plots[0]
        plot.gap_width = 45
        plot.overlap = 100
        for ser, col in zip(plot.series, (GOOD, RESTANT)):
            ser.invert_if_negative = False
            ser.format.fill.solid()
            ser.format.fill.fore_color.rgb = col
        ca = ch.category_axis
        ca.reverse_order = True
        ca.major_tick_mark = XL_TICK_MARK.NONE
        ca.tick_labels.font.size = Pt(11)
        ca.tick_labels.font.color.rgb = INK
        ca.format.line.color.rgb = AXIS
        va = ch.value_axis
        va.visible = False
        va.has_major_gridlines = False
        va.minimum_scale = 0
    return s


def _slides_plan(prs, entity, syn, sl, par_slide=8):
    plan = syn["plan_action"]
    mode = syn["mode_division"]
    if not plan:
        s = _blank(prs)
        _title(s, "Plan d'action", entity)
        _message(s, MX, TOP, CW, Inches(1.2), "Aucune anomalie — tous les indicateurs sont conformes.")
        return [s]
    pages = [plan[i:i + par_slide] for i in range(0, len(plan), par_slide)]
    slides = []
    for n, lot in enumerate(pages, start=1):
        s = _blank(prs)
        suite = f" ({n}/{len(pages)})" if len(pages) > 1 else ""
        _title(s, f"Plan d'action{suite}",
               f"{entity} — {len(plan)} indicateur(s) en anomalie, triés par nombre d'anomalies")
        rows = [[p["kpi"], f"{p['actual']:.0f}%", f"{p['target']:.0f}%", str(p["nb_anom"]),
                 p["responsable"], p["action"]] for p in lot]

        def fmt(r, c):
            if c == 3:
                return {"color": CRIT, "bold": True}
            return None

        _table(s, MX, TOP, CW, ["Indicateur", "% conf." if mode else "Valeur", "Cible", "Anom.",
                                "Responsable", "Action corrective"], rows,
               [2.9, 0.95, 0.8, 0.8, 1.9, 5.0], font_size=11.5, row_h=Inches(0.55),
               cell_fmt=fmt, align=[PP_ALIGN.LEFT, PP_ALIGN.CENTER, PP_ALIGN.CENTER,
                                    PP_ALIGN.CENTER, PP_ALIGN.LEFT, PP_ALIGN.LEFT])
        slides.append(s)
    return slides


def _footer(slide, n, total, entity, date_str):
    y = Inches(7.08)
    _text(slide, MX, y, Inches(9), Inches(0.25), f"OCP — Rapport KPI SAP PM · {entity} · {date_str}",
          size=9.5, color=MUTED)
    _text(slide, SW - MX - Inches(1.5), y, Inches(1.5), Inches(0.25), f"{n} / {total}",
          size=9.5, color=MUTED, align=PP_ALIGN.RIGHT)


# ═════════════════════════════════════════════════════════════════════════════
# API publique (signature inchangée)
# ═════════════════════════════════════════════════════════════════════════════
def build_presentation(vp, ckdf, ano_map, pa, qa,
                       pscores, qscores, hist_df=None, fichier_date="",
                       df_full=None, avf_full=None, now_ts=None):
    """
    Construit la présentation et retourne ses bytes (.pptx).
    pa / qa / df_full / avf_full / now_ts sont conservés pour compatibilité
    avec l'appel existant de app.py ; les moyennes et scores sont recalculés
    avec les mêmes règles que les rapports PDF (core/report_data.py).
    """
    sl = _short_labels()
    postes = [p for p in (vp or []) if ckdf is not None and p in ckdf.index]
    entity = _entity_name(postes or vp)
    syn = rd.synthese_perimetre(ckdf, pscores, qscores, ano_map, postes)
    mode = syn["mode_division"]

    def _safe(fn):
        try:
            return fn()
        except Exception:
            return None

    comp = _safe(lambda: rd.comparaison_semaines(hist_df, postes, mode))
    evol = _safe(lambda: rd.evolution_scores(hist_df, postes, mode))
    bc = _safe(lambda: rd.backlog_caract_counts(hist_df, postes))
    tr = _safe(lambda: rd.traitement_backlog(hist_df, postes))
    impact = _safe(lambda: rd.impact_postes_critiques(ano_map, postes)) if mode else None

    prs = Presentation()
    prs.slide_width, prs.slide_height = SW, SH
    slides = [_slide_titre(prs, entity, fichier_date, syn),
              _slide_kpi(prs, entity, syn, sl),
              _slide_anomalies(prs, entity, syn, sl)]
    if impact:
        slides.append(_slide_impact(prs, entity, impact, sl))
    slides.append(_slide_evolution(prs, entity, syn, comp, evol))
    if comp:
        slides.append(_slide_butterfly(prs, entity, comp, "perf", "Performance", PERF_PREC, PERF, sl, mode))
        slides.append(_slide_butterfly(prs, entity, comp, "qual", "Qualité", QUAL_PREC, QUAL, sl, mode))
    slides.append(_slide_backlog(prs, entity, bc, tr))
    if tr:
        slides.append(_slide_traitement(prs, entity, tr))
    slides += _slides_plan(prs, entity, syn, sl)

    total = len(slides)
    for i, s in enumerate(slides[1:], start=2):
        _footer(s, i, total, entity, fichier_date)

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.getvalue()
