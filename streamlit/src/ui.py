import streamlit as st
import pandas as pd

def page_header(title, description=None):
    st.title(title)
    if description:
        st.caption(description)

def season_filter(df, label="Temporada", key=None):
    seasons = sorted(df["season"].dropna().unique().tolist())
    return st.multiselect(
        label, seasons, default=seasons, key=key
    )

def apply_seasons(df, seasons):
    return df[df["season"].isin(seasons)].copy() if seasons else df.iloc[0:0].copy()

def dataframe(df, height=360, hide_index=True):
    st.dataframe(df, use_container_width=True, height=height, hide_index=hide_index)

def metric_row(items):
    cols = st.columns(len(items))
    for col, (label, value, help_text) in zip(cols, items):
        col.metric(label, value, help=help_text)

def correlation_metric(label, value, n):
    st.metric(label, f"{value:.3f}" if value == value else "—", help=f"n = {n}")

def insight(text):
    st.info(text)
