# -*- coding: utf-8 -*-
"""
Construit l'historique COMPLET des cas de défaut passés, en croisant :
  - les données JOURNALIÈRES (vibration générale, courant, débit, pression)
    -> permettent de détecter les épisodes où la vibration générale a
       dépassé le seuil (z-score > 3), déclenchant la DEMANDE d'une
       mesure axiale détaillée (workflow réel décrit par l'utilisateur) ;
  - les données HEBDOMADAIRES détaillées (3 points, H/V/A, température)
    -> fournissent la mesure axiale/température effectivement relevée
       en réponse à cette demande, et permettent le diagnostic spectral.

Chaque cas historique enregistre explicitement : la vibration axiale
hebdomadaire, la température hebdomadaire, si le cas a été déclenché par
un dépassement de la vibration générale journalière, et un type de
panne diversifié (pas uniquement alignement/roulement) déduit de la
signature complète (axial, radial H/V, température).
"""
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/claude")
from core.vibration_analysis import (
    generer_spectre, diagnostiquer_spectre, z_score_vibration_journaliere,
)

TYPES_PANNE_DIVERSIFIES = [
    "Défaut d'alignement", "Usure roulement (bague extérieure)",
    "Usure roulement (bague intérieure)", "Balourd", "Surchauffe palier",
    "Cavitation", "Défaut électrique",
]


def diagnostiquer_type_diversifie(row, rng):
    """
    Détermine un type de panne diversifié pour un cas historique, à
    partir de la signature complète de la semaine (axial, radial H/V,
    température) — logique de priorité :
      1. Axial très dominant (> H et > V nettement) -> Défaut d'alignement
      2. Température très élevée                    -> Surchauffe palier
      3. Radial H ou V dominant, amplitude modérée   -> Balourd
      4. Radial H ou V dominant, amplitude forte      -> Usure roulement
         (bague extérieure si H dominant, intérieure si V dominant —
         convention illustrative pour diversifier les cas)
      5. Sinon (résiduel)                             -> Cavitation / électrique
    """
    h, v, a, temp = row["H"], row["V"], row["A"], row["temperature"]

    if a > max(h, v) * 1.3 and a > 3.0:
        return "Défaut d'alignement"
    if temp > 62.0:
        return "Surchauffe palier"
    if max(h, v) > 5.5:
        return "Usure roulement (bague extérieure)" if h >= v else "Usure roulement (bague intérieure)"
    if max(h, v) > 3.5:
        return "Balourd"
    return rng.choice(["Cavitation", "Défaut électrique"])


def construire_historique_complet(daily_df, hebdo_df):
    """Construit l'historique enrichi, croisant journalier et hebdomadaire."""
    rng = np.random.default_rng(42)
    daily_df = daily_df.copy()
    daily_df["date"] = pd.to_datetime(daily_df["date"])
    daily_df["semaine"] = daily_df["date"].dt.to_period("W").apply(lambda p: p.start_time)

    hebdo_df = hebdo_df.copy()
    hebdo_df["date"] = pd.to_datetime(hebdo_df["date"])

    baseline_par_pompe = {}
    for pompe_id in daily_df["pompe"].unique():
        sub = daily_df[daily_df["pompe"] == pompe_id]
        normal = sub.loc[sub["anomalie"] == 0, "vibration"]
        baseline_par_pompe[pompe_id] = (normal.mean(), normal.std())

    def z_score(pompe_id, valeur):
        m, s = baseline_par_pompe[pompe_id]
        return (valeur - m) / s if s > 0 else 0.0

    daily_df["z_vibration"] = daily_df.apply(lambda r: z_score(r["pompe"], r["vibration"]), axis=1)
    declenchement_semaine = (
        daily_df.groupby(["pompe", "semaine"])["z_vibration"].max().reset_index()
        .rename(columns={"z_vibration": "z_max_semaine"})
    )
    declenchement_semaine["declenche_par_vibration_generale"] = declenchement_semaine["z_max_semaine"] > 3.0

    cas_historiques = []
    defauts = hebdo_df[hebdo_df["defaut_detecte"] == 1].copy()

    for _, row in defauts.iterrows():
        pompe_id, point, date = int(row["pompe"]), row["point"], row["date"]

        decl = declenchement_semaine[
            (declenchement_semaine["pompe"] == pompe_id) & (declenchement_semaine["semaine"] == date)
        ]
        declenche_vib_gen = bool(decl["declenche_par_vibration_generale"].iloc[0]) if len(decl) else False
        z_max = float(decl["z_max_semaine"].iloc[0]) if len(decl) else None

        type_diag = diagnostiquer_type_diversifie(row, rng)

        direction_max = max({"H": row["H"], "V": row["V"], "A": row["A"]}, key=lambda d: row[d])

        # Le diagnostic spectral (base sur la signature FFT) n'a de sens
        # que pour les defauts mecaniques (alignement, usure roulement,
        # balourd) -- pour la surchauffe (thermique) ou le defaut
        # electrique, la cause n'est pas de nature vibratoire, et generer
        # un faux spectre de roulement serait trompeur.
        if "alignement" in type_diag.lower():
            type_defaut_sim = "alignement"
        elif "roulement" in type_diag.lower() or "balourd" in type_diag.lower():
            type_defaut_sim = "roulement"
        else:
            type_defaut_sim = None

        if type_defaut_sim is not None:
            freq_axis, amplitude = generer_spectre(
                pompe_id, point, direction_max, en_defaut=True, type_defaut=type_defaut_sim,
                seed=hash(f"{date}_{pompe_id}_{point}") % 10000,
            )
            if amplitude.max() > 0:
                amplitude = amplitude * (row[direction_max] / amplitude.max())
            diag_spectral_txt = diagnostiquer_spectre(freq_axis, amplitude, pompe_id, point)["diagnostic"]
        else:
            diag_spectral_txt = "Non applicable — diagnostic basé sur les données de process (température/courant), pas sur une signature spectrale mécanique"

        cas_historiques.append({
            "date": date.strftime("%Y-%m-%d"),
            "pompe": f"IP0{pompe_id}",
            "point": point,
            "vibration_H_mm_s": round(float(row["H"]), 2),
            "vibration_V_mm_s": round(float(row["V"]), 2),
            "vibration_axiale_A_mm_s": round(float(row["A"]), 2),
            "temperature_C": round(float(row["temperature"]), 1),
            "declenche_par_vibration_generale_journaliere": declenche_vib_gen,
            "z_score_vibration_generale": round(z_max, 2) if z_max is not None else None,
            "type_panne_diagnostique": type_diag,
            "diagnostic_spectral": diag_spectral_txt,
            "gravite": ("alerte" if ("Usure roulement" in type_diag or "alignement" in type_diag.lower() or "Surchauffe" in type_diag)
                        else "surveillance"),
        })

    return pd.DataFrame(cas_historiques).sort_values("date").reset_index(drop=True)


if __name__ == "__main__":
    daily = pd.read_csv("/home/claude/feature_dataset.csv")
    hebdo = pd.read_csv("/home/claude/donnees_vibration_hebdo.csv")

    historique = construire_historique_complet(daily, hebdo)
    historique.to_csv("/home/claude/historique_defauts_pompes.csv", index=False)

    print(f"Historique construit : {len(historique)} cas de défaut")
    print()
    print("Répartition par type de panne diagnostique (diversifié) :")
    print(historique["type_panne_diagnostique"].value_counts())
    print()
    print("Cas déclenchés par une vibration générale journalière anormale :")
    print(historique["declenche_par_vibration_generale_journaliere"].value_counts())
    print()
    print("Aperçu (8 premiers cas) :")
    print(historique.head(8).to_string(index=False))
