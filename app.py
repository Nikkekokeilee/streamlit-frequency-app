import streamlit as st
import pandas as pd
import datetime
import altair as alt
import random
import pytz

# Streamlit app configuration
st.set_page_config(page_title="📊 Frequency Trend Monitor", layout="wide")
st.title("📊 Frequency Trend Monitor")

# Sidebar controls
st.sidebar.header("⚙️ Asetukset")
minutes_back = st.sidebar.slider("Näytettävä historian pituus (minuuttia)", 1, 60, 10)
refresh_interval = st.sidebar.slider("Päivitystiheys (sekuntia)", 5, 120, 30)

# Auto-refresh
st.markdown(f"<meta http-equiv='refresh' content='{refresh_interval}'>", unsafe_allow_html=True)

# Simulate frequency data
def simulate_frequency_data(minutes):
    local_tz = pytz.timezone("Europe/Helsinki")
    now = datetime.datetime.now(local_tz)
    points = int((minutes * 60) / 10)  # 10s välein
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
    'color': ['#ffcccc', '#cce5ff']
})

background = alt.Chart(zones).mark_rect(opacity=0.3).encode(
    y='y:Q',
    y2='y2:Q',
    color=alt.Color('color:N', scale=None, legend=None)
)

# Line chart with smooth interpolation
line = alt.Chart(df).mark_line(
    color='black',
    strokeWidth=2,
    interpolate='monotone'
).encode(
    x=alt.X("Timestamp:T", title="Aika", axis=alt.Axis(format="%H:%M:%S")),
    y=alt.Y("FrequencyHz:Q", title="Taajuus (Hz)", scale=alt.Scale(domain=[49.5, 50.5], nice=False, clamp=True)),
    tooltip=["Timestamp:T", "FrequencyHz:Q"]
)

# Combine background and line
chart = (background + line).properties(
    width=900,
    height=450,
    title="📈 Taajuuden kehitys"
)

st.altair_chart(chart, use_container_width=True)
