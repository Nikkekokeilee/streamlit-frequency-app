import streamlit as st
import pandas as pd
import datetime
import altair as alt
import random
import pytz

# Page configuration
st.set_page_config(page_title="Frequency Trend Dashboard", layout="wide")

# Header
st.markdown("""
    <style>
        .main-title {
            font-size: 2.5em;
            font-weight: 600;
            color: #2c3e50;
            text-align: center;
            margin-bottom: 20px;
        }
        .sidebar .sidebar-content {
            background-color: #f8f9fa;
        }
    </style>
    <div class="main-title">📊 Frequency Trend Dashboard</div>
""", unsafe_allow_html=True)

# Sidebar controls
st.sidebar.header("⚙️ Controls")
minutes_back = st.sidebar.slider("History Length (minutes)", 1, 60, 10)
refresh_interval = st.sidebar.slider("Refresh Interval (seconds)", 5, 120, 30)

# Auto-refresh
st.markdown(f"<meta http-equiv='refresh' content='{refresh_interval}'>", unsafe_allow_html=True)

# Simulate frequency data
def simulate_frequency_data(minutes):
    local_tz = pytz.timezone("Europe/Helsinki")
    now = datetime.datetime.now(local_tz)
    points = int((minutes * 60) / 10)  # every 10 seconds
    timestamps = [now - datetime.timedelta(seconds=i*10) for i in range(points)][::-1]
    frequencies = []
    base = 50
    for _ in range(points):
        base += random.uniform(-0.05, 0.05)
        base = max(49.5, min(50.5, base))
        frequencies.append(round(base, 3))
    return pd.DataFrame({"Timestamp": timestamps, "FrequencyHz": frequencies})

df = simulate_frequency_data(minutes_back)

# Background zones
zones = pd.DataFrame({
    'y': [49.5, 50],
    'y2': [50, 50.5],
    'color': ['#ffe6e6', '#e6f0ff']
})

background = alt.Chart(zones).mark_rect(opacity=0.4).encode(
    y='y:Q',
    y2='y2:Q',
    color=alt.Color('color:N', scale=None, legend=None)
)

# Line chart
line_chart = alt.Chart(df).mark_line(
    color='#34495e',
    strokeWidth=3,
    interpolate='monotone'
).encode(
    x=alt.X("Timestamp:T", title="Time", axis=alt.Axis(format="%H:%M:%S")),
    y=alt.Y("FrequencyHz:Q", title="Frequency (Hz)", scale=alt.Scale(domain=[49.5, 50.5], nice=False, clamp=True)),
    tooltip=["Timestamp:T", "FrequencyHz:Q"]
)

# Combine and display
chart = (background + line_chart).properties(
    width=1000,
    height=500,
    title="Live Frequency Monitoring"
)

st.altair_chart(chart, use_container_width=True)
