import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Statnett Frequency Viewer", layout="wide")
st.title("Statnett Grid Frequency Viewer")

st_autorefresh(interval=120_000, key="data_refresh")

if st.button("Päivitä nyt"):
    st.experimental_rerun()

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
    start_utc = now_utc - timedelta(hours=1)

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
    df["TimestampUTC"] = pd.to_datetime(df["UtcTimestamp"])
    df["Time_10s"] = df["TimestampUTC"].dt.floor("10S")

    grouped = df.groupby("Time_10s").agg(FrequencyHz=("FrequencyHz", "mean")).reset_index()
    grouped["Color"] = grouped["FrequencyHz"].apply(lambda f: "Blue" if f >= 50 else "Red")
    grouped.rename(columns={"Time_10s": "Timestamp"}, inplace=True)

    # ✅ Korjaus: poista aikavyöhykkeet molemmista
    grouped["Timestamp"] = pd.to_datetime(grouped["Timestamp"]).dt.tz_localize(None)
    cutoff_time = pd.to_datetime(now_utc - timedelta(minutes=interval_minutes)).tz_localize(None)

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
                type="rect", xref="x", yref="y",
                x0=result["Timestamp"].min(), x1=result["Timestamp"].max(),
                y0=max(50.01, y_axis_min), y1=y_axis_max,
                fillcolor="rgba(0,0,255,0.1)", line_width=0, layer="below"
            )

        fig.add_trace(go.Scatter(x=result["Timestamp"], y=result["FrequencyHz"],
                                 mode="lines+markers", line=dict(color="black")))

        fig.update_layout(
            title=f"Grid Frequency (Hz) – viimeiset {interval_option}",
            xaxis_title="Time",
            yaxis_title="Frequency (Hz)",
            yaxis=dict(range=[y_axis_min, y_axis_max])
        )

        chart_placeholder.plotly_chart(fig, use_container_width=True)

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
