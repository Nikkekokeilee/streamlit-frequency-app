import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
import plotly.graph_objects as go


# Language selection
with st.sidebar:
    lang = st.selectbox("Kieli / Language", ["Suomi", "English"], index=0)

if lang == "English":
    st.set_page_config(layout="wide", page_title="Frequency (Norway & Finland)")
    st.title("📊 Frequency (Norway & Finland)")
else:
    st.set_page_config(layout="wide", page_title="Taajuus (Norja & Suomi)")
    st.title("📊 Taajuus (Norja & Suomi)")

# Tarkista API-avain
if "FINGRID_API_KEY" not in st.secrets:
    st.error("Fingridin API-avainta ei ole määritetty. Lisää se tiedostoon .streamlit/secrets.toml avaimella 'FINGRID_API_KEY'.")
    st.stop()
api_key = st.secrets["FINGRID_API_KEY"]

# Sessioasetukset ja välimuisti
if "interval" not in st.session_state:
    st.session_state.interval = "1 h"
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = False
if "last_updated" not in st.session_state:
    st.session_state.last_updated = None
if "data" not in st.session_state:
    st.session_state.data = None
if "last_fetch_time" not in st.session_state:
    st.session_state.last_fetch_time = datetime.min
if "data_cache" not in st.session_state:
    st.session_state.data_cache = {}

# Aikaväli ja mukautettu valinta
interval_minutes_map = {"10 min": 10, "30 min": 30, "1 h": 60}
now = datetime.utcnow()

# Sidebar for custom date/time selection
with st.sidebar:
    st.header("Aikaväli")
    use_custom_range = st.checkbox("Käytä mukautettua aikaväliä", value=False)
    if use_custom_range:
        default_start = now - timedelta(hours=1)
        custom_start = st.datetime_input("Aloitusaika (UTC)", value=default_start, max_value=now)
        custom_end = st.datetime_input("Lopetusaika (UTC)", value=now, min_value=custom_start, max_value=now)
        start_time = custom_start
        end_time = custom_end
    else:
        interval_minutes = interval_minutes_map[st.session_state.interval]
        start_time = now - timedelta(minutes=interval_minutes)
        end_time = now

# Hae Norjan taajuusdata
def fetch_nordic_data():
    try:
        # Statnett API only supports date, not time, so fetch for the whole day
        from_param = start_time.strftime("%Y-%m-%d")
        url = f"https://driftsdata.statnett.no/restapi/Frequency/BySecond?From={from_param}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        start_point_utc = data["StartPointUTC"]
        period_tick_ms = data["PeriodTickMs"]
        measurements = data["Measurements"]
        if not measurements:
            st.warning("Norjan datasta ei löytynyt mittauksia. Yritä myöhemmin uudelleen.")
            return pd.DataFrame()
        start_dt = datetime(1970, 1, 1) + timedelta(milliseconds=start_point_utc)
        period_sec = period_tick_ms / 1000
        df = pd.DataFrame(measurements, columns=["FrequencyHz"])
        df["Timestamp"] = [start_dt + timedelta(seconds=i * period_sec) for i in range(len(df))]
        df["Timestamp"] = pd.to_datetime(df["Timestamp"])
        df.set_index("Timestamp", inplace=True)
        df_resampled = df.resample("1min").mean().reset_index()
        # Filter to selected range
        mask = (df_resampled["Timestamp"] >= start_time) & (df_resampled["Timestamp"] <= end_time)
        return df_resampled.loc[mask].reset_index(drop=True)
    except requests.exceptions.Timeout:
        st.error("Norjan datan haku aikakatkaistiin. Tarkista verkkoyhteys ja yritä uudelleen.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Norjan datan haussa tapahtui virhe: {e}. Yritä päivittää sivu tai tarkista API-palvelun tila.")
        return pd.DataFrame()

# Hae Suomen taajuusdata
def fetch_finnish_data():
    try:
        fingrid_url = (
            f"https://data.fingrid.fi/api/datasets/177/data?"
            f"startTime={start_time.isoformat()}Z&endTime={end_time.isoformat()}Z"
        )
        headers = {"x-api-key": api_key}
        response = requests.get(fingrid_url, headers=headers, timeout=10)
        response.raise_for_status()
        fi_data = response.json()
        if "data" not in fi_data or not fi_data["data"]:
            st.warning("Suomen datasta ei löytynyt mittauksia. Yritä myöhemmin uudelleen.")
            return pd.DataFrame()
        df_fi = pd.DataFrame(fi_data["data"])
        df_fi["Timestamp"] = pd.to_datetime(df_fi["startTime"]).dt.tz_localize(None)
        df_fi["FrequencyHz"] = df_fi["value"]
        df_fi = df_fi[["Timestamp", "FrequencyHz"]]
        return df_fi
    except requests.exceptions.Timeout:
        st.error("Suomen datan haku aikakatkaistiin. Tarkista verkkoyhteys ja yritä uudelleen.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Suomen datan haussa tapahtui virhe: {e}. Yritä päivittää sivu tai tarkista API-palvelun tila.")
        return pd.DataFrame()

# Päivitä data
def update_data():
    cache_key = (str(start_time), str(end_time))
    if cache_key in st.session_state.data_cache:
        st.session_state.data = st.session_state.data_cache[cache_key]
        st.session_state.last_updated = datetime.utcnow()
        st.session_state.last_fetch_time = datetime.utcnow()
        return
    with st.spinner("Haetaan dataa..."):
        df_nordic = fetch_nordic_data()
        df_finnish = fetch_finnish_data()
        if df_nordic.empty or df_finnish.empty:
            st.warning("Datan haku epäonnistui tai dataa ei löytynyt. Tarkista yhteys ja yritä uudelleen.")
            st.session_state.data = None
            return
        df_merged = pd.merge_asof(
            df_finnish.sort_values("Timestamp"),
            df_nordic.sort_values("Timestamp"),
            on="Timestamp",
            direction="nearest",
            suffixes=("_Suomi", "_Norja")
        )
        st.session_state.data = df_merged
        st.session_state.data_cache[cache_key] = df_merged
        st.session_state.last_updated = datetime.utcnow()
        st.session_state.last_fetch_time = datetime.utcnow()

# Automaattinen päivitys ja päivitysvälin valinta
if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 60

with st.sidebar:
    st.header("Päivitysasetukset")
    st.session_state.auto_refresh = st.checkbox("Automaattipäivitys", value=st.session_state.auto_refresh)
    st.session_state.refresh_interval = st.slider("Päivitysväli (sekuntia)", min_value=10, max_value=600, value=st.session_state.refresh_interval, step=10)

refresh_countdown = None
if st.session_state.auto_refresh:
    now = datetime.utcnow()
    elapsed = (now - st.session_state.last_fetch_time).total_seconds()
    interval = st.session_state.refresh_interval
    refresh_countdown = max(0, int(interval - elapsed))
    if elapsed > interval:
        update_data()

# Haetaan data tarvittaessa ja lisää retry-nappi
if st.session_state.data is None:
    update_data()
    if st.session_state.data is None:
        if st.button("Yritä hakea data uudelleen"):
            update_data()

# Näytä päivityslaskuri
if refresh_countdown is not None and st.session_state.auto_refresh:
    st.sidebar.info(f"Seuraava päivitys: {refresh_countdown} s")


# Ohje/info-osio
with st.expander("ℹ️ Ohjeet ja tietoa" if lang=="Suomi" else "ℹ️ Help & Info"):
    if lang == "Suomi":
        st.markdown("""
**Tietolähteet:**
- Norjan taajuus: [Statnett Driftsdata](https://driftsdata.statnett.no/)
- Suomen taajuus: [Fingrid Datahub](https://data.fingrid.fi/)

**Päivitys:**
- Data päivittyy automaattisesti valitulla aikavälillä, tai voit päivittää manuaalisesti.
- Voit valita kiinteän tai mukautetun aikavälin.

**Kuvaajan tulkinta:**
- Punainen alue: taajuus alle 49.95 Hz (alhainen)
- Sininen alue: taajuus yli 50.05 Hz (korkea)
- Voit piilottaa/näyttää maiden käyrät ja tarkastella yhteenvetotilastoja.
        """)
    else:
        st.markdown("""
**Data sources:**
- Norway frequency: [Statnett Driftsdata](https://driftsdata.statnett.no/)
- Finland frequency: [Fingrid Datahub](https://data.fingrid.fi/)

**Refresh:**
- Data refreshes automatically at the selected interval, or you can refresh manually.
- You can select a fixed or custom time range.

**Chart interpretation:**
- Red area: frequency below 49.95 Hz (low)
- Blue area: frequency above 50.05 Hz (high)
- You can hide/show country curves and view summary statistics.
        """)

# Näytä kuvaaja
df_merged = st.session_state.data

# Muunna aikaleimat Suomen aikaan
helsinki_tz = pytz.timezone("Europe/Helsinki")
df_merged["Timestamp_local"] = df_merged["Timestamp"].dt.tz_localize("UTC").dt.tz_convert(helsinki_tz)

# Piirrä kuvaaja
fig = go.Figure()

# Varoitusalueet
x_start = df_merged["Timestamp_local"].min()
x_end = df_merged["Timestamp_local"].max()
y_min = df_merged[["FrequencyHz_Suomi", "FrequencyHz_Norja"]].min().min()
y_max = df_merged[["FrequencyHz_Suomi", "FrequencyHz_Norja"]].max().max()
y_axis_min = y_min - 0.05
y_axis_max = y_max + 0.05

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

# Norjan taajuus
# Norjan taajuus
fig.add_trace(go.Scatter(
    x=df_merged["Timestamp_local"],
    y=df_merged["FrequencyHz_Norja"],
    mode="lines+markers",
    name="Norja (1 min)" if lang=="Suomi" else "Norway (1 min)",
    line=dict(color="#1f77b4"),  # blue, colorblind-friendly
    visible=True,
    hovertemplate=("Aika: %{x}<br>Norja: %{y:.3f} Hz<extra></extra>" if lang=="Suomi" else "Time: %{x}<br>Norway: %{y:.3f} Hz<extra></extra>")
))

# Suomen taajuus
fig.add_trace(go.Scatter(
    x=df_merged["Timestamp_local"],
    y=df_merged["FrequencyHz_Suomi"],
    mode="lines+markers",
    name="Suomi (3 min)" if lang=="Suomi" else "Finland (3 min)",
    line=dict(color="#ff7f0e"),  # orange, colorblind-friendly
    visible=True,
    hovertemplate=("Aika: %{x}<br>Suomi: %{y:.3f} Hz<extra></extra>" if lang=="Suomi" else "Time: %{x}<br>Finland: %{y:.3f} Hz<extra></extra>")
))

# Aikajanat
fig.update_layout(
    xaxis=dict(
        title=dict(text="Aika (Suomen aika)", font=dict(size=22)),
        tickformat="%H:%M",
        domain=[0.0, 1.0],
        anchor="y",
        tickfont=dict(size=18)
    ),
    xaxis2=dict(
        title=dict(text="Aika (UTC)", font=dict(size=20)),
        overlaying="x",
        side="top",
        tickvals=df_merged["Timestamp_local"],
        ticktext=df_merged["Timestamp"].dt.strftime("%H:%M"),
        showgrid=False,
        tickfont=dict(size=16)
    ),
    yaxis=dict(
        title=dict(text="Taajuus (Hz)", font=dict(size=22)),
        range=[y_axis_min, y_axis_max],
        tickfont=dict(size=18)
    ),
    height=600,
    margin=dict(t=60, b=40, l=60, r=40),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
        font=dict(size=18)
    ),
    title=dict(
        text="Taajuusvertailu: Norja (1 min) & Suomi (3 min)",
        font=dict(size=26)
    )
)


# Toggle traces (legend click is default in Plotly, but add checkboxes for clarity)
with st.expander("Näytä/piilota maat kuvaajassa" if lang=="Suomi" else "Show/hide countries in chart"):
    show_norja = st.checkbox("Näytä Norja" if lang=="Suomi" else "Show Norway", value=True)
    show_suomi = st.checkbox("Näytä Suomi" if lang=="Suomi" else "Show Finland", value=True)
fig.data[0].visible = show_norja
fig.data[1].visible = show_suomi

st.plotly_chart(fig, use_container_width=True)

# Summary statistics
with st.expander("📈 Yhteenveto valitulta aikaväliltä" if lang=="Suomi" else "📈 Summary for selected period"):
    st.write("**Norja**" if lang=="Suomi" else "**Norway**")
    if show_norja and not df_merged["FrequencyHz_Norja"].isnull().all():
        st.write((f"Min: {df_merged['FrequencyHz_Norja'].min():.3f} Hz" if lang=="Suomi" else f"Min: {df_merged['FrequencyHz_Norja'].min():.3f} Hz"))
        st.write((f"Max: {df_merged['FrequencyHz_Norja'].max():.3f} Hz" if lang=="Suomi" else f"Max: {df_merged['FrequencyHz_Norja'].max():.3f} Hz"))
        st.write((f"Keskiarvo: {df_merged['FrequencyHz_Norja'].mean():.3f} Hz" if lang=="Suomi" else f"Mean: {df_merged['FrequencyHz_Norja'].mean():.3f} Hz"))
        st.write((f"Keskihajonta: {df_merged['FrequencyHz_Norja'].std():.3f} Hz" if lang=="Suomi" else f"Std: {df_merged['FrequencyHz_Norja'].std():.3f} Hz"))
    else:
        st.write("Ei dataa." if lang=="Suomi" else "No data.")
    st.write("**Suomi**" if lang=="Suomi" else "**Finland**")
    if show_suomi and not df_merged["FrequencyHz_Suomi"].isnull().all():
        st.write((f"Min: {df_merged['FrequencyHz_Suomi'].min():.3f} Hz" if lang=="Suomi" else f"Min: {df_merged['FrequencyHz_Suomi'].min():.3f} Hz"))
        st.write((f"Max: {df_merged['FrequencyHz_Suomi'].max():.3f} Hz" if lang=="Suomi" else f"Max: {df_merged['FrequencyHz_Suomi'].max():.3f} Hz"))
        st.write((f"Keskiarvo: {df_merged['FrequencyHz_Suomi'].mean():.3f} Hz" if lang=="Suomi" else f"Mean: {df_merged['FrequencyHz_Suomi'].mean():.3f} Hz"))
        st.write((f"Keskihajonta: {df_merged['FrequencyHz_Suomi'].std():.3f} Hz" if lang=="Suomi" else f"Std: {df_merged['FrequencyHz_Suomi'].std():.3f} Hz"))
    else:
        st.write("Ei dataa." if lang=="Suomi" else "No data.")

if st.session_state.last_updated:
    st.caption(f"Viimeisin päivitys: {st.session_state.last_updated.strftime('%H:%M:%S')} UTC")

# Asetukset alasvetovalikossa
with st.expander("⚙️ Asetukset" if lang=="Suomi" else "⚙️ Settings"):
    if not use_custom_range:
        selected_interval = st.selectbox(
            "Valitse aikaväli" if lang=="Suomi" else "Select interval",
            ["10 min", "30 min", "1 h"],
            index=["10 min", "30 min", "1 h"].index(st.session_state.interval))
        if selected_interval != st.session_state.interval:
            st.session_state.interval = selected_interval
            update_data()

    if st.button("Päivitä nyt" if lang=="Suomi" else "Update now"):
        update_data()
