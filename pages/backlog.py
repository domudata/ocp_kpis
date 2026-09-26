# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd

from components.backlog_widgets import render_backlog_tab


def render_backlog_page(dfp: pd.DataFrame, vp: list, *args, **kwargs) -> None:
    df_toutes_dates = kwargs.get('df_toutes_dates', args[0] if len(args) > 0 else None)
    hist_df = kwargs.get('hist_df', args[1] if len(args) > 1 else None)
    render_backlog_tab(dfp, vp, df_toutes_dates=df_toutes_dates, hist_df=hist_df)
