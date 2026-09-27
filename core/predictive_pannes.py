# -*- coding: utf-8 -*-
"""
Maintenance prédictive — probabilité de panne par équipement pour la
semaine S, plan de contrôle (top N), et suivi de l'efficacité réelle.

PANNE (définition validée) : un équipement est « en panne » une semaine
s'il reçoit au moins :
  · un avis ZC (avis correctif) qui n'est pas un simple travail annexe
    (échafaudage, peinture, calorifugeage, étalonnage, test…), ou
  · un OT ZCOR SANS avis correspondant à une vraie réparation
    (changement, réparation, remise en état, étanchement de fuite,
    soudure, révision, déblocage…).

ÉQUIPEMENT : poste technique tronqué à 5 niveaux
(SF01-PS-PS04-XXXX-YYYY) — les niveaux plus fins sont regroupés.

CALENDRIER :
  · le plan de la semaine S est calculé avec les données ANTÉRIEURES au
    lundi de S (même s'il est calculé plus tard dans la semaine) puis
    figé dans le registre ;
  · les résultats réels de S sont évalués dès que l'extraction couvre
    toute la semaine S (affichés à partir du lundi S+1).

5 MODÈLES, ré-entraînés chaque semaine sur tout l'historique disponible :
  M1 Historique (référence sans apprentissage : fréquence récente)
  M2 Régression logistique
  M3 Random Forest
  M4 Gradient Boosting
  M5 Ensemble adaptatif : combine M1–M4, pondérés par leur taux de
     détection mesuré les semaines précédentes → s'améliore avec le temps.
"""
import re
import numpy as np
import pandas as pd

MODELES = {
    "M1": "Historique (référence)",
    "M2": "Régression logistique",
    "M3": "Random Forest",
    "M4": "Gradient Boosting",
    "M5": "Ensemble adaptatif",
}
TOP_N = 50
LOOKBACK_MIN = 26          # semaines d'historique minimum avant la 1re semaine d'entraînement
NIVEAU_EQUIPEMENT = 5

_EXCLURE = re.compile(
    r"[ée]chaf|peintur|sablage|calorif|[ée]talonn|\btest\b|nettoy|ouverture et fermeture|"
    r"branchement|d[ée]branchement|pr[ée]paration|massif|confection|consignation|"
    r"inventaire|formation|essai", re.I)
_REPARATION = re.compile(
    r"chang|remplac|r[ée]par|remise en [ée]tat|remettre en [ée]tat|[ée]tanch|fuite|soud|"
    r"r[ée]vis|rebobin|d[ée]blo|d[ée]coin|cass|rupt|d[ée]bouch|bouch|colmat|d[ée]faut|panne|"
    r"gripp|usure|us[ée]e?\b|fissur|perc[ée]|r[ée]fection|rafistol|vibr|[ée]chauff|d[ée]clench|"
    r"arrach|d[ée]form|coinc|bloqu|brul|br[uû]l", re.I)

# Familles de défaillance → contrôle recommandé (plan de contrôle)
FAMILLES = [
    ("Fuite / étanchéité", r"fuite|[ée]tanch|joint|bride|garniture|presse.?[ée]toupe",
     "Contrôle d'étanchéité : joints, brides, garnitures, circuits"),
    ("Roulements / vibrations", r"roulement|palier|vibr|balourd|jeu|alignement|accoupl",
     "Analyse vibratoire et contrôle des paliers / roulements"),
    ("Électrique / moteur", r"moteur|[ée]lectri|c[âa]ble|d[ée]clench|disjonct|variateur|contacteur|bobin",
     "Thermographie et contrôle électrique (moteur, connexions)"),
    ("Transmission / manutention", r"bande|courroie|cha[iî]ne|[ée]l[ée]vateur|godet|rouleau|tambour|r[ée]dler|convoy",
     "Inspection transmission : bande, courroies, chaîne, rouleaux"),
    ("Pompe", r"pompe|ppe\b|aspiration|refoulement|impulseur|turbine",
     "Contrôle pompe : garniture, paliers, pression / débit"),
    ("Structure / usure", r"soud|fissur|corros|perc|t[ôo]le|usure|us[ée]|bavette|chemise|blindage|charpente",
     "Contrôle structure : épaisseur, corrosion, soudures, usure"),
    ("Bouchage / colmatage", r"bouch|colmat|obstru|encrass|filtre|cyclone",
     "Nettoyage / débouchage préventif et contrôle des filtres"),
    ("Instrumentation", r"capteur|sonde|transmetteur|instrument|vanne|r[ée]gul|analyseur|d[ée]bitm",
     "Contrôle instrumentation et vannes (réglage, fonctionnement)"),
]
_FAM_RE = [(n, re.compile(p, re.I), a) for n, p, a in FAMILLES]


# ═══════════════════════════════════════════════════════════════════════════
# 1. Événements
# ═══════════════════════════════════════════════════════════════════════════
NIVEAU_MIN = 4   # en dessous (division, atelier, zone) ce n'est pas un équipement


def cle_equipement(pt):
    s = str(pt).strip()
    if not s or s.lower() == "nan":
        return None
    seg = s.split("-")
    if len(seg) < NIVEAU_MIN:
        return None
    return "-".join(seg[:NIVEAU_EQUIPEMENT])


def lundi(ts):
    ts = pd.Timestamp(ts).normalize()
    return ts - pd.Timedelta(days=ts.weekday())


def extraire_pannes(df_ot, avis):
    """Événements de panne : colonnes [equip, date, source, texte, poste_travail]."""
    out = []
    if avis is not None and not avis.empty and "Type d'avis" in avis.columns:
        a = avis[avis["Type d'avis"].astype(str).str.strip().str.upper() == "ZC"].copy()
        txt = a.get("Description", pd.Series("", index=a.index)).fillna("").astype(str)
        a = a[~txt.str.contains(_EXCLURE)]
        out.append(pd.DataFrame({
            "equip": a["Poste technique"].map(cle_equipement),
            "date": pd.to_datetime(a["Créé le"], errors="coerce"),
            "source": "Avis ZC",
            "texte": a.get("Description", pd.Series("", index=a.index)).fillna("").astype(str),
            "poste_travail": a.get("Poste travail princ.", pd.Series("", index=a.index)),
        }))
    if df_ot is not None and not df_ot.empty and "Type d'ordre" in df_ot.columns:
        o = df_ot[(df_ot["Type d'ordre"].astype(str).str.strip() == "ZCOR") & df_ot["Avis"].isna()].copy()
        txt = o.get("Désignation", pd.Series("", index=o.index)).fillna("").astype(str)
        o = o[txt.str.contains(_REPARATION) & ~txt.str.contains(_EXCLURE)]
        out.append(pd.DataFrame({
            "equip": o["Poste technique"].map(cle_equipement),
            "date": pd.to_datetime(o["Créé le"], errors="coerce"),
            "source": "OT ZCOR",
            "texte": o.get("Désignation", pd.Series("", index=o.index)).fillna("").astype(str),
            "poste_travail": o.get("Poste travail princ.", pd.Series("", index=o.index)),
        }))
    if not out:
        return pd.DataFrame(columns=["equip", "date", "source", "texte", "poste_travail"])
    ev = pd.concat(out, ignore_index=True).dropna(subset=["equip", "date"])
    return ev


def _activite(df_ot, avis):
    """Événements d'activité (préventif, correctif total, avis ZO/ZI)."""
    parts = []
    if df_ot is not None and not df_ot.empty:
        o = df_ot[["Poste technique", "Type d'ordre", "Créé le"]].copy()
        o["equip"] = o["Poste technique"].map(cle_equipement)
        o["date"] = pd.to_datetime(o["Créé le"], errors="coerce")
        o["kind"] = np.where(o["Type d'ordre"].astype(str).str.strip() == "ZPRV", "prev",
                             np.where(o["Type d'ordre"].astype(str).str.strip() == "ZCOR", "cor", None))
        parts.append(o.dropna(subset=["equip", "date", "kind"])[["equip", "date", "kind"]])
    if avis is not None and not avis.empty:
        a = avis[avis["Type d'avis"].astype(str).str.strip().str.upper().isin(["ZO", "ZI"])].copy()
        a["equip"] = a["Poste technique"].map(cle_equipement)
        a["date"] = pd.to_datetime(a["Créé le"], errors="coerce")
        a["kind"] = "insp"
        parts.append(a.dropna(subset=["equip", "date"])[["equip", "date", "kind"]])
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["equip", "date", "kind"])


def infos_equipements(df_ot, avis, ev):
    """Désignation et poste de travail principal par équipement."""
    frames = []
    for d in (df_ot, avis):
        if d is None or d.empty:
            continue
        x = pd.DataFrame({"equip": d["Poste technique"].map(cle_equipement),
                          "pt": d["Poste technique"].astype(str),
                          "desig": d.get("Désignation du poste technique", pd.Series("", index=d.index)),
                          "poste": d.get("Poste travail princ.", pd.Series("", index=d.index))}).dropna(subset=["equip"])
        frames.append(x)
    if not frames:
        return pd.DataFrame(columns=["designation", "poste_travail"])
    x = pd.concat(frames, ignore_index=True)
    exact = x[x["pt"] == x["equip"]]
    desig = exact.dropna(subset=["desig"]).groupby("equip")["desig"].agg(lambda s: s.mode().iat[0] if len(s.mode()) else "")
    desig_any = x.dropna(subset=["desig"]).groupby("equip")["desig"].agg(lambda s: s.mode().iat[0] if len(s.mode()) else "")
    poste = x.dropna(subset=["poste"]).groupby("equip")["poste"].agg(lambda s: s.mode().iat[0] if len(s.mode()) else "")
    info = pd.DataFrame({"designation": desig.reindex(desig_any.index).fillna(desig_any), "poste_travail": poste})
    return info


# ═══════════════════════════════════════════════════════════════════════════
# 2. Matrices hebdomadaires et features
# ═══════════════════════════════════════════════════════════════════════════
class Donnees:
    """Prépare une fois les matrices équipement × semaine."""

    def __init__(self, df_ot, avis):
        self.ev = extraire_pannes(df_ot, avis)
        act = _activite(df_ot, avis)
        dates = pd.concat([self.ev["date"], act["date"]]).dropna()
        self.origine = lundi(dates.min()) if len(dates) else lundi(pd.Timestamp.today())
        self.equips = sorted(set(self.ev["equip"]) | set(act["equip"]))
        self.idx = {e: i for i, e in enumerate(self.equips)}
        self.n_sem = int((lundi(dates.max()) - self.origine).days // 7) + 2 if len(dates) else 1
        E, T = len(self.equips), self.n_sem
        self.panne = np.zeros((E, T), dtype=np.int16)
        for kind in ("prev", "cor", "insp"):
            setattr(self, kind, np.zeros((E, T), dtype=np.int16))
        self._fill(self.panne, self.ev)
        for kind in ("prev", "cor", "insp"):
            self._fill(getattr(self, kind), act[act["kind"] == kind])
        self.panne_bin = (self.panne > 0).astype(np.int8)
        self.info = infos_equipements(df_ot, avis, self.ev)

    def semaine(self, ts):
        return int((lundi(ts) - self.origine).days // 7)

    def date_semaine(self, w):
        return self.origine + pd.Timedelta(weeks=w)

    def _fill(self, M, df):
        if df is None or df.empty:
            return
        w = ((df["date"].dt.normalize() - self.origine).dt.days // 7).astype(int).values
        e = df["equip"].map(self.idx).values
        ok = (w >= 0) & (w < M.shape[1]) & ~pd.isna(e)
        np.add.at(M, (e[ok].astype(int), w[ok]), 1)

    def features(self, W):
        """Features de tous les équipements pour prédire la semaine W (données < W)."""
        P = self.panne_bin[:, :W]
        cs = lambda M, k: M[:, max(0, W - k):W].sum(axis=1)
        f = {}
        for k in (1, 2, 4, 8, 13, 26, 52):
            f[f"pannes_{k}s"] = cs(P, k)
        f["pannes_total"] = P.sum(axis=1)
        any_p = P.any(axis=1)
        last = np.where(any_p, W - 1 - np.argmax(P[:, ::-1], axis=1), -999)
        f["sem_depuis_derniere"] = np.where(any_p, W - last, 104).clip(0, 104)
        n = P.sum(axis=1)
        first = np.where(any_p, np.argmax(P, axis=1), W)
        span = (last - first).clip(min=0)
        f["mtbf_sem"] = np.where(n >= 2, span / np.maximum(n - 1, 1), 104).clip(0, 104)
        f["ratio_mtbf"] = (f["sem_depuis_derniere"] / np.maximum(f["mtbf_sem"], 1)).clip(0, 20)
        for kind, lab in (("prev", "preventif"), ("cor", "correctif"), ("insp", "inspection")):
            M = getattr(self, kind)[:, :W]
            f[f"{lab}_4s"] = cs(M, 4)
            f[f"{lab}_13s"] = cs(M, 13)
        f["sf02"] = np.array([1 if str(e).startswith("SF02") else 0 for e in self.equips])
        X = pd.DataFrame(f, index=self.equips)
        univers = (cs(P, 52) > 0) | (cs(self.cor[:, :W], 13) > 0) | (cs(self.insp[:, :W], 13) > 0)
        return X, univers

    def cible(self, W):
        return self.panne_bin[:, W] if W < self.n_sem else np.zeros(len(self.equips), dtype=np.int8)


# ═══════════════════════════════════════════════════════════════════════════
# 3. Les 5 modèles
# ═══════════════════════════════════════════════════════════════════════════
def _score_historique(X):
    return (3 * X["pannes_4s"] + 2 * X["pannes_13s"] / 3 + X["pannes_52s"] / 13
            + 1.0 / (1 + X["sem_depuis_derniere"])).values


def _jeu_entrainement(D, W, max_sem=60):
    Xs, ys = [], []
    for w in range(max(LOOKBACK_MIN, W - max_sem), W):
        X, u = D.features(w)
        y = D.cible(w)
        Xs.append(X[u]); ys.append(y[u])
    if not Xs:
        return None, None
    return pd.concat(Xs), np.concatenate(ys)


def entrainer_et_predire(D, W, poids_ensemble=None, rapide=False):
    """
    Entraîne M1–M4 sur les semaines < W et prédit la semaine W.
    Retourne (scores: {modele: Series proba indexée par équipement}, info).
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier

    Xtr, ytr = _jeu_entrainement(D, W, max_sem=40 if rapide else 60)
    Xp, u = D.features(W)
    Xp = Xp[u]
    scores = {}
    if Xtr is None or ytr.sum() < 5:
        s = pd.Series(_score_historique(Xp), index=Xp.index)
        s = s / (s.max() or 1) * 0.5
        return {m: s for m in MODELES}, {"n_train": 0, "pos_train": 0}

    # M1 : score historique calibré (1 variable)
    lr1 = LogisticRegression(max_iter=500)
    lr1.fit(_score_historique(Xtr).reshape(-1, 1), ytr)
    scores["M1"] = pd.Series(lr1.predict_proba(_score_historique(Xp).reshape(-1, 1))[:, 1], index=Xp.index)
    # M2 : régression logistique
    m2 = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=0.5))
    m2.fit(Xtr, ytr)
    scores["M2"] = pd.Series(m2.predict_proba(Xp)[:, 1], index=Xp.index)
    # M3 : random forest
    m3 = RandomForestClassifier(n_estimators=80 if rapide else 200, min_samples_leaf=20, max_features="sqrt",
                                n_jobs=-1, random_state=42)
    m3.fit(Xtr, ytr)
    scores["M3"] = pd.Series(m3.predict_proba(Xp)[:, 1], index=Xp.index)
    # M4 : gradient boosting
    m4 = HistGradientBoostingClassifier(max_iter=120 if rapide else 250, learning_rate=0.05,
                                        min_samples_leaf=40, l2_regularization=1.0, random_state=42)
    m4.fit(Xtr, ytr)
    scores["M4"] = pd.Series(m4.predict_proba(Xp)[:, 1], index=Xp.index)
    # M5 : ensemble adaptatif
    scores["M5"] = ensemble(scores, poids_ensemble)
    return scores, {"n_train": int(len(ytr)), "pos_train": int(ytr.sum())}


def poids_depuis_historique(evaluations, fenetre=8, temperature=0.015):
    """
    Poids de M1–M4 pour l'ensemble M5 : chaque modèle est noté sur ses
    semaines évaluées récentes (moyenne précision + détection) ; les poids
    suivent exp(écart au meilleur / température). Un modèle 3 points
    derrière le meilleur pèse ~8× moins. Poids égaux sans historique.
    """
    base = {m: 1.0 for m in ("M1", "M2", "M3", "M4")}
    if not evaluations:
        return base
    recents = evaluations[-fenetre:]
    notes = {}
    for m in base:
        vals = [(e["modeles"][m]["precision"] + e["modeles"][m]["detection"]) / 2
                for e in recents if m in e.get("modeles", {})]
        notes[m] = float(np.mean(vals)) if vals else 0.0
    best = max(notes.values())
    out = {m: float(np.exp((notes[m] - best) / temperature)) for m in base}
    s = sum(out.values())
    return {m: v / s * 4 for m, v in out.items()}


def ensemble(scores, poids=None):
    poids = poids or {m: 1.0 for m in ("M1", "M2", "M3", "M4")}
    tot = sum(poids.values())
    idx = scores["M1"].index
    return sum(scores[m].reindex(idx) * poids[m] for m in ("M1", "M2", "M3", "M4")) / tot


# ═══════════════════════════════════════════════════════════════════════════
# 4. Évaluation d'une semaine
# ═══════════════════════════════════════════════════════════════════════════
def evaluer(scores_top, pannes_reelles, top_n=TOP_N):
    """
    scores_top : {modele: {equip: proba}} (classement complet ou top) ;
    pannes_reelles : ensemble des équipements en panne dans la semaine.
    """
    res = {}
    n_reel = len(pannes_reelles)
    for m, sc in scores_top.items():
        top = [e for e, _ in sorted(sc.items(), key=lambda x: -x[1])[:top_n]]
        hits = len(set(top) & pannes_reelles)
        res[m] = {"detection": round(hits / n_reel, 4) if n_reel else 0.0,
                  "precision": round(hits / top_n, 4),
                  "detectees": hits, "pannes_reelles": n_reel,
                  "prevues": round(float(sum(sc.values())), 1)}
    return res


def pannes_semaine(D, W, equips_filtre=None):
    y = D.cible(W)
    s = {e for e, v in zip(D.equips, y) if v}
    if equips_filtre is not None:
        s &= set(equips_filtre)
    return s


def retro_test(D, W_fin, n_semaines=12, top_n=TOP_N, progress=None):
    """
    Rejoue les n dernières semaines complètes (< W_fin) comme si chaque
    prédiction avait été faite le lundi : montre l'évolution des 5 modèles,
    y compris l'apprentissage des poids de M5.
    """
    evals = []
    debut = max(LOOKBACK_MIN + 4, W_fin - n_semaines)
    for k, W in enumerate(range(debut, W_fin)):
        if progress:
            progress(k, W_fin - debut)
        poids = poids_depuis_historique(evals)
        scores, _ = entrainer_et_predire(D, W, poids, rapide=True)
        top = {m: s.sort_values(ascending=False).head(300).round(4).to_dict() for m, s in scores.items()}
        reel = pannes_semaine(D, W)
        ev = {"semaine": semaine_label(D.date_semaine(W)), "debut": str(D.date_semaine(W).date()),
              "modeles": evaluer(top, reel, top_n), "poids_M5": {m: round(v, 3) for m, v in poids.items()},
              "type": "rétro-test"}
        evals.append(ev)
    return evals


def semaine_label(ts):
    ts = pd.Timestamp(ts)
    iso = ts.isocalendar()
    return f"{iso.year}-S{iso.week:02d}"


# ═══════════════════════════════════════════════════════════════════════════
# 5. Plan de contrôle
# ═══════════════════════════════════════════════════════════════════════════
def famille_et_controle(textes):
    comptes = {}
    for t in textes:
        for nom, rx, action in _FAM_RE:
            if rx.search(str(t)):
                comptes[nom] = comptes.get(nom, 0) + 1
    if not comptes:
        return "Non classé", "Inspection visuelle générale de l'équipement", ""
    top = sorted(comptes.items(), key=lambda x: -x[1])
    nom = top[0][0]
    action = next(a for n, _, a in _FAM_RE if n == nom)
    motif = ", ".join(f"{n.lower()} ({c})" for n, c in top[:2])
    return nom, action, motif


def plan_controle(D, scores_m5, W, postes=None, top_n=TOP_N):
    """Top N équipements de la semaine W avec contrôle recommandé."""
    s = pd.Series(scores_m5)
    info = D.info
    if postes is not None:
        ok = [e for e in s.index if str(info["poste_travail"].get(e, "")) in set(postes)]
        s = s.reindex(ok)
    s = s.dropna().sort_values(ascending=False).head(top_n)
    X, _ = D.features(W)
    debut = D.date_semaine(W)
    ev = D.ev[(D.ev["date"] < debut) & (D.ev["date"] >= debut - pd.Timedelta(weeks=52))]
    lignes = []
    for rang, (e, p) in enumerate(s.items(), 1):
        hist = ev[ev["equip"] == e]
        fam, action, motif = famille_et_controle(hist["texte"].tolist())
        derniere = hist["date"].max()
        niveau = "Très élevé" if p >= 0.5 else ("Élevé" if p >= 0.3 else ("Moyen" if p >= 0.15 else "Modéré"))
        lignes.append({
            "Rang": rang, "Équipement": e,
            "Désignation": str(info["designation"].get(e, "") or ""),
            "Poste de travail": str(info["poste_travail"].get(e, "") or ""),
            "Probabilité de panne": round(float(p) * 100, 1), "Risque": niveau,
            "Pannes (13 sem.)": int(X.loc[e, "pannes_13s"]) if e in X.index else 0,
            "Pannes (52 sem.)": int(X.loc[e, "pannes_52s"]) if e in X.index else 0,
            "Dernière panne": derniere.strftime("%d/%m/%Y") if pd.notna(derniere) else "—",
            "Défaillance dominante": fam, "Contrôle recommandé": action, "Historique 52 sem. (interventions)": motif,
        })
    return pd.DataFrame(lignes)


# ═══════════════════════════════════════════════════════════════════════════
# 6. Registre hebdomadaire (plan figé le lundi, résultats réels à S+1)
# ═══════════════════════════════════════════════════════════════════════════
import json, os

CHEMIN_REGISTRE = "predictif/registre_predictions.json"


def charger_registre():
    """GitHub si configuré (source de vérité), sinon fichier local."""
    try:
        from core.github_publish import download_file, is_configured
        if is_configured():
            contenu, err = download_file(CHEMIN_REGISTRE)
            if contenu:
                return json.loads(contenu.decode("utf-8")), "GitHub"
    except Exception:
        pass
    if os.path.exists(CHEMIN_REGISTRE):
        try:
            with open(CHEMIN_REGISTRE, encoding="utf-8") as f:
                return json.load(f), "local"
        except Exception:
            pass
    return {"version": 1, "predictions": {}, "evaluations": {}, "retro_test": []}, "nouveau"


def sauver_registre(reg):
    data = json.dumps(reg, ensure_ascii=False, indent=1, default=float).encode("utf-8")
    msg = []
    try:
        os.makedirs(os.path.dirname(CHEMIN_REGISTRE), exist_ok=True)
        with open(CHEMIN_REGISTRE, "wb") as f:
            f.write(data)
        msg.append("local OK")
    except Exception as e:
        msg.append(f"local : {e}")
    try:
        from core.github_publish import upload_file, is_configured
        if is_configured():
            ok, m = upload_file(CHEMIN_REGISTRE, data, "Registre maintenance prédictive")
            msg.append("GitHub OK" if ok else f"GitHub : {m}")
    except Exception as e:
        msg.append(f"GitHub : {e}")
    return " · ".join(msg)


def _evals_chrono(reg):
    live = sorted(reg.get("evaluations", {}).values(), key=lambda e: e["debut"])
    retro = [e for e in reg.get("retro_test", []) if not live or e["debut"] < live[0]["debut"]]
    return retro + live


def executer_cycle(df_ot, avis, aujourd_hui, date_extraction, reg, n_retro=12):
    """
    Cycle complet, idempotent :
      1. plan de la semaine S (semaine d'aujourd'hui) : calculé une seule
         fois avec les données < lundi S, puis figé dans le registre ;
      2. évaluation de toute semaine prédite qui est terminée ET couverte
         par l'extraction (résultats affichés à partir du lundi S+1) ;
      3. rétro-test des dernières semaines (une fois par extraction).
    Retourne (resultat, registre_modifie).
    """
    D = Donnees(df_ot, avis)
    aujourd_hui = pd.Timestamp(aujourd_hui).normalize()
    date_extraction = pd.Timestamp(date_extraction).normalize()
    lundi_S = lundi(aujourd_hui)
    W_S = D.semaine(lundi_S)
    cle_S = semaine_label(lundi_S)
    modifie = False

    # 3. rétro-test (avant tout : il alimente les poids de M5)
    if reg.get("retro_extraction") != str(date_extraction.date()) or not reg.get("retro_test"):
        W_fin = min(W_S, D.semaine(date_extraction))   # semaines complètes seulement
        reg["retro_test"] = retro_test(D, W_fin, n_semaines=n_retro)
        reg["retro_extraction"] = str(date_extraction.date())
        modifie = True

    # 1. plan de la semaine S, figé
    if cle_S not in reg["predictions"]:
        poids = poids_depuis_historique(_evals_chrono(reg))
        scores, info = entrainer_et_predire(D, W_S, poids)
        reg["predictions"][cle_S] = {
            "debut": str(lundi_S.date()),
            "genere_le": str(pd.Timestamp.now().round("s")),
            "donnees_jusqu_au": str(date_extraction.date()),
            "poids_M5": {m: round(v, 3) for m, v in poids.items()},
            "pannes_prevues": round(float(scores["M5"].sum()), 1),
            "univers": int(len(scores["M5"])),
            "entrainement": info,
            "scores": {m: (s.round(4).to_dict() if m == "M5" else
                           s.sort_values(ascending=False).head(300).round(4).to_dict())
                       for m, s in scores.items()},
        }
        modifie = True

    # 2. évaluations réelles des semaines terminées et couvertes
    for cle, pred in reg["predictions"].items():
        if cle in reg["evaluations"]:
            continue
        debut = pd.Timestamp(pred["debut"])
        fin = debut + pd.Timedelta(days=6)
        if aujourd_hui >= debut + pd.Timedelta(days=7) and date_extraction >= fin:
            W = D.semaine(debut)
            reel = pannes_semaine(D, W)
            reg["evaluations"][cle] = {
                "semaine": cle, "debut": pred["debut"], "type": "réel",
                "modeles": evaluer(pred["scores"], reel),
                "pannes_reelles_liste": sorted(reel),
            }
            modifie = True

    return {"D": D, "W_S": W_S, "cle_S": cle_S, "lundi_S": lundi_S,
            "evolution": _evals_chrono(reg)}, modifie
