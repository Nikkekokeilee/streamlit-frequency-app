import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="Statnett Frequency Viewer", layout="wide")
st.title("Statnett Grid Frequency (Last 30 Minutes)")

# Aikaväli: viimeiset 30 minuuttia
now_utc = datetime.now(timezone.utc)
half_hour_ago_utc = now_utc - timedelta(minutes=30)

from_str = half_hour_ago_utc.strftime("%Y-%m-%dT%H:%M:%S")
to_str = now_utc.strftime("%Y-%m-%dT%H:%M:%S")

url = f"https://driftsdata.statnett.no/restapi/Frequency/BySecond?From={from_str}&To={to_str}"

try:
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

    st.line_chart(result.set_index("Timestamp")["FrequencyHz"])

    st.dataframe(result, use_container_width=True)

except Exception as e:
    st.error(f"Virhe datan haussa: {e}")
