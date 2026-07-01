# -*- coding: utf-8 -*-
"""Génération de sparklines SVG inline pour les tableaux."""
# ── RECONSTRUIT ──


def sparkline_svg(values, width=80, height=24, color="#3b82f6"):
    """
    Génère un SVG de sparkline à insérer dans un <td>.
    values : liste de nombres
    Retourne une chaîne HTML <svg>...</svg>
    """
    if not values or len(values) < 2:
        return ""

    import numpy as np

    vals = [float(v) for v in values if v is not None]
    if len(vals) < 2:
        return ""

    min_v = min(vals)
    max_v = max(vals)
    range_v = max_v - min_v if max_v != min_v else 1

    points = []
    for i, v in enumerate(vals):
        x = (i / (len(vals) - 1)) * width
        y = height - ((v - min_v) / range_v) * (height - 4) - 2
        points.append(f"{x:.1f},{y:.1f}")

    polyline = " ".join(points)

    # Déterminer couleur selon tendance
    if vals[-1] > vals[0]:
        color = "#10b981"  # vert = hausse
    elif vals[-1] < vals[0]:
        color = "#ef4444"  # rouge = baisse
    else:
        color = "#f59e0b"  # jaune = stable

    svg = (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="1.5" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f'</svg>'
    )
    return svg


def sparkline_cell(values, width=80, height=24):
    """Retourne le HTML complet d'une cellule avec sparkline."""
    svg = sparkline_svg(values, width, height)
    if not svg:
        return '<td class="spark-cell">-</td>'
    return f'<td class="spark-cell">{svg}</td>'
