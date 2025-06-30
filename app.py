import streamlit as st
import pandas as pd
import datetime
import altair as alt
import random

# Simuloi taajuusdataa
def simulate_frequency_data():
    now = datetime.datetime.utcnow()
    timestamps = [now - datetime.timedelta(seconds=i*30) for i in range(30)][::-1]
    frequencies = [50 + random.uniform(-0.2, 0.2) for _ in range(30)]
    df = pd.DataFrame({"Timestamp": timestamps, "FrequencyHz": frequencies})
    return df

# Streamlit-sovellus
st.set_page_config(page_title="Live Frequency Monitor", layout="wide")
st.title("🔄 Live Frequency Monitor (Simulated Data)")

# Päivitä automaattisesti 30 sekunnin välein
st.markdown("<meta http-equiv='refresh' content='30'>", unsafe_allow_html=True)

# Hae ja näytä simuloitu data
df = simulate_frequency_data()

# Lisää värikenttä
def get_color(freq):
    if freq < 50:
        return "red"
    elif freq > 50:
        return "blue"
    else:
        return "white"

df["Color"] = df["FrequencyHz"].apply(get_color)

# Luo kuvaaja Altairilla (vain pisteet)
chart = alt.Chart(df).mark_point(filled=True, size=60).encode(
    x=alt.X("Timestamp:T", title="Time"),
    y=alt.Y("FrequencyHz:Q", title="Frequency (Hz)", scale=alt.Scale(domain=[49.5, 50.5])),
    color=alt.Color("Color:N", scale=None, legend=None)
).properties(
    width=800,
    height=400
)

st.altair_chart(chart, use_container_width=True)
