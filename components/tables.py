# -*- coding: utf-8 -*-
"""Composants de tableaux HTML réutilisables."""
import streamlit as st
from core.constants import CIBLE


def html_statut_pivot(piv_df, table_class):
    """Génère un tableau HTML coloré par statut OT (CRÉÉ, LANC, CLOT, TCLO)."""
    cols = ["Poste de travail", "CRÉÉ", "LANC", "CLOT", "TCLO", "Total"]
    statut_colors = {
        "CRÉÉ": "background:#fef3c7;color:#92400e;font-weight:600;",
        "LANC": "background:#dbeafe;color:#1e40af;font-weight:600;",
        "CLOT": "background:#d1fae5;color:#065f46;font-weight:600;",
        "TCLO": "background:#a7f3d0;color:#064e3b;font-weight:600;",
        "Total": "background:#ede9fe;color:#5b21b6;font-weight:700;"
    }

    h = '<table class="tw %s"><thead><tr>' % table_class + ''.join('<th>%s</th>' % c for c in cols) + '</tr></thead><tbody>'
    for poste, row in piv_df.iterrows():
        h += '<tr><td style="font-weight:700">%s</td>' % poste
        for c in ["CRÉÉ", "LANC", "CLOT", "TCLO"]:
            h += '<td style="text-align:center;%s">%d</td>' % (statut_colors[c], int(row.get(c, 0)))
        h += '<td style="text-align:center;%s">%d</td>' % (statut_colors["Total"], int(row.get("Total", 0)))
        h += '</tr>'

    h += '<tr class="tr"><td style="font-weight:800">Total</td>'
    for c in ["CRÉÉ", "LANC", "CLOT", "TCLO"]:
        h += '<td style="text-align:center;font-weight:800;%s">%d</td>' % (statut_colors[c], int(piv_df[c].sum()))
    h += '<td style="text-align:center;font-weight:800;%s">%d</td>' % (statut_colors["Total"], int(piv_df["Total"].sum()))
    h += '</tr></tbody></table>'
    return h


def render_synthesis_table(rows, cols, table_class=""):
    """Rendu d'un tableau de synthèse KPI avec coloration conditionnelle."""
    if not rows or not cols:
        st.markdown('<div class="es">Aucune donnée</div>', unsafe_allow_html=True)
        return

    h = '<table class="tw %s"><thead><tr>' % table_class
    for c in cols:
        h += '<th>%s</th>' % c
    h += '</tr></thead><tbody>'

    for i, row in enumerate(rows):
        poste = row.get("Poste de travail", "")
        is_total = poste == "Total general"
        is_cible = poste == "CIBLE"
        row_class = ' class="cb"' if is_cible else ''

        h += '<tr%s>' % row_class
        for j, c in enumerate(cols):
            val = row.get(c, "")
            if j == 0:
                cell_style = ' style="font-weight:800"' if is_total else ' class="poste-cell"'
                h += '<td%s>%s</td>' % (cell_style, val)
            else:
                cell_html = _color_kpi_cell(c, val, is_cible)
                h += '<td style="text-align:center;%s">%s</td>' % (cell_html[0], cell_html[1])
        h += '</tr>'

    h += '</tbody></table>'
    st.markdown(h, unsafe_allow_html=True)


def _color_kpi_cell(col_name, value, is_cible=False):
    """Retourne (style, display_value) avec coloration conditionnelle pour une cellule KPI."""
    if is_cible:
        return ("", str(value))

    try:
        v = float(value)
    except (ValueError, TypeError):
        return ("", str(value) if value is not None else "")

    cible = CIBLE.get(col_name, None)
    if cible is None:
        return ("", str(round(v, 1)))

    from core.constants import LOWER_BETTER
    if col_name in LOWER_BETTER:
        if v <= cible:
            return ("background:#d1fae5;color:#065f46;font-weight:700;", str(round(v, 1)))
        elif v <= cible * 1.5:
            return ("background:#fef3c7;color:#92400e;font-weight:600;", str(round(v, 1)))
        else:
            return ("background:#fee2e2;color:#991b1b;font-weight:700;", str(round(v, 1)))
    else:
        if v >= cible:
            return ("background:#d1fae5;color:#065f46;font-weight:700;", str(round(v, 1)))
        elif v >= cible * 0.8:
            return ("background:#fef3c7;color:#92400e;font-weight:600;", str(round(v, 1)))
        else:
            return ("background:#fee2e2;color:#991b1b;font-weight:700;", str(round(v, 1)))


def render_anomaly_table(rows, cols, table_class="at"):
    """Rendu du tableau des anomalies."""
    if not rows:
        st.markdown('<div class="es">✅ Aucune anomalie détectée</div>', unsafe_allow_html=True)
        return

    h = '<table class="tw %s"><thead><tr>' % table_class
    for c in cols:
        h += '<th>%s</th>' % c
    h += '</tr></thead><tbody>'

    for row in rows:
        h += '<tr>'
        for c in cols:
            val = row.get(c, "")
            if c == "Poste de travail":
                h += '<td class="poste-cell">%s</td>' % val
            elif c == "Statut":
                h += '<td style="text-align:center;background:#fee2e2;color:#991b1b;font-weight:700;">%s</td>' % val
            else:
                h += '<td style="text-align:center">%s</td>' % val
        h += '</tr>'

    h += '</tbody></table>'
    st.markdown(h, unsafe_allow_html=True)
