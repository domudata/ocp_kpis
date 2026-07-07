# -*- coding: utf-8 -*-
import base64
import pandas as pd

from core.constants import CIBLE, LOWER_BETTER, ACT_MAP, KPI_RESP_MAP, QK, PK, ALL_KPI


# ──────────────────────────────────────────────
# Helpers de couleur / style
# ──────────────────────────────────────────────

def is_lb(k: str) -> bool:
    return k in LOWER_BETTER


def get_bar_color(kpi, val) -> str:
    try:
        v = float(val)
    except Exception:
        return "#cbd5e0"
    if kpi in ["OT préparation <1 mois", "OT planification <1 mois", "OT exécution <1 mois"]:
        return "#38a169" if v >= 80 else ("#f59e0b" if v >= 75 else "#e53e3e")
    if kpi in ["OT préparation 1mois< <3mois", "OT planification 1mois< <3mois", "OT exécution 1mois< <3mois"]:
        return "#38a169" if v <= 15 else "#e53e3e"
    if kpi in ["OT préparation >3 mois", "OT planification >3 mois", "OT exécution >3 mois"]:
        return "#38a169" if v <= 5 else "#e53e3e"
    if kpi == "TAUX_REALISATION_CORRECTIF/PT":
        return "#38a169" if v >= 85 else ("#f59e0b" if v >= 80 else "#e53e3e")
    if kpi == "Taux d'approbation des Avis":
        return "#38a169" if v >= 95 else ("#f59e0b" if v >= 90 else "#e53e3e")
    if kpi in ["OT LANC ESTIME", "Backlog préparation caractérisé",
               "Backlog planification caractérisé", "OT CONFIME", "OT_COR_EGAL"]:
        return "#38a169" if v >= 100 else ("#f59e0b" if v >= 95 else "#e53e3e")
    if kpi in ["Performance Graissage", "Performance Inspection", "Performance Systématiques"]:
        return "#38a169" if v >= 95 else ("#f59e0b" if v > 90 else "#e53e3e")
    if kpi in ["OT Fiabilité", "Total Avis de Panne"]:
        return "#38a169" if v >= 100 else "#f59e0b"
    return "#38a169" if v >= 90 else ("#f59e0b" if v >= 80 else "#e53e3e")


def ks(v, c) -> str:
    try:
        val = float(v)
    except Exception:
        return ""
    if c in ["OT préparation <1 mois", "OT planification <1 mois", "OT exécution <1 mois"]:
        return "background:#c6efce;color:#006100;font-weight:600" if val >= 80 else ("background:#ffeb9c;color:#9c6500;font-weight:600" if val >= 75 else "background:#ffc7ce;color:#9c0006;font-weight:600")
    if c in ["OT préparation 1mois< <3mois", "OT planification 1mois< <3mois", "OT exécution 1mois< <3mois"]:
        return "background:#c6efce;color:#006100;font-weight:600" if val <= 15 else "background:#ffc7ce;color:#9c0006;font-weight:600"
    if c in ["OT préparation >3 mois", "OT planification >3 mois", "OT exécution >3 mois"]:
        return "background:#c6efce;color:#006100;font-weight:600" if val <= 5 else "background:#ffc7ce;color:#9c0006;font-weight:600"
    if c == "TAUX_REALISATION_CORRECTIF/PT":
        return "background:#c6efce;color:#006100;font-weight:600" if val >= 85 else ("background:#ffeb9c;color:#9c6500;font-weight:600" if val >= 80 else "background:#ffc7ce;color:#9c0006;font-weight:600")
    if c == "Taux d'approbation des Avis":
        return "background:#c6efce;color:#006100;font-weight:600" if val >= 95 else ("background:#ffeb9c;color:#9c6500;font-weight:600" if val >= 90 else "background:#ffc7ce;color:#9c0006;font-weight:600")
    if c in ["OT LANC ESTIME", "Backlog préparation caractérisé", "Backlog planification caractérisé", "OT CONFIME", "OT_COR_EGAL"]:
        return "background:#c6efce;color:#006100;font-weight:600" if val >= 100 else ("background:#ffeb9c;color:#9c6500;font-weight:600" if val >= 95 else "background:#ffc7ce;color:#9c0006;font-weight:600")
    if c in ["Performance Graissage", "Performance Inspection", "Performance Systématiques"]:
        return "background:#c6efce;color:#006100;font-weight:600" if val >= 95 else ("background:#ffeb9c;color:#9c6500;font-weight:600" if val > 90 else "background:#ffc7ce;color:#9c0006;font-weight:600")
    if c in ["OT Fiabilité", "Total Avis de Panne"]:
        return "background:#c6efce;color:#006100;font-weight:600" if val >= 100 else "background:#ffeb9c;color:#9c6500;font-weight:600"
    return ""


def cs(v) -> str:
    try:
        val = float(str(v).replace(' %', '').strip())
    except Exception:
        return ""
    return ("background:#c6efce;color:#006100;font-weight:700" if val >= 90
            else ("background:#ffeb9c;color:#9c6500;font-weight:700" if val >= 80
                  else "background:#ffc7ce;color:#9c0006;font-weight:700"))


def kas(v) -> str:
    try:
        val = int(v)
    except Exception:
        return ""
    if val == 0:   return "background:#c6efce;color:#006100;font-weight:600"
    if val <= 3:   return "background:#ffeb9c;color:#9c6500;font-weight:600"
    if val <= 10:  return "background:#ffc7ce;color:#9c0006;font-weight:600"
    return "background:#ff9999;color:#7f1d1d;font-weight:800"


# ──────────────────────────────────────────────
# Tableaux HTML
# ──────────────────────────────────────────────

def html_table(rows: list, cols: list, tc: str, sc_col=None) -> str:
    h = '<table class="tw %s"><thead><tr>' % tc
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
                h += '<td style="background:#1e3a5f;color:#FFFFFF;font-weight:bold;text-align:center;">%s</td>' % v
            elif is_total:
                s = cs(v) if sc_col and c in sc_col else ks(v, c)
                style = "font-weight:800;font-size:12px;text-align:center;"
                if s:
                    clean = s.replace("font-weight:600", "").replace("font-weight:700", "")
                    style += clean
                h += '<td style="%s">%s</td>' % (style, v)
            else:
                s = cs(v) if sc_col and c in sc_col else ks(v, c)
                h += '<td style="%s">%s</td>' % (s or "", v)
        h += '</tr>'
    return h + '</tbody></table>'


def html_anomaly_table(rows: list, cols: list, tc: str) -> str:
    h = '<table class="tw %s"><thead><tr>' % tc
    h += ''.join('<th>%s</th>' % c for c in cols)
    h += '</tr></thead><tbody>'
    for r in rows:
        rc = "tr" if r.get("Poste de travail") == "Total" else ""
        h += '<tr class="%s">' % rc
        for c in cols:
            v = r.get(c, "")
            if c == "Poste de travail":
                h += '<td style="font-weight:700">%s</td>' % v
            elif c == "Total Anomalies":
                h += '<td style="text-align:center;font-weight:800">%s</td>' % v
            else:
                s = kas(v)
                h += '<td style="%s;text-align:center">%s</td>' % (s or "", v)
        h += '</tr>'
    return h + '</tbody></table>'


def html_actions_table(kpi_list: list, actuals: dict, targets: dict, act_map: dict) -> str:
    h = ('<table class="tw at"><thead><tr>'
         '<th>KPI</th><th>Valeur Actuelle</th><th>Cible</th>'
         '<th>Ecart</th><th>Statut</th><th>Action Recommandee</th>'
         '</tr></thead><tbody>')
    for k in kpi_list:
        av  = actuals.get(k, 0)
        tv  = targets.get(k, 100)
        diff = av - tv
        met = av <= tv if is_lb(k) else av >= tv
        status = "ATTEINT" if met else "NON ATTEINT"
        st_s   = "background:#c6efce;color:#006100;font-weight:700" if met else "background:#ffc7ce;color:#9c0006;font-weight:700"
        ec_clr = "#059669" if met else "#dc2626"
        action = "Objectif atteint" if met else act_map.get(k, "")
        h += ('<tr><td style="font-weight:600">%s</td><td>%.1f%%</td><td>%.0f%%</td>'
              '<td style="color:%s;font-weight:700">%+.1f%%</td>'
              '<td style="%s">%s</td>'
              '<td style="color:#4a5568">%s</td></tr>') % (
            k, av, tv, ec_clr, diff, st_s, status, action)
    return h + '</tbody></table>'


def html_statut_pivot(piv_df: pd.DataFrame, table_class: str) -> str:
    cols = ["Poste de travail", "CRÉÉ", "LANC", "CLOT", "TCLO", "Total"]
    statut_colors = {
        "CRÉÉ":  "background:#fef3c7;color:#92400e;font-weight:600;",
        "LANC":  "background:#dbeafe;color:#1e40af;font-weight:600;",
        "CLOT":  "background:#d1fae5;color:#065f46;font-weight:600;",
        "TCLO":  "background:#a7f3d0;color:#064e3b;font-weight:600;",
        "Total": "background:#ede9fe;color:#5b21b6;font-weight:700;",
    }
    h = '<table class="tw %s"><thead><tr>' % table_class
    h += ''.join('<th>%s</th>' % c for c in cols)
    h += '</tr></thead><tbody>'
    for poste, row in piv_df.iterrows():
        h += '<tr><td style="font-weight:700">%s</td>' % poste
        for c in ["CRÉÉ", "LANC", "CLOT", "TCLO"]:
            h += '<td style="text-align:center;%s">%d</td>' % (statut_colors[c], int(row.get(c, 0)))
        h += '<td style="text-align:center;%s">%d</td>' % (statut_colors["Total"], int(row.get("Total", 0)))
        h += '</tr>'
    h += '<tr class="tr"><td style="font-weight:800">Total</td>'
    for c in ["CRÉÉ", "LANC", "CLOT", "TCLO"]:
        h += '<td style="text-align:center;font-weight:800;%s">%d</td>' % (statut_colors[c], int(piv_df[c].sum()))
    h += '<td style="text-align:center;font-weight:800;%s">%d</td>' % (statut_colors["Total"], int(piv_df["Total"].sum()))
    h += '</tr></tbody></table>'
    return h


def html_generic_pivot(piv_df: pd.DataFrame, table_class: str, title: str) -> str:
    piv_df = piv_df.copy()
    piv_df["Total"] = piv_df.sum(axis=1)
    cols = ["Poste de travail"] + [str(c) for c in piv_df.columns]

    def get_style(col_name):
        if col_name == "CARACTERISE":     return "background:#d1fae5;color:#065f46;font-weight:600;"
        if col_name == "NON CARACTERISE": return "background:#fee2e2;color:#991b1b;font-weight:600;"
        if col_name == "Total":           return "background:#ede9fe;color:#5b21b6;font-weight:700;"
        return "background:#f8fafc;color:#1e293b;font-weight:600;"

    h = '<div class="ca"><div class="ct" style="color:#1e3a5f">%s</div>' % title
    h += '<table class="tw %s"><thead><tr>' % table_class
    h += ''.join('<th>%s</th>' % c for c in cols)
    h += '</tr></thead><tbody>'
    for poste, row in piv_df.iterrows():
        h += '<tr><td style="font-weight:700">%s</td>' % poste
        for c in piv_df.columns:
            h += '<td style="text-align:center;%s">%d</td>' % (get_style(c), int(row.get(c, 0)))
        h += '</tr>'
    h += '<tr class="tr"><td style="font-weight:800">Total</td>'
    for c in piv_df.columns:
        h += '<td style="text-align:center;font-weight:800;%s">%d</td>' % (get_style(c), int(piv_df[c].sum()))
    h += '</tr></tbody></table></div>'
    return h


def html_synthese_table(synth_data: dict, kpi_list: list, posts: list) -> str:
    h = '<table class="synth-tbl"><thead><tr><th style="min-width:160px;text-align:left">Poste de travail</th>'
    for kpi in kpi_list:
        h += '<th>%s</th>' % kpi
    h += '</tr></thead><tbody>'
    for poste in posts:
        h += '<tr><td class="poste-cell">%s</td>' % poste
        for kpi in kpi_list:
            info = synth_data.get(poste, {}).get(kpi, {})
            diff = info.get("diff", "—")
            if diff != "—":
                try:
                    d = float(diff)
                    clr = "#d1fae5" if d > 0 else ("#fee2e2" if d < 0 else "")
                    h += '<td style="background:%s;text-align:center;font-weight:700">%s</td>' % (clr, diff)
                except Exception:
                    h += '<td style="text-align:center">—</td>'
            else:
                h += '<td style="text-align:center">—</td>'
        h += '</tr>'
    h += '</tbody></table>'
    return h


def html_classement(scores: dict, accent: str) -> str:
    sp   = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    met  = [(p, s) for p, s in sp if s >= 80]
    not_ = [(p, s) for p, s in sp if s < 80]
    t5   = met[:5]
    b5   = not_[-5:] if len(not_) > 5 else not_

    h = '<div class="cg"><div><div class="ct" style="color:#10b981">Top 5 — Objectif Atteint</div>'
    if t5:
        for i, (p, s) in enumerate(t5):
            h += '<div class="cgr"><span class="rk" style="color:%s">%s</span><span class="pn">%s</span><span class="ps" style="%s">%.2f%%</span></div>' % (accent, i + 1, p, cs("%.2f" % s), s)
    else:
        h += '<div style="padding:6px;font-size:12px;color:#64748b">Aucun poste</div>'

    h += '</div><div><div class="ct" style="color:#f97316">Bottom 5 — Non Atteint</div>'
    if b5:
        for i, (p, s) in enumerate(reversed(b5)):
            h += '<div class="cgr"><span class="rk" style="color:#f97316">%s</span><span class="pn">%s</span><span class="ps" style="%s">%.2f%%</span></div>' % (len(b5) - i, p, cs("%.2f" % s), s)
    else:
        h += '<div style="padding:6px;font-size:12px;color:#10b981">Tous atteints</div>'

    h += '</div></div>'
    return h


def html_kpi_bars(kpi_list: list, actuals: dict, targets: dict,
                  title: str, color_ok: str, color_fail: str) -> str:
    h = '<div class="ca"><div class="ct" style="color:%s">%s</div>' % (color_ok, title)
    h += ('<div class="gbr-legend"><span>'
          '<span style="display:inline-block;width:3px;height:14px;background:#3b82f6;'
          'border-radius:1px;box-shadow:0 0 3px rgba(59,130,246,.6);margin-right:5px;'
          'vertical-align:middle;"></span> Cible</span></div>')
    for k in kpi_list:
        av  = actuals.get(k, 0)
        tv  = targets.get(k, 100)
        bw  = min(max(av, 0), 100)
        bg  = get_bar_color(k, av)
        tvp = min(max(tv, 0), 100)
        h += (
            '<div class="car">'
            '<div class="cal">%s</div>'
            '<div class="cab">'
            '<div class="caf" style="width:%s%%;background:%s"></div>'
            '<div class="target-mark" style="position:absolute;top:-5px;bottom:-5px;width:4px;'
            'background:#3b82f6;z-index:20;left:%s%%;transform:translateX(-50%%);'
            'box-shadow:0 0 6px rgba(59,130,246,1);border-radius:2px;"></div>'
            '</div>'
            '<div class="cav-out">%.1f%%</div>'
            '<div class="cav-tgt">/%.0f%%</div>'
            '</div>'
        ) % (k, bw, bg, tvp, av, tv)
    return h + '</div>'


def html_grouped_bars(posts: list, pscores: dict, qscores: dict, title: str) -> str:
    h = '<div class="ca"><div class="ct" style="color:#1e3a5f">%s</div>' % title
    h += ('<div style="display:flex;align-items:center;margin-bottom:8px;padding-bottom:5px;border-bottom:1px solid #e2e8f0;">'
          '<div class="gbr-l"></div><div class="gbr-g">'
          '<div style="flex:1;text-align:center;font-weight:800;color:#2563eb;font-size:14px;">Performance</div>'
          '<div style="min-width:48px;"></div>'
          '<div style="flex:1;text-align:center;font-weight:800;color:#059669;font-size:14px;">Qualite</div>'
          '<div style="min-width:48px;"></div>'
          '</div></div>')
    sorted_posts = sorted(posts, key=lambda x: (pscores.get(x, 0) + qscores.get(x, 0)) / 2, reverse=True)
    for p in sorted_posts:
        pv = pscores.get(p, 0)
        qv = qscores.get(p, 0)
        pc = get_bar_color(None, pv)
        qc = get_bar_color(None, qv)
        h += (
            '<div class="gbr"><div class="gbr-l">%s</div><div class="gbr-g">'
            '<div class="gbr-w"><div class="gbr-f" style="width:%s%%;background:%s"></div></div>'
            '<div class="gbr-v">%.1f%%</div>'
            '<div class="gbr-w"><div class="gbr-f" style="width:%s%%;background:%s"></div></div>'
            '<div class="gbr-v">%.1f%%</div>'
            '</div></div>'
        ) % (p, min(max(pv, 0), 100), pc, pv, min(max(qv, 0), 100), qc, qv)
    return h + '</div>'


def html_plan_actions_table(rows: list, title: str, accent_color: str,
                             anomaly_dfs: dict) -> str:
    if not rows:
        return (
            '<div class="ca" style="margin-bottom:10px;">'
            '<div class="ct" style="color:%s;border-bottom:2px solid %s;">%s</div>'
            '<div class="es" style="padding:20px;">✅ Aucune action requise — Tous les KPIs sont conformes !</div>'
            '</div>'
        ) % (accent_color, accent_color, title)

    from itertools import groupby
    rows_sorted = sorted(rows, key=lambda x: (x["poste"], -abs(x["ecart"])))
    grouped = [(k, list(g)) for k, g in groupby(rows_sorted, key=lambda x: x["poste"])]

    h = ('<div class="ca" style="margin-bottom:12px;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;">'
         '<div style="background:linear-gradient(135deg,%s,%s);padding:10px 14px;color:#fff;font-size:15px;'
         'font-weight:800;display:flex;justify-content:space-between;align-items:center;">'
         '<span>%s</span>'
         '<span style="background:rgba(255,255,255,0.2);padding:3px 12px;border-radius:14px;font-size:13px;">%d action(s)</span>'
         '</div>') % (accent_color, accent_color, title, len(rows))

    h += '<table class="plan-action-table"><thead><tr>'
    for hdr in ["Poste de travail", "KPI", "Nécessite Action", "Écart", "Nb Anomalies", "Responsable", "Action Recommandée", "Délai"]:
        h += '<th>%s</th>' % hdr
    h += '</tr></thead><tbody>'

    row_idx = 0
    for poste, group_rows in grouped:
        rowspan = len(group_rows)
        first   = True
        for r in group_rows:
            bg  = "#ffffff" if row_idx % 2 == 0 else "#f8fafc"
            h  += '<tr style="background:%s;">' % bg

            if first:
                poste_bg = "#eff6ff" if accent_color == "#3b82f6" else "#f0fdf4"
                h += ('<td rowspan="%d" style="color:%s;background:%s;border-right:3px solid %s;">%s</td>'
                      ) % (rowspan, accent_color, poste_bg, accent_color, poste)
                first = False

            h += '<td style="text-align:left;font-weight:600;color:#2d3748;">%s</td>' % r["kpi"]

            _st = r.get("status", "oui_rouge" if r["needs_action"] else "non_vert")
            if _st == "oui_rouge":
                h += '<td><span style="background:#e53e3e;color:#fff;padding:2px 10px;border-radius:12px;font-size:10px;font-weight:700;">OUI</span></td>'
            elif _st == "oui_vert":
                h += '<td><span style="background:#38a169;color:#fff;padding:2px 10px;border-radius:12px;font-size:10px;font-weight:700;">OUI</span></td>'
            else:
                h += '<td><span style="background:#38a169;color:#fff;padding:2px 10px;border-radius:12px;font-size:10px;font-weight:700;">NON</span></td>'

            # Ecart deja SIGNE dans app.py (positif = conforme, negatif = non
            # conforme, sens deja adapte pour les KPI LOWER_BETTER). NE PAS
            # reappliquer le test LOWER_BETTER ici -> cela inversait le signe
            # une seconde fois et affichait en rouge des ecarts positifs (OK).
            ecart  = r["ecart"]
            is_bad = ecart < 0
            ec_clr = "#dc2626" if is_bad else "#059669"
            h += '<td style="font-weight:800;color:%s;">%+.1f%%</td>' % (ec_clr, ecart)

            nb = r["nb_anom"]
            link_html = str(nb)
            if nb == 0:
                h += '<td style="font-weight:800;color:#065f46;">0</td>'
            else:
                nb_clr = "#92400e" if nb <= 3 else ("#991b1b" if nb <= 10 else "#7f1d1d")
                try:
                    kpi_name  = r["kpi"]
                    poste_name = r["poste"]
                    if kpi_name in anomaly_dfs:
                        df_anom = anomaly_dfs[kpi_name]
                        df_poste = df_anom[df_anom["Poste travail princ."] == poste_name] if "Poste travail princ." in df_anom.columns else df_anom
                        if not df_poste.empty:
                            csv_data = df_poste.to_csv(index=False, sep=';')
                            b64 = base64.b64encode(csv_data.encode('utf-8')).decode()
                            safe_fn = (f"{poste_name}_{kpi_name}"
                                       .replace("/", "-").replace("\\", "-")
                                       .replace(" ", "_").replace("<", "").replace(">", "")[:50])
                            link_html = (
                                f'<a href="data:text/csv;charset=utf-8;base64,{b64}" '
                                f'download="{safe_fn}.csv" '
                                f'style="color:{nb_clr};text-decoration:underline;cursor:pointer;font-weight:800;">'
                                f'{nb}</a>'
                            )
                except Exception:
                    pass
                h += '<td>%s</td>' % link_html

            h += '<td style="font-weight:600;color:#4a5568;">%s</td>' % r["responsable"]
            h += '<td style="text-align:left;color:#4a5568;">%s</td>' % r["action"]
            h += '<td style="color:#a0aec0;">—</td>'
            h += '</tr>'
            row_idx += 1

    h += '</tbody></table></div>'
    return h
