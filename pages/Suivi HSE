# -*- coding: utf-8 -*-
"""
Onglet "Suivi HSE" — suivi des avis de type ZI (incidents) et ZH
(hygiène/sécurité) : statut, transformation en ordre de travail (OT),
et clôture.

À placer dans : pages/suivi_hse.py
"""
import io
import streamlit as st
import pandas as pd
import numpy as np

TYPES_HSE = ["ZI", "ZH"]
LIBELLE_TYPE = {"ZI": "ZI — Incident", "ZH": "ZH — Hygiène / Sécurité"}

COULEURS = {
    "Transformé en OT": "#2563EB",
    "Non transformé": "#F59E0B",
    "Clôturé": "#10B981",
    "En cours": "#EF4444",
}


def _statut_avis(row):
    """Détermine le statut simplifié d'un avis à partir du statut système SAP.
    AENC = avis en cours (non clôturé) · OAFF = ordre affecté ·
    AOUV = avis ouvert (sans ordre) · AIMP = avis imprimé."""
    st_sys = str(row.get("Statut système", "")).upper()
    if "ACLO" in st_sys or "MSCL" in st_sys or pd.notna(row.get("Date de la clôture")):
        return "Clôturé"
    return "En cours"


def _preparer_donnees(avf):
    """Filtre les avis HSE (ZI/ZH) et calcule leurs indicateurs de suivi."""
    if "Type d'avis" not in avf.columns:
        return None
    sub = avf[avf["Type d'avis"].isin(TYPES_HSE)].copy()
    if sub.empty:
        return sub
    sub["Transformé"] = np.where(sub["Ordre"].notna(), "Transformé en OT", "Non transformé")
    sub["Statut HSE"] = sub.apply(_statut_avis, axis=1)
    return sub


def _camembert(donnees, titre):
    """Construit un graphique camembert via matplotlib (rendu net et cohérent
    avec les autres figures de l'application)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = list(donnees.keys())
    valeurs = list(donnees.values())
    couleurs = [COULEURS.get(l, "#64748B") for l in labels]

    fig, ax = plt.subplots(figsize=(4.2, 3.4), dpi=150)
    total = sum(valeurs)

    def _autopct(p):
        # Masquer l'etiquette interne pour les parts trop petites : le texte
        # y serait illisible. La valeur reste lisible dans la legende.
        if p < 8:
            return ""
        return f"{p:.0f}%\n({int(round(p*total/100))})"

    wedges, _, autotexts = ax.pie(
        valeurs, colors=couleurs, autopct=_autopct,
        startangle=90, textprops={"fontsize": 8.5, "color": "white", "fontweight": "bold"},
        wedgeprops={"edgecolor": "white", "linewidth": 2},
    )
    # Legende enrichie avec les valeurs, pour compenser les etiquettes masquees
    labels_legende = [f"{l} — {v} ({v/total*100:.0f}%)" for l, v in zip(labels, valeurs)]
    ax.legend(wedges, labels_legende, loc="center left", bbox_to_anchor=(0.98, 0.5), fontsize=8, frameon=False)
    ax.set_title(titre, fontsize=10.5, fontweight="bold", color="#1E3A5F", pad=10)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf


def _generer_rapport_pdf(sub, date_str):
    """Génère un rapport PDF de synthèse HSE (Python pur, sans dépendance système)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

    NAVY = colors.HexColor("#1E3A5F")
    GREY = colors.HexColor("#64748B")
    LGREY = colors.HexColor("#F1F5F9")

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="T1", fontSize=18, textColor=NAVY, fontName="Helvetica-Bold",
                               leading=23, spaceAfter=8))
    styles.add(ParagraphStyle(name="Sub", fontSize=9.5, textColor=GREY, leading=13, spaceAfter=14))
    styles.add(ParagraphStyle(name="H2x", fontSize=12, textColor=NAVY, fontName="Helvetica-Bold",
                               spaceBefore=14, spaceAfter=6))
    styles.add(ParagraphStyle(name="Cx", fontSize=9, leading=12))

    story = [
        Paragraph("Rapport de suivi HSE — Avis ZI / ZH", styles["T1"]),
        Paragraph(f"Avis d'incident (ZI) et d'hygiène/sécurité (ZH) — Extraction du {date_str}", styles["Sub"]),
    ]

    # Synthèse chiffrée
    total = len(sub)
    transformes = (sub["Transformé"] == "Transformé en OT").sum()
    clotures = (sub["Statut HSE"] == "Clôturé").sum()
    story.append(Paragraph("Synthèse générale", styles["H2x"]))
    synth = [
        ["Indicateur", "Valeur"],
        ["Nombre total d'avis HSE (ZI + ZH)", str(total)],
        ["dont avis ZI (incidents)", str((sub["Type d'avis"] == "ZI").sum())],
        ["dont avis ZH (hygiène / sécurité)", str((sub["Type d'avis"] == "ZH").sum())],
        ["Avis transformés en ordre de travail", f"{transformes} ({transformes/total*100:.0f}%)" if total else "0"],
        ["Avis non transformés", f"{total - transformes} ({(total-transformes)/total*100:.0f}%)" if total else "0"],
        ["Avis clôturés", f"{clotures} ({clotures/total*100:.0f}%)" if total else "0"],
        ["Avis encore en cours", f"{total - clotures} ({(total-clotures)/total*100:.0f}%)" if total else "0"],
    ]
    t = Table(synth, colWidths=[11 * cm, 5 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LGREY]),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
    ]))
    story.append(t)

    # Graphiques
    story.append(Paragraph("Répartition graphique", styles["H2x"]))
    buf1 = _camembert(sub["Transformé"].value_counts().to_dict(), "Transformation en OT")
    buf2 = _camembert(sub["Statut HSE"].value_counts().to_dict(), "Statut de clôture")
    imgs = Table([[Image(buf1, width=7.8 * cm, height=6.3 * cm), Image(buf2, width=7.8 * cm, height=6.3 * cm)]],
                  colWidths=[8.2 * cm, 8.2 * cm])
    imgs.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(imgs)

    # Détail par type et par poste
    story.append(Paragraph("Détail par type d'avis et poste de travail", styles["H2x"]))
    detail = (sub.groupby(["Type d'avis", "Poste travail princ."])
                 .agg(Total=("Avis", "count"),
                      Transformes=("Transformé", lambda x: (x == "Transformé en OT").sum()),
                      Clotures=("Statut HSE", lambda x: (x == "Clôturé").sum()))
                 .reset_index().sort_values("Total", ascending=False).head(25))
    rows = [["Type", "Poste de travail", "Total", "Transf. OT", "Clôturés"]]
    for _, r in detail.iterrows():
        rows.append([r["Type d'avis"], str(r["Poste travail princ."]), str(r["Total"]),
                      str(r["Transformes"]), str(r["Clotures"])])
    t2 = Table(rows, colWidths=[2 * cm, 7 * cm, 2.3 * cm, 2.5 * cm, 2.5 * cm])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LGREY]),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t2)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=1.6 * cm, bottomMargin=1.6 * cm,
                             leftMargin=1.8 * cm, rightMargin=1.8 * cm)
    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def _carte(col, label, valeur, couleur, sous_texte=""):
    col.markdown(
        f"""<div style="background:{couleur}15;border:1px solid {couleur}40;border-radius:10px;
        padding:16px 14px;text-align:center;">
            <div style="font-size:12px;color:#64748B;font-weight:700;text-transform:uppercase;
            letter-spacing:0.5px;margin-bottom:6px;">{label}</div>
            <div style="font-size:28px;font-weight:800;color:{couleur};line-height:1.1;">{valeur}</div>
            <div style="font-size:11px;color:#64748B;margin-top:4px;">{sous_texte}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def render_suivi_hse_tab(avf, date_str=""):
    """
    avf : DataFrame des avis (déjà chargé par l'application principale).
    """
    st.markdown("### 🦺 Suivi HSE — Avis ZI / ZH")
    st.caption(
        "Suivi des avis d'incident (ZI) et d'hygiène/sécurité (ZH) : statut de traitement, "
        "transformation en ordre de travail, et clôture."
    )

    sub = _preparer_donnees(avf)
    if sub is None:
        st.warning("⚠️ La colonne « Type d'avis » est absente du fichier avis.xlsx.")
        return
    if sub.empty:
        st.info("Aucun avis de type ZI ou ZH sur le périmètre et la période sélectionnés.")
        return

    total = len(sub)
    n_zi = (sub["Type d'avis"] == "ZI").sum()
    n_zh = (sub["Type d'avis"] == "ZH").sum()
    transformes = (sub["Transformé"] == "Transformé en OT").sum()
    clotures = (sub["Statut HSE"] == "Clôturé").sum()

    c1, c2, c3, c4, c5 = st.columns(5)
    _carte(c1, "Total avis HSE", str(total), "#1E3A5F", "ZI + ZH")
    _carte(c2, "ZI — Incidents", str(n_zi), "#EF4444", f"{n_zi/total*100:.0f}% du total")
    _carte(c3, "ZH — Hygiène/Sécu.", str(n_zh), "#F59E0B", f"{n_zh/total*100:.0f}% du total")
    _carte(c4, "Transformés en OT", str(transformes), "#2563EB", f"{transformes/total*100:.0f}% du total")
    _carte(c5, "Clôturés", str(clotures), "#10B981", f"{clotures/total*100:.0f}% du total")

    st.markdown("---")

    # ── Graphiques camembert ──
    st.markdown("#### 📊 Répartition graphique")
    g1, g2 = st.columns(2)
    with g1:
        st.image(_camembert(sub["Transformé"].value_counts().to_dict(), "Transformation en ordre de travail"),
                 use_container_width=True)
    with g2:
        st.image(_camembert(sub["Statut HSE"].value_counts().to_dict(), "Statut de clôture"),
                 use_container_width=True)

    st.markdown("---")

    # ── Tableau de synthèse par type ──
    st.markdown("#### 📋 Synthèse par type d'avis")
    synthese = []
    for t in TYPES_HSE:
        s = sub[sub["Type d'avis"] == t]
        if s.empty:
            continue
        n = len(s)
        tr = (s["Transformé"] == "Transformé en OT").sum()
        cl = (s["Statut HSE"] == "Clôturé").sum()
        synthese.append({
            "Type d'avis": LIBELLE_TYPE.get(t, t),
            "Nombre d'avis": n,
            "Transformés en OT": tr,
            "% transformés": f"{tr/n*100:.0f}%",
            "Non transformés": n - tr,
            "Clôturés": cl,
            "% clôturés": f"{cl/n*100:.0f}%",
            "En cours": n - cl,
        })
    st.dataframe(pd.DataFrame(synthese), use_container_width=True, hide_index=True)

    # ── Détail par poste de travail ──
    st.markdown("#### 🏭 Détail par poste de travail")
    detail = (sub.groupby(["Poste travail princ.", "Type d'avis"])
                 .agg(Total=("Avis", "count"),
                      Transformés=("Transformé", lambda x: (x == "Transformé en OT").sum()),
                      Clôturés=("Statut HSE", lambda x: (x == "Clôturé").sum()))
                 .reset_index().sort_values("Total", ascending=False))
    detail = detail.rename(columns={"Poste travail princ.": "Poste de travail", "Type d'avis": "Type"})
    st.dataframe(detail, use_container_width=True, hide_index=True, height=320)

    # ── Liste détaillée des avis ──
    with st.expander("🔍 Liste détaillée de tous les avis HSE", expanded=False):
        cols_aff = ["Avis", "Type d'avis", "Description", "Poste travail princ.",
                     "Désignation du poste technique", "Statut système", "Transformé", "Statut HSE", "Créé le"]
        cols_dispo = [c for c in cols_aff if c in sub.columns]
        st.dataframe(sub[cols_dispo].sort_values("Créé le", ascending=False),
                     use_container_width=True, hide_index=True, height=380)

    st.markdown("---")

    # ── Bouton de génération du rapport PDF ──
    st.markdown("#### 📄 Rapport de synthèse HSE")
    if st.button("🖨️ Générer le rapport PDF", type="primary", use_container_width=True):
        try:
            pdf_bytes = _generer_rapport_pdf(sub, date_str or "date non précisée")
            st.download_button(
                "⬇️ Télécharger le rapport HSE (PDF)",
                data=pdf_bytes,
                file_name=f"rapport_HSE_ZI_ZH_{str(date_str).replace('/', '-')}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
            st.success("✅ Rapport généré — cliquez sur le bouton de téléchargement ci-dessus.")
        except Exception as e:
            st.error(f"❌ Erreur lors de la génération du rapport : {e}")
