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

    hf = Font(bold=True, color="FFFFFF", size=10)
    hfl = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
    tf = Font(bold=True, size=12, color="1E3A5F")
    tb = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    # CORRIGÉ : chaque étape à risque (création dossier, écriture disque)
    # est maintenant tracée avec un message explicite dans la sidebar en
    # cas d'échec, au lieu d'un `except: pass` qui avalait silencieusement
    # toute erreur (permissions, disque en lecture seule sur Streamlit
    # Cloud, etc.) — l'app continuait à tourner normalement sans que la
    # date ne soit réellement sauvegardée, sans aucun signal visible.
    try:
        os.makedirs(kpis_dir, exist_ok=True)
    except Exception as e:
        st.sidebar.error(f"❌ Impossible de créer le dossier '{kpis_dir}/' : {e}")
        return

    filepath = os.path.join(kpis_dir, "indicateurs_kpis.xlsx")

    sn = (
        str(sheet_name)
        .replace("/", "-").replace("\\", "-").replace("*", "")
        .replace("?", "").replace("[", "").replace("]", "")[:31]
    )

    try:
        wb = load_workbook(filepath)
    except FileNotFoundError:
        wb = Workbook()
    except Exception as e:
        st.sidebar.error(f"❌ Impossible d'ouvrir '{filepath}' (fichier corrompu ?) : {e}")
        return

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
    except Exception as e:
        st.sidebar.error(
            f"❌ Échec de la sauvegarde de l'historique ('{filepath}') : {e}\n\n"
            f"La date '{sn}' n'a PAS été enregistrée. Téléchargez quand même "
            f"le fichier via le bouton de secours ci-dessous si besoin."
        )
        # Filet de secours : proposer le téléchargement direct du classeur
        # en mémoire, même si l'écriture disque a échoué, pour ne pas
        # perdre les données de cette extraction.
        try:
            buf = io.BytesIO()
            wb.save(buf)
            buf.seek(0)
            st.sidebar.download_button(
                "⬇️ Télécharger quand même (sauvegarde disque échouée)",
                data=buf, file_name="indicateurs_kpis.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"fallback_dl_{sn}",
            )
        except Exception:
            pass
        return

    # Confirmation visible que la sauvegarde a réussi (absente avant).
    st.sidebar.success(f"✅ Historique mis à jour : date '{sn}' enregistrée dans {filepath}")

def export_btn(df: pd.DataFrame, filename: str) -> None:
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine='openpyxl')
    buf.seek(0)
    st.download_button(
        "📥 Exporter Excel", data=buf,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
