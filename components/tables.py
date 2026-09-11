# -*- coding: utf-8 -*-
"""
PATCH — coloration de la ligne « Total general ».

PROBLÈME CORRIGÉ : dans html_table(), la ligne « Total general » était
colorée avec la même fonction ks(valeur, kpi) que les lignes de postes
individuels. Or ces deux lignes ne contiennent PAS la même grandeur :

  · ligne d'un poste  → la VALEUR BRUTE du KPI pour ce poste
      (ex. « 63,6 » dans la colonne "1mois< <3mois" = 63,6% des OT de ce
       poste sont dans cette tranche d'âge → mauvais, donc rouge)

  · ligne Total general → le TAUX DE CONFORMITÉ de la colonne
      (ex. « 63,6 » = 63,6% des postes sont conformes sur ce KPI
       → plutôt bon, et en tout cas une grandeur où PLUS C'EST HAUT,
       MIEUX C'EST, quelle que soit la nature du KPI)

Conséquences du bug :
  · KPI « plus bas = mieux » (tranches d'âge) : un taux de conformité
    élevé (95%) était affiché en ROUGE, car interprété comme « 95% des
    OT sont en retard » ;
  · KPI normaux : le taux de conformité étant presque toujours élevé,
    la cellule ressortait systématiquement en VERT — d'où une ligne
    Total general entièrement verte, sans valeur informative.

CORRECTION : la ligne Total general utilise désormais tcs(), qui applique
une échelle unique de taux de conformité (vert ≥ 90%, orange ≥ 70%,
rouge en dessous), identique pour tous les KPI.

Remplace la fonction html_table() existante dans components/tables.py,
et ajoute la fonction tcs() juste avant.
"""


def tcs(v) -> str:
    """Style d'une cellule de la ligne « Total general ».

    La valeur reçue est un TAUX DE CONFORMITÉ (% de postes conformes sur
    ce KPI) : une seule échelle s'applique, valable pour tous les KPI,
    puisque plus ce taux est élevé, meilleure est la situation.
    """
    try:
        val = float(str(v).replace(" %", "").strip())
    except Exception:
        return ""
    if val >= 90:
        return "background:#c6efce;color:#006100;"
    if val >= 70:
        return "background:#ffeb9c;color:#9c6500;"
    return "background:#ffc7ce;color:#9c0006;"


def html_table(rows: list, cols: list, tc: str, sc_col=None) -> str:
    h = '<table class="%s"><thead><tr>' % tc
    h += ''.join('<th>%s</th>' % c for c in cols)
    h += '</tr></thead><tbody>'
    for r in rows:
        is_cible = r.get("_t") == "cible"
        is_total = r.get("_t") == "total"
        rc = "cb" if is_cible else ""
        h += '<tr class="%s">' % rc
        for c in cols:
            v = r.get(c, "")
            if is_cible:
                h += '<td>%s</td>' % v
            elif is_total:
                # CORRIGÉ : la colonne "Score" garde l'échelle de score
                # (cs), les autres colonnes utilisent l'échelle de TAUX
                # DE CONFORMITÉ (tcs) — et non plus ks(), qui interprétait
                # à tort cette valeur comme une valeur brute de KPI.
                s = cs(v) if sc_col and c in sc_col else tcs(v)
                style = "font-weight:800;font-size:12px;text-align:center;" + s
                h += '<td style="%s">%s</td>' % (style, v)
            else:
                s = cs(v) if sc_col and c in sc_col else ks(v, c)
                h += '<td style="%s">%s</td>' % (s or "", v)
        h += '</tr>'
    return h + '</tbody></table>'
