# -*- coding: utf-8 -*-
"""
Maintenance prédictive — probabilité de panne par équipement pour la
semaine S, plan de contrôle (top N), et suivi de l'efficacité réelle.

PANNE (définition validée) : un poste technique est « en panne » une semaine
s'il reçoit un avis ZC ou un OT ZCOR sans avis décrivant un problème
MÉCANIQUE, ÉLECTRIQUE ou d'INSTRUMENTATION : roulements, alignement,
accouplement, courroies / transmission, machines tournantes, moteur et
alimentation, capteurs, étalonnage, vannes, remise en état…
Sont exclus : les fuites et travaux d'étanchéité, la chaudronnerie /
tuyauterie / génie civil, le bouchage, et les travaux annexes
(échafaudage, peinture, calorifugeage, nettoyage…).

POSTE TECHNIQUE EXACT : la prédiction est faite sur le poste technique tel
qu'il est saisi dans SAP (4 à 7 niveaux, ex. SF01-PE-00LN-REACTI-0HB137-GMOT).
Les niveaux trop hauts (division, atelier, zone : < 4 niveaux) sont exclus.
Le poste technique parent (un niveau au-dessus) sert de variable : un moteur
dont l'équipement porteur tombe souvent en panne est plus à risque.

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
NIVEAU_EQUIPEMENT = 5      # ancien mode (registres antérieurs)
MODE_CLE = "pt_exact_meca_elec_instr"   # clé (poste technique exact) + définition de la panne

# Classement des pannes par famille (méca / élec / instrumentation)
_I = re.I
# 1. Travaux annexes (jamais une panne)
_ANNEXE = re.compile(
    r"[ée]cha?f+au|peintur|sablage|calorif|nettoy|massif|confection|consignation|inventaire|formation|"
    r"essai|\btest\b|ouverture et fermeture|branchement|pr[ée]paration|g[ée]nie civil|ma[çc]onn|b[ée]ton|"
    r"am[ée]nagement|manutention|d[ée]placement|installation (?:d'?un )?nouve|achèvement|achevement", _I)
# 2. Fuites / étanchéité (exclues à la demande)
_FUITE = re.compile(r"fuite|fuit\b|[ée]tanch|\bjoints?\b|\bj\.?p\b|\bbrides?\b|garniture|presse.?[ée]toupe|"
                   r"suintement|goutte", _I)
# 2 bis. Chaudronnerie (soudure, tôle…) : exclue même sur une machine
_CHAUDRON = re.compile(r"\bsoud|fissur|corros|\bt[ôo]le|perc[ée]|d[ée]coup|rechargement", _I)
# 3. Hors périmètre méca / élec / instrumentation (chaudronnerie, tuyauterie, génie civil, process)
_HORS = re.compile(
    r"d[ée]bouch|bouch|colmat|obstru|encrass|\bsoud|fissur|corros|\bt[ôo]le|perc[ée]|chemis|blindage|"
    r"charpente|caillebotis|garde.?corps|toiture|escalier|passerelle|bardage|chamotte|r[ée]fractaire|"
    r"tuyaut|conduite|circuit|manchette|compensateur|flexible|filtre|grille|porte|trappe|[ée]clairage|"
    r"climatis|sanitaire|plomberie|bac\b|cuve|tr[ée]mie|goulotte|virole|chambre", _I)
_TAG = r"\b[PTFLAHZSDKWXU][ISTCVEYQAHLDZ]{1,4}\s?-?\d{3,5}[A-Z]?\b"
_INSTR_RE = re.compile(
    r"[ée]talonn|calibr|capteur|sonde|transmetteur|thermocouple|thermom|manom[èe]tre|pressostat|thermostat|"
    r"d[ée]bitm|analyseur|ph.?m[èe]tre|conductivim|positionneur|fin de course|d[ée]tecteur|instrument|"
    r"[ée]lectrovanne|servomoteur|r[ée]gulat|alarme|boucle|signal|4.?20|radar|jauge|contr[ôo]leur de|"
    r"(?:indicateur|transmetteur|contr[ôo]le|mesure) de niveau|niveau radar|" + _TAG, _I)
_VANNE = re.compile(r"vanne|robinet|clapet", _I)
_MECA_ROT = re.compile(r"roulement|palier|vibr|balourd|alignement|align|accoupl|\barbre|clavette|\bjeu\b|bruit", _I)
_MECA_TR = re.compile(r"courroie|cha[iî]ne|\bbande\b|rouleau|tambour|r[ée]ducteur|engrenage|poulie|pignon|godet|"
                     r"[ée]l[ée]vateur|r[ée]dler|convoy|transmission|motor[ée]ducteur|moyeu|tendeur|racleur|galet", _I)
_MECA_MT = re.compile(r"pompe|\bppe\b|ventilat|compresseur|agitat|broyeur|crible|turbine|soufflante|malaxeur|"
                     r"doseur|dosom|\bvis\b|extracteur|surpresseur|impulseur|\broue\b|v[ée]rin|hydraul|lubrif|"
                     r"frein|embrayage|ressort|\baxe\b|bague|came", _I)
_ELEC_RE = re.compile(r"moteur|[ée]lectri|c[âa]ble|d[ée]clench|disjonct|variateur|contacteur|bobin|alimentation|"
                  r"armoire|coffret|relais|fusible|court.?circuit|isolement|d[ée]marreur|onduleur|\bmt\b|\bbt\b", _I)
_REPAR = re.compile(r"chang|remplac|r[ée]par|remise en [ée]tat|remettre en [ée]tat|r[ée]vis|rebobin|d[ée]blo|"
                   r"d[ée]coin|cass|rupt|d[ée]faut|panne|gripp|usure|us[ée]e?\b|coinc|bloqu|arrach|d[ée]form|"
                   r"r[ée]fection|contr[ôo]le|v[ée]rif|r[ée]glage|serrage|resserr|remontage|d[ée]montage|entretien", _I)
_PT_ELEC = re.compile(r"-(GMOT|MOTEUR|MOT\w*|ELEC\w*|ARMOIR\w*)(-|$)", _I)
_PT_MECA = re.compile(r"-(REDUCT\w*|ACCOUP\w*|PALIER\w*|TRANSM\w*|GENT)(-|$)", _I)
_PT_INSTR = re.compile(r"-(CSUR|INSTR\w*|ACCINSTR)(-|$)|-[PTFLAHZSDKWXU][ISTCVEYQAHLDZ]{1,4}\d{3,5}[A-Z]?$", _I)

CONTROLES = {
    "Instrumentation": "Étalonnage et contrôle fonctionnel : capteur, boucle, signal, vanne automatique",
    "Roulements / alignement": "Analyse vibratoire, contrôle roulements, alignement et accouplement",
    "Transmission": "Inspection transmission : courroies, chaîne, bande, rouleaux, réducteur",
    "Machine tournante": "Contrôle machine tournante : paliers, jeu, lubrification, performance",
    "Électrique / moteur": "Thermographie, mesure d'isolement et contrôle des connexions moteur",
    "Vannes / robinetterie": "Contrôle manœuvre et étanchéité interne des vannes, clapets",
}

def classer_panne(texte, pt="", atelier=None):
    """Famille de défaillance méca / élec / instrumentation, ou None (hors périmètre).
    atelier « E » (électrique) ou « R » (régulation) : une remise en état générique
    faite par cet atelier est classée électrique / instrumentation."""
    t = str(texte or ""); p = str(pt or "")
    if not t or t.lower() == "nan" or _ANNEXE.search(t) or _FUITE.search(t) or _CHAUDRON.search(t):
        return None
    if _MECA_ROT.search(t): return "Roulements / alignement"
    if _MECA_TR.search(t): return "Transmission"
    if _ELEC_RE.search(t): return "Électrique / moteur"
    if _INSTR_RE.search(t): return "Instrumentation"
    if _VANNE.search(t): return "Vannes / robinetterie"
    if _MECA_MT.search(t): return "Machine tournante"
    if _HORS.search(t): return None
    if _REPAR.search(t):
        if _PT_ELEC.search(p): return "Électrique / moteur"
        if _PT_MECA.search(p): return "Transmission"
        if _PT_INSTR.search(p): return "Instrumentation"
        if atelier == "E": return "Électrique / moteur"
        if atelier == "R": return "Instrumentation"
    return None


# Périmètres de prédiction (chacun a ses modèles, son plan et son registre)
PERIMETRES = {
    "meca": {"label": "Mécanique (SF1-M, SF2-M)", "court": "Mécanique", "fichier": "Meca",
             "prefixes": ("SF1-M", "SF2-M"),
             "registre": "predictif/registre_predictions_meca.json"},
    "elec_regul": {"label": "Électrique & Régulation (SF1-E, SF1-R, SF2-E, SF2-R)",
                   "court": "Électrique & Régulation", "fichier": "Elec_Regul",
                   "prefixes": ("SF1-E", "SF1-R", "SF2-E", "SF2-R"),
                   "registre": "predictif/registre_predictions_elec_regul.json"},
    # ancien périmètre global (tous ateliers) — conservé, non affiché
    "general": {"label": "Toute la maintenance", "court": "", "fichier": "", "prefixes": None,
                "registre": "predictif/registre_predictions.json", "masque": True},
}


def _atelier(poste):
    """« E » ou « R » pour SF1-EPP1, SF2-RMCP… sinon None."""
    s = str(poste or "").strip().upper()
    return s[4] if len(s) > 4 and s[:4] in ("SF1-", "SF2-") and s[4] in "ER" else None


def filtrer_perimetre(df, perimetre):
    """Ne garde que les lignes dont le poste de travail commence par un préfixe du périmètre."""
    pref = PERIMETRES.get(perimetre, {}).get("prefixes")
    if df is None or df.empty or not pref or "Poste travail princ." not in df.columns:
        return df
    return df[df["Poste travail princ."].astype(str).str.strip().str.upper().str.startswith(pref)]


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
    return s


def cle_ancienne(pt):
    """Clé de l'ancien mode (poste technique tronqué à 5 niveaux)."""
    s = str(pt).strip()
    return "-".join(s.split("-")[:NIVEAU_EQUIPEMENT])


def cle_parent(e):
    """Poste technique parent (un niveau au-dessus, jamais au-dessus du niveau 4)."""
    seg = str(e).split("-")
    return "-".join(seg[:max(NIVEAU_MIN, len(seg) - 1)])


def lundi(ts):
    ts = pd.Timestamp(ts).normalize()
    return ts - pd.Timedelta(days=ts.weekday())


def extraire_pannes(df_ot, avis, avec_atelier=False):
    """Pannes méca / élec / instrumentation : [famille, equip, date, source, texte, poste_travail].
    avec_atelier (périmètre Électrique & Régulation) : tous les OT ZCOR de l'atelier comptent,
    avec ou sans avis (l'avis est souvent saisi par un autre atelier) ; les avis ZC déjà
    rattachés à un de ces OT ne sont pas comptés deux fois."""
    out = []
    deja = set()
    if avec_atelier and df_ot is not None and not df_ot.empty and "Avis" in df_ot.columns:
        z = df_ot[df_ot["Type d'ordre"].astype(str).str.strip() == "ZCOR"]
        deja = set(z["Avis"].dropna().astype("int64").astype(str)) if len(z) else set()
    if avis is not None and not avis.empty and "Type d'avis" in avis.columns:
        a = avis[avis["Type d'avis"].astype(str).str.strip().str.upper() == "ZC"].copy()
        if deja and "Avis" in a.columns:
            a = a[~a["Avis"].astype(str).str.replace(r"\.0$", "", regex=True).isin(deja)]
        txt = a.get("Description", pd.Series("", index=a.index)).fillna("").astype(str)
        pt_a = a.get("Poste travail princ.", pd.Series("", index=a.index))
        a["famille"] = [classer_panne(t, p, _atelier(w) if avec_atelier else None) for t, p, w in zip(txt, a["Poste technique"], pt_a)]
        a = a[a["famille"].notna()]
        out.append(pd.DataFrame({
            "famille": a["famille"],
            "equip": a["Poste technique"].map(cle_equipement),
            "date": pd.to_datetime(a["Créé le"], errors="coerce"),
            "source": "Avis ZC",
            "texte": a.get("Description", pd.Series("", index=a.index)).fillna("").astype(str),
            "poste_travail": a.get("Poste travail princ.", pd.Series("", index=a.index)),
        }))
    if df_ot is not None and not df_ot.empty and "Type d'ordre" in df_ot.columns:
        zcor = df_ot["Type d'ordre"].astype(str).str.strip() == "ZCOR"
        o = df_ot[zcor if avec_atelier else (zcor & df_ot["Avis"].isna())].copy()
        txt = o.get("Désignation", pd.Series("", index=o.index)).fillna("").astype(str)
        pt_o = o.get("Poste travail princ.", pd.Series("", index=o.index))
        o["famille"] = [classer_panne(t, p, _atelier(w) if avec_atelier else None) for t, p, w in zip(txt, o["Poste technique"], pt_o)]
        o = o[o["famille"].notna()]
        out.append(pd.DataFrame({
            "famille": o["famille"],
            "equip": o["Poste technique"].map(cle_equipement),
            "date": pd.to_datetime(o["Créé le"], errors="coerce"),
            "source": "OT ZCOR",
            "texte": o.get("Désignation", pd.Series("", index=o.index)).fillna("").astype(str),
            "poste_travail": o.get("Poste travail princ.", pd.Series("", index=o.index)),
        }))
    if not out:
        return pd.DataFrame(columns=["famille", "equip", "date", "source", "texte", "poste_travail"])
    ev = pd.concat(out, ignore_index=True).dropna(subset=["equip", "date"])
    return ev


def _activite(df_ot, avis, prev_types=("ZPRV",), insp_types=("ZO", "ZI")):
    """Événements d'activité (préventif, correctif total, avis d'inspection)."""
    parts = []
    if df_ot is not None and not df_ot.empty:
        o = df_ot[["Poste technique", "Type d'ordre", "Créé le"]].copy()
        o["equip"] = o["Poste technique"].map(cle_equipement)
        o["date"] = pd.to_datetime(o["Créé le"], errors="coerce")
        o["kind"] = np.where(o["Type d'ordre"].astype(str).str.strip().isin(prev_types), "prev",
                             np.where(o["Type d'ordre"].astype(str).str.strip() == "ZCOR", "cor", None))
        parts.append(o.dropna(subset=["equip", "date", "kind"])[["equip", "date", "kind"]])
    if avis is not None and not avis.empty:
        a = avis[avis["Type d'avis"].astype(str).str.strip().str.upper().isin(list(insp_types))].copy()
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

    def __init__(self, df_ot, avis, perimetre="general"):
        self.perimetre = perimetre
        if PERIMETRES.get(perimetre, {}).get("prefixes"):
            df_ot, avis = filtrer_perimetre(df_ot, perimetre), filtrer_perimetre(avis, perimetre)
            act = _activite(df_ot, avis, prev_types=("ZPRV", "ZREV"), insp_types=("ZO", "ZI", "ZP", "ZR"))
        else:
            act = _activite(df_ot, avis)
        self.ev = extraire_pannes(df_ot, avis, avec_atelier=bool(PERIMETRES.get(perimetre, {}).get("prefixes")))
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
        parents = [cle_parent(e) for e in self.equips]
        p_idx = {p: i for i, p in enumerate(sorted(set(parents)))}
        self.parent_idx = np.array([p_idx[p] for p in parents], dtype=int)
        self.n_parents = len(p_idx)
        self.niveau = np.array([str(e).count("-") + 1 for e in self.equips])
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
        for k in (13, 52):   # pannes du poste technique parent (et de ses sous-postes)
            par = np.bincount(self.parent_idx, weights=f[f"pannes_{k}s"], minlength=self.n_parents)
            f[f"parent_pannes_{k}s"] = par[self.parent_idx] - f[f"pannes_{k}s"]
        f["niveau_pt"] = self.niveau
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
def famille_et_controle(familles):
    """Défaillance dominante sur 52 semaines → contrôle recommandé."""
    comptes = pd.Series([f for f in familles if f], dtype=object).value_counts()
    if comptes.empty:
        return "Non classé", "Inspection mécanique, électrique et instrumentation de l'équipement", ""
    nom = comptes.index[0]
    motif = ", ".join(f"{n.lower()} ({c})" for n, c in comptes.head(2).items())
    return nom, CONTROLES.get(nom, ""), motif


def familles_dominantes(D, W):
    """Défaillance dominante (52 semaines avant W) de chaque poste technique."""
    debut = D.date_semaine(W)
    ev = D.ev[(D.ev["date"] < debut) & (D.ev["date"] >= debut - pd.Timedelta(weeks=52))]
    if ev.empty:
        return pd.Series(dtype=object)
    return ev.groupby("equip")["famille"].agg(lambda x: x.value_counts().index[0])


def plan_controle(D, scores_m5, W, postes=None, top_n=TOP_N, familles=None):
    """Top N postes techniques de la semaine W avec contrôle recommandé.
    familles : restreint le plan aux défaillances dominantes choisies."""
    s = pd.Series(scores_m5)
    info = D.info
    if postes is not None:
        ok = [e for e in s.index if str(info["poste_travail"].get(e, "")) in set(postes)]
        s = s.reindex(ok)
    if familles:
        dom = familles_dominantes(D, W)
        s = s.reindex([e for e in s.index if dom.get(e) in set(familles)])
    s = s.dropna().sort_values(ascending=False).head(top_n)
    X, _ = D.features(W)
    debut = D.date_semaine(W)
    ev = D.ev[(D.ev["date"] < debut) & (D.ev["date"] >= debut - pd.Timedelta(weeks=52))]
    lignes = []
    for rang, (e, p) in enumerate(s.items(), 1):
        hist = ev[ev["equip"] == e]
        fam, action, motif = famille_et_controle(hist["famille"].tolist())
        derniere = hist["date"].max()
        niveau = "Très élevé" if p >= 0.5 else ("Élevé" if p >= 0.3 else ("Moyen" if p >= 0.15 else "Modéré"))
        lignes.append({
            "Rang": rang, "Poste technique": e,
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


def _chemin(perimetre):
    return PERIMETRES.get(perimetre, PERIMETRES["general"])["registre"]


def charger_registre(perimetre="general"):
    """GitHub si configuré (source de vérité), sinon fichier local."""
    CHEMIN_REGISTRE = _chemin(perimetre)
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


def sauver_registre(reg, perimetre="general"):
    CHEMIN_REGISTRE = _chemin(perimetre)
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
            ok, m = upload_file(CHEMIN_REGISTRE, data, f"Registre maintenance prédictive ({perimetre})")
            msg.append("GitHub OK" if ok else f"GitHub : {m}")
    except Exception as e:
        msg.append(f"GitHub : {e}")
    return " · ".join(msg)


def _evals_chrono(reg):
    live = sorted(reg.get("evaluations", {}).values(), key=lambda e: e["debut"])
    retro = [e for e in reg.get("retro_test", []) if not live or e["debut"] < live[0]["debut"]]
    return retro + live


def executer_cycle(df_ot, avis, aujourd_hui, date_extraction, reg, n_retro=12, perimetre="general"):
    """
    Cycle complet, idempotent :
      1. plan de la semaine S (semaine d'aujourd'hui) : calculé une seule
         fois avec les données < lundi S, puis figé dans le registre ;
      2. évaluation de toute semaine prédite qui est terminée ET couverte
         par l'extraction (résultats affichés à partir du lundi S+1) ;
      3. rétro-test des dernières semaines (une fois par extraction).
    Retourne (resultat, registre_modifie).
    """
    D = Donnees(df_ot, avis, perimetre)
    aujourd_hui = pd.Timestamp(aujourd_hui).normalize()
    date_extraction = pd.Timestamp(date_extraction).normalize()
    lundi_S = lundi(aujourd_hui)
    W_S = D.semaine(lundi_S)
    cle_S = semaine_label(lundi_S)
    modifie = False

    # 3. rétro-test (avant tout : il alimente les poids de M5)
    if (reg.get("retro_extraction") != str(date_extraction.date()) or not reg.get("retro_test")
            or reg.get("retro_mode") != MODE_CLE):
        # semaines complètes seulement (une extraction du dimanche couvre sa semaine)
        W_fin = min(W_S, D.semaine(date_extraction + pd.Timedelta(days=1)))
        reg["retro_test"] = retro_test(D, W_fin, n_semaines=n_retro)
        reg["retro_extraction"] = str(date_extraction.date())
        reg["retro_mode"] = MODE_CLE
        modifie = True

    # 1. plan de la semaine S, figé (recalculé une seule fois s'il avait été
    #    fait avec l'ancien mode « équipement 5 niveaux » et n'est pas évalué)
    ancien = reg["predictions"].get(cle_S)
    a_refaire = ancien is not None and ancien.get("mode_cle") != MODE_CLE and cle_S not in reg["evaluations"]
    if ancien is None or a_refaire:
        poids = poids_depuis_historique(_evals_chrono(reg))
        scores, info = entrainer_et_predire(D, W_S, poids)
        reg["predictions"][cle_S] = {
            "debut": str(lundi_S.date()),
            "genere_le": str(pd.Timestamp.now().round("s")),
            "donnees_jusqu_au": str(date_extraction.date()),
            "mode_cle": MODE_CLE,
            "recalcule": bool(a_refaire),
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
            if pred.get("mode_cle") is None:          # plan de l'ancien mode (5 niveaux)
                reel = {cle_ancienne(e) for e in reel}
            reg["evaluations"][cle] = {
                "semaine": cle, "debut": pred["debut"], "type": "réel",
                "modeles": evaluer(pred["scores"], reel),
                "pannes_reelles_liste": sorted(reel),
            }
            modifie = True

    # 4. journal d'efficacité : enregistré au début de la semaine S
    if enregistrer_efficacite(reg, cle_S, lundi_S):
        modifie = True

    return {"D": D, "W_S": W_S, "cle_S": cle_S, "lundi_S": lundi_S,
            "evolution": _evals_chrono(reg)}, modifie


# ═══════════════════════════════════════════════════════════════════════════
# 7. Journal d'efficacité (un enregistrement par semaine S) et tendance
# ═══════════════════════════════════════════════════════════════════════════
def _moyenne(vals):
    vals = [v for v in vals if v is not None]
    return round(float(np.mean(vals)), 4) if vals else None


def enregistrer_efficacite(reg, cle_S, lundi_S):
    """
    Au début de la semaine S, fige l'efficacité de la prédictive :
    résultat réel de S-1 s'il est disponible, sinon la dernière semaine
    évaluée (enregistrement « provisoire », complété dès que S-1 est
    évaluée). Un enregistrement complet n'est plus jamais modifié.
    Retourne True si le journal a changé.
    """
    journal = reg.setdefault("journal_efficacite", {})
    ent = journal.get(cle_S)
    if ent is not None and ent.get("statut") == "complet":
        return False
    cle_prec = semaine_label(pd.Timestamp(lundi_S) - pd.Timedelta(days=7))
    evol = _evals_chrono(reg)
    ev_prec = reg.get("evaluations", {}).get(cle_prec)
    if ev_prec is not None:
        base, statut = ev_prec, "complet"
    elif not evol:
        return False
    else:
        base = evol[-1]
        # S-1 n'avait pas de plan publié : le rétro-test est définitif
        statut = "provisoire" if cle_prec in reg.get("predictions", {}) else "complet"
        if ent is not None and ent.get("semaine_evaluee") == base["semaine"]:
            return False
    jusqua = [e for e in evol if e["debut"] <= base["debut"]]
    m5 = base["modeles"]["M5"]
    precedents = [journal[k] for k in sorted(journal) if k < cle_S]
    prec_ant = precedents[-1]["precision"] if precedents else None
    premier = precedents[0]["precision"] if precedents else None
    journal[cle_S] = {
        "semaine": cle_S,
        "debut": str(pd.Timestamp(lundi_S).date()),
        "enregistre_le": str(pd.Timestamp.now().round("s")),
        "statut": statut,
        "semaine_evaluee": base["semaine"],
        "source": base.get("type", "réel"),
        "precision": m5["precision"], "detection": m5["detection"],
        "detectees": m5.get("detectees"), "pannes_reelles": m5.get("pannes_reelles"),
        "precision_moy4": _moyenne([e["modeles"]["M5"]["precision"] for e in jusqua[-4:]]),
        "detection_moy4": _moyenne([e["modeles"]["M5"]["detection"] for e in jusqua[-4:]]),
        "delta_vs_prec": (round(m5["precision"] - prec_ant, 4) if prec_ant is not None else None),
        "delta_vs_debut": (round(m5["precision"] - premier, 4) if premier is not None else None),
        "modeles": {m: {"precision": v["precision"], "detection": v["detection"]}
                    for m, v in base["modeles"].items()},
    }
    return True


def tendance(valeurs, n_bloc=4):
    """
    valeurs : série chronologique en %.
    Retourne pente (points / semaine, régression linéaire), droite
    ajustée, écart moyen « récent vs début » en points et en % relatif.
    """
    v = [float(x) for x in valeurs if x is not None]
    if len(v) < 2:
        return None
    x = np.arange(len(v))
    pente, ordo = np.polyfit(x, v, 1)
    k = max(1, min(n_bloc, len(v) // 2))
    debut, recent = float(np.mean(v[:k])), float(np.mean(v[-k:]))
    return {
        "pente": float(pente),
        "droite": [float(ordo + pente * i) for i in x],
        "debut": debut, "recent": recent, "n_bloc": k,
        "gain_pts": recent - debut,
        "gain_rel": ((recent - debut) / debut * 100) if debut else None,
        "sens": "amélioration" if pente > 0.25 else ("dégradation" if pente < -0.25 else "stable"),
    }
