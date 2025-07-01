import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import plotly.graph_objects as go
import pytz
import time

st.set_page_config(layout="wide")

# ✅ Tarkista, että API-avain on määritetty
if "FINGRID_API_KEY" not in st.secrets:
    st.error("Fingridin API-avainta ei ole määritetty. Lisää se tiedostoon .streamlit/secrets.toml avaimella 'FINGRID_API_KEY'.")
    st.stop()

# ✅ Hae avain käyttöön
api_key = st.secrets["FINGRID_API_KEY"]

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

# Kello
col1, col2 = st.columns(2)
with col1:
    st.markdown(f"**UTC-aika:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
with col2:
    helsinki_time = datetime.now(pytz.timezone("Europe/Helsinki"))
    st.markdown(f"**Suomen aika:** {helsinki_time.strftime('%Y-%m-%d %H:%M:%S')}")

# Datahaku Norjan taajuudelle
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

# Suomen taajuus Fingridiltä
def fetch_finland_data():
    now = datetime.utcnow()
    interval_minutes = {"10 min": 10, "30 min": 30, "1 h": 60}
    start_time = now - timedelta(minutes=interval_minutes[st.session_state.interval])
    fingrid_url = (
        f"https://data.fingrid.fi/api/datasets/177/data?"
        f"startTime={start_time.isoformat()}Z&endTime={now.isoformat()}Z"
    )
    headers = {"x-api-key": api_key}
    response = requests.get(fingrid_url, headers=headers)
    response.raise_for_status()
    fi_data = response.json()
    df_fi = pd.DataFrame(fi_data["data"])
    df_fi["Timestamp"] = pd.to_datetime(df_fi["startTime"])
    df_fi["FrequencyHz"] = df_fi["value"]
    return df_fi[["Timestamp", "FrequencyHz"]]

# Ruotsin taajuus Kontrollrummetista
def fetch_sweden_data():
    now = int(time.time() * 1000)
    one_hour_ago = now - 60 * 60 * 1000
    url = f"https://www.svk.se/kontrollrummet/api/frequency?lower_unix={one_hour_ago}&upper_unix={now}"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    df = pd.DataFrame(data)
    df["Timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df["FrequencyHz"] = df["frequency"]
    df = df[["Timestamp", "FrequencyHz"]]
    return df

# Päivitä data
def update_data():
    st.session_state.data = fetch_norway_data()
    st.session_state.last_updated = datetime.utcnow()
    st.session_state.last_fetch_time = datetime.utcnow()

# Painikkeet
st.markdown("### Valinnat")
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

# Välilehdet
tab1, tab3, tab4 = st.tabs(["Norjan taajuus", "Suomen taajuus", "Ruotsin taajuus"])

# Kaaviofunktio
def plot_frequency(df, title):
    if not df.empty:
        y_min = df["FrequencyHz"].min()
        y_max = df["FrequencyHz"].max()
        y_axis_min = y_min - 0.05
        y_axis_max = y_max + 0.05

        fig = go.Figure()

        fig.add_shape(
            type="rect", xref="x", yref="y",
            x0=df["Timestamp"].min(), x1=df["Timestamp"].max(),
            y0=y_axis_min, y1=min(49.97, y_axis_max),
            fillcolor="rgba(255,0,0,0.1)", line_width=0, layer="below"
        )

        fig.add_shape(
            type="rect", xref="x", yref="y",
            x0=df["Timestamp"].min(), x1=df["Timestamp"].max(),
            y0=max(50.03, y_axis_min), y1=y_axis_max,
            fillcolor="rgba(0,0,255,0.1)", line_width=0, layer="below"
        )

        fig.add_trace(go.Scatter(x=df["Timestamp"], y=df["FrequencyHz"],
                                 mode="lines+markers", line=dict(color="black")))

        fig.update_layout(
            title=title,
            xaxis_title="Aika (UTC)",
            yaxis_title="Taajuus (Hz)",
            height=600,
            margin=dict(t=10)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Ei dataa valitulla aikavälillä.")

# Norjan kaavio
with tab1:
    plot_frequency(filtered, "Norjan taajuus")

# Suomen kaavio
with tab3:
    try:
        fi_data = fetch_finland_data()
        fi_filtered = fi_data[fi_data["Timestamp"] >= cutoff]
        plot_frequency(fi_filtered, "Suomen taajuus")
    except Exception as e:
        st.error(f"Virhe haettaessa Fingridin dataa: {e}")

# Ruotsin kaavio
with tab4:
    try:
        se_data = fetch_sweden_data()
        se_filtered = se_data[se_data["Timestamp"] >= cutoff]
        plot_frequency(se_filtered, "Ruotsin taajuus")
    except Exception as e:
        st.error(f"Virhe haettaessa Ruotsin dataa: {e}")

