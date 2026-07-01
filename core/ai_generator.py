# -*- coding: utf-8 -*-
"""Génération IA de plans d'action et recommandations via OpenAI."""
# ── RECONSTRUIT ──
from core.constants import ACT_MAP, KPI_RESP_MAP, CIBLE


def generate_action_plan(anomalies, api_key, model="gpt-4o-mini"):
    """Appelle OpenAI pour générer un plan d'action à partir des anomalies."""
    if not api_key or not anomalies:
        return ""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        # Construire le prompt
        prompt = "Tu es un expert en maintenance industrielle. "
        prompt += "Génère un plan d'action détaillé pour les anomalies KPI suivantes.\n\n"
        prompt += "Format : tableau markdown avec colonnes | Poste | KPI | Valeur | Cible | "
        prompt += "Action corrective | Responsable | Délai | Priorité |\n\n"
        prompt += "Anomalies détectées :\n"
        for a in anomalies:
            prompt += (f"- {a.get('Poste de travail', '')} | {a.get('KPI', '')} | "
                       f"{a.get('Valeur', '')} | {a.get('Cible', '')} | "
                       f"{a.get('Action', '')} | {a.get('Responsable', '')}\n")

        prompt += "\nGénère maintenant le plan d'action complet en français."

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Tu es un expert maintenance industrielle. Réponds en français."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=4000
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Erreur IA : {str(e)}"


def generate_recommendations(kpi_data, api_key, model="gpt-4o-mini"):
    """Génère des recommandations par poste de travail."""
    if not api_key:
        return ""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        prompt = "Tu es un expert en maintenance industrielle. "
        prompt += "Analyse les KPI suivants et donne 3 recommandations prioritaires par poste.\n\n"

        for row in kpi_data.get("p_rows", []):
            poste = row.get("Poste de travail", "")
            if poste in ("Total general", "CIBLE"):
                continue
            prompt += f"\n### {poste}\n"
            for k, v in row.items():
                if k != "Poste de travail" and v != "":
                    cible = CIBLE.get(k, "")
                    prompt += f"- {k}: {v}"
                    if cible:
                        prompt += f" (cible: {cible})"
                    prompt += "\n"

        for row in kpi_data.get("q_rows", []):
            poste = row.get("Poste de travail", "")
            if poste in ("Total general", "CIBLE"):
                continue
            prompt += f"\n### {poste}\n"
            for k, v in row.items():
                if k != "Poste de travail" and v != "":
                    cible = CIBLE.get(k, "")
                    prompt += f"- {k}: {v}"
                    if cible:
                        prompt += f" (cible: {cible})"
                    prompt += "\n"

        prompt += "\nGénère les recommandations en français, par poste, avec priorité (Haute/Moyenne/Basse)."

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Tu es un expert maintenance. Réponds en français avec un format clair."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=4000
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Erreur IA : {str(e)}"
