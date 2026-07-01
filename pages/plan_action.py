# -*- coding: utf-8 -*-
"""Page Plan d'action — actions correctives pour chaque anomalie."""
import streamlit as st
from core.constants import ACT_MAP, KPI_RESP_MAP, CIBLE


def render(kpi_data, selected_posts):
    """Affiche le plan d'action basé sur les anomalies détectées."""
    all_anomalies = kpi_data.get("ano_p_r", []) + kpi_data.get("ano_q_r", [])

    # Filtrer par postes sélectionnés
    filtered = [a for a in all_anomalies if a.get("Poste de travail") in selected_posts]

    if not filtered:
        st.markdown('<div class="es">✅ Aucune action requise — Tous les KPI sont conformes</div>',
                    unsafe_allow_html=True)
        return

    st.markdown('<div class="stl">PLAN D\'ACTION — %d ANOMALIES</div>' % len(filtered),
                unsafe_allow_html=True)

    # Tableau plan d'action
    h = '<table class="plan-action-table"><thead><tr>'
    cols = ["N°", "Poste", "KPI", "Valeur", "Cible", "Écart", "Action", "Responsable", "Priorité", "Délai", "Statut"]
    for c in cols:
        h += '<th>%s</th>' % c
    h += '</tr></thead><tbody>'

    for i, a in enumerate(filtered, 1):
        ecart = a.get("Écart", 0)
        # Calculer priorité
        abs_ecart = abs(float(ecart)) if ecart else 0
        if abs_ecart > 20:
            priorite = '<span style="color:#dc2626;font-weight:800">HAUTE</span>'
        elif abs_ecart > 10:
            priorite = '<span style="color:#d97706;font-weight:700">MOYENNE</span>'
        else:
            priorite = '<span style="color:#059669;font-weight:600">BASSE</span>'

        h += '<tr>'
        h += '<td>%d</td>' % i
        h += '<td style="font-weight:800">%s</td>' % a.get("Poste de travail", "")
        h += '<td>%s</td>' % a.get("KPI", "")
        h += '<td>%s</td>' % a.get("Valeur", "")
        h += '<td>%s</td>' % a.get("Cible", "")
        h += '<td style="font-weight:700;color:#dc2626">%s</td>' % a.get("Écart", "")
        h += '<td style="text-align:left;font-size:11px">%s</td>' % a.get("Action", "")
        h += '<td>%s</td>' % a.get("Responsable", "")
        h += '<td>%s</td>' % priorite
        h += '<td>À définir</td>'
        h += '<td>En cours</td>'
        h += '</tr>'

    h += '</tbody></table>'
    st.markdown(h, unsafe_allow_html=True)

    # Export
    st.markdown("---")
    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        if st.button("📥 Exporter le plan d'action (Excel)", use_container_width=True):
            _export_plan_action_excel(filtered, cols)
            st.success("Export Excel généré !")
    with col_exp2:
        if st.button("📋 Copier le plan d'action", use_container_width=True):
            _copy_plan_action(filtered, cols)
            st.success("Copié dans le presse-papiers !")


def _export_plan_action_excel(anomalies, cols):
    """Exporte le plan d'action en Excel."""
    try:
        import pandas as pd
        df = pd.DataFrame(anomalies)
        df.to_excel("plan_action.xlsx", index=False, sheet_name="Plan d'action")
    except Exception as e:
        st.error(f"Erreur export : {e}")


def _copy_plan_action(anomalies, cols):
    """Copie le plan d'action dans le presse-papiers."""
    try:
        text = "\t".join(cols) + "\n"
        for i, a in enumerate(anomalies, 1):
            row = [str(i)]
            for c in cols[1:]:
                row.append(str(a.get(c, "")))
            text += "\t".join(row) + "\n"

        import streamlit.components.v1 as components
        components.html(
            f'''<script>
            navigator.clipboard.writeText({repr(text)});
            </script>''',
            height=0
        )
    except Exception:
        pass
