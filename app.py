import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import plotly.graph_objects as go

st.set_page_config(layout="wide")

# Sessioasetukset
if "interval" not in st.session_state:
    st.session_state.interval = "1 h"
if "last_updated" not in st.session_state:
    st.session_state.last_updated = None
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = False
if "data" not in st.session_state:
    st.session_state.data = None

# Datahaku
def fetch_data():
    now = datetime.utcnow()
    start_time = now - timedelta(hours=1)
    from_param = start_time.strftime("%Y-%m-%d")
    url = f"https://driftsdata.statnett.no/restapi/Frequency/BySecond?From={from_param}"

    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    start_point_utc = data["StartPointUTC"]
    period_tick_ms = data["PeriodTickMs"]
    measurements = data["Measurements"]

    if not measurements:
        return pd.DataFrame()

    start_dt = datetime(1970, 1, 1) + timedelta(milliseconds=start_point_utc)
    period_sec = period_tick_ms / 1000

    df = pd.DataFrame(measurements, columns=["FrequencyHz"])
    df["Index"] = df.index
    df["Timestamp"] = df["Index"].apply(lambda i: start_dt + timedelta(seconds=i * period_sec))
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    df["Time_10s"] = df["Timestamp"].dt.floor("10S")
    grouped = df.groupby("Time_10s").agg(FrequencyHz=("FrequencyHz", "mean")).reset_index()
    grouped.rename(columns={"Time_10s": "Timestamp"}, inplace=True)

    return grouped

# Automaattinen päivitys
if st.session_state.auto_refresh:
    st.experimental_rerun()

# Näkymävalinta
view_option = st.radio("", ["Kaavio", "Taulukko"], horizontal=True, label_visibility="collapsed")

# Painikkeet ja valinnat keskitetysti
st.markdown
