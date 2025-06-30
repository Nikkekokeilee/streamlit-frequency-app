import streamlit as st
import pandas as pd
import requests
import datetime
import altair as alt

# Hakee dataa Statnettin API:sta tai luo simuloitua dataa
def fetch_frequency_data():
    try:
        now = datetime.datetime.utcnow()
        half_hour_ago = now - datetime.timedelta(minutes=0.5)
        from_str = half_hour_ago.strftime("%Y-%m-%dT%H:%M:%S")
        to_str = now.strftime("%Y-%m-%dT%H:%M:%S")
        url = f"https://driftsdata.statnett.no/restapi/Frequency/BySecond?From={from_str}&To={to_str}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        start_time = datetime.datetime(1970, 1, 1) + datetime.timedelta(seconds=data["StartPointUTC"] / 1000)
        period_sec = data["PeriodTickMs"] / 1000
        measurements = data["Measurements"]
        timestamps = [start_time + datetime.timedelta(seconds=i * period_sec) for i in range(len(measurements))]
        df = pd.DataFrame({"Timestamp": timestamps, "FrequencyHz": measurements})
        return df
    except:
        now = datetime.datetime.utcnow()
        timestamps = [now - datetime.timedelta(seconds=i*5) for i in range(30)][::-1]
        frequencies = [50 + 0.5 * (-1)**i for i in range(30)]
        df = pd.DataFrame({"Timestamp": timestamps, "FrequencyHz": frequencies})
        return df

# Streamlit-sovellus
st.set_page_config(page_title="Live Frequency Monitor", layout="wide")
st.title("🔄 Live Frequency Monitor (Statnett API)")

# Päivitä automaattisesti 5 sekunnin välein
st.markdown(
    "<meta http-equiv='refresh' content='5'>",
    unsafe_allow_html=True
)

# Hae ja näytä data
df = fetch_frequency_data()

# Luo kuvaaja Altairilla
chart = alt.Chart(df).mark_line(point=True).encode(
    x="Timestamp:T",
    y=alt.Y("FrequencyHz:Q", scale=alt.Scale(domain=[49.5, 50.5])),
    color=alt.condition(
        alt.datum.FrequencyHz < 50, alt.value("red"),
        alt.condition(alt.datum.FrequencyHz > 50, alt.value("blue"), alt.value("white"))
    )
).properties(
    width=800,
    height=400
)

st.altair_chart(chart, use_container_width=True)
