import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("📊 Taajuusvertailu: Norja & Suomi")

# ✅ Tarkista API-avain
if "FINGRID_API_KEY" not in st.secrets:
    st.error("Fingridin API-avainta ei ole määritetty. Lisää se tiedostoon .streamlit/secrets.toml avaimella 'FINGRID_API_KEY'.")
    st.stop()
api_key = st.secrets["FINGRID_API_KEY"]

# ✅ Asetukset (sivupalkissa)
st.sidebar.header("⚙️ Asetukset")
interval_option = st.sidebar.selectbox("Aikaväli", ["10 min", "30 min", "1 h"], index=2)
auto_refresh = st.sidebar.checkbox("Automaattipäivitys (1 min)", value=False)

interval_minutes = {"10 min": 10, "30 min": 30, "1 h": 60}[interval_option]
now = datetime.utcnow()
start_time = now - timedelta(minutes=interval_minutes)

# ✅ Norjan taajuusdata (1 min keskiarvo)
def fetch_nordic_data():
    from_param = start_time.strftime("%Y-%m-%d")
    url = f"https://driftsdata.statnett.no/restapi/Frequency/BySecond?From={from_param}"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    start_point_utc = data["StartPointUTC"]
    period_tick_ms = data["PeriodTickMs"]
    measurements = data["Measurements"]
    if not measurements:
        return pd.DataFrame()
    start_dt = datetime(1970, 1, 1) + timedelta(milliseconds=start_point_utc)
    period_sec = period_tick_ms / 1000
    df = pd.DataFrame(measurements, columns=["FrequencyHz"])
    df["Timestamp"] = [start_dt + timedelta(seconds=i * period_sec) for i in range(len(df))]
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    df.set_index("Timestamp", inplace=True)
    df_resampled = df.resample("1min").mean().reset_index()
    return df_resampled

# ✅ Suomen taajuusdata (3 min välein)
def fetch_finnish_data():
    fingrid_url = (
        f"https://data.fingrid.fi/api/datasets/177/data?"
        f"startTime={start_time.isoformat()}Z&endTime={now.isoformat()}Z"
    )
    headers = {"x-api-key": api_key}
    response = requests.get(fingrid_url, headers=headers)
    response.raise_for_status()
    fi_data = response.json()
    df_fi = pd.DataFrame(fi_data["data"])
    df_fi["Timestamp"] = pd.to_datetime(df_fi["startTime"]).dt.tz_localize(None)
    df_fi["FrequencyHz"] = df_fi["value"]
    df_fi = df_fi[["Timestamp", "FrequencyHz"]]
    return df_fi

# ✅ Hae ja yhdistä data
try:
    df_nordic = fetch_nordic_data()
    df_finnish = fetch_finnish_data()
    df_merged = pd.merge_asof(
        df_finnish.sort_values("Timestamp"),
        df_nordic.sort_values("Timestamp"),
        on="Timestamp",
        direction="nearest",
        suffixes=("_Suomi", "_Norja")
    )
except Exception as e:
    st.error(f"Virhe datan haussa: {e}")
    st.stop()

# ✅ Muunna aikaleimat Suomen aikaan
helsinki_tz = pytz.timezone("Europe/Helsinki")
df_merged["Timestamp_local"] = df_merged["Timestamp"].dt.tz_localize("UTC").dt.tz_convert(helsinki_tz)

# ✅ Piirrä kuvaaja
fig = go.Figure()

x_start = df_merged["Timestamp_local"].min()
x_end = df_merged["Timestamp_local"].max()
y_min = df_merged[["FrequencyHz_Suomi", "FrequencyHz_Norja"]].min().min()
y_max = df_merged[["FrequencyHz_Suomi", "FrequencyHz_Norja"]].max().max()
y_axis_min = y_min - 0.05
y_axis_max = y_max + 0.05

# Varoitusalueet
fig.add_shape(
    type="rect", xref="x", yref="y",
    x0=x_start, x1=x_end,
    y0=y_axis_min, y1=min(49.95, y_axis_max),
    fillcolor="rgba(255,0,0,0.1)", line_width=0, layer="below"
)
fig.add_shape(
    type="rect", xref="x", yref="y",
    x0=x_start, x1=x_end,
    y0=max(50.05, y_axis_min), y1=y_axis_max,
    fillcolor="rgba(0,0,255,0.1)", line_width=0, layer="below"
)

# Taajuuskäyrät
fig.add_trace(go.Scatter(
    x=df_merged["Timestamp_local"], y=df_merged["FrequencyHz_Norja"],
    mode="lines+markers", name="Norja (1 min)", line=dict(color="black")
))
fig.add_trace(go.Scatter(
    x=df_merged["Timestamp_local"], y=df_merged["FrequencyHz_Suomi"],
    mode="lines+markers", name="Suomi (3 min)", line=dict(color="green")
))

# Aikajanat
fig.update_layout(
    xaxis=dict(
        title="Aika (Suomen aika)",
        tickformat="%H:%M",
        domain=[0, 1]
    ),
    xaxis2=dict(
        title="UTC-aika",
        overlaying="x",
        side="top",
        tickvals=df_merged["Timestamp_local"],
        ticktext=df_merged["Timestamp"].dt.strftime("%H:%M"),
        showgrid=False
    ),
    yaxis=dict(title="Taajuus (Hz)", range=[y_axis_min, y_axis_max]),
    height=800,
    width=1600,
    margin=dict(t=60, b=40, l=60, r=40),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    title="Taajuusvertailu: Norja (1 min) & Suomi (3 min)"
)

st.plotly_chart(fig, use_container_width=False)
