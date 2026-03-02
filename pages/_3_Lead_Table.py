import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Lead Table — Outreach CRM", page_icon="📋", layout="wide")

@st.cache_data(ttl=300)
def load_data():
    csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "leads.csv")
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path, low_memory=False)
        df["quality_score"] = pd.to_numeric(df.get("quality_score", 0), errors="coerce").fillna(0).astype(int)
        return df
    return pd.DataFrame()

df = load_data()
for col, default in {"quality_score": 0, "lead_temperature": "Unknown", "pipeline_stage": "Found", "source": "", "warm_up_status": "Not started", "outreach_status": "Not contacted", "verified": "", "notes": ""}.items():
    if col not in df.columns:
        df[col] = default

from dashboard.components.lead_table import render
render(df)
