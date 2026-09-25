# -*- coding: utf-8 -*-
"""
Génération d'une présentation PowerPoint dynamique selon le filtre
Poste de travail (SF1 → Maroc Chimie, SF2 → FEEDS, mixte → OCP).

Usage dans app.py :
    from core.export_pptx import build_presentation
    pptx_bytes = build_presentation(
        vp, ckdf, ano_map, pa, qa, pscores, qscores, hist_df, fichier_date,
        df_full=df_full, avf_full=av_full, now_ts=now_ts,
    )
    st.download_button("📊 Exporter PowerPoint", pptx_bytes,
                       file_name="presentation_kpis.pptx")

── NOUVEAU (amélioration demandée) ──────────────────────────────────────
- Section « Suivi d'anomalies — semaine précédente vs semaine en cours »,
  répartie sur 2 pages (Performance / Qualité), chacune avec un
  graphique « papillon » (butterfly chart) + un tableau de synthèse
  (S-1, S actuelle, écart, tendance).
- Habillage visuel harmonisé sur toutes les pages : bandeau de titre
  avec liseré, logo discret en coin, pied de page avec numérotation,
  entité et date d'extraction.
- df_full / avf_full / now_ts sont OPTIONNELS : si absents, les 2
  nouvelles pages sont simplement omises (rétrocompatible avec l'appel
  existant dans app.py).
"""
import io
from datetime import datetime

import numpy as np
import pandas as pd
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from core.constants import QK, PK, CIBLE, KPI_RESP_MAP

try:
    from core.calcul_kpi import calc_kpis
except Exception:
    calc_kpis = None
try:
    from core.anomalies import build_ano_map
except Exception:
    build_ano_map = None

# ── Palette OCP ──────────────────────────────────────────────────────────
GREEN_OCP  = RGBColor(0x2C, 0x5F, 0x2D)
MOSS       = RGBColor(0x97, 0xBC, 0x62)
WHITE      = RGBColor(0xFF, 0xFF, 0xFF)
DARK       = RGBColor(0x1E, 0x29, 0x3B)
GREY       = RGBColor(0x64, 0x74, 0x8B)
RED        = RGBColor(0xEF, 0x44, 0x44)
AMBER      = RGBColor(0xF5, 0x9E, 0x0B)
GREEN      = RGBColor(0x10, 0xB9, 0x81)
LIGHT_BG   = RGBColor(0xF5, 0xF5, 0xF5)
BLUE       = RGBColor(0x25, 0x63, 0xEB)

# Palette matplotlib (hex) — mêmes couleurs que la palette pptx ci-dessus,
# pour une cohérence visuelle totale entre tableaux et graphiques.
HEX_NAVY   = "#1E3A5F"
HEX_GREEN_OCP = "#2C5F2D"
HEX_GREEN  = "#10B981"
HEX_RED    = "#EF4444"
HEX_AMBER  = "#F59E0B"
HEX_GREY   = "#94A3B8"
HEX_BLUE   = "#2563EB"

SW, SH = Inches(13.333), Inches(7.5)   # 16:9

# LOWER_BETTER (import paresseux pour éviter les erreurs si absent)
try:
    from core.constants import LOWER_BETTER as _LOWER
except Exception:
    _LOWER = []


# ═══════════════════════════════════════════════════════════════════════════
# Utilitaires génériques
# ═══════════════════════════════════════════════════════════════════════════
def _entity_name(vp):
    """SF1 → Maroc Chimie, SF2 → FEEDS, mixte → OCP (SF1 & SF2)."""
    has_sf1 = any(str(p).startswith("SF1") for p in vp)
    has_sf2 = any(str(p).startswith("SF2") for p in vp)
    if has_sf1 and not has_sf2:
        return "Maroc Chimie"
    if has_sf2 and not has_sf1:
        return "FEEDS"
    return "OCP — Maroc Chimie & FEEDS"


def _score_color(v, s1=70, s2=90):
    if v >= s2: return GREEN
    if v >= s1: return AMBER
    return RED


def _short_kpi(kpi: str) -> str:
    return (str(kpi).replace("OT ", "").replace("Performance ", "Perf ")
            .replace("TAUX_REALISATION_CORRECTIF/PT", "Taux Réalis. Corr.")
            .replace("Backlog ", "Bcklg ")
            .replace("Taux d'approbation des Avis", "Taux Appro. Avis")
            .replace("planification", "planif.")
            .replace("préparation", "prépa.")
            .replace("exécution", "exéc."))


def _blank_slide(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def _find_logo():
    import os
    for logo_path in ("logo.png", "assets/logo.png", "images/logo.png"):
        if os.path.exists(logo_path):
            return logo_path
    return None


def _add_title_bar(slide, text, subtitle=None, icon=""):
    """Bandeau titre haut de slide, avec liseré vert/moss et logo discret."""
    # Liseré fin en haut de page (accent visuel)
    bar = slide.shapes.add_shape(1, 0, 0, SW, Inches(0.08))
    bar.fill.solid(); bar.fill.fore_color.rgb = GREEN_OCP
    bar.line.fill.background(); bar.shadow.inherit = False

    box = slide.shapes.add_textbox(Inches(0.5), Inches(0.28), Inches(10.8), Inches(0.9))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    r = p.add_run(); r.text = f"{icon}  {text}".strip()
    r.font.size = Pt(26); r.font.bold = True; r.font.color.rgb = GREEN_OCP
    r.font.name = "Calibri"
    if subtitle:
        p2 = tf.add_paragraph()
        r2 = p2.add_run(); r2.text = subtitle
        r2.font.size = Pt(13); r2.font.color.rgb = GREY; r2.font.name = "Calibri"

    # Liseré fin sous le titre
    line = slide.shapes.add_shape(1, Inches(0.5), Inches(1.22), Inches(12.3), Pt(1.4))
    line.fill.solid(); line.fill.fore_color.rgb = MOSS
    line.line.fill.background(); line.shadow.inherit = False

    logo = _find_logo()
    if logo:
        try:
            slide.shapes.add_picture(logo, Inches(11.9), Inches(0.28), height=Inches(0.55))
        except Exception:
            pass


def _add_footer(slide, page_num, total_pages, entity, fichier_date):
    """Pied de page harmonisé : entité — date — n° de page."""
    box = slide.shapes.add_textbox(Inches(0.5), Inches(7.14), Inches(12.3), Inches(0.3))
    tf = box.text_frame
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = f"{entity}   •   Données du {fichier_date}"
    r.font.size = Pt(8.5); r.font.color.rgb = GREY; r.font.name = "Calibri"

    box2 = slide.shapes.add_textbox(Inches(12.0), Inches(7.14), Inches(0.83), Inches(0.3))
    tf2 = box2.text_frame
    p2 = tf2.paragraphs[0]; p2.alignment = PP_ALIGN.RIGHT
    r2 = p2.add_run()
    r2.text = f"{page_num} / {total_pages}"
    r2.font.size = Pt(8.5); r2.font.color.rgb = GREY; r2.font.name = "Calibri"


def _carte_stat(slide, x, y, w, label, valeur, couleur, sous=""):
    """Petite carte de synthèse (statistique) réutilisable dans les slides."""
    box = slide.shapes.add_shape(1, x, y, w, Inches(1.05))
    box.fill.solid(); box.fill.fore_color.rgb = RGBColor(0xF8, 0xFA, 0xFC)
    box.line.color.rgb = couleur; box.line.width = Pt(1)
    box.shadow.inherit = False

    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.08); tf.margin_right = Inches(0.08)
    tf.margin_top = Inches(0.06); tf.margin_bottom = Inches(0.02)
    p0 = tf.paragraphs[0]; p0.alignment = PP_ALIGN.CENTER
    r0 = p0.add_run(); r0.text = label.upper()
    r0.font.size = Pt(9); r0.font.bold = True; r0.font.color.rgb = GREY; r0.font.name = "Calibri"

    p1 = tf.add_paragraph(); p1.alignment = PP_ALIGN.CENTER
    r1 = p1.add_run(); r1.text = str(valeur)
    r1.font.size = Pt(22); r1.font.bold = True; r1.font.color.rgb = couleur; r1.font.name = "Calibri"

    if sous:
        p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
        r2 = p2.add_run(); r2.text = sous
        r2.font.size = Pt(9); r2.font.color.rgb = GREY; r2.font.name = "Calibri"


# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 1 — Titre
# ═══════════════════════════════════════════════════════════════════════════
def _slide_title(prs, entity, fichier_date, vp=None):
    slide = _blank_slide(prs)
    bg = slide.shapes.add_shape(1, 0, 0, SW, SH)
    bg.fill.solid(); bg.fill.fore_color.rgb = GREEN_OCP
    bg.line.fill.background()
    bg.shadow.inherit = False
    slide.shapes._spTree.remove(bg._element)
    slide.shapes._spTree.insert(2, bg._element)

    band = slide.shapes.add_shape(1, 0, Inches(6.6), SW, Inches(0.9))
    band.fill.solid(); band.fill.fore_color.rgb = MOSS
    band.line.fill.background(); band.shadow.inherit = False

    logo = _find_logo()
    if logo:
        try:
            slide.shapes.add_picture(logo, Inches(0.5), Inches(0.4), height=Inches(1.1))
        except Exception:
            pass

    box = slide.shapes.add_textbox(Inches(1.0), Inches(2.1), Inches(11.3), Inches(2.0))
    tf = box.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = "Présentation des KPIs"
    r.font.size = Pt(48); r.font.bold = True; r.font.color.rgb = WHITE; r.font.name = "Calibri"
    p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
    r2 = p2.add_run(); r2.text = "Maintenance SAP PM"
    r2.font.size = Pt(30); r2.font.color.rgb = RGBColor(0xE7, 0xE8, 0xD1); r2.font.name = "Calibri"

    box2 = slide.shapes.add_textbox(Inches(1.0), Inches(4.25), Inches(11.3), Inches(0.9))
    tf2 = box2.text_frame; p3 = tf2.paragraphs[0]; p3.alignment = PP_ALIGN.CENTER
    r3 = p3.add_run(); r3.text = entity
    r3.font.size = Pt(32); r3.font.bold = True; r3.font.color.rgb = WHITE; r3.font.name = "Calibri"

    if vp:
        postes_txt = ", ".join(str(p) for p in vp)
        if len(postes_txt) > 130:
            postes_txt = postes_txt[:127] + "…"
        box_p = slide.shapes.add_textbox(Inches(1.0), Inches(5.15), Inches(11.3), Inches(1.2))
        tfp = box_p.text_frame; tfp.word_wrap = True
        pp = tfp.paragraphs[0]; pp.alignment = PP_ALIGN.CENTER
        lbl = pp.add_run(); lbl.text = f"Postes de travail ({len(vp)}) : "
        lbl.font.size = Pt(13); lbl.font.bold = True
        lbl.font.color.rgb = RGBColor(0xE7, 0xE8, 0xD1); lbl.font.name = "Calibri"
        val = pp.add_run(); val.text = postes_txt
        val.font.size = Pt(13); val.font.color.rgb = WHITE; val.font.name = "Calibri"

    box3 = slide.shapes.add_textbox(Inches(1.0), Inches(6.75), Inches(11.3), Inches(0.55))
    tf3 = box3.text_frame; p4 = tf3.paragraphs[0]; p4.alignment = PP_ALIGN.CENTER
    r4 = p4.add_run(); r4.text = f"Données du {fichier_date}   •   Généré le {datetime.now().strftime('%d/%m/%Y')}"
    r4.font.size = Pt(13); r4.font.color.rgb = DARK; r4.font.name = "Calibri"


# ═══════════════════════════════════════════════════════════════════════════
# Table helper
# ═══════════════════════════════════════════════════════════════════════════
def _add_table(slide, headers, rows, left, top, width, height,
               col_widths=None, header_fill=GREEN_OCP, font_size=10,
               color_col=None, cible_map=None, lower_set=None):
    nrows, ncols = len(rows) + 1, len(headers)
    tbl_shape = slide.shapes.add_table(nrows, ncols, left, top, width, height)
    tbl = tbl_shape.table

    if col_widths:
        for i, w in enumerate(col_widths):
            tbl.columns[i].width = w

    for j, h in enumerate(headers):
        c = tbl.cell(0, j)
        c.fill.solid(); c.fill.fore_color.rgb = header_fill
        c.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf = c.text_frame; tf.word_wrap = True
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = str(h)
        r.font.size = Pt(font_size); r.font.bold = True; r.font.color.rgb = WHITE
        r.font.name = "Calibri"

    for i, row in enumerate(rows, start=1):
        for j, val in enumerate(row):
            c = tbl.cell(i, j)
            c.fill.solid()
            c.fill.fore_color.rgb = WHITE if i % 2 else LIGHT_BG
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = c.text_frame; tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER
            r = p.add_run(); r.text = str(val)
            r.font.size = Pt(font_size); r.font.name = "Calibri"; r.font.color.rgb = DARK
            if color_col is not None and j == color_col:
                try:
                    fv = float(str(val).replace('%', '').replace(',', '.'))
                    kpi_name = str(row[0])
                    tgt = (cible_map or {}).get(kpi_name, 100)
                    lower = kpi_name in (lower_set or set())
                    ok = (fv <= tgt) if lower else (fv >= tgt)
                    r.font.color.rgb = GREEN if ok else RED
                    r.font.bold = True
                except (ValueError, TypeError):
                    pass
    return tbl_shape


# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 2/3 — Scores globaux + Indicateurs Performance / Qualité (barres)
# ═══════════════════════════════════════════════════════════════════════════
def _bar_row(slide, label, value, y, x0=Inches(0.8), maxw=8.5,
             s1=70, s2=90, label_w=3.2):
    lb = slide.shapes.add_textbox(x0, y, Inches(label_w), Inches(0.32))
    tf = lb.text_frame; tf.margin_left = 0; tf.margin_top = 0
    p = tf.paragraphs[0]; r = p.add_run(); r.text = str(label)
    r.font.size = Pt(11); r.font.color.rgb = DARK; r.font.name = "Calibri"
    p.alignment = PP_ALIGN.RIGHT

    bar_x = x0 + Inches(label_w + 0.15)
    track = slide.shapes.add_shape(1, bar_x, y + Emu(20000),
                                    Inches(maxw), Inches(0.20))
    track.fill.solid(); track.fill.fore_color.rgb = RGBColor(0xE5, 0xE7, 0xEB)
    track.line.fill.background(); track.shadow.inherit = False

    w = max(0.02, maxw * min(value, 100) / 100.0)
    bar = slide.shapes.add_shape(1, bar_x, y + Emu(20000),
                                  Inches(w), Inches(0.20))
    bar.fill.solid(); bar.fill.fore_color.rgb = _score_color(value, s1, s2)
    bar.line.fill.background(); bar.shadow.inherit = False

    vb = slide.shapes.add_textbox(bar_x + Inches(maxw + 0.1), y, Inches(0.9), Inches(0.32))
    tf2 = vb.text_frame; tf2.margin_left = 0; tf2.margin_top = 0
    p2 = tf2.paragraphs[0]; r2 = p2.add_run(); r2.text = f"{value:.0f}%"
    r2.font.size = Pt(11); r2.font.bold = True; r2.font.color.rgb = DARK; r2.font.name = "Calibri"


def _slide_scores_indicateurs(prs, entity, vp, scores, moyennes, kpi_list, kind):
    slide = _blank_slide(prs)
    icon = "📈" if kind == "Performance" else "✅"
    _add_title_bar(slide, f"Scores globaux par poste — {kind}", icon=icon,
                   subtitle=f"{entity} — score par poste et taux moyens par indicateur")

    postes = [p for p in vp if p in scores][:9]
    y = Inches(1.5)
    for poste in postes:
        _bar_row(slide, poste, scores.get(poste, 0), y,
                 x0=Inches(0.4), maxw=4.2, label_w=1.9)
        y += Inches(0.55)

    hdr = slide.shapes.add_textbox(Inches(7.2), Inches(1.35), Inches(5.5), Inches(0.4))
    p = hdr.text_frame.paragraphs[0]; r = p.add_run()
    r.text = f"Taux moyens — {kind}"
    r.font.size = Pt(15); r.font.bold = True; r.font.color.rgb = GREEN_OCP; r.font.name = "Calibri"

    y2 = Inches(1.9)
    for kpi in kpi_list[:9]:
        if kpi in moyennes and pd.notna(moyennes[kpi]):
            short = _short_kpi(kpi)[:24]
            _bar_row(slide, short, moyennes[kpi], y2, x0=Inches(6.7), maxw=3.2, label_w=2.6)
            y2 += Inches(0.52)
    return slide


# ═══════════════════════════════════════════════════════════════════════════
# SLIDES 4/5 — Détail indicateurs + anomalies (Perf / Qualité)
# ═══════════════════════════════════════════════════════════════════════════
def _slide_detail(prs, entity, vp, ckdf, ano_map, kpi_list, kind):
    slide = _blank_slide(prs)
    icon = "📈" if kind == "Performance" else "✅"
    _add_title_bar(slide, f"Détail des indicateurs de {kind}", icon=icon,
                   subtitle=f"{entity} — valeurs et nombre d'anomalies par KPI")

    postes = [p for p in vp if p in ckdf.index][:8]

    headers = ["Indicateur", "Valeur moy.", "Cible", "Anomalies"]
    rows = []
    for kpi in kpi_list:
        vals = [float(ckdf.loc[p, kpi]) for p in postes if kpi in ckdf.columns and p in ckdf.index]
        vmoy = sum(vals) / len(vals) if vals else 0
        tgt = CIBLE.get(kpi, 100)
        nb = 0
        if kpi in ano_map:
            s = ano_map[kpi]
            nb = int(sum(int(s.get(p, 0)) for p in postes))
        rows.append([_short_kpi(kpi)[:38], f"{vmoy:.1f}%", f"{tgt}%", str(nb)])

    _add_table(
        slide, headers, rows,
        Inches(0.5), Inches(1.5), Inches(12.3), Inches(5.3),
        col_widths=[Inches(6.5), Inches(2.0), Inches(1.8), Inches(2.0)],
        header_fill=GREEN_OCP, font_size=11,
        color_col=1, cible_map=CIBLE,
        lower_set=set(k for k in kpi_list if k in _LOWER),
    )
    return slide


# ═══════════════════════════════════════════════════════════════════════════
# NOUVEAU — Suivi d'anomalies : semaine précédente vs semaine en cours
# ═══════════════════════════════════════════════════════════════════════════
def _bounds_semaine(annee, semaine):
    lundi = pd.Timestamp.fromisocalendar(int(annee), int(semaine), 1)
    dimanche = lundi + pd.Timedelta(days=6, hours=23, minutes=59, seconds=59)
    return lundi, dimanche


def _semaine_precedente(annee, semaine):
    lundi, _ = _bounds_semaine(annee, semaine)
    lundi_prec = lundi - pd.Timedelta(days=7)
    iso = lundi_prec.isocalendar()
    return int(iso.year), int(iso.week)


def _ano_totaux_semaine(df_full, avf_full, now_ts, vp, annee, semaine, kpi_list):
    """Recalcule (via build_ano_map, la source unique de vérité des
    anomalies) le total d'anomalies pour une semaine ISO donnée, restreint
    aux postes vp et à une liste de KPI (QK ou PK)."""
    if calc_kpis is None or build_ano_map is None or df_full is None or df_full.empty:
        return 0, {}
    lundi, dimanche = _bounds_semaine(annee, semaine)

    df_sem = df_full[df_full["Date de début planifiée"].between(lundi, dimanche)].copy()
    avf_sem = avf_full.copy() if avf_full is not None else pd.DataFrame()
    if not avf_sem.empty and "Créé le" in avf_sem.columns:
        avf_sem = avf_sem[avf_sem["Créé le"].between(lundi, dimanche)]

    try:
        res = calc_kpis(df_sem, avf_sem, now_ts, list(vp))
        dfp_sem, avf_sem2 = res.get("dfp", df_sem), res.get("avf", avf_sem)
        ano = build_ano_map(dfp_sem, avf_sem2, now_ts)
    except Exception:
        return 0, {}

    detail = {}
    total = 0
    for kpi in kpi_list:
        if kpi not in ano:
            detail[kpi] = 0
            continue
        s = ano[kpi]
        nb = int(sum(int(s.get(p, 0)) for p in vp))
        detail[kpi] = nb
        total += nb
    return total, detail


def _butterfly_image(labels, valeurs_prec, valeurs_act, titre,
                      couleur_prec=HEX_GREY, figsize=(9.6, 4.6)):
    """Graphique papillon (butterfly) : semaine précédente à gauche (barres
    négatives, gris), semaine en cours à droite (barres positives, verte
    si amélioration / rouge si dégradation / ambre si stable)."""
    if not labels:
        return None
    fig, ax = plt.subplots(figsize=figsize, dpi=170)
    y_pos = np.arange(len(labels))

    ax.barh(y_pos, [-v for v in valeurs_prec], color=couleur_prec, height=0.62,
            edgecolor="white", linewidth=0.8, label="Semaine précédente")

    couleurs_act = []
    for vp_, va in zip(valeurs_prec, valeurs_act):
        if va > vp_:
            couleurs_act.append(HEX_RED)
        elif va < vp_:
            couleurs_act.append(HEX_GREEN)
        else:
            couleurs_act.append(HEX_AMBER)
    ax.barh(y_pos, valeurs_act, color=couleurs_act, height=0.62,
            edgecolor="white", linewidth=0.8, label="Semaine en cours")

    maxi = max(max(valeurs_prec, default=0), max(valeurs_act, default=0), 1)
    for i, (vp_, va) in enumerate(zip(valeurs_prec, valeurs_act)):
        if vp_ > 0:
            ax.text(-vp_ - maxi * 0.02, i, f"{int(vp_)}", va="center", ha="right",
                    fontsize=8.5, color=HEX_NAVY, fontweight="bold")
        if va > 0:
            ax.text(va + maxi * 0.02, i, f"{int(va)}", va="center", ha="left",
                    fontsize=8.5, color=HEX_NAVY, fontweight="bold")

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=9.5)
    ax.axvline(0, color="#CBD5E1", linewidth=1)
    ax.set_xlim(-maxi * 1.25, maxi * 1.25)
    xt = ax.get_xticks()
    ax.set_xticks(xt)
    ax.set_xticklabels([str(int(abs(t))) for t in xt], fontsize=8.5)
    ax.set_title(titre, fontsize=13, fontweight="bold", color=HEX_NAVY, pad=12)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", color="#F1F5F9", linewidth=1)
    ax.set_axisbelow(True)

    from matplotlib.patches import Patch
    handles = [Patch(color=couleur_prec, label="Semaine précédente"),
               Patch(color=HEX_GREEN, label="Amélioration"),
               Patch(color=HEX_RED, label="Dégradation"),
               Patch(color=HEX_AMBER, label="Stable")]
    ax.legend(handles=handles, loc="lower right", fontsize=8, frameon=False,
              ncol=2, bbox_to_anchor=(1.0, -0.22))

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf


def _slide_suivi_semaine(prs, entity, vp, df_full, avf_full, now_ts, kpi_list, kind, accent):
    """Une page (Performance OU Qualité) : suivi des anomalies de la
    semaine précédente comparées à la semaine en cours, avec graphique
    papillon + tableau de synthèse par indicateur."""
    if now_ts is None:
        return None
    iso = pd.Timestamp(now_ts).isocalendar()
    annee_act, sem_act = int(iso.year), int(iso.week)
    annee_prec, sem_prec = _semaine_precedente(annee_act, sem_act)

    tot_act, det_act = _ano_totaux_semaine(df_full, avf_full, now_ts, vp, annee_act, sem_act, kpi_list)
    tot_prec, det_prec = _ano_totaux_semaine(df_full, avf_full, now_ts, vp, annee_prec, sem_prec, kpi_list)

    slide = _blank_slide(prs)
    icon = "📈" if kind == "Performance" else "✅"
    _add_title_bar(
        slide, f"Suivi d'anomalies — {kind}", icon=icon,
        subtitle=f"{entity} — semaine S{sem_prec:02d}/{annee_prec} (précédente) vs "
                 f"S{sem_act:02d}/{annee_act} (en cours)",
    )

    diff = tot_act - tot_prec
    traite = max(0, tot_prec - tot_act) if tot_prec else 0
    pct_traite = (traite / tot_prec * 100) if tot_prec else 0
    tendance_couleur = GREEN if diff < 0 else (RED if diff > 0 else AMBER)

    cx = Inches(0.5)
    for label, val, couleur, sous in [
        (f"Anomalies S{sem_prec:02d}", str(tot_prec), GREY, "semaine précédente"),
        (f"Anomalies S{sem_act:02d}", str(tot_act), accent, "semaine en cours"),
        ("Écart", f"{diff:+d}", tendance_couleur, "vs semaine précédente"),
        ("Traitées", f"{traite}", GREEN, f"{pct_traite:.0f}% résorbées"),
    ]:
        _carte_stat(slide, cx, Inches(1.42), Inches(2.95), label, val, couleur, sous)
        cx += Inches(3.08)

    labels, v_prec, v_act = [], [], []
    for kpi in kpi_list:
        vp_ = det_prec.get(kpi, 0)
        va = det_act.get(kpi, 0)
        if vp_ == 0 and va == 0:
            continue
        labels.append(_short_kpi(kpi)[:26])
        v_prec.append(vp_)
        v_act.append(va)

    img = _butterfly_image(
        labels, v_prec, v_act,
        f"Anomalies par indicateur — {kind} (◀ S{sem_prec:02d}  |  S{sem_act:02d} ▶)",
    )
    if img:
        slide.shapes.add_picture(img, Inches(0.5), Inches(2.7), width=Inches(7.9))
    else:
        box = slide.shapes.add_textbox(Inches(0.5), Inches(3.2), Inches(7.9), Inches(1))
        p = box.text_frame.paragraphs[0]; r = p.add_run()
        r.text = "✅ Aucune anomalie sur ces 2 semaines — rien à afficher."
        r.font.size = Pt(16); r.font.color.rgb = GREEN; r.font.name = "Calibri"

    headers = ["Indicateur", f"S{sem_prec:02d}", f"S{sem_act:02d}", "Écart"]
    rows = []
    for kpi in kpi_list:
        vp_ = det_prec.get(kpi, 0)
        va = det_act.get(kpi, 0)
        if vp_ == 0 and va == 0:
            continue
        rows.append([_short_kpi(kpi)[:28], str(vp_), str(va), f"{va - vp_:+d}"])
    rows.sort(key=lambda r: -abs(int(r[3])))
    rows = rows[:12]

    if rows:
        tbl = _add_table(
            slide, headers, rows,
            Inches(8.65), Inches(2.7), Inches(4.2), Inches(4.1),
            col_widths=[Inches(2.0), Inches(0.75), Inches(0.75), Inches(0.7)],
            header_fill=accent, font_size=9.5,
        )
        # Colorer la colonne Écart : rouge si dégradation, vert si amélioration
        for i, row in enumerate(rows, start=1):
            try:
                d = int(row[3])
                cell = tbl.table.cell(i, 3)
                r = cell.text_frame.paragraphs[0].runs[0]
                r.font.color.rgb = RED if d > 0 else (GREEN if d < 0 else GREY)
                r.font.bold = True
            except Exception:
                pass
    return slide


# ═══════════════════════════════════════════════════════════════════════════
# SLIDE — Sparklines (évolution par poste, version texte tendance)
# ═══════════════════════════════════════════════════════════════════════════
def _slide_sparklines(prs, entity, vp, hist_df, pscores, qscores):
    slide = _blank_slide(prs)
    _add_title_bar(slide, "Suivi Sparklines par Poste de Travail", icon="📊",
                   subtitle=f"{entity} — évolution récente des scores")

    postes = [p for p in vp if p in pscores or p in qscores][:10]
    headers = ["Poste de travail", "Performance", "Qualité", "Tendance"]
    rows = []
    for poste in postes:
        ps = pscores.get(poste, 0)
        qs = qscores.get(poste, 0)
        trend = "→"
        if hist_df is not None and not hist_df.empty:
            try:
                h = hist_df[hist_df["Poste"] == poste].sort_values("Date")
                if len(h) >= 2:
                    d = h.iloc[-1]["Value"] - h.iloc[-2]["Value"]
                    trend = "↑" if d > 1 else ("↓" if d < -1 else "→")
            except Exception:
                pass
        rows.append([poste, f"{ps:.0f}%", f"{qs:.0f}%", trend])

    _add_table(
        slide, headers, rows,
        Inches(1.2), Inches(1.6), Inches(10.9), Inches(5.0),
        col_widths=[Inches(4.5), Inches(2.3), Inches(2.3), Inches(1.8)],
        header_fill=GREEN_OCP, font_size=12,
    )
    return slide


# ═══════════════════════════════════════════════════════════════════════════
# SLIDE — Plan d'action
# ═══════════════════════════════════════════════════════════════════════════
def _slide_plan_action(prs, entity, vp, ckdf, ano_map):
    slide = _blank_slide(prs)
    _add_title_bar(slide, "Plan d'action", icon="🎯",
                   subtitle=f"{entity} — KPIs nécessitant une action (anomalies > 0)")

    postes = [p for p in vp if p in ckdf.index]
    rows = []
    for poste in postes:
        for kpi in list(QK) + list(PK):
            if kpi not in ano_map:
                continue
            nb = int(ano_map[kpi].get(poste, 0))
            if nb > 0:
                resp = KPI_RESP_MAP.get(kpi, "Non assigné")
                rows.append([poste, _short_kpi(kpi)[:30], str(nb), resp[:20]])
    rows.sort(key=lambda r: -int(r[2]))
    rows = rows[:12]

    if not rows:
        box = slide.shapes.add_textbox(Inches(1), Inches(3), Inches(11), Inches(1))
        p = box.text_frame.paragraphs[0]; r = p.add_run()
        r.text = "🎉 Aucune action requise — tous les indicateurs sont conformes."
        r.font.size = Pt(20); r.font.color.rgb = GREEN; r.font.name = "Calibri"
        return slide

    headers = ["Poste", "Indicateur", "Anomalies", "Responsable"]
    _add_table(
        slide, headers, rows,
        Inches(0.6), Inches(1.55), Inches(12.1), Inches(5.4),
        col_widths=[Inches(2.4), Inches(5.0), Inches(1.9), Inches(2.8)],
        header_fill=RED, font_size=11,
    )
    return slide


# ═══════════════════════════════════════════════════════════════════════════
# API publique
# ═══════════════════════════════════════════════════════════════════════════
def build_presentation(vp, ckdf, ano_map, pa, qa,
                        pscores, qscores, hist_df=None, fichier_date="",
                        df_full=None, avf_full=None, now_ts=None):
    """
    df_full / avf_full / now_ts (optionnels) : données BRUTES non filtrées
    par la période (mêmes objets que dans app.py — df_full/av_full/now_ts
    issus de render_sidebar), nécessaires pour recalculer en direct les
    anomalies de la semaine précédente et de la semaine en cours. Si
    absents, les 2 pages « Suivi d'anomalies » sont simplement omises.
    """
    prs = Presentation()
    prs.slide_width = SW
    prs.slide_height = SH

    entity = _entity_name(vp)

    slides = []
    slides.append(_slide_title(prs, entity, fichier_date, vp))
    slides.append(_slide_scores_indicateurs(prs, entity, vp, pscores, pa, QK, "Performance"))
    slides.append(_slide_scores_indicateurs(prs, entity, vp, qscores, qa, PK, "Qualité"))
    slides.append(_slide_detail(prs, entity, vp, ckdf, ano_map, QK, "Performance"))
    slides.append(_slide_detail(prs, entity, vp, ckdf, ano_map, PK, "Qualité"))

    if df_full is not None and avf_full is not None and now_ts is not None:
        s = _slide_suivi_semaine(prs, entity, vp, df_full, avf_full, now_ts, QK, "Performance", GREEN_OCP)
        if s is not None:
            slides.append(s)
        s = _slide_suivi_semaine(prs, entity, vp, df_full, avf_full, now_ts, PK, "Qualité", BLUE)
        if s is not None:
            slides.append(s)

    slides.append(_slide_sparklines(prs, entity, vp, hist_df, pscores, qscores))
    slides.append(_slide_plan_action(prs, entity, vp, ckdf, ano_map))

    # Pied de page harmonisé sur toutes les slides sauf la page de titre
    total = len(slides)
    for i, sl in enumerate(slides[1:], start=2):
        _add_footer(sl, i, total, entity, fichier_date)

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.getvalue()
