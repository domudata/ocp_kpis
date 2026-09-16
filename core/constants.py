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

CIBLE = {
    "TAUX_REALISATION_CORRECTIF/PT": 85,
    "OT préparation <1 mois": 80,
    "OT préparation 1mois< <3mois": 15,
    "OT préparation >3 mois": 5,
    "OT planification <1 mois": 80,
    "OT planification 1mois< <3mois": 15,
    "OT planification >3 mois": 5,
    "OT exécution <1 mois": 80,
    "OT exécution 1mois< <3mois": 15,
    "OT exécution >3 mois": 5,
    "Performance Graissage": 95,
    "Performance Inspection": 95,
    "Performance Systématiques": 85,
    "Taux d'approbation des Avis": 95,
    "OT LANC ESTIME": 100,
    "Backlog préparation caractérisé": 100,
    "Backlog planification caractérisé": 100,
    "OT CONFIME": 100,
    "OT_COR_EGAL": 100,
    "OT Fiabilité": 100,
    "Total Avis de Panne": 100,
}

LOWER_BETTER = [
    "OT préparation 1mois< <3mois", "OT préparation >3 mois",
    "OT planification 1mois< <3mois", "OT planification >3 mois",
    "OT exécution 1mois< <3mois", "OT exécution >3 mois",
]

KPI_RESP_MAP = {
    # Préparateur Méthodes
    "OT préparation <1 mois": "Préparateur Méthodes",
    "OT préparation 1mois< <3mois": "Préparateur Méthodes",
    "OT préparation >3 mois": "Préparateur Méthodes",
    "Backlog préparation caractérisé": "Préparateur Méthodes",
    "OT LANC ESTIME": "Préparateur Méthodes",

    # Planificateur Méthodes
    "OT planification <1 mois": "Planificateur Méthodes",
    "OT planification 1mois< <3mois": "Planificateur Méthodes",
    "OT planification >3 mois": "Planificateur Méthodes",
    "Backlog planification caractérisé": "Planificateur Méthodes",

    # Chef d'Atelier
    "OT exécution <1 mois": "Chef d'Atelier",
    "OT exécution 1mois< <3mois": "Chef d'Atelier",
    "OT exécution >3 mois": "Chef d'Atelier",
    "Performance Graissage": "Chef d'Atelier",
    "Performance Inspection": "Chef d'Atelier",
    "Performance Systématiques": "Chef d'Atelier",
    "TAUX_REALISATION_CORRECTIF/PT": "Chef d'Atelier",
    "Taux d'approbation des Avis": "Chef d'Atelier",
    "Total Avis de Panne": "Chef d'Atelier",

    # Agent de Saisie
    "OT CONFIME": "Agent de Saisie",
    "OT_COR_EGAL": "Agent de Saisie",

    # Ingénieur Fiabilité
    "OT Fiabilité": "Ingénieur Fiabilité",
}

ACT_MAP = {
    "TAUX_REALISATION_CORRECTIF/PT": "Augmenter le taux de réalisation et clôturer techniquement les OT terminés (CLOT/TCLO).",
    "OT préparation <1 mois": "Traiter et préparer les OT récemment créés pour éviter l'accumulation en amont.",
    "OT préparation 1mois< <3mois": "Accélérer l'approvisionnement des pièces (ATPD) ou la contractualisation marché (ATMR).",
    "OT préparation >3 mois": "Traiter d'urgence les blocages de longue durée (>3 mois) ou annuler les OT devenus sans objet.",
    "OT planification <1 mois": "Programmer les OT dans le planning hebdomadaire de maintenance selon les priorités.",
    "OT planification 1mois< <3mois": "Coordonner les arrêts d'équipement (ATEI) ou de ligne (ATAL) avec la production.",
    "OT planification >3 mois": "Planifier impérativement lors du prochain arrêt programmé ou débloquer les contraintes associées.",
    "OT exécution <1 mois": "Exécuter les ordres lancés conformément au planning hebdomadaire validé.",
    "OT exécution 1mois< <3mois": "Mobiliser les équipes d'intervention pour résorber les ordres en cours d'exécution.",
    "OT exécution >3 mois": "Finaliser les travaux sur le terrain et procéder à la clôture immédiate des OT.",
    "Performance Graissage": "Assurer la réalisation complète des tournées de graissage hebdomadaires prévues.",
    "Performance Inspection": "Réaliser l'ensemble des inspections planifiées et consigner les anomalies détectées.",
    "Performance Systématiques": "Respecter l'échéancier des interventions systématiques préventives.",
    "Taux d'approbation des Avis": "Traiter et approuver les avis de maintenance ouverts (statut système AOUV) dans SAP.",
    "OT LANC ESTIME": "Renseigner systématiquement l'estimation des coûts (PDR et main d'œuvre) avant lancement de l'OT.",
    "Backlog préparation caractérisé": "Caractériser les OT non caractérisés (ATPD, ATMR, ATER, ATRS, ATMO) et réduire les OT de préparation dépassant les délais.",
    "Backlog planification caractérisé": "Qualifier le motif d'arrêt requis (ATEI, ATAL, ATAS, AGAR, ATHS) et réduire le backlog de planification ancien.",
    "OT CONFIME": "Saisir les confirmations d'heures réelles (CONF) et vérifier les confirmations des OT exécutés.",
    "OT_COR_EGAL": "Contrôler la cohérence entre coûts budgétés et coûts réels, et corriger les OT dont les coûts ne sont pas cohérents (coûts réels = 0 ou égaux au budget).",
    "OT Fiabilité": "Analyser les pannes récurrentes et intégrer les actions correctives dans les plans d'entretien.",
    "Total Avis de Panne": "Valider la qualification technique des avis de panne et traiter les avis de panne dans les délais.",
}


MP_KW = ["CRPR ATPD", "CRPR ATMR", "CRPR ATER", "CRPR ATRS", "CRPR ATMO",
         "ATPD", "ATMR", "ATER", "ATRS", "ATMO"]
MPLAN_KW = ["ATPL ATEI", "ATPL ATAL", "ATPL ATER", "ATPL AGAR", "ATPL ATHS",
            "ATEI", "ATAL", "ATAS", "AGAR", "ATHS"]

CODES_PREP_EXACT = {"ATPD", "ATMR", "ATER", "ATRS", "ATMO"}
CODES_PLAN_EXACT = {"ATEI", "ATAL", "ATAS", "AGAR", "ATHS"}
ALL_CARAC_EXACT = CODES_PREP_EXACT | CODES_PLAN_EXACT

CONSIGNES_HSE = ["Port obligatoire des EPI avant toute intervention."]

