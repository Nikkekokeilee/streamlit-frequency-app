import streamlit as st
import pandas as pd
import datetime
import altair as alt
import random
import pytz

# Streamlit-sovellus
st.set_page_config(page_title="Live Frequency Monitor", layout="wide")
st.title("📈 Live Frequency Monitor (Simulated Data)")

# Käyttäjän valinnat
minutes_back = st.slider("Kuinka monta minuuttia taaksepäin näytetään?", min_value=1, max_value=30, value=5)
refresh_interval = st.slider("Päivitystiheys sekunteina", min_value=10, max_value=120, value=30)

# Päivitä automaattisesti
st.markdown(f"<meta http-equiv='refresh' content='{refresh_interval}'>", unsafe_allow_html=True)

# Simuloi taajuusdataa
def simulate_frequency_data(minutes):
    local_tz = pytz.timezone("Europe/Helsinki")
    now = datetime.datetime.now(local_tz)
    points = int((minutes * 60) / 30)
    timestamps = [now - datetime.timedelta(seconds=i*30) for i in range(points)][::-1]
    frequencies = [50 + random.uniform(-0.2, 0.2) for _ in range(points)]
    df = pd.DataFrame({"Timestamp": timestamps, "FrequencyHz": frequencies})
    return df

df = simulate_frequency_data(minutes_back)

# Luo taustavyöhykkeet: punainen 49.5–50, sininen 50–50.5
background = alt.Chart(pd.DataFrame({
    'y': [49.5, 50],
    'y2': [50, 50.5],
    'color': ['red', 'blue']
})).mark_rect(opacity=0.1).encode(
    y='y:Q',
    y2='y2:Q',
    color=alt.Color('color:N', scale=None, legend=None)
)

# Luo viivakaavio
line = alt.Chart(df).mark_line(color='black').encode(
    x=alt.X("Timestamp:T", title="Time"),
    y=alt.Y("FrequencyHz:Q", title="Frequency (Hz)", scale=alt.Scale(domain=[49.5, 50.5], nice=False)),
    tooltip=["Timestamp:T", "FrequencyHz:Q"]
)

# Yhdistä tausta ja viiva
chart = (background + line).properties(
    width=800,
    height=400
)

st.altair_chart(chart, use_container_width=True)
