import streamlit as st
import pandas as pd
import numpy as np
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
if "last_fetch_time" not in st.session_state:
    st.session_state.last_fetch_time = datetime.min

# Datahaku Norjan taajuudelle
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

# Päivitä data
def update_data():
    st.session_state.data = fetch_data()
    st.session_state.last_updated = datetime.utcnow()
    st.session_state.last_fetch_time = datetime.utcnow()

# Välilehdet
tab1, tab2, tab3 = st.tabs(["Kaavio", "Taulukko", "Suomen taajuus"])

# Painikkeet
st.markdown("<h4 style='text-align: center;'>Valinnat</h4>", unsafe_allow_html=True)
button_cols = st.columns([1, 1, 1, 1, 2], gap="small")

with button_cols[0]:
    if st.button("10 min"):
        st.session_state.interval = "10 min"
with button_cols[1]:
    if st.button("30 min"):
        st.session_state.interval = "30 min"
with button_cols[2]:
    if st.button("1 h"):
        st.session_state.interval = "1 h"
with button_cols[3]:
    if st.button("Päivitä"):
        update_data()
with button_cols[4]:
    st.session_state.auto_refresh = st.checkbox("Automaattipäivitys (1 min)", value=st.session_state.auto_refresh)

# Automaattinen päivitys
if st.session_state.auto_refresh:
    now = datetime.utcnow()
    if (now - st.session_state.last_fetch_time).total_seconds() > 60:
        update_data()

# Päivitysaika
if st.session_state.last_updated:
    st.caption(f"Viimeisin päivitys: {st.session_state.last_updated.strftime('%H:%M:%S')} UTC")

# Haetaan data tarvittaessa
if st.session_state.data is None:
    update_data()

data = st.session_state.data

# Suodatus
interval_minutes = {"10 min": 10, "30 min": 30, "1 h": 60}
cutoff = datetime.utcnow() - timedelta(minutes=interval_minutes[st.session_state.interval])
filtered = data[data["Timestamp"] >= cutoff]

# Kaavio
with tab1:
    if not filtered.empty:
        y_min = filtered["FrequencyHz"].min()
        y_max = filtered["FrequencyHz"].max()
        y_axis_min = y_min - 0.05
        y_axis_max = y_max + 0.05

        fig = go.Figure()

        fig.add_shape(
            type="rect", xref="x", yref="y",
            x0=filtered["Timestamp"].min(), x1=filtered["Timestamp"].max(),
            y0=y_axis_min, y1=min(49.97, y_axis_max),
            fillcolor="rgba(255,0,0,0.1)", line_width=0, layer="below"
        )

        fig.add_shape(
            type="rect", xref="x", yref="y",
            x0=filtered["Timestamp"].min(), x1=filtered["Timestamp"].max(),
            y0=max(50.03, y_axis_min), y1=y_axis_max,
            fillcolor="rgba(0,0,255,0.1)", line_width=0, layer="below"
        )

        fig.add_trace(go.Scatter(x=filtered["Timestamp"], y=filtered["FrequencyHz"],
                                 mode="lines+markers", line=dict(color="black")))

        fig.update_layout(
            xaxis_title="Aika (UTC)",
            yaxis_title="Taajuus 
