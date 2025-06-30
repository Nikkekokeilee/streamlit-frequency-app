import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import plotly.graph_objects as go

st.set_page_config(page_title="Statnett Frequency Viewer", layout="wide")
st.title("Statnett Grid Frequency Viewer")

# Valitse näkymä: kaavio tai taulukko
view_option = st.radio("Valitse näkymä:", ["Kaavio", "Taulukko"], horizontal=True)

# Lasketaan aikaväli
now = datetime.utcnow()
start_time = now - timedelta(hours=1)

# Haetaan data From-parametrilla
from_param = start_time.strftime("%Y-%m-%d")
url = f"https://driftsdata.statnett.no/restapi/Frequency/BySecond?From={from_param}"

# Alustetaan session_state
if "interval_option" not in st.session_state:
    st.session_state.interval_option = "1 h"

interval_minutes = {
    "10 min": 10,
    "30 min": 30,
    "1 h": 60
}[st.session_state.interval_option]

cutoff_time = now - timedelta(minutes=interval_minutes)

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
    df = df[df["Timestamp"] >= cutoff_time]

    if df.empty:
        st.warning("Ei dataa valitulla aikavälillä.")
    else:
        df["Time_10s"] = df["Timestamp"].dt.floor("10S")
        grouped = df.groupby("Time_10s").agg(FrequencyHz=("FrequencyHz", "mean")).reset_index()
        grouped.rename(columns={"Time_10s": "Timestamp"}, inplace=True)

        y_min = grouped["FrequencyHz"].min()
        y_max = grouped["FrequencyHz"].max()
        y_axis_min = y_min - 0.05
        y_axis_max = y_max + 0.05

        if view_option == "Kaavio":
            if st.button("Päivitä kaavio"):
                st.experimental_rerun()

            fig = go.Figure()

            if y_axis_min < 49.97:
                fig.add_shape(
                    type="rect", xref="x", yref="y",
                    x0=grouped["Timestamp"].min(), x1=grouped["Timestamp"].max(),
                    y0=y_axis_min, y1=min(49.97, y_axis_max),
                    fillcolor="rgba(255,0,0,0.1)", line_width=0, layer="below"
                )

            if y_axis_max > 50.03:
                fig.add_shape(
                    type="rect", xref="x", yref="y",
                    x0=grouped["Timestamp"].min(), x1=grouped["Timestamp"].max(),
                    y0=max(50.03, y_axis_min), y1=y_axis_max,
                    fillcolor="rgba(0,0,255,0.1)", line_width=0, layer="below"
                )

            fig.add_trace(go.Scatter(x=grouped["Timestamp"], y=grouped["FrequencyHz"],
                                     mode="lines+markers", name="Frequency (Hz)",
                                     line=dict(color="black")))
            fig.update_layout(
                title=f"Grid Frequency (Hz) – viimeiset {st.session_state.interval_option}",
                xaxis_title="Aika (UTC)",
                yaxis_title="Taajuus (Hz)",
                yaxis=dict(range=[y_axis_min, y_axis_max]),
                height=600
            )
            st.plotly_chart(fig, use_container_width=True)

        else:
            if st.button("Päivitä taulukko"):
                st.experimental_rerun()
            st.dataframe(grouped[["Timestamp", "FrequencyHz"]].reset_index(drop=True), use_container_width=True)

        # ✅ Aikavälin valintapainikkeet keskitetysti kaavion/taulukon alapuolelle
        st.markdown("<div style='text-align: center; margin-top: 12px;'>", unsafe_allow_html=True)
        cols = st.columns([1,1,1,5])
        with cols[0]:
            if st.button("10 min"):
                st.session_state.interval_option = "10 min"
                st.experimental_rerun()
        with cols[1]:
            if st.button("30 min"):
                st.session_state.interval_option = "30 min"
                st.experimental_rerun()
        with cols[2]:
            if st.button("1 h"):
                st.session_state.interval_option = "1 h"
                st.experimental_rerun()
        st.markdown("</div>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"Virhe datan haussa: {e}")

