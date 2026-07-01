# -*- coding: utf-8 -*-
import base64
import os
import streamlit as st


def get_logo_base64() -> str | None:
    for path in ["logo.png", "./logo.png", "../logo.png"]:
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    return base64.b64encode(f.read()).decode()
            except Exception:
                pass
    return None


def render_header(fichier_date: str) -> None:
    logo_b64 = get_logo_base64()
    if logo_b64:
        st.markdown(
            f'<div class="mh">'
            f'<img src="data:image/png;base64,{logo_b64}" class="logo" alt="Logo">'
            f'<h1>Tableau de Bord KPIs Performance &amp; Qualite</h1>'
            f'<span class="db">📅 {fichier_date}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="mh">'
            f'<h1>Tableau de Bord KPIs Performance &amp; Qualite</h1>'
            f'<span class="db">📅 {fichier_date}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
