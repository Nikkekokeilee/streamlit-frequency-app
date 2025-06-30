import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Statnett Frequency Viewer", layout="wide")
st.title("Statnett Grid Frequency Viewer")

# Automaattinen päivitys 2 minuutin välein
st_autorefresh(interval=120_000, key="data_refresh")

# Manuaalinen päivityspainike
if st.button("Päivitä nyt"):
    st.experimental_rerun()

# Aikavälin valinta (max 1h)
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

chart_placeholder = st.empty()
table_placeholder = st.empty()

try:
    now_utc = datetime.now(timezone.utc)
    start_utc = now_utc - timedelta(hours=1)  # haetaan aina 1h historia

    from_str = start_utc.strftime("%Y-%m-%dT%H:%M:%S")
    to_str = now_utc.strftime("%Y-%m-%dT%H:%M:%S")

    url = f"https://driftsdata.statnett.no/restapi/Frequency/BySecond?From={from_str}&To={to_str}"

    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    start_point_utc = data["StartPointUTC"]
    period_tick_ms = data["PeriodTickMs"]
    measurements = data["Measurements"]

    start_time = datetime(1970, 1, 1) + timedelta(seconds=start_point_utc // 1000)
    period_sec = period_tick_ms / 1000

    df = pd.DataFrame(measurements, columns=["FrequencyHz"])
    df["Index"] = df.index
    df["UtcTimestamp"] = df["Index"].apply(lambda i: start_time + timedelta(seconds=i * period_sec))
    df["TimestampUTC"] = df["UtcTimestamp"]
    df["Time_10s"] = pd.to_datetime(df["TimestampUTC"]).dt.floor("10S")

    grouped = df.groupby("Time_10s").agg(FrequencyHz=("FrequencyHz", "mean")).reset_index()
    grouped["Color"] = grouped["FrequencyHz"].apply(lambda f: "Blue" if f >= 50 else "Red")
    grouped.rename(columns={"Time_10s": "Timestamp"}, inplace=True)

    # ✅ Varmistetaan, että Timestamp on datetime64[ns]
    grouped["Timestamp"] = pd.to_datetime(grouped["Timestamp"])
    cutoff_time = now_utc - timedelta(minutes=interval_minutes)
    result = grouped[grouped["Timestamp"] >= cutoff_time]

    if result.empty:
        st.warning("Ei dataa valitulla aikavälillä.")
    else:
        y_min = result["FrequencyHz"].min()
        y_max = result["FrequencyHz"].max()
        y_margin = (y_max - y_min) * 0.1 if y_max > y_min else 0.1
        y_axis_min = y_min - y_margin
        y_axis_max = y_max + y_margin

        fig = go.Figure()

        if y_axis_min < 49.99:
            fig.add_shape(
                type="rect", xref="x", yref="y",
                x0=result["Timestamp"].min(), x1=result["Timestamp"].max(),
                y0=y_axis_min, y1=min(49.99, y_axis_max),
                fillcolor="rgba(255,0,0,0.1)", line_width=0, layer="below"
            )

        if y_axis_max > 50.01:
            fig.add_shape(
                type="rect
