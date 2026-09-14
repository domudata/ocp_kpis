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
    "OT_COR_EGAL": 5,
    "OT Fiabilité": 100,
    "Total Avis de Panne": 100,
}

LOWER_BETTER = [
    "OT préparation 1mois< <3mois", "OT préparation >3 mois",
    "OT planification 1mois< <3mois", "OT planification >3 mois",
    "OT exécution 1mois< <3mois", "OT exécution >3 mois",
    "OT_COR_EGAL",
]

ACT_MAP = {}
KPI_RESP_MAP = {}

MP_KW = ["CRPR ATPD", "CRPR ATMR", "CRPR ATER", "CRPR ATRS", "CRPR ATMO",
         "ATPD", "ATMR", "ATER", "ATRS", "ATMO"]
MPLAN_KW = ["ATPL ATEI", "ATPL ATAL", "ATPL ATER", "ATPL AGAR", "ATPL ATHS",
            "ATEI", "ATAL", "ATAS", "AGAR", "ATHS"]

CONSIGNES_HSE = ["Port obligatoire des EPI avant toute intervention."]
