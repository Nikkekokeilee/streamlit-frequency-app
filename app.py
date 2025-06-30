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

# Määritä väri taajuuden mukaan
def get_color(freq):
    if freq < 50:
        return "red"
    elif freq > 50:
        return "blue"
    else:
        return "white"

df["Color"] = df["FrequencyHz"].apply(get_color)

# Luo viivakaavio, jossa väri vaihtuu
chart = alt.Chart(df).mark_line().encode(
    x=alt.X("Timestamp:T", title="Time"),
    y=alt.Y("FrequencyHz:Q", title="Frequency (Hz)", scale=alt.Scale(domain=[49.5, 50.5])),
    color=alt.Color("Color:N", scale=None, legend=None),
    tooltip=["Timestamp:T", "FrequencyHz:Q"]
).properties(
    width=800,
    height=400
)

st.altair_chart(chart, use_container_width=True)
