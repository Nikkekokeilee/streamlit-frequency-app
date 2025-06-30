import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Statnett Frequency Viewer", layout="wide")
st.title("Statnett Grid Frequency Viewer")

# Automaattinen päivitys 10 sekunnin välein
st_autorefresh(interval=10_000, key="data_refresh")

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
    df["TimestampFI"] = df["UtcTimestamp"].apply(lambda ts: ts.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=3))))
    df["Time_10s"] = df["TimestampFI"].dt.floor("10S")

    grouped = df.groupby("Time_10s").agg(FrequencyHz=("FrequencyHz", "mean")).reset_index()
    grouped["Color"] = grouped["FrequencyHz"].apply(lambda f: "Blue" if f >= 50 else "Red")
    grouped.rename(columns={"Time_10s": "Timestamp"}, inplace=True)

    # Rajataan näkyvä aikaväli valinnan mukaan
    cutoff_time = datetime.now(timezone(timedelta(hours=3))) - timedelta(minutes=interval_minutes)
    result = grouped[grouped["Timestamp"] >= cutoff_time]

    # Plotly chart
    fig = go.Figure()

    # Taustavärit
    fig.add_shape(
        type="rect", xref="x", yref="y",
        x0=result["Timestamp"].min(), x1=result["Timestamp"].max(),
        y0=0, y1=49.99,
        fillcolor="rgba(255,0,0,0.1)", line_width=0, layer="below"
    )
    fig.add_shape(
        type="rect", xref="x", yref="y",
        x0=result["Timestamp"].min(), x1=result["Timestamp"].max(),
        y0=50.01, y1=100,
        fillcolor="rgba(0,0,255,0.1)", line_width=0, layer="below"
    )

    # Musta viiva
    fig.add_trace(go.Scatter(x=result["Timestamp"], y=result["FrequencyHz"],
                             mode="lines+markers", line=dict(color="black")))

    fig.update_layout(
        title=f"Grid Frequency (Hz) – viimeiset {interval_option}",
        xaxis_title="Time",
        yaxis_title="Frequency (Hz)",
        yaxis=dict(autorange=True)
    )

    chart_placeholder.plotly_chart(fig, use_container_width=True)

    # Taulukon värit ja fonttikoko
    def highlight_frequency(row):
        color = row["Color"]
        if color == "Blue":
            bg = "background-color: rgba(0, 0, 255, 0.2)"
        else:
            bg = "background-color: rgba(255, 0, 0, 0.2)"
        return [bg if col == "FrequencyHz" else '' for col in row.index]

    styled_df = result.copy()
    styled = styled_df.style \
        .apply(highlight_frequency, axis=1) \
        .set_properties(subset=["Timestamp", "FrequencyHz"], **{'font-size': '16px'}) \
        .hide(axis="columns", subset=["Color"])

    table_placeholder.dataframe(styled, use_container_width=True)

except Exception as e:
    st.error(f"Virhe datan haussa: {e}")

