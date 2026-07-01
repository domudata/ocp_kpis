# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
from core.constants import CIBLE, LOWER_BETTER
from core.calcul_kpi import build_statut_pivot

def html_statut_pivot(piv_df, table_class):
    cols=["Poste de travail","CRÉÉ","LANC","CLOT","TCLO","Total"]
    sc = {"CRÉÉ":"background:#fef3c7;color:#92400e;font-weight:600;","LANC":"background:#dbeafe;color:#1e40af;font-weight:600;","CLOT":"background:#d1fae5;color:#065f46;font-weight:600;","TCLO":"background:#a7f3d0;color:#064e3b;font-weight:600;","Total":"background:#ede9fe;color:#5b21b6;font-weight:700;"}
    h='<table class="tw %s"><thead><tr>'%table_class+''.join('<th>%s</th>'%c for c in cols)+'</tr></thead><tbody>'
    for poste,row in piv_df.iterrows():
        h+='<tr><td style="font-weight:700">%s</td>'%poste
        for c in ["CRÉÉ","LANC","CLOT","TCLO"]: h+='<td style="text-align:center;%s">%d</td>'%(sc[c], int(row.get(c,0)))
        h+='<td style="text-align:center;%s">%d</td>'%(sc["Total"], int(row.get("Total",0)))+'</tr>'
    h+='<tr><td style="font-weight:800">Total</td>'
    for c in ["CRÉÉ","LANC","CLOT","TCLO"]: h+='<td style="text-align:center;font-weight:800;%s">%d</td>'%(sc[c], int(piv_df[c].sum()))
    h+='<td style="text-align:center;font-weight:800;%s">%d</td>'%(sc["Total"], int(piv_df["Total"].sum()))+'</tr></tbody></table>'
    return h

def render_kpi_table(rows, cols, table_class):
    h='<table class="tw %s"><thead><tr>'%table_class+''.join('<th>%s</th>'%c for c in cols)+'</tr></thead><tbody>'
    for r in rows:
        is_cb = str(r.get("Poste de travail","")) == "CIBLE"
        h+='<tr class="cb" if is_cb else ""><tr>'
        for j,c in enumerate(cols):
            val=r.get(c,"")
            if j==0: h+='<td style="font-weight:700">%s</td>'%val
            else:
                style=""
                try:
                    v=float(val); cible=CIBLE.get(c,100)
                    if is_cb: style=""
                    elif c in LOWER_BETTER:
                        if v<=cible: style="background:#d1fae5;color:#065f46;font-weight:700"
                        elif v<=cible*1.5: style="background:#fef3c7;color:#92400e;font-weight:600"
                        else: style="background:#fee2e2;color:#991b1b;font-weight:700"
                    else:
                        if v>=cible: style="background:#d1fae5;color:#065f46;font-weight:700"
                        elif v>=cible*0.8: style="background:#fef3c7;color:#92400e;font-weight:600"
                        else: style="background:#fee2e2;color:#991b1b;font-weight:700"
                except: pass
                h+='<td style="text-align:center;%s">%s</td>'%(style, val)
        h+='</tr>'
    h+='</tbody></table>'
    st.markdown(h, unsafe_allow_html=True)

def render_anomaly_table(rows, cols):
    if not rows:
        st.markdown('<div class="es">✅ Aucune anomalie détectée</div>', unsafe_allow_html=True); return
    h='<table class="tw at"><thead><tr>'+''.join('<th>%s</th>'%c for c in cols)+'</tr></thead><tbody>'
    for r in rows:
        h+='<tr>'
        for c in cols:
            v=r.get(c,"")
            if c=="Poste de travail": h+='<td style="font-weight:700">%s</td>'%v
            else: h+='<td style="text-align:center">%s</td>'%v
        h+='</tr>'
    h+='</tbody></table>'
    st.markdown(h, unsafe_allow_html=True)
