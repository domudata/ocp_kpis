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

    # ── NOUVEAU : synchronisation GitHub-first ──────────────────────────
    # Avant de charger le fichier local, on tente de récupérer la
    # DERNIÈRE version publiée sur GitHub et on l'utilise comme point de
    # départ si elle est plus complète que ce qu'il y a en local (ou si
    # rien n'existe en local). Ça évite de perdre l'historique quand le
    # disque local de l'app a été réinitialisé entre deux sessions
    # (redémarrage Streamlit Cloud) — le seul cas où on perdrait des
    # dates malgré cette synchronisation est si GitHub lui-même n'a
    # jamais reçu la publication (vérifier GITHUB_TOKEN/GITHUB_REPO).
    try:
        from core.github_publish import download_file as _gh_download, is_configured as _gh_is_configured
        if _gh_is_configured():
            _remote_bytes, _dl_err = _gh_download("kpis/indicateurs_kpis.xlsx")
            if _remote_bytes:
                _use_remote = True
                if os.path.exists(filepath):
                    try:
                        _local_wb = load_workbook(filepath, read_only=True)
                        _remote_wb = load_workbook(io.BytesIO(_remote_bytes), read_only=True)
                        # Ne remplace le local que si le distant a AUTANT
                        # ou PLUS de dates (feuilles) que le local — pour
                        # ne jamais régresser si, par ordre d'exécution,
                        # le local avait exceptionnellement plus de dates
                        # que la dernière version publiée.
                        _use_remote = len(_remote_wb.sheetnames) >= len(_local_wb.sheetnames)
                        _local_wb.close()
                        _remote_wb.close()
                    except Exception:
                        _use_remote = True
                if _use_remote:
                    with open(filepath, "wb") as _f:
                        _f.write(_remote_bytes)
            elif _dl_err:
                st.sidebar.caption(f"ℹ️ Historique GitHub non récupéré avant fusion : {_dl_err}")
    except Exception as _sync_e:
        st.sidebar.caption(f"ℹ️ Synchronisation GitHub avant fusion ignorée : {_sync_e}")

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
