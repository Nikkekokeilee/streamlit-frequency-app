import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone
import plotly.graph_objects as go
import time

st.set_page_config(page_title="Statnett Frequency Viewer", layout="wide")
st.title("Statnett Grid Frequency (Last 30 Minutes)")

chart_placeholder = st.empty()
table_placeholder = st.empty()

def fetch_and_display():
    now_utc = datetime.now(timezone.utc)
    half_hour_ago_utc = now_utc - timedelta(minutes=30)

    from_str = half_hour_ago_utc.strftime("%Y-%m-%dT%H:%M:%S")
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
    df["TimestampFI"] = df["UtcTimestamp"].apply(lambda ts: ts.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=3))))
    df["Time_1s"] = df["TimestampFI"].dt.floor("S")

    grouped = df.groupby("Time_1s").agg(FrequencyHz=("FrequencyHz", "mean")).reset_index()
    grouped["Color"] = grouped["FrequencyHz"].apply(lambda f: "Blue" if f >= 50 else "Red")
    grouped.rename(columns={"Time_1s": "Timestamp"}, inplace=True)

    result = grouped.sort_values("Timestamp", ascending=False).head(30).sort_values("Timestamp")

    # Plotly chart with background color bands that do NOT affect autoscaling
    fig = go.Figure()

    fig.add_shape(type="rect", xref="x", yref="paper",
                  x0=result["Timestamp"].min(), x1=result["Timestamp"].max(),
                  y0=0, y1=0.4,
                  fillcolor="rgba(255,0,0,0.1)", line_width=0, layer="below")

    fig.add_shape(type="rect", xref="x", yref="paper",
                  x0=result["Timestamp"].min(), x1=result["Timestamp"].max(),
                  y0=0.6, y1=1,
                  fillcolor="rgba(0,0,255,0.1)", line_width=0, layer="below")

    fig.add_trace(go.Scatter(x=result["Timestamp"], y=result["FrequencyHz"],
                             mode="lines+markers", line=dict(color="black")))

    fig.update_layout(
        title="Grid Frequency (Hz)",
        xaxis_title="Time",
        yaxis_title="Frequency (Hz)",
        yaxis=dict(autorange=True)
    )

    chart_placeholder.plotly_chart(fig, use_container_width=True)

    # Style table
    def highlight_frequency(row):
        color = row["Color"]
        if color == "Blue":
            bg = "background-color: rgba(0, 0, 255, 0.2)"
        else:
            bg = "background-color: rgba(255, 0, 0, 0.2)"
        return [bg if col == "FrequencyHz" else '' for col in row.index]

    styled_df = result.style \
        .apply(highlight_frequency, axis=1) \
        .set_properties(subset=["Timestamp", "FrequencyHz"], **{'font-size': '16px'}) \
        .hide(axis="columns", subset=["Color"])

    table_placeholder.dataframe(styled_df, use_container_width=True)

# Päivitä automaattisesti 10 sekunnin välein
while True:
    try:
        fetch_and_display()
    except Exception as e:
        st.error(f"Virhe datan haussa: {e}")
    time.sleep(10)
