import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import plotly.graph_objects as go

st.set_page_config(page_title="Statnett Frequency Viewer", layout="wide")
st.title("Statnett Grid Frequency Viewer")

# Aikavälin valinta
interval_option = st.selectbox(
    "Valitse aikaväli:",
    options=["10 min", "30 min", "1 h"],
    index=2
)

interval_minutes = {
    "10 min": 10,
    "30 min": 30,
    "1 h": 60
}[interval_option]

# Näyttövalinta: kaavio vai taulukko
view_option = st.radio("Valitse näkymä:", ["Kaavio", "Taulukko"], index=0)

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

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=grouped["Timestamp"], y=grouped["FrequencyHz"],
                                     mode="lines+markers", name="Frequency (Hz)",
                                     line=dict(color="black")))
            fig.update_layout(
                title=f"Grid Frequency (Hz) – viimeiset {interval_option}",
                xaxis_title="Aika (UTC)",
                yaxis_title="Taajuus (Hz)",
                yaxis=dict(range=[y_min, y_max])
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.dataframe(grouped[["Timestamp", "FrequencyHz"]].reset_index(drop=True), use_container_width=True)

except Exception as e:
    st.error(f"Virhe datan haussa: {e}")

