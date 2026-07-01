# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd

from components.backlog_widgets import render_backlog_tab


def render_backlog_page(dfp: pd.DataFrame, vp: list) -> None:
    render_backlog_tab(dfp, vp)
