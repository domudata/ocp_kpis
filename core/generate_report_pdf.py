# -*- coding: utf-8 -*-
"""
Génère un rapport KPI (1 page) par poste de travail, DIRECTEMENT en PDF
via reportlab (Python pur) — AUCUNE dépendance à LibreOffice/soffice.

CONTEXTE : la génération PDF reposait initialement sur une conversion
PPTX -> PDF via LibreOffice (subprocess "soffice --headless
--convert-to pdf"). Ce mécanisme s'est révélé fragile sur Streamlit
Cloud : la suppression de packages.txt (nécessaire pour résoudre un
échec de déploiement lié à un dépôt Debian expiré côté plateforme) a
entraîné la disparition de LibreOffice, et donc l'échec systématique
de la génération PDF (0/29 postes), sans affecter la génération Excel
(pure Python). Cette version reconstruit le même contenu directement
en PDF, éliminant cette dépendance système fragile.
"""
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.enums import TA_LEFT, TA_CENTER

from core.constants import LOWER_BETTER

NAVY = colors.HexColor("#1E3A5F")
GREEN = colors.HexColor("#10B981")
ORANGE = colors.HexColor("#F59E0B")
RED = colors.HexColor("#EF4444")
BLUE = colors.HexColor("#2563EB")
GREY = colors.HexColor("#64748B")
LGREY = colors.HexColor("#F1F5F9")
WHITE = colors.white
DARK = colors.HexColor("#1E293B")


def _color_for(val, cible, lower, mode_conformite=False):
    """Couleur d'une cellule de valeur KPI.

    mode_conformite=True : la valeur reçue est un TAUX DE CONFORMITÉ
    (% de postes conformes sur ce KPI) et non la valeur brute du KPI.
    Pour ce taux, plus c'est haut mieux c'est — quelle que soit la
    nature du KPI. Sans ce mode, un taux de conformité de 96% sur un
    indicateur « plus bas = mieux » serait affiché en rouge, car
    interprété comme « 96% des OT sont en retard ».
    """
    val = round(val)
    if mode_conformite:
        if val >= 90:
            return GREEN
        if val >= 70:
            return ORANGE
        return RED
    if lower:
        if val <= cible:
            return GREEN
        if val <= cible * 1.5:
            return ORANGE
        return RED
    else:
        if val >= cible:
            return GREEN
        if val >= cible * 0.9:
            return ORANGE
        return RED


def _kpi_table_flowable(title, kpi_dict, cibles, accent_hex, styles, mode_conformite=False):
    accent = colors.HexColor(accent_hex)
    rows = [["Indicateur", "Val.", "Cible"]]
    cell_colors = []
    for k, v in kpi_dict.items():
        cible = cibles[k]
        lower = k in LOWER_BETTER
        c = _color_for(v, cible, lower, mode_conformite)
        rows.append([k, f"{v:.0f}%", f"{'≤' if lower else '≥'}{cible:.0f}"])
        cell_colors.append(c)

    t = Table(rows, colWidths=[6.2 * cm, 1.6 * cm, 1.6 * cm])
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), accent),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for i, c in enumerate(cell_colors, start=1):
        style.append(("BACKGROUND", (1, i), (1, i), c))
        style.append(("TEXTCOLOR", (1, i), (1, i), WHITE))
        style.append(("FONTNAME", (1, i), (1, i), "Helvetica-Bold"))
    t.setStyle(TableStyle(style))
    return t


def _graphique_anomalies_image(anomalies, short_labels):
    ano_entries = sorted([(k, v) for k, v in anomalies.items() if v > 0], key=lambda x: x[1])
    if not ano_entries:
        return None
    labels = [short_labels.get(k, k) for k, _ in ano_entries]
    valeurs = [v for _, v in ano_entries]

    fig, ax = plt.subplots(figsize=(4.2, 3.6), dpi=150)
    bars = ax.barh(labels, valeurs, color="#2563EB", height=0.6)
    for bar, v in zip(bars, valeurs):
        ax.text(bar.get_width() + max(valeurs) * 0.02, bar.get_y() + bar.get_height() / 2,
                str(v), va="center", fontsize=7, color="#1E293B")
    ax.set_xticks([])
    ax.tick_params(axis="y", labelsize=7)
    for spine in ["top", "right", "bottom"]:
        ax.spines[spine].set_visible(False)
    plt.tight_layout(pad=0.3)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def build_poste_report_pdf(
    poste, pscore, qscore, kpi_perf, kpi_qual, cibles,
    anomalies, total_anomalies, plan_action, date_str,
    short_labels=None, mode_conformite=False,
):
    """Construit et retourne les bytes PDF (1 page, paysage) pour un poste — équivalent direct de build_poste_report_pptx, sans LibreOffice."""
    short_labels = short_labels or {}
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitrePoste", fontSize=20, textColor=WHITE, fontName="Helvetica-Bold", leading=24))
    styles.add(ParagraphStyle(name="SousTitre", fontSize=9, textColor=colors.HexColor("#CBD5E1")))
    styles.add(ParagraphStyle(name="SectionTitre", fontSize=10.5, textColor=NAVY, fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=4))
    styles.add(ParagraphStyle(name="Corps", fontSize=8.5, fontName="Helvetica", leading=11))
    styles.add(ParagraphStyle(name="CorpsBlanc", fontSize=8.5, fontName="Helvetica", leading=11, textColor=WHITE))

    story = []

    # ── En-tête (bandeau bleu marine avec 3 badges de score) ──
    p_color = GREEN if pscore >= 90 else (ORANGE if pscore >= 80 else RED)
    q_color = GREEN if qscore >= 90 else (ORANGE if qscore >= 80 else RED)

    entete_gauche = [
        Paragraph(poste, styles["TitrePoste"]),
        Spacer(1, 8),
        Paragraph(f"Rapport KPI Performance & Qualité — SAP PM OCP • {date_str}", styles["SousTitre"]),
    ]
    badge_style = ParagraphStyle(name="Badge", fontSize=8, fontName="Helvetica-Bold", textColor=GREY, alignment=TA_CENTER)

    def badge_cell(label, valeur, couleur):
        vs = ParagraphStyle(name="BadgeVal", fontSize=16, fontName="Helvetica-Bold", textColor=couleur, alignment=TA_CENTER)
        return [Paragraph(label, badge_style), Paragraph(valeur, vs)]

    badges_table = Table([[
        badge_cell("SCORE PERFORMANCE", f"{pscore:.1f}%", p_color),
        badge_cell("SCORE QUALITÉ", f"{qscore:.1f}%", q_color),
        badge_cell("ANOMALIES", str(total_anomalies), RED),
    ]], colWidths=[4 * cm, 4 * cm, 3 * cm])
    badges_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), WHITE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (0, 0), 0.5, colors.HexColor("#E2E8F0")), ("BOX", (1, 0), (1, 0), 0.5, colors.HexColor("#E2E8F0")),
        ("BOX", (2, 0), (2, 0), 0.5, colors.HexColor("#E2E8F0")),
    ]))

    entete_table = Table([[entete_gauche, badges_table]], colWidths=[16 * cm, 11 * cm])
    entete_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 14), ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(entete_table)
    story.append(Spacer(1, 10))

    # ── Tableaux KPI + graphique anomalies (3 colonnes) ──
    perf_flow = [Paragraph("INDICATEURS DE PERFORMANCE", ParagraphStyle(name="t1", fontSize=9.5, fontName="Helvetica-Bold", textColor=colors.HexColor("#059669"))),
                 Spacer(1, 4), _kpi_table_flowable("Performance", kpi_perf, cibles, "#059669", styles, mode_conformite)]
    qual_flow = [Paragraph("INDICATEURS DE QUALITÉ", ParagraphStyle(name="t2", fontSize=9.5, fontName="Helvetica-Bold", textColor=BLUE)),
                 Spacer(1, 4), _kpi_table_flowable("Qualité", kpi_qual, cibles, "#2563EB", styles, mode_conformite)]

    img_buf = _graphique_anomalies_image(anomalies, short_labels)
    if img_buf:
        chart_flow = [Paragraph("ANOMALIES PAR INDICATEUR", ParagraphStyle(name="t3", fontSize=9.5, fontName="Helvetica-Bold", textColor=BLUE)),
                      Spacer(1, 4), Image(img_buf, width=8 * cm, height=6.8 * cm)]
    else:
        chart_flow = [Paragraph("ANOMALIES PAR INDICATEUR", ParagraphStyle(name="t3", fontSize=9.5, fontName="Helvetica-Bold", textColor=BLUE)),
                      Spacer(1, 4), Paragraph("Aucune anomalie sur ce poste.", styles["Corps"])]

    trois_colonnes = Table([[perf_flow, qual_flow, chart_flow]], colWidths=[9.2 * cm, 9.2 * cm, 9 * cm])
    trois_colonnes.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(trois_colonnes)
    story.append(Spacer(1, 12))

    # ── Plan d'action ──
    plan_sorted = sorted(plan_action, key=lambda p: -p["nb_anom"])
    story.append(Paragraph(f"PLAN D'ACTION — TOUS LES INDICATEURS EN ANOMALIE ({len(plan_sorted)})", styles["SectionTitre"]))

    cell_style = ParagraphStyle(name="cell", fontSize=7.5, fontName="Helvetica", leading=9)
    rows = [["Indicateur", "Écart", "Nécessité action", "Responsable", "Action"]]
    necessite_colors = []
    for p in plan_sorted:
        necessite = "Oui" if p["nb_anom"] > 0 else "Non"
        necessite_colors.append(RED if necessite == "Oui" else GREEN)
        rows.append([
            Paragraph(p["kpi"], cell_style), f"{p['ecart']:+.1f}", necessite,
            Paragraph(p["responsable"], cell_style), Paragraph(p["action"], cell_style),
        ])
    t = Table(rows, colWidths=[4.5 * cm, 1.8 * cm, 2.8 * cm, 3.5 * cm, 14.4 * cm])
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("ALIGN", (1, 0), (2, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LGREY]),
    ]
    for i, c in enumerate(necessite_colors, start=1):
        style.append(("BACKGROUND", (2, i), (2, i), c))
        style.append(("TEXTCOLOR", (2, i), (2, i), WHITE))
        style.append(("FONTNAME", (2, i), (2, i), "Helvetica-Bold"))
    t.setStyle(TableStyle(style))
    story.append(t)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), topMargin=1 * cm, bottomMargin=1 * cm,
                             leftMargin=1 * cm, rightMargin=1 * cm)
    doc.build(story)
    buf.seek(0)
    return buf.getvalue()
