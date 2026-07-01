# -*- coding: utf-8 -*-
import io
import os

import pandas as pd
import streamlit as st
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side


def save_kpis_to_excel(prows, pcols, qrows, qcols,
                        ano_p_r, ano_p_c, ano_q_r, ano_q_c,
                        sheet_name: str) -> None:
    kpis_dir = "kpis"
    os.makedirs(kpis_dir, exist_ok=True)
    filepath = os.path.join(kpis_dir, "indicateurs_kpis.xlsx")

    sn = (
        str(sheet_name)
        .replace("/", "-").replace("\\", "-").replace("*", "")
        .replace("?", "").replace("[", "").replace("]", "")[:31]
    )

    hf  = Font(bold=True, color="FFFFFF", size=10)
    hfl = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
    tf  = Font(bold=True, size=12, color="1E3A5F")
    tb  = Border(
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

    rn = 1
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


def export_btn(df: pd.DataFrame, filename: str) -> None:
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine='openpyxl')
    buf.seek(0)
    st.download_button(
        "📥 Exporter Excel", data=buf,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
