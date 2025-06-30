import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import plotly.graph_objects as go

st.set_page_config(page_title="Statnett Frequency Viewer", layout="wide")
st.title("Statnett Grid Frequency Viewer")

# Automaattipäivityksen tila
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = False

# Automaattipäivitys 1 minuutin välein, jos aktiivinen
if st.session_state.auto_refresh:
    st.experimental_rerun()

# Näkymän valinta
view_option = st.radio("Valitse näkymä:", ["Kaavio", "Taulukko"], index=0)

# Päivityspainikkeet
col1, col2 = st.columns([1, 1])
with col1:
    if view_option == "Kaavio":
        if st.button("Päivitä kaavio"):
            st.session_state.refresh_chart = True
    else:
        if st.button("Päivitä taulukko"):
            st.session_state.refresh_table = True
with col2:
    toggle = st.checkbox("Automaattipäivitys (1 min välein)", value=st.session_state.auto_refresh)
    st.session_state.auto_refresh = toggle

# Aikavälin valinta painikkeilla
interval_minutes = 60  # oletus
interval_container = st.container()
with interval_container:
    st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
    col_a, col_b, col_c = st.columns([1, 1, 1])
    with col_a:
        if st.button("10 min"):
            interval_minutes = 10
    with col_b:
        if st.button("30 min"):
            interval_minutes = 30
    with col_c:
        if st.button("1 h"):
            interval_minutes = 60
    st.markdown("</div>", unsafe_allow_html=True)

# Lasketaan aikaväli
now = datetime.utcnow()
start_time = now - timedelta(hours=1)
cutoff_time = now - timedelta(minutes=interval_minutes)

# Haetaan data From-parametrilla
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

    # Lasketaan aikaleimat
    start_dt = datetime(1970, 1, 1) + timedelta(milliseconds=start_point_utc)
    period_sec = period_tick_ms / 1000

    df = pd.DataFrame(measurements, columns=["FrequencyHz"])
    df["Index"] = df.index
    df["Timestamp"] = df["Index"].apply(lambda i: start_dt + timedelta(seconds=i * period_sec))
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])

    # Suodatetaan viimeisen tunnin data
    df = df[df["Timestamp"] >= cutoff_time]

    if df.empty:
        st.warning("Ei dataa valitulla aikavälillä.")
    else:
        # Ryhmitellään 10 sekunnin keskiarvoihin
        df["Time_10s"] = df["Timestamp"].dt.floor("10S")
        grouped = df.groupby("Time_10s").agg(FrequencyHz=("FrequencyHz", "mean")).reset_index()
        grouped.rename(columns={"Time_10s": "Timestamp"}, inplace=True)

        if view_option == "Kaavio":
            y_min = grouped["FrequencyHz"].min()
            y_max = grouped["FrequencyHz"].max()
            y_axis_min = y_min - 0.05
            y_axis_max = y_max + 0.05

            fig = go.Figure()

            # Punainen alue alle 49.97 Hz
            fig.add_shape(
                type="rect", xref="x", yref="y",
                x0=grouped["Timestamp"].min(), x1=grouped["Timestamp"].max(),
                y0=y_axis_min, y1=min(49.97, y_axis_max),
                fillcolor="rgba(255,0,0,0.1)", line_width=0, layer="below"
            )

            # Sininen alue yli 50.03 Hz
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
                title=f"Grid Frequency (Hz) – viimeiset {interval_minutes} min",
                xaxis_title="Aika (UTC)",
                yaxis_title="Taajuus (Hz)",
                yaxis=dict(range=[y_axis_min, y_axis_max]),
                height=600
            )
            st.plotly_chart(fig, use_container_width=True)

        else:
            st.dataframe(grouped[["Timestamp", "FrequencyHz"]].reset_index(drop=True), use_container_width=True)

except Exception as e:
    st.error(f"Virhe datan haussa: {e}")

