import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import plotly.graph_objects as go

st.set_page_config(layout="wide")

# Aseta oletusarvot sessioon
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
if "filtered_fi" not in st.session_state:
    st.session_state.filtered_fi = pd.DataFrame()

# Tarkista API-avain
if "FINGRID_API_KEY" not in st.secrets:
    st.error("Fingridin API-avainta ei ole määritetty. Lisää se Streamlitin Secrets-osioon avaimella 'FINGRID_API_KEY'.")
    st.stop()

api_key = st.secrets["FINGRID_API_KEY"]

interval_minutes = {"10 min": 10, "30 min": 30, "1 h": 60}

# Hae Norjan taajuusdata
def fetch_norway_data():
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

# Hae Suomen taajuusdata Fingridiltä
def fetch_fingrid_data():
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
        fi_data = response.json()["data"]
        df_fi = pd.DataFrame(fi_data)
        df_fi["Timestamp"] = pd.to_datetime(df_fi["startTime"], errors="coerce")
        df_fi["FrequencyHz"] = df_fi["value"]
        if df_fi["Timestamp"].isnull().all():
            st.error("Fingridin datassa ei ole kelvollisia aikaleimoja.")
            return pd.DataFrame()
        return df_fi[["Timestamp", "FrequencyHz"]]
    except Exception as e:
        st.error(f"Virhe haettaessa Fingridin dataa: {e}")
        return pd.DataFrame()

# Päivitä data
def update_data():
    st.session_state.data = fetch_norway_data()
    st.session_state.filtered_fi = fetch_fingrid_data()
    st.session_state.last_updated = datetime.utcnow()
    st.session_state.last_fetch_time = datetime.utcnow()

# Käynnistä päivitys tarvittaessa
if st.session_state.data is None:
    update_data()

# Automaattinen päivitys
if st.session_state.auto_refresh:
    now = datetime.utcnow()
    if (now - st.session_state.last_fetch_time).total_seconds() > 60:
        update_data()

# UI: painikkeet
st.markdown("### Valinnat")
col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 2])
with col1:
    if st.button("10 min"):
        st.session_state.interval = "10 min"
with col2:
    if st.button("30 min"):
        st.session_state.interval = "30 min"
with col3:
    if st.button("1 h"):
        st.session_state.interval = "1 h"
with col4:
    if st.button("Päivitä"):
        update_data()
with col5:
    st.session_state.auto_refresh = st.checkbox("Automaattipäivitys (1 min)", value=st.session_state.auto_refresh)

if st.session_state.last_updated:
    st.caption(f"Viimeisin päivitys: {st.session_state.last_updated.strftime('%H:%M:%S')} UTC")

# Suodata data
cutoff = datetime.utcnow() - timedelta(minutes=interval_minutes[st.session_state.interval])
filtered_norway = st.session_state.data[st.session_state.data["Timestamp"] >= cutoff]
filtered_fi = st.session_state.filtered_fi[st.session_state.filtered_fi["Timestamp"] >= cutoff]

# Välilehdet
tab1, tab2, tab3 = st.tabs(["Kaavio", "Taulukko", "Suomen taajuus"])

# Kaavio
with tab1:
    st.markdown("### Näytettävät viivat")
    c1, c2 = st.columns(2)
    with c1:
        show_norja = st.checkbox("Näytä Norjan taajuus", value=True)
    with c2:
        show_suomi = st.checkbox("Näytä Suomen taajuus", value=True)

    if not filtered_norway.empty or not filtered_fi.empty:
        y_min = min(
            filtered_norway["FrequencyHz"].min() if not filtered_norway.empty else np.inf,
            filtered_fi["FrequencyHz"].min() if not filtered_fi.empty else np.inf
        )
        y_max = max(
            filtered_norway["FrequencyHz"].max() if not filtered_norway.empty else -np.inf,
            filtered_fi["FrequencyHz"].max() if not filtered_fi.empty else -np.inf
        )
        y_axis_min = y_min - 0.05
        y_axis_max = y_max + 0.05

        fig = go.Figure()

        fig.add_shape(
            type="rect", xref="x", yref="y",
            x0=cutoff, x1=datetime.utcnow(),
            y0=y_axis_min, y1=min(49.97, y_axis_max),
            fillcolor="rgba(255,0,0,0.1)", line_width=0, layer="below"
        )
        fig.add_shape(
            type="rect", xref="x", yref="y",
            x0=cutoff, x1=datetime.utcnow(),
            y0=max(50.03, y_axis_min), y1=y_axis_max,
            fillcolor="rgba(0,0,255,0.1)", line_width=0, layer="below"
        )

        if show_norja and not filtered_norway.empty:
            fig.add_trace(go.Scatter(
                x=filtered_norway["Timestamp"],
                y=filtered_norway["FrequencyHz"],
                mode="lines+markers",
                name="Norja",
                line=dict(color="black")
            ))

        if show_suomi and not filtered_fi.empty:
            fig.add_trace(go.Scatter(
                x=filtered_fi["Timestamp"],
                y=filtered_fi["FrequencyHz"],
                mode="lines+markers",
                name="Suomi",
                line=dict(color="blue")
            ))

        fig.update_layout(
            xaxis_title="Aika (UTC)",
            yaxis_title="Taajuus (Hz)",
            height=600,
            margin=dict(t=10)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Ei dataa valitulla aikavälillä.")

# Taulukko
with tab2:
    combined = pd.concat([
        filtered_norway.assign(Lähde="Norja"),
        filtered_fi.assign(Lähde="Suomi")
    ])
    combined = combined.sort_values(by="Timestamp", ascending=False).reset_index(drop=True)
    st.dataframe(combined[["Timestamp", "FrequencyHz", "Lähde"]], use_container_width=True)

# Suomen taajuus
with tab3:
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

        fig_fi.add_trace(go.Scatter(
            x=filtered_fi["Timestamp"],
            y=filtered_fi["FrequencyHz"],
            mode="lines+markers",
            name="Suomi",
            line=dict(color="blue")
        ))

        fig_fi.update_layout(
            xaxis_title="Aika (UTC)",
            yaxis_title="Taajuus (Hz)",
            height=600,
            margin=dict(t=10)
        )
        st.plotly_chart(fig_fi, use_container_width=True)
    else:
        st.warning("Ei dataa saatavilla Fingridiltä.")

