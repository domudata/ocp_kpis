# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components

from components.tables import html_plan_actions_table


def _stars_html(stars: int, score) -> str:
    """5 etoiles pleines/vides selon le score global du poste (0-100% -> 0-5)."""
    stars = max(0, min(5, int(stars)))
    full = "★" * stars
    empty = "☆" * (5 - stars)
    return (
        f'<span style="color:#f59e0b;font-size:16px;letter-spacing:1px">{full}</span>'
        f'<span style="color:#cbd5e1;font-size:16px;letter-spacing:1px">{empty}</span>'
    )


def html_poste_scores_table(vp: list, poste_stars: dict) -> str:
    """Tableau recapitulatif : Score global (5 etoiles) par poste de travail."""
    if not poste_stars:
        return '<div class="es">Aucune donnee de score</div>'

    rows_sorted = sorted(
        vp, key=lambda p: (poste_stars.get(p, {}).get("score") or 0), reverse=True
    )

    h = (
        '<div class="ca" style="margin-bottom:14px;">'
        '<div class="ct" style="color:#1e3a5f">⭐ Score global par poste de travail</div>'
        '<table class="plan-action-table"><thead><tr>'
        '<th>Poste de travail</th><th>Score global</th>'
        '</tr></thead><tbody>'
    )
    for i, poste in enumerate(rows_sorted):
        info = poste_stars.get(poste, {"score": None, "stars": 0})
        bg = "#ffffff" if i % 2 == 0 else "#f8fafc"
        h += (
            f'<tr style="background:{bg};">'
            f'<td style="text-align:left;font-weight:700;color:#1e293b;">{poste}</td>'
            f'<td>{_stars_html(info["stars"], info["score"])}</td>'
            f'</tr>'
        )
    h += '</tbody></table></div>'
    return h


# ── CSS embarqué pour la page d'impression ────────────────────────────────
_PRINT_CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
  body { background: #f8fafc; padding: 20px; font-size: 12px; color: #1e293b; }

  h1 { font-size: 20px; font-weight: 800; color: #1e3a5f; margin-bottom: 6px; }
  .subtitle { font-size: 12px; color: #64748b; margin-bottom: 20px; }

  .section-header {
    display: flex; justify-content: space-between; align-items: center;
    padding: 8px 14px; color: #fff; font-size: 14px; font-weight: 800;
    border-radius: 8px 8px 0 0; margin-top: 20px;
  }
  .badge {
    background: rgba(255,255,255,0.2); padding: 2px 10px;
    border-radius: 12px; font-size: 11px;
  }

  table { width: 100%; border-collapse: collapse; font-size: 11px; }
  th {
    background: #1e3a5f; color: #fff; font-weight: 700;
    padding: 6px 8px; border: 1px solid #1e3a5f; text-align: center;
  }
  td {
    padding: 5px 8px; border: 1px solid #cbd5e1;
    text-align: center; vertical-align: middle;
  }
  td.left { text-align: left; }
  tr:nth-child(even) td { background: #f8fafc; }

  .badge-oui { background:#e53e3e; color:#fff; padding:1px 8px; border-radius:10px; font-size:9px; font-weight:700; }
  .badge-non { background:#38a169; color:#fff; padding:1px 8px; border-radius:10px; font-size:9px; font-weight:700; }
  .badge-oui-vert { background:#38a169; color:#fff; padding:1px 8px; border-radius:10px; font-size:9px; font-weight:700; }
  .red   { color: #dc2626; font-weight: 800; }
  .green { color: #059669; font-weight: 800; }
  .grey  { color: #94a3b8; }

  .footer { margin-top: 30px; text-align: center; font-size: 10px; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 10px; }

  @media print {
    body { padding: 10px; }
    .no-print { display: none !important; }
    table { page-break-inside: auto; }
    tr { page-break-inside: avoid; }
  }
</style>
"""


def _build_print_table(rows: list, title: str, accent: str, anomaly_dfs: dict) -> str:
    """Génère un bloc HTML autonome (titre + tableau) pour l'impression."""
    if not rows:
        return f'<div class="section-header" style="background:{accent};margin-top:20px">{title} <span class="badge">0 action</span></div><p style="padding:12px;border:1px solid #e2e8f0;border-top:none;color:#64748b">✅ Aucune action requise</p>'

    from itertools import groupby
    from core.constants import LOWER_BETTER

    rows_sorted = sorted(rows, key=lambda x: (x["poste"], -abs(x["ecart"])))
    grouped = [(k, list(g)) for k, g in groupby(rows_sorted, key=lambda x: x["poste"])]

    h = f'<div class="section-header" style="background:{accent};margin-top:20px">{title} <span class="badge">{len(rows)} action(s)</span></div>'
    h += '<table><thead><tr>'
    for col in ["Poste de travail", "KPI", "Cible", "Action requise", "Écart", "Nb anomalies", "Responsable", "Action recommandée"]:
        h += f'<th>{col}</th>'
    h += '</tr></thead><tbody>'

    row_idx = 0
    for poste, group_rows in grouped:
        rowspan = len(group_rows)
        first = True
        for r in group_rows:
            h += '<tr>'
            if first:
                h += f'<td rowspan="{rowspan}" class="left" style="font-weight:700;color:{accent};border-right:3px solid {accent}">{poste}</td>'
                first = False
            h += f'<td class="left">{r["kpi"]}</td>'
            _target = r.get("target")
            _target_txt = f"{_target:.0f}%" if _target is not None else "—"
            h += f'<td>{_target_txt}</td>'
            _st = r.get("status", "oui_rouge" if r["needs_action"] else "non_vert")
            if _st == "oui_rouge":
                h += '<td><span class="badge-oui">OUI</span></td>'
            elif _st == "oui_vert":
                h += '<td><span class="badge-oui-vert">OUI</span></td>'
            else:
                h += '<td><span class="badge-non">NON</span></td>'

            ecart = r["ecart"]
            is_bad = ecart < 0
            clr_cls = "red" if is_bad else "green"
            h += f'<td class="{clr_cls}">{ecart:+.1f}%</td>'
            h += f'<td>{"<span class=red>" + str(r["nb_anom"]) + "</span>" if r["nb_anom"] > 0 else "<span class=green>0</span>"}</td>'
            h += f'<td>{r["responsable"]}</td>'
            h += f'<td class="left" style="color:#4a5568">{r["action"]}</td>'
            h += '</tr>'
            row_idx += 1

    h += '</tbody></table>'
    return h


def _build_full_html(sf1_rows, sf2_rows, anomaly_dfs, fichier_date="") -> str:
    """Assemble la page HTML complète pour impression."""
    body  = _build_print_table(sf1_rows, "SF1 — Plan d'Actions", "#3b82f6", anomaly_dfs)
    body += _build_print_table(sf2_rows, "SF2 — Plan d'Actions", "#10b981", anomaly_dfs)
    total = len(sf1_rows) + len(sf2_rows)

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <title>Plan d'action KPI</title>
  {_PRINT_CSS}
</head>
<body>
  <button class="no-print"
    onclick="window.print()"
    style="margin-bottom:16px;padding:8px 18px;background:#1e3a5f;color:#fff;
           border:none;border-radius:6px;font-size:13px;font-weight:700;cursor:pointer;">
    🖨️ Imprimer / Enregistrer en PDF
  </button>

  <h1>📋 Plan d'action — KPIs Performance &amp; Qualité</h1>
  <p class="subtitle">Date : {fichier_date} &nbsp;|&nbsp; Total actions : {total}
     &nbsp;|&nbsp; SF1 : {len(sf1_rows)} &nbsp;|&nbsp; SF2 : {len(sf2_rows)}</p>

  {body}

  <div class="footer">Bureau Méthodes Maroc Chimie – © 2026 Tous droits réservés</div>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────

def render_plan_action_tab(plan_actions_rows: list, sf1_rows: list,
                            sf2_rows: list, anomaly_dfs: dict,
                            fichier_date: str = "", poste_stars: dict = None) -> None:
    st.markdown('<div class="stl a">📋 Plan d\'action</div>', unsafe_allow_html=True)

    # ── Métriques ──
    col_metrics = st.columns(3)
    with col_metrics[0]: st.metric("🔔 Total Actions Requises", len(plan_actions_rows))
    with col_metrics[1]: st.metric("🏭 Actions SF1", len(sf1_rows))
    with col_metrics[2]: st.metric("🏭 Actions SF2", len(sf2_rows))

    st.write("")

    # ── Tableaux dans l'app (étoiles intégrées dans la colonne Poste) ──
    st.markdown(
        html_plan_actions_table(sf1_rows, "SF1 — Plan d'Actions", "#3b82f6", anomaly_dfs, poste_stars),
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="height:28px;border-bottom:2px dashed #cbd5e1;margin-bottom:24px;"></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        html_plan_actions_table(sf2_rows, "SF2 — Plan d'Actions", "#10b981", anomaly_dfs, poste_stars),
        unsafe_allow_html=True,
    )

    if not plan_actions_rows:
        st.markdown(
            '<div class="es">🎉 Aucune anomalie détectée. Tous les KPIs sont aux normes !</div>',
            unsafe_allow_html=True,
        )
        return

    # ── Aperçu PDF : caché par défaut, affiché seulement sur demande ──
    st.markdown("---")

    if "show_pdf_preview" not in st.session_state:
        st.session_state.show_pdf_preview = False

    col_btn, _ = st.columns([1, 3])
    with col_btn:
        if st.button("🖨️ Générer l'aperçu PDF", use_container_width=True):
            st.session_state.show_pdf_preview = True

    if st.session_state.show_pdf_preview:
        if st.button("✖️ Fermer l'aperçu"):
            st.session_state.show_pdf_preview = False
            st.rerun()

        st.markdown("### 📥 Aperçu PDF — cliquez sur *Imprimer* dans l'aperçu ci-dessous")

        full_html = _build_full_html(sf1_rows, sf2_rows, anomaly_dfs, fichier_date)

        # Hauteur dynamique : ~38px par ligne + marge
        estimated_height = max(600, (len(plan_actions_rows) * 38) + 300)

        components.html(full_html, height=min(estimated_height, 1800), scrolling=True)
