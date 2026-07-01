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

    pts     = [get_xy(i, v) for i, v in enumerate(clean)]
    line_d  = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area_d  = line_d + f" L{pts[-1][0]:.1f},{height - pad} L{pts[0][0]:.1f},{height - pad} Z"
    fx, fy  = pts[0]
    lx, ly  = pts[-1]

    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{color}" stop-opacity="0.30"/>'
        f'<stop offset="100%" stop-color="{color}" stop-opacity="0.02"/>'
        f'</linearGradient></defs>'
        f'<path d="{area_d}" fill="url(#{gid})"/>'
        f'<path d="{line_d}" fill="none" stroke="{color}" stroke-width="{stroke_w}" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="{fx:.1f}" cy="{fy:.1f}" r="2" fill="#94a3b8"/>'
        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="2.8" fill="{color}" stroke="#fff" stroke-width="1"/>'
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
    if pd.isna(v):  return "#cbd5e0"
    if v >= 90:     return "#10b981"
    if v >= 80:     return "#f59e0b"
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
        svg += f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{col}" stroke-width="2.5" />'
    for i, v in enumerate(scores):
        x, y = get_xy(i, v)
        col  = get_spark_color(v)
        svg += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{col}" />'
    svg += '</svg>'
    return svg


def get_comparison_html(scores: list) -> str:
    if not scores:
        return '<span style="color:#94a3b8">N/A</span>'
    if len(scores) == 1:
        return '<span style="color:#94a3b8">Première mesure disponible</span>'
    prev, curr = scores[-2], scores[-1]
    if prev == 0:
        return '<span style="color:#94a3b8">➜ Stable</span>'
    pct = ((curr - prev) / prev) * 100
    if pct > 0.05:
        return f'<span style="color:#10b981;font-weight:600">▲ +{pct:.1f} % — Amélioration</span>'
    elif pct < -0.05:
        return f'<span style="color:#ef4444;font-weight:600">▼ {pct:.1f} % — Dégradation</span>'
    return '<span style="color:#94a3b8;font-weight:600">➜ Stable</span>'


def render_sparkline_table(hist_df: pd.DataFrame, kpi_list: list,
                            section_label: str, table_css: str) -> str:
    sec_map = {"Performance": "perf", "Qualité": "qual", "Qualite": "qual"}
    sec_key = sec_map.get(section_label, section_label)

    if hist_df.empty:
        return '<div class="es">Aucune donnée historique. Enregistrez au moins 2 périodes.</div>'

    dates = sorted(hist_df["Date_parsed"].dropna().unique())
    if len(dates) < 2:
        return '<div class="es">Minimum 2 périodes requises pour afficher les sparklines.</div>'

    sub    = hist_df[hist_df["_section"] == sec_key]
    postes = sorted(sub["Poste de travail"].dropna().unique())
    if not postes:
        return '<div class="es">Aucun poste trouvé.</div>'

    pivots = {kpi: _spark_pivot(hist_df, kpi, sec_key) for kpi in kpi_list}
    pivots = {k: v for k, v in pivots.items() if not v.empty}
    if not pivots:
        return '<div class="es">Aucune donnée KPI trouvée pour cette section.</div>'

    nb       = len(dates)
    d_labels = [d.strftime("%d/%m/%Y") for d in dates]

    h = (
        f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;'
        f'padding:8px 14px;background:#f0f9ff;border-radius:8px;border:1px solid #bae6fd">'
        f'<span style="font-size:13px;font-weight:700;color:#0369a1">'
        f'📊 {nb} période(s) : {" → ".join(d_labels[:6])}'
        f'{"…" if len(d_labels) > 6 else ""}</span></div>'
    )

    h += f'<table class="tw {table_css}"><thead><tr><th>Poste de travail</th>'
    for kpi in kpi_list:
        if kpi in pivots:
            cible = CIBLE.get(kpi, 100)
            arrow = "↓" if kpi in LOWER_BETTER else "↑"
            h += (f'<th style="min-width:130px">{kpi}<br>'
                  f'<span style="font-size:9px;font-weight:400;opacity:.85">'
                  f'Cible {arrow}{cible}%</span></th>')
    h += '</tr></thead><tbody>'

    for poste in postes:
        h += f'<tr><td style="font-weight:700">{poste}</td>'
        for kpi in kpi_list:
            if kpi not in pivots or poste not in pivots[kpi].index:
                h += '<td class="spark-cell">—</td>'
                continue
            vals  = pivots[kpi].loc[poste].values.tolist()
            last  = vals[-1] if vals else None
            first = vals[0]  if vals else None
            cible = CIBLE.get(kpi, 100)
            clr   = "#10b981" if (last is not None and (last <= cible if kpi in LOWER_BETTER else last >= cible)) else "#ef4444"
            svg   = make_sparkline_svg(vals, color=clr)

            var_html = ""
            if first is not None and last is not None and first != 0:
                pct = ((last - first) / abs(first)) * 100
                if pct > 0.5:
                    var_html = f'<span style="color:#10b981;font-size:9px;font-weight:800"> ▲+{pct:.1f}%</span>'
                elif pct < -0.5:
                    var_html = f'<span style="color:#ef4444;font-size:9px;font-weight:800"> ▼{pct:.1f}%</span>'
                else:
                    var_html = f'<span style="color:#f59e0b;font-size:9px;font-weight:800"> →0%</span>'

            v_str = f'{last:.1f}%' if last is not None else '—'
            if svg:
                h += (f'<td class="spark-cell">{svg}<br>'
                      f'<span style="font-size:11px;font-weight:800;color:{clr}">'
                      f'{v_str}</span>{var_html}</td>')
            else:
                h += f'<td class="spark-cell"><span style="font-size:11px;font-weight:700">{v_str}</span></td>'
        h += '</tr>'

    h += '</tbody></table>'
    return h
