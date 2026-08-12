# -*- coding: utf-8 -*-
import math
import pandas as pd

from core.constants import CIBLE, LOWER_BETTER

_sparkline_uid = 0

def make_sparkline_svg(values, width=90, height=30, color="#3b82f6", stroke_w=1.8) -> str:
    global _sparkline_uid
    _sparkline_uid += 1
    gid = f"spG{_sparkline_uid}"

    clean = []
    for v in values:
        try:
            fv = float(v)
            if math.isfinite(fv):
                clean.append(fv)
        except (ValueError, TypeError):
            continue

    if len(clean) < 2:
        return ""

    mn, mx = min(clean), max(clean)
    rng = mx - mn if mx != mn else 1.0
    pad = 3
    pw, ph = width - 2 * pad, height - 2 * pad
    n = len(clean)

    def get_xy(i, v):
        x = pad + (i / (n - 1)) * pw if n > 1 else width / 2
        y = pad + ph - ((v - mn) / rng) * ph
        return x, y

    pts = [get_xy(i, v) for i, v in enumerate(clean)]
    line_d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area_d = line_d + f" L{pts[-1][0]:.1f},{height - pad} L{pts[0][0]:.1f},{height - pad} Z"
    fx, fy = pts[0]
    lx, ly = pts[-1]

    # Points (cercles) sur CHAQUE valeur de la serie, avec titre (tooltip)
    # affichant la valeur exacte au survol -> repond a la demande
    # "montrer sur les sparklines les points des valeurs".
    dots = ""
    for i, (x, y) in enumerate(pts):
        r = 2.2 if (i == 0 or i == n - 1) else 1.6
        dots += (
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{color}" '
            f'stroke="#fff" stroke-width="0.6">'
            f'<title>{clean[i]:.1f}</title></circle>'
        )

    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{color}" stop-opacity="0.25"/>'
        f'<stop offset="100%" stop-color="{color}" stop-opacity="0"/>'
        f'</linearGradient></defs>'
        f'<path d="{area_d}" fill="url(#{gid})" stroke="none"/>'
        f'<path d="{line_d}" fill="none" stroke="{color}" stroke-width="{stroke_w}" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f'{dots}'
        f'<circle cx="{fx:.1f}" cy="{fy:.1f}" r="0" fill="none"/>'
        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="0" fill="none"/>'
        f'</svg>'
    )

def _spark_pivot(hist_df: pd.DataFrame, kpi_name: str, section: str) -> pd.DataFrame:
    if hist_df.empty:
        return pd.DataFrame()
    sub = hist_df[hist_df["_section"] == section].copy()
    if kpi_name not in sub.columns or "Poste de travail" not in sub.columns:
        return pd.DataFrame()
    sub["Date_str"] = sub["Date_parsed"].dt.strftime("%d/%m/%Y")
    pv = sub.pivot_table(
        index="Poste de travail", columns="Date_str",
        values=kpi_name, aggfunc="first",
    )
    return pv.sort_index(axis=1)

def get_spark_color(v) -> str:
    if pd.isna(v): return "#cbd5e0"
    if v >= 90: return "#10b981"
    if v >= 80: return "#f59e0b"
    return "#ef4444"

def get_sparkline_html(scores: list) -> str:
    n = len(scores)
    if n == 0:
        return ""
    W, H = 130, 35
    pad = 5

    def get_xy(i, v):
        x = pad + (i / (n - 1) * (W - 2 * pad)) if n > 1 else W / 2
        v_disp = max(0, min(100, v if pd.notna(v) else 0))
        y = H - pad - (v_disp / 100 * (H - 2 * pad))
        return x, y

    svg = f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">'
    for i in range(n - 1):
        x1, y1 = get_xy(i, scores[i])
        x2, y2 = get_xy(i + 1, scores[i + 1])
        col = get_spark_color(scores[i + 1])
        svg += f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{col}" stroke-width="2" stroke-linecap="round"/>'
    for i, v in enumerate(scores):
        x, y = get_xy(i, v)
        col = get_spark_color(v)
        r = 3 if i == n - 1 else 2
        svg += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{col}" stroke="#fff" stroke-width="0.8"><title>{v:.1f}</title></circle>'
    svg += '</svg>'
    return svg

def get_comparison_html(scores: list) -> str:
    if not scores:
        return '<span style="color:#94a3b8;font-size:11px;">N/A</span>'
    if len(scores) == 1:
        return '<span style="color:#94a3b8;font-size:11px;">Première mesure disponible</span>'
    prev, curr = scores[-2], scores[-1]
    if prev == 0:
        return '<span style="color:#94a3b8;">➜ Stable</span>'
    pct = ((curr - prev) / prev) * 100
    if pct > 0.05:
        return f'<span style="color:#10b981;font-weight:600;">▲ +{pct:.1f}% — Amélioration</span>'
    elif pct < -0.05:
        return f'<span style="color:#ef4444;font-weight:600;">▼ {pct:.1f}% — Dégradation</span>'
    return '<span style="color:#94a3b8;">➜ Stable</span>'

def render_sparkline_table(hist_df: pd.DataFrame, kpi_list: list,
                            section_label: str, table_css: str = "") -> str:
    sec_map = {"Performance": "perf", "Qualité": "qual", "Qualite": "qual"}
    sec_key = sec_map.get(section_label, section_label)

    if hist_df.empty:
        return '<div style="padding:12px;color:#94a3b8;">Aucune donnée historique. Enregistrez au moins 2 périodes.</div>'

    dates = sorted(hist_df["Date_parsed"].dropna().unique())
    if len(dates) < 2:
        return '<div style="padding:12px;color:#94a3b8;">Minimum 2 périodes requises pour afficher les sparklines.</div>'

    sub = hist_df[hist_df["_section"] == sec_key]
    postes = sorted(sub["Poste de travail"].dropna().unique())
    if not postes:
        return '<div style="padding:12px;color:#94a3b8;">Aucun poste trouvé.</div>'

    pivots = {kpi: _spark_pivot(hist_df, kpi, sec_key) for kpi in kpi_list}
    pivots = {k: v for k, v in pivots.items() if not v.empty}
    if not pivots:
        return '<div style="padding:12px;color:#94a3b8;">Aucune donnée KPI trouvée pour cette section.</div>'

    nb = len(dates)
    d_labels = [pd.Timestamp(d).strftime("%d/%m/%Y") for d in dates]

    h = (
        f'<div style="margin-bottom:8px;font-size:12px;color:#64748b;">'
        f'📊 {nb} période(s) : {" → ".join(d_labels[:6])}'
        f'{"…" if len(d_labels) > 6 else ""}</div>'
    )

    h += '<table style="width:100%;border-collapse:collapse;font-size:12px;">'
    h += '<tr style="background:#f1f5f9;"><th style="padding:6px;text-align:left;">Poste de travail</th>'
    for kpi in kpi_list:
        if kpi in pivots:
            cible = CIBLE.get(kpi, 100)
            arrow = "↓" if kpi in LOWER_BETTER else "↑"
            h += (f'<th style="padding:6px;text-align:center;min-width:110px;">{kpi}<br>'
                  f'<span style="font-weight:400;color:#94a3b8;">Cible {arrow}{cible}%</span></th>')
    h += '</tr>'

    for poste in postes:
        h += f'<tr style="border-top:1px solid #e2e8f0;"><td style="padding:6px;font-weight:600;">{poste}</td>'
        for kpi in kpi_list:
            if kpi not in pivots or poste not in pivots[kpi].index:
                h += '<td style="text-align:center;color:#cbd5e0;">—</td>'
                continue
            vals = pivots[kpi].loc[poste].values.tolist()
            last = vals[-1] if vals else None
            first = vals[0] if vals else None
            cible = CIBLE.get(kpi, 100)
            clr = "#10b981" if (last is not None and (last <= cible if kpi in LOWER_BETTER else last >= cible)) else "#ef4444"
            svg = make_sparkline_svg(vals, color=clr)

            var_html = ""
            if first is not None and last is not None and first != 0:
                pct = ((last - first) / abs(first)) * 100
                if pct > 0.5:
                    var_html = f'<span style="color:#10b981;">▲+{pct:.1f}%</span>'
                elif pct < -0.5:
                    var_html = f'<span style="color:#ef4444;">▼{pct:.1f}%</span>'
                else:
                    var_html = '<span style="color:#94a3b8;">→0%</span>'

            v_str = f'{last:.1f}%' if last is not None else '—'
            if svg:
                h += (f'<td style="text-align:center;padding:4px;">{svg}<br>'
                      f'<b>{v_str}</b> {var_html}</td>')
            else:
                h += f'<td style="text-align:center;">{v_str}</td>'
        h += '</tr>'

    h += '</table>'
    return h

def render_anomaly_sparkline_table(hist_df: pd.DataFrame, kpi_list: list,
                                    ano_section_key: str) -> str:
    """NOUVEAU : équivalent de render_sparkline_table, mais pour les
    NOMBRES D'ANOMALIES (colonnes de ano_perf/ano_qual) plutôt que les
    valeurs de KPI. Sémantique toujours "plus bas = mieux", vert si 0
    anomalie, rouge sinon (pas de notion de cible en %).
    ano_section_key : "ano_perf" ou "ano_qual".
    """
    if hist_df.empty:
        return '<div style="padding:12px;color:#94a3b8;">Aucune donnée historique d\'anomalies. Enregistrez au moins 2 périodes.</div>'

    dates = sorted(hist_df["Date_parsed"].dropna().unique())
    if len(dates) < 2:
        return '<div style="padding:12px;color:#94a3b8;">Minimum 2 périodes requises pour afficher les sparklines.</div>'

    sub = hist_df[hist_df["_section"] == ano_section_key]
    if sub.empty or "Poste de travail" not in sub.columns:
        return '<div style="padding:12px;color:#94a3b8;">Aucune donnée d\'anomalies trouvée pour cette section.</div>'
    postes = sorted(sub["Poste de travail"].dropna().unique())
    if not postes:
        return '<div style="padding:12px;color:#94a3b8;">Aucun poste trouvé.</div>'

    all_cols = kpi_list + ["Total Anomalies"]
    pivots = {kpi: _spark_pivot(hist_df, kpi, ano_section_key) for kpi in all_cols}
    pivots = {k: v for k, v in pivots.items() if not v.empty}
    if not pivots:
        return '<div style="padding:12px;color:#94a3b8;">Aucune colonne d\'anomalies trouvée.</div>'

    nb = len(dates)
    d_labels = [pd.Timestamp(d).strftime("%d/%m/%Y") for d in dates]

    h = (
        f'<div style="margin-bottom:8px;font-size:12px;color:#64748b;">'
        f'🔺 {nb} période(s) : {" → ".join(d_labels[:6])}'
        f'{"…" if len(d_labels) > 6 else ""}</div>'
    )

    h += '<table style="width:100%;border-collapse:collapse;font-size:12px;">'
    h += '<tr style="background:#fef2f2;"><th style="padding:6px;text-align:left;">Poste de travail</th>'
    for kpi in all_cols:
        if kpi in pivots:
            label = "TOTAL" if kpi == "Total Anomalies" else kpi
            h += f'<th style="padding:6px;text-align:center;min-width:100px;">{label}</th>'
    h += '</tr>'

    for poste in postes:
        h += f'<tr style="border-top:1px solid #e2e8f0;"><td style="padding:6px;font-weight:600;">{poste}</td>'
        for kpi in all_cols:
            if kpi not in pivots or poste not in pivots[kpi].index:
                h += '<td style="text-align:center;color:#cbd5e0;">—</td>'
                continue
            vals = pivots[kpi].loc[poste].values.tolist()
            last = vals[-1] if vals else None
            first = vals[0] if vals else None
            clr = "#10b981" if (last is not None and last == 0) else "#ef4444"
            svg = make_sparkline_svg(vals, color=clr)

            var_html = ""
            if first is not None and last is not None:
                diff = last - first
                if diff > 0:
                    var_html = f'<span style="color:#ef4444;">▲+{diff:.0f}</span>'
                elif diff < 0:
                    var_html = f'<span style="color:#10b981;">▼{diff:.0f}</span>'
                else:
                    var_html = '<span style="color:#94a3b8;">→0</span>'

            v_str = f'{last:.0f}' if last is not None else '—'
            if svg:
                h += (f'<td style="text-align:center;padding:4px;">{svg}<br>'
                      f'<b>{v_str}</b> {var_html}</td>')
            else:
                h += f'<td style="text-align:center;">{v_str}</td>'
        h += '</tr>'

    h += '</table>'
    return h
