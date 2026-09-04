# -*- coding: utf-8 -*-
"""
Module d'analyse vibratoire avancée pour la maintenance prédictive des
pompes — à placer dans : core/vibration_analysis.py

Contient :
  - Le calcul des fréquences caractéristiques de défaut de roulement
    (BPFO/BPFI/BSF/FTF), à partir de la fiche technique du roulement ;
  - La génération d'un spectre vibratoire simulé (à remplacer par un
    spectre réel dès qu'un capteur FFT sera disponible, chapitre 7) ;
  - Le diagnostic automatique par correspondance pic/fréquence
    caractéristique ;
  - La détection d'anomalie sur la mesure journalière de vibration
    (déclenchement de l'analyse détaillée à 7 jours).

⚠️ Les caractéristiques de roulement (FICHE_TECHNIQUE_ROULEMENTS) sont
des valeurs TYPIQUES pour des roulements à billes de taille compatible
avec le parc de pompes IP01-IP04 — à remplacer par les références
exactes des roulements montés dès que la fiche technique constructeur
sera disponible.
"""
import math
import numpy as np
import pandas as pd

# ═══════════════════════════════════════════════════════════════════
# 1) Fréquences caractéristiques de défaut de roulement
# ═══════════════════════════════════════════════════════════════════

FICHE_TECHNIQUE_ROULEMENTS = {
    1: {  # IP01 - HF 10V-2R, 750 tr/min
        "moteur_DE": {"n_billes": 8, "d_bille": 12.7, "d_primitif": 71.5, "angle": 0, "type": "6312"},
        "moteur_NDE": {"n_billes": 8, "d_bille": 11.1, "d_primitif": 63.5, "angle": 0, "type": "6310"},
        "pompe": {"n_billes": 10, "d_bille": 15.08, "d_primitif": 90.0, "angle": 0, "type": "6316"},
    },
    2: {  # IP02 - AGV 12D, 600 tr/min
        "moteur_DE": {"n_billes": 8, "d_bille": 11.1, "d_primitif": 63.5, "angle": 0, "type": "6310"},
        "moteur_NDE": {"n_billes": 8, "d_bille": 9.5, "d_primitif": 55.0, "angle": 0, "type": "6308"},
        "pompe": {"n_billes": 10, "d_bille": 12.7, "d_primitif": 80.0, "angle": 0, "type": "6314"},
    },
    3: {  # IP03 - 500 VE 470-54-2R, 1000 tr/min
        "moteur_DE": {"n_billes": 9, "d_bille": 12.7, "d_primitif": 75.0, "angle": 0, "type": "6313"},
        "moteur_NDE": {"n_billes": 8, "d_bille": 11.1, "d_primitif": 63.5, "angle": 0, "type": "6310"},
        "pompe": {"n_billes": 8, "d_bille": 14.29, "d_primitif": 85.0, "angle": 0, "type": "6315"},
    },
    4: {  # IP04 - 600 VE 530-70-2, 750 tr/min
        "moteur_DE": {"n_billes": 8, "d_bille": 15.08, "d_primitif": 90.0, "angle": 0, "type": "6316"},
        "moteur_NDE": {"n_billes": 8, "d_bille": 12.7, "d_primitif": 71.5, "angle": 0, "type": "6312"},
        "pompe": {"n_billes": 10, "d_bille": 17.46, "d_primitif": 100.0, "angle": 0, "type": "6318"},
    },
}

VITESSE_ROTATION_TR_MIN = {1: 750, 2: 600, 3: 1000, 4: 750}
POINTS_MESURE = ["moteur_DE", "moteur_NDE", "pompe"]
DIRECTIONS = ["H", "V", "A"]


def frequence_rotation_hz(pompe_id):
    return VITESSE_ROTATION_TR_MIN[pompe_id] / 60.0


def frequences_roulement(n_billes, d_bille, d_primitif, angle_deg, fr_hz):
    angle_rad = math.radians(angle_deg)
    ratio = (d_bille / d_primitif) * math.cos(angle_rad)
    bpfo = (n_billes / 2) * fr_hz * (1 - ratio)
    bpfi = (n_billes / 2) * fr_hz * (1 + ratio)
    bsf = (d_primitif / (2 * d_bille)) * fr_hz * (1 - ratio ** 2)
    ftf = (fr_hz / 2) * (1 - ratio)
    return {"BPFO": round(bpfo, 2), "BPFI": round(bpfi, 2), "BSF": round(bsf, 2), "FTF": round(ftf, 2)}


def toutes_frequences_pompe(pompe_id):
    fr = frequence_rotation_hz(pompe_id)
    out = {"1x": round(fr, 2), "2x": round(fr * 2, 2)}
    for point, carac in FICHE_TECHNIQUE_ROULEMENTS[pompe_id].items():
        out[point] = frequences_roulement(
            carac["n_billes"], carac["d_bille"], carac["d_primitif"], carac["angle"], fr
        )
        out[point]["type_roulement"] = carac["type"]
    return out


# ═══════════════════════════════════════════════════════════════════
# 2) Génération de spectre simulé
# ═══════════════════════════════════════════════════════════════════

def generer_spectre(pompe_id, point, direction, en_defaut=False, type_defaut=None,
                     n_points=800, f_max=100.0, seed=None):
    """Génère un spectre FFT simulé (fréquence Hz, amplitude mm/s)."""
    if seed is not None:
        np.random.seed(seed)
    freqs_carac = toutes_frequences_pompe(pompe_id)
    freq_axis = np.linspace(0.5, f_max, n_points)
    amplitude = np.abs(np.random.normal(0, 0.04, n_points))

    def ajouter_pic(amplitude, f0, hauteur, largeur=0.6):
        return amplitude + hauteur * np.exp(-((freq_axis - f0) ** 2) / (2 * largeur ** 2))

    amplitude = ajouter_pic(amplitude, freqs_carac["1x"], 0.5)
    amplitude = ajouter_pic(amplitude, freqs_carac["2x"], 0.25)

    if en_defaut:
        point_freqs = freqs_carac.get(point, {})
        if type_defaut == "roulement":
            f_defaut = point_freqs.get("BPFO", freqs_carac["1x"] * 3)
            for h in [1, 2, 3]:
                amplitude = ajouter_pic(amplitude, f_defaut * h, 1.8 / h, largeur=0.5)
        elif type_defaut == "alignement":
            amplitude = ajouter_pic(amplitude, freqs_carac["2x"], 2.2, largeur=0.7)
            amplitude = ajouter_pic(amplitude, freqs_carac["1x"], 1.0, largeur=0.6)

    return freq_axis, np.clip(amplitude, 0, None)


# ═══════════════════════════════════════════════════════════════════
# 3) Diagnostic automatique par correspondance spectrale
# ═══════════════════════════════════════════════════════════════════

TOLERANCE_HZ = 1.5
SEUIL_AMPLITUDE_PIC = 0.3


def detecter_pics(freq_axis, amplitude, seuil=SEUIL_AMPLITUDE_PIC):
    pics = []
    for i in range(2, len(amplitude) - 2):
        if amplitude[i] < seuil:
            continue
        if amplitude[i] > amplitude[i - 1] and amplitude[i] > amplitude[i + 1] \
           and amplitude[i] >= amplitude[i - 2] and amplitude[i] >= amplitude[i + 2]:
            pics.append((freq_axis[i], amplitude[i]))
    pics.sort(key=lambda x: -x[1])
    pics_filtres = []
    for f, a in pics:
        if all(abs(f - f2) > TOLERANCE_HZ for f2, _ in pics_filtres):
            pics_filtres.append((f, a))
    return sorted(pics_filtres, key=lambda x: -x[1])[:8]


def diagnostiquer_spectre(freq_axis, amplitude, pompe_id, point):
    freqs_carac = toutes_frequences_pompe(pompe_id)
    point_freqs = freqs_carac.get(point, {})

    reference = {
        "1x (déséquilibre/balourd)": freqs_carac["1x"],
        "2x (désalignement)": freqs_carac["2x"],
        "BPFO (défaut bague extérieure)": point_freqs.get("BPFO"),
        "BPFI (défaut bague intérieure)": point_freqs.get("BPFI"),
        "BSF (défaut élément roulant)": point_freqs.get("BSF"),
        "FTF (défaut de cage)": point_freqs.get("FTF"),
    }

    pics = detecter_pics(freq_axis, amplitude)
    correspondances = []
    for f_pic, a_pic in pics:
        for label, f_ref in reference.items():
            if f_ref is None:
                continue
            for h in [1, 2, 3]:
                if abs(f_pic - f_ref * h) <= TOLERANCE_HZ:
                    correspondances.append({
                        "pic_hz": round(float(f_pic), 1), "amplitude": round(float(a_pic), 2),
                        "type": label, "harmonique": h, "frequence_ref_hz": round(f_ref * h, 1),
                    })
                    break

    roulement_matches = [c for c in correspondances if any(k in c["type"] for k in ["BPFO", "BPFI", "BSF", "FTF"])]
    alignement_matches = [c for c in correspondances if "2x" in c["type"] and c["amplitude"] > 1.2]

    if roulement_matches:
        best = max(roulement_matches, key=lambda c: c["amplitude"])
        diagnostic = f"Défaut de roulement suspecté ({best['type'].split(' ')[0]}) — pic à {best['pic_hz']} Hz, amplitude {best['amplitude']} mm/s"
        gravite = "alerte" if best["amplitude"] > 1.5 else "surveillance"
    elif alignement_matches:
        best = max(alignement_matches, key=lambda c: c["amplitude"])
        diagnostic = f"Défaut d'alignement suspecté — pic marqué à 2x ({best['pic_hz']} Hz), amplitude {best['amplitude']} mm/s"
        gravite = "alerte" if best["amplitude"] > 1.8 else "surveillance"
    elif pics and pics[0][1] > 0.8:
        diagnostic = f"Amplitude globale élevée sans signature de défaut spécifique identifiée (pic principal à {pics[0][0]:.1f} Hz)"
        gravite = "surveillance"
    else:
        diagnostic = "Spectre normal — aucune signature de défaut significative détectée"
        gravite = "normal"

    return {
        "pics": pics, "correspondances": correspondances,
        "diagnostic": diagnostic, "gravite": gravite, "reference": reference,
    }


# ═══════════════════════════════════════════════════════════════════
# 4) Détection d'anomalie sur mesure journalière -> déclenchement 7j
# ═══════════════════════════════════════════════════════════════════

def z_score_vibration_journaliere(daily_df, pompe_id):
    """Calcule le z-score de la DERNIÈRE mesure de vibration journalière
    d'une pompe par rapport à sa propre moyenne/écart-type historique
    (hors anomalies). Retourne (derniere_valeur, z_score, date)."""
    sub = daily_df[daily_df["pompe"] == pompe_id].sort_values("date")
    normal = sub.loc[sub["anomalie"] == 0, "vibration"] if "anomalie" in sub.columns else sub["vibration"]
    m, s = normal.mean(), normal.std()
    derniere = sub.iloc[-1]
    z = (derniere["vibration"] - m) / s if s > 0 else 0.0
    return float(derniere["vibration"]), float(z), derniere["date"]


def necessite_analyse_spectrale(daily_df, pompe_id, seuil_z=3.0):
    """Retourne True si la dernière mesure journalière de vibration
    dépasse le seuil de déclenchement (z-score > seuil_z, par défaut 3)."""
    _, z, _ = z_score_vibration_journaliere(daily_df, pompe_id)
    return z > seuil_z


def historique_7_jours(daily_df, pompe_id):
    """Retourne les 7 derniers jours de mesure de vibration d'une pompe,
    pour le graphique de tendance de l'analyse détaillée."""
    sub = daily_df[daily_df["pompe"] == pompe_id].sort_values("date")
    return sub.iloc[-7:][["date", "vibration", "courant", "debit", "pression"]].reset_index(drop=True)
