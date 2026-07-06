# -*- coding: utf-8 -*-
"""
Assistant IA (Groq — gratuit) pour le tableau de bord KPI OCP.

Deux fonctionnalités :
  1. Analyse automatique  : synthèse écrite des KPIs du périmètre affiché
  2. Chat                 : questions/réponses sur les données

Configuration (Streamlit Cloud → Settings → Secrets) :
    GROQ_API_KEY = "gsk_..."

Obtenir une clé gratuite : https://console.groq.com (menu API Keys)

Dépendance à ajouter dans requirements.txt :
    groq
"""
import streamlit as st

# Modèle Groq (gratuit, rapide). Llama 3.3 70B = bon raisonnement en français.
MODEL = "llama-3.3-70b-versatile"
MAX_TOKENS = 1500


def _get_client():
    """Retourne un client Groq ou None si la clé n'est pas configurée."""
    api_key = st.secrets.get("GROQ_API_KEY", None)
    if not api_key:
        return None
    try:
        from groq import Groq
        return Groq(api_key=api_key)
    except Exception:
        return None


def _build_context(entity, vp, pa, qa, pscores, qscores, ano_map,
                    fichier_date, cible_map):
    """Construit un résumé compact des données pour le contexte de l'IA."""
    lines = [
        f"Entité : {entity}",
        f"Date des données : {fichier_date}",
        f"Postes analysés ({len(vp)}) : {', '.join(str(p) for p in vp)}",
        "",
        "TAUX MOYENS PAR INDICATEUR (valeur % / cible %) :",
        "— Performance —",
    ]
    for k, v in pa.items():
        tgt = cible_map.get(k, 100)
        try:
            lines.append(f"  {k} : {float(v):.1f}% (cible {tgt}%)")
        except (ValueError, TypeError):
            lines.append(f"  {k} : n/a")
    lines.append("— Qualité —")
    for k, v in qa.items():
        tgt = cible_map.get(k, 100)
        try:
            lines.append(f"  {k} : {float(v):.1f}% (cible {tgt}%)")
        except (ValueError, TypeError):
            lines.append(f"  {k} : n/a")

    # Top anomalies
    lines.append("")
    lines.append("NOMBRE TOTAL D'ANOMALIES PAR INDICATEUR :")
    ano_totals = {}
    for kpi, series in ano_map.items():
        try:
            ano_totals[kpi] = int(sum(int(series.get(p, 0)) for p in vp))
        except Exception:
            pass
    for kpi, n in sorted(ano_totals.items(), key=lambda x: -x[1])[:10]:
        if n > 0:
            lines.append(f"  {kpi} : {n} OT")

    # Scores par poste (les 5 plus faibles)
    lines.append("")
    lines.append("SCORES PERFORMANCE LES PLUS FAIBLES (par poste) :")
    worst_p = sorted(pscores.items(), key=lambda x: x[1])[:5]
    for p, s in worst_p:
        lines.append(f"  {p} : {s:.0f}%")

    return "\n".join(lines)


SYSTEM_PROMPT = """Tu es un assistant expert en maintenance industrielle et en \
analyse de KPIs SAP PM, pour le groupe OCP (Maroc Chimie / FEEDS).

Tu aides les responsables maintenance à interpréter leurs indicateurs de \
performance et de qualité. Réponds toujours en français, de façon concise, \
concrète et orientée action.

Contexte métier :
- Les KPIs "Age préparation/planification/exécution" en tranches <1 mois, \
1-3 mois, >3 mois représentent le pourcentage d'OT dans chaque tranche d'âge \
(plus bas = mieux pour les tranches 1-3m et >3m).
- Les cibles : <1 mois >= 80%, tranche 1-3 mois <= 15%, tranche >3 mois <= 5%.
- "Caractérisé" = un OT dont le blocage est renseigné (ATPD, ATMR, etc.).
- Une "anomalie" = un OT qui ne respecte pas la règle d'un indicateur.

Quand tu analyses, identifie les points forts, les points faibles prioritaires, \
et propose 2-3 actions concrètes. Ne fais pas de tableaux longs ; privilégie des \
phrases courtes et des listes à puces."""


def _call_groq(client, system, messages):
    """Appel à l'API Groq (compatible OpenAI chat completions)."""
    resp = client.chat.completions.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "system", "content": system}] + messages,
    )
    return resp.choices[0].message.content


def render_ai_assistant(entity, vp, pa, qa, pscores, qscores, ano_map,
                        fichier_date, cible_map):
    """Affiche l'assistant IA (analyse auto + chat)."""
    st.markdown('<div class="stl p">🤖 Assistant IA — Analyse des KPIs</div>',
                unsafe_allow_html=True)

    client = _get_client()
    if client is None:
        st.warning(
            "🔑 Assistant IA non configuré. Ajoutez votre clé API Groq (gratuite) dans "
            "**Manage app → Settings → Secrets** :\n\n"
            '```toml\nGROQ_API_KEY = "gsk_..."\n```\n\n'
            "Obtenez une clé gratuite sur https://console.groq.com (menu API Keys)."
        )
        return

    context = _build_context(entity, vp, pa, qa, pscores, qscores,
                             ano_map, fichier_date, cible_map)

    # ── 1. Analyse automatique ───────────────────────────────────────────
    col1, col2 = st.columns([1, 3])
    with col1:
        analyse = st.button("📊 Générer l'analyse", use_container_width=True)
    if analyse:
        with st.spinner("L'IA analyse vos KPIs…"):
            try:
                analysis_text = _call_groq(
                    client, SYSTEM_PROMPT,
                    [{
                        "role": "user",
                        "content": (
                            "Voici les données KPI du périmètre sélectionné. "
                            "Rédige une synthèse managériale : état général, "
                            "2-3 points forts, 2-3 points faibles prioritaires, "
                            "et des actions concrètes.\n\n" + context
                        ),
                    }],
                )
                st.session_state["ai_last_analysis"] = analysis_text
            except Exception as e:
                st.error(f"Erreur lors de l'analyse : {e}")

    if st.session_state.get("ai_last_analysis"):
        st.markdown(st.session_state["ai_last_analysis"])

    st.markdown("---")

    # ── 2. Chat ──────────────────────────────────────────────────────────
    st.markdown('<div class="stl s">💬 Posez une question sur vos données</div>',
                unsafe_allow_html=True)

    if "ai_chat_history" not in st.session_state:
        st.session_state["ai_chat_history"] = []

    for role, text in st.session_state["ai_chat_history"]:
        with st.chat_message(role):
            st.markdown(text)

    user_q = st.chat_input("Ex : Quel poste a le plus d'OT en retard de préparation ?")
    if user_q:
        st.session_state["ai_chat_history"].append(("user", user_q))
        with st.chat_message("user"):
            st.markdown(user_q)
        with st.chat_message("assistant"):
            with st.spinner("…"):
                try:
                    # Historique complet pour le contexte conversationnel
                    history_msgs = [
                        {"role": role, "content": text}
                        for role, text in st.session_state["ai_chat_history"][:-1]
                    ]
                    answer = _call_groq(
                        client,
                        SYSTEM_PROMPT + "\n\nContexte données actuelles :\n" + context,
                        history_msgs + [{"role": "user", "content": user_q}],
                    )
                    st.markdown(answer)
                    st.session_state["ai_chat_history"].append(("assistant", answer))
                except Exception as e:
                    st.error(f"Erreur : {e}")

    if st.session_state.get("ai_chat_history"):
        if st.button("🗑️ Effacer la conversation"):
            st.session_state["ai_chat_history"] = []
            st.rerun()
