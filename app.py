import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import plotly.graph_objects as go

st.set_page_config(page_title="Statnett Frequency Viewer", layout="wide")
st.title("Statnett Grid Frequency Viewer")

# Valitse näkymä: kaavio tai taulukko
view_option = st.radio("Valitse näkymä:", ["Kaavio", "Taulukko"], index=0)

# Aikaväli oletuksena session_statessa
if "interval_minutes" not in st.session_state:
    st.session_state.interval_minutes = 60

# Päivityspainikkeet
if view_option == "Kaavio":
    if st.button("Päivitä kaavio"):
        st.session_state.update_chart = True
elif view_option == "Taulukko":
    if st.button("Päivitä taulukko"):
        st.session_state.update_table = True

# Haetaan data vain jos painike painettu tai ei vielä ladattu
if "data" not in st.session_state or \
   (view_option == "Kaavio" and st.session_state.get("update_chart")) or \
   (view_option == "Taulukko" and st.session_state.get("update_table")):

    now = datetime.utcnow()
    start_time = now - timedelta(hours=1)
    cutoff_time = now - timedelta(minutes=st.session_state.interval_minutes)

    from_param = start_time.strftime("%Y-%m-%d")
    url = f"https://driftsdata.statnett.no/restapi/Frequency/BySecond?From={from_param}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        start_point_utc = data["StartPointUTC"]
        period_tick_ms = data["PeriodTickMs"]
        measurements = data["Measurements"]

        if not measurements:
            st.warning("Statnettin API ei palauttanut dataa.")
            st.stop()

        start_dt = datetime(1970, 1, 1) + timedelta(milliseconds=start_point_utc)
        period_sec = period_tick_ms / 1000

        df = pd.DataFrame(measurements, columns=["FrequencyHz"])
        df["Index"] = df.index
        df["Timestamp"] = df["Index"].apply(lambda i: start_dt + timedelta(seconds=i * period_sec))
        df["Timestamp"] = pd.to_datetime(df["Timestamp"])
        df["Time_10s"] = df["Timestamp"].dt.floor("10S")
        grouped = df.groupby("Time_10s").agg(FrequencyHz=("FrequencyHz", "mean")).reset_index()
        grouped.rename(columns={"Time_10s": "Timestamp"}, inplace=True)
        grouped = grouped[grouped["Timestamp"] >= cutoff_time]

        st.session_state.data = grouped
        st.session_state.update_chart = False
        st.session_state.update_table = False

    except Exception as e:
        st.error(f"Virhe datan haussa: {e}")
        st.stop()

# Näytetään näkymä
if "data" in st.session_state and not st.session_state.data.empty:
    data = st.session_state.data

    if view_option == "Kaavio":
        y_min = data["FrequencyHz"].min()
        y_max = data["FrequencyHz"].max()
        y_axis_min = y_min - 0.05
        y_axis_max = y_max + 0.05

        fig = go.Figure()

        if y_axis_min < 49.97:
            fig.add_shape(
                type="rect", xref="x", yref="y",
                x0=data["Timestamp"].min(), x1=data["Timestamp"].max(),
                y0=y_axis_min, y1=min(49.97, y_axis_max),
                fillcolor="rgba(255,0,0,0.1)", line_width=0, layer="below"
            )

        if y_axis_max > 50.03:
            fig.add_shape(
                type="rect", xref="x", yref="y",
                x0=data["Timestamp"].min(), x1=data["Timestamp"].max(),
                y0=max(50.03, y_axis_min), y1=y_axis_max,
                fillcolor="rgba(0,0,255,0.1)", line_width=0, layer="below"
            )

        fig.add_trace(go.Scatter(x=data["Timestamp"], y=data["FrequencyHz"],
                                 mode="lines+markers", name="Frequency (Hz)",
                                 line=dict(color="black")))
        fig.update_layout(
            title=f"Grid Frequency (Hz) – viimeiset {st.session_state.interval_minutes} min",
            xaxis_title="Aika (UTC)",
            yaxis_title="Taajuus (Hz)",
            height=600,
            yaxis=dict(range=[y_axis_min, y_axis_max])
        )
        st.plotly_chart(fig, use_container_width=True)

    elif view_option == "Taulukko":
        st.dataframe(data[["Timestamp", "FrequencyHz"]].reset_index(drop=True), use_container_width=True)

# Aikavälin valintapainikkeet kaavion/taulukon alapuolelle
st.markdown("### Valitse aikaväli:")
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("10 min"):
        st.session_state.interval_minutes = 10
        st.session_state.update_chart = True
        st.session_state.update_table = True
with col2:
    if st.button("30 min"):
        st.session_state.interval_minutes = 30
        st.session_state.update_chart = True
        st.session_state.update_table = True
with col3:
    if st.button("1 h"):
        st.session_state.interval_minutes = 60
        st.session_state.update_chart = True
        st.session_state.update_table = True

