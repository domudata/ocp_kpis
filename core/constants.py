# -*- coding: utf-8 -*-

QK = [
    "TAUX_REALISATION_CORRECTIF/PT",
    "OT préparation <1 mois",
    "OT préparation 1mois< <3mois",
    "OT préparation >3 mois",
    "OT planification <1 mois",
    "OT planification 1mois< <3mois",
    "OT planification >3 mois",
    "OT exécution <1 mois",
    "OT exécution 1mois< <3mois",
    "OT exécution >3 mois",
    "Performance Graissage",
    "Performance Inspection",
    "Performance Systématiques",
]

PK = [
    "Taux d'approbation des Avis",
    "OT LANC ESTIME",
    "Backlog préparation caractérisé",
    "Backlog planification caractérisé",
    "OT CONFIME",
    "OT_COR_EGAL",
    "OT Fiabilité",
    "Total Avis de Panne",
]

ALL_KPI = QK + PK

# ── CIBLES ────────────────────────────────────────────────────────────────────
# Logique age backlog :
#   <1m  : score = taux brut direct         → cible >= 80%
#   1-3m : score = 100 - taux_brut          → cible >= 85% (= max 15% OT dans tranche)
#   >3m  : score = 100 - taux_brut          → cible >= 95% (= max 5%  OT dans tranche)
# Tous les KPIs sont "plus haut = mieux" grâce à la logique 100-val
CIBLE = {
    # Performance
    "TAUX_REALISATION_CORRECTIF/PT":     85,

    # Age Préparation
    "OT préparation <1 mois":            80,
    "OT préparation 1mois< <3mois":      85,   # score = 100 - taux_brut
    "OT préparation >3 mois":            95,   # score = 100 - taux_brut

    # Age Planification
    "OT planification <1 mois":          80,
    "OT planification 1mois< <3mois":    85,
    "OT planification >3 mois":          95,

    # Age Exécution
    "OT exécution <1 mois":              80,
    "OT exécution 1mois< <3mois":        85,
    "OT exécution >3 mois":              95,

    # Performance préventif
    "Performance Graissage":             95,
    "Performance Inspection":            95,
    "Performance Systématiques":         85,

    # Qualité
    "Taux d'approbation des Avis":       95,
    "OT LANC ESTIME":                    100,
    "Backlog préparation caractérisé":   100,
    "Backlog planification caractérisé": 100,
    "OT CONFIME":                        100,
    "OT_COR_EGAL":                       100,
    "OT Fiabilité":                      100,
    "Total Avis de Panne":               100,
}

# ── LOWER_BETTER ─────────────────────────────────────────────────────────────
# VIDE — avec la logique 100-val, tous les KPIs sont "plus haut = mieux"
# needs_action = actual < target pour TOUS les KPIs
LOWER_BETTER = []

# ── ACTIONS ──────────────────────────────────────────────────────────────────
ACT_MAP = {
    "TAUX_REALISATION_CORRECTIF/PT":     "Ameliorer le taux de realisation des OT correctifs.",
    "OT préparation <1 mois":            "Accelerer la preparation des OT (reduire age < 1 mois).",
    "OT préparation 1mois< <3mois":      "Reduire les OT en preparation entre 1 et 3 mois.",
    "OT préparation >3 mois":            "Traiter en priorite les OT en preparation > 3 mois.",
    "OT planification <1 mois":          "Accelerer la planification des OT (reduire age < 1 mois).",
    "OT planification 1mois< <3mois":    "Reduire les OT en planification entre 1 et 3 mois.",
    "OT planification >3 mois":          "Traiter en priorite les OT en planification > 3 mois.",
    "OT exécution <1 mois":              "Accelerer l execution des OT (reduire age < 1 mois).",
    "OT exécution 1mois< <3mois":        "Reduire les OT en execution entre 1 et 3 mois.",
    "OT exécution >3 mois":              "Traiter en priorite les OT en execution > 3 mois.",
    "Performance Graissage":             "Ameliorer le taux de realisation des OT de graissage (TW=350).",
    "Performance Inspection":            "Ameliorer le taux de realisation des OT d inspection (TW=290/300/310).",
    "Performance Systématiques":         "Ameliorer le taux de realisation des appels systematiques (TW=360).",
    "Taux d'approbation des Avis":       "Approuver les avis en attente (statut APRQ).",
    "OT LANC ESTIME":                    "Estimer les couts des OT lances (renseigner charge estimee).",
    "Backlog préparation caractérisé":   "Caracteriser le backlog de preparation (ATPD/ATMR/ATRS/ATMO/ATER).",
    "Backlog planification caractérisé": "Caracteriser le backlog de planification (ATEI/ATAL/ATAS/AGAR/ATHS).",
    "OT CONFIME":                        "Confirmer les OT termines (statut CONF).",
    "OT_COR_EGAL":                       "Verifier l imputation des couts reels des OT correctifs.",
    "OT Fiabilité":                      "Maintenir la fiabilite des OT.",
    "Total Avis de Panne":               "Maintenir le suivi des avis de panne.",
}

# ── RESPONSABLES ─────────────────────────────────────────────────────────────
KPI_RESP_MAP = {
    "TAUX_REALISATION_CORRECTIF/PT":     "Chef d'atelier",
    "OT préparation <1 mois":            "Préparateur BM",
    "OT préparation 1mois< <3mois":      "Préparateur BM",
    "OT préparation >3 mois":            "Préparateur BM",
    "OT planification <1 mois":          "Planificateur BM",
    "OT planification 1mois< <3mois":    "Planificateur BM",
    "OT planification >3 mois":          "Planificateur BM",
    "OT exécution <1 mois":              "Chef d'atelier",
    "OT exécution 1mois< <3mois":        "Chef d'atelier",
    "OT exécution >3 mois":              "Chef d'atelier",
    "Performance Graissage":             "Chef d'atelier",
    "Performance Inspection":            "Chef d'atelier",
    "Performance Systématiques":         "Chef d'atelier",
    "Taux d'approbation des Avis":       "Chef d'atelier",
    "OT LANC ESTIME":                    "Fiabilité",
    "Backlog préparation caractérisé":   "Préparateur BM",
    "Backlog planification caractérisé": "Planificateur BM",
    "OT CONFIME":                        "Agent de saisie",
    "OT_COR_EGAL":                       "Agent de saisie",
    "OT Fiabilité":                      "Fiabilité",
    "Total Avis de Panne":               "Fiabilité",
}

# ── MOTS CLES CARACTERISATION ────────────────────────────────────────────────
MP_KW    = ["CRPR ATPD","CRPR ATMR","CRPR ATER","CRPR ATRS","CRPR ATMO",
            "ATPD","ATMR","ATER","ATRS","ATMO"]
MPLAN_KW = ["ATPL ATEI","ATPL ATAL","ATPL ATER","ATPL AGAR","ATPL ATHS",
            "ATEI","ATAL","ATAS","AGAR","ATHS"]

# ── CONSIGNES HSE ────────────────────────────────────────────────────────────
CONSIGNES_HSE = [
    "Port obligatoire des EPI avant toute intervention.",
    "Port obligatoire du casque de securite.",
    "Port obligatoire des lunettes de protection.",
    "Port obligatoire des gants adaptes au travail.",
    "Utiliser les protections auditives dans les zones bruyantes.",
    "Verifier l absence de tension avant toute intervention electrique.",
    "Respecter la procedure de consignation et deconsignation.",
    "Ne jamais intervenir sur un equipement en marche.",
    "Baliser et securiser la zone de travail.",
    "Maintenir le poste de travail propre et ordonne.",
    "Verifier l etat des outils avant utilisation.",
    "Utiliser uniquement du materiel homologue.",
    "Respecter les permis de travail en vigueur.",
    "Identifier les risques avant de commencer une tache.",
    "Signaler immediatement toute situation dangereuse.",
    "Signaler tout incident ou presque accident.",
    "Ne jamais neutraliser un dispositif de securite.",
    "Verifier les detecteurs de gaz avant utilisation.",
    "Verifier la bonne ventilation des zones de travail.",
    "Respecter les regles des espaces confines.",
    "Controler l atmosphere avant d entrer dans un espace confine.",
    "Utiliser les points d ancrage pour les travaux en hauteur.",
    "Verifier l etat des echafaudages avant utilisation.",
    "Securiser les outils lors des travaux en hauteur.",
    "Ne pas travailler seul lors des operations a risque.",
    "Controler les elingues avant chaque levage.",
    "Respecter les limites de charge des equipements.",
    "Verifier l etat des appareils de levage.",
    "Maintenir les voies de circulation degagees.",
    "Respecter la signalisation de securite.",
    "Verifier les extincteurs a proximite du chantier.",
    "Connaitre les issues de secours les plus proches.",
    "Respecter les procedures d arret d urgence.",
    "Verifier les flexibles et raccords avant mise en service.",
    "Controler les fuites avant demarrage d un equipement.",
    "Respecter les distances de securite.",
    "Ne jamais contourner une procedure HSE.",
    "Porter les EPI adaptes au risque identifie.",
    "Prevenir son responsable avant toute intervention particuliere.",
    "Analyser les risques avant chaque demarrage de chantier.",
    "Arreter immediatement les travaux en cas de danger.",
    "Proteger l environnement lors des interventions.",
    "Collecter et trier correctement les dechets.",
    "Eviter toute pollution accidentelle.",
    "Respecter les consignes de stockage des produits dangereux.",
    "Lire les fiches de securite avant manipulation.",
    "Verifier les equipements avant chaque prise de poste.",
    "Communiquer clairement avec l equipe avant intervention.",
    "Respecter les regles de circulation des engins.",
    "Garder une vigilance permanente sur son environnement.",
    "La securite est l affaire de tous.",
    "Chaque incident peut etre evite par la prevention.",
    "Aucun travail n est plus urgent que la securite.",
    "Zero accident commence par un comportement sur.",
]
