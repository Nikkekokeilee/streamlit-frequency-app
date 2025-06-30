import streamlit as st
import pandas as pd
import altair as alt
import datetime
import requests

# Streamlit app configuration
st.set_page_config(page_title="Statnett Frequency Monitor", layout="wide")
st.title("📡 Real-Time Frequency Monitor from Statnett")

# Sidebar controls
st.sidebar.header("⚙️ Controls")
minutes_back = st.sidebar.slider("History Length (minutes)", 1, 60, 10)
refresh_interval = st.sidebar.slider("Refresh Interval (seconds)", 5, 120, 30)

# Auto-refresh
st.markdown(f"<meta http-equiv='refresh' content='{refresh_interval}'>", unsafe_allow_html=True)

# Fetch frequency data from Statnett API
@st.cache_data(ttl=refresh_interval)
def fetch_statnett_frequency_data(minutes):
    try:
        end_time = datetime.datetime.utcnow()
        start_time = end_time - datetime.timedelta(minutes=minutes)
        from_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"https://driftsdata.statnett.no/restapi/Frequency/BySecond?From={from_time_str}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            start_point = pd.to_datetime(data["StartPointUTC"])
            interval_ms = data["PeriodTickMs"]
            values = data["Measurements"]
            timestamps = [start_point + pd.Timedelta(milliseconds=i * interval_ms) for i in range(len(values))]
            df = pd.DataFrame({"Timestamp": timestamps, "FrequencyHz": values})
            return df
        else:
            st.error(f"Failed to fetch data: {response.status_code}")
            return pd.DataFrame(columns=["Timestamp", "FrequencyHz"])
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame(columns=["Timestamp", "FrequencyHz"])

df = fetch_statnett_frequency_data(minutes_back)

if not df.empty:
    # Fixed y-axis range
    y_min = 49.5
    y_max = 50.5

    # Background zones
    zones = pd.DataFrame({
        'y': [49.5, 50],
        'y2': [50, 50.5],
        'color': ['#ffe6e6', '#e6f0ff']
    })

    background = alt.Chart(zones).mark_rect(opacity=0.3).encode(
        y='y:Q',
        y2='y2:Q',
        color=alt.Color('color:N', scale=None, legend=None)
    )

    # Line chart
    line_chart = alt.Chart(df).mark_line(
        color='#34495e',
        strokeWidth=2,
        interpolate='monotone'
    ).encode(
        x=alt.X("Timestamp:T", title="Time", axis=alt.Axis(format="%H:%M:%S")),
        y=alt.Y("FrequencyHz:Q", title="Frequency (Hz)", scale=alt.Scale(domain=[y_min, y_max], nice=False, clamp=True)),
        tooltip=["Timestamp:T", "FrequencyHz:Q"]
    )

    chart = (background + line_chart).properties(
        width=1000,
        height=500,
        title="Live Frequency from Statnett"
    )

    st.altair_chart(chart, use_container_width=True)
else:
    st.warning("No data available to display.")

