# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
from itertools import groupby
from components.tables import html_plan_actions_table
from core.constants import LOWER_BETTER

_PRINT_CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
*{box-sizing:border-box;margin:0;padding:0;font-family:'Inter',sans-serif}
body{background:#f8fafc;padding:20px;font-size:12px;color:#1e293b}
h1{font-size:20px;font-weight:800;color:#1e3a5f;margin-bottom:6px}
.subtitle{font-size:12px;color:#64748b;margin-bottom:20px}
.section-header{display:flex;justify-content:space-between;align-items:center;
  padding:8px 14px;color:#fff;font-size:14px;font-weight:800;
  border-radius:8px 8px 0 0;margin-top:20px}
.badge{background:rgba(255,255,255,0.2);padding:2px 10px;border-radius:12px;font-size:11px}
table{width:100%;border-collapse:collapse;font-size:11px}
th{background:#1e3a5f;color:#fff;font-weight:700;padding:6px 8px;
   border:1px solid #1e3a5f;text-align:center}
td{padding:5px 8px;border:1px solid #cbd5e1;text-align:center;vertical-align:middle}
td.left{text-align:left}
tr:nth-child(even) td{background:#f8fafc}
.badge-oui{background:#e53e3e;color:#fff;padding:1px 8px;border-radius:10px;
           font-size:9px;font-weight:700}
.badge-non{background:#38a169;color:#fff;padding:1px 8px;border-radius:10px;
           font-size:9px;font-weight:700}
.red{color:#dc2626;font-weight:800}
.green{color:#059669;font-weight:800}
.footer{margin-top:30px;text-align:center;font-size:10px;color:#94a3b8;
        border-top:1px solid #e2e8f0;padding-top:10px}
@media print{
  body{padding:10px}
  .no-print{display:none!important}
  tr{page-break-inside:avoid}
}
</style>"""


def _build_print_table(rows, title, accent):
    if not rows:
        return (f'<div class="section-header" style="background:{accent};margin-top:20px">'
                f'{title} <span class="badge">0 action</span></div>'
                f'<p style="padding:12px;border:1px solid #e2e8f0;border-top:none;color:#64748b">'
                f'✅ Aucune action requise</p>')
    rows_sorted = sorted(rows, key=lambda x: (x["poste"], -abs(x["ecart"])))
    grouped = [(k, list(g)) for k, g in groupby(rows_sorted, key=lambda x: x["poste"])]
    h = (f'<div class="section-header" style="background:{accent};margin-top:20px">'
         f'{title} <span class="badge">{len(rows)} action(s)</span></div>')
    h += '<table><thead><tr>'
    for col in ["Poste de travail","KPI","Action requise","Écart",
                "Nb anomalies","Responsable","Action recommandée"]:
        h += f'<th>{col}</th>'
    h += '</tr></thead><tbody>'
    for poste, group_rows in grouped:
        rowspan = len(group_rows)
        first = True
        for r in group_rows:
            h += '<tr>'
            if first:
                h += (f'<td rowspan="{rowspan}" class="left" '
                      f'style="font-weight:700;color:{accent};border-right:3px solid {accent}">'
                      f'{poste}</td>')
                first = False
            h += f'<td class="left">{r["kpi"]}</td>'
            badge = "badge-oui" if r["needs_action"] else "badge-non"
            label = "OUI" if r["needs_action"] else "NON"
            h += f'<td><span class="{badge}">{label}</span></td>'
            ecart = r["ecart"]
            lower = r["kpi"] in LOWER_BETTER
            is_bad = (ecart < 0 and not lower) or (ecart > 0 and lower)
            clr = "red" if is_bad else "green"
            h += f'<td class="{clr}">{ecart:+.1f}%</td>'
            nb = r["nb_anom"]
            nb_html = f'<span class="red">{nb}</span>' if nb > 0 else f'<span class="green">0</span>'
            h += f'<td>{nb_html}</td>'
            h += f'<td>{r["responsable"]}</td>'
            h += f'<td class="left" style="color:#4a5568">{r["action"]}</td>'
            h += '</tr>'
    h += '</tbody></table>'
    return h


def _build_full_html(sf1_rows, sf2_rows, fichier_date=""):
    body  = _build_print_table(sf1_rows, "SF1 — Plan d'Actions", "#3b82f6")
    body += _build_print_table(sf2_rows, "SF2 — Plan d'Actions", "#10b981")
    total = len(sf1_rows) + len(sf2_rows)
    return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><title>Plan d'action KPI</title>{_PRINT_CSS}</head>
<body>
  <button class="no-print" onclick="window.print()"
    style="margin-bottom:16px;padding:8px 18px;background:#1e3a5f;color:#fff;
           border:none;border-radius:6px;font-size:13px;font-weight:700;cursor:pointer;">
    🖨️ Imprimer / Enregistrer en PDF
  </button>
  <h1>📋 Plan d'action — KPIs Performance &amp; Qualité</h1>
  <p class="subtitle">Date : {fichier_date} &nbsp;|&nbsp; Total : {total}
     &nbsp;|&nbsp; SF1 : {len(sf1_rows)} &nbsp;|&nbsp; SF2 : {len(sf2_rows)}</p>
  {body}
  <div class="footer">Bureau Méthodes Maroc Chimie – © 2026 Tous droits réservés</div>
</body>
</html>"""


def render_plan_action_tab(plan_actions_rows: list, sf1_rows: list,
                            sf2_rows: list, anomaly_dfs: dict) -> None:
    fichier_date = ""
    try:
        if __import__("os").path.exists("date.txt"):
            with open("date.txt", "r", encoding="utf-8") as f:
                fichier_date = f.read().strip()
    except Exception:
        pass

    st.markdown('<div class="stl a">📋 Plan d\'action</div>', unsafe_allow_html=True)

    col_metrics = st.columns(3)
    with col_metrics[0]: st.metric("🔔 Total Actions Requises", len(plan_actions_rows))
    with col_metrics[1]: st.metric("🏭 Actions SF1", len(sf1_rows))
    with col_metrics[2]: st.metric("🏭 Actions SF2", len(sf2_rows))

    st.write("")

    st.markdown(
        html_plan_actions_table(sf1_rows, "SF1 — Plan d'Actions", "#3b82f6", anomaly_dfs),
        unsafe_allow_html=True,
    )
    st.markdown(
        html_plan_actions_table(sf2_rows, "SF2 — Plan d'Actions", "#10b981", anomaly_dfs),
        unsafe_allow_html=True,
    )

    if not plan_actions_rows:
        st.markdown(
            '<div class="es">🎉 Aucune anomalie détectée. Tous les KPIs sont aux normes !</div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown("---")
    st.markdown("### 📥 Aperçu impression")
    full_html = _build_full_html(sf1_rows, sf2_rows, fichier_date)
    estimated_height = max(600, (len(plan_actions_rows) * 38) + 300)
    components.html(full_html, height=min(estimated_height, 1800), scrolling=True)
