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

# Fetch frequency data from Statnett API using new endpoint
@st.cache_data(ttl=refresh_interval)
def fetch_statnett_frequency_data(minutes):
    try:
        end_time = datetime.datetime.utcnow()
        start_time = end_time - datetime.timedelta(minutes=minutes)
        from_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"https://driftsdata.statnett.no/restapi/Frequency/BySecond?From={from_time_str}"

        response = requests.get(url)
        st.text(f"API URL: {url}")
        st.text(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            try:
                data = response.json()
            except Exception as e:
                st.error(f"Error parsing JSON: {e}")
                return pd.DataFrame(columns=["Timestamp", "FrequencyHz"])

            start_point = pd.to_datetime(data.get("StartPointUTC"))
            tick_ms = data.get("PeriodTickMs", 1000)
            measurements = data.get("Measurements", [])

            if not measurements:
                st.warning("No measurements returned from API.")
                return pd.DataFrame(columns=["Timestamp", "FrequencyHz"])

            timestamps = [start_point + pd.Timedelta(milliseconds=i * tick_ms) for i in range(len(measurements))]
            df = pd.DataFrame({
                "Timestamp": timestamps,
                "FrequencyHz": measurements
            })
            return df
        else:
            st.error(f"Failed to fetch data: {response.status_code}")
            return pd.DataFrame(columns=["Timestamp", "FrequencyHz"])
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame(columns=["Timestamp", "FrequencyHz"])

df = fetch_statnett_frequency_data(minutes_back)

if not df.empty:
    # Determine y-axis scale based on data range with padding
    min_freq = df["FrequencyHz"].min()
    max_freq = df["FrequencyHz"].max()
    padding = 0.01
    y_min = max(49.5, min_freq - padding)
    y_max = min(50.5, max_freq + padding)

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

