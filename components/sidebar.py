# -*- coding: utf-8 -*-
import os
import time
from datetime import datetime

import streamlit as st

from components.header import get_logo_base64
from core.prepare_data import prepare_data


def render_sidebar(fichier_date: str, apm: list, df_full, av_full, now_ts):
    """
    Affiche la sidebar et retourne un dict avec tous les filtres/état.

    Retour : dict avec les clés
        unf, ot_f, av_f, sp, sa, sd, sdt, edt, vp,
        df_full, av_full, apm, now_ts
    """
    with st.sidebar:
        logo_b64 = get_logo_base64()
        if logo_b64:
            st.markdown(
                '<div style="display:flex;justify-content:center;padding:10px 0 15px 0;'
                'border-bottom:1px solid rgba(255,255,255,0.1);margin-bottom:10px;">'
                '<img src="data:image/png;base64,%s" style="max-width:100%%;height:auto;'
                'max-height:200px;object-fit:contain;border-radius:4px;"></div>' % logo_b64,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="padding:10px 0 4px 0">'
                '<div style="font-size:22px;margin-bottom:2px">⚙️</div>'
                '<div style="font-size:14px;font-weight:800;color:white">Filtres &amp; Parametres</div>'
                '<div style="font-size:11px;color:rgba(255,255,255,.5);text-transform:uppercase;letter-spacing:1px">Configuration</div>'
                '</div>',
                unsafe_allow_html=True,
            )

        if st.button("🔄 Rafraîchir le cache", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        show_filters = st.checkbox("✅ Afficher les filtres", value=True, key="show_filters")
        unf = ot_f = av_f = None

        if show_filters:
            unf = st.toggle("📁 Charger nouveaux fichiers", value=False, key="tf")
            if unf:
                pwd = st.text_input("Mot de passe administrateur", type="password")
                if pwd == "779900":
                    ot_f = st.file_uploader("Fichier OT",   type=["xlsx"], key="uot")
                    av_f = st.file_uploader("Fichier AVIS", type=["xlsx"], key="uav")
                    new_date = st.text_input("Entrez la date (JJ/MM/AAAA)", value=fichier_date)

                    from core.github_sync import is_configured as _gh_ok
                    push_gh = st.checkbox(
                        "☁️ Enregistrer aussi sur GitHub (écrase l'ancien fichier)",
                        value=_gh_ok(), disabled=not _gh_ok(),
                        help="Nécessite GITHUB_TOKEN et GITHUB_REPO dans les Secrets."
                        if not _gh_ok() else "Committe ot.xlsx/avis.xlsx/date.txt sur GitHub.",
                    )

                    if st.button("💾 Sauvegarder et Appliquer"):
                        try:
                            datetime.strptime(new_date, "%d/%m/%Y")
                            if ot_f is not None:
                                with open("ot.xlsx", "wb") as f:
                                    f.write(ot_f.getbuffer())
                            if av_f is not None:
                                with open("avis.xlsx", "wb") as f:
                                    f.write(av_f.getbuffer())
                            with open("date.txt", "w", encoding="utf-8") as f:
                                f.write(new_date)
                            st.success("Fichiers et date mis à jour localement !")

                            if push_gh:
                                from core.github_sync import push_multiple_files
                                files_to_push = {"date.txt": new_date.encode("utf-8")}
                                if ot_f is not None:
                                    files_to_push["ot.xlsx"] = ot_f.getvalue()
                                if av_f is not None:
                                    files_to_push["avis.xlsx"] = av_f.getvalue()
                                with st.spinner("☁️ Envoi vers GitHub..."):
                                    results = push_multiple_files(
                                        files_to_push,
                                        f"Mise a jour donnees KPI - {new_date}",
                                    )
                                for path, ok, msg in results:
                                    (st.success if ok else st.error)(msg)

                            time.sleep(2)
                            st.cache_data.clear()
                            st.rerun()
                        except ValueError:
                            st.error("Format de date invalide. Veuillez utiliser JJ/MM/AAAA.")
                elif pwd != "":
                    st.error("Mot de passe incorrect.")
            else:
                st.markdown(
                    '<div style="background:rgba(255,255,255,.1);padding:6px 10px;border-radius:6px;'
                    'border:1px solid rgba(255,255,255,.15)">'
                    '<div style="font-size:11px;color:rgba(255,255,255,.5);text-transform:uppercase;letter-spacing:1px">Donnees</div>'
                    '<div style="font-size:14px;color:white;font-weight:600;margin-top:2px">📅 %s</div>'
                    '</div>' % fichier_date,
                    unsafe_allow_html=True,
                )

            st.markdown("---")
            st.markdown("**🎯 Postes**")
            sp = st.multiselect("Poste", ["All"] + apm, ["All"], key="sp")
            st.markdown("**🏭 Atelier**")
            sa = st.multiselect(
                "Atelier",
                ["All", "Sulfurique (PS)", "Phosphorique (PP)", "Centrale (CU)",
                 "Engrais (TSP/REX)", "Feed (MCP/DCP)"],
                ["All"], key="sa",
            )
            st.markdown("**🏢 Division**")
            sd = st.multiselect("Division", ["All", "SF1", "SF2"], ["All"], key="sd")
            st.markdown("---")
            st.markdown("**📅 Periode**")
            dr = st.date_input(
                "Date debut planifiee",
                value=(datetime(2025, 1, 1).date(), datetime.today().date()),
                format="DD/MM/YYYY", key="dr",
            )
        else:
            sp = ["All"]; sa = ["All"]; sd = ["All"]
            dr = (datetime(2025, 1, 1).date(), datetime.today().date())

    # ── Résolution postes filtrés ──
    import pandas as pd

    if "All" in sp or not sp: sp = apm
    if "All" in sa or not sa: sa = ["All"]
    if "All" in sd or not sd: sd = ["All"]
    sdt = pd.to_datetime(dr[0]) if len(dr) == 2 else pd.to_datetime(datetime(2025, 1, 1))
    edt = pd.to_datetime(dr[1]) if len(dr) == 2 else pd.to_datetime(datetime.today())

    def mf(poste):
        p = str(poste).upper()
        if "All" not in sa:
            m = False
            if "Sulfurique (PS)"     in sa and "PS"  in p: m = True
            if "Phosphorique (PP)"   in sa and "PP"  in p: m = True
            if "Engrais (TSP/REX)"  in sa and ("TSP" in p or "REX" in p): m = True
            if "Feed (MCP/DCP)"     in sa and ("MCP" in p or "DCP" in p): m = True
            if "Centrale (CU)"      in sa and "CU"  in p: m = True
            if not m: return False
        if "All" not in sd:
            m = False
            if "SF1" in sd and "SF1" in p: m = True
            if "SF2" in sd and "SF2" in p: m = True
            if not m: return False
        return True

    vp = [p for p in apm if mf(p) and p in sp]

    # Rechargement si nouveaux fichiers
    if unf and ot_f is not None and av_f is not None:
        df_full, av_full, apm, now_ts = prepare_data(
            ot_f.getvalue(), av_f.getvalue(), fichier_date
        )

    return {
        "unf": unf, "ot_f": ot_f, "av_f": av_f,
        "sp": sp, "sa": sa, "sd": sd,
        "sdt": sdt, "edt": edt, "vp": vp,
        "df_full": df_full, "av_full": av_full,
        "apm": apm, "now_ts": now_ts,
    }
