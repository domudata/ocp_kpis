# -*- coding: utf-8 -*-
"""Export des KPI vers Excel (sauvegarde historique)."""
import os
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side


def save_kpis_to_excel(prows, pcols, qrows, qcols,
                       ano_p_r, ano_p_c, ano_q_r, ano_q_c,
                       sheet_name, output_dir="kpis"):
    """Sauvegarde les indicateurs dans kpis/indicateurs_kpis.xlsx."""
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, "indicateurs_kpis.xlsx")

    sn = str(sheet_name).replace("/", "-").replace("\\", "-").replace("*", "").replace(
        "?", "").replace("[", "").replace("]", "")[:31]

    hf = Font(bold=True, color="FFFFFF", size=10)
    hfl = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
    tf = Font(bold=True, size=12, color="1E3A5F")
    tb = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    try:
        wb = load_workbook(filepath)
    except Exception:
        wb = Workbook()
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]
    if sn in wb.sheetnames:
        del wb[sn]

    ws = wb.create_sheet(sn)
    rn = 1

    def ws_sec(title, cols, rows, sr):
        ws.cell(row=sr, column=1, value=title).font = tf
        sr += 1
        for j, c in enumerate(cols, 1):
            cl = ws.cell(row=sr, column=j, value=c)
            cl.font = hf
            cl.fill = hfl
            cl.alignment = Alignment(horizontal='center')
            cl.border = tb
        sr += 1
        for r in rows:
            for j, c in enumerate(cols, 1):
                cl = ws.cell(row=sr, column=j, value=r.get(c, ""))
                cl.border = tb
                cl.alignment = Alignment(horizontal='center')
            sr += 1
        return sr + 1

    rn = ws_sec("INDICATEURS DE PERFORMANCE", pcols, prows, rn)
    if ano_p_c and ano_p_r:
        rn = ws_sec("ANOMALIES PERFORMANCE", ano_p_c, ano_p_r, rn)
    rn = ws_sec("INDICATEURS DE QUALITE", qcols, qrows, rn)
    if ano_q_c and ano_q_r:
        rn = ws_sec("ANOMALIES QUALITE", ano_q_c, ano_q_r, rn)

    try:
        wb.save(filepath)
    except Exception:
        pass

    return filepath
