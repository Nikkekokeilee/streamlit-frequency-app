import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import plotly.graph_objects as go

st.set_page_config(layout="wide")

# ✅ Validate API key
if "FINGRID_API_KEY" not in st.secrets:
    st.error("Fingridin API-avainta ei ole määritetty. Lisää se tiedostoon .streamlit/secrets.toml avaimella 'FINGRID_API_KEY'.")
    st.stop()

api_key = st.secrets["FINGRID_API_KEY"]

# Session state initialization
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

# Fetch data from Statnett
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

# Update data
def update_data():
    st.session_state.data = fetch_data()
    st.session_state.last_updated = datetime.utcnow()
    st.session_state.last_fetch_time = datetime.utcnow()

# Tabs
tab1, tab2, tab3 = st.tabs(["Kaavio", "Taulukko", "Suomen taajuus"])

# Controls
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

# Auto refresh
if st.session_state.auto_refresh:
    now = datetime.utcnow()
    if (now - st.session_state.last_fetch_time).total_seconds() > 60:
        update_data()

# Last updated
if st.session_state.last_updated:
    st.caption(f"Viimeisin päivitys: {st.session_state.last_updated.strftime('%H:%M:%S')} UTC")

# Initial data fetch
if st.session_state.data is None:
    update_data()

data = st.session_state.data

# Filter data
interval_minutes = {"10 min": 10, "30 min": 30, "1 h": 60}
cutoff = datetime.utcnow() - timedelta(minutes=interval_minutes[st.session_state.interval])
filtered = data[data["Timestamp"] >= cutoff]

# Chart tab
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
            yaxis_title="Taajuus (Hz)",
            height=600,
            margin=dict(t=10)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Ei dataa valitulla aikavälillä.")

# Table tab
with tab2:
    sorted_table = filtered.sort_values(by="Timestamp", ascending=False).reset_index(drop=True)
    st.dataframe(sorted_table[["Timestamp", "FrequencyHz"]], use_container_width=True)

# Fingrid frequency tab
with tab3:
    now = datetime.utcnow()
    start_time = now - timedelta(minutes=interval_minutes[st.session_state.interval])
    fingrid_url = (
        f"https://data.fingrid.fi/api/datasets/177/data?"
        f"startTime={start_time.isoformat()}Z&endTime={now.isoformat()}Z"
    )
    headers = {"x-api-key": api_key}
    try:
        response = requests.get(fingrid_url, headers=headers)
        response.raise_for_status()
        fi_data = response.json()
        df_fi = pd.DataFrame(fi_data["data"])
        df_fi["Timestamp"] = pd.to_datetime(df_fi["startTime"])
        df_fi["FrequencyHz"] = df_fi["value"]
        filtered_fi = df_fi[["Timestamp", "FrequencyHz"]]
    except Exception as e:
        st.error(f"Virhe haettaessa Fingridin dataa: {e}")
        filtered_fi = pd.DataFrame()

    if not filtered_fi.empty:
        y_min = filtered_fi["FrequencyHz"].min()
        y_max = filtered_fi["FrequencyHz"].max()
        y_axis_min = y_min - 0.05
        y_axis_max = y_max + 0.05

        fig_fi = go.Figure()

        fig_fi.add_shape(
            type="rect", xref="x", yref="y",
            x0=filtered_fi["Timestamp"].min(), x1=filtered_fi["Timestamp"].max(),
            y0=y_axis_min, y1=min(49.97, y_axis_max),
            fillcolor="rgba(255,0,0,0.1)", line_width=0, layer="below"
        )

        fig_fi.add_shape(
            type="rect", xref="x", yref="y",
            x0=filtered_fi["Timestamp"].min(), x1=filtered_fi["Timestamp"].max(),
            y0=max(50.03, y_axis_min), y1=y_axis_max,
            fillcolor="rgba(0,0,255,0.1)", line_width=0, layer="below"
        )

        fig_fi.add_trace(go.Scatter(x=filtered_fi["Timestamp"], y=filtered_fi["FrequencyHz"],
                                    mode="lines+markers", line=dict(color="black")))

        fig_fi.update_layout(
            xaxis_title="Aika (UTC)",
            yaxis_title="Taajuus (Hz)",
            height=600,
            margin=dict(t=10)
        )
        st.plotly_chart(fig_fi, use_container_width=True)
    else:
        st.warning("Ei dataa saatavilla Fingridiltä.")

